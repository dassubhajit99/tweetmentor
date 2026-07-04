"""Tests for tweetmentor.ui (spinner + status helpers), no real terminal needed."""

from __future__ import annotations

import io

from tweetmentor.ui import Spinner, _color_enabled, _fmt_elapsed, note, success


class _FakeStream(io.StringIO):
    """A StringIO that can pretend to be (or not be) a TTY."""

    def __init__(self, isatty: bool = False):
        super().__init__()
        self._isatty = isatty

    def isatty(self) -> bool:
        return self._isatty


def test_fmt_elapsed_seconds_only():
    assert _fmt_elapsed(5) == "5s"
    assert _fmt_elapsed(59.9) == "59s"


def test_fmt_elapsed_minutes_and_seconds():
    assert _fmt_elapsed(65) == "1m05s"
    assert _fmt_elapsed(3661) == "61m01s"


def test_color_enabled_false_when_not_a_tty(monkeypatch):
    monkeypatch.delenv("NO_COLOR", raising=False)
    stream = _FakeStream(isatty=False)
    assert _color_enabled(stream) is False


def test_color_enabled_true_when_tty_and_no_color_unset(monkeypatch):
    monkeypatch.delenv("NO_COLOR", raising=False)
    stream = _FakeStream(isatty=True)
    assert _color_enabled(stream) is True


def test_color_enabled_false_when_no_color_set_even_if_tty(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    stream = _FakeStream(isatty=True)
    assert _color_enabled(stream) is False


def test_color_enabled_handles_stream_without_isatty(monkeypatch):
    monkeypatch.delenv("NO_COLOR", raising=False)

    class NoIsATty:
        pass

    assert _color_enabled(NoIsATty()) is False


def test_success_writes_message_with_check(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    stream = _FakeStream(isatty=False)
    success("all good", stream=stream)
    assert "all good" in stream.getvalue()
    assert "✓" in stream.getvalue()


def test_note_writes_plain_message_when_color_disabled(monkeypatch):
    monkeypatch.setenv("NO_COLOR", "1")
    stream = _FakeStream(isatty=False)
    note("a note", stream=stream)
    assert stream.getvalue().strip() == "a note"


def test_spinner_non_tty_prints_plain_status_lines_on_start_and_update(monkeypatch):
    monkeypatch.delenv("NO_COLOR", raising=False)
    stream = _FakeStream(isatty=False)
    sp = Spinner("Scraping @karpathy", stream=stream)

    sp.start()
    assert "Scraping @karpathy …" in stream.getvalue()

    sp.update("Halfway done")
    assert "Halfway done …" in stream.getvalue()

    sp.stop("Done!")
    assert "Done!" in stream.getvalue()
    # non-tty mode must never emit cursor-hide/show escape codes
    assert "\x1b[?25l" not in stream.getvalue()
    assert "\x1b[?25h" not in stream.getvalue()


def test_spinner_non_tty_context_manager_does_not_raise(monkeypatch):
    monkeypatch.delenv("NO_COLOR", raising=False)
    stream = _FakeStream(isatty=False)
    with Spinner("working", stream=stream) as sp:
        sp.update("still working")
    assert "working" in stream.getvalue()


def test_spinner_tty_animates_and_clears_cursor_on_stop(monkeypatch):
    monkeypatch.delenv("NO_COLOR", raising=False)
    stream = _FakeStream(isatty=True)
    sp = Spinner("Loading", stream=stream, interval=0.001)

    sp.start()
    try:
        assert "\x1b[?25l" in stream.getvalue()
    finally:
        sp.stop()

    assert "\x1b[?25h" in stream.getvalue()


def test_spinner_update_strips_whitespace():
    stream = _FakeStream(isatty=False)
    sp = Spinner(stream=stream)
    sp.start()
    sp.update("  padded text  ")
    assert "padded text …" in stream.getvalue()
