"""
Text Injector for LocalWhisper

Handles inserting transcribed text into the active application.
Uses clipboard-based injection for smooth, instant text output.
"""

import time
import platform
import subprocess
import threading
from typing import Optional, Callable

from pynput.keyboard import Controller, Key


class TextInjectorError(Exception):
    """Base exception for text injector errors."""
    pass


class TextInjector:
    """
    Cross-platform text injector using clipboard paste.

    Uses clipboard-based injection (copy + paste) for smooth, instant text
    output without the jitter of character-by-character keyboard simulation.
    """

    def __init__(
        self,
        on_complete: Optional[Callable[[str], None]] = None,
        use_clipboard: bool = True,
    ):
        """
        Initialize the text injector.

        Args:
            on_complete: Callback when injection is complete
            use_clipboard: If True, use clipboard paste (smooth). If False, use keyboard simulation.
        """
        self._controller = Controller()
        self._on_complete = on_complete
        self._use_clipboard = use_clipboard

        # Platform detection
        self._system = platform.system()

        # State
        self._is_typing = False
        self._saved_clipboard: Optional[str] = None

    def inject_text(self, text: str) -> bool:
        """
        Inject text into the active application.

        Uses clipboard paste for instant, smooth text insertion.

        Args:
            text: Text to inject

        Returns:
            True if successful, False otherwise
        """
        if not text or not text.strip():
            return True

        text = text.strip()
        self._is_typing = True

        try:
            if self._use_clipboard:
                success = self._inject_via_clipboard(text)
            else:
                success = self._inject_via_keyboard(text)

            if self._on_complete and success:
                self._on_complete(text)

            return success
        finally:
            self._is_typing = False

    def _inject_via_clipboard(self, text: str) -> bool:
        """
        Inject text using clipboard copy + paste.

        This is the smoothest method - text appears instantly.

        Args:
            text: Text to inject

        Returns:
            True if successful
        """
        # Save current clipboard content (optional - for restoration)
        # We skip this for performance, as it can be slow

        # Set clipboard content
        if not self._set_clipboard(text):
            # Fallback to keyboard simulation if clipboard fails
            return self._inject_via_keyboard(text)

        # Small delay to ensure clipboard is set
        time.sleep(0.02)

        # Simulate paste keystroke (Ctrl+V on Windows/Linux, Cmd+V on macOS)
        try:
            if self._system == "Darwin":
                self._controller.press(Key.cmd)
                time.sleep(0.01)
                self._controller.press('v')
                time.sleep(0.01)
                self._controller.release('v')
                self._controller.release(Key.cmd)
            else:
                self._controller.press(Key.ctrl)
                time.sleep(0.01)
                self._controller.press('v')
                time.sleep(0.01)
                self._controller.release('v')
                self._controller.release(Key.ctrl)

            # Small delay after paste
            time.sleep(0.05)
            return True

        except Exception as e:
            print(f"Paste keystroke failed: {e}")
            return False

    def _set_clipboard(self, text: str) -> bool:
        """
        Set clipboard content using platform-specific methods.

        Args:
            text: Text to copy to clipboard

        Returns:
            True if successful
        """
        try:
            if self._system == "Windows":
                return self._set_clipboard_windows(text)
            elif self._system == "Darwin":
                return self._set_clipboard_macos(text)
            else:
                return self._set_clipboard_linux(text)
        except Exception as e:
            print(f"Clipboard error: {e}")
            return False

    def _set_clipboard_windows(self, text: str) -> bool:
        """Set clipboard on Windows using native API."""
        try:
            import ctypes
            from ctypes import wintypes

            # Windows clipboard API
            user32 = ctypes.windll.user32
            kernel32 = ctypes.windll.kernel32

            # Constants
            CF_UNICODETEXT = 13
            GMEM_MOVEABLE = 0x0002

            # Open clipboard
            if not user32.OpenClipboard(None):
                return self._set_clipboard_windows_powershell(text)

            try:
                # Empty clipboard
                user32.EmptyClipboard()

                # Encode text as UTF-16
                text_bytes = text.encode('utf-16-le') + b'\x00\x00'

                # Allocate global memory
                h_mem = kernel32.GlobalAlloc(GMEM_MOVEABLE, len(text_bytes))
                if not h_mem:
                    return False

                # Lock memory and copy text
                p_mem = kernel32.GlobalLock(h_mem)
                if not p_mem:
                    kernel32.GlobalFree(h_mem)
                    return False

                ctypes.memmove(p_mem, text_bytes, len(text_bytes))
                kernel32.GlobalUnlock(h_mem)

                # Set clipboard data
                if not user32.SetClipboardData(CF_UNICODETEXT, h_mem):
                    kernel32.GlobalFree(h_mem)
                    return False

                return True

            finally:
                user32.CloseClipboard()

        except Exception as e:
            # Fallback to PowerShell method
            return self._set_clipboard_windows_powershell(text)

    def _set_clipboard_windows_powershell(self, text: str) -> bool:
        """Fallback: Set clipboard on Windows using PowerShell."""
        try:
            # Escape special characters for PowerShell
            escaped_text = text.replace('`', '``').replace('"', '`"').replace('$', '`$')

            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE

            process = subprocess.Popen(
                ['powershell', '-NoProfile', '-Command',
                 f'Set-Clipboard -Value "{escaped_text}"'],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                startupinfo=startupinfo,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            process.wait(timeout=2)
            return process.returncode == 0
        except Exception as e:
            print(f"PowerShell clipboard error: {e}")
            return False

    def _set_clipboard_macos(self, text: str) -> bool:
        """Set clipboard on macOS using pbcopy."""
        try:
            process = subprocess.Popen(
                ['pbcopy'],
                stdin=subprocess.PIPE,
                env={'LANG': 'en_US.UTF-8'}
            )
            process.communicate(text.encode('utf-8'), timeout=2)
            return process.returncode == 0
        except Exception as e:
            print(f"macOS clipboard error: {e}")
            return False

    def _set_clipboard_linux(self, text: str) -> bool:
        """Set clipboard on Linux using xclip or xsel."""
        # Try xclip first
        for cmd in [
            ['xclip', '-selection', 'clipboard'],
            ['xsel', '--clipboard', '--input'],
            ['wl-copy'],  # Wayland
        ]:
            try:
                process = subprocess.Popen(
                    cmd,
                    stdin=subprocess.PIPE,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                process.communicate(text.encode('utf-8'), timeout=2)
                if process.returncode == 0:
                    return True
            except FileNotFoundError:
                continue
            except Exception:
                continue

        return False

    def _inject_via_keyboard(self, text: str) -> bool:
        """
        Fallback: Inject text using keyboard simulation.

        This is slower and may show jitter, but works without clipboard access.

        Args:
            text: Text to inject

        Returns:
            True if successful
        """
        try:
            # Use pynput's type method - fastest keyboard simulation
            self._controller.type(text)
            return True
        except Exception as e:
            print(f"Keyboard injection error: {e}")
            return False

    def type_text(self, text: str, immediate: bool = True) -> None:
        """
        Type text into the active application.

        For backwards compatibility. Calls inject_text internally.

        Args:
            text: Text to type
            immediate: Ignored (always immediate with clipboard method)
        """
        self.inject_text(text)

    def inject_text_async(self, text: str) -> None:
        """
        Inject text asynchronously in a background thread.

        Args:
            text: Text to inject
        """
        def inject_thread():
            self.inject_text(text)

        threading.Thread(target=inject_thread, daemon=True).start()

    @property
    def is_typing(self) -> bool:
        """Check if currently injecting text."""
        return self._is_typing

    def set_use_clipboard(self, use_clipboard: bool) -> None:
        """
        Set whether to use clipboard-based injection.

        Args:
            use_clipboard: True for clipboard (smooth), False for keyboard (jittery)
        """
        self._use_clipboard = use_clipboard


# Backwards compatibility alias
ClipboardInjector = TextInjector
