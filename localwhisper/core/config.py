"""
Configuration Manager for LocalWhisper

Handles all application settings with persistence to JSON files.
"""

import json
import os
import platform
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional, Tuple


def get_config_dir() -> Path:
    """Get platform-appropriate configuration directory."""
    system = platform.system()
    if system == "Windows":
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
        return Path(base) / "LocalWhisper"
    elif system == "Darwin":  # macOS
        return Path.home() / "Library" / "Application Support" / "LocalWhisper"
    else:  # Linux and others
        xdg_config = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
        return Path(xdg_config) / "localwhisper"


def get_data_dir() -> Path:
    """Get platform-appropriate data directory."""
    system = platform.system()
    if system == "Windows":
        base = os.environ.get("LOCALAPPDATA", os.environ.get("APPDATA", os.path.expanduser("~")))
        return Path(base) / "LocalWhisper"
    elif system == "Darwin":  # macOS
        return Path.home() / "Library" / "Application Support" / "LocalWhisper"
    else:  # Linux and others
        xdg_data = os.environ.get("XDG_DATA_HOME", os.path.expanduser("~/.local/share"))
        return Path(xdg_data) / "localwhisper"


def get_cache_dir() -> Path:
    """Get platform-appropriate cache directory for models."""
    system = platform.system()
    if system == "Windows":
        base = os.environ.get("LOCALAPPDATA", os.environ.get("APPDATA", os.path.expanduser("~")))
        return Path(base) / "LocalWhisper" / "models"
    elif system == "Darwin":  # macOS
        return Path.home() / "Library" / "Caches" / "LocalWhisper" / "models"
    else:  # Linux and others
        xdg_cache = os.environ.get("XDG_CACHE_HOME", os.path.expanduser("~/.cache"))
        return Path(xdg_cache) / "localwhisper" / "models"


@dataclass
class AudioSettings:
    """Audio capture settings."""
    sample_rate: int = 16000  # Whisper native sample rate
    channels: int = 1  # Mono
    chunk_size: int = 1600  # 100ms at 16kHz
    input_device: Optional[str] = None  # None = system default
    gain: float = 1.0  # Gain multiplier
    noise_reduction: bool = True


@dataclass
class TranscriptionSettings:
    """Transcription engine settings."""
    model_name: str = "turbo"  # tiny, base, small, medium, large-v3, turbo
    language: str = "en"
    compute_type: str = "auto"  # auto, float16, int8, float32
    device: str = "auto"  # auto, cuda, cpu
    beam_size: int = 5
    vad_enabled: bool = True
    vad_threshold: float = 0.5


@dataclass
class HotkeySettings:
    """Hotkey configuration."""
    activation_key: str = "ctrl+shift"  # Default hotkey
    hold_to_record: bool = True  # Press and hold mode


@dataclass
class UISettings:
    """User interface settings."""
    theme: str = "dark"  # dark, light, auto
    accent_color: str = "#3B82F6"  # Blue
    waveform_height: int = 60
    waveform_width: int = 400
    opacity: float = 0.9
    show_status_text: bool = True
    animation_fps: int = 60
    waveform_always_on_top: bool = True  # Keep waveform overlay always on top
    waveform_background_color: str = "#131313"  # Dark background for waveform


@dataclass
class FeedbackSettings:
    """Audio and visual feedback settings."""
    sound_enabled: bool = True
    sound_volume: float = 0.5  # 0.0 to 1.0
    start_sound: str = "start.wav"
    stop_sound: str = "stop.wav"
    visual_feedback: bool = True


@dataclass
class HistorySettings:
    """Transcription history settings."""
    enabled: bool = True
    retention_days: int = 30
    encrypt_storage: bool = False
    max_entries: int = 10000


@dataclass
class GeneralSettings:
    """General application settings."""
    launch_at_startup: bool = False
    start_minimized: bool = True
    check_updates: bool = True
    first_run: bool = True


@dataclass
class Config:
    """Main configuration class containing all settings."""
    general: GeneralSettings = field(default_factory=GeneralSettings)
    audio: AudioSettings = field(default_factory=AudioSettings)
    transcription: TranscriptionSettings = field(default_factory=TranscriptionSettings)
    hotkey: HotkeySettings = field(default_factory=HotkeySettings)
    ui: UISettings = field(default_factory=UISettings)
    feedback: FeedbackSettings = field(default_factory=FeedbackSettings)
    history: HistorySettings = field(default_factory=HistorySettings)

    _config_path: Path = field(default_factory=lambda: get_config_dir() / "config.json", repr=False)

    def __post_init__(self):
        """Ensure config directory exists."""
        self._config_path.parent.mkdir(parents=True, exist_ok=True)

    @classmethod
    def load(cls, config_path: Optional[Path] = None) -> "Config":
        """Load configuration from file or create default."""
        path = config_path or (get_config_dir() / "config.json")

        if path.exists():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                config = cls(
                    general=GeneralSettings(**data.get("general", {})),
                    audio=AudioSettings(**data.get("audio", {})),
                    transcription=TranscriptionSettings(**data.get("transcription", {})),
                    hotkey=HotkeySettings(**data.get("hotkey", {})),
                    ui=UISettings(**data.get("ui", {})),
                    feedback=FeedbackSettings(**data.get("feedback", {})),
                    history=HistorySettings(**data.get("history", {})),
                )
                config._config_path = path
                return config
            except (json.JSONDecodeError, TypeError, KeyError) as e:
                # Config file corrupted, return default
                print(f"Warning: Config file corrupted, using defaults: {e}")

        # Return default config
        config = cls()
        config._config_path = path
        return config

    def save(self) -> None:
        """Save configuration to file."""
        self._config_path.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "general": asdict(self.general),
            "audio": asdict(self.audio),
            "transcription": asdict(self.transcription),
            "hotkey": asdict(self.hotkey),
            "ui": asdict(self.ui),
            "feedback": asdict(self.feedback),
            "history": asdict(self.history),
        }

        with open(self._config_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def reset_to_defaults(self) -> None:
        """Reset all settings to defaults."""
        self.general = GeneralSettings()
        self.audio = AudioSettings()
        self.transcription = TranscriptionSettings()
        self.hotkey = HotkeySettings()
        self.ui = UISettings()
        self.feedback = FeedbackSettings()
        self.history = HistorySettings()
        self.save()

    @staticmethod
    def get_model_path(model_name: str) -> Path:
        """Get the path where a model should be stored."""
        return get_cache_dir() / model_name

    @staticmethod
    def get_database_path() -> Path:
        """Get the path for the history database."""
        return get_data_dir() / "history.db"

    @staticmethod
    def get_sounds_dir() -> Path:
        """Get the directory containing sound files."""
        # First check package resources, then user data dir
        package_dir = Path(__file__).parent.parent / "resources" / "sounds"
        if package_dir.exists():
            return package_dir
        return get_data_dir() / "sounds"


# Available Whisper models with their properties
AVAILABLE_MODELS = {
    "tiny.en": {
        "size_mb": 75,
        "vram_gb": 1,
        "relative_speed": 32,
        "english_only": True,
    },
    "base.en": {
        "size_mb": 145,
        "vram_gb": 1,
        "relative_speed": 16,
        "english_only": True,
    },
    "small.en": {
        "size_mb": 488,
        "vram_gb": 2,
        "relative_speed": 6,
        "english_only": True,
    },
    "medium.en": {
        "size_mb": 1530,
        "vram_gb": 5,
        "relative_speed": 2,
        "english_only": True,
    },
    "turbo": {
        "size_mb": 1600,
        "vram_gb": 6,
        "relative_speed": 8,
        "english_only": False,
    },
    "large-v3": {
        "size_mb": 3100,
        "vram_gb": 10,
        "relative_speed": 1,
        "english_only": False,
    },
}
