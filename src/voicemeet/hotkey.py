"""Global hotkey management via pynput.

Lazy-imports pynput for graceful degradation.
Default hotkey: Cmd+Shift+M toggles meeting recording.
"""

from __future__ import annotations

from collections.abc import Callable

DEFAULT_HOTKEY = "<cmd>+<shift>+m"


class HotkeyManager:
    """Manages a global keyboard shortcut.

    Args:
        callback: Called when the hotkey is pressed.
        hotkey: Key combination string (pynput format).
    """

    def __init__(
        self,
        callback: Callable[[], None],
        hotkey: str = DEFAULT_HOTKEY,
    ) -> None:
        self.callback = callback
        self.hotkey = hotkey
        self._listener = None

    def start(self) -> None:
        """Start listening for the global hotkey."""
        try:
            from pynput import keyboard
        except ImportError as e:
            raise ImportError(
                "pynput is required for global hotkeys. Install with: pip install pynput"
            ) from e

        self._listener = keyboard.GlobalHotKeys({self.hotkey: self._on_pressed})
        self._listener.start()

    def stop(self) -> None:
        """Stop listening."""
        if self._listener:
            self._listener.stop()
            self._listener = None

    def _on_pressed(self) -> None:
        """Internal callback wrapper."""
        try:
            self.callback()
        except Exception:
            pass  # Hotkey errors should not crash the listener

    @property
    def is_running(self) -> bool:
        return self._listener is not None
