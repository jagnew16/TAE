from datetime import date

import pytest

from aaa.context import load_rep

TODAY = date(2026, 10, 5)


@pytest.fixture(autouse=True)
def fresh_state(tmp_path, monkeypatch):
    """Every test starts from the seed data in its own state directory."""
    monkeypatch.setenv("AAA_STATE_DIR", str(tmp_path / "state"))


@pytest.fixture
def alice():
    return load_rep("alice", today=TODAY)


@pytest.fixture
def ben():
    return load_rep("ben", today=TODAY)


@pytest.fixture
def dana():
    return load_rep("dana", today=TODAY)
