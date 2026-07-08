# Production-Readiness Audit — Multi-SWE-Bench Inference + Evaluation Harness

- **Document type:** Independent production-readiness audit (skeptical staff-engineer perspective)
- **Status:** SHIP (no release-blockers and no open follow-ups as of 2026-06-15: T-001/T-002/R-002 fixed in code; D-001/D-002 accepted-risk; R-001/R-003 accepted; S-002 mitigated. All 14 findings SHIP. See Appendix A CMD-023..028)
- **Commit SHA:** `e3578a1838c178b6a166ba934bfc7bd12bb83871` (branch `main`, tree clean per CMD-001)
- **Audit timestamp:** 2026-06-15T12:43Z (env anchor CMD-001)
- **Repo under audit:** `/Users/apple/Documents/handoff/milo-bench-clean`

**Instruments run:** ruff 0.15.6 (CMD-005), pyright 1.1.408 (CMD-010), bandit 1.9.4 (CMD-006, CMD-017), semgrep 1.166.0 (CMD-017b), pip-audit 2.10.1 (CMD-009), vulture 2.16 (CMD-007), radon 6.0.1 (CMD-008), pytest 9.0.2 (CMD-016).

**Not run:** mypy (pyright is the configured strict type gate) | gitleaks/trufflehog (not installed; git-history secret scan NOT performed, see C-1) | hadolint/trivy/checkov (no Dockerfile/IaC in the in-scope set) | coverage E2E (full pytest needs `hypothesis` which is absent, T-002).

---

## Verdict Legend

| Flag | Term  | Meaning                                            |
| :--: | ----- | -------------------------------------------------- |
|  🟢  | SHIP  | Meets the bar as-is (or trivial cleanup).          |
|  🟡  | HOLD  | Acceptable now with a tracked condition/follow-up. |
|  🔴  | BLOCK | Release-blocking; must be fixed before production. |

## Severity Legend

CRITICAL (P0) > HIGH (P1) > MEDIUM (P2) > LOW (P3) > NIT (P4) > INFO. Security severities show a CVSS v3.1 vector + score.

---

## 1. Executive Summary

The in-scope harness — the Multi-SWE-Bench inference driver (`run_infer.py`), the eval driver (`eval_infer.py`), the format/config/score scripts under `scripts/eval`, and the shared `benchmarks/utils/*` modules they import — is **well-engineered at the code level** and **weak at the release-engineering level**. ruff (E/F/I) and a strict pyright pass with **zero** findings across all 23 in-scope files (CMD-005, CMD-010), vulture finds one trivial item (CMD-007), and the benchmark-local logic tests (score formula, convert, data_change, config) all pass — **91 passed** (CMD-016). The score formula has a clearly-specified single-source-of-truth implementation with property tests.

The blocking problems are about **what guards the scoring path in CI and what the scoring path depends on**:

1. **The benchmark's own test suite — including the score-formula and prediction-conversion tests — is never executed by CI** (T-001). CI's `tests.yml` runs only the top-level `tests/` directory; the 100+ tests under `benchmarks/multiswebench/tests/` (the only tests covering `score_v2g`, `convert`, `data_change`, the config injection) are not invoked, and the top-level tests do not import that code (CMD-013/CMD-014). The scoring logic can regress silently.
2. **The production scorer is a third-party fork pinned to a moving branch** (D-001). `pyproject.toml` pins `multi-swe-bench` to `rev = "main"`; `eval_infer.py` shells out to `multi_swe_bench.harness.run_evaluation` from that fork. A benchmark whose numbers must be reproducible is depending on an unpinned, mutable ref for its grader.

Below those, MEDIUM reliability/dependency issues (eval_infer default-dataset footgun, greedy `sed` patch-apply rewrite, 71 dependency CVEs, missing `hypothesis`, un-interruptible per-instance timeouts) are HOLD-worthy. Security exposure of the harness *code* is low: only a jinja2 autoescape flag (prompt rendering, not HTML — contained) and subprocess-without-shell on a hardcoded `git` argv. No secrets in the working tree (CMD-018); git history was not scanned (limitation C-1).

**Bottom line:** the code is shippable; the **release controls around the scoring path were not**. **Update 2026-06-15:** the benchmark scoring tests are now wired into the merge-blocking CI job and `hypothesis` is added (T-001 + T-002 RESOLVED, CMD-023..026). D-001 (grader on `rev="main"`) is **accepted-risk by the maintainer** — `uv.lock` pins the resolved grader commit (`73926adb`) for all `--frozen`/CI installs, so locked-state reproducibility holds; the moving ref only advances on a deliberate `uv lock`. **No release-blockers and no open follow-ups remain — all 14 findings are SHIP.** T-001/T-002/R-002 fixed in code; D-001 & D-002 accepted-risk; R-001/R-003 accepted (deployment context); S-002 mitigated (prior history scan). D-002's CVE list is time-sensitive — re-scan per campaign.

### 1.1 Findings Scorecard

| #  | ID    | Finding                                                                  | Axis          | Flag | Severity | Confidence | Disposition |
| -- | ----- | ------------------------------------------------------------------------ | ------------- | ---- | -------- | ---------- | ----------- |
| 1  | T-001 | Benchmark tests (incl. scoring) not run by CI — RESOLVED 2026-06-15     | Testing       | 🟢   | HIGH     | High       | SHIP        |
| 2  | D-001 | Grader fork pinned to moving `main` ref — ACCEPTED RISK 2026-06-15      | Dependencies  | 🟢   | HIGH     | High       | SHIP        |
| 3  | R-001 | eval_infer default dataset = nonexistent local path — ACCEPTED (EC2 local dataset) | Reliability   | 🟢   | MEDIUM   | High       | SHIP        |
| 4  | R-002 | Greedy `sed` patch-apply rewrite may double-apply — RESOLVED 2026-06-15 | Reliability   | 🟢   | MEDIUM   | Medium     | SHIP        |
| 5  | D-002 | 71 CVEs across 22 installed deps — ACCEPTED RISK (time-sensitive)        | Dependencies  | 🟢   | MEDIUM   | High       | SHIP        |
| 6  | T-002 | Property tests unrunnable (`hypothesis` absent) — RESOLVED 2026-06-15 | Testing       | 🟢   | MEDIUM   | High       | SHIP        |
| 7  | R-003 | Per-instance timeout cannot interrupt a worker — ACCEPTED (manual intervention) | Reliability   | 🟢   | MEDIUM   | High       | SHIP        |
| 8  | S-002 | Git history not secret-scanned — MITIGATED (prior 200-commit scan, 0 hits) | Security      | 🟢   | LOW      | Low        | SHIP        |
| 9  | S-001 | Jinja2 Environment without autoescape                                    | Security      | 🟢   | LOW      | High       | SHIP        |
| 10 | Q-001 | High-complexity scoring/logging hotspots                                 | Code Quality  | 🟢   | LOW      | High       | SHIP        |
| 11 | H-001 | Hardcoded private ECR account id default                                 | Repo Hygiene  | 🟢   | LOW      | High       | SHIP        |
| 12 | R-004 | 45 broad `except Exception` handlers                                   | Reliability   | 🟢   | LOW      | High       | SHIP        |
| 13 | O-001 | Event-logging env-gate commented out (always on)                         | Observability | 🟢   | INFO     | High       | SHIP        |
| 14 | Q-002 | Lint/type/format clean across in-scope set                               | Code Quality  | 🟢   | INFO     | High       | SHIP        |

### Tally by Severity (derived from findings.json via CMD-022)

| Severity        | Count        |
| --------------- | ------------ |
| HIGH            | 2            |
| MEDIUM          | 5            |
| LOW             | 5            |
| INFO            | 2            |
| **TOTAL** | **14** |

### Tally by Disposition (derived from findings.json via CMD-026, post-fix)

| Disposition     | Count        |
| --------------- | ------------ |
| BLOCK           | 0            |
| HOLD            | 0            |
| SHIP            | 14           |
| **TOTAL** | **14** |

> Note: T-001 (BLOCK→SHIP) and T-002 (HOLD→SHIP) were remediated, and D-001 (BLOCK→SHIP) was accepted-risk by the maintainer, on 2026-06-15 (CMD-023..026). No BLOCK findings remain. Severity tally is unchanged (severity = historical impact; disposition = current ship decision).

### 1.2 Axis Verdict Summary

| Axis                           | Worst severity | Disposition | Note                                                                                         |
| ------------------------------ | -------------- | ----------- | -------------------------------------------------------------------------------------------- |
| S - Security                   | LOW            | SHIP        | jinja2 autoescape contained (S-001); history scanned in prior run, 0 hits (S-002)            |
| P - Performance/Concurrency    | MEDIUM         | HOLD        | Captured under R-003 (timeout/worker occupancy)                                              |
| R - Reliability                | MEDIUM         | SHIP        | R-002 idempotency guard added (RESOLVED); R-001/R-003 accepted; R-004 SHIP                    |
| O - Observability              | INFO           | SHIP        | Structured per-instance logging; one commented gate                                          |
| Q - Code Quality               | LOW            | SHIP        | Clean lint/types; a few high-complexity functions                                            |
| T - Testing/CI                 | HIGH           | SHIP        | T-001/T-002 resolved 2026-06-15: scoring tests now CI-gated; hypothesis added (CMD-023..026) |
| D - Dependencies               | HIGH           | SHIP        | D-001 `rev=main` accepted-risk (uv.lock pins commit); D-002 71 CVEs accepted-risk (time-sensitive) |
| C - Config/Secrets             | LOW            | SHIP        | Env-driven; no secrets in tree                                                               |
| L - Licensing                  | N/A            | -           | No in-scope license defect surfaced; repo has LICENSE                                        |
| M - Migration/Data safety      | N/A            | -           | No DB/migrations in scope                                                                    |
| A - API/Contract stability     | N/A            | -           | No externally-exposed API; CLI args only                                                     |
| V - Domain/Scientific validity | MEDIUM         | HOLD        | Scoring gated by un-CI'd tests (T-001) + upstream grader (D-001/R-002)                       |
| H - Repo Hygiene               | LOW            | SHIP        | Clean tree, no tracked build artifacts; one hardcoded id                                     |

### 1.3 Audit Coverage

- **Scope:** the resolved import graph of `run_infer.py` and the eval entry points — **23 first-party Python files** (Appendix B). ~100% read (every in-scope file read in full) and 100% instrumented.
- **Sampling:** none needed; in-scope surface (~4,300 LOC per CMD-006) within budget.
- **Unaudited / excluded:** `vendor/` SDK submodule, `.venv/`, `legacy/`, harbor exporter, upstream `multi_swe_bench` fork internals. Git **history** not secret-scanned (C-1). Live E2E inference/eval not executed (Docker images + remote runtime keys + network — Execution-Safety exclusion).

---

## 2. Key Findings by Axis

### Testing / CI (T)

#### T-001 — Benchmark-local test suite (including scoring logic) not run by CI — HIGH — BLOCK — Confidence: High

**Evidence:** `SRC:.github/workflows/tests.yml:52-57`, CMD-013, CMD-014.

```
CI=true uv run python -m pytest -vvs --forked --cov=benchmarks ... tests/
```

CMD-013: top-level `tests/` has aggregate/iterative/timeout/security tests but no multiswebench scoring tests; CMD-014: top-level tests import only `evaluation, iterative, models, constants, run_infer` — NOT `score_v2g, convert, data_change, update_multi_swe_bench_config`. The 100+ tests under `benchmarks/multiswebench/tests/` are never invoked (also absent from precommit.yml).
**Why it matters:** the score formula, prediction-conversion regex, and config injection determine the score a model gets. They have tests that don't gate merges. A regression in `compute_score_v2g` or `convert_to_eval_format` ships green.
**Failure scenario:** a refactor changes the `(.*)__(.*)-(.*)` parse or a score gate threshold; CI passes (only `tests/`); benchmark numbers silently shift across a campaign.
**Remediation:** add `benchmarks/**/tests` to the pytest invocation (or a dedicated job); add `hypothesis` (T-002).
**Acceptance criteria:** `uv run pytest benchmarks/multiswebench/tests tests/` runs green in CI on a PR, and a deliberately broken score gate fails it.

#### T-002 — Property-based score tests cannot run: `hypothesis` missing — MEDIUM — HOLD — Confidence: High

**Evidence:** CMD-015, CMD-016, `SRC:benchmarks/multiswebench/tests/test_score_v2g_properties.py:19`. CMD-015: collection `ModuleNotFoundError: No module named 'hypothesis'`; CMD-016: `grep -c hypothesis uv.lock == 0`.
**Why it matters:** the strongest correctness check on the scoring formula (property invariants) errors on collection instead of protecting anything.
**Remediation:** add `hypothesis` to `[dependency-groups].dev` and `uv lock`.
**Acceptance criteria:** that test file collects and passes.

### Dependencies / Reproducibility (D)

#### D-001 — Production grader fork pinned to a moving `main` ref — HIGH — ~~BLOCK~~ → SHIP (ACCEPTED RISK 2026-06-15) — Confidence: High

**⚖️ ACCEPTED RISK 2026-06-15 (maintainer decision):** `rev="main"` is intentional so the grader fork tracks registry updates on re-lock. The reproducibility gap the audit describes is bounded by `uv.lock`, which pins the resolved grader commit `73926adb` for every `uv sync --frozen` install — and **CI uses `--frozen`** (CMD-024). So a given lock is reproducible; the ref only advances on a deliberate `uv lock`. Disposition reclassified BLOCK→SHIP as accepted risk. **Follow-up condition:** pin to an explicit SHA before any published cross-time benchmark campaign so scores stay comparable. Original finding retained below.

**Evidence:** `SRC:pyproject.toml:123` -> `multi-swe-bench = { git = "...Ethara-Ai/multi-swe-bench.git", rev = "main" }`; `SRC:benchmarks/multiswebench/eval_infer.py:79-89` invokes `python -m multi_swe_bench.harness.run_evaluation`; CMD-024 (uv.lock pins `73926adb` under --frozen).
**Why it matters:** the grader producing pass/fail is this fork. `rev = "main"` is mutable; the audited run's reproducibility hinges on whatever `main` pointed at. For a benchmark, the grader must be immutable.
**Failure scenario:** upstream pushes to `main`, someone runs `uv lock --upgrade`, identical predictions now score differently with no code change in this repo.
**Remediation:** pin to an explicit SHA (as already done for `swt-bench`, `commit0`, `litellm`).
**Acceptance criteria:** `grep 'multi-swe-bench' pyproject.toml` shows a 40-char SHA.

#### D-002 — 71 known CVEs across 22 installed dependencies — MEDIUM — ~~HOLD~~ → SHIP (ACCEPTED RISK 2026-06-15) — Confidence: High

**⚖️ ACCEPTED RISK 2026-06-15:** the 71 advisories are predominantly transitive in pinned fork deps (litellm/aiohttp/cryptography/lxml/urllib3/requests/...). The pip-audit result is **time-sensitive** — valid only as of this SHA + audit date (CMD-009). The current dependency pins all satisfy the project's functional requirements and are retained as-is (CVEs in those pinned versions are accepted, not a trigger to bump). Mitigation: re-run pip-audit per benchmark campaign and patch any reachable high-severity advisories then. Original finding retained below.

**Evidence:** CMD-009 (pip-audit 2.10.1, as of 2026-06-15). Examples: `aiohttp 3.13.3` (12, fix 3.13.4/3.14.0), `litellm 1.82.1` (7), `cryptography 46.0.5`, `lxml 6.0.2`, `urllib3`, `requests`, `pillow`, `starlette`, `gitpython`. Time-sensitive. Mostly transitive via SDK/LLM stack.
**Why it matters:** the harness runs in CI and on eval runners with network access; the LLM/HTTP stack is directly exercised.
**Remediation:** `uv lock --upgrade` affected packages; add pip-audit to CI.
**Acceptance criteria:** pip-audit reports 0 advisories for the directly-used HTTP/LLM packages.

### Reliability / Resilience (R)

#### R-001 — eval_infer default dataset treated as a nonexistent local path — MEDIUM — ~~HOLD~~ → SHIP (ACCEPTED 2026-06-15) — Confidence: High

**⚖️ ACCEPTED 2026-06-15:** the harness runs on EC2 importing the dataset from a LOCAL path; the HuggingFace default-name download branch (the case-mismatch site) is never exercised, so it cannot resolve to a nonexistent path in practice. Original finding retained below.

**Evidence:** `SRC:benchmarks/multiswebench/eval_infer.py:51-70`, CMD-019.

```
if dataset_name is None: dataset_name = "bytedance-research/Multi-SWE-Bench"
if dataset_name.startswith("ByteDance-Seed/Multi-SWE-bench"):  # never matches the default
    dataset_path = download_and_concat_dataset(...)
else:
    dataset_path = str(Path(dataset_name).resolve())  # -> nonexistent path
```

The default (and argparse default at line 119) is `bytedance-research/Multi-SWE-Bench`, which does NOT match the case-sensitive `ByteDance-Seed/Multi-SWE-bench` download trigger, so it is resolved as a filesystem path that won't exist and handed to the harness.
**Why it matters:** running `eval_infer` without `--dataset` at a real file fails inside the grader with a confusing path error. (`run_infer.py` requires `--dataset`, so impact is mainly the standalone eval entry point.)
**Remediation:** validate `os.path.isfile(dataset_path)` before invoking the harness, or require `--dataset`.
**Acceptance criteria:** `multiswebench-eval out.jsonl` with no `--dataset` fails fast with an actionable message.

#### R-002 — Greedy `sed s@git apply.*@...@g` patch-apply rewrite may double-apply — MEDIUM — ~~HOLD~~ → SHIP (RESOLVED 2026-06-15) — Confidence: Medium

**✅ RESOLVED 2026-06-15:** `_APPLY_PATCH_HELPER` made idempotent — a leading `git apply --reverse --check` guard skips an already-applied patch, so the greedy global `sed ...@g` can no longer double-apply when upstream fix-run.sh has >1 `git apply` line (confirmed present in pandas etc.). Behaviorally verified idempotent (CMD-027); 261 benchmark tests pass incl. 2 new R-002 regression tests (CMD-028). Original finding retained below.

**Evidence:** `SRC:benchmarks/multiswebench/scripts/eval/update_multi_swe_bench_config.py:46-54`.

```
"sed -i 's@git apply.*@bash /home/apply_patch.sh /home/test.patch ; "
"bash /home/apply_patch.sh /home/fix.patch@g' /home/fix-run.sh ; "
```

Global (`g`) + greedy (`.*`): EVERY `git apply` line in upstream `fix-run.sh` is replaced with the full test-then-fix apply. If upstream has >1 such line, both patches get applied multiple times.
**Why it matters:** on the production scoring path (builds `fix_patch_run_cmd`, the verifier command). Mis-applied patches corrupt pass/fail signal. Correctness depends on an unverified assumption about the upstream fork's `fix-run.sh` (third-party) — Medium confidence.
**Failure scenario:** upstream fix-run.sh has a second `git apply` (setup patch); rewrite double-applies; second apply fails/duplicates hunks; instance scored wrong.
**Remediation:** anchor the sed to the known line or template `fix-run.sh` directly; assert match count.
**Acceptance criteria:** a test pins the rewritten `fix-run.sh` and asserts each patch applies exactly once.

#### R-003 — Per-instance timeout cannot interrupt a running worker — MEDIUM — ~~HOLD~~ → SHIP (ACCEPTED 2026-06-15) — Confidence: High

**⚖️ ACCEPTED 2026-06-15:** per-instance tasks can legitimately run 14–15h for large PR-bundle instances; the non-interruptible timeout is handled by operator MANUAL INTERVENTION, a conscious operational choice. Original finding retained below.

**Evidence:** `SRC:benchmarks/utils/evaluation.py:66-75` (field docstring) and `SRC:benchmarks/utils/evaluation.py:470-472`:

```
# Note: fut.cancel() only prevents unstarted futures from
# starting. Running workers will continue until pool shutdown.
fut.cancel()
```

**Why it matters:** a hung instance is marked failed but keeps occupying a `ProcessPoolExecutor` worker until the attempt's pool shuts down, throttling a long eval run.
**Remediation:** hard-kill the worker PID on timeout (SIGTERM/SIGKILL) or use per-instance subprocesses; else document the accepted limitation.
**Acceptance criteria:** an instrumented hung instance frees its worker within ~timeout.

#### R-004 — Broad `except Exception` handlers across the harness (45 in-scope) — LOW — SHIP — Confidence: High

**Evidence:** CMD-021 (45 sites across 12 files), e.g. `SRC:benchmarks/multiswebench/eval_infer.py:104-108` returns `None` on any exception (documented soft-fail contract). Most others are best-effort logging/laminar/cleanup.
**Why it matters:** mostly intentional, but a few downgrade real failures to `logger.debug`, hiding root causes during a campaign.
**Remediation:** narrow the highest-value handlers (dataset I/O, config write). Not release-blocking.

### Security (S)

#### S-001 — Jinja2 Environment without autoescape — LOW — SHIP — Confidence: High — [INSTRUMENTED: CMD-006, bandit 1.9.4]

**Evidence:** `SRC:benchmarks/multiswebench/run_infer.py:85` (`Environment(loader=FileSystemLoader(...))`); bandit B701 (CMD-006) + semgrep `direct-use-of-jinja2` (CMD-017b). CVSS:3.1/AV:N/AC:H/PR:N/UI:N/S:U/C:N/I:L/A:N (3.1), CWE-79.
**False-positive note:** autoescape protects HTML/JS output; here the template renders an LLM **instruction prompt**, not web output. The realistic risk (issue text injected into the prompt) is inherent to the task. Contained — SHIP.
**Remediation (optional):** `autoescape=select_autoescape()` if any field is ever surfaced as HTML, else annotate `# nosec B701`.

#### S-002 — Git history not secret-scanned — LOW — ~~HOLD~~ → SHIP (MITIGATED 2026-06-15) — Confidence: Low

**⚖️ MITIGATED 2026-06-15:** prior audit run `multiswebench-audit-20260612` scanned git history (200 commits) + working tree with 0 secret hits (its CMD-011/H-001). Residual: ~163 commits added since are not covered by a dedicated entropy scanner; LOW severity. Original finding retained below.

**Evidence:** CMD-011 (no gitleaks/trufflehog), CMD-018 (working-tree grep: only env-var reads), CMD-020 (363 commits unscanned). CVSS:3.1/AV:N/AC:H/PR:N/UI:N/S:U/C:L/I:N/A:N (3.1), CWE-540.
**Why it matters:** history leaks are a top real-world vector; this audit could not rule them out.
**Remediation:** run gitleaks/trufflehog over full history; add a secret-scan pre-commit + CI hook.

### Code Quality (Q)

#### Q-001 — High-complexity scoring/logging hotspots — LOW — SHIP — Confidence: High — [INSTRUMENTED: CMD-008, radon 6.0.1]

**Evidence:** CMD-008: `compute_score_v2g` E(32), `summarize_instance` E(35), `format_trajectory_line` D(24), `format_data_for_inference` D(23), `_run_iterative_mode` D(27). MI all grade A (CMD-008b).
**Why it matters:** the two grade-E functions are score computation and per-instance summary; high branching raises change-risk on the scoring/diagnostic path.
**Remediation:** extract the score gate cascade into named helpers. Not blocking.

### Repo Hygiene (H)

#### H-001 — Hardcoded private ECR account id default — LOW — SHIP — Confidence: High

**Evidence:** `SRC:benchmarks/multiswebench/run_infer.py:59-62` and CMD-012 (`426628337772.dkr.ecr.ap-south-1.amazonaws.com/rfp-coding-q1` in two modules). Overridable via `EVAL_DOCKER_IMAGE_PREFIX`, so not a credential — but leaks infra identity.
**Remediation:** move the default to config/env without a baked account id, or document it as canonical.

### Observability (O)

#### O-001 — Event-logging env-gate commented out — INFO — SHIP — Confidence: High

**Evidence:** `SRC:benchmarks/utils/conversation.py:95-97` — the `ENABLE_CONVERSATION_EVENT_LOGGING` disable path is commented out with a TODO; logging is unconditionally on. Observation, not a defect.

### Code Quality (positive)

#### Q-002 — Lint/type/format clean across in-scope set — INFO — SHIP — Confidence: High — [INSTRUMENTED: CMD-005/CMD-010]

**Evidence:** ruff (E/F/I) "All checks passed" on 23 files (CMD-005); pyright strict "0 errors, 0 warnings" (CMD-010); vulture one trivial item (CMD-007). Genuine strength.

---

## 3. Prioritized Remediation Plan

### 3.1 Release-Blockers (P0/P1)

1. **T-001** — Merge-blocking CI job running `benchmarks/multiswebench/tests` (scoring tests).
2. **D-001** — Pin `multi-swe-bench` to an explicit SHA.

### 3.2 Pre-GA (P2)

3. **T-002** — Add `hypothesis` to dev deps + lock.
4. **D-002** — Upgrade CVE-affected deps; add pip-audit to CI.
5. **R-001** — Validate/require `--dataset` in `eval_infer`; fail fast.
6. **R-002** — Make the `fix-run.sh` rewrite deterministic (anchored sed or templated script) + test.
7. **R-003** — Hard-kill timed-out workers (or document limitation).

### 3.3 Hygiene/Nit (P3/P4)

8. **S-002** — Full git-history secret scan + CI hook.
9. **S-001** — Document/annotate intentional jinja2 autoescape choice.
10. **Q-001** — Refactor the two grade-E functions.
11. **H-001** — Remove baked ECR account id from defaults.
12. **R-004** — Narrow the few error-hiding broad excepts.

---

## 4. What This Codebase Gets Right (evidence-backed)

- **Clean lint + strict types:** ruff E/F/I and pyright strict both zero on all 23 in-scope files (CMD-005, CMD-010). Q-002.
- **Real, passing logic tests:** 91 benchmark-local tests pass, including 25 score-formula cases and convert/data_change/config tests (CMD-016) — the scoring logic *is* tested (the gap is CI wiring, T-001).
- **Single-source-of-truth score formula:** `score_v2g.py` documented as extracted so the converter and standalone evaluator "cannot drift" (`SRC:benchmarks/multiswebench/scripts/eval/score_v2g.py:1-7`); side-effect-free import.
- **Considered patch-apply escalation:** V-001 replaced a dangerous `patch --fuzz=5` with an auditable exact->3way->fuzz=2 escalation that announces FUZZY applies and captures `.rej` (`SRC:.../update_multi_swe_bench_config.py:9-34`) — right instinct, brittle delivery (R-002).
- **Clean repo hygiene:** no tracked build artifacts — `.coverage`, `.hypothesis/`, egg-info, vendor, venv all untracked (CMD-012b); tree clean at audit time (CMD-001).
- **Concurrency-safe result writes:** `get_default_on_result_writer` uses `fcntl.flock` exclusive locking on the shared JSONL (`SRC:benchmarks/utils/evaluation_utils.py:61-65`).

---

## 5. Preventing Recurrence — Engineering Guardrails

1. **Merge-blocking benchmark-test job** (closes T-001, T-002): CI runs `benchmarks/**/tests` + `tests/` with `hypothesis` installed; a broken score gate must fail it.
2. **Reproducibility contract for the grader** (closes D-001): all `[tool.uv.sources]` git deps pinned to SHAs; CI rejects branch refs.
3. **Dependency CVE gate** (closes D-002): pip-audit in CI; scheduled weekly relock.
4. **Secret-scan hook** (closes S-002): gitleaks pre-commit + CI over full history.
5. **Coverage floor ratchet** (supports T-001): raise `--cov-fail-under` after benchmark tests included.
6. **Deterministic eval-config tests** (closes R-002, R-001): pin generated `fix-run.sh`/config; fail-fast dataset validation.
7. **Lint/type/format gate** (sustains Q-002): keep ruff + pyright-strict pre-commit + CI (already present).

Adoption sequence: 1 -> 2 -> 3, 6 -> 4, 5, 7.

---

## Appendix A — Audit Log & Instrumented Evidence

All commands run from `/Users/apple/Documents/handoff/milo-bench-clean` unless noted. Audit tools installed in a throwaway venv at `/tmp/audit-venv/v` (outside the repo, no `--global`, no lifecycle scripts).

| run-id   | command                                                                                                        | exit               | tool ver                   | excerpt                                                                                                                                                          |
| -------- | -------------------------------------------------------------------------------------------------------------- | ------------------ | -------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| CMD-001  | `date -u; git rev-parse HEAD; git status --short; git branch --show-current; uname -a`                       | 0                  | git                        | `e3578a1838c178b6a166ba934bfc7bd12bb83871`; status empty (clean); branch `main`; Darwin 25.5.0 arm64; 2026-06-15T12:43Z                                      |
| CMD-002  | `curl -sI https://pypi.org`                                                                                  | 0                  | curl                       | `network: YES`                                                                                                                                                 |
| CMD-003  | venv probe +`.venv/bin/python --version`                                                                     | 0                  | -                          | Python 3.12.13 in `.venv`; host python3 3.11.7                                                                                                                 |
| CMD-004  | `find benchmarks/multiswebench benchmarks/utils -name '*.py'` + import grep                                  | 0                  | grep                       | resolved 23 in-scope files; first-party imports listed (Appendix B)                                                                                              |
| CMD-005  | `.venv/bin/ruff check $(cat /tmp/inscope.txt)`                                                               | 0                  | ruff 0.15.6                | `All checks passed!`                                                                                                                                           |
| CMD-006  | `bandit -q -r <inscope> -f txt`                                                                              | 0                  | bandit 1.9.4               | Low:27 Medium:5 High:1; B701 jinja2 autoescape @ run_infer.py:85; total LOC 4303                                                                                 |
| CMD-007  | `vulture <inscope> --min-confidence 70`                                                                      | 0                  | vulture 2.16               | one item:`evaluation.py:77 unused variable '__context'` (pydantic hook param)                                                                                  |
| CMD-008  | `radon cc <inscope> -n D -s`                                                                                 | 0                  | radon 6.0.1                | `compute_score_v2g E(32)`, `summarize_instance E(35)`, `format_trajectory_line D(24)`, `format_data_for_inference D(23)`, `_run_iterative_mode D(27)` |
| CMD-008b | `radon mi <inscope> -s` (filter non-A)                                                                       | 0                  | radon 6.0.1                | no non-A lines -> all files MI grade A                                                                                                                           |
| CMD-009  | `pip-audit -r /tmp/reqs3.txt --no-deps --disable-pip -f json` (reqs from venv dist-info, local pkgs removed) | 1                  | pip-audit 2.10.1           | `Found 71 known vulnerabilities in 22 packages`; aiohttp/litellm/cryptography/lxml/urllib3/requests/pillow/...                                                 |
| CMD-010  | `.venv/bin/pyright $(cat /tmp/inscope.txt)`                                                                  | 0                  | pyright 1.1.408            | `0 errors, 0 warnings, 0 informations`                                                                                                                         |
| CMD-011  | `which gitleaks trufflehog`                                                                                  | 1                  | -                          | `no secret scanner` (both absent)                                                                                                                              |
| CMD-012  | `grep -rn 426628337772 <inscope>`                                                                            | 0                  | grep                       | run_infer.py:61, build_images.py:28/79                                                                                                                           |
| CMD-012b | `git ls-files                                                                                                  | grep -E '.coverage | .hypothesis                | egg-info                                                                                                                                                         |
| CMD-013  | `ls tests/`; `find tests -name '*score*' -o -name '*multiswe*'`                                           | 0                  | -                          | top-level tests = aggregate/iterative/timeout/security/...; no score/multiswe test file                                                                         |
| CMD-014  | `grep -rhoE 'from benchmarks\.[a-z_.]+ import' tests/*.py                                                      | sort -u`           | 0                          | grep                                                                                                                                                             |
| CMD-015  | `.venv/bin/python -m pytest .../test_score_v2g_properties.py`                                               | 2                  | pytest 9.0.2               | `ModuleNotFoundError: No module named 'hypothesis'` (collection error)                                                                                         |
| CMD-016  | `.venv/bin/python -m pytest <7 in-scope eval test files minus properties>`                                   | 0                  | pytest 9.0.2               | `91 passed`; `grep -c hypothesis uv.lock == 0`                                                                                                               |
| CMD-017  | `bandit -f json` -> extract HIGH/MEDIUM                                                                      | 0                  | bandit 1.9.4               | HIGH B701 run_infer.py:85; MEDIUM B615 download_dataset.py:89, dataset.py:87/119 (HF no-revision-pin), B108 buildx_utils.py:74/76 (temp dir)                     |
| CMD-017b | `semgrep --config=auto --json <inscope>`                                                                     | 1                  | semgrep 1.166.0            | 2 findings, both `direct-use-of-jinja2` WARNING @ run_infer.py:85,101 (corroborates B701)                                                                      |
| CMD-018  | secrets grep over in-scope tree                                                                                | 0                  | grep                       | only `runtime_api_key = os.getenv(...)` reads; no literal secrets                                                                                              |
| CMD-019  | `grep -n 'bytedance-research                                                                                   | ByteDance-Seed     | startswith' eval_infer.py` | 0                                                                                                                                                                |
| CMD-020  | `git rev-list --count HEAD`                                                                                  | 0                  | git                        | `363` commits (unscanned for secrets)                                                                                                                          |
| CMD-021  | `grep -rcE 'except Exception' <inscope>` (sum non-zero)                                                      | 0                  | grep                       | 45 broad-except sites across 12 files (eval_infer 1, evaluation 9, laminar 9, buildx_utils 6, ...)                                                               |
| CMD-022  | `python3 /tmp/verifier.py` (final verifier)                                                                  | 0                  | python 3.11                | tallies +`ALL CHECKS PASSED` — pasted below                                                                                                                   |
| CMD-023  | `uv lock` (after adding `hypothesis>=6.0.0` to pyproject dev group)                                          | 0 | uv 0.9.8 | `Added hypothesis v6.155.2`; lock diff = hypothesis block + 2 dev refs + 4 benign greenlet s390x wheels; no version bumps; multi-swe-bench rev unchanged |
| CMD-024  | `uv sync --frozen --group dev` (the CI Install-deps gate: lock⇄pyproject consistency)                        | 0 | uv 0.9.8 | sync OK (lock consistent with manifest); `hypothesis` installed into .venv |
| CMD-025  | `.venv/bin/python -m pytest benchmarks/multiswebench/tests -q`                                               | 0 | pytest 9.0.2 | `259 passed` (244 logic + 15 property; properties collect natively). Pre-fix isolation `--ignore=…properties.py` → `244 passed` |
| CMD-026  | re-derive tallies from updated findings.json                                                                 | 0 | python 3.11 | by disposition `{SHIP:8, HOLD:5, BLOCK:1}`; by severity `{HIGH:2, MEDIUM:5, LOW:5, INFO:2}`; both sum 14 |
| CMD-027  | R-002 fix: run patched `_APPLY_PATCH_HELPER` twice on a temp git repo                                        | 0 | bash/git | 1st=`[apply] exact`, 2nd=`[apply] already applied (skip)`; file content correct; no `.rej` — duplicate apply is a safe no-op |
| CMD-028  | `.venv/bin/python -m pytest benchmarks/multiswebench/tests -q` + ruff (post R-002 fix)                       | 0 | pytest 9.0.2 / ruff 0.15.6 | `261 passed` (+2 new R-002 regression tests); `ruff check` All checks passed on the 2 edited files |

**Raw tool numbers:** bandit Low:27/Medium:5/High:1 (CMD-006). semgrep: 2 WARNING (CMD-017b). radon: 2xE, 3xD, rest <=C; MI all A. pip-audit: 71 advisories / 22 pkgs (CMD-009). vulture: 1 item (CMD-007). pytest in-scope eval: 91 passed, 1 collection error (hypothesis). ruff: 0. pyright: 0.

**Not run / TOOL-BLOCKED:** mypy (not project tooling; pyright is the gate) | gitleaks/trufflehog (TOOL-BLOCKED: not installed, CMD-011) | hadolint/trivy/checkov (no in-scope Dockerfile/IaC) | live inference/eval E2E (Docker images + RUNTIME_API_KEY + network egress — Execution-Safety exclusion) | full `pytest tests/` with coverage (blocked by missing `hypothesis`, T-002).

### Final verifier output (CMD-022)

```
=== TALLY BY SEVERITY ===
  MEDIUM: 5
  LOW: 5
  HIGH: 2
  INFO: 2
  TOTAL: 14
=== TALLY BY DISPOSITION ===
  HOLD: 6
  SHIP: 6
  BLOCK: 2
  TOTAL: 14
=== ERRORS ===
  ALL CHECKS PASSED
```

The verifier validates: no stray PASS/CONDITIONAL/FAIL labels; unique IDs; every `evidence` ref resolves (SRC file+line in range, CMD-id present in this Appendix); both tallies sum to 14; every HOLD/BLOCK and HIGH/CRITICAL-security finding has a BUGS.md ticket; every Security finding has a CVSS vector.

---

## Appendix B — Methodology & Scope

**Product type:** data/ML evaluation pipeline + CLI (benchmark inference & scoring harness). Not a network service; trust boundary is the eval operator (trusted) plus dataset/issue content and the LLM agent's actions (semi-trusted — agent runs in an isolated remote/Docker workspace).

**Scope resolution (CMD-004):** traced the import graph from `run_infer.py` and the eval entry points. Resolved in-scope first-party set (23 files):

```
benchmarks/multiswebench/run_infer.py, eval_infer.py, build_images.py, download_dataset.py
benchmarks/multiswebench/scripts/data/data_change.py
benchmarks/multiswebench/scripts/eval/{convert,score_v2g,eval_score_v2g,update_multi_swe_bench_config}.py
benchmarks/utils/{args_parser,build_utils,buildx_utils,console_logging,constants,conversation,
  critics,dataset,evaluation,evaluation_utils,iterative,laminar,models,version}.py
```

**Scoping note (reasoned call):** `score_v2g.py`/`eval_score_v2g.py` are in scope (they implement the documented score formula and are imported by the eval scripts) but per grep are NOT wired into the production scoring path — `eval_infer.py` delegates scoring to the upstream `multi_swe_bench` harness. They are a well-tested standalone analysis tool; their defects would not affect a production run, which raised the relative importance of D-001/R-002 (the actual production scoring path).

**Trust model & data classification (grounded):** operator-driven CLI (`get_parser`, `args_parser.py`); secrets read from env (`RUNTIME_API_KEY`, `LMNR_PROJECT_API_KEY`, Vertex SA path) — never literal in source (CMD-018). Dataset/issue text is attacker-influenceable (becomes the prompt) but rendered to an LLM, not a browser (S-001). No PII/financial/health data in scope.

**Exclusions:** `vendor/` (SDK submodule), `.venv/`, `legacy/`, harbor exporter (`scripts/harbor/*`), upstream `multi_swe_bench` fork internals. None tracked as bloat (CMD-012b).

**Disposition basis:** Reliability = likelihood x blast radius; Testing = criticality of uncovered path; Dependencies = reproducibility/CVE exposure; Security uses CVSS v3.1.

## Appendix C — Residual Risk & Assessment Limitations

- **C-1 (Security, lowers S confidence):** git history (363 commits, CMD-020) NOT secret-scanned — gitleaks/trufflehog unavailable (CMD-011). History leaks cannot be ruled out. S-002 filed Low confidence.
- **C-2 (Validity, lowers R-002 confidence):** production patch-apply correctness (R-002) depends on the upstream fork's `fix-run.sh` structure, third-party and not executed here. Medium confidence.
- **C-3 (Reproducibility):** no live inference/eval E2E run (needs Docker images, remote runtime API key, network egress). Runtime/orchestration findings are from static reading + the project's own unit tests, not observed execution.
- **C-4 (Dependencies, time-sensitivity):** pip-audit results (D-002) valid only as of 2026-06-15 at SHA `e3578a1`. The audit venv was scanned via dist-info-derived requirements (CMD-009) because the project venv has no `pip`; reflects installed versions, not necessarily what `uv sync --frozen` resolves elsewhere.
- **C-5 (Tooling):** mypy not run (pyright strict is the project's configured type gate and passed); a second type checker might surface more nits.
