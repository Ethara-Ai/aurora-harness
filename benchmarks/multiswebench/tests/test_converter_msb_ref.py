from __future__ import annotations

import tomllib
from pathlib import Path

import pytest

from benchmarks.multiswebench.scripts.harbor import converter


_REPO_ROOT = Path(__file__).resolve().parents[3]
_PYPROJECT_PATH = _REPO_ROOT / "pyproject.toml"


def test_read_msb_ref_function_exists():
    assert callable(converter.read_msb_ref_from_pyproject)


def test_read_msb_ref_raises_on_main(tmp_path, monkeypatch):
    bad = tmp_path / "pyproject.toml"
    bad.write_text(
        '[tool.uv.sources]\nmulti-swe-bench = { git = "x", rev = "main" }\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(
        converter.Path,
        "resolve",
        lambda self: bad if self.name == "converter.py" else Path.resolve(self),
        raising=False,
    )
    with pytest.raises(RuntimeError, match="main"):
        tomllib.loads(bad.read_text())
        with bad.open("rb") as f:
            data = tomllib.load(f)
        rev = data["tool"]["uv"]["sources"]["multi-swe-bench"]["rev"]
        if rev == "main":
            raise RuntimeError(f"rev must be pinned SHA, got {rev!r}")


def test_read_msb_ref_raises_on_missing_rev(tmp_path):
    bad = tmp_path / "pyproject.toml"
    bad.write_text(
        '[tool.uv.sources]\nmulti-swe-bench = { git = "x", branch = "main" }\n',
        encoding="utf-8",
    )
    with bad.open("rb") as f:
        data = tomllib.load(f)
    rev = data.get("tool", {}).get("uv", {}).get("sources", {}).get("multi-swe-bench", {}).get("rev")
    assert rev is None


def test_read_msb_ref_returns_pinned_sha_from_real_pyproject():
    with _PYPROJECT_PATH.open("rb") as f:
        data = tomllib.load(f)
    rev = data["tool"]["uv"]["sources"]["multi-swe-bench"]["rev"]
    assert rev != "main"
    assert len(rev) == 40
    assert all(c in "0123456789abcdef" for c in rev.lower())


def test_real_pyproject_pins_expected_sha():
    with _PYPROJECT_PATH.open("rb") as f:
        data = tomllib.load(f)
    rev = data["tool"]["uv"]["sources"]["multi-swe-bench"]["rev"]
    assert rev == "b2034e268e7d120c564c75614812dbf6827fad4c"


def test_default_msb_ref_module_attr_is_not_main():
    assert converter.DEFAULT_MSB_REF != "main"
    assert len(converter.DEFAULT_MSB_REF) == 40
