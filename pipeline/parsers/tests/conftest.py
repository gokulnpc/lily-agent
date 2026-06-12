from __future__ import annotations

import pathlib

import pytest

FIXTURES = pathlib.Path(__file__).parent / "fixtures"


@pytest.fixture
def fixture() -> object:
    def _load(name: str) -> str:
        return (FIXTURES / f"{name}.html").read_text()

    return _load
