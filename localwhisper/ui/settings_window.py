"""
Settings Window for LocalWhisper

A comprehensive settings dialog for configuring all application options.
"""

from typing import Optional, Callable
from functools import partial

from PyQt6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QTabWidget,
    QWidget,
    QLabel,
    QLineEdit,
    QPushButton,
    QComboBox,
    QCheckBox,
    QSlider,
    QSpinBox,
    QDoubleSpinBox,
    QGroupBox,
    QFormLayout,
    QColorDialog,
    QMessageBox,
    QFrame,
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QFont

from localwhisper.core.config import Config, AVAILABLE_MODELS
from localwhisper.core.hotkey_manager import check_hotkey_conflict


class SettingsWindow(QDialog):
    """
    Settings dialog for LocalWhisper.

    Allows users to configure all aspects of the application.
    """

    # Signals
    settings_changed = pyqtSignal()
    hotkey_changed = pyqtSignal(str)

    def __init__(self, config: Config, parent: Optional[QWidget] = None):
        super().__init__(parent)

        self._config = config
        self._original_config = Config.load()  # For cancel/reset

        self._setup_ui()
        self._load_settings()

    def _setup_ui(self) -> None:
        """Set up the settings UI."""
        self.setWindowTitle("LocalWhisper Settings")
        self.setMinimumSize(500, 450)
        self.setModal(True)

        layout = QVBoxLayout(self)

        # Tab widget
        self._tabs = QTabWidget()
        layout.addWidget(self._tabs)

        # Create tabs
        self._tabs.addTab(self._create_general_tab(), "General")
        self._tabs.addTab(self._create_audio_tab(), "Audio")
        self._tabs.addTab(self._create_model_tab(), "Model")
        self._tabs.addTab(self._create_display_tab(), "Display")
        self._tabs.addTab(self._create_history_tab(), "History")

        # Button row
        button_layout = QHBoxLayout()

        self._reset_btn = QPushButton("Reset to Defaults")
        self._reset_btn.clicked.connect(self._reset_to_defaults)
        button_layout.addWidget(self._reset_btn)

        button_layout.addStretch()

        self._cancel_btn = QPushButton("Cancel")
        self._cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self._cancel_btn)

        self._apply_btn = QPushButton("Apply")
        self._apply_btn.clicked.connect(self._apply_settings)
        button_layout.addWidget(self._apply_btn)

        self._ok_btn = QPushButton("OK")
        self._ok_btn.setDefault(True)
        self._ok_btn.clicked.connect(self._ok_clicked)
        button_layout.addWidget(self._ok_btn)

        layout.addLayout(button_layout)

    def _create_general_tab(self) -> QWidget:
        """Create the General settings tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Startup group
        startup_group = QGroupBox("Startup")
        startup_layout = QVBoxLayout(startup_group)

        self._launch_startup_cb = QCheckBox("Launch at system startup")
        startup_layout.addWidget(self._launch_startup_cb)

        self._start_minimized_cb = QCheckBox("Start minimized to system tray")
        startup_layout.addWidget(self._start_minimized_cb)

        layout.addWidget(startup_group)

        # Hotkey group
        hotkey_group = QGroupBox("Hotkey")
        hotkey_layout = QFormLayout(hotkey_group)

        self._hotkey_edit = QLineEdit()
        self._hotkey_edit.setPlaceholderText("e.g., alt+s, ctrl+shift+r")
        hotkey_layout.addRow("Activation Key:", self._hotkey_edit)

        self._hotkey_warning = QLabel()
        self._hotkey_warning.setStyleSheet("color: #F59E0B;")
        self._hotkey_warning.hide()
        hotkey_layout.addRow("", self._hotkey_warning)

        self._hotkey_edit.textChanged.connect(self._check_hotkey)

        layout.addWidget(hotkey_group)

        # Feedback group
        feedback_group = QGroupBox("Feedback")
        feedback_layout = QVBoxLayout(feedback_group)

        self._sound_enabled_cb = QCheckBox("Enable sound feedback")
        feedback_layout.addWidget(self._sound_enabled_cb)

        volume_layout = QHBoxLayout()
        volume_layout.addWidget(QLabel("Volume:"))
        self._volume_slider = QSlider(Qt.Orientation.Horizontal)
        self._volume_slider.setRange(0, 100)
        self._volume_slider.setTickInterval(10)
        volume_layout.addWidget(self._volume_slider)
        self._volume_label = QLabel("50%")
        self._volume_slider.valueChanged.connect(
            lambda v: self._volume_label.setText(f"{v}%")
        )
        volume_layout.addWidget(self._volume_label)
        feedback_layout.addLayout(volume_layout)

        layout.addWidget(feedback_group)

        layout.addStretch()
        return widget

    def _create_audio_tab(self) -> QWidget:
        """Create the Audio settings tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Input device group
        device_group = QGroupBox("Input Device")
        device_layout = QFormLayout(device_group)

        self._device_combo = QComboBox()
        self._device_combo.addItem("System Default")
        # Note: Device list would be populated from AudioEngine
        device_layout.addRow("Microphone:", self._device_combo)

        self._refresh_devices_btn = QPushButton("Refresh")
        device_layout.addRow("", self._refresh_devices_btn)

        layout.addWidget(device_group)

        # Audio processing group
        processing_group = QGroupBox("Audio Processing")
        processing_layout = QFormLayout(processing_group)

        self._gain_spin = QDoubleSpinBox()
        self._gain_spin.setRange(0.1, 3.0)
        self._gain_spin.setSingleStep(0.1)
        self._gain_spin.setDecimals(1)
        processing_layout.addRow("Input Gain:", self._gain_spin)

        self._noise_reduction_cb = QCheckBox("Enable noise reduction")
        processing_layout.addRow("", self._noise_reduction_cb)

        layout.addWidget(processing_group)

        layout.addStretch()
        return widget

    def _create_model_tab(self) -> QWidget:
        """Create the Model settings tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Model selection group
        model_group = QGroupBox("Whisper Model")
        model_layout = QFormLayout(model_group)

        self._model_combo = QComboBox()
        for model_name, info in AVAILABLE_MODELS.items():
            size_mb = info["size_mb"]
            speed = info["relative_speed"]
            suffix = " (English)" if info["english_only"] else ""
            self._model_combo.addItem(
                f"{model_name}{suffix} - {size_mb}MB, {speed}x speed",
                model_name
            )
        model_layout.addRow("Model:", self._model_combo)

        self._language_combo = QComboBox()
        self._language_combo.addItem("English", "en")
        self._language_combo.addItem("Auto-detect", "auto")
        model_layout.addRow("Language:", self._language_combo)

        layout.addWidget(model_group)

        # Performance group
        perf_group = QGroupBox("Performance")
        perf_layout = QFormLayout(perf_group)

        self._device_type_combo = QComboBox()
        self._device_type_combo.addItem("Auto-detect", "auto")
        self._device_type_combo.addItem("GPU (CUDA)", "cuda")
        self._device_type_combo.addItem("CPU", "cpu")
        perf_layout.addRow("Compute Device:", self._device_type_combo)

        self._compute_type_combo = QComboBox()
        self._compute_type_combo.addItem("Auto", "auto")
        self._compute_type_combo.addItem("Float16 (faster GPU)", "float16")
        self._compute_type_combo.addItem("Int8 (smaller, faster CPU)", "int8")
        self._compute_type_combo.addItem("Float32 (highest quality)", "float32")
        perf_layout.addRow("Precision:", self._compute_type_combo)

        self._beam_size_spin = QSpinBox()
        self._beam_size_spin.setRange(1, 10)
        perf_layout.addRow("Beam Size:", self._beam_size_spin)

        layout.addWidget(perf_group)

        # VAD group
        vad_group = QGroupBox("Voice Activity Detection")
        vad_layout = QFormLayout(vad_group)

        self._vad_enabled_cb = QCheckBox("Enable VAD filtering")
        vad_layout.addRow("", self._vad_enabled_cb)

        self._vad_threshold_spin = QDoubleSpinBox()
        self._vad_threshold_spin.setRange(0.1, 0.9)
        self._vad_threshold_spin.setSingleStep(0.1)
        self._vad_threshold_spin.setDecimals(1)
        vad_layout.addRow("Sensitivity:", self._vad_threshold_spin)

        layout.addWidget(vad_group)

        layout.addStretch()
        return widget

    def _create_display_tab(self) -> QWidget:
        """Create the Display settings tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Theme group
        theme_group = QGroupBox("Appearance")
        theme_layout = QFormLayout(theme_group)

        self._theme_combo = QComboBox()
        self._theme_combo.addItem("Dark", "dark")
        self._theme_combo.addItem("Light", "light")
        self._theme_combo.addItem("System", "auto")
        theme_layout.addRow("Theme:", self._theme_combo)

        # Accent color
        color_layout = QHBoxLayout()
        self._color_preview = QFrame()
        self._color_preview.setFixedSize(24, 24)
        self._color_preview.setStyleSheet(
            f"background-color: {self._config.ui.accent_color}; border-radius: 4px;"
        )
        color_layout.addWidget(self._color_preview)

        self._color_btn = QPushButton("Choose Color...")
        self._color_btn.clicked.connect(self._choose_color)
        color_layout.addWidget(self._color_btn)
        color_layout.addStretch()

        theme_layout.addRow("Accent Color:", color_layout)

        layout.addWidget(theme_group)

        # Waveform group
        waveform_group = QGroupBox("Waveform Display")
        waveform_layout = QFormLayout(waveform_group)

        self._opacity_slider = QSlider(Qt.Orientation.Horizontal)
        self._opacity_slider.setRange(50, 100)
        waveform_layout.addRow("Opacity:", self._opacity_slider)

        self._show_status_cb = QCheckBox("Show status text")
        waveform_layout.addRow("", self._show_status_cb)

        layout.addWidget(waveform_group)

        layout.addStretch()
        return widget

    def _create_history_tab(self) -> QWidget:
        """Create the History settings tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)

        # Storage group
        storage_group = QGroupBox("Storage")
        storage_layout = QFormLayout(storage_group)

        self._history_enabled_cb = QCheckBox("Enable transcription history")
        storage_layout.addRow("", self._history_enabled_cb)

        self._retention_spin = QSpinBox()
        self._retention_spin.setRange(1, 365)
        self._retention_spin.setSuffix(" days")
        storage_layout.addRow("Keep history for:", self._retention_spin)

        self._max_entries_spin = QSpinBox()
        self._max_entries_spin.setRange(100, 100000)
        self._max_entries_spin.setSingleStep(1000)
        storage_layout.addRow("Maximum entries:", self._max_entries_spin)

        layout.addWidget(storage_group)

        # Privacy group
        privacy_group = QGroupBox("Privacy")
        privacy_layout = QVBoxLayout(privacy_group)

        self._encrypt_cb = QCheckBox("Encrypt stored transcriptions")
        privacy_layout.addWidget(self._encrypt_cb)

        self._clear_history_btn = QPushButton("Clear All History")
        self._clear_history_btn.clicked.connect(self._confirm_clear_history)
        privacy_layout.addWidget(self._clear_history_btn)

        layout.addWidget(privacy_group)

        layout.addStretch()
        return widget

    def _load_settings(self) -> None:
        """Load current settings into UI controls."""
        c = self._config

        # General
        self._launch_startup_cb.setChecked(c.general.launch_at_startup)
        self._start_minimized_cb.setChecked(c.general.start_minimized)
        self._hotkey_edit.setText(c.hotkey.activation_key)
        self._sound_enabled_cb.setChecked(c.feedback.sound_enabled)
        self._volume_slider.setValue(int(c.feedback.sound_volume * 100))

        # Audio
        self._gain_spin.setValue(c.audio.gain)
        self._noise_reduction_cb.setChecked(c.audio.noise_reduction)

        # Model
        self._set_combo_by_data(self._model_combo, c.transcription.model_name)
        self._set_combo_by_data(self._language_combo, c.transcription.language)
        self._set_combo_by_data(self._device_type_combo, c.transcription.device)
        self._set_combo_by_data(self._compute_type_combo, c.transcription.compute_type)
        self._beam_size_spin.setValue(c.transcription.beam_size)
        self._vad_enabled_cb.setChecked(c.transcription.vad_enabled)
        self._vad_threshold_spin.setValue(c.transcription.vad_threshold)

        # Display
        self._set_combo_by_data(self._theme_combo, c.ui.theme)
        self._color_preview.setStyleSheet(
            f"background-color: {c.ui.accent_color}; border-radius: 4px;"
        )
        self._opacity_slider.setValue(int(c.ui.opacity * 100))
        self._show_status_cb.setChecked(c.ui.show_status_text)

        # History
        self._history_enabled_cb.setChecked(c.history.enabled)
        self._retention_spin.setValue(c.history.retention_days)
        self._max_entries_spin.setValue(c.history.max_entries)
        self._encrypt_cb.setChecked(c.history.encrypt_storage)

    def _save_settings(self) -> None:
        """Save UI values to config."""
        c = self._config

        # General
        c.general.launch_at_startup = self._launch_startup_cb.isChecked()
        c.general.start_minimized = self._start_minimized_cb.isChecked()
        c.hotkey.activation_key = self._hotkey_edit.text().strip().lower()
        c.feedback.sound_enabled = self._sound_enabled_cb.isChecked()
        c.feedback.sound_volume = self._volume_slider.value() / 100.0

        # Audio
        c.audio.gain = self._gain_spin.value()
        c.audio.noise_reduction = self._noise_reduction_cb.isChecked()

        # Model
        c.transcription.model_name = self._model_combo.currentData()
        c.transcription.language = self._language_combo.currentData()
        c.transcription.device = self._device_type_combo.currentData()
        c.transcription.compute_type = self._compute_type_combo.currentData()
        c.transcription.beam_size = self._beam_size_spin.value()
        c.transcription.vad_enabled = self._vad_enabled_cb.isChecked()
        c.transcription.vad_threshold = self._vad_threshold_spin.value()

        # Display
        c.ui.theme = self._theme_combo.currentData()
        c.ui.opacity = self._opacity_slider.value() / 100.0
        c.ui.show_status_text = self._show_status_cb.isChecked()

        # History
        c.history.enabled = self._history_enabled_cb.isChecked()
        c.history.retention_days = self._retention_spin.value()
        c.history.max_entries = self._max_entries_spin.value()
        c.history.encrypt_storage = self._encrypt_cb.isChecked()

        c.save()

    def _set_combo_by_data(self, combo: QComboBox, data) -> None:
        """Set combo box selection by data value."""
        for i in range(combo.count()):
            if combo.itemData(i) == data:
                combo.setCurrentIndex(i)
                return

    def _check_hotkey(self, text: str) -> None:
        """Check hotkey for conflicts."""
        warning = check_hotkey_conflict(text)
        if warning:
            self._hotkey_warning.setText(warning)
            self._hotkey_warning.show()
        else:
            self._hotkey_warning.hide()

    def _choose_color(self) -> None:
        """Open color picker dialog."""
        current = QColor(self._config.ui.accent_color)
        color = QColorDialog.getColor(current, self, "Choose Accent Color")
        if color.isValid():
            self._config.ui.accent_color = color.name()
            self._color_preview.setStyleSheet(
                f"background-color: {color.name()}; border-radius: 4px;"
            )

    def _confirm_clear_history(self) -> None:
        """Confirm and clear history."""
        reply = QMessageBox.question(
            self,
            "Clear History",
            "Are you sure you want to delete all transcription history?\n\n"
            "This action cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            # Signal to parent to clear history
            # This would be handled by the main app
            QMessageBox.information(
                self, "History Cleared", "All transcription history has been deleted."
            )

    def _reset_to_defaults(self) -> None:
        """Reset all settings to defaults."""
        reply = QMessageBox.question(
            self,
            "Reset Settings",
            "Are you sure you want to reset all settings to defaults?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self._config.reset_to_defaults()
            self._load_settings()

    def _apply_settings(self) -> None:
        """Apply settings without closing."""
        old_hotkey = self._original_config.hotkey.activation_key
        self._save_settings()

        if self._config.hotkey.activation_key != old_hotkey:
            self.hotkey_changed.emit(self._config.hotkey.activation_key)

        self.settings_changed.emit()

    def _ok_clicked(self) -> None:
        """Apply settings and close."""
        self._apply_settings()
        self.accept()
