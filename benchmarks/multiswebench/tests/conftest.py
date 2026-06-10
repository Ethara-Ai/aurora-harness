from __future__ import annotations

import json
from pathlib import Path

import pytest


@pytest.fixture
def jsonl_writer(tmp_path: Path):
    def _write(name: str, records: list[dict]) -> Path:
        path = tmp_path / name
        with path.open("w", encoding="utf-8") as f:
            for record in records:
                f.write(json.dumps(record) + "\n")
        return path

    return _write


@pytest.fixture
def empty_jsonl(tmp_path: Path) -> Path:
    path = tmp_path / "empty.jsonl"
    path.write_text("", encoding="utf-8")
    return path
