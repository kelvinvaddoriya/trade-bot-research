import pytest

from tradebot import risk


@pytest.fixture(autouse=True)
def kill_switch_in_tmp(tmp_path, monkeypatch):
    """No test may touch the real data/KILL."""
    monkeypatch.setattr(risk, "KILL_FILE", tmp_path / "KILL")
    monkeypatch.setattr(risk, "KILL_LOG", tmp_path / "kill_log.jsonl")
