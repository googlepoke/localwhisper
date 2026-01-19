"""
LocalWhisper - Real-Time Speech-to-Text Desktop Application

A privacy-focused, local speech recognition application using OpenAI's Whisper model.
"""

__version__ = "1.0.0"
__author__ = "LocalWhisper Team"

from localwhisper.core.config import Config
from localwhisper.app import LocalWhisperApp

__all__ = ["LocalWhisperApp", "Config", "__version__"]
