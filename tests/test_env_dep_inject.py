"""Unit tests for env_dep_inject.run_commands (INVENTORY.md §C.2)."""

import pytest

from benchmarks.multiswebench.scripts.eval.env_dep_inject import run_commands


REQUIRED_KEYS = {"run_cmd", "test_patch_run_cmd", "fix_patch_run_cmd"}

ALL_LANGUAGES = [
    "python", "py",
    "javascript", "js", "node",
    "typescript", "ts",
    "go", "golang",
    "java",
    "rust", "rs",
]


class TestReturnShape:
    @pytest.mark.parametrize("lang", ALL_LANGUAGES)
    def test_returns_dict_with_three_canonical_keys(self, lang):
        result = run_commands(lang, "/tmp/ds.jsonl", "FIX_PLACEHOLDER")
        assert isinstance(result, dict)
        assert set(result.keys()) == REQUIRED_KEYS

    @pytest.mark.parametrize("lang", ALL_LANGUAGES)
    def test_no_legacy_key_run_patch_run_cmd(self, lang):
        result = run_commands(lang, "/tmp/ds.jsonl", "FIX")
        assert "run_patch_run_cmd" not in result, (
            "Found legacy key 'run_patch_run_cmd' — upstream uses 'run_cmd' "
            "(see instance.run(run_cmd: str = '') signature)."
        )

    @pytest.mark.parametrize("lang", ALL_LANGUAGES)
    def test_all_values_are_non_empty_strings(self, lang):
        result = run_commands(lang, "/tmp/ds.jsonl", "FIX")
        for k, v in result.items():
            assert isinstance(v, str) and v, f"Key {k!r} returned empty: {v!r}"


class TestFixCmdPassthrough:
    @pytest.mark.parametrize("lang", ALL_LANGUAGES)
    def test_fix_cmd_returned_verbatim(self, lang):
        sentinel = "echo SENTINEL_FIX_CMD_VALUE_12345"
        result = run_commands(lang, "/tmp/ds.jsonl", sentinel)
        assert result["fix_patch_run_cmd"] == sentinel

    @pytest.mark.parametrize("lang", ALL_LANGUAGES)
    def test_fix_cmd_preserves_special_chars(self, lang):
        sentinel = "bash /home/fix-run.sh && echo 'done' || exit 1"
        result = run_commands(lang, "/tmp/ds.jsonl", sentinel)
        assert result["fix_patch_run_cmd"] == sentinel


class TestLanguageDispatch:
    def test_python_uses_uv_or_venv(self):
        cmds = run_commands("python", "/tmp/ds.jsonl", "FIX")
        assert "uv venv" in cmds["run_cmd"] or "python3 -m venv" in cmds["run_cmd"]
        assert "pytest" in cmds["run_cmd"]

    @pytest.mark.parametrize("alias", ["py", "PYTHON", "Py"])
    def test_python_aliases_match_python(self, alias):
        canon = run_commands("python", "/tmp/ds.jsonl", "FIX")
        alias_result = run_commands(alias, "/tmp/ds.jsonl", "FIX")
        assert alias_result == canon

    def test_javascript_uses_pnpm_or_npm(self):
        cmds = run_commands("javascript", "/tmp/ds.jsonl", "FIX")
        assert "pnpm" in cmds["run_cmd"] or "npm" in cmds["run_cmd"]

    @pytest.mark.parametrize("alias", ["js", "node", "JavaScript"])
    def test_js_aliases_match_javascript(self, alias):
        canon = run_commands("javascript", "/tmp/ds.jsonl", "FIX")
        assert run_commands(alias, "/tmp/ds.jsonl", "FIX") == canon

    def test_typescript_includes_build_step(self):
        cmds = run_commands("typescript", "/tmp/ds.jsonl", "FIX")
        assert "build" in cmds["run_cmd"].lower()

    @pytest.mark.parametrize("alias", ["ts"])
    def test_typescript_aliases_match_typescript(self, alias):
        canon = run_commands("typescript", "/tmp/ds.jsonl", "FIX")
        assert run_commands(alias, "/tmp/ds.jsonl", "FIX") == canon

    def test_go_uses_go_test(self):
        cmds = run_commands("go", "/tmp/ds.jsonl", "FIX")
        assert "go test" in cmds["run_cmd"]

    @pytest.mark.parametrize("alias", ["golang", "Go"])
    def test_go_aliases_match_go(self, alias):
        canon = run_commands("go", "/tmp/ds.jsonl", "FIX")
        assert run_commands(alias, "/tmp/ds.jsonl", "FIX") == canon

    def test_java_uses_mvn_or_gradle(self):
        cmds = run_commands("java", "/tmp/ds.jsonl", "FIX")
        assert "mvn" in cmds["run_cmd"] or "gradle" in cmds["run_cmd"]

    def test_rust_uses_cargo(self):
        cmds = run_commands("rust", "/tmp/ds.jsonl", "FIX")
        assert "cargo" in cmds["run_cmd"]

    @pytest.mark.parametrize("alias", ["rs"])
    def test_rust_aliases_match_rust(self, alias):
        canon = run_commands("rust", "/tmp/ds.jsonl", "FIX")
        assert run_commands(alias, "/tmp/ds.jsonl", "FIX") == canon


class TestFallbackToPython:
    @pytest.mark.parametrize("lang", ["", "unknown-lang", None, "csharp", "ruby"])
    def test_unknown_or_empty_falls_back_to_python(self, lang):
        canon = run_commands("python", "/tmp/ds.jsonl", "FIX")
        assert run_commands(lang, "/tmp/ds.jsonl", "FIX") == canon


class TestCaseInsensitivity:
    @pytest.mark.parametrize("variant", ["PYTHON", "Python", "  python  "])
    def test_lang_is_normalized(self, variant):
        canon = run_commands("python", "/tmp/ds.jsonl", "FIX")
        assert run_commands(variant, "/tmp/ds.jsonl", "FIX") == canon


class TestDatasetFileIgnored:
    @pytest.mark.parametrize(
        "ds_file",
        ["/tmp/a.jsonl", "/different/path.jsonl", "", "not-even-a-path"],
    )
    def test_dataset_file_does_not_affect_output(self, ds_file):
        a = run_commands("python", ds_file, "FIX")
        b = run_commands("python", "/some/other/path", "FIX")
        assert a == b
