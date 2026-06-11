"""Regression test for Q-002 m0691 (silent no-op on missing Dockerfile anchor).

The fix at converter.py inject_dockerfile_language_patches ensures:
  - c++ language with missing marker -> RuntimeError (not silent no-op)
  - java language with missing marker -> RuntimeError (not silent no-op)
  - other languages (python, etc.) fall through unchanged by design

Pre-fix: silent fall-through produced misconfigured builds with no buster
sources fallback (c++) or no --allow-releaseinfo-change patch (java).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from benchmarks.multiswebench.scripts.harbor.converter import (
    inject_dockerfile_language_patches,
)

_CONVERTER = (
    Path(__file__).resolve().parents[1]
    / "scripts" / "harbor" / "converter.py"
)

_VALID_DOCKERFILE = (
    "FROM debian:bookworm-slim\n"
    "# marker for language-specific fixes\n"
    "\n"
    "RUN apt-get update && apt-get install -y curl\n"
)

_BROKEN_DOCKERFILE = "FROM debian:bookworm-slim\nRUN apt-get update && true\n"


def test_cpp_raises_on_missing_anchor():
    with pytest.raises(RuntimeError, match="missing required anchor"):
        inject_dockerfile_language_patches(_BROKEN_DOCKERFILE, "c++")


def test_java_raises_on_missing_anchor():
    with pytest.raises(RuntimeError, match="missing required anchor"):
        inject_dockerfile_language_patches(_BROKEN_DOCKERFILE, "java")


def test_python_falls_through_unchanged():
    result = inject_dockerfile_language_patches(_BROKEN_DOCKERFILE, "python")
    assert result == _BROKEN_DOCKERFILE


def test_source_uses_raise_not_silent_fallthrough():
    source = _CONVERTER.read_text(encoding="utf-8")
    assert "raise RuntimeError(" in source
    assert "missing required anchor for language" in source
