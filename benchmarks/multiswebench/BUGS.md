# BUGS.md — Multi-SWE-Bench Harness Audit Tickets

Commit `e3578a1838c178b6a166ba934bfc7bd12bb83871` | 2026-06-15. One ticket per HOLD/BLOCK finding plus every HIGH/CRITICAL-security finding. Disposition vocabulary: SHIP / HOLD / BLOCK.

---

## BUG-T-001 — Benchmark scoring tests are not run by CI

- **Issue Key:** BUG-T-001 | **Type:** Bug (CI gap) | **Priority:** P1 | **Severity:** HIGH | **Status:** Resolved (2026-06-15) | **Resolution:** Fixed — `tests.yml` now runs `benchmarks/multiswebench/tests tests/`; 259 tests pass (REPORT CMD-025)
- **Components:** CI / test gate, multiswebench scoring tests | **Labels:** ci, testing, scoring, blocker
- **Affects Version:** e3578a1 | **Fix Version:** TBD | **Environment:** GitHub Actions (`.github/workflows/tests.yml`)
- **CWE:** N/A | **Exploitable-by:** N/A (Failure Mode below)

**Summary:** CI runs only top-level `tests/`; the 100+ tests under `benchmarks/multiswebench/tests/` (the only ones covering `score_v2g`, `convert`, `data_change`, config injection) never execute, so scoring-logic regressions ship green.

**Description / Evidence:**
`SRC:.github/workflows/tests.yml:52-57`:
```
CI=true uv run python -m pytest -vvs --forked --cov=benchmarks ... tests/
```
CMD-013: `tests/` has no score/multiswe test file. CMD-014: top-level tests import only `evaluation, iterative, models, constants, run_infer` — not the scoring modules. precommit.yml runs only ruff/pycodestyle/pyright.

**Steps to Reproduce:**
1. `grep pytest .github/workflows/tests.yml` -> target is `tests/`.
2. `ls benchmarks/multiswebench/tests/` -> 100+ tests including `test_score_v2g.py`.
3. Confirm no CI job references that path.

**Expected:** the scoring tests gate merges. **Actual:** they are never run by CI.

**Impact:** a regression in the score formula or prediction-conversion parse passes CI and silently shifts benchmark numbers across an eval campaign.

**Failure Mode:** undetected scoring drift after a refactor.

**Suggested Fix:** run `benchmarks/**/tests` in CI (add `hypothesis`, see BUG-T-002); keep/raise `--cov-fail-under`.

**Acceptance Criteria:**
- [ ] CI runs `benchmarks/multiswebench/tests` on every PR.
- [ ] A deliberately broken score gate makes the job fail.
- [ ] Coverage floor covers the scoring modules.

---

## BUG-D-001 — Production grader fork pinned to moving `main` ref

- **Issue Key:** BUG-D-001 | **Type:** Bug (reproducibility) | **Priority:** P1 | **Severity:** HIGH | **Status:** Closed — Accepted Risk (2026-06-15) | **Resolution:** Won't Fix — `rev="main"` intentional (auto-tracks registry updates); `uv.lock` pins commit `73926adb` for `--frozen`/CI installs. Follow-up: pin to a SHA before any published cross-time campaign.
- **Components:** dependencies, scoring harness | **Labels:** reproducibility, supply-chain, blocker
- **Affects Version:** e3578a1 | **Fix Version:** TBD | **Environment:** uv / pyproject
- **CWE:** CWE-1357 (reliance on insufficiently-controlled component) | **Exploitable-by:** N/A

**Summary:** `multi-swe-bench` (the production scorer) is pinned to `rev = "main"`, a mutable branch, so the grader can change underfoot.

**Description / Evidence:**
`SRC:pyproject.toml:122`: `multi-swe-bench = { git = "...Ethara-Ai/multi-swe-bench.git", rev = "main" }`.
`SRC:benchmarks/multiswebench/eval_infer.py:79-89`: invokes `python -m multi_swe_bench.harness.run_evaluation`.
Other git deps (`swt-bench`, `commit0`, `litellm`) are pinned to SHAs — `multi-swe-bench` is the exception.

**Steps to Reproduce:** `grep 'multi-swe-bench' pyproject.toml` -> `rev = "main"`.

**Expected:** grader pinned to an immutable SHA. **Actual:** pinned to a branch.

**Impact:** identical predictions can score differently after an upstream push + relock, with no traceable change in this repo. Breaks benchmark reproducibility.

**Failure Mode:** silent grader drift.

**Suggested Fix:** pin to an explicit commit SHA; add a CI check rejecting branch refs in `[tool.uv.sources]`.

**Acceptance Criteria:**
- [ ] `grep 'multi-swe-bench' pyproject.toml` shows a 40-char SHA.
- [ ] CI fails if any `[tool.uv.sources]` entry uses a branch ref.

---

## BUG-R-001 — eval_infer default dataset resolves to a nonexistent local path

- **Issue Key:** BUG-R-001 | **Type:** Bug | **Priority:** P2 | **Severity:** MEDIUM | **Status:** Closed — Accepted (2026-06-15) | **Resolution:** Won't Fix — EC2 deployment imports the dataset locally; HF default-name download branch never exercised.
- **Components:** eval_infer dataset resolution | **Labels:** reliability, ux
- **Affects Version:** e3578a1 | **Fix Version:** TBD | **Environment:** `multiswebench-eval` CLI
- **CWE:** CWE-665 (improper initialization) | **Exploitable-by:** N/A

**Summary:** The default dataset name `bytedance-research/Multi-SWE-Bench` does not match the case-sensitive `ByteDance-Seed/Multi-SWE-bench` download trigger, so it is resolved as a filesystem path that won't exist and handed to the grader.

**Description / Evidence:** `SRC:benchmarks/multiswebench/eval_infer.py:51-70` and line 119 (argparse default). CMD-019 shows the mismatch.

**Steps to Reproduce:** call `run_multi_swebench_evaluation(input_file=...)` (no `dataset_name`) or `multiswebench-eval out.jsonl` without `--dataset`.

**Expected:** clear "dataset not found" error or a working default. **Actual:** a nonexistent resolved path is passed to the harness, which fails later with a confusing error.

**Impact:** confusing failures on the standalone eval entry point. (`run_infer.py` requires `--dataset`, limiting blast radius.)

**Suggested Fix:** validate `os.path.isfile(dataset_path)` before invoking the harness, or require `--dataset`.

**Acceptance Criteria:**
- [ ] Missing/invalid dataset fails fast with an actionable message before subprocess launch.

---

## BUG-R-002 — Greedy global sed may double-apply patches in fix-run.sh

- **Issue Key:** BUG-R-002 | **Type:** Bug | **Priority:** P2 | **Severity:** MEDIUM | **Status:** Resolved (2026-06-15) | **Resolution:** Fixed — `_APPLY_PATCH_HELPER` idempotency guard (`git apply --reverse --check`) neutralizes the greedy-sed double-apply; behaviorally verified (REPORT CMD-027) + 2 regression tests (CMD-028).
- **Components:** production patch-apply / scoring config | **Labels:** reliability, scoring, fragile
- **Affects Version:** e3578a1 | **Fix Version:** TBD | **Environment:** grader container (`fix_patch_run_cmd`)
- **CWE:** CWE-697 (incorrect comparison/over-broad match) | **Exploitable-by:** N/A

**Summary:** `sed -i 's@git apply.*@<test+fix apply>@g' /home/fix-run.sh` is global and greedy: every `git apply` line is replaced with the full two-patch apply. If upstream `fix-run.sh` has more than one such line, patches get applied multiple times.

**Description / Evidence:** `SRC:benchmarks/multiswebench/scripts/eval/update_multi_swe_bench_config.py:46-54`. Correctness depends on the upstream fork's `fix-run.sh` having exactly one `git apply` line (third-party, not verified here — Residual Risk C-2).

**Steps to Reproduce:** inspect `_build_fix_patch_run_cmd()`; note `g` flag + `.*`.

**Expected:** each patch applied exactly once at the intended location. **Actual:** any second `git apply` line triggers duplicate application.

**Impact:** corrupted pass/fail signal on the production scoring path (this builds the verifier command the grader runs).

**Failure Mode:** mis-scored instances when upstream fix-run.sh structure changes.

**Suggested Fix:** anchor the sed to the specific known line, or template `fix-run.sh` directly; assert the substitution match count.

**Acceptance Criteria:**
- [ ] A test pins the rewritten `fix-run.sh` for a representative upstream template and asserts each patch applies exactly once.

---

## BUG-D-002 — 71 known CVEs across 22 installed dependencies

- **Issue Key:** BUG-D-002 | **Type:** Vulnerability (dependencies) | **Priority:** P2 | **Severity:** MEDIUM | **Status:** Closed — Accepted Risk (2026-06-15) | **Resolution:** Won't Fix now — CVE list time-sensitive (valid as of SHA/date); deps are pinned forks; re-scan + patch reachable high-sev per campaign.
- **Components:** dependency tree | **Labels:** security, dependencies, cve
- **Affects Version:** e3578a1 (as of 2026-06-15) | **Fix Version:** TBD | **Environment:** project `.venv`
- **CWE:** CWE-1395 (dependency on vulnerable component) | **Exploitable-by:** depends on advisory; HTTP/LLM stack is directly exercised

**Summary:** pip-audit reports 71 advisories in 22 installed packages, including the directly-used HTTP/LLM stack.

**Description / Evidence:** CMD-009 (pip-audit 2.10.1). Examples: `aiohttp 3.13.3` (12; fix 3.13.4/3.14.0), `litellm 1.82.1` (7), `cryptography 46.0.5`, `lxml 6.0.2`, `urllib3`, `requests`, `pillow`, `starlette`, `gitpython`, `idna`, `pyjwt`, `authlib`. Time-sensitive. Mostly transitive via the SDK.

**Steps to Reproduce:** run pip-audit against the venv package set (CMD-009).

**Expected:** 0 advisories on directly-used packages. **Actual:** 71 across 22 packages.

**Impact:** exploitable surface in the HTTP/LLM client path used during eval runs.

**Suggested Fix:** `uv lock --upgrade` the affected packages to fix versions; add pip-audit to CI.

**Acceptance Criteria:**
- [ ] pip-audit reports 0 advisories for aiohttp/litellm/urllib3/requests/cryptography/lxml.
- [ ] pip-audit runs in CI.

---

## BUG-T-002 — Property-based score tests cannot run (hypothesis missing)

- **Issue Key:** BUG-T-002 | **Type:** Bug (test infra) | **Priority:** P2 | **Severity:** MEDIUM | **Status:** Resolved (2026-06-15) | **Resolution:** Fixed — `hypothesis>=6.0.0` added to dev group + `uv.lock` (REPORT CMD-023/024); 15 property tests pass (CMD-025)
- **Components:** score formula property tests | **Labels:** testing, dependencies
- **Affects Version:** e3578a1 | **Fix Version:** TBD | **Environment:** project `.venv` / uv.lock
- **CWE:** N/A | **Exploitable-by:** N/A

**Summary:** `test_score_v2g_properties.py` imports `hypothesis`, which is absent from the venv and from `uv.lock`, so the strongest scoring-correctness test errors on collection.

**Description / Evidence:** `SRC:benchmarks/multiswebench/tests/test_score_v2g_properties.py:19`; CMD-015 (`ModuleNotFoundError: No module named 'hypothesis'`); CMD-016 (`grep -c hypothesis uv.lock == 0`).

**Steps to Reproduce:** `.venv/bin/python -m pytest benchmarks/multiswebench/tests/test_score_v2g_properties.py` -> collection error.

**Expected:** test collects and runs. **Actual:** ImportError.

**Impact:** the property invariants protecting the score formula are inert; compounds BUG-T-001.

**Suggested Fix:** add `hypothesis` to `[dependency-groups].dev`; `uv lock`.

**Acceptance Criteria:**
- [ ] `hypothesis` present in uv.lock.
- [ ] The property test file collects and passes in CI.

---

## BUG-R-003 — Per-instance timeout cannot interrupt a running worker

- **Issue Key:** BUG-R-003 | **Type:** Bug | **Priority:** P2 | **Severity:** MEDIUM | **Status:** Closed — Accepted (2026-06-15) | **Resolution:** Won't Fix — 14–15h tasks handled by operator manual intervention.
- **Components:** evaluation orchestrator | **Labels:** reliability, concurrency, throughput
- **Affects Version:** e3578a1 | **Fix Version:** TBD | **Environment:** ProcessPoolExecutor
- **CWE:** CWE-400 (uncontrolled resource consumption) | **Exploitable-by:** N/A

**Summary:** On per-instance timeout, the orchestrator marks the instance failed but `fut.cancel()` cannot stop an already-running worker; it stays busy until pool shutdown.

**Description / Evidence:** `SRC:benchmarks/utils/evaluation.py:66-75` (the field's own docstring) and `SRC:benchmarks/utils/evaluation.py:470-472`.

**Steps to Reproduce:** start an instance that hangs past `instance_timeout`; observe the worker remains occupied.

**Expected:** timed-out instance frees its worker. **Actual:** worker occupied until pool shutdown.

**Impact:** a few hung instances throttle throughput of a long eval run and skew wall-clock accounting.

**Failure Mode:** degraded parallelism / stalled runs.

**Suggested Fix:** hard-kill the worker PID (SIGTERM/SIGKILL) on timeout, or run each instance as a killable subprocess; otherwise document the accepted limitation explicitly.

**Acceptance Criteria:**
- [ ] An instrumented hung instance frees its worker within ~timeout, not at pool shutdown.

---

## BUG-S-002 — Git history not secret-scanned

- **Issue Key:** BUG-S-002 | **Type:** Risk (assurance gap) | **Priority:** P3 | **Severity:** LOW | **Status:** Closed — Mitigated (2026-06-15) | **Resolution:** prior audit scanned 200 commits + tree, 0 secret hits; ~163 newer commits residual.
- **Components:** repo / git history | **Labels:** security, secrets, assurance
- **Affects Version:** e3578a1 | **Fix Version:** TBD | **Environment:** repo history (363 commits)
- **CWE:** CWE-540 | **CVSS:** CVSS:3.1/AV:N/AC:H/PR:N/UI:N/S:U/C:L/I:N/A:N (3.1) | **Exploitable-by:** anyone with repo read access IF a secret was ever committed (unverified)

**Summary:** No secret-scanning tool was available, so 363 commits of history were not verified clean. The working tree is clean (only env-var reads).

**Description / Evidence:** CMD-011 (no gitleaks/trufflehog), CMD-018 (working-tree grep clean), CMD-020 (363 commits).

**Steps to Reproduce:** `which gitleaks trufflehog` -> absent.

**Expected:** history verified free of secrets. **Actual:** unverified.

**Impact:** a historically-committed credential would remain retrievable; could not be ruled out.

**Suggested Fix:** run gitleaks/trufflehog over full history; add a secret-scan pre-commit + CI hook.

**Acceptance Criteria:**
- [ ] gitleaks (or equivalent) scans full history with 0 findings (or remediates/rotates any hit).
- [ ] Secret-scan hook added to pre-commit + CI.

---

## False Positives / Accepted Non-Issues

| ID | Tool output | Why rejected / downgraded |
|----|-------------|---------------------------|
| FP-1 (jinja2 autoescape) | bandit B701 + semgrep `direct-use-of-jinja2` @ run_infer.py:85 (CMD-006/CMD-017b) | Template renders an LLM **prompt**, not HTML/web output. XSS autoescape does not apply; injection of issue text into the prompt is inherent to the task. Downgraded to LOW/SHIP (S-001), not dropped. |
| FP-2 (subprocess B404/B603/B607) | bandit @ version.py:1/9 (CMD-006) | `subprocess.run(["git","submodule","status", path])` — fixed argv, no shell, no user-controlled executable. Standard git invocation. Not filed. |
| FP-3 (HF download no revision pin, B615) | bandit @ download_dataset.py:89, dataset.py:87/119 | Loading the public benchmark dataset by name is the intended behavior; revision pinning would be a nice-to-have but is not a harness defect (dataset identity is part of the run config). Noted, not filed as a bug. |
| FP-4 (temp dir B108) | bandit @ buildx_utils.py:74/76 | `/tmp/buildkit-reset.lock` paths are operator-controlled build-runner lock files, env-overridable (`BUILDKIT_RESET_LOCK`), not security-sensitive temp files. Not filed. |
| FP-5 (vulture `__context`) | vulture @ evaluation.py:77 (CMD-007) | `__context` is the required pydantic `model_post_init` signature parameter; intentionally unused. Not a defect. |

## Triage Summary Matrix

| Disposition | IDs | Count |
|-------------|-----|-------|
| BLOCK | T-001, D-001 | 2 |
| HOLD | R-001, R-002, D-002, T-002, R-003, S-002 | 6 |
| SHIP | S-001, Q-001, H-001, R-004, O-001, Q-002 | 6 |
| **Total** | | **14** |

Release note: BUG-T-001 (CI scoring-test gate) and BUG-T-002 (hypothesis) were **RESOLVED 2026-06-15**; BUG-D-001 (grader `rev=main`) is **accepted-risk / Won't Fix** (uv.lock pins the commit for `--frozen` installs; revisit before a published campaign). **No release-blockers and no open items remain as of 2026-06-15.** T-001/T-002/R-002 fixed; D-001/D-002 accepted-risk; R-001/R-003 accepted; S-002 mitigated. (D-002 CVE list is time-sensitive — re-scan per campaign.)
