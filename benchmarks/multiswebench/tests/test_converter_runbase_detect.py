"""Regression anchor for R-002: converter.py run_base_dir detection precedence.

The predicate at the run_base_dir detection site previously parsed as
`(child.is_dir() and (child/"run_1").exists()) or child.name.startswith("run_")`
because of Python operator precedence. A stray top-level file whose name
started with "run_" was enough to misclassify the entire tree as a single
instance. Inner parens now gate the OR clause by `child.is_dir()`.
"""

from pathlib import Path

_CONVERTER = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "harbor"
    / "converter.py"
)


def _predicate(child: Path) -> bool:
    """Mirror of the converter.py L1402 predicate post-fix."""
    return child.is_dir() and (
        (child / "run_1").exists() or child.name.startswith("run_")
    )


def test_inner_parens_present_in_source():
    text = _CONVERTER.read_text(encoding="utf-8")
    assert (
        'child.is_dir() and ((child / "run_1").exists() '
        'or child.name.startswith("run_"))' in text
    ), "R-002 inner parens missing from converter.py run_base_dir detection"
    assert (
        'child.is_dir() and (child / "run_1").exists() '
        'or child.name.startswith("run_")\n' not in text
    ), "R-002 unparenthesised predicate still present in converter.py"


def test_stray_run_file_excluded(tmp_path: Path):
    stray = tmp_path / "run_orphan.txt"
    stray.write_text("not a dir")
    assert _predicate(stray) is False


def test_valid_run_dir_detected(tmp_path: Path):
    instance = tmp_path / "run_42"
    instance.mkdir()
    (instance / "run_1").mkdir()
    assert _predicate(instance) is True


def test_non_dir_with_arbitrary_name_rejected(tmp_path: Path):
    other = tmp_path / "scratch"
    other.write_text("non-dir, non-run prefix")
    assert _predicate(other) is False
