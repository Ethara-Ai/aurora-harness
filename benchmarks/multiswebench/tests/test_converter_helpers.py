from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

import pytest

from benchmarks.multiswebench.scripts.harbor.converter import (
    LANGUAGE_COMMANDS,
    RESOURCE_CONFIG,
    get_language_commands,
    get_resource_config,
    iso8601_microseconds,
    iso8601_microseconds_offset,
    map_difficulty,
    provider_name_split,
    random_trial_suffix,
    read_text,
    render_literal,
    sanitize_task_id,
    sha256_of_dir,
    to_ecr_image,
)


def test_read_text_returns_file_contents(tmp_path: Path):
    f = tmp_path / "x.txt"
    f.write_text("hello\nworld", encoding="utf-8")
    assert read_text(f) == "hello\nworld"


def test_read_text_raises_file_not_found(tmp_path: Path):
    with pytest.raises(FileNotFoundError, match="Missing file"):
        read_text(tmp_path / "missing.txt")


def test_render_literal_replaces_known_keys():
    out = render_literal("a={a} b={b}", a="1", b="two")
    assert out == "a=1 b=two"


def test_render_literal_preserves_unknown_keys():
    out = render_literal("known={a} unknown={x}", a="1")
    assert out == "known=1 unknown={x}"


def test_render_literal_handles_no_placeholders():
    assert render_literal("plain text", a="x") == "plain text"


def test_render_literal_repeated_placeholder():
    out = render_literal("{n} {n} {n}", n="bob")
    assert out == "bob bob bob"


def test_render_literal_ignores_non_word_chars():
    out = render_literal("{not-a-key} {fine}", fine="ok")
    assert "{not-a-key}" in out
    assert "ok" in out


def test_sanitize_task_id_strips_separators():
    assert sanitize_task_id("apache/commons-cli:pr-42") == "apache_commonscli_pr42"


def test_sanitize_task_id_lowercases():
    assert sanitize_task_id("FOO/BAR") == "foo_bar"


def test_sanitize_task_id_prepends_task_prefix_when_first_char_not_alpha():
    assert sanitize_task_id("123abc").startswith("task_")


def test_sanitize_task_id_no_prefix_when_starts_with_letter():
    assert sanitize_task_id("alpha-beta") == "alphabeta"


def test_map_difficulty_15min_is_easy():
    assert map_difficulty(time_estimate="15min") == "easy"


def test_map_difficulty_1h_is_medium():
    assert map_difficulty(time_estimate="1h") == "medium"


def test_map_difficulty_4h_is_hard():
    assert map_difficulty(time_estimate="4h") == "hard"


def test_map_difficulty_patch_lines_under_20_is_easy():
    assert map_difficulty(patch_lines=10) == "easy"


def test_map_difficulty_patch_lines_under_100_is_medium():
    assert map_difficulty(patch_lines=50) == "medium"


def test_map_difficulty_patch_lines_100_or_more_is_hard():
    assert map_difficulty(patch_lines=200) == "hard"


def test_map_difficulty_no_signals_defaults_to_medium():
    assert map_difficulty() == "medium"


def test_map_difficulty_time_estimate_dominates_patch_lines():
    assert map_difficulty(time_estimate="15min", patch_lines=500) == "easy"


def test_to_ecr_image_format():
    assert to_ecr_image("reg", "apache", "kafka", 42) == "reg/apache_m_kafka:pr-42"


def test_get_resource_config_known_language_repo_specific():
    cfg = get_resource_config("c", "ponyc/foo")
    assert cfg["memory_mb"] == 16384


def test_get_resource_config_falls_back_to_lang_default():
    cfg = get_resource_config("c", "unknown-repo")
    assert cfg["memory_mb"] == 8192


def test_get_resource_config_unknown_language_falls_back_to_global_default():
    cfg = get_resource_config("brainfuck", "x")
    assert cfg == RESOURCE_CONFIG["_default"]["_default"]


def test_get_resource_config_case_insensitive_on_language():
    cfg = get_resource_config("JAVA", "dubbo")
    assert cfg["memory_mb"] == 16384


def test_get_resource_config_repo_matches_substring_case_insensitive():
    cfg = get_resource_config("typescript", "facebook/Material-UI-Pickers")
    assert cfg["memory_mb"] == 16384


def test_get_language_commands_python():
    assert get_language_commands("python") == LANGUAGE_COMMANDS["python"]


def test_get_language_commands_case_insensitive():
    assert get_language_commands("PYTHON") == LANGUAGE_COMMANDS["python"]


def test_get_language_commands_unknown_returns_placeholders():
    run, test = get_language_commands("foo-lang")
    assert "appropriate" in run
    assert "appropriate" in test


def test_iso8601_microseconds_normalizes_z_suffix():
    out = iso8601_microseconds("2024-01-01T12:00:00Z")
    assert out.endswith("Z")
    assert "+00:00" not in out
    assert "2024-01-01" in out


def test_iso8601_microseconds_returns_now_when_blank():
    out = iso8601_microseconds("")
    parsed = datetime.fromisoformat(out.replace("Z", "+00:00"))
    assert (datetime.now(timezone.utc) - parsed).total_seconds() < 5


def test_iso8601_microseconds_returns_now_when_none():
    out = iso8601_microseconds(None)
    assert out.endswith("Z")


def test_iso8601_microseconds_passthrough_on_unparseable():
    assert iso8601_microseconds("not a date") == "not a date"


def test_iso8601_microseconds_offset_keeps_offset_suffix():
    out = iso8601_microseconds_offset("2024-01-01T12:00:00Z")
    assert out.endswith("+00:00")
    assert not out.endswith("Z")


def test_iso8601_microseconds_offset_returns_now_when_none():
    out = iso8601_microseconds_offset(None)
    assert "+00:00" in out


def test_iso8601_microseconds_offset_passthrough_on_unparseable():
    assert iso8601_microseconds_offset("bad") == "bad"


def test_iso8601_microseconds_naive_input_assumed_utc():
    out = iso8601_microseconds("2024-06-15T10:30:00")
    assert "2024-06-15T10:30:00" in out
    assert out.endswith("Z")


def test_provider_name_split_with_dot():
    assert provider_name_split("openai.gpt-4") == ("openai", "gpt-4")


def test_provider_name_split_without_dot():
    assert provider_name_split("claude") == ("", "claude")


def test_provider_name_split_multiple_dots_only_partitions_once():
    assert provider_name_split("a.b.c") == ("a", "b.c")


def test_random_trial_suffix_default_length():
    out = random_trial_suffix()
    assert len(out) == 7
    assert re.fullmatch(r"[A-Za-z0-9]+", out)


def test_random_trial_suffix_custom_length():
    out = random_trial_suffix(length=12)
    assert len(out) == 12


def test_random_trial_suffix_uses_alnum_only():
    for _ in range(50):
        out = random_trial_suffix(20)
        assert re.fullmatch(r"[A-Za-z0-9]+", out)


def test_sha256_of_dir_deterministic(tmp_path: Path):
    (tmp_path / "a.txt").write_text("hello")
    (tmp_path / "b.txt").write_text("world")
    h1 = sha256_of_dir(tmp_path)
    h2 = sha256_of_dir(tmp_path)
    assert h1 == h2
    assert len(h1) == 64


def test_sha256_of_dir_changes_with_content(tmp_path: Path):
    (tmp_path / "a.txt").write_text("hello")
    h1 = sha256_of_dir(tmp_path)
    (tmp_path / "a.txt").write_text("hello!")
    h2 = sha256_of_dir(tmp_path)
    assert h1 != h2


def test_sha256_of_dir_changes_with_filename(tmp_path: Path):
    (tmp_path / "a.txt").write_text("x")
    h1 = sha256_of_dir(tmp_path)
    (tmp_path / "a.txt").rename(tmp_path / "renamed.txt")
    h2 = sha256_of_dir(tmp_path)
    assert h1 != h2


def test_sha256_of_dir_ignores_subdir_paths_consistently(tmp_path: Path):
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "x.txt").write_text("nested")
    h1 = sha256_of_dir(tmp_path)
    h2 = sha256_of_dir(tmp_path)
    assert h1 == h2
