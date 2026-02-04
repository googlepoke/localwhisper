"""
LocalWhisper Application

Main application class that coordinates all components.
"""

import sys
import threading
from typing import Optional
from pathlib import Path

from PyQt6.QtWidgets import QApplication, QMessageBox
from PyQt6.QtCore import QObject, pyqtSignal, QTimer

from localwhisper.core.config import Config
from localwhisper.core.audio_engine import AudioEngine, AudioEngineError
from localwhisper.core.transcription_engine import TranscriptionEngine, TranscriptionEngineError
from localwhisper.core.hotkey_manager import HotkeyManager
from localwhisper.core.text_injector import TextInjector
from localwhisper.core.history_manager import HistoryManager
from localwhisper.core.audio_feedback import AudioFeedback
from localwhisper.ui.waveform_widget import WaveformOverlay
from localwhisper.ui.tray_icon import TrayIcon, TrayState
from localwhisper.ui.settings_window import SettingsWindow
from localwhisper.ui.history_window import HistoryWindow


class LocalWhisperApp(QObject):
    """
    Main application controller.

    Coordinates all components: audio capture, transcription, UI, and text injection.
    """

    # Internal signals for thread-safe UI updates
    _amplitude_signal = pyqtSignal(float)
    _transcription_complete = pyqtSignal(str)
    _transcription_error = pyqtSignal(str)
    _recording_started = pyqtSignal()
    _recording_stopped = pyqtSignal()

    def __init__(self):
        super().__init__()

        # Load configuration
        self._config = Config.load()

        # Initialize components
        self._audio_engine: Optional[AudioEngine] = None
        self._transcription_engine: Optional[TranscriptionEngine] = None
        self._hotkey_manager: Optional[HotkeyManager] = None
        self._text_injector: Optional[TextInjector] = None
        self._history_manager: Optional[HistoryManager] = None
        self._audio_feedback: Optional[AudioFeedback] = None

        # UI components
        self._waveform_overlay: Optional[WaveformOverlay] = None
        self._tray_icon: Optional[TrayIcon] = None
        self._settings_window: Optional[SettingsWindow] = None
        self._history_window: Optional[HistoryWindow] = None

        # State
        self._is_recording = False
        self._is_processing = False

        # Connect internal signals
        self._amplitude_signal.connect(self._on_amplitude_update)
        self._transcription_complete.connect(self._on_transcription_complete)
        self._transcription_error.connect(self._on_transcription_error)
        self._recording_started.connect(self._on_recording_started)
        self._recording_stopped.connect(self._on_recording_stopped)

    def initialize(self) -> bool:
        """
        Initialize all application components.

        Returns:
            True if successful, False otherwise
        """
        try:
            # Initialize core components
            self._audio_engine = AudioEngine(self._config.audio)
            self._audio_engine.initialize()
            self._audio_engine.set_amplitude_callback(self._on_amplitude)

            self._transcription_engine = TranscriptionEngine(self._config.transcription)

            self._hotkey_manager = HotkeyManager(
                hotkey=self._config.hotkey.activation_key,
                on_toggle=self._toggle_recording,
            )

            self._text_injector = TextInjector()

            self._history_manager = HistoryManager(self._config.history)
            self._history_manager.initialize()

            self._audio_feedback = AudioFeedback(self._config.feedback)

            # Initialize UI components
            self._waveform_overlay = WaveformOverlay(self._config.ui)

            self._tray_icon = TrayIcon()
            self._tray_icon.show_requested.connect(self._show_main_window)
            self._tray_icon.settings_requested.connect(self._show_settings)
            self._tray_icon.history_requested.connect(self._show_history)
            self._tray_icon.quit_requested.connect(self._quit)
            self._tray_icon.toggle_recording.connect(self._toggle_recording)

            # Show tray icon
            self._tray_icon.show()

            # Start hotkey listener
            self._hotkey_manager.start()

            # Show welcome message on first run
            if self._config.general.first_run:
                self._config.general.first_run = False
                self._config.save()
                self._tray_icon.show_info(
                    f"LocalWhisper is ready!\n"
                    f"Press {self._config.hotkey.activation_key.upper()} to start recording."
                )

            # Pre-load model in background
            self._preload_model()

            return True

        except AudioEngineError as e:
            QMessageBox.critical(
                None,
                "Audio Error",
                f"Failed to initialize audio:\n{str(e)}\n\n"
                "Please check your microphone connection.",
            )
            return False
        except Exception as e:
            QMessageBox.critical(
                None,
                "Initialization Error",
                f"Failed to initialize LocalWhisper:\n{str(e)}",
            )
            return False

    def _preload_model(self) -> None:
        """Pre-load the transcription model in background."""
        def load_thread():
            try:
                self._transcription_engine.load_model()
            except TranscriptionEngineError as e:
                # Will be loaded on first use
                print(f"Model pre-load skipped: {e}")

        threading.Thread(target=load_thread, daemon=True).start()

    def _on_amplitude(self, amplitude: float) -> None:
        """Handle amplitude update from audio engine (called from audio thread)."""
        self._amplitude_signal.emit(amplitude)

    def _on_amplitude_update(self, amplitude: float) -> None:
        """Handle amplitude update in main thread."""
        if self._waveform_overlay and self._waveform_overlay.isVisible():
            self._waveform_overlay.add_amplitude(amplitude)

    def _on_recording_started(self) -> None:
        """Handle recording start in main thread."""
        self._is_recording = True

        # Play start sound
        if self._audio_feedback:
            self._audio_feedback.play_start()

        # Show waveform overlay
        if self._waveform_overlay:
            self._waveform_overlay.show_overlay()

        # Update tray icon
        if self._tray_icon:
            self._tray_icon.set_state(TrayState.RECORDING)

        # Start audio capture
        if self._audio_engine:
            self._audio_engine.start_recording()

    def _on_recording_stopped(self) -> None:
        """Handle recording stop in main thread."""
        if not self._is_recording:
            return

        self._is_recording = False
        self._is_processing = True

        # Play stop sound
        if self._audio_feedback:
            self._audio_feedback.play_stop()

        # Update UI to processing state
        if self._waveform_overlay:
            self._waveform_overlay.set_processing()

        if self._tray_icon:
            self._tray_icon.set_state(TrayState.PROCESSING)

        # Stop audio capture and get audio
        audio = self._audio_engine.stop_recording() if self._audio_engine else None

        if audio is None or len(audio) < 1600:  # Less than 100ms
            self._is_processing = False
            if self._waveform_overlay:
                self._waveform_overlay.hide_overlay()
            if self._tray_icon:
                self._tray_icon.set_state(TrayState.IDLE)
            return

        # Transcribe in background
        def transcribe_thread():
            try:
                result = self._transcription_engine.transcribe(audio)
                self._transcription_complete.emit(result.text)
            except Exception as e:
                self._transcription_error.emit(str(e))

        threading.Thread(target=transcribe_thread, daemon=True).start()

    def _on_transcription_complete(self, text: str) -> None:
        """Handle successful transcription in main thread."""
        self._is_processing = False

        # Show success in overlay
        if self._waveform_overlay:
            self._waveform_overlay.show_success()

        # Update tray icon
        if self._tray_icon:
            self._tray_icon.set_state(TrayState.IDLE)

        if not text.strip():
            return

        # Inject the transcribed text (uses clipboard paste for smooth output)
        if self._text_injector:
            # Small delay to let the overlay hide and focus return to original app
            QTimer.singleShot(150, lambda: self._text_injector.inject_text(text))

        # Save to history
        if self._history_manager and self._transcription_engine:
            self._history_manager.add_entry(
                text=text,
                duration=len(self._audio_engine.get_current_audio()) / 16000 if self._audio_engine else 0,
                confidence=0.9,  # Approximate
                language=self._config.transcription.language,
                model=self._config.transcription.model_name,
            )

    def _on_transcription_error(self, error: str) -> None:
        """Handle transcription error in main thread."""
        self._is_processing = False

        # Play error sound
        if self._audio_feedback:
            self._audio_feedback.play_error()

        # Show error in overlay
        if self._waveform_overlay:
            self._waveform_overlay.show_error(f"Transcription failed: {error}")

        # Update tray icon
        if self._tray_icon:
            self._tray_icon.set_state(TrayState.ERROR)
            self._tray_icon.show_error(f"Transcription failed: {error}")

            # Reset to idle after delay
            QTimer.singleShot(3000, lambda: self._tray_icon.set_state(TrayState.IDLE))

    def _toggle_recording(self) -> None:
        """Toggle recording state - called when hotkey is pressed."""
        if self._is_processing:
            # Don't toggle during processing
            return
        
        if self._is_recording:
            # Stop recording
            self._recording_stopped.emit()
        else:
            # Start recording
            self._recording_started.emit()

    def _show_main_window(self) -> None:
        """Show the main application window."""
        # For now, just show settings
        self._show_settings()

    def _show_settings(self) -> None:
        """Show the settings window."""
        if self._settings_window is None:
            self._settings_window = SettingsWindow(self._config)
            self._settings_window.settings_changed.connect(self._on_settings_changed)
            self._settings_window.hotkey_changed.connect(self._on_hotkey_changed)

        self._settings_window.show()
        self._settings_window.raise_()
        self._settings_window.activateWindow()

    def _show_history(self) -> None:
        """Show the history window."""
        if self._history_window is None:
            self._history_window = HistoryWindow(self._history_manager)

        self._history_window.refresh()
        self._history_window.show()
        self._history_window.raise_()
        self._history_window.activateWindow()

    def _on_settings_changed(self) -> None:
        """Handle settings change."""
        # Reload config
        self._config = Config.load()

        # Update components
        if self._audio_engine:
            self._audio_engine.settings = self._config.audio

        if self._audio_feedback:
            self._audio_feedback.settings = self._config.feedback

        if self._waveform_overlay:
            self._waveform_overlay.set_accent_color(self._config.ui.accent_color)
            self._waveform_overlay.set_background_color(self._config.ui.waveform_background_color)
            self._waveform_overlay.set_background_alpha(self._config.ui.waveform_background_alpha)
            self._waveform_overlay.set_line_thickness(self._config.ui.waveform_line_thickness)
            self._waveform_overlay.set_sensitivity(self._config.ui.waveform_sensitivity)
            self._waveform_overlay.set_width(self._config.ui.waveform_width)
            self._waveform_overlay.set_always_on_top(self._config.ui.waveform_always_on_top)

    def _on_hotkey_changed(self, new_hotkey: str) -> None:
        """Handle hotkey change."""
        if self._hotkey_manager:
            self._hotkey_manager.set_hotkey(new_hotkey)

    def _quit(self) -> None:
        """Quit the application."""
        self.shutdown()
        QApplication.quit()

    def shutdown(self) -> None:
        """Shutdown all components."""
        # Stop hotkey listener
        if self._hotkey_manager:
            self._hotkey_manager.stop()

        # Stop any ongoing recording
        if self._is_recording and self._audio_engine:
            self._audio_engine.stop_recording()

        # Shutdown components
        if self._audio_engine:
            self._audio_engine.shutdown()

        if self._transcription_engine:
            self._transcription_engine.unload_model()

        if self._history_manager:
            self._history_manager.shutdown()

        if self._audio_feedback:
            self._audio_feedback.shutdown()

        # Hide UI
        if self._waveform_overlay:
            self._waveform_overlay.hide()

        if self._tray_icon:
            self._tray_icon.hide()

    def run(self) -> int:
        """
        Run the application.

        Returns:
            Exit code
        """
        if not self.initialize():
            return 1

        return 0


def main():
    """Main entry point."""
    # Create Qt application
    app = QApplication(sys.argv)
    app.setApplicationName("LocalWhisper")
    app.setOrganizationName("LocalWhisper")
    app.setQuitOnLastWindowClosed(False)  # Keep running in tray

    # Set application style
    app.setStyle("Fusion")

    # Create and run main app
    local_whisper = LocalWhisperApp()
    exit_code = local_whisper.run()

    if exit_code != 0:
        return exit_code

    # Run event loop
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
