"""Tiny, zero-dependency terminal UI helpers (spinner + status lines).

The scrape/analyze steps make long blocking calls that print nothing until
they finish, so the terminal looks frozen. ``Spinner`` runs an animation on a
background thread while the main thread is busy, giving live feedback plus an
elapsed timer.

Design goals:
  * No third-party deps (pure ANSI escapes).
  * Animation goes to ``stderr`` so piped ``stdout`` stays clean.
  * TTY-aware: when the stream isn't a terminal (piped, redirected, CI) it
    degrades to plain one-line status prints instead of escape-code spam.
  * Honors the ``NO_COLOR`` convention.
"""

from __future__ import annotations

import itertools
import os
import sys
import threading
import time
from typing import IO

# A smooth braille spinner — elegant and monospace-safe.
_BRAILLE = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"

_HIDE_CURSOR = "\x1b[?25l"
_SHOW_CURSOR = "\x1b[?25h"
_CLEAR_EOL = "\x1b[K"  # erase from cursor to end of line


def _color_enabled(stream: IO[str]) -> bool:
    if os.environ.get("NO_COLOR"):
        return False
    return bool(getattr(stream, "isatty", lambda: False)())


def _paint(code: str, text: str, enabled: bool) -> str:
    return f"\x1b[{code}m{text}\x1b[0m" if enabled else text


def _fmt_elapsed(seconds: float) -> str:
    secs = int(seconds)
    if secs < 60:
        return f"{secs}s"
    return f"{secs // 60}m{secs % 60:02d}s"


class Spinner:
    """Animated status line usable as a context manager.

    Example::

        with Spinner("Scraping @karpathy") as sp:
            do_slow_work(progress=sp.update)
    """

    def __init__(
        self,
        text: str = "",
        *,
        stream: IO[str] | None = None,
        frames: str = _BRAILLE,
        interval: float = 0.08,
    ) -> None:
        self._stream = stream if stream is not None else sys.stderr
        self._text = text
        self._frames = frames
        self._interval = interval
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._lock = threading.Lock()
        self._start = 0.0
        self._animate = bool(getattr(self._stream, "isatty", lambda: False)())
        self._color = _color_enabled(self._stream)

    # -- lifecycle -----------------------------------------------------------
    def start(self) -> "Spinner":
        self._start = time.monotonic()
        if not self._animate:
            if self._text:
                print(f"{self._text} …", file=self._stream, flush=True)
            return self
        self._stream.write(_HIDE_CURSOR)
        self._stream.flush()
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()
        return self

    def update(self, text: str) -> None:
        """Change the message shown next to the spinner."""
        text = text.strip()
        with self._lock:
            self._text = text
        if not self._animate and text:
            print(f"{text} …", file=self._stream, flush=True)

    def stop(self, final: str | None = None) -> None:
        if self._animate:
            self._stop.set()
            if self._thread is not None:
                self._thread.join()
                self._thread = None
            self._stream.write("\r" + _CLEAR_EOL + _SHOW_CURSOR)
            self._stream.flush()
        if final is not None:
            print(final, file=self._stream, flush=True)

    # -- internals -----------------------------------------------------------
    def _loop(self) -> None:
        for frame in itertools.cycle(self._frames):
            if self._stop.is_set():
                break
            with self._lock:
                text = self._text
            spin = _paint("36", frame, self._color)  # cyan
            elapsed = _paint("2", f"({_fmt_elapsed(time.monotonic() - self._start)})", self._color)
            self._stream.write(f"\r{spin} {text} {elapsed}{_CLEAR_EOL}")
            self._stream.flush()
            time.sleep(self._interval)

    # -- context manager -----------------------------------------------------
    def __enter__(self) -> "Spinner":
        return self.start()

    def __exit__(self, exc_type, exc, tb) -> bool:
        # Always restore the cursor / clear the line, even on error or Ctrl-C.
        self.stop()
        return False


def success(msg: str, stream: IO[str] | None = None) -> None:
    """Print a green ✓ status line (defaults to stdout)."""
    stream = stream if stream is not None else sys.stdout
    check = _paint("32", "✓", _color_enabled(stream))
    print(f"{check} {msg}", file=stream, flush=True)


def note(msg: str, stream: IO[str] | None = None) -> None:
    """Print a dimmed secondary line (defaults to stdout)."""
    stream = stream if stream is not None else sys.stdout
    print(_paint("2", msg, _color_enabled(stream)), file=stream, flush=True)
