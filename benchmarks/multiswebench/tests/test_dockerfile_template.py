from pathlib import Path

DOCKERFILE_PATH = (
    Path(__file__).resolve().parent.parent
    / "scripts"
    / "harbor"
    / "task-template"
    / "environment"
    / "Dockerfile"
)


def _read_dockerfile() -> str:
    return DOCKERFILE_PATH.read_text(encoding="utf-8")


def _python_fetch_stage(text: str) -> str:
    fetch_start = text.index("FROM debian:bookworm-slim AS python-fetch")
    base_start = text.index("FROM {base_image}", fetch_start)
    return text[fetch_start:base_start]


def test_python_fetch_stage_sets_shell_pipefail():
    stage = _python_fetch_stage(_read_dockerfile())
    assert 'SHELL ["/bin/bash", "-eo", "pipefail", "-c"]' in stage


def test_shell_pipefail_precedes_curl_pipe():
    stage = _python_fetch_stage(_read_dockerfile())
    shell_pos = stage.index("SHELL [")
    curl_pos = stage.index("curl -fsSL")
    assert shell_pos < curl_pos


def test_curl_tar_pipe_format_preserved():
    text = _read_dockerfile()
    assert "curl -fsSL" in text
    assert "| tar -xzC /opt/python --strip-components=1" in text


def test_q002_language_patch_marker_present():
    text = _read_dockerfile()
    assert text.count("# marker for language-specific fixes") == 1


def test_msb_ref_arg_preserved():
    text = _read_dockerfile()
    assert "ARG MSB_REF=main" in text


def test_user_root_preserved():
    text = _read_dockerfile()
    assert "USER root" in text


def test_workdir_template_preserved():
    text = _read_dockerfile()
    assert "WORKDIR /workspace/{repo_name}" in text


def test_base_image_template_preserved():
    text = _read_dockerfile()
    assert "FROM {base_image}" in text
