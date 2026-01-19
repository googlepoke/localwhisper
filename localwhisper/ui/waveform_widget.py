"""
Waveform Visualization Widget for LocalWhisper

A modern, minimal floating waveform display that shows audio input levels.
Appears at bottom center of screen during recording.
"""

from typing import Optional, List
from collections import deque
import math

from PyQt6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QGraphicsDropShadowEffect,
    QApplication,
)
from PyQt6.QtCore import (
    Qt,
    QTimer,
    QPropertyAnimation,
    QEasingCurve,
    pyqtSignal,
    QPoint,
    QSize,
)
from PyQt6.QtGui import (
    QPainter,
    QColor,
    QPainterPath,
    QLinearGradient,
    QFont,
    QPen,
    QBrush,
)

from localwhisper.core.config import UISettings


class WaveformCanvas(QWidget):
    """Canvas widget that draws the actual waveform."""

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        accent_color: str = "#3B82F6",
        bar_count: int = 40,
    ):
        super().__init__(parent)

        self._accent_color = QColor(accent_color)
        self._bar_count = bar_count
        self._amplitudes: deque = deque([0.0] * bar_count, maxlen=bar_count)

        # Animation
        self._target_amplitudes: List[float] = [0.0] * bar_count
        self._animation_timer = QTimer(self)
        self._animation_timer.timeout.connect(self._animate)
        self._animation_timer.start(16)  # ~60fps

        self.setMinimumSize(360, 40)

    def set_accent_color(self, color: str) -> None:
        """Set the waveform accent color."""
        self._accent_color = QColor(color)
        self.update()

    def add_amplitude(self, amplitude: float) -> None:
        """Add a new amplitude value to the waveform."""
        # Normalize and clamp
        amplitude = max(0.0, min(1.0, amplitude))

        # Shift existing and add new
        self._target_amplitudes.pop(0)
        self._target_amplitudes.append(amplitude)

    def clear(self) -> None:
        """Clear the waveform."""
        self._target_amplitudes = [0.0] * self._bar_count
        self._amplitudes = deque([0.0] * self._bar_count, maxlen=self._bar_count)
        self.update()

    def _animate(self) -> None:
        """Smoothly animate towards target amplitudes."""
        changed = False
        smoothing = 0.3  # Lower = smoother

        for i, target in enumerate(self._target_amplitudes):
            current = self._amplitudes[i]
            if abs(current - target) > 0.01:
                self._amplitudes[i] = current + (target - current) * smoothing
                changed = True
            else:
                self._amplitudes[i] = target

        if changed:
            self.update()

    def paintEvent(self, event) -> None:
        """Paint the waveform."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        width = self.width()
        height = self.height()

        # Calculate bar dimensions
        bar_spacing = 3
        bar_width = max(2, (width - (self._bar_count - 1) * bar_spacing) // self._bar_count)
        total_width = self._bar_count * bar_width + (self._bar_count - 1) * bar_spacing
        start_x = (width - total_width) // 2

        # Create gradient
        gradient = QLinearGradient(0, 0, 0, height)
        gradient.setColorAt(0, self._accent_color.lighter(120))
        gradient.setColorAt(1, self._accent_color)

        # Draw bars
        center_y = height // 2

        for i, amplitude in enumerate(self._amplitudes):
            x = start_x + i * (bar_width + bar_spacing)

            # Bar height based on amplitude
            bar_height = max(4, int(amplitude * (height - 8)))

            # Draw bar centered vertically
            y = center_y - bar_height // 2

            # Round corners
            path = QPainterPath()
            radius = min(bar_width // 2, 2)
            path.addRoundedRect(x, y, bar_width, bar_height, radius, radius)

            painter.fillPath(path, QBrush(gradient))

        painter.end()


class WaveformWidget(QWidget):
    """
    Complete waveform widget with status text.

    Shows a waveform visualization with a status label below it.
    """

    # Signals
    clicked = pyqtSignal()

    # States
    STATE_LISTENING = "listening"
    STATE_PROCESSING = "processing"
    STATE_SUCCESS = "success"
    STATE_ERROR = "error"

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        settings: Optional[UISettings] = None,
    ):
        super().__init__(parent)

        self.settings = settings or UISettings()

        self._state = self.STATE_LISTENING
        self._status_text = "Listening..."
        self._error_message = ""

        self._setup_ui()
        self._apply_style()

    def _setup_ui(self) -> None:
        """Set up the widget UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        # Waveform canvas
        self._canvas = WaveformCanvas(
            self,
            accent_color=self.settings.accent_color,
            bar_count=40,
        )
        layout.addWidget(self._canvas)

        # Status label
        self._status_label = QLabel()
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_label.setFont(QFont("Segoe UI", 10))
        layout.addWidget(self._status_label)

        self._update_status_display()

        # Fixed size
        self.setFixedSize(self.settings.waveform_width, self.settings.waveform_height + 20)

    def _apply_style(self) -> None:
        """Apply the visual style."""
        # Determine colors based on state
        if self._state == self.STATE_ERROR:
            bg_color = "rgba(127, 29, 29, 0.95)"  # Dark red
            text_color = "#FCA5A5"
        elif self._state == self.STATE_SUCCESS:
            bg_color = "rgba(6, 78, 59, 0.95)"  # Dark green
            text_color = "#6EE7B7"
        else:
            bg_color = "rgba(30, 30, 30, 0.95)"
            text_color = "#FFFFFF"

        self.setStyleSheet(f"""
            WaveformWidget {{
                background-color: {bg_color};
                border-radius: 12px;
            }}
            QLabel {{
                color: {text_color};
                background: transparent;
            }}
        """)

    def set_state(self, state: str, message: str = "") -> None:
        """
        Set the widget state.

        Args:
            state: One of STATE_LISTENING, STATE_PROCESSING, STATE_SUCCESS, STATE_ERROR
            message: Optional message to display
        """
        self._state = state
        self._error_message = message

        if state == self.STATE_LISTENING:
            self._status_text = "Listening..."
        elif state == self.STATE_PROCESSING:
            self._status_text = "Processing..."
        elif state == self.STATE_SUCCESS:
            self._status_text = "Done!"
        elif state == self.STATE_ERROR:
            self._status_text = message or "Error"

        self._update_status_display()
        self._apply_style()

        # Update canvas color
        if state == self.STATE_ERROR:
            self._canvas.set_accent_color("#EF4444")
        elif state == self.STATE_SUCCESS:
            self._canvas.set_accent_color("#10B981")
        else:
            self._canvas.set_accent_color(self.settings.accent_color)

    def _update_status_display(self) -> None:
        """Update the status label."""
        icon = ""
        if self._state == self.STATE_LISTENING:
            icon = "\U0001F3A4"  # Microphone emoji
        elif self._state == self.STATE_PROCESSING:
            icon = "\u23F3"  # Hourglass
        elif self._state == self.STATE_SUCCESS:
            icon = "\u2713"  # Check mark
        elif self._state == self.STATE_ERROR:
            icon = "\u26A0"  # Warning

        self._status_label.setText(f"{icon} {self._status_text}")

    def add_amplitude(self, amplitude: float) -> None:
        """Add amplitude data to the waveform."""
        self._canvas.add_amplitude(amplitude)

    def clear_waveform(self) -> None:
        """Clear the waveform display."""
        self._canvas.clear()

    def set_accent_color(self, color: str) -> None:
        """Set the accent color."""
        self.settings.accent_color = color
        self._canvas.set_accent_color(color)

    def mousePressEvent(self, event) -> None:
        """Handle mouse press."""
        self.clicked.emit()
        super().mousePressEvent(event)


class WaveformOverlay(QWidget):
    """
    Floating overlay window that displays the waveform.

    This is a frameless, always-on-top window that appears at the bottom
    center of the screen during recording.
    """

    def __init__(self, settings: Optional[UISettings] = None):
        super().__init__(None)

        self.settings = settings or UISettings()

        # Window flags for overlay behavior
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool |
            Qt.WindowType.WindowTransparentForInput
        )

        # Transparent background
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # Don't show in taskbar
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)

        self._setup_ui()
        self._setup_animations()

    def _setup_ui(self) -> None:
        """Set up the overlay UI."""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Main waveform widget
        self._waveform = WaveformWidget(self, self.settings)
        layout.addWidget(self._waveform)

        # Add shadow effect
        shadow = QGraphicsDropShadowEffect(self)
        shadow.setBlurRadius(20)
        shadow.setColor(QColor(0, 0, 0, 80))
        shadow.setOffset(0, 4)
        self._waveform.setGraphicsEffect(shadow)

        # Size based on waveform widget
        self.setFixedSize(
            self.settings.waveform_width + 40,  # Extra for shadow
            self.settings.waveform_height + 60,
        )

    def _setup_animations(self) -> None:
        """Set up show/hide animations."""
        # Fade in animation
        self._fade_animation = QPropertyAnimation(self, b"windowOpacity")
        self._fade_animation.setDuration(200)
        self._fade_animation.setEasingCurve(QEasingCurve.Type.OutCubic)

    def _position_at_bottom_center(self) -> None:
        """Position the overlay at bottom center of primary screen."""
        screen = QApplication.primaryScreen()
        if screen:
            screen_geometry = screen.availableGeometry()
            x = screen_geometry.x() + (screen_geometry.width() - self.width()) // 2
            y = screen_geometry.y() + screen_geometry.height() - self.height() - 50  # 50px from bottom
            self.move(x, y)

    def show_overlay(self) -> None:
        """Show the overlay with animation."""
        self._position_at_bottom_center()
        self._waveform.set_state(WaveformWidget.STATE_LISTENING)
        self._waveform.clear_waveform()

        # Fade in
        self.setWindowOpacity(0)
        self.show()
        self._fade_animation.setStartValue(0)
        self._fade_animation.setEndValue(self.settings.opacity)
        self._fade_animation.start()

    def hide_overlay(self, delay_ms: int = 0) -> None:
        """
        Hide the overlay with animation.

        Args:
            delay_ms: Optional delay before hiding
        """
        if delay_ms > 0:
            QTimer.singleShot(delay_ms, self._do_hide)
        else:
            self._do_hide()

    def _do_hide(self) -> None:
        """Perform the hide animation."""
        self._fade_animation.setStartValue(self.windowOpacity())
        self._fade_animation.setEndValue(0)
        self._fade_animation.finished.connect(self.hide)
        self._fade_animation.start()

    def show_success(self, delay_hide_ms: int = 500) -> None:
        """Show success state and then hide."""
        self._waveform.set_state(WaveformWidget.STATE_SUCCESS)
        self.hide_overlay(delay_ms=delay_hide_ms)

    def show_error(self, message: str, delay_hide_ms: int = 3000) -> None:
        """Show error state and then hide."""
        self._waveform.set_state(WaveformWidget.STATE_ERROR, message)
        self.hide_overlay(delay_ms=delay_hide_ms)

    def set_processing(self) -> None:
        """Set the widget to processing state."""
        self._waveform.set_state(WaveformWidget.STATE_PROCESSING)

    def add_amplitude(self, amplitude: float) -> None:
        """Add amplitude data to the waveform."""
        self._waveform.add_amplitude(amplitude)

    def set_accent_color(self, color: str) -> None:
        """Set the accent color."""
        self._waveform.set_accent_color(color)

    @property
    def waveform(self) -> WaveformWidget:
        """Get the waveform widget."""
        return self._waveform
