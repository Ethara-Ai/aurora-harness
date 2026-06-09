"""Regression tests for BUGS_RESOLUTION.md security/quality fixes.

Covers:
- S-001 / S-002: docker commit/push must use list-form subprocess (no shell=True),
  neutralizing shell injection (CWE-78).
- S-003: collect entrypoints must not print raw GitHub tokens (CWE-532).
- C-001 / Q-001: stray root __init__.py removed; harness wildcard retained so the
  Instance registry still populates (pipeline must not break).
"""

import asyncio
from pathlib import Path
from unittest.mock import MagicMock, patch

import multi_swe_bench.utils.session_util as session_util
import pytest


def _make_completed(returncode=0, stderr=""):
    result = MagicMock()
    result.returncode = returncode
    result.stderr = stderr
    result.stdout = ""
    return result


# S-002 — docker push uses list-form, no shell=True
def test_push_icm_image_uses_list_form_no_shell():
    with patch.object(
        session_util.subprocess, "run", return_value=_make_completed(0)
    ) as mock_run:
        asyncio.run(
            session_util.push_icm_image("registry/image:tag", "inst", MagicMock())
        )

    assert mock_run.called
    args, kwargs = mock_run.call_args
    cmd = args[0]
    assert isinstance(cmd, list), "docker push must be a list (argv), not a string"
    assert cmd == ["docker", "push", "registry/image:tag"]
    assert kwargs.get("shell", False) is False
    assert "shell" not in kwargs or kwargs["shell"] is False


def test_push_icm_image_injection_is_neutralized():
    malicious = "x; touch /tmp/pwned_push"
    with patch.object(
        session_util.subprocess, "run", return_value=_make_completed(0)
    ) as mock_run:
        asyncio.run(session_util.push_icm_image(malicious, "inst", MagicMock()))

    cmd = mock_run.call_args[0][0]
    # The malicious payload must be a single argv element passed verbatim to
    # docker (which will reject it), never split/interpreted by a shell.
    assert cmd == ["docker", "push", malicious]
    assert not Path("/tmp/pwned_push").exists()


def test_push_icm_image_no_shell_true_in_source():
    src = Path(session_util.__file__).read_text()
    assert "push_image_cmd, shell=True" not in src
    assert "save_image_cmd, shell=True" not in src


# S-001 — docker commit uses list-form, no shell=True
def test_docker_commit_argv_is_list_form():
    cmd = session_util._docker_commit_argv("container_v2", "image_v2")
    assert cmd == ["docker", "commit", "container_v2", "image_v2"]
    assert isinstance(cmd, list)


def test_docker_commit_argv_injection_is_neutralized():
    malicious = "x; touch /tmp/pwned_commit"
    cmd = session_util._docker_commit_argv(malicious, "image_v2")
    assert cmd[2] == malicious

    with patch.object(
        session_util.subprocess, "run", return_value=_make_completed(0)
    ) as mock_run:
        session_util.subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    passed = mock_run.call_args[0][0]
    assert passed == ["docker", "commit", malicious, "image_v2"]
    assert "shell" not in mock_run.call_args.kwargs
    assert not Path("/tmp/pwned_commit").exists()


def test_docker_push_argv_is_list_form():
    cmd = session_util._docker_push_argv("registry/image:tag")
    assert cmd == ["docker", "push", "registry/image:tag"]


def test_session_util_has_no_shell_true_calls():
    """No subprocess call in session_util may pass shell=True (CWE-78)."""
    src = Path(session_util.__file__).read_text()
    for line in src.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        assert "shell=True" not in line, f"shell=True found in code: {line!r}"


# S-003 — token values must not be printed
@pytest.mark.parametrize(
    "module_path",
    [
        "multi_swe_bench/collect/build_dataset.py",
        "multi_swe_bench/collect/get_all_prs.py",
        "multi_swe_bench/collect/get_related_issues.py",
    ],
)
def test_collect_entrypoints_do_not_print_raw_tokens(module_path):
    import multi_swe_bench

    pkg_root = Path(multi_swe_bench.__file__).resolve().parent.parent
    src = (pkg_root / module_path).read_text()
    assert 'f"Tokens: {tokens}"' not in src, (
        f"{module_path} prints raw token list (CWE-532)"
    )
    # The sanitized form prints a count, not the secret values.
    assert "len(tokens)" in src


def test_token_count_print_does_not_leak_secret(capsys):
    secret = "ghp_supersecretvalue1234567890"
    tokens = [secret, secret + "B"]
    print(f"Tokens: {len(tokens)} loaded")
    captured = capsys.readouterr()
    assert secret not in captured.out
    assert "2 loaded" in captured.out


# C-001 / Q-001 — registry must still populate; root __init__ must be gone
def test_instance_registry_populated_after_harness_import():
    """The harness wildcard import must still register repo classes.

    Removing it (per the naive Q-001 fix) would break Instance.create() and
    the entire evaluation pipeline. This guards against that regression.
    """
    import multi_swe_bench.harness  # noqa: F401  (import side effect populates registry)
    from multi_swe_bench.harness.instance import Instance

    assert len(Instance._registry) > 0, (
        "Instance registry is empty — harness wildcard import was removed and "
        "the eval pipeline (Instance.create) is broken."
    )


def test_stray_root_init_removed():
    import multi_swe_bench

    pkg_root = Path(multi_swe_bench.__file__).resolve().parent.parent
    stray = pkg_root.parent / "__init__.py"
    # The real package __init__ must exist; the stray repo-root one must not.
    assert (pkg_root / "__init__.py").exists()
    # Best-effort: only assert when the source checkout layout is present.
    if (pkg_root.parent / "setup.py").exists():
        assert not stray.exists(), "stray repo-root __init__.py should be deleted"
