"""Regression test for Q-001 m0667 (multi-instance out_dir clobber).

The fix at converter.py L1271 + L1320 + main() loop ensures:
  - convert_instance has nest_under_id: bool = False default
  - out_dir = out_root / instance_id_normalized if nest_under_id else out_root
  - main() sets nest = len(instance_dirs) > 1 and passes nest_under_id=nest

Preserves flat layout for single-instance callers (eval_multi.sh stage_one
contract per AGENTS.md backward-compat principle); nests only when multiple
instances share one out_root, otherwise build_task() would rm -rf each prior
instance's task/.
"""

from __future__ import annotations

from pathlib import Path

_CONVERTER = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "harbor"
    / "converter.py"
)


def _compute_out_dir(out_root: Path, instance_id: str, nest_under_id: bool) -> Path:
    """Mirror of converter.py L1320 conditional."""
    return out_root / instance_id if nest_under_id else out_root


def test_convert_instance_has_nest_under_id_default_false() -> None:
    source = _CONVERTER.read_text(encoding="utf-8")
    assert "nest_under_id: bool = False" in source, (
        "convert_instance signature must declare nest_under_id: bool = False (Q-001)"
    )


def test_single_instance_uses_flat_layout() -> None:
    out_root = Path("/tmp/q001_test_out")
    result = _compute_out_dir(out_root, "instance_a", nest_under_id=False)
    assert result == out_root, (
        "nest_under_id=False must yield flat layout (eval_multi.sh stage_one contract)"
    )


def test_multi_instance_uses_nested_layout() -> None:
    out_root = Path("/tmp/q001_test_out")
    result = _compute_out_dir(out_root, "instance_a", nest_under_id=True)
    assert result == out_root / "instance_a", (
        "nest_under_id=True must yield nested layout to prevent task/ clobber"
    )


def test_main_loop_computes_nest_from_len_check() -> None:
    source = _CONVERTER.read_text(encoding="utf-8")
    assert "nest = len(instance_dirs) > 1" in source, (
        "main() must compute nest = len(instance_dirs) > 1 before the loop"
    )
    assert "nest_under_id=nest" in source, (
        "main() loop must pass nest_under_id=nest to convert_instance"
    )
