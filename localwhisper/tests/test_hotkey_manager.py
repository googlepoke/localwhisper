"""
Tests for Hotkey Manager
"""

import pytest
from unittest.mock import Mock, patch

from localwhisper.core.hotkey_manager import (
    HotkeyCombo,
    HotkeyManager,
    check_hotkey_conflict,
)


class TestHotkeyCombo:
    """Tests for HotkeyCombo class."""

    def test_parse_simple_hotkey(self):
        """Should parse simple hotkey like 'alt+s'."""
        combo = HotkeyCombo.from_string("alt+s")
        assert combo.modifiers == {"alt"}
        assert combo.key == "s"

    def test_parse_multiple_modifiers(self):
        """Should parse hotkey with multiple modifiers."""
        combo = HotkeyCombo.from_string("ctrl+shift+r")
        assert combo.modifiers == {"ctrl", "shift"}
        assert combo.key == "r"

    def test_parse_with_spaces(self):
        """Should handle spaces in hotkey string."""
        combo = HotkeyCombo.from_string("alt + s")
        assert combo.modifiers == {"alt"}
        assert combo.key == "s"

    def test_parse_uppercase(self):
        """Should handle uppercase input."""
        combo = HotkeyCombo.from_string("ALT+S")
        assert combo.modifiers == {"alt"}
        assert combo.key == "s"

    def test_parse_control_alias(self):
        """Should normalize 'control' to 'ctrl'."""
        combo = HotkeyCombo.from_string("control+c")
        assert combo.modifiers == {"ctrl"}
        assert combo.key == "c"

    def test_parse_no_key_raises(self):
        """Should raise for modifier-only hotkey."""
        with pytest.raises(ValueError):
            HotkeyCombo.from_string("alt+ctrl")

    def test_to_string(self):
        """Should convert back to string."""
        combo = HotkeyCombo(modifiers={"alt"}, key="s")
        assert combo.to_string() == "alt+s"

    def test_to_string_multiple_modifiers(self):
        """Should produce consistent string for multiple modifiers."""
        combo = HotkeyCombo(modifiers={"shift", "ctrl"}, key="r")
        # Should be sorted alphabetically
        assert combo.to_string() == "ctrl+shift+r"


class TestHotkeyManager:
    """Tests for HotkeyManager class."""

    def test_init_default_hotkey(self):
        """Should initialize with default hotkey."""
        manager = HotkeyManager()
        assert manager.current_hotkey == "alt+s"

    def test_init_custom_hotkey(self):
        """Should initialize with custom hotkey."""
        manager = HotkeyManager(hotkey="ctrl+shift+r")
        assert manager.current_hotkey == "ctrl+shift+r"

    def test_set_hotkey(self):
        """Should change hotkey."""
        manager = HotkeyManager(hotkey="alt+s")
        manager.set_hotkey("ctrl+d")
        assert manager.current_hotkey == "ctrl+d"

    def test_is_running_initial_false(self):
        """Should not be running initially."""
        manager = HotkeyManager()
        assert manager.is_running is False

    def test_is_active_initial_false(self):
        """Hotkey should not be active initially."""
        manager = HotkeyManager()
        assert manager.is_active is False

    def test_set_callbacks(self):
        """Should set callbacks."""
        manager = HotkeyManager()
        on_press = Mock()
        on_release = Mock()

        manager.set_callbacks(on_press=on_press, on_release=on_release)

        assert manager._on_press is on_press
        assert manager._on_release is on_release

    def test_context_manager(self):
        """Should work as context manager."""
        with patch.object(HotkeyManager, 'start') as mock_start:
            with patch.object(HotkeyManager, 'stop') as mock_stop:
                with HotkeyManager() as manager:
                    mock_start.assert_called_once()
                mock_stop.assert_called_once()


class TestCheckHotkeyConflict:
    """Tests for check_hotkey_conflict function."""

    def test_no_conflict(self):
        """Should return None for non-conflicting hotkey."""
        result = check_hotkey_conflict("alt+s")
        assert result is None

    def test_alt_f4_conflict(self):
        """Should warn about Alt+F4 conflict."""
        result = check_hotkey_conflict("alt+f4")
        assert result is not None
        assert "Close window" in result

    def test_ctrl_c_conflict(self):
        """Should warn about Ctrl+C conflict."""
        result = check_hotkey_conflict("ctrl+c")
        assert result is not None
        assert "Copy" in result

    def test_ctrl_v_conflict(self):
        """Should warn about Ctrl+V conflict."""
        result = check_hotkey_conflict("ctrl+v")
        assert result is not None
        assert "Paste" in result

    def test_case_insensitive(self):
        """Should check conflicts case-insensitively."""
        result = check_hotkey_conflict("CTRL+C")
        assert result is not None
