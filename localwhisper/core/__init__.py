"""
LocalWhisper Core Module

Contains the core functionality for audio capture, transcription, and text injection.
"""

from localwhisper.core.config import Config
from localwhisper.core.audio_engine import AudioEngine
from localwhisper.core.transcription_engine import TranscriptionEngine
from localwhisper.core.hotkey_manager import HotkeyManager
from localwhisper.core.text_injector import TextInjector
from localwhisper.core.history_manager import HistoryManager
from localwhisper.core.audio_feedback import AudioFeedback

__all__ = [
    "Config",
    "AudioEngine",
    "TranscriptionEngine",
    "HotkeyManager",
    "TextInjector",
    "HistoryManager",
    "AudioFeedback",
]
