"""
Text Injector for LocalWhisper

Handles typing transcribed text into the active application using keyboard simulation.
Supports cross-platform text injection with proper character encoding.
"""

import time
import platform
import threading
from typing import Optional, Callable
from queue import Queue

from pynput.keyboard import Controller, Key


class TextInjectorError(Exception):
    """Base exception for text injector errors."""
    pass


class TextInjector:
    """
    Cross-platform text injector using keyboard simulation.

    Types text character by character into the currently focused application.
    Supports rate limiting to prevent dropped characters.
    """

    # Default typing rate (characters per second)
    DEFAULT_RATE = 50

    # Special character mappings that need shift key
    SHIFT_CHARS = '~!@#$%^&*()_+{}|:"<>?'

    def __init__(
        self,
        typing_rate: int = DEFAULT_RATE,
        on_complete: Optional[Callable[[str], None]] = None,
    ):
        """
        Initialize the text injector.

        Args:
            typing_rate: Characters per second (default 50)
            on_complete: Callback when typing is complete
        """
        self._controller = Controller()
        self._typing_rate = typing_rate
        self._on_complete = on_complete

        # Typing state
        self._is_typing = False
        self._should_stop = False
        self._type_thread: Optional[threading.Thread] = None
        self._text_queue: Queue = Queue()

        # Platform-specific settings
        self._system = platform.system()

        # Inter-character delay (seconds)
        self._char_delay = 1.0 / typing_rate

    def set_typing_rate(self, rate: int) -> None:
        """
        Set the typing rate.

        Args:
            rate: Characters per second
        """
        self._typing_rate = max(1, min(200, rate))  # Clamp between 1-200
        self._char_delay = 1.0 / self._typing_rate

    def type_text(self, text: str, immediate: bool = False) -> None:
        """
        Type text into the active application.

        Args:
            text: Text to type
            immediate: If True, type immediately without rate limiting
        """
        if not text:
            return

        if immediate:
            self._type_immediate(text)
        else:
            self._type_with_rate_limit(text)

    def _type_immediate(self, text: str) -> None:
        """Type text immediately using pynput's type method."""
        try:
            # pynput's type() method handles most text well
            self._controller.type(text)
        except Exception as e:
            # Fallback to character-by-character
            self._type_characters(text, delay=0)

    def _type_with_rate_limit(self, text: str) -> None:
        """Type text with rate limiting."""
        self._type_characters(text, delay=self._char_delay)

    def _type_characters(self, text: str, delay: float) -> None:
        """
        Type text character by character.

        Args:
            text: Text to type
            delay: Delay between characters in seconds
        """
        for char in text:
            if self._should_stop:
                break

            try:
                self._type_character(char)
                if delay > 0:
                    time.sleep(delay)
            except Exception as e:
                print(f"Error typing character '{char}': {e}")

    def _type_character(self, char: str) -> None:
        """
        Type a single character.

        Args:
            char: Character to type
        """
        # Handle special characters
        if char == '\n':
            self._controller.press(Key.enter)
            self._controller.release(Key.enter)
        elif char == '\t':
            self._controller.press(Key.tab)
            self._controller.release(Key.tab)
        elif char == ' ':
            self._controller.press(Key.space)
            self._controller.release(Key.space)
        else:
            # Regular character - use type() for better Unicode support
            try:
                self._controller.type(char)
            except Exception:
                # Fallback for problematic characters
                self._controller.press(char)
                self._controller.release(char)

    def type_text_async(self, text: str) -> None:
        """
        Type text asynchronously in a background thread.

        Args:
            text: Text to type
        """
        if not text:
            return

        self._should_stop = False
        self._is_typing = True

        def type_thread():
            try:
                self._type_with_rate_limit(text)
            finally:
                self._is_typing = False
                if self._on_complete:
                    self._on_complete(text)

        self._type_thread = threading.Thread(target=type_thread, daemon=True)
        self._type_thread.start()

    def stop_typing(self) -> None:
        """Stop any ongoing async typing."""
        self._should_stop = True
        if self._type_thread and self._type_thread.is_alive():
            self._type_thread.join(timeout=0.5)
        self._is_typing = False

    def type_streaming(self, text_generator) -> None:
        """
        Type text from a generator as it becomes available.

        This is useful for streaming transcription where text
        appears progressively.

        Args:
            text_generator: Generator yielding text chunks
        """
        self._should_stop = False
        self._is_typing = True

        last_text = ""

        try:
            for text in text_generator:
                if self._should_stop:
                    break

                # Only type the new part
                if text.startswith(last_text):
                    new_text = text[len(last_text):]
                    if new_text:
                        self._type_with_rate_limit(new_text)
                else:
                    # Text changed completely (shouldn't happen often)
                    # Would need to handle backspace/correction here
                    pass

                last_text = text
        finally:
            self._is_typing = False

    def press_key(self, key: Key) -> None:
        """
        Press a special key.

        Args:
            key: pynput Key to press
        """
        self._controller.press(key)
        self._controller.release(key)

    def press_enter(self) -> None:
        """Press the Enter key."""
        self.press_key(Key.enter)

    def press_backspace(self, count: int = 1) -> None:
        """
        Press backspace to delete characters.

        Args:
            count: Number of times to press backspace
        """
        for _ in range(count):
            self.press_key(Key.backspace)
            time.sleep(0.01)  # Small delay between backspaces

    @property
    def is_typing(self) -> bool:
        """Check if currently typing."""
        return self._is_typing

    @property
    def typing_rate(self) -> int:
        """Get the current typing rate."""
        return self._typing_rate


class ClipboardInjector:
    """
    Alternative text injector using clipboard paste.

    Faster than keyboard simulation but requires clipboard access.
    """

    def __init__(self):
        """Initialize the clipboard injector."""
        self._controller = Controller()
        self._system = platform.system()

    def inject_text(self, text: str) -> bool:
        """
        Inject text by copying to clipboard and pasting.

        Args:
            text: Text to inject

        Returns:
            True if successful, False otherwise
        """
        try:
            # Try to use pyperclip if available
            import pyperclip
            pyperclip.copy(text)
        except ImportError:
            # Fallback to platform-specific clipboard
            if not self._set_clipboard(text):
                return False

        # Simulate Ctrl+V / Cmd+V
        time.sleep(0.05)  # Small delay before paste

        if self._system == "Darwin":
            self._controller.press(Key.cmd)
            self._controller.press('v')
            self._controller.release('v')
            self._controller.release(Key.cmd)
        else:
            self._controller.press(Key.ctrl)
            self._controller.press('v')
            self._controller.release('v')
            self._controller.release(Key.ctrl)

        return True

    def _set_clipboard(self, text: str) -> bool:
        """Set clipboard content using platform-specific methods."""
        import subprocess

        try:
            if self._system == "Darwin":
                process = subprocess.Popen(
                    ['pbcopy'],
                    stdin=subprocess.PIPE,
                    env={'LANG': 'en_US.UTF-8'}
                )
                process.communicate(text.encode('utf-8'))
                return process.returncode == 0

            elif self._system == "Linux":
                # Try xclip first, then xsel
                for cmd in [['xclip', '-selection', 'clipboard'],
                           ['xsel', '--clipboard', '--input']]:
                    try:
                        process = subprocess.Popen(
                            cmd,
                            stdin=subprocess.PIPE
                        )
                        process.communicate(text.encode('utf-8'))
                        if process.returncode == 0:
                            return True
                    except FileNotFoundError:
                        continue
                return False

            elif self._system == "Windows":
                # Use PowerShell for clipboard access
                process = subprocess.Popen(
                    ['powershell', '-command', f'Set-Clipboard -Value "{text}"'],
                    stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    creationflags=subprocess.CREATE_NO_WINDOW
                )
                process.wait()
                return process.returncode == 0

        except Exception as e:
            print(f"Clipboard error: {e}")
            return False

        return False
