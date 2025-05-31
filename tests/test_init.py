"""Tests for the main module."""

from async_task_pipeline import __version__


def test_version() -> None:
    """Test that version is defined."""
    assert __version__ == "0.1.0"
