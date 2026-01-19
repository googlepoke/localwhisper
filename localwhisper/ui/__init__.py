"""
LocalWhisper UI Module

Contains PyQt6-based user interface components.
"""

from localwhisper.ui.waveform_widget import WaveformWidget, WaveformOverlay
from localwhisper.ui.settings_window import SettingsWindow
from localwhisper.ui.history_window import HistoryWindow
from localwhisper.ui.tray_icon import TrayIcon

__all__ = [
    "WaveformWidget",
    "WaveformOverlay",
    "SettingsWindow",
    "HistoryWindow",
    "TrayIcon",
]
