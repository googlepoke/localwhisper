"""
Audio Feedback for LocalWhisper

Handles playing audio cues for recording start/stop events.
"""

import threading
import platform
from pathlib import Path
from typing import Optional
import math
import struct

from localwhisper.core.config import FeedbackSettings, get_data_dir


class AudioFeedback:
    """
    Audio feedback player for UI events.

    Plays subtle audio cues when recording starts and stops.
    Uses a simple synthesized sound if no custom sounds are available.
    """

    def __init__(self, settings: Optional[FeedbackSettings] = None):
        """
        Initialize audio feedback.

        Args:
            settings: Feedback configuration settings
        """
        self.settings = settings or FeedbackSettings()
        self._player = None

        # Try to set up audio playback
        self._setup_player()

    def _setup_player(self) -> None:
        """Set up the audio player backend."""
        # Try different audio backends
        try:
            import sounddevice as sd
            self._backend = "sounddevice"
            return
        except ImportError:
            pass

        try:
            import pyaudio
            self._backend = "pyaudio"
            self._pyaudio = pyaudio.PyAudio()
            return
        except ImportError:
            pass

        # Windows fallback using built-in winsound
        if platform.system() == "Windows":
            try:
                import winsound
                self._backend = "winsound"
                return
            except ImportError:
                pass

        self._backend = None

    def _generate_tone(
        self,
        frequency: float,
        duration: float,
        sample_rate: int = 44100,
        fade: bool = True,
    ) -> bytes:
        """
        Generate a simple sine wave tone.

        Args:
            frequency: Tone frequency in Hz
            duration: Duration in seconds
            sample_rate: Sample rate
            fade: Whether to apply fade in/out

        Returns:
            Audio data as bytes
        """
        num_samples = int(sample_rate * duration)
        samples = []

        for i in range(num_samples):
            t = i / sample_rate

            # Sine wave
            sample = math.sin(2 * math.pi * frequency * t)

            # Apply envelope (fade in/out)
            if fade:
                fade_samples = int(sample_rate * 0.01)  # 10ms fade
                if i < fade_samples:
                    sample *= i / fade_samples
                elif i > num_samples - fade_samples:
                    sample *= (num_samples - i) / fade_samples

            # Volume
            sample *= self.settings.sound_volume * 0.3  # Keep it subtle

            # Convert to 16-bit
            samples.append(int(sample * 32767))

        return struct.pack(f"{len(samples)}h", *samples)

    def _generate_start_sound(self) -> bytes:
        """Generate the recording start sound (ascending tone)."""
        sample_rate = 44100
        samples = []

        # Two-tone ascending
        for freq, duration in [(440, 0.05), (550, 0.05)]:
            num_samples = int(sample_rate * duration)
            for i in range(num_samples):
                t = i / sample_rate
                sample = math.sin(2 * math.pi * freq * t)

                # Fade
                fade_samples = int(sample_rate * 0.01)
                if i < fade_samples:
                    sample *= i / fade_samples
                elif i > num_samples - fade_samples:
                    sample *= (num_samples - i) / fade_samples

                sample *= self.settings.sound_volume * 0.3
                samples.append(int(sample * 32767))

        return struct.pack(f"{len(samples)}h", *samples)

    def _generate_stop_sound(self) -> bytes:
        """Generate the recording stop sound (descending tone)."""
        sample_rate = 44100
        samples = []

        # Two-tone descending
        for freq, duration in [(550, 0.05), (440, 0.05)]:
            num_samples = int(sample_rate * duration)
            for i in range(num_samples):
                t = i / sample_rate
                sample = math.sin(2 * math.pi * freq * t)

                # Fade
                fade_samples = int(sample_rate * 0.01)
                if i < fade_samples:
                    sample *= i / fade_samples
                elif i > num_samples - fade_samples:
                    sample *= (num_samples - i) / fade_samples

                sample *= self.settings.sound_volume * 0.3
                samples.append(int(sample * 32767))

        return struct.pack(f"{len(samples)}h", *samples)

    def _play_audio(self, audio_data: bytes, frequency: int = 440, duration_ms: int = 100) -> None:
        """
        Play audio data.

        Args:
            audio_data: Raw audio bytes (16-bit, 44100Hz, mono)
            frequency: Frequency for winsound fallback
            duration_ms: Duration in ms for winsound fallback
        """
        if not self.settings.sound_enabled:
            return

        if self._backend == "sounddevice":
            self._play_sounddevice(audio_data)
        elif self._backend == "pyaudio":
            self._play_pyaudio(audio_data)
        elif self._backend == "winsound":
            self._play_winsound(frequency, duration_ms)

    def _play_sounddevice(self, audio_data: bytes) -> None:
        """Play using sounddevice."""
        import sounddevice as sd
        import numpy as np

        # Convert bytes to numpy array
        samples = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32) / 32767.0

        # Play non-blocking
        def play_thread():
            try:
                sd.play(samples, samplerate=44100)
                sd.wait()
            except Exception as e:
                print(f"Audio playback error: {e}")

        threading.Thread(target=play_thread, daemon=True).start()

    def _play_pyaudio(self, audio_data: bytes) -> None:
        """Play using PyAudio."""
        import pyaudio

        def play_thread():
            try:
                stream = self._pyaudio.open(
                    format=pyaudio.paInt16,
                    channels=1,
                    rate=44100,
                    output=True,
                )
                stream.write(audio_data)
                stream.stop_stream()
                stream.close()
            except Exception as e:
                print(f"Audio playback error: {e}")

        threading.Thread(target=play_thread, daemon=True).start()

    def _play_winsound(self, frequency: int, duration_ms: int) -> None:
        """Play using Windows winsound (built-in, no dependencies)."""
        import winsound

        def play_thread():
            try:
                # Apply volume by adjusting duration (winsound doesn't support volume)
                adjusted_duration = int(duration_ms * self.settings.sound_volume)
                if adjusted_duration > 0:
                    winsound.Beep(frequency, adjusted_duration)
            except Exception as e:
                print(f"Audio playback error: {e}")

        threading.Thread(target=play_thread, daemon=True).start()

    def play_start(self) -> None:
        """Play the recording start sound."""
        if not self.settings.sound_enabled:
            return

        audio = self._generate_start_sound()
        # Ascending tone: 550Hz for winsound fallback
        self._play_audio(audio, frequency=550, duration_ms=100)

    def play_stop(self) -> None:
        """Play the recording stop sound."""
        if not self.settings.sound_enabled:
            return

        audio = self._generate_stop_sound()
        # Descending tone: 440Hz for winsound fallback
        self._play_audio(audio, frequency=440, duration_ms=100)

    def play_error(self) -> None:
        """Play an error sound."""
        if not self.settings.sound_enabled:
            return

        # Lower tone for error
        audio = self._generate_tone(220, 0.15)
        self._play_audio(audio, frequency=220, duration_ms=150)

    def play_success(self) -> None:
        """Play a success sound."""
        if not self.settings.sound_enabled:
            return

        # Higher, pleasant tone for success
        audio = self._generate_tone(660, 0.1)
        self._play_audio(audio, frequency=660, duration_ms=100)

    def set_enabled(self, enabled: bool) -> None:
        """Enable or disable sound feedback."""
        self.settings.sound_enabled = enabled

    def set_volume(self, volume: float) -> None:
        """Set the sound volume (0.0 to 1.0)."""
        self.settings.sound_volume = max(0.0, min(1.0, volume))

    def shutdown(self) -> None:
        """Clean up resources."""
        if self._backend == "pyaudio" and hasattr(self, "_pyaudio"):
            self._pyaudio.terminate()
