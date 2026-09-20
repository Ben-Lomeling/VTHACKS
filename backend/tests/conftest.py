"""Tests never touch the network: the app's startup bank reload is off here."""
import os

import pytest

os.environ.setdefault("BANK_RELOAD_ON_START", "off")


@pytest.fixture(autouse=True)
def _gemini_offline(monkeypatch):
    """No test calls the real Gemini API, even on a machine with a key in .env.

    Without this, the suite's results depend on whether a developer has a key — slow, flaky, and
    it bills a real quota. Tests that want the live code path patch `_api_key` themselves.
    """
    import app.gemini as gemini

    monkeypatch.setattr(gemini, "_api_key", lambda: None)
