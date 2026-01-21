"""
Hotkey Manager for LocalWhisper

Handles global keyboard shortcuts for activating/deactivating recording.
Supports press-and-hold mode where recording starts on key press and stops on release.
"""

import threading
import platform
import time
from typing import Optional, Callable, Set
from dataclasses import dataclass
from enum import Enum

from pynput import keyboard


class HotkeyState(Enum):
    """State of the hotkey."""
    IDLE = "idle"
    PRESSED = "pressed"
    RELEASED = "released"


@dataclass
class HotkeyCombo:
    """Represents a hotkey combination."""
    modifiers: Set[str]  # e.g., {"alt", "ctrl", "shift"}
    key: str  # e.g., "s", "space", "f1"

    @classmethod
    def from_string(cls, hotkey_str: str) -> "HotkeyCombo":
        """
        Parse a hotkey string like "alt+s" or "ctrl+shift+f1".

        Args:
            hotkey_str: String representation of the hotkey

        Returns:
            HotkeyCombo instance
        """
        parts = hotkey_str.lower().replace(" ", "").split("+")

        modifier_names = {"alt", "ctrl", "control", "shift", "cmd", "win", "meta"}
        modifiers = set()
        key = None

        for part in parts:
            if part in modifier_names:
                # Normalize modifier names
                if part == "control":
                    part = "ctrl"
                elif part in ("cmd", "win", "meta"):
                    part = "cmd" if platform.system() == "Darwin" else "win"
                modifiers.add(part)
            else:
                key = part

        if key is None:
            raise ValueError(f"Invalid hotkey: {hotkey_str} - no key specified")

        return cls(modifiers=modifiers, key=key)

    def to_string(self) -> str:
        """Convert back to string representation."""
        parts = sorted(self.modifiers) + [self.key]
        return "+".join(parts)

    def matches_pynput_key(self, key) -> bool:
        """Check if a pynput key matches this hotkey's key."""
        try:
            # First check if it's a special key (like F1, space, etc.)
            if hasattr(key, "name") and key.name:
                return key.name.lower() == self.key.lower()
            
            # On Windows, when Ctrl is pressed, the char becomes a control code
            # Check the virtual key code (vk) FIRST - this is the most reliable
            if hasattr(key, "vk") and key.vk:
                # vk codes for A-Z are 0x41-0x5A (65-90)
                if 65 <= key.vk <= 90:
                    return chr(key.vk).lower() == self.key.lower()
                # vk codes for 0-9 are 0x30-0x39 (48-57)
                if 48 <= key.vk <= 57:
                    return chr(key.vk) == self.key
            
            # Fallback: check regular character (only for unmodified keys)
            if hasattr(key, "char") and key.char and len(key.char) == 1 and key.char.isprintable():
                return key.char.lower() == self.key.lower()
        except (AttributeError, TypeError):
            pass
        return False


class HotkeyManager:
    """
    Global hotkey manager for press-and-hold recording activation.

    Listens for global keyboard events and triggers callbacks when
    the configured hotkey is pressed/released.
    """

    def __init__(
        self,
        hotkey: str = "alt+s",
        on_press: Optional[Callable[[], None]] = None,
        on_release: Optional[Callable[[], None]] = None,
    ):
        """
        Initialize the hotkey manager.

        Args:
            hotkey: Hotkey string (e.g., "alt+s", "ctrl+shift+r")
            on_press: Callback when hotkey is pressed
            on_release: Callback when hotkey is released
        """
        self._hotkey = HotkeyCombo.from_string(hotkey)
        self._on_press = on_press
        self._on_release = on_release

        self._listener: Optional[keyboard.Listener] = None
        self._is_running = False

        # Track pressed modifiers
        self._pressed_modifiers: Set[str] = set()
        self._hotkey_active = False
        self._activation_time: float = 0.0
        self._min_hold_time: float = 0.15  # Minimum 150ms hold to prevent spurious releases

        # Thread safety
        self._lock = threading.Lock()

    def set_hotkey(self, hotkey: str) -> None:
        """
        Change the hotkey combination.

        Args:
            hotkey: New hotkey string
        """
        was_running = self._is_running
        if was_running:
            self.stop()

        self._hotkey = HotkeyCombo.from_string(hotkey)

        if was_running:
            self.start()

    def set_callbacks(
        self,
        on_press: Optional[Callable[[], None]] = None,
        on_release: Optional[Callable[[], None]] = None,
    ) -> None:
        """
        Set the press/release callbacks.

        Args:
            on_press: Callback when hotkey is pressed
            on_release: Callback when hotkey is released
        """
        with self._lock:
            if on_press is not None:
                self._on_press = on_press
            if on_release is not None:
                self._on_release = on_release

    def start(self) -> None:
        """Start listening for the hotkey."""
        if self._is_running:
            return

        self._pressed_modifiers.clear()
        self._hotkey_active = False

        self._listener = keyboard.Listener(
            on_press=self._handle_press,
            on_release=self._handle_release,
        )
        self._listener.start()
        self._is_running = True

    def stop(self) -> None:
        """Stop listening for the hotkey."""
        if not self._is_running:
            return

        if self._listener:
            self._listener.stop()
            self._listener = None

        self._is_running = False
        self._hotkey_active = False
        self._pressed_modifiers.clear()

    def _get_modifier_name(self, key) -> Optional[str]:
        """Get the modifier name for a key, if it's a modifier."""
        try:
            if key == keyboard.Key.alt or key == keyboard.Key.alt_l or key == keyboard.Key.alt_r:
                return "alt"
            elif key == keyboard.Key.ctrl or key == keyboard.Key.ctrl_l or key == keyboard.Key.ctrl_r:
                return "ctrl"
            elif key == keyboard.Key.shift or key == keyboard.Key.shift_l or key == keyboard.Key.shift_r:
                return "shift"
            elif key == keyboard.Key.cmd or key == keyboard.Key.cmd_l or key == keyboard.Key.cmd_r:
                return "cmd" if platform.system() == "Darwin" else "win"
        except AttributeError:
            pass
        return None

    def _handle_press(self, key) -> None:
        """Handle key press event."""
        # Check if it's a modifier
        modifier = self._get_modifier_name(key)
        if modifier:
            self._pressed_modifiers.add(modifier)
            return

        # Check if the hotkey combo is complete
        if self._hotkey.matches_pynput_key(key):
            if self._pressed_modifiers == self._hotkey.modifiers:
                with self._lock:
                    if not self._hotkey_active:
                        self._hotkey_active = True
                        self._activation_time = time.time()
                        if self._on_press:
                            try:
                                self._on_press()
                            except Exception as e:
                                print(f"Error in hotkey press callback: {e}")

    def _handle_release(self, key) -> None:
        """Handle key release event."""
        # Check if it's a modifier
        modifier = self._get_modifier_name(key)
        if modifier:
            self._pressed_modifiers.discard(modifier)
            # Don't trigger release on modifier release - only on main key release
            # This prevents spurious modifier release events from stopping recording
            return

        # Check if the main key is released - this is the only trigger for release
        if self._hotkey.matches_pynput_key(key):
            if self._hotkey_active:
                self._trigger_release()

    def _trigger_release(self) -> None:
        """Trigger the release callback."""
        with self._lock:
            if self._hotkey_active:
                # Check minimum hold time to prevent spurious releases
                elapsed = time.time() - self._activation_time
                if elapsed < self._min_hold_time:
                    # Spurious release - keep hotkey active, don't trigger callback
                    # The actual release will come later
                    return
                self._hotkey_active = False
                self._activation_time = 0.0
                if self._on_release:
                    try:
                        self._on_release()
                    except Exception as e:
                        print(f"Error in hotkey release callback: {e}")

    @property
    def is_running(self) -> bool:
        """Check if the hotkey manager is running."""
        return self._is_running

    @property
    def is_active(self) -> bool:
        """Check if the hotkey is currently pressed."""
        return self._hotkey_active

    @property
    def current_hotkey(self) -> str:
        """Get the current hotkey string."""
        return self._hotkey.to_string()

    def __enter__(self):
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop()
        return False


def check_hotkey_conflict(hotkey: str) -> Optional[str]:
    """
    Check if a hotkey might conflict with common system shortcuts.

    Args:
        hotkey: Hotkey string to check

    Returns:
        Warning message if conflict detected, None otherwise
    """
    common_conflicts = {
        "alt+f4": "Close window (Windows/Linux)",
        "alt+tab": "Switch window",
        "ctrl+c": "Copy",
        "ctrl+v": "Paste",
        "ctrl+x": "Cut",
        "ctrl+z": "Undo",
        "ctrl+s": "Save",
        "ctrl+a": "Select all",
        "cmd+c": "Copy (macOS)",
        "cmd+v": "Paste (macOS)",
        "cmd+q": "Quit (macOS)",
        "cmd+w": "Close window (macOS)",
    }

    normalized = hotkey.lower().replace(" ", "")
    if normalized in common_conflicts:
        return f"Warning: '{hotkey}' conflicts with '{common_conflicts[normalized]}'"

    return None


def validate_hotkey(hotkey: str) -> Optional[str]:
    """
    Validate a hotkey string format.

    Args:
        hotkey: Hotkey string to validate

    Returns:
        Error message if invalid, None if valid
    """
    if not hotkey or not hotkey.strip():
        return "Hotkey cannot be empty"

    try:
        HotkeyCombo.from_string(hotkey)
        return None  # Valid
    except ValueError as e:
        return str(e)
