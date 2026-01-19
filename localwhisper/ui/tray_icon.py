"""
System Tray Icon for LocalWhisper

Provides system tray integration with context menu and status indication.
"""

from typing import Optional, Callable
from enum import Enum

from PyQt6.QtWidgets import (
    QSystemTrayIcon,
    QMenu,
    QApplication,
)
from PyQt6.QtGui import QIcon, QPixmap, QPainter, QColor, QBrush, QPen
from PyQt6.QtCore import pyqtSignal, QObject, Qt


class TrayState(Enum):
    """Tray icon states."""
    IDLE = "idle"
    RECORDING = "recording"
    PROCESSING = "processing"
    ERROR = "error"


class TrayIcon(QObject):
    """
    System tray icon with context menu.

    Shows application status and provides quick access to common actions.
    """

    # Signals
    show_requested = pyqtSignal()
    settings_requested = pyqtSignal()
    history_requested = pyqtSignal()
    quit_requested = pyqtSignal()
    toggle_recording = pyqtSignal()

    # Icon colors for different states
    STATE_COLORS = {
        TrayState.IDLE: "#6B7280",      # Gray
        TrayState.RECORDING: "#EF4444",  # Red
        TrayState.PROCESSING: "#F59E0B", # Yellow
        TrayState.ERROR: "#DC2626",      # Dark red
    }

    def __init__(self, parent: Optional[QObject] = None):
        super().__init__(parent)

        self._state = TrayState.IDLE
        self._tray = QSystemTrayIcon()

        self._setup_menu()
        self._update_icon()

        # Connect activation
        self._tray.activated.connect(self._on_activated)

    def _setup_menu(self) -> None:
        """Set up the context menu."""
        menu = QMenu()

        # Status item (non-clickable)
        self._status_action = menu.addAction("LocalWhisper - Ready")
        self._status_action.setEnabled(False)

        menu.addSeparator()

        # Quick actions
        self._record_action = menu.addAction("Start Recording")
        self._record_action.triggered.connect(self.toggle_recording.emit)

        menu.addSeparator()

        # Show main window
        show_action = menu.addAction("Show Window")
        show_action.triggered.connect(self.show_requested.emit)

        # History
        history_action = menu.addAction("View History")
        history_action.triggered.connect(self.history_requested.emit)

        # Settings
        settings_action = menu.addAction("Settings")
        settings_action.triggered.connect(self.settings_requested.emit)

        menu.addSeparator()

        # Quit
        quit_action = menu.addAction("Quit")
        quit_action.triggered.connect(self.quit_requested.emit)

        self._tray.setContextMenu(menu)

    def _create_icon(self, color: str, with_dot: bool = False) -> QIcon:
        """
        Create a tray icon with the given color.

        Args:
            color: Hex color string
            with_dot: Whether to add a recording indicator dot

        Returns:
            QIcon instance
        """
        size = 64
        pixmap = QPixmap(size, size)
        pixmap.fill(QColor(0, 0, 0, 0))  # Transparent

        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        # Main circle (microphone base)
        base_color = QColor(color)
        painter.setBrush(QBrush(base_color))
        painter.setPen(QPen(base_color.darker(120), 2))

        # Draw microphone shape
        center_x = size // 2
        center_y = size // 2

        # Mic body (rounded rectangle)
        mic_width = size // 3
        mic_height = size // 2
        mic_x = center_x - mic_width // 2
        mic_y = center_y - mic_height // 2 - 4

        painter.drawRoundedRect(
            mic_x, mic_y, mic_width, mic_height,
            mic_width // 2, mic_width // 2
        )

        # Mic stand (arc)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(base_color, 3))

        arc_width = mic_width + 10
        arc_x = center_x - arc_width // 2
        arc_y = center_y

        painter.drawArc(arc_x, arc_y, arc_width, 20, 0, -180 * 16)

        # Stand line
        painter.drawLine(center_x, arc_y + 10, center_x, arc_y + 18)

        # Stand base
        base_width = 16
        painter.drawLine(
            center_x - base_width // 2, arc_y + 18,
            center_x + base_width // 2, arc_y + 18
        )

        # Recording dot (if recording)
        if with_dot:
            dot_color = QColor("#EF4444")
            painter.setBrush(QBrush(dot_color))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(size - 16, 0, 14, 14)

        painter.end()

        return QIcon(pixmap)

    def _update_icon(self) -> None:
        """Update the tray icon based on current state."""
        color = self.STATE_COLORS.get(self._state, self.STATE_COLORS[TrayState.IDLE])
        with_dot = self._state == TrayState.RECORDING

        icon = self._create_icon(color, with_dot)
        self._tray.setIcon(icon)

        # Update tooltip and status
        status_text = {
            TrayState.IDLE: "LocalWhisper - Ready",
            TrayState.RECORDING: "LocalWhisper - Recording...",
            TrayState.PROCESSING: "LocalWhisper - Processing...",
            TrayState.ERROR: "LocalWhisper - Error",
        }.get(self._state, "LocalWhisper")

        self._tray.setToolTip(status_text)
        self._status_action.setText(status_text)

        # Update record action text
        if self._state == TrayState.RECORDING:
            self._record_action.setText("Stop Recording")
        else:
            self._record_action.setText("Start Recording")

    def set_state(self, state: TrayState) -> None:
        """
        Set the tray icon state.

        Args:
            state: New state
        """
        if state != self._state:
            self._state = state
            self._update_icon()

    def show(self) -> None:
        """Show the tray icon."""
        self._tray.show()

    def hide(self) -> None:
        """Hide the tray icon."""
        self._tray.hide()

    def show_message(
        self,
        title: str,
        message: str,
        icon: QSystemTrayIcon.MessageIcon = QSystemTrayIcon.MessageIcon.Information,
        duration_ms: int = 3000,
    ) -> None:
        """
        Show a notification balloon/toast.

        Args:
            title: Notification title
            message: Notification message
            icon: Icon type
            duration_ms: Duration in milliseconds
        """
        self._tray.showMessage(title, message, icon, duration_ms)

    def show_error(self, message: str) -> None:
        """Show an error notification."""
        self.show_message(
            "LocalWhisper Error",
            message,
            QSystemTrayIcon.MessageIcon.Critical,
        )

    def show_info(self, message: str) -> None:
        """Show an info notification."""
        self.show_message(
            "LocalWhisper",
            message,
            QSystemTrayIcon.MessageIcon.Information,
        )

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        """Handle tray icon activation."""
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show_requested.emit()
        elif reason == QSystemTrayIcon.ActivationReason.Trigger:
            # Single click - could show menu or toggle recording
            pass

    @property
    def state(self) -> TrayState:
        """Get the current state."""
        return self._state

    @property
    def is_visible(self) -> bool:
        """Check if tray icon is visible."""
        return self._tray.isVisible()
