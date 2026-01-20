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
    """Canvas widget that draws an oscilloscope-style line waveform."""

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        accent_color: str = "#3B82F6",
        background_color: str = "#131313",
        sample_count: int = 200,
    ):
        super().__init__(parent)

        self._accent_color = QColor(accent_color)
        self._background_color = QColor(background_color)
        self._sample_count = sample_count
        
        # Store waveform samples (0.0-1.0, 0.5 is center/silence)
        self._samples: List[float] = [0.5] * sample_count
        
        # Current amplitude for wave generation
        self._current_amplitude: float = 0.0
        self._target_amplitude: float = 0.0
        
        # Phase for continuous sine wave generation
        self._phase: float = 0.0

        # Animation timer for continuous wave generation
        self._animation_timer = QTimer(self)
        self._animation_timer.timeout.connect(self._animate)
        self._animation_timer.start(16)  # ~60fps

        self.setMinimumSize(360, 40)

    def set_accent_color(self, color: str) -> None:
        """Set the waveform line color."""
        self._accent_color = QColor(color)
        self.update()

    def set_background_color(self, color: str) -> None:
        """Set the waveform background color."""
        self._background_color = QColor(color)
        self.update()

    def add_amplitude(self, amplitude: float) -> None:
        """
        Update the target amplitude for the waveform.
        
        The waveform continuously oscillates with amplitude controlling the wave height.
        """
        # Normalize and clamp amplitude, with some scaling for visibility
        self._target_amplitude = max(0.0, min(1.0, amplitude * 2.5))

    def clear(self) -> None:
        """Clear the waveform to flat center line."""
        self._samples = [0.5] * self._sample_count
        self._current_amplitude = 0.0
        self._target_amplitude = 0.0
        self._phase = 0.0
        self.update()

    def _animate(self) -> None:
        """Generate continuous waveform based on current amplitude."""
        # Smoothly interpolate towards target amplitude
        smoothing = 0.15
        self._current_amplitude += (self._target_amplitude - self._current_amplitude) * smoothing
        
        # Decay target amplitude over time (audio callbacks will refresh it)
        self._target_amplitude *= 0.95
        
        # Generate new samples for the wave
        # Shift all samples left and add new ones on the right
        samples_per_frame = 4  # How many new samples to add per animation frame
        
        for _ in range(samples_per_frame):
            # Advance phase for sine wave
            # Vary frequency slightly based on amplitude for more organic look
            freq_multiplier = 0.25 + self._current_amplitude * 0.15
            self._phase += freq_multiplier
            
            # Calculate displacement using sine wave modulated by amplitude
            # Add some harmonics for richer wave shape
            wave = math.sin(self._phase)
            wave += 0.3 * math.sin(self._phase * 2.1)  # Add harmonic
            wave += 0.15 * math.sin(self._phase * 3.2)  # Add another harmonic
            wave = wave / 1.45  # Normalize
            
            # Scale by amplitude (max displacement of 0.45 from center)
            displacement = self._current_amplitude * 0.45 * wave
            sample = 0.5 + displacement
            
            # Shift samples left and add new one
            self._samples.pop(0)
            self._samples.append(sample)
        
        self.update()

    def paintEvent(self, event) -> None:
        """Paint the oscilloscope-style line waveform."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        width = self.width()
        height = self.height()

        # Fill background
        painter.fillRect(0, 0, width, height, QBrush(self._background_color))

        # Set up pen for the waveform line
        pen = QPen(self._accent_color)
        pen.setWidth(2)
        painter.setPen(pen)

        # Calculate slice width (how much x-space each sample takes)
        slice_width = width / self._sample_count

        # Build the path through all samples
        path = QPainterPath()
        
        for i, sample in enumerate(self._samples):
            x = i * slice_width
            # Sample is 0.0-1.0, convert to y coordinate (inverted: 0=top, 1=bottom)
            y = sample * height
            
            if i == 0:
                path.moveTo(x, y)
            else:
                path.lineTo(x, y)

        # Draw line to right edge at center
        path.lineTo(width, height / 2)

        # Stroke the path
        painter.drawPath(path)
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
        
        # Adjust margins based on whether status text is shown
        if self.settings.show_status_text:
            layout.setContentsMargins(16, 12, 16, 12)
            layout.setSpacing(8)
        else:
            layout.setContentsMargins(8, 8, 8, 8)
            layout.setSpacing(0)

        # Waveform canvas with oscilloscope-style line drawing
        self._canvas = WaveformCanvas(
            self,
            accent_color=self.settings.accent_color,
            background_color=self.settings.waveform_background_color,
            sample_count=256,
        )
        layout.addWidget(self._canvas)

        # Status label (only show if enabled in settings)
        self._status_label = QLabel()
        self._status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status_label.setFont(QFont("Segoe UI", 10))
        
        if self.settings.show_status_text:
            layout.addWidget(self._status_label)
            self._update_status_display()
            # Fixed size with status text
            self.setFixedSize(self.settings.waveform_width, self.settings.waveform_height + 30)
        else:
            # Compact size without status text
            self._status_label.hide()
            self.setFixedSize(self.settings.waveform_width, self.settings.waveform_height)

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

    def set_background_color(self, color: str) -> None:
        """Set the waveform background color."""
        self.settings.waveform_background_color = color
        self._canvas.set_background_color(color)

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
        self._always_on_top = self.settings.waveform_always_on_top

        # Set initial window flags
        self._update_window_flags()

        # Transparent background
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)

        # Don't show in taskbar and don't take focus
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WidgetAttribute.WA_X11DoNotAcceptFocus, True)

        self._setup_ui()
        self._setup_animations()

        # Timer to periodically ensure window stays on top
        self._stay_on_top_timer = QTimer(self)
        self._stay_on_top_timer.timeout.connect(self._ensure_on_top)
        self._stay_on_top_timer.setInterval(100)  # Check every 100ms

    def _update_window_flags(self) -> None:
        """Update window flags based on always-on-top setting."""
        base_flags = (
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.Tool |
            Qt.WindowType.WindowDoesNotAcceptFocus
        )
        if self._always_on_top:
            self.setWindowFlags(
                base_flags |
                Qt.WindowType.WindowStaysOnTopHint
            )
        else:
            self.setWindowFlags(base_flags)

    def set_always_on_top(self, enabled: bool) -> None:
        """Set whether the overlay should stay always on top."""
        if self._always_on_top != enabled:
            self._always_on_top = enabled
            was_visible = self.isVisible()
            self._update_window_flags()
            if was_visible:
                self.show()

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

        # Size based on waveform widget and status text setting
        if self.settings.show_status_text:
            height_extra = 50  # Extra height for status text and shadow
        else:
            height_extra = 20  # Compact height without status text
            
        self.setFixedSize(
            self.settings.waveform_width + 40,  # Extra for shadow
            self.settings.waveform_height + height_extra,
        )

    def _setup_animations(self) -> None:
        """Set up show/hide animations."""
        # Fade in animation
        self._fade_in_animation = QPropertyAnimation(self, b"windowOpacity")
        self._fade_in_animation.setDuration(200)
        self._fade_in_animation.setEasingCurve(QEasingCurve.Type.OutCubic)

        # Fade out animation (separate to avoid signal connection issues)
        self._fade_out_animation = QPropertyAnimation(self, b"windowOpacity")
        self._fade_out_animation.setDuration(200)
        self._fade_out_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._fade_out_animation.finished.connect(self.hide)

    def _position_at_bottom_center(self) -> None:
        """Position the overlay at bottom center of primary screen, just above taskbar."""
        screen = QApplication.primaryScreen()
        if screen:
            screen_geometry = screen.availableGeometry()
            x = screen_geometry.x() + (screen_geometry.width() - self.width()) // 2
            # Position right at the bottom of available screen area (just above taskbar)
            y = screen_geometry.y() + screen_geometry.height() - self.height() - 5  # 5px margin from taskbar
            self.move(x, y)

    def _ensure_on_top(self) -> None:
        """Ensure the overlay stays on top of other windows."""
        if self.isVisible() and self._always_on_top:
            self.raise_()

    def show_overlay(self) -> None:
        """Show the overlay with animation."""
        # Stop any ongoing hide animation
        self._fade_out_animation.stop()
        
        self._position_at_bottom_center()
        self._waveform.set_state(WaveformWidget.STATE_LISTENING)
        self._waveform.clear_waveform()

        # Fade in
        self.setWindowOpacity(0)
        self.show()
        self.raise_()  # Ensure on top immediately

        # Start timer to keep on top (only if always-on-top is enabled)
        if self._always_on_top:
            self._stay_on_top_timer.start()

        self._fade_in_animation.setStartValue(0)
        self._fade_in_animation.setEndValue(self.settings.opacity)
        self._fade_in_animation.start()

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
        # Stop the stay-on-top timer
        self._stay_on_top_timer.stop()
        
        # Stop any ongoing show animation
        self._fade_in_animation.stop()

        self._fade_out_animation.setStartValue(self.windowOpacity())
        self._fade_out_animation.setEndValue(0)
        self._fade_out_animation.start()

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

    def set_background_color(self, color: str) -> None:
        """Set the waveform background color."""
        self._waveform.set_background_color(color)

    @property
    def waveform(self) -> WaveformWidget:
        """Get the waveform widget."""
        return self._waveform
