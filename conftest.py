from __future__ import annotations

import os
from pathlib import Path
from uuid import uuid4

import pytest


def pytest_configure() -> None:
    temp_root = Path(__file__).parent / ".pytest_tmp_root"
    temp_root.mkdir(exist_ok=True)
    os.environ.setdefault("PYTEST_DEBUG_TEMPROOT", str(temp_root))


@pytest.fixture
def tmp_path(request: pytest.FixtureRequest) -> Path:
    temp_root = Path(__file__).parent / ".pytest_tmp_manual"
    temp_root.mkdir(exist_ok=True)
    path = temp_root / f"{request.node.name}_{uuid4().hex}"
    path.mkdir()
    return path
