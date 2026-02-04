"""
Tests for Configuration Manager
"""

import pytest
import json
import tempfile
from pathlib import Path

from localwhisper.core.config import (
    Config,
    GeneralSettings,
    AudioSettings,
    TranscriptionSettings,
    HotkeySettings,
    UISettings,
    FeedbackSettings,
    HistorySettings,
    get_config_dir,
    get_data_dir,
    get_cache_dir,
    AVAILABLE_MODELS,
)


class TestConfigDirectories:
    """Tests for config directory functions."""

    def test_get_config_dir_returns_path(self):
        """Config dir should return a Path object."""
        result = get_config_dir()
        assert isinstance(result, Path)

    def test_get_data_dir_returns_path(self):
        """Data dir should return a Path object."""
        result = get_data_dir()
        assert isinstance(result, Path)

    def test_get_cache_dir_returns_path(self):
        """Cache dir should return a Path object."""
        result = get_cache_dir()
        assert isinstance(result, Path)


class TestAudioSettings:
    """Tests for AudioSettings dataclass."""

    def test_default_values(self):
        """AudioSettings should have correct defaults."""
        settings = AudioSettings()
        assert settings.sample_rate == 16000
        assert settings.channels == 1
        assert settings.chunk_size == 1600
        assert settings.input_device is None
        assert settings.gain == 1.0
        assert settings.noise_reduction is True

    def test_custom_values(self):
        """AudioSettings should accept custom values."""
        settings = AudioSettings(
            sample_rate=44100,
            channels=2,
            gain=1.5,
        )
        assert settings.sample_rate == 44100
        assert settings.channels == 2
        assert settings.gain == 1.5


class TestTranscriptionSettings:
    """Tests for TranscriptionSettings dataclass."""

    def test_default_values(self):
        """TranscriptionSettings should have correct defaults."""
        settings = TranscriptionSettings()
        assert settings.model_name == "turbo"
        assert settings.language == "en"
        assert settings.compute_type == "auto"
        assert settings.device == "auto"
        assert settings.beam_size == 5
        assert settings.vad_enabled is True
        assert settings.vad_threshold == 0.5

    def test_custom_model(self):
        """TranscriptionSettings should accept custom model."""
        settings = TranscriptionSettings(model_name="small.en")
        assert settings.model_name == "small.en"


class TestHotkeySettings:
    """Tests for HotkeySettings dataclass."""

    def test_default_values(self):
        """HotkeySettings should have correct defaults."""
        settings = HotkeySettings()
        assert settings.activation_key == "ctrl+alt+r"

    def test_custom_hotkey(self):
        """HotkeySettings should accept custom hotkey."""
        settings = HotkeySettings(activation_key="ctrl+shift+r")
        assert settings.activation_key == "ctrl+shift+r"


class TestUISettings:
    """Tests for UISettings dataclass."""

    def test_default_values(self):
        """UISettings should have correct defaults."""
        settings = UISettings()
        assert settings.theme == "dark"
        assert settings.accent_color == "#3B82F6"
        assert settings.waveform_height == 60
        assert settings.waveform_width == 400
        assert settings.opacity == 0.9
        assert settings.show_status_text is True
        assert settings.animation_fps == 60


class TestHistorySettings:
    """Tests for HistorySettings dataclass."""

    def test_default_values(self):
        """HistorySettings should have correct defaults."""
        settings = HistorySettings()
        assert settings.enabled is True
        assert settings.retention_days == 30
        assert settings.encrypt_storage is False
        assert settings.max_entries == 10000


class TestConfig:
    """Tests for main Config class."""

    def test_default_config(self):
        """Config should have all default sub-settings."""
        config = Config()
        assert isinstance(config.general, GeneralSettings)
        assert isinstance(config.audio, AudioSettings)
        assert isinstance(config.transcription, TranscriptionSettings)
        assert isinstance(config.hotkey, HotkeySettings)
        assert isinstance(config.ui, UISettings)
        assert isinstance(config.feedback, FeedbackSettings)
        assert isinstance(config.history, HistorySettings)

    def test_save_and_load(self):
        """Config should save and load correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "test_config.json"

            # Create and save config
            config = Config()
            config._config_path = config_path
            config.hotkey.activation_key = "ctrl+shift+t"
            config.ui.accent_color = "#FF0000"
            config.save()

            # Load config
            loaded = Config.load(config_path)
            assert loaded.hotkey.activation_key == "ctrl+shift+t"
            assert loaded.ui.accent_color == "#FF0000"

    def test_reset_to_defaults(self):
        """Config should reset to defaults."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "test_config.json"

            config = Config()
            config._config_path = config_path
            config.hotkey.activation_key = "custom+key"
            config.reset_to_defaults()

            assert config.hotkey.activation_key == "alt+s"

    def test_load_missing_file(self):
        """Config.load should return defaults for missing file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "nonexistent.json"
            config = Config.load(config_path)
            assert config.hotkey.activation_key == "alt+s"

    def test_load_corrupted_file(self):
        """Config.load should return defaults for corrupted file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "corrupted.json"
            config_path.write_text("not valid json {{{")

            config = Config.load(config_path)
            assert config.hotkey.activation_key == "alt+s"


class TestAvailableModels:
    """Tests for AVAILABLE_MODELS constant."""

    def test_models_exist(self):
        """AVAILABLE_MODELS should contain expected models."""
        assert "turbo" in AVAILABLE_MODELS
        assert "tiny.en" in AVAILABLE_MODELS
        assert "base.en" in AVAILABLE_MODELS
        assert "small.en" in AVAILABLE_MODELS
        assert "large-v3" in AVAILABLE_MODELS

    def test_model_properties(self):
        """Each model should have required properties."""
        for model_name, info in AVAILABLE_MODELS.items():
            assert "size_mb" in info
            assert "vram_gb" in info
            assert "relative_speed" in info
            assert "english_only" in info
            assert isinstance(info["size_mb"], int)
            assert isinstance(info["english_only"], bool)
