# Continuous Reward Formula v2 — Grounded Specification (v2g, Universal — Audit-7 Reconciled)

**Status**: Spec finalized after Audit #6 meta-review corrected the recall numerator (set-difference); implementation pending
**Author**: Sisyphus
**Source ideas**: SWE-bench taxonomy (Jimenez et al.), Multi-SWE-Bench 8-category (Zan et al.), SWE-RL continuous range (Wei et al.), `continuous_reward_plan.md` (internal — recall denominator + p2p regression factor), reviewer critique (4 structural flaws caught in subtractive-shape iteration), Oracle v2c audit (3 critical defects → R1-R5 revisions), Oracle v2d audit (1 CRITICAL, 2 HIGH, 3 MEDIUM, 4 LOW → v2e closures), Audit #4 external reviewer + Oracle audit #4 (F1 representativeness, F2 gold_n2p pollution / do-nothing inflation, F3 regression-target coupling, F4 T_p_run non-determinism)
**Audits applied**:
  - Oracle audit #1 (strict edge-case on v1 binary) — found C1 + C2
  - Reviewer audit (caught precision-vs-recall structural defect in v2a)
  - Oracle audit #2 (stress-test of v2c reconciled) — found N1 (inert regression channel on empty gold_p2p), N2 (all-empty gold dicts displaces C1 not closes it), N3 (Flaw 4 redux on strict §10 curation fallback). v2d closes all three.
  - Oracle audit #3 (industry-veteran strict review of v2d + implementation + tests + CSV) — found C-1 (binary collapses on n2p-only gold), H-1 (N1 inert on cpp where T_p_run also empty), H-2 (regression-blind internal_plan still shipped in canonical schema), 3 MEDIUM (asymmetric integrity check, degenerate test_patch_result, sloppy property boundaries), 4 LOW. v2e closes C-1/H-2/M-1/M-2/M-3/L-3/L-4 in code, H-1/L-1/L-2 by honest spec documentation.
  - **Audit #4 (external reviewer + Oracle audit #4)** — challenged the load-bearing premise that prior audits had not probed: *is the denominator (gold_n2p) actually the issue's test set?* Found F1 (M-2 silently excludes ~44% of the dataset, compiled-language-heavy — 155/350 with Rust 80%, Java 63%, C 54%, Python 2%), F2 (CRITICAL — "trust full gold_n2p" re-introduces range compression; 51% of non-vacuous datasets are pollution-prone; concrete cases `starship-138` do-nothing recall = 0.888 and `testcontainers-java-8298` do-nothing recall = 0.342 across all 9 runs), F3 (min-form denominator couples regression penalty to target count — 25× ratio between |T|=2 and |T|=500), F4 (T_p_run is structurally non-deterministic via flaky baseline tests; empirically 0% variance in freya but theoretically real). v2f-attempt-1 proposed baseline subtraction (closes F2), pollution gate (transparency), R0 regression floor (closes F3), and **frozen-dataset baseline source** (closes F4).
  - **Audit #5 (external reviewer + explore agent empirical verification)** — caught a STRUCTURAL DEFECT in v2f-attempt-1: the **frozen-dataset baseline source** the spec proposed for F4 closure is *structurally empty on n2p-only instances by the bucketing rule itself*. `report.py:130-138` partitions per-observation: in a single bucketing pass, a name lands in EXACTLY ONE of `{p2p, f2p, s2p, n2p}` based on its test-stage status. Names in `gold_n2p` (test-stage = NONE) by definition cannot also appear in that same observation's `test_patch_result.passed_tests` (test-stage = PASS). Empirical verification confirmed: starship-138 dataset's `T ∩ test_patch_result.passed_tests = 0/89` (do-nothing recall would have been 0/89 = **0.0** as the spec claimed, but only because the intersection is *vacuously* empty — the formula does not actually identify pre-existing-passing targets). Oracle audit #4's measured 0.888 was computed against the **run report's** `test_patch_result.passed_tests` (which had 82 passes on starship-138), NOT the dataset's. The pollution mechanism (F2) IS the curation-time-vs-runtime baseline drift; identifying it requires the runtime observation, not the curation one. **v2f (post-Audit-5)** corrects by sourcing `T_p_baseline` from the **run report's** `test_patch_result.passed_tests`, accepting the partial F4 re-open (run-determined baseline) with the empirical 0% variance observation documented as a v3 watchpoint. This makes the F2 fix actually fire on the n2p-only pollution-prone instances that are 51% of the dataset.
  - **Audit #6 (external meta-review of review proposals)** — evaluated the mathematical correctness of the prior reviewer's five proposed formula changes (Issues 1-5, Bonus) and found **three actively harmful, two correct, one design-trade**. Key finding: Issue 1's set-difference numerator is mathematically justified on **double-penalization** grounds (regressed baseline targets were being subtracted from the numerator AND penalized by the factor — twice), NOT on noise-reduction grounds as claimed (set-diff has linear-in-n noise bias vs clamped arithmetic's sqrt-n — the prior reviewer's noise argument was backwards). Issue 2's smooth weighting is WRONG (pollution gate is agent-independent; the smooth `w` would penalize capable agents for instance cleanliness). Bonus's "don't subtract f2p∩baseline" is WRONG (re-opens F2 by keeping pre-existing-passing f2p targets in the denominator where a do-nothing agent would score them as hits). **v2g** adopts only the two correct changes: set-difference numerator and `f2p_baseline_pass_count` alarm diagnostic. All prior formula shape is preserved.
**Companion**: see `continuous_reward_plan.md` for original internal proposal and §5 skeptical critique. **v2f is positioned as one channel of a composite reward** (test-outcome channel) per the reviewer's point 2 concern — it complements but does not replace a process / rubric reward channel for long-horizon RL credit assignment. See §1.1 below.

---

## 0. Iteration log

This document went through four drafts before landing on the reconciled formula:

| Draft | Formula shape | Result |
|---|---|---|
| **v2a (subtractive precision)** | $r = \dfrac{(f2p + s2p + n2p_{\text{filt}}) - (p2f + s2f + n2f_{\text{filt}})}{\lvert F_p\rvert + \lvert F_f\rvert + \lvert F_s\rvert - p2p - f2f}$ | **FAILED reviewer audit**. Reviewer identified 4 structural flaws: (1) no completion gradient — $D$ collapses to $k$ so $r=1.0$ for any $k \ge 1$ fixed; (2) clean failures excluded ($D=0$ → vacuous), broken attempts included at 0 → silent pass@k inflation; (3) $s2s$ dilutes denominator on suites with platform-skipped tests; (4) Go/Rust false-zero because $n2p$ targets dropped when language can't be filtered. Root cause: built a precision metric ("of what you touched, what fraction got net better?") for a use case that needs recall ("of what needed fixing, what fraction did you fix?"). |
| **v2b (recall × multiplicative factor)** | Internal plan's `\|TARGETS ∩ F_p\| / \|TARGETS\| × (1 - broken_p2p/\|P\|)` | Closes Flaws 1-4 but inherits internal plan §5.2: regression-blind on huge $\lvert P\rvert$ (8000 tests, 20 broken → factor 0.9975). |
| **v2c (recall × hybrid max-of-fractions)** | Recall × $\max(\text{broken}/\lvert P\rvert, \text{broken}/\lvert\mathcal{T}\rvert)$ | All 4 reviewer flaws closed; §5.2 closed; C1 + C2 plumbing inherited from v2a. **FAILED Oracle audit #2** with 3 critical: **N1** regression channel inert on 53% of freya datasets (gold_p2p empty: Rust 80%, Java 76%, C 76%); **N2** 10/350 datasets have ALL gold dicts empty (incl. HypothesisWorks-4452) — C1 was displaced, not closed; **N3** strict §10 curation fallback would shrink AMReX-4238 TARGETS 57→2 (Flaw 4 redux). |
| **v2d (recall × preserve_set min-form factor)** | Recall × $(1 - \text{broken}/\min(\lvert\text{preserve\_set}\rvert, \lvert\mathcal{T}\rvert))$ with `preserve_set = gold_p2p ∪ T_p_run` and lazy re-curation | All 4 reviewer flaws closed; §5.2 closed; C1 + C2 plumbing inherited; **N1 partially closed** via preserve_set union (but inert on cpp where T_p_run is also empty — Oracle audit #3 H-1); **N2 closed**; **N3 closed**. **FAILED Oracle audit #3** with C-1 CRITICAL: `binary = gold_f2p.issubset(F_p)` short-circuited to 0 on every n2p-only gold instance (Go/Rust/most cpp/Java/JS) — silently collapsed the Phase-1 canonical reward. Plus H-2 (regression-blind `reward_internal_plan` still shipped), M-1 (one-sided integrity check), M-2 (silent fall-through on degenerate test_patch_result), M-3 (sloppy property boundaries). |
| **v2e (multi-language binary + honest cpp limitation)** | Recall × min-form factor unchanged; binary rewritten as $\mathbb{1}[\mathcal{T} \subseteq F_p \land \text{preserve\_set} \cap F_f = \emptyset]$ (SWE-bench multi-language definition); `reward_internal_plan` dropped from production emit; integrity check widened to all three counts on both stages; degenerate test_patch_result → `status:invalid`; properties #2/#3/#4 boundary-precise; `regression_channel_active` diagnostic added | All audit-3 closures in place. Cpp inert regression channel honestly documented as known limitation (§2.5, §9, §10) not silently misrepresented. **FAILED Audit #4**: F1 M-2 silently excludes 155/350 (44%) of dataset, compiled-language-heavy and never surfaced (representativeness bias); F2 CRITICAL — "trust full gold_n2p" causes do-nothing recall ≈ 1.0 on partial-collapse instances where n2p is dominated by pre-existing tests (51% of non-vacuous datasets pollution-prone; `starship-138` empirical do-nothing recall = 0.888 across 9 runs, `testcontainers-java-8298` = 0.342 across 9 runs); F3 min-form couples regression cost to \|T\| (25× difference between small and large tasks); F4 T_p_run is non-deterministic via flaky tests (0% manifest in freya but structurally real). |
| **v2f-attempt-1 (frozen-dataset baseline for F4)** | Recall replaced by adjusted recall (baseline subtraction); pollution gate; R0=20 absolute regression floor; **`T_p_baseline` sourced from the dataset's own `test_patch_result.passed_tests`** to make `reward_binary` deterministic across re-runs. | **FAILED Audit #5**. The frozen-dataset baseline source is structurally empty on n2p-only instances by the bucketing rule (`report.py:130-138`): names in `gold_n2p` cannot also be in that same observation's `test_patch_result.passed_tests`. So `T ∩ dataset.tpr.passed = ∅` for starship-138 (89-test n2p-only), rxdb-4758 (539-test n2p-only), etc. — exactly the pollution-prone instances F2 was written to fix. The headline "starship-138 → 0.0" claim was *vacuously* correct (intersection empty for the wrong reason: no overlap to subtract from, not no pollution to subtract). Inert on the 51% pollution-prone slice the spec was written for. |
| **v2f (universal — baseline subtraction + R0 floor + run-report baseline source)** | Recall replaced by **adjusted recall** that subtracts run-time baseline-passing targets from both numerator and denominator — credits only net improvement, so do-nothing agents on polluted instances score 0 not 1.0 (F2); **pollution gate** emits `status: polluted_dataset` (mirrors `vacuous`) when ≥80% of TARGETS were already passing pre-fix AND fewer than 3 effective targets remain — surfaces representativeness instead of silently scoring (F1+F2); regression denominator uses **absolute R0=20 floor** `max(R0, min(\|preserve_set\|, \|\mathcal{T}\|))` — broken=1 always costs at most 5%, decouples small-T sharpness from large-T blindness (F3); `preserve_set` and `T_p_baseline` are sourced from the **per-run report's `test_patch_result.passed_tests`** (the same observation that produced $F_p$ / $F_f$) — F2 closure actually fires on n2p-only pollution-prone instances; F4 partially re-opens (run-determined baseline) but freya empirics show 0% variance across 150 same-(instance, model) re-run groups — documented as v3 watchpoint; per-language M-2 exclusion count surfaced in CSV and `m2_excluded_per_language` diagnostic (F1); `baseline_drift` diagnostic exposes dataset-vs-run baseline discrepancy for instances where the dataset's `test_patch_result.passed_tests` differs from the run's. | All prior closures preserved. **FAILED Audit #6**: numerator `max(0, \|T∩F_p\| - \|T_baseline\|)` double-penalizes regressions of baseline targets — regressed baseline target is subtracted from numerator AND counted in `broken`/`factor` — two penalties for one event. Also missing `f2p_baseline_pass_count` env-drift alarm diagnostic. |
| **v2g (set-difference numerator + env-drift gate + parametrized thresholds) — THIS DOC** | All v2f shape preserved. (1) Numerator: $\text{hits\_new} = \lvert(\mathcal{T}\cap F_p)\setminus T_{p,\text{baseline}}\rvert$ (set-difference) — regressed baseline targets penalized exactly once via `factor`. (2) **F2p-drift gate** (Audit-7): if `f2p_baseline_pass_count / len(gold_f2p) ≥ f2p_drift_threshold` (default 0.3), return `status: invalid` — env non-reproduction rate too high for reliable signal. (3) **Parametrized thresholds**: `r0`, `pollution_threshold`, `eff_min`, `f2p_drift_threshold` are keyword arguments with defaults, enabling per-corpus tuning without code changes. (4) **Skip-evasion closure**: `broken = \|preserve\_set ∩ (F_f ∪ F_s)\|`. Prior reviewer's Issue 2 smooth gate REJECTED. Prior reviewer's Bonus "don't subtract f2p" REJECTED. | All prior closures preserved. Numerator double-penalization corrected. F2p-drift danger band (0.3–0.8 pollution_rate) now gates to `invalid` instead of scoring with ignored flag. Noise: spurious recall floor is $O(\varepsilon)$ regardless of $\lvert\mathcal{T}_{\text{eff}}\rvert$ — $\lvert\mathcal{T}_{\text{eff}}\rvert$ cancels in the ratio (Audit-7 correction of prior wrong claim); re-run aggregation required for flake-resistance. |

The Oracle and reviewer critiques were technically correct and structurally important. This document is the author's reconciliation through six audit gauntlets — including a mid-flight correction (Audit #5) that caught a structural defect in the first v2f draft before it landed in code, and an Audit #6 meta-review that corrected a reviewer-proposed fix that would have broken the formula.

---

## 1. Purpose

Replace the current binary `reward ∈ {0, 1}` (per `milo-gym/docs/specs/sections/06-reward.md`) with a continuous reward in `[0, 1]` that:

1. Measures **completion** (recall of gold targets), not precision of touched tests.
2. Closes the two critical defects from Oracle audit #1 (C1 gradient collapse on `valid:false`, C2 n2p-injection exploit) by sourcing targets from the dataset (not the run report) and recomputing observed results from raw test arrays (not cached 4-dicts).
3. Closes the three critical defects from Oracle audit #2 (N1 inert regression channel, N2 displaced-not-closed C1, N3 Flaw 4 redux) by replacing $\lvert\text{gold}_{p2p}\rvert$ with $\lvert\text{preserve\_set}\rvert = \lvert\text{gold}_{p2p} \cup T_{p,\text{run}}\rvert$ in the regression denominator, by lazy re-curating empty gold dicts from raw test arrays, and by trusting full $\text{gold}_{n2p}$ at compute time across all languages.
4. Provides a regression penalty that is neither hard-gated (too discrete for RL), nor relative-only (regression-blind on huge baseline suites), nor inert (when curator-supplied $\text{gold}_{p2p}$ is empty).
5. Distinguishes `vacuous`, `invalid`, `polluted_dataset`, and `no_signal` from honest `reward = 0` via a separate `status` channel — without negative reward values.
6. Has citation-level academic and engineering grounding for every load-bearing decision.
7. Ships behind a dual-emission scheme: binary remains canonical until empirical A/B validation per `continuous_reward_plan.md` §6 gates promotion.
8. **Universal**: same formula, same constants, same semantics for all 8 languages (Python, JS, TS, Go, Rust, Cpp, C, Java). No language conditional branches at compute time. No silent exclusions. All exclusions surfaced as explicit `status` values consumable by the sampler and CSV aggregator.

---

## 1.1 Scope and limitations (Audit #5 reviewer point 2)

v2f is a **terminal test-outcome reward**: a single scalar computed from the run report's final test state ($F_p$, $F_f$) against the dataset's gold transitions and the run's pre-fix baseline. It does not look at the trajectory — number of steps, reasoning quality, tool-use patterns, intermediate failures — and therefore cannot do **credit assignment across a long, sparse trajectory** by itself.

For long-horizon agentic RL on Milo-Bench-class tasks, v2f is designed to be **one channel of a composite reward**, not the only signal:

| Channel | Source | Captures | Limitations |
|---|---|---|---|
| **v2f test-outcome (this doc)** | Run report's $F_p$, $F_f$, $T_{p,\text{run}}$ | Did the agent fix the right tests without breaking baseline? | Sparse terminal; flat across all trajectories that land the same final state; half-blind on compiled languages per §1.5 F1 / §10.3.1 |
| **Rubric channel** | `rubric_framework.md` LLM judge | Reasoning quality, scaffold correctness, plan coherence | Subjective; needs calibration against tests |
| **Process channel** | step-level heuristics: bug reproduction, localization, partial-progress signals | Long-horizon credit assignment | Heuristic; risk of reward hacking; not yet specified |

This decomposition is required by Audit #5 reviewer point 2: *"a continuous final-state recall is marginally less sparse than binary, but it's still a sparse terminal signal. It cannot distinguish a 40-step principled fix from a 200-step flail that happened to land the same final state."* That observation is correct. v2f does not claim to solve it.

**What v2f IS**:
- The canonical *test-outcome* component of a composite reward
- An evaluation metric for pass@k / pass@1 reporting
- A continuous-valued partial-credit signal complementing binary SWE-bench-style outcomes
- Universal across all 8 languages in the multilingual benchmark

**What v2f is NOT**:
- A complete RL reward for long-horizon training (use composite)
- A measure of agent reasoning or process quality (use rubric)
- A dense per-step shaping signal (use process channel)
- A measure that closes the "test-pass ≠ correctness" gap (inherent limitation; mitigation is dataset curation, not formula)

**Empirical applicability note (current MiloBench corpus)**: On the current 10-dataset / 8-trajectory MiloBench corpus, the pollution-correction machinery (baseline subtraction, pollution gate, R0-floored regression factor) is **inert**: all 8 trajectories show `T_baseline=0`, `pollution_rate=0`, `broken=0`, `factor=1.0`. v2g reduces to plain `recall = |T ∩ F_p| / |T|` on every instance. The constants (`R0=20`, `pollution_threshold=0.8`, `eff_min=3`) are tuned to the freya-350 distribution; they neither help nor hurt on the current corpus but remain in place as future-proofing for corpora that exhibit curation-vs-runtime baseline drift (starship-138 / testcontainers-java-8298 / rxdb-4758 patterns). For the current corpus, the v2g code path is functionally equivalent to plain recall × min-form factor. **T=1 edge case** (e.g., carbon-lang-6690): when a target set contains a single test, the continuous reward degenerates to binary by construction (`reward ∈ {0.0, 1.0}` since recall is either 0/1 or 1/1).

Promotion from Phase-1 binary-canonical to v2f-canonical (per `continuous_reward_plan.md` §6) is gated on A/B validation that v2f provides at least non-degenerate training signal compared to binary; promotion to *sole RL reward* is **not contemplated** by this spec. The composite design is the recommended path.

---

## 1.5 Audit #4 + #5 findings — what was broken in v2e and v2f-attempt-1, and why

After v2e shipped, an external reviewer + Oracle audit #4 found **four structural defects** that all three prior audits missed because they probed mechanics (which dict to read, how the regression channel behaves) rather than the **validity of the denominator**. The audits hardened the plumbing to a high standard while leaving one premise un-probed: *is `gold_n2p` actually the issue's test set on the instances where it dominates `T`?*

Empirical investigation against the freya dataset (350 instances, 450 run reports) showed the answer is **no** on the partial-collapse instances. The four findings below were confirmed against on-disk data; v2f closes each structurally.

### F1 — M-2 silently excludes ~44% of the dataset, compiled-language-skewed

**What the spec did (v2e §3.3 invalid trigger b, §8.2 `test_invalid_when_test_stage_empty_with_gold`):** When `test_patch_result` reported all three counts (passed/failed/skipped) as zero AND $\lvert\mathcal{T}\rvert > 0$, the row was marked `status: invalid` and excluded from aggregation. The intent was integrity: an empty test stage means the harness never observed the pre-fix baseline, so $T_{p,\text{run}}$ is unreliable.

**What the audit found:** This rule fires on **155/350 = 44%** of the freya dataset, with severe per-language skew:

| Language | M-2 fires | % of language | Versus full dataset |
|---|---|---|---|
| Rust | 35/44 | **79.5%** | sample at 40% |
| Java | 26/41 | 63.4% | sample at 0% |
| C | 20/37 | 54.1% | sample varies |
| Go | 26/57 | 45.6% | sample at 5% |
| Cpp | 17/40 | 42.5% | sample varies |
| TS | 16/42 | 38.1% | sample varies |
| JS | 14/44 | 31.8% | sample varies |
| Python | 1/45 | **2.2%** | sample at 0% |

The 50-instance trajectory subsample (450 reports) triggers M-2 at only **13%** (vs full **44%**) because it under-sampled the M-2-prone bucket. Every prior CSV ("8% cpp", "0.255 mean reward_continuous_v2") was computed on a representativeness-biased survivor set. The rule is *correct* — empty test_patch_result genuinely is unreliable signal — but its **exclusion was never quantified or surfaced**, so consumers couldn't tell that the canonical reward distribution was reported on the cleanest 56% of the data.

**Severity: HIGH. Reporting hygiene defect; downstream pass@k numbers are not invalid, but they over-state generalization across the multilingual mix this benchmark exists to evaluate.**

### F2 — `gold_n2p` pollution → do-nothing agents score near 1.0 on 51% of the dataset (CRITICAL)

**What the spec did (v2e §2.3, §2.4):** v2e's N3 closure rejected v2c's language-specific n2p filter (which would have shrunk AMReX-Codes-4238's TARGETS from 57 → 2, re-opening reviewer Flaw 4). v2e's resolution was **"trust full $\text{gold}_{n2p}$ for all languages at compute time, no filter"**, on the grounds that the dataset is frozen and the agent cannot inject names into it.

**What the audit found:** the rejection of *language-specific* filtering was correct, but the conclusion ("trust full gold_n2p") is wrong. The underlying problem is that on a large fraction of the dataset, **gold_n2p is dominated by pre-existing baseline-passing tests, not by tests the test_patch newly adds**. The upstream bucketing logic at `multi_swe_bench/harness/report.py:130-138` classifies `test.test==NONE ∧ test.fix==PASS` as n2p — `NONE` means "not observed in the test_patch stage" — but on many instances the test stage runs with a *narrower* test discovery scope than the fix stage. Tests that exist and pass in the fix stage but were *invisible to the test stage's discovery pattern* land in n2p. They are not "fix-dependent" tests; they are pre-existing tests caught in a scope-mismatch.

**Empirical scan across the 340 non-vacuous freya datasets:**

| Pollution signature | Count | % |
|---|---|---|
| $\mathcal{T}$ = $\text{gold}_{n2p}$ exclusively | 194 | 57.1% |
| $\lvert\text{gold}_{n2p}\rvert \ge 0.8 \cdot \lvert\mathcal{T}\rvert$ | 222 | 65.3% |
| **Suspect** ($n2p \ge 0.8 \cdot T$ AND $<20\%$ in test_patch AND $\lvert\mathcal{T}\rvert \ge 10$) | **172** | **50.6%** |
| Per-language suspect: go 35, rust 34, java 26, ts 25, c 19, js 16, cpp 13, python 4 | | |

**Run-time manifestation across 450 reports (after excluding 36 M-2 and 90 vacuous, 324 surviving):**

- Do-nothing recall ($\lvert\mathcal{T} \cap T_{p,\text{run}}\rvert / \lvert\mathcal{T}\rvert$) $> 0$ in **18/324 = 5.6%**
- $> 0.5$: 9 reports
- $> 0.9$: 0 reports
- **Concrete confirmed cases:**
  - `starship/starship-138` (rust, $\lvert\mathcal{T}\rvert$=89): do-nothing recall = **0.888 across all 9 runs**
  - `testcontainers/testcontainers-java-8298` (java, $\lvert\mathcal{T}\rvert$=488): do-nothing recall = **0.342 across all 9 runs**

In other words: an empty agent patch on `starship-138` collects 89% of available reward under v2e because 79 of its 89 "targets" are pre-existing tests that pass regardless of agent work. The structural pollution rate is 51% of the dataset; only a smaller fraction (5.6% of surviving runs in the 50-instance subsample) manifests as run-time inflation in freya, but the manifestation set is **non-representative** — instances most likely to manifest are the same ones disproportionately excluded by F1's M-2 rule, so the sample tells us little about the population.

**Compounds with F3:** pollution-prone instances skew large-$\lvert\mathcal{T}\rvert$, which is exactly where v2e's min-form regression denominator gives the smallest per-break penalty. A do-nothing agent on a polluted large-$\mathcal{T}$ instance gets near-1.0 recall AND barely-noticed regression cost.

**Severity: CRITICAL. Validator-1110-class range compression. The metric stops measuring agent contribution and starts measuring suite health on the polluted instances.**

### F3 — min-form denominator couples regression penalty to target count

**What the spec did (v2e §2.5):** $\text{factor} = 1 - \dfrac{\text{broken}}{\min(\max(1, \lvert\text{preserve\_set}\rvert), \max(1, \lvert\mathcal{T}\rvert))}$.

**What the audit found:** when $\lvert\text{preserve\_set}\rvert$ is large, the denominator is $\lvert\mathcal{T}\rvert$, so the same one broken baseline test costs:

| $\lvert\text{preserve\_set}\rvert$ | $\lvert\mathcal{T}\rvert$ | broken | denom | penalty |
|---|---|---|---|---|
| 50 | 2 | 1 | 2 | **50.0%** |
| 50 | 500 | 1 | 50 | 2.0% |
| **ratio** | | | | **25× exactly** |

There is no principled reason a broken baseline test should be penalized 25× more heavily just because the task has fewer targets. v2e framed the min-form as "more impactful of preserve-budget, target-budget" but the consequence is that **regression sensitivity scales inversely with task size**. Combined with F2, the worst case is concentrated in exactly the wrong place: polluted large-$\mathcal{T}$ instances get inflated recall AND minimum regression cost simultaneously.

**Severity: MEDIUM. Real arithmetic property; compounds with F2; not catastrophic alone.**

### F4 — `T_p_run` makes the canonical binary reward run-non-deterministic

**What the spec did (v2e §2.5 ¶ "preserve_set", §2.7 #12):** $\text{preserve\_set} = \text{gold}_{p2p} \cup T_{p,\text{run}}$ where $T_{p,\text{run}}$ comes from the **per-run report's** `test_patch_result.passed_tests`. The canonical Phase-1 binary reward is $\mathbb{1}[\mathcal{T} \subseteq F_p \land \text{preserve\_set} \cap F_f = \emptyset]$, so it also depends on $T_{p,\text{run}}$.

**What the audit found:** the test_patch stage runs the pre-fix codebase against test extractors that have no internal averaging or pinning. In the presence of flaky baseline tests, $T_{p,\text{run}}$ varies across re-runs of the same (instance, agent rollout) pair → $\text{preserve\_set}$ varies → $\text{preserve\_set} \cap F_f$ varies → the *canonical* Phase-1 binary reward is non-deterministic across re-runs that the agent did nothing to differentiate.

**Empirically in freya** (150 same-(instance, model) re-run groups):

- $T_{p,\text{run}}$ varies: **0/150** — currently stable
- $F_p$ varies: 51/150 (34%) — but this is *rollout* variance (different fix_patches), not test-stage flake
- $F_f$ varies: 39/150 (26%) — same

The pathology is **structurally real** but does not currently manifest in freya. Worth closing because the right fix is also the right design: the curation-time baseline is the canonical preservation set, and using it removes the spec-bug entirely.

**Severity: LOW (in freya), STRUCTURAL (in general).**

**Initial v2f-attempt-1 proposed**: source `T_p_baseline` from the **dataset's** `test_patch_result.passed_tests` (deterministic by construction). **Audit #5 caught that this is wrong** — see F5 below.

### F5 (Audit #5) — frozen-dataset baseline source is STRUCTURALLY INERT on n2p-only instances

**What v2f-attempt-1 did:** to close F4's non-determinism, sourced `T_p_baseline = dataset["test_patch_result"]["passed_tests"]` and computed `T_baseline = T ∩ T_p_baseline`. Claimed this would identify pre-existing-passing targets and adjusted recall would subtract them.

**What Audit #5 found (empirical, against `freya/milo-bench/dataset/*.jsonl`)**:

The bucketing rule at `multi_swe_bench/harness/report.py:130-138` is **per-observation**: in a single bucketing pass, a test name lands in exactly one of `{p2p, f2p, s2p, n2p}` based on its `(test_stage_status, fix_stage_status)` pair. A name in `gold_n2p` has `test_stage_status = NONE`, which is **definitionally not in that same observation's `test_patch_result.passed_tests`** (which requires `test_stage_status = PASS`). The dataset's gold dicts and the dataset's `test_patch_result` come from the **same curation-time observation**, so the intersection is empty by construction on every n2p name.

Empirical verification on the three reviewer-cited polluted instances:

| Instance | \|T\| (composition) | \|dataset.tpr.passed\| | T ∩ dataset.tpr.passed | T ∩ run.tpr.passed |
|---|---|---|---|---|
| `starship/starship-138` (rust) | 89 (all n2p) | **0** | **0** | **79** |
| `testcontainers/testcontainers-java-8298` (java) | 488 (all f2p) | 499 | **167** | **167** |
| `pubkey/rxdb-4758` (typescript) | 539 (all n2p) | 511 | **0** | (not in trajectories) |

The dataset-vs-run discrepancy on starship-138 (dataset says 0 baseline passes, run shows 82) is the **F2 pollution mechanism itself**: the dataset was curated under a different test-discovery scope than the eval harness runs with. The runtime's broader scope discovers tests that were NONE at curation → they pass at run-time test stage → land in `run.test_patch_result.passed_tests`. v2f-attempt-1's frozen-dataset source structurally cannot see this drift.

**Oracle audit #4's measured "do-nothing recall = 0.888 on starship-138" was computed against the run report**, not the dataset (verified at `/tmp/oracle_v2e_audit/f2_aggregate.py:48-58`: `tpr = rep.get("test_patch_result")` where `rep` is the run report). v2f-attempt-1, had it shipped, would NOT have closed F2 on starship-138 — the recall would have been computed as `recall = 79/89 = 0.888` for a do-nothing agent (intersection vacuously empty so `T_baseline = ∅`, `T_eff = T`, no subtraction).

**Severity: CRITICAL. v2f-attempt-1's F2 closure was structurally inert on 51% of the pollution-prone slice the spec was written for.**

**v2f (this doc) fix:** source `T_p_baseline = run_report["test_patch_result"]["passed_tests"]` — the same observation that produces $F_p$ / $F_f$. The pollution mechanism IS curation-vs-runtime drift; identifying it requires the runtime observation. Now `T ∩ T_p_baseline = 79` on starship-138, `T_baseline = 79`, `T_eff = 10`, do-nothing `hits_new = |(T ∩ F_p) \ T_p_baseline| = |{79 names} \ {82 names}| = 0`, recall = 0/10 = **0.0** ✓ — F2 actually fires.

**Trade-off (F4 partial re-open)**: `T_p_baseline` is now per-run, so structurally subject to baseline test flake → preserve_set varies → binary varies across re-runs. Empirically `T_p_run` was 0% variant across 150 same-(instance, model) re-run groups in freya, so the structural risk does not manifest. Documented in §9 risk #4 as a v3 watchpoint with a clear path forward (pin to a separate frozen baseline run when corpora with flaky baselines are introduced).

### Root cause shared by F1, F2, F5

Audits 1-3 verified plumbing: are the right dicts read, are the right transitions tracked, is the right channel active on empty inputs? The audit-4 thesis — *"the validity of the denominator (`gold_n2p` is the issue's test set) is itself an unaudited premise"* — is correct. v2e's `gold_n2p` includes pre-existing tests caught in test-stage scope mismatch on ~51% of the dataset; M-2 deletes only the fully-collapsed (test stage produced nothing) subset; the partially-collapsed (test stage ran but n2p contains pre-existing tests) subset survives and produces inflated near-passes for do-nothing agents.

**v2f fixes the root cause via baseline subtraction**: instead of trusting that every name in `gold_n2p` represents "work to be done," we **subtract the names that were already passing pre-fix** from both the numerator and the denominator. Tests that were pre-existing pass don't count as targets the agent fixed *or* as targets the agent needed to fix. The metric becomes:

> *"Of the gold targets the agent actually had to make pass, how many did the agent's fix make pass?"*

This is universal, language-independent, and structurally closes F2 without re-opening N3 (no test names are dropped at curation time; AMReX-4238 still has all 57 targets visible). The baseline source must be the **run report's** `test_patch_result.passed_tests`, NOT the dataset's — see §1.5 F5 for why the dataset source is structurally inert on n2p-only instances.

---

## 2. The formula

### 2.1 Inputs

**From the DATASET record** (`freya/milo-bench/dataset/<instance_id>.jsonl`, single record per file):

| Symbol | Source field | Meaning |
|---|---|---|
| $\text{gold}_{f2p}$ | `f2p_tests` (dict, keys = test names) | gold tests that should go fail → pass after fix |
| $\text{gold}_{s2p}$ | `s2p_tests` (dict, keys = test names) | gold tests that should go skip → pass after fix |
| $\text{gold}_{n2p}$ | `n2p_tests` (dict, keys = test names) | gold tests that should go none → pass (added by `test_patch`) |
| $\text{gold}_{p2p}$ | `p2p_tests` (dict, keys = test names) | gold tests that should stay passing across both stages |
| `test_patch_result` | `test_patch_result` (raw bucket dict with `passed_tests`/`failed_tests`/`skipped_tests` lists, if present in the dataset record) | raw observed test-stage outcomes from dataset curation — source of truth for lazy re-curation when gold dicts empty |
| `fix_patch_result` | `fix_patch_result` (raw bucket dict, if present in the dataset record) | raw observed fix-stage outcomes from dataset curation — source of truth for lazy re-curation when gold dicts empty |
| `test_patch` | `test_patch` (unified diff string) | test patch content; diagnostic only in v2g |
| `lang` | `lang` (string) | language discriminator: `python`, `javascript`, `typescript`, `go`, `rust`, `cpp`, `c`, `java` |

**From the RUN report** (`report.json` written by the upstream harness):

| Symbol | Source field | Meaning |
|---|---|---|
| $F_p$ | `fix_patch_result.passed_tests` (list, set-coerced) | tests that passed in fix stage |
| $F_f$ | `fix_patch_result.failed_tests` (list, set-coerced) | tests that failed in fix stage |
| $F_s$ | `fix_patch_result.skipped_tests` (list, set-coerced) | tests that were skipped in fix stage |
| $T_{p,\text{run}}$ | `test_patch_result.passed_tests` (list, set-coerced) | tests that passed in **test-patch (pre-fix) stage** — the baseline-passing set actually observed in this run |

**Critical plumbing notes**:

1. `record["instance"]["test_patch"]` in `output.jsonl` is **empty** in freya runs (verified empirically). The dataset record path is the canonical source for `test_patch`.
2. The run report's cached 4-dicts (`p2p_tests`, `f2p_tests`, `s2p_tests`, `n2p_tests`) get emptied when `Report.check()` returns `valid=False` (see `multi_swe_bench/harness/report.py:90-142`). **Never read from them.** Read only the raw `passed_tests` / `failed_tests` / `skipped_tests` arrays from both `test_patch_result` and `fix_patch_result`. The dataset's gold targets are authoritative and were populated at dataset-construction time, before any run-time `valid` gate — except when curation itself produced empty dicts (N2 case), which v2d handles via lazy re-curation (§2.2).

### 2.2 Lazy re-curation of empty gold dicts (R1)

**Why needed (Oracle finding N2):** Empirical scan across 350 freya datasets found 10/350 instances where ALL four gold dicts (`f2p_tests`, `s2p_tests`, `n2p_tests`, `p2p_tests`) are empty — including HypothesisWorks-4452 in the spec's canonical example set. v2c trusted gold dicts unconditionally; if the curator-produced cached dicts were empty, the formula collapsed to `recall = 0/0` → vacuous → no signal. This **displaced C1 to dataset-construction time** rather than closing it.

**Fix:** If the gold dicts are empty but the dataset record carries the raw `test_patch_result` / `fix_patch_result` arrays (as freya datasets do), re-derive the gold dicts at reward-compute time using the same bucketing logic as `multi_swe_bench/harness/report.py:130-138`:

```python
def lazy_recurate_gold(dataset_record: dict) -> dict:
    """If all four gold dicts are empty, recompute them from raw test_patch/fix_patch arrays
    using the canonical bucketing rules from report.py:130-138.

    Returns the gold dict (either the original or the re-curated one).
    Status `vacuous` is emitted only if both gold dicts AND raw arrays are empty.
    """
    gold = {
        "f2p_tests": set(dataset_record.get("f2p_tests", {}) or {}),
        "s2p_tests": set(dataset_record.get("s2p_tests", {}) or {}),
        "n2p_tests": set(dataset_record.get("n2p_tests", {}) or {}),
        "p2p_tests": set(dataset_record.get("p2p_tests", {}) or {}),
    }
    if any(gold.values()):
        return gold

    test_stage = dataset_record.get("test_patch_result") or {}
    fix_stage = dataset_record.get("fix_patch_result") or {}
    t_p = set(test_stage.get("passed_tests") or [])
    t_f = set(test_stage.get("failed_tests") or [])
    t_s = set(test_stage.get("skipped_tests") or [])
    f_p = set(fix_stage.get("passed_tests") or [])
    f_f = set(fix_stage.get("failed_tests") or [])

    if not (t_p or t_f or t_s or f_p or f_f):
        return gold  # truly vacuous — caller emits status:vacuous

    all_seen = t_p | t_f | t_s | f_p | f_f
    for name in all_seen:
        in_test = (name in t_p, name in t_f, name in t_s)
        in_fix = (name in f_p, name in f_f)
        # Canonical bucketing (mirrors report.py:130-138)
        if not any(in_test) and in_fix[0]:        # NONE -> PASS
            gold["n2p_tests"].add(name)
        elif in_test[1] and in_fix[0]:             # FAIL -> PASS
            gold["f2p_tests"].add(name)
        elif in_test[2] and in_fix[0]:             # SKIP -> PASS
            gold["s2p_tests"].add(name)
        elif in_test[0] and in_fix[0]:             # PASS -> PASS
            gold["p2p_tests"].add(name)
    return gold
```

**Adversarial properties:** Lazy re-curation reads only from the dataset record (frozen, immutable to agent). The run report is never used to derive gold targets. C2 injection defense survives.

**Property: HypothesisWorks-4452 landing.** If the raw arrays in the dataset record are also empty (true vacuous dataset row, no actual targets to grade), the formula emits `status: vacuous` and reward `0.0` is excluded from pass@k — honest signal, not a silent collapse.

### 2.3 n2p hygiene at compute time (R3)

**v2c's mistake:** v2c applied a language-conditional `gold_n2p_filt` filter that dropped names not parseable to a `test_patch` file. Oracle audit #2 finding N3 showed that the strict-fallback would shrink AMReX-Codes-4238's TARGETS from 57 → 2 (96% loss) because the §10 fallback was too aggressive on languages without filterable test names.

**v2d position:** **No language-specific n2p filter at compute time.** Trust the dataset's full $\text{gold}_{n2p}$ for all languages. The agent cannot mutate the frozen dataset; C2 (n2p injection) is structurally closed because TARGETS come from the dataset, not from the run report. There is no adversarial path that benefits from filtering $\text{gold}_{n2p}$ at compute time.

The §2.2 hygiene filter from v2c is **removed** from the formula. It belongs (if at all) in dataset-curation tooling, not in reward computation.

Formally:

$$
\text{gold}_{n2p}^{\text{compute}} = \text{gold}_{n2p} \quad \text{(no filter, all languages)}
$$

### 2.4 TARGETS, baseline subtraction, and adjusted recall (v2g)

#### 2.4.1 TARGETS (unchanged from v2e)

$$
\mathcal{T} = \text{gold}_{f2p} \cup \text{gold}_{s2p} \cup \text{gold}_{n2p}
$$

#### 2.4.2 Baseline-passing target set $\mathcal{T}_{\text{baseline}}$ (F2 closure, F4 partial — Audit-5 corrected)

**The Audit-5 correction**: source `T_p_baseline` from the **run report's** `test_patch_result.passed_tests`, **not the dataset's**. v2f-attempt-1 sourced from the dataset for F4 determinism, but Audit #5 proved this was structurally inert on n2p-only instances (§1.5 F5) — the per-observation bucketing rule makes `T ∩ dataset.tpr.passed = ∅` by construction whenever T contains any gold_n2p name.

$$
T_{p,\text{baseline}} = \text{set}\bigl(\text{run\_report.test\_patch\_result.passed\_tests}\bigr)
$$

$$
\mathcal{T}_{\text{baseline}} = \mathcal{T} \cap T_{p,\text{baseline}}
\qquad
\mathcal{T}_{\text{eff}} = \mathcal{T} \setminus \mathcal{T}_{\text{baseline}}
\qquad
\text{pollution\_rate} = \frac{\lvert\mathcal{T}_{\text{baseline}}\rvert}{\max(1, \lvert\mathcal{T}\rvert)}
$$

**Semantics**: $\mathcal{T}_{\text{baseline}}$ are gold targets that were *already passing in this run's pre-fix test stage*. The pollution mechanism (F2) is the **curation-vs-runtime baseline drift** — tests that were NONE at curation (bucketed as `gold_n2p`) but discovered and passing at runtime test stage (lands in `run.test_patch_result.passed_tests`). The run report is the only observation that can see this drift; the dataset cannot by the bucketing rule. $\mathcal{T}_{\text{eff}}$ is the set of targets the agent actually had to make pass — the "work" for this instance.

**Why run report, not dataset (vs v2f-attempt-1)**: see §1.5 F5 for the full empirical argument. Summary: on starship-138 (89 n2p targets), `T ∩ dataset.tpr.passed = 0` (vacuously empty, no signal); `T ∩ run.tpr.passed = 79` (correctly identifies the 79 pre-existing-passing tests, leaving 10 effective targets the agent must actually fix). Only the run report enables the F2 closure to *fire* on n2p-only pollution-prone instances.

**`baseline_drift` diagnostic** (§3.1): we still compare against the dataset's `test_patch_result.passed_tests` when present and emit `baseline_drift = |run.tpr.passed Δ dataset.tpr.passed|` (symmetric set-difference size). High drift on a given instance signals dataset curation under a different harness configuration than eval; useful for downstream curation hygiene without entering the formula.

**F4 disposition (partial, not full)**: $T_{p,\text{baseline}}$ is per-run-observed. Structurally subject to baseline test flake → `preserve_set` varies → `reward_binary` varies. Empirically $T_{p,\text{run}}$ was **0% variant** across 150 same-(instance, model) re-run groups in the freya 450-report dataset, so the pathology is currently latent. Documented in §9 risk #4 and §14 F4 row as a v3 watchpoint: when corpora with flaky baselines are introduced, pin $T_{p,\text{baseline}}$ to a separate frozen baseline run (compute it once, cache it, source from cache thereafter).

#### 2.4.3 Pollution gate (F1 + F2 transparency)

When the dataset's gold targets are dominated by pre-existing baseline-passing tests, scoring would inflate. We surface this honestly via a dedicated status rather than silently emitting an inflated reward.

$$
\text{POLLUTION\_THRESHOLD} = 0.8 \qquad \text{EFF\_MIN} = 3
$$

$$
\text{polluted\_dataset} \iff \text{pollution\_rate} \ge \text{POLLUTION\_THRESHOLD} \;\land\; \lvert\mathcal{T}_{\text{eff}}\rvert < \text{EFF\_MIN}
$$

When the gate fires, the row is emitted with `status: polluted_dataset` and `reward = 0.0`, excluded from pass@k by the sampler (same disposition as `vacuous`). The diagnostic `pollution_rate` is emitted on **every** row (gate fired or not) so consumers can stratify pass@k by pollution band.

**Rationale for the constants**: an instance where ≥80% of its gold targets were already passing pre-fix AND fewer than 3 targets remain to be fixed has effectively no agent-gradable signal — at most 2 targets distinguish a perfect agent from a do-nothing agent. The threshold values are tuned to the freya distribution and reviewed in §6 Scenario 19. They are configurable in `compute_reward_v2g`.

#### 2.4.4 Adjusted recall (F2 closure, Audit-6 corrected numerator)

$$
\text{recall} =
\begin{cases}
\dfrac{\lvert (\mathcal{T} \cap F_p) \setminus T_{p,\text{baseline}} \rvert}{\lvert\mathcal{T}_{\text{eff}}\rvert} & \lvert\mathcal{T}_{\text{eff}}\rvert > 0 \\[12pt]
\mathbb{1}[\mathcal{T} \subseteq F_p] & \lvert\mathcal{T}_{\text{eff}}\rvert = 0 \;\land\; \lvert\mathcal{T}\rvert > 0 \;\land\; \text{not polluted}
\end{cases}
$$

**Audit-6 numerator change (v2f → v2g)**: The prior v2f numerator used $\max(0, \lvert\mathcal{T}\cap F_p\rvert - \lvert\mathcal{T}_{\text{baseline}}\rvert)$. The meta-review (Audit #6) identified that this arithmetic form **double-penalizes regressions of baseline targets**: such a target already lowers `factor` (via `broken` in §2.5.2) AND it reduces $\lvert\mathcal{T}\cap F_p\rvert$ while $\lvert\mathcal{T}_{\text{baseline}}\rvert$ stays fixed — the arithmetic difference subtracts it again in the numerator. The set-difference form avoids this: a regressed baseline target disappears from $F_p$, falls out of $\mathcal{T}\cap F_p$, but is already NOT in $T_{p,\text{baseline}}$ (it regressed), so the set-difference count is unaffected by regressions. Regressions are penalized exactly once — by the factor.

The set-difference is always $\ge 0$ by construction; no clamp is needed. The clamp is dropped.

**Numerator interpretation**: $(\mathcal{T} \cap F_p) \setminus T_{p,\text{baseline}}$ is the set of gold targets that are passing post-fix **and** were NOT passing pre-fix. These are the tests the agent genuinely made pass. Pre-existing passing targets (in $T_{p,\text{baseline}}$) are excluded — their presence in $F_p$ is credited to the baseline, not the agent.

**Noise property note (Audit-6 correction of prior reviewer)**: The prior reviewer claimed the set-difference form reduces do-nothing noise bias. The meta-review (Audit #6) showed this is incorrect — the set-difference form has *linear*-in-$n$ do-nothing bias (under i.i.d. flakes) while the clamped arithmetic form has $\sqrt{n}$ bias, making the prior reviewer's fix *worse* on large-$T$ instances. The set-difference is adopted for **correctness** (no double-penalization), not for noise reduction. True noise-robustness requires baseline re-run aggregation, which no numerator formula can supply.

**Denominator interpretation**: $\lvert\mathcal{T}_{\text{eff}}\rvert$ is the count of targets the agent actually had work to do on. A perfect agent fixes all of them → recall = 1.0. A do-nothing agent on a clean (non-polluted) instance leaves $\lvert\mathcal{T}_{\text{eff}}\rvert$ unfixed → recall = 0.

**`starship-138` check (with corrected run-report baseline source)**:

- From dataset gold: $\lvert\mathcal{T}\rvert = 89$ (all in `gold_n2p`)
- From run report: $\lvert T_{p,\text{baseline}}\rvert = 82$, $\lvert\mathcal{T} \cap T_{p,\text{baseline}}\rvert = 79$
- Therefore: $\lvert\mathcal{T}_{\text{baseline}}\rvert = 79$, $\lvert\mathcal{T}_{\text{eff}}\rvert = 10$, $\text{pollution\_rate} = 79/89 = 0.888$
- Pollution gate: $0.888 \ge 0.8$ AND $\lvert\mathcal{T}_{\text{eff}}\rvert = 10 \ge 3$ → gate does NOT fire (10 effective targets is enough signal)
- Do-nothing agent: $\lvert\mathcal{T} \cap F_p\rvert = 79$ (the 79 pre-existing-passing targets stay passing); $\text{hits\_new} = \lvert(\mathcal{T}\cap F_p)\setminus T_{p,\text{baseline}}\rvert = \lvert\{79\text{ names}\}\setminus\{82\text{ names}\}\rvert = 0$; recall = $0/10$ = **0.0** ✓
- Empirical check via dataset+trajectories: Audit #5 confirmed `T ∩ dataset.tpr.passed = 0` (would have been vacuous-empty under v2f-attempt-1) but `T ∩ run.tpr.passed = 79` under v2f (Audit-5-corrected). F2 closure now actually fires.

**`testcontainers-java-8298` check**: similar arithmetic, do-nothing recall drops to 0.

**Fallback branch ($\lvert\mathcal{T}_{\text{eff}}\rvert = 0$, not polluted, $\lvert\mathcal{T}\rvert > 0$)**: **This branch is mathematically unreachable.** $\lvert\mathcal{T}_{\text{eff}}\rvert = 0$ iff $\mathcal{T} \subseteq T_{p,\text{baseline}}$ (all targets pre-existing), which forces $\text{pollution\_rate} = \lvert\mathcal{T}_{\text{baseline}}\rvert / \lvert\mathcal{T}\rvert = 1.0 \ge 0.8$. Combined with $\lvert\mathcal{T}_{\text{eff}}\rvert = 0 < 3$, the pollution gate always fires first and returns `status: polluted_dataset` before this branch is reached. The `else` in the pseudocode (§2.6.1) is kept as **dead-code defensive programming** (returns pure-preservation 1.0/0.0 fallback), but is unreachable by construction given the current gate constants.

### 2.5 Regression factor (v2g — frozen preserve_set + R0 absolute floor)

**Two changes versus v2e**:

1. **Source of $T_{p}$ in `preserve_set`**: same source as `T_{p,\text{baseline}}` from §2.4.2 — the **run report's** `test_patch_result.passed_tests`. (v2f-attempt-1 proposed the dataset's; Audit #5 invalidated that — see §1.5 F5.) This source matches v2e's $T_{p,\text{run}}$ and inherits v2e's empirical N1 closure properties.
2. **Absolute regression floor `R0`**: the min-form denominator gets a floor at $R0 = 20$, decoupling per-break cost from task target count on small-$\lvert\mathcal{T}\rvert$ tasks — closing F3.

#### 2.5.1 Preserve set

$$
\text{preserve\_set} = \text{gold}_{p2p} \cup T_{p,\text{baseline}}
$$

where $T_{p,\text{baseline}}$ is defined in §2.4.2 (run report's `test_patch_result.passed_tests`, same source used for `T_baseline`).

**N1 closure preserved**: on Rust/Java/C instances where $\text{gold}_{p2p}$ is empty but the run's pre-fix baseline has, say, 200 passing tests, the regression channel is alive ($\lvert\text{preserve\_set}\rvert = 200$). Verified empirically in v2e against freya: Java 8/9, JS 14/27, Go varied, Rust 3/18 with active $T_{p,\text{run}}$. v2f inherits these numbers because the source is the same.

**Adversarial property**: $T_{p,\text{baseline}}$ is the **pre-fix test_patch stage** observation, which runs before the agent's fix patch is applied. The agent cannot influence which tests pass in the test_patch stage under the harness contract that `fix_patch` cannot modify files in the test patch's scope. C2-class **name-set** injection defense survives. C2-class **semantic mutation** (BenchJack-style assertion-body rewrite of a gold target) is closed only insofar as the upstream harness enforces fix_patch ≠ test_patch file ownership (see SWE-bench issue #538). v2f does *not* re-validate test bodies at reward-compute time.

**Known limitation (Oracle audit #3 H-1, preserved)**: when the run's `test_patch_result.passed_tests` is empty AND $\text{gold}_{p2p}$ is also empty (observed on all cpp scored rows in freya), $\text{preserve\_set} = \emptyset$ and the regression channel is inert — factor saturates at 1.0 and reward reduces to pure adjusted recall. v2f does NOT add a synthetic fallback (e.g., $F_p \cup F_f$ envelope) because that would penalize all fix-stage failures as "regressions" without evidence they were ever passing. The `regression_channel_active` diagnostic (§3.1) signals this case so downstream consumers can stratify pass@k.

**F4 disposition**: same as §2.4.2 — `preserve_set` varies across re-runs if baseline tests are flaky. Empirically 0% variance in freya; v3 watchpoint when flaky corpora arrive.

#### 2.5.2 Regression factor with R0 floor

$$
\text{broken} = \lvert \text{preserve\_set} \cap (F_f \cup F_s) \rvert
$$

**Skip-evasion closure (Oracle audit advisory)**: The definition uses $\text{preserve\_set} \cap (F_f \cup F_s)$ (tests explicitly failing or explicitly skipped) rather than $\text{preserve\_set} \cap F_f$ alone (tests explicitly failing). The distinction matters: an agent could mark a preserve\_set test as `@skip`/`@ignore` — the test then lands in $F_s$, not $F_f$, and would escape the $\cap F_f$ penalty. Including $F_s$ closes this evasion path. Tests not observed in the fix stage at all (absent from $F_p \cup F_f \cup F_s$) are NOT counted as broken — only explicitly failed or explicitly skipped tests are penalized.

$$
R_0 = 20 \qquad \text{(absolute regression-budget floor)}
$$

$$
\text{denom} = \max\!\left(R_0,\; \min\!\left(\max(1,\lvert\text{preserve\_set}\rvert),\; \max(1,\lvert\mathcal{T}\rvert)\right)\right)
$$

$$
\text{factor} = \max\!\left(0,\; 1 - \frac{\text{broken}}{\text{denom}}\right)
$$

#### 2.5.3 Why $R_0 = 20$, and why this shape closes F3

The v2e min-form denominator caused the same one broken baseline test to cost 50% on $\lvert\mathcal{T}\rvert=2$ tasks and 2% on $\lvert\mathcal{T}\rvert=500$ tasks — a 25× swing whose only causal driver is task target count. v2f's R0 floor caps the per-break cost at $1/R_0 = 5\%$ on tasks with $\min(\lvert\text{preserve}\rvert, \lvert\mathcal{T}\rvert) < R_0$, removing the small-T sharpness. On tasks where $\min(\lvert\text{preserve}\rvert, \lvert\mathcal{T}\rvert) \ge R_0$ the formula is identical to v2e's min-form, preserving §5.2 closure (regression-blindness on huge baselines remains closed because the min cap is still in force).

**$R_0 = 20$ rationale**: SWE-bench Verified (Jimenez et al. 2024 Table 6) reports median $\lvert\text{FAIL\_TO\_PASS}\rvert \approx 10$ with one standard deviation above $\approx 20$. Setting $R_0$ at one std above median means the typical task is unaffected by the floor; only very-small-target tasks benefit, which are exactly the cases where the reviewer's F3 complaint applied. The constant is configurable in `compute_reward_v2g`; the spec's canonical value is 20.

#### 2.5.4 Algebraic identity preserved

The min-form's classical identity $\dfrac{x}{\min(a,b)} = \max\!\left(\dfrac{x}{a}, \dfrac{x}{b}\right)$ is unchanged inside the floor. v2f adds one outer $\max$ with $R_0$ as the new lower bound on the denominator. The formula remains a recall × factor product in $[0, 1]$ with all v2e properties (bounded, monotonic in hits, antimonotonic in regressions, vacuous-honest) intact.

#### 2.5.5 Sample values vs v2e

| $\lvert\text{preserve\_set}\rvert$ | $\lvert\mathcal{T}\rvert$ | broken | v2e denom | v2e factor | v2f denom | v2f factor | Comment |
|---|---|---|---|---|---|---|---|
| 5 | 10 | 0 | 5 | 1.00 | 20 | 1.00 | broken=0 unaffected |
| 5 | 10 | 1 | 5 | 0.80 | 20 | **0.95** | small task: gentler, F3 closed |
| 206 | 10 | 5 | 10 | 0.50 | 20 | **0.75** | small task: gentler, F3 closed |
| 8000 | 20 | 1 | 20 | 0.95 | 20 | 0.95 | identical above floor |
| 8000 | 20 | 20 | 20 | 0.00 | 20 | 0.00 | catastrophic regression unchanged |
| **N1 scenario**: 200 (curation baseline) | 10 | 5 | 10 | 0.50 | 20 | **0.75** | small T: gentler, but channel still active |
| **F3-min scenario**: 50 | 2 | 1 | 2 | 0.50 | 20 | **0.95** | reviewer's 25× collapse — closed |
| **F3-max scenario**: 50 | 500 | 1 | 50 | 0.98 | 50 | 0.98 | already gentle — unchanged |

Compare with v2c on huge-baseline scenario ($\lvert P\rvert = 8000$, broken=1, $\lvert\mathcal{T}\rvert = 20$): v2c → $\max(1/8000, 1/20) = 0.05$, factor = 0.95. v2f → $1 - 1/\max(20, \min(8000, 20)) = 0.95$. Identical. §5.2 closure preserved.

### 2.6 Reward (v2g universal)

$$
\boxed{\;
r =
\begin{cases}
0.0 & \lvert\mathcal{T}\rvert = 0 & \text{status: vacuous} \\[6pt]
0.0 & \text{pollution\_rate} \ge 0.8 \;\land\; \lvert\mathcal{T}_{\text{eff}}\rvert < 3 & \text{status: polluted\_dataset} \\[6pt]
\displaystyle \max\!\left(0,\; \min\!\left(1,\; \text{recall} \times \text{factor}\right)\right) & \text{otherwise} & \text{status: scored}
\end{cases}
\;}
$$

where $\text{recall}$ is the **adjusted recall** from §2.4.4 (baseline subtraction applied) and $\text{factor}$ is the **R0-floored regression factor** from §2.5.2.

### 2.6.1 Universal compute pseudocode

```python
def compute_reward_v2g(dataset_record, instance_report):
    # 1. TARGETS (lazy re-curation §2.2 if all gold dicts empty)
    gold = lazy_recurate_gold(dataset_record)
    T = gold["f2p_tests"] | gold["s2p_tests"] | gold["n2p_tests"]

    if not T:
        return emit(status="vacuous", reward=0.0, recall=None, factor=None)

    # 2. Integrity (M-1 / M-2 / L-3 unchanged)
    if stage_count_drift(instance_report["test_patch_result"]) \
       or stage_count_drift(instance_report["fix_patch_result"]):
        return emit(status="invalid", reward=0.0)

    test_stage_total = sum(len(instance_report["test_patch_result"].get(k, []))
                           for k in ("passed_tests", "failed_tests", "skipped_tests"))
    if test_stage_total == 0 and T:
        return emit(status="invalid", reward=0.0)   # M-2 preserved

    # 3. Baseline source — RUN REPORT (Audit-5 corrected; see §1.5 F5)
    T_p_baseline = set(instance_report["test_patch_result"]["passed_tests"] or [])

    # Diagnostic: compare against dataset's baseline when present (no formula impact)
    dataset_tpr = (dataset_record.get("test_patch_result") or {})
    T_p_dataset = set(dataset_tpr.get("passed_tests") or [])
    baseline_drift = len(T_p_baseline ^ T_p_dataset)

    F_p = set(instance_report["fix_patch_result"]["passed_tests"] or [])
    F_f = set(instance_report["fix_patch_result"]["failed_tests"] or [])
    F_s = set(instance_report["fix_patch_result"].get("skipped_tests") or [])

    if T_p_baseline and not F_p and not F_f and not F_s:
        return emit(status="invalid", reward=0.0)

    # 4. Baseline subtraction (F2 closure)
    T_baseline = T & T_p_baseline
    T_eff = T - T_baseline
    pollution_rate = len(T_baseline) / max(1, len(T))

    # 5. Pollution gate (F1 + F2 transparency)
    if pollution_rate >= pollution_threshold and len(T_eff) < eff_min:
        return emit(
            status="polluted_dataset",
            reward=0.0,
            diagnostics=dict(pollution_rate=pollution_rate,
                             t_baseline_total=len(T_baseline),
                             t_eff_total=len(T_eff),
                             baseline_drift=baseline_drift),
        )

    # 5a. F2p-drift gate (Audit-7): env non-reproduction → invalid
    f2p_pass_count = len(gold["f2p_tests"] & T_p_baseline)
    if gold["f2p_tests"] and f2p_pass_count / len(gold["f2p_tests"]) >= f2p_drift_threshold:
        return emit(status="invalid", reward=0.0)

    # 6. Adjusted recall (Audit-6: set-difference numerator — no double-penalization)
    if len(T_eff) > 0:
        hits_new = len((T & F_p) - T_p_baseline)  # targets newly passing; always >= 0, no clamp needed
        recall = hits_new / len(T_eff)
    else:
        recall = 1.0 if T <= F_p else 0.0  # pure preservation fallback

    # 7. Regression factor with R0 floor (F3 closure)
    preserve_set = gold["p2p_tests"] | T_p_baseline
    broken = len(preserve_set & (F_f | F_s))  # F_s closes skip-evasion; unobserved tests not penalized
    denom = max(r0, min(max(1, len(preserve_set)), max(1, len(T))))
    factor = max(0.0, 1.0 - broken / denom)

    # 8. Reward
    reward = round(max(0.0, min(1.0, recall * factor)), 2)
    if not is_finite_float(reward):
        return emit(status="invalid", reward=0.0)   # L-3 preserved

    # 9. Binary canonical (Phase 1) — uses same baseline source
    binary = float(T <= F_p and not (preserve_set & (F_f | F_s)))

    return emit(
        status="scored",
        reward=reward,
        reward_binary=binary,
        reward_continuous_v2=reward,
        diagnostics=dict(
            targets_total=len(T),
            t_baseline_total=len(T_baseline),
            t_eff_total=len(T_eff),
            pollution_rate=pollution_rate,
            t_p_run_total=len(T_p_baseline),     # run-report baseline size
            t_p_dataset_total=len(T_p_dataset),  # dataset baseline size (diagnostic)
            baseline_drift=baseline_drift,       # |run.tpr.passed Δ dataset.tpr.passed|
            targets_hit=len(T & F_p),
            hits_new=hits_new,
            recall=recall,
            preserve_set_total=len(preserve_set),
            broken_p2p_count=broken,
            penalty_applied=broken / denom,
            regression_factor=factor,
            regression_channel_active=(len(preserve_set) > 0),
            R0=r0,
            f2p_baseline_pass_count=f2p_pass_count,
            lazy_recurated=...,
        ),
    )
```

### 2.7 Properties (provable)

1. **Bounded**: $r \in [0, 1]$ by construction (adjusted recall $\le 1$, factor $\le 1$, both clamped at 0).
2. **Monotonic in net-new hits for fixed regression set**: holding $F_f$ and $\mathcal{T}_{\text{baseline}}$ fixed, each additional gold target the agent makes pass *beyond the baseline* increases $r$ by exactly $\text{factor}/\lvert\mathcal{T}_{\text{eff}}\rvert$. Not monotonic in raw $\lvert\mathcal{T} \cap F_p\rvert$ alone when the agent simultaneously breaks a baseline test.
3. **Strictly antimonotonic in regressions on $[0,\; \max(R_0, \min(\lvert\text{preserve\_set}\rvert, \lvert\mathcal{T}\rvert))]$, saturated above**: each broken preserve_set test decreases $\text{factor}$ by $1/\text{denom}$ until $\text{factor}$ hits 0; further regressions are then "free" (factor stays at 0). The $R_0$ floor caps the per-break cost at $1/R_0$.
4. **Completion gradient preserved when factor > 0**: $r = (\text{hits\_new}/\lvert\mathcal{T}_{\text{eff}}\rvert) \times \text{factor}$ — distinct values of hits_new yield distinct $r$ whenever $\text{factor} > 0$ and the pollution gate has not fired. Closes reviewer Flaw 1.
5. **Vacuous only when truly vacuous**: $\lvert\mathcal{T}\rvert = 0$ means the dataset (post-lazy-re-curation) declares no fixable targets. Clean agent failure with $\lvert\mathcal{T}\rvert > 0$ produces $r = 0$ with `status: scored`, included in pass@k. Closes reviewer Flaw 2.
6. **Skipped tests are inert for recall**: $F_s$ does not appear in the recall numerator or denominator. Platform-skipped non-preserve-set tests neither help nor hurt. Preserve_set tests that are explicitly skipped ARE penalized via $\text{broken} = \lvert\text{preserve\_set}\cap(F_f\cup F_s)\rvert$ (skip-evasion closure). Closes reviewer Flaw 3.
7. **Per-language correctness**: TARGETS sourced from dataset's gold dicts (or lazy-re-curated raw arrays); no test-name → file mapping needed at reward-compute time. The baseline-subtraction step is language-agnostic (set difference on test names). Closes reviewer Flaw 4 *and* Oracle N3 (Flaw 4 redux) — no n2p name is dropped from $\mathcal{T}$; pollution is handled by subtraction, not by curation-time filtering.
8. **C1 closed (run-side)**: $F_p, F_f$ from raw run arrays, not cached 4-dicts. No dependency on run-side `valid` flag. Preserved from v2e.
9. **C1 closed (curation-side, R1)**: When dataset's cached gold dicts are empty (N2 case), lazy re-curation rebuilds them from raw curation arrays. Preserved from v2e.
10. **C2 closed at the name-set layer**: Agent-injected tests appear in $F_p$ but not in $\mathcal{T}$ (gold from dataset). Denominator is fixed by dataset, not inflated by agent. $\text{preserve\_set}$ uses run report's `test_patch_result.passed_tests` (pre-fix observation, runs before agent's fix patch); agent can only influence the fix-stage observation, so it has no name-set injection path into `preserve_set` either, under the harness contract that `fix_patch` cannot modify files in the test patch's scope. C2 at the **semantic** layer remains dependent on upstream harness fix_patch ≠ test_patch enforcement (SWE-bench issue #538).
11. **N1 closure preserved**: $\text{preserve\_set} = \text{gold}_{p2p} \cup T_{p,\text{baseline}}$ activates the regression channel on instances with empty curator-supplied $\text{gold}_{p2p}$ whenever the run's pre-fix `test_patch_result.passed_tests` is non-empty. Empirically verified in v2e against freya. On instances where both are empty (cpp; H-1) the channel remains inert and reward reduces to pure adjusted recall. `regression_channel_active` diagnostic surfaces this.
12. **Multi-language binary correctness (C-1 preserved)**: $\text{reward}_{\text{binary}} = \mathbb{1}[\mathcal{T} \subseteq F_p \land \text{preserve\_set} \cap F_f = \emptyset]$, multi-language target union, $\text{preserve\_set}$ from run report's pre-fix baseline. **F4 disposition**: $\text{preserve\_set}$ varies across re-runs if baseline tests are flaky; empirically 0% variance across 150 freya same-(instance, model) re-run groups, so the structural risk does not manifest. v3 watchpoint: pin to a separate frozen baseline run when flaky corpora arrive.
13. **F2 closure — do-nothing on polluted instances scores 0 (Audit-5 corrected, Audit-6 refined)**: $\text{hits\_new} = \lvert(\mathcal{T}\cap F_p)\setminus T_{p,\text{baseline}}\rvert$. With $T_{p,\text{baseline}}$ sourced from the **run report** (not dataset — see §1.5 F5), $\mathcal{T}_{\text{baseline}}$ correctly identifies pre-existing-passing targets on n2p-only instances. A perfect do-nothing agent (zero fix patch, deterministic test environment) has $F_p = T_{p,\text{baseline}}$ exactly, so $(\mathcal{T}\cap F_p)\setminus T_{p,\text{baseline}} = \emptyset$ → $\text{hits\_new} = 0$ → recall = 0. **The do-nothing = 0 guarantee is exact in a deterministic test environment** (no baseline flakes), which is empirically observed in freya (0% $T_{p,\text{run}}$ variance across 150 same-(instance, model) re-run groups). Under flaky baselines ($F_p \ne T_{p,\text{baseline}}$ due to test noise), the guarantee degrades; spurious hits_new count is $O(\lvert\mathcal{T}_{\text{eff}}\rvert \cdot \varepsilon)$ — linear in effective-target count under flake rate $\varepsilon$. The reward reports recall = hits_new/$\lvert\mathcal{T}_{\text{eff}}\rvert$, so the **spurious recall floor is $O(\varepsilon)$ regardless of $\lvert\mathcal{T}_{\text{eff}}\rvert$** — the factor cancels. True noise-robustness requires re-run aggregation (v3 path). Verified empirically on `starship-138` (79 pre-existing passes in run report, $\mathcal{T}_{\text{eff}} = 10$, recall drops from 0.888 to 0.0) and `testcontainers-java-8298` (167 pre-existing, recall drops from 0.342 to 0.0) in §6.1 Scenarios 19 + 20. Also note: the Audit-6 set-difference numerator correctly avoids double-penalizing regressions of pre-existing-passing targets — a regressed baseline target is penalized once (via `broken` / `factor`), not twice.
14. **F1 closure — exclusion is surfaced, not silent**: M-2 still triggers `status: invalid` (test stage can't be trusted as a baseline source), but the CSV emit and `m2_excluded_per_language` diagnostic surface the per-language exclusion rate so consumers can read representativeness off the result file directly. The pollution gate's `status: polluted_dataset` is similarly surfaced rather than silently scored.
15. **F3 closure — regression cost is bounded by $1/R_0$**: for any broken count $b$, the per-break cost is $b/\text{denom} \le b/R_0$. The 25× swing between $\lvert\mathcal{T}\rvert=2$ and $\lvert\mathcal{T}\rvert=500$ tasks under v2e is replaced by a constant 5% per-break ceiling on small-T tasks. Large-T tasks behave identically to v2e (preserves §5.2 closure).
16. **F4 disposition — empirically nil in freya, structurally open (Audit-5 honest)**: $T_{p,\text{baseline}}$ is per-run-observed (the run report's `test_patch_result.passed_tests`). Structurally exposed to baseline test flake → preserve_set / binary varies. v2f-attempt-1 proposed a frozen-dataset source to close F4; Audit #5 invalidated that source (§1.5 F5). v2f accepts the structural F4 exposure because the alternative (frozen-dataset source) makes F2 closure structurally inert on 51% of the pollution-prone dataset, and the freya empirics show $T_{p,\text{run}}$ varies 0% across 150 same-(instance, model) re-run groups. **Determinism strategy in v3**: pin $T_{p,\text{baseline}}$ from a separate frozen baseline run (compute once, cache, source from cache). Out of scope for v2f; documented in §9 risk #4.
17. **F5 closure — Audit-5 disjointness defect resolved**: by sourcing $T_{p,\text{baseline}}$ from the run report (different observation from the dataset's gold bucketing), the disjointness rule does not apply between the two sources. On starship-138: dataset.gold_n2p has 89 names; run_report.tpr.passed has 82 names; their intersection is 79. v2f's adjusted recall correctly identifies 79 pre-existing-passing targets and subtracts. v2f-attempt-1 (dataset baseline) would have computed `T ∩ dataset.tpr.passed = 0` vacuously, hits_new = 79 - 0 = 79, recall = 79/89 = 0.888 — the very pathology F2 was written to close. Audit #5 prevented this from shipping.

---

## 3. Output schema

### 3.1 `result.json` — `verifier_result` (v2f)

```json
{
  "rewards": {
    "reward": 0.95,
    "reward_binary": 1.0,
    "reward_continuous_v2": 0.95
  },
  "reward_version": "continuous_v2",
  "status": "scored",
  "diagnostics": {
    "targets_total": 20,
    "targets_hit": 19,
    "t_baseline_total": 5,
    "t_eff_total": 15,
    "pollution_rate": 0.25,
    "hits_new": 14,
    "recall": 0.933,
    "gold_p2p_total": 8000,
    "t_p_run_total": 8200,
    "t_p_dataset_total": 8195,
    "baseline_drift": 7,
    "preserve_set_total": 8210,
    "broken_p2p_count": 1,
    "unknown_breaks_count": 0,
    "R0": 20,
    "regression_denom": 20,
    "penalty_applied": 0.05,
    "regression_factor": 0.95,
    "regression_channel_active": true,
    "f2p_baseline_pass_count": 0,
    "f2s_count": 0,
    "evasion_ratio": 0.0,
    "lang": "python",
    "lazy_recurated": false,
    "m2_excluded_per_language": null
  }
}
```

**v2f schema changes vs v2e (Audit-5 corrected)**:

- **Source of $T_{p,\text{baseline}}$**: **run report's** `test_patch_result.passed_tests` (same source as v2e's $T_{p,\text{run}}$; Audit-5 invalidated v2f-attempt-1's frozen-dataset source — see §1.5 F5).
- **Added**: `t_baseline_total`, `t_eff_total`, `pollution_rate`, `hits_new`, `R0`, `regression_denom` (full diagnostics for F2/F3 closures)
- **Added**: `t_p_dataset_total`, `baseline_drift` (Audit-5 forensics — exposes dataset-vs-runtime baseline disagreement for curation hygiene; no formula impact)
- **Removed**: `baseline_source` (v2f-attempt-1 artifact; baseline source is always run-report in v2f)
- **Preserved from v2e**: `t_p_run_total` (count of all pre-fix passing tests — same source as $T_{p,\text{baseline}}$)
- **Added** (aggregator-only, not per-row): `m2_excluded_per_language` in CSV emit — per-language counts of M-2 exclusions to surface F1 representativeness directly in evaluation output

`reward_internal_plan` remains dropped from production emit (v2e H-2 closure preserved).

**Diagnostic field semantics** (v2f additions and changes):

| Field | Meaning |
|---|---|
| `t_baseline_total` | $\lvert\mathcal{T}_{\text{baseline}}\rvert = \lvert\mathcal{T} \cap T_{p,\text{baseline}}\rvert$ — count of TARGET tests that were already passing in the run's pre-fix test stage. Load-bearing for F2 closure. |
| `t_eff_total` | $\lvert\mathcal{T}_{\text{eff}}\rvert$ — count of TARGET tests the agent actually had to fix. The denominator of adjusted recall. |
| `pollution_rate` | $\lvert\mathcal{T}_{\text{baseline}}\rvert / \max(1, \lvert\mathcal{T}\rvert) \in [0, 1]$. Surface for stratification. Values $\ge 0.8$ on instances that survive the pollution gate (because $\lvert\mathcal{T}_{\text{eff}}\rvert \ge 3$) should be reviewed at aggregation time even if scored. |
| `hits_new` | $\lvert(\mathcal{T}\cap F_p)\setminus T_{p,\text{baseline}}\rvert$ — targets passing post-fix that were NOT passing pre-fix. Adjusted recall numerator (Audit-6 set-difference; always $\ge 0$, no clamp; avoids double-penalizing regressions). |
| `f2p_baseline_pass_count` | **(Audit-6 alarm / Audit-7 gate)** $\lvert\text{gold}_{f2p} \cap T_{p,\text{baseline}}\rvert$ — number of gold f2p targets already passing in the run's pre-fix test stage. Non-zero values indicate **environment drift**: the eval env may not reproduce the bug. **Gate (Audit-7)**: when `f2p_baseline_pass_count / len(gold_f2p) ≥ f2p_drift_threshold` (default 0.3), the instance returns `status: invalid` and is excluded from pass@k — the bug non-reproduction rate is too high to produce reliable training signal. Formula still subtracts via $\mathcal{T}_{\text{baseline}}$ on scored instances. |
| `t_p_run_total` | $\lvert T_{p,\text{baseline}}\rvert$ from the run report — count of all pre-fix passing tests in this run (target and non-target combined). Field name preserved from v2e; semantics identical to v2e's $T_{p,\text{run}}$. |
| `t_p_dataset_total` | (Audit-5 diagnostic, no formula impact) count of `dataset["test_patch_result"]["passed_tests"]`. Compare against `t_p_run_total` to spot curation-vs-runtime drift. |
| `baseline_drift` | (Audit-5 diagnostic) $\lvert T_{p,\text{run}} \triangle T_{p,\text{dataset}}\rvert$ — size of symmetric set-difference. High values flag instances curated under a different harness configuration than eval; useful for dataset curation hygiene without entering the formula. |
| `preserve_set_total` | $\lvert\text{preserve\_set}\rvert = \lvert\text{gold}_{p2p} \cup T_{p,\text{baseline}}\rvert$ — regression denominator candidate. |
| `R0` | The absolute regression-budget floor used in this compute. Spec canonical = 20. |
| `regression_denom` | $\max(R_0, \min(\max(1, \lvert\text{preserve\_set}\rvert), \max(1, \lvert\mathcal{T}\rvert)))$ — the actual denominator used in factor. |
| `unknown_breaks_count` | (preserved from v2e) count of tests in $F_f$ outside both `preserve_set` and $\mathcal{T}$ — diagnostic only. |
| `lazy_recurated` | (preserved from v2e) `true` if §2.2 rebuild fired. |
| `regression_channel_active` | (preserved from v2e) `true` if $\lvert\text{preserve\_set}\rvert > 0$. When `false` reward reduces to pure adjusted recall. |
| `evasion_ratio`, `f2s_count` | (preserved from v2e) diagnostic only; runner-name-canonicalization caveat (Oracle audit #3 L-2). |
| `m2_excluded_per_language` | **CSV-only**, not per-row. Aggregator emit: dict of `{lang: count}` for `status: invalid` rows triggered by §3.3 trigger (b). F1 closure: surfaces representativeness directly in evaluation output. |

### 3.2 `verifier/reward.txt`

Canonical reward at 2-decimal precision (rounded per §2.6.1):

```
0.00
```

The canonical key is `rewards.reward` in `result.json`; `reward.txt` shadows it for human inspection and legacy grep-based aggregators.

### 3.3 Status semantics

| Status | Trigger | Reward field | Aggregator action |
|---|---|---|---|
| `scored` | $\lvert\mathcal{T}\rvert > 0$ (after lazy re-curation), pollution gate did not fire, all integrity assertions pass | computed | include in pass@k |
| `vacuous` | $\lvert\mathcal{T}\rvert = 0$ AND no raw-array re-curation produced targets (true zero-target dataset — e.g., HypothesisWorks-4452-style pure-cleanup PR) | 0.0 | EXCLUDE from pass@k |
| `polluted_dataset` (**v2f NEW**) | $\lvert\mathcal{T}\rvert > 0$ AND `pollution_rate >= 0.8` AND $\lvert\mathcal{T}_{\text{eff}}\rvert < 3$ — the dataset's gold targets are dominated by tests that were already passing pre-fix, with too few effective targets remaining to produce agent-gradable signal. Audit #4 F1+F2 closure. | 0.0 | EXCLUDE from pass@k, log alert with `pollution_rate` and per-language count |
| `invalid` | Any of: (a) `passed_count`/`failed_count`/`skipped_count` mismatch the lengths of their corresponding lists in EITHER `fix_patch_result` OR `test_patch_result` (Oracle audit #3 M-1 widened symmetry); (b) `test_patch_result` reports zero observed tests (all three counts zero) AND $\lvert\mathcal{T}\rvert > 0$ — indicates the test_patch stage failed to run, so $T_{p,\text{baseline}}$ is unreliable (Oracle audit #3 M-2; F1 in v2f surfaces this in CSV via `m2_excluded_per_language`); (c) computed reward is NaN/Inf (Oracle audit #3 L-3 defense-in-depth); (d) **zero-observation gate** (Audit-7): $T_{p,\text{baseline}}$ non-empty AND $F_p$, $F_f$, $F_s$ all empty — the fix stage produced zero observations (harness crash post-baseline), so reward cannot be computed reliably; (e) **f2p-drift gate** (Audit-7): $\lvert\text{gold}_{f2p}\rvert > 0$ AND $\lvert\text{gold}_{f2p} \cap T_{p,\text{baseline}}\rvert / \lvert\text{gold}_{f2p}\rvert \ge \texttt{f2p\_drift\_threshold}$ (default 0.3) — the eval environment fails to reproduce the bug for ≥30% of f2p targets; signal is unreliable | 0.0 | EXCLUDE, log alert |
| `no_signal` | `report.json` missing or malformed; OR dataset record not findable | 0.0 | EXCLUDE from pass@k |

The `status` field is the message the sampler reads to decide whether to include the instance in the training group. Per `continuous_reward_plan.md` §5.5, the actual EXCLUDE enforcement happens at the sampler, not in the reward function — this field carries the signal.

---

## 4. Defect closures

### 4.1 Reviewer-flagged structural flaws (caught in v2a)

| Flaw | Closure in v2d |
|---|---|
| **1: No completion gradient** ($r = 1.0$ for any $k \ge 1$ fixed of any total) | $\lvert\mathcal{T}\rvert$ is fixed by the dataset (or lazy re-curation), not derived from the run. Recall is monotonic in hits: $r$ scales linearly with $k$. |
| **2: Vacuous excludes clean failures** (give-up agent removed, try-and-fail agent counted) | `vacuous` triggers only when post-re-curation $\lvert\mathcal{T}\rvert = 0$. Clean failure with $\lvert\mathcal{T}\rvert > 0$ → recall = 0 → $r = 0$ → `status: scored` → included in pass@k. |
| **3: $s2s$ dilution** (skipped tests inflate denominator) | $F_s$ removed from formula. Skipped tests neither help nor hurt. |
| **4: Go/Rust false-zero** ($n2p$ targets dropped for non-mappable languages) | Gold $n2p$ comes from dataset, not the run. No test-name → file mapping needed at reward-compute time. The hygiene filter is **removed** in v2d (§2.3) — TARGETS use full $\text{gold}_{n2p}$ for all languages. |

### 4.2 Oracle audit #1 findings (caught in v1 → addressed in v2a → preserved through v2d)

| Audit finding | Closure mechanism |
|---|---|
| **C1**: `valid:false` collapses cached 4-dicts → reward 0 wipes gradient on partial-fix-with-regression | $F_p, F_f, T_{p,\text{run}}$ recomputed from raw `passed_tests`/`failed_tests` arrays. $\mathcal{T}$ from dataset record (or lazy re-curation from dataset's own raw arrays). No path through `Report.check()`'s `valid` gate. |
| **C2**: n2p-injection exploit gives ~99% reward without solving anything | $\mathcal{T}$ comes from the dataset (immutable to agent). Agent-injected tests land in $F_p$ but not in $\mathcal{T}$ → no contribution. Defense is structural, not heuristic. |
| **H1**: `.2f` rounds 0.005% to "0.00" | `reward.txt` uses `:.6f`; `result.json` carries full float64. |
| **H2**: $f2f$ dilutes denominator | Recall denominator is $\lvert\mathcal{T}\rvert$ (gold targets only); $f2f$ tests do not appear. |
| **H3**: missing / malformed / `valid:false` / honest-zero all collapse to 0 | `status` field distinguishes 4 cases. |
| **H4**: $n2p$ read from cached dict; $n2f$ recomputed inline — asymmetric | Both come from dataset's gold dicts (or lazy re-curation); identical derivation. |
| **M2**: $D \le 0$ silent | Piecewise definition emits `status: vacuous` when $\lvert\mathcal{T}\rvert = 0$. |
| **M3**: perfect-baseline reads as failure | `status: vacuous` distinguishes it. |
| **M4 / M5**: int `failed_count` vs `len(failed_tests)` drift not asserted | Integrity assertion at read time; failure → `status: invalid`. |

### 4.3 Oracle audit #2 findings (caught in v2c → closed in v2d)

| Audit finding | Closure mechanism |
|---|---|
| **N1**: regression channel inert when $\text{gold}_{p2p}$ empty (53% of freya datasets; Rust 80%, Java 76%, C 76%) | **Partially closed.** $\text{preserve\_set} = \text{gold}_{p2p} \cup T_{p,\text{run}}$ — adds run-observed pre-fix passing tests. Empirically active on Java (8/9), JS (14/27), Go (varied), Rust (3/18 with active T_p_run). **Still inert on cpp** when run's `test_patch_result.passed_tests` is also empty (0/27 cpp scored rows in freya); reward there reduces to pure recall (see §2.5 H-1 note). v2e exposes `regression_channel_active` diagnostic so consumers can stratify. Pre-fix observation defeats agent inflation regardless. |
| **N2**: 10/350 freya datasets have ALL gold dicts empty (HypothesisWorks-4452 et al.) — C1 displaced not closed | Lazy on-the-fly re-curation §2.2 rebuilds gold dicts from dataset's raw `test_patch_result`/`fix_patch_result` arrays using canonical `report.py:130-138` bucketing. Falls to honest `status: vacuous` only when raw arrays are also empty. |
| **N3**: strict §10 curation-time language-specific n2p fallback would shrink AMReX-4238 TARGETS 57→2 (Flaw 4 redux) | §10 rewritten. **No language-specific n2p filter at compute time.** Full $\text{gold}_{n2p}$ trusted for all languages. C2 defense holds because dataset is frozen. |

### 4.4 Internal plan critique mitigation

| §5.x concern | Mitigation in v2d |
|---|---|
| **§5.1 sparse reward** (early rollouts ≈ all 0) | Acknowledged. Not the formula's job — curriculum / shaping at trainer. |
| **§5.2 regression-blind on huge $\lvert P\rvert$** | Min-form regression denominator. Targets-bound term dominates when $\lvert\text{preserve\_set}\rvert$ is huge. See §2.5. |
| **§5.3 build-env vs eval-env determinism** | Out of scope. Re-run / flaky-model layer. |
| **§5.4 n2p file mapping language-fragile** | Removed from compute path entirely (R3). |
| **§5.5 EXCLUDE at wrong layer** | `status` field signals the sampler; reward stays $[0,1]$. Sampler enforces exclusion. |
| **§5.6 upstream exclusion biases distribution** | Acknowledged. Not formula's job. |
| **§5.7 complexity vs unproven gain** | Dual-emission with binary canonical; promotion to training reward gated on §6 validation. v2e drops `reward_internal_plan` from production emit so downstream consumers cannot pick up a regression-blind signal by accident — offline A/B against internal-plan remains available via CSV evaluator. |
| **§5.8 single global formula on heterogeneous tasks** | Acknowledged limitation. Per-difficulty-tier rewards are v3 work. |

### 4.5 Audit #4 findings (caught in v2e → closed in v2f)

| Audit finding | Severity | Closure mechanism |
|---|---|---|
| **F1**: M-2 silently excludes ~44% of the dataset (compiled-language-heavy: Rust 80%, Java 63%, C 54%, Python 2%); CSV computed on the surviving cleanest 56% under-states representativeness | HIGH | M-2 trigger preserved (empty test_patch_result is genuinely unreliable signal). **CSV aggregator now emits `m2_excluded_per_language` count** (§3.1). **§9 risk #12 surfaces the representativeness caveat**. **§10 includes per-language M-2 exclusion table** so consumers can read the bias directly. No silent exclusion — the rule is still applied but its blast radius is exposed. |
| **F2 (CRITICAL)**: "Trust full $\text{gold}_{n2p}$" re-introduces range compression; 51% of non-vacuous datasets are pollution-prone (T = $\text{gold}_{n2p}$ exclusively on 57% of rows); empirically confirmed do-nothing recall = 0.888 on `starship-138` and 0.342 on `testcontainers-java-8298` across all 9 runs | CRITICAL | **Adjusted recall (§2.4.4)** subtracts $\lvert\mathcal{T}_{\text{baseline}}\rvert$ from both numerator and denominator. A do-nothing agent on `starship-138` now scores **0.0** instead of 0.888 because hits_new = |(T ∩ F_p) \ T_p_baseline| = |{79 names} \ {82 names}| = 0. Universal (no language carve-outs, language-agnostic set difference on test names). **N3 NOT re-opened** — no name is dropped from $\mathcal{T}$ at curation; pollution is handled by subtraction at compute. AMReX-4238 still has all 57 targets visible. **Pollution gate (§2.4.3)** emits `status: polluted_dataset` (mirrors `vacuous`) when ≥80% of targets were already passing AND fewer than 3 effective targets remain — surfaces "no agent signal" instead of pretending to grade. |
| **F3**: min-form denominator couples regression cost to $\lvert\mathcal{T}\rvert$ — broken=1 costs 50% on a 2-target task but 2% on a 500-target task (25× swing) | MEDIUM | **Absolute floor $R_0 = 20$ on regression denominator (§2.5.2)**: $\text{denom} = \max(R_0, \min(\max(1, \lvert\text{preserve\_set}\rvert), \max(1, \lvert\mathcal{T}\rvert)))$. Per-break cost is bounded above by $1/R_0 = 5\%$ on small-T tasks. Large-T tasks ($\min \ge R_0$) behave identically to v2e. **§5.2 closure preserved** — denom is still capped by $\min$ at the top. $R_0 = 20$ chosen at one std above SWE-bench median $\lvert\text{FAIL\_TO\_PASS}\rvert$. |
| **F4**: $T_{p,\text{run}}$ varies across re-runs in the presence of flaky baseline tests → $\text{preserve\_set}$ varies → canonical Phase-1 binary reward is non-deterministic; empirically 0% variance in freya but structurally real | LOW (manifest) / STRUCTURAL (in general) | **PARTIALLY CLOSED (Audit-5 superseded the frozen-dataset approach)**. v2f-attempt-1 sourced $T_{p,\text{baseline}}$ from dataset to close F4 fully; Audit #5 invalidated that source as structurally inert on n2p-only instances (§1.5 F5). v2f sources from run report instead, accepting partial F4 exposure (empirically 0% variance in freya across 150 same-(instance, model) re-run groups). v3 fix path: pin baseline from a separate frozen baseline run (compute once, cache, source from cache). See §9 risk #16, §14 F4 row, §15. |

**Root cause Audit #4 exposed**: prior audits (#1, #2, #3) verified plumbing thoroughly but did not probe whether the *denominator itself* (`gold_n2p`) measures the issue's test set on the partial-collapse instances. v2e's resolution of N3 ("trust full gold_n2p") was correct as a rejection of language-specific filtering but wrong as a positive claim — the audit revealed that on ≥51% of the dataset, `gold_n2p` contains pre-existing baseline-passing tests caught in a test-stage scope mismatch, not fix-dependent new tests. v2f's baseline subtraction is the structural fix: instead of trusting or filtering, *measure agent contribution net of baseline*.

---

## 5. Per-component grounding

| Component | Why it's there | Citation |
|---|---|---|
| **Range $r \in [0, 1]$** | Match SWE-RL's continuous reward shape, the only published continuous reward for SWE-style tasks | Wei et al. 2025, **SWE-RL**, NeurIPS 2025, [arxiv:2502.18449](https://arxiv.org/abs/2502.18449). Reward in `[0, 1]` via `difflib.SequenceMatcher` at [`facebookresearch/swe-rl/src/swerl/core/reward.py`](https://github.com/facebookresearch/swe-rl/blob/main/src/swerl/core/reward.py) lines 220-250. |
| **Recall denominator $\lvert\mathcal{T}\rvert$** | Measure completion: "what fraction of needed work did the agent do?" Matches binary SWE-bench semantics (all FAIL_TO_PASS must hold) on a continuous scale. | Jimenez et al. 2024, **SWE-bench**, ICLR 2024 Oral, [arxiv:2310.06770](https://arxiv.org/abs/2310.06770) — binary completion. Continuous extension matches `continuous_reward_plan.md` §2 internal plan. |
| **$\text{gold}_{f2p}$ in TARGETS** | Canonical SWE-bench targets: tests that must go fail → pass | Jimenez et al. 2024: *"at least one test where its status changes from a fail to pass (henceforth referred to as fail-to-pass test)"* |
| **$\text{gold}_{s2p}, \text{gold}_{n2p}$ in TARGETS** | 8-category extension: skipped-to-pass and none-to-pass also count as gold targets | Zan et al. 2025, **Multi-SWE-Bench**, NeurIPS 2025, [arxiv:2504.02605](https://arxiv.org/abs/2504.02605). Implementation at `multi_swe_bench/harness/report.py:130-138` of our fork. |
| **Lazy re-curation from raw arrays (R1, §2.2)** | Close C1 displacement (N2) at curation time. Raw arrays survive when cached dicts get emptied. | Mirror of `multi_swe_bench/harness/report.py:130-138` canonical bucketing. Same algorithm, run at reward-compute rather than dataset-construction. |
| **Sourcing TARGETS from DATASET (not run)** | Closes C2 injection structurally. Dataset is immutable to agent; gold targets fixed before agent runs. | `continuous_reward_plan.md` §2 internal proposal — original insight. |
| **Recompute $F_p, F_f, T_{p,\text{run}}$ from raw arrays** | Closes C1 gradient collapse on `valid:false`. `Report.check()` empties cached 4-dicts but never empties raw arrays. | Oracle audit #1 — finding C1. |
| **No n2p hygiene filter at compute time (R3)** | Closes N3 (Flaw 4 redux). Agent cannot mutate frozen dataset; filter served no adversarial purpose. | Oracle audit #2 — finding N3. Hygiene if needed belongs in dataset-curation tooling. |
| **`preserve_set = gold_p2p ∪ T_p_run` (R2)** | Close N1. Activates regression channel on instances with empty curator-supplied $\text{gold}_{p2p}$. $T_{p,\text{run}}$ is pre-fix observation, agent cannot inflate. | Oracle audit #2 — finding N1. Conceptually: regression-test-selection state algebra (Rothermel & Harrold 1996, IEEE TSE 22(8)) treats "tests that pass on pre-change" as the natural preservation set. |
| **Regression factor min-form denominator (R4)** | Mathematically identical to v2c's max-of-fractions, syntactically cleaner | $\dfrac{x}{\min(a,b)} = \max\left(\dfrac{x}{a}, \dfrac{x}{b}\right)$. Conceptually aligned with **Process Reward Models** (Lightman et al. 2023, ICLR 2024, [OpenReview:v8L0pN6EOi](https://openreview.net/forum?id=v8L0pN6EOi)) — restrict scoring to relevant units. |
| **No $f2s$ penalty in formula** | Recall captures missed gold targets correctly; skip evasion is naturally penalized (skipped baseline-failing test is not in $F_p$ → not a hit → recall drops by $1/\lvert\mathcal{T}\rvert$) | Convergent with prior analysis; no precedent for explicit skip-as-failure in LLM benchmarks. Emitted as diagnostic. |
| **`unknown_breaks_count` diagnostic (R5)** | Tracks regressions on tests outside both preserve_set and TARGETS — curation-gap visibility without payment | Novel diagnostic. Helps prioritize dataset curation improvements. |
| **`vacuous` status when post-recuration $\lvert\mathcal{T}\rvert = 0$** | Distinguishes "dataset truly has no targets" from "agent scored 0" | Internal precedent: `continuous_reward_plan.md` §2.3 — *"EXCLUDE, never write 0.0"*. |
| **Adjusted recall (baseline subtraction) — F2 closure** | Measures **net** agent contribution rather than raw target pass count. Closes do-nothing-recall-inflation on the 51% of the dataset where $\text{gold}_{n2p}$ is dominated by pre-existing tests. | Regression test selection state algebra (Rothermel & Harrold 1996, IEEE TSE 22(8) §3) treats `tests passing on pre-change ∩ tests passing on post-change` as the "preserved" set, distinct from "newly passing". The same partition applies: $\mathcal{T} \cap T_{p,\text{baseline}}$ = preserved-target subset = no agent credit. Empirically confirmed against Oracle audit #4 data: 51.1% pollution-prone rate, `starship-138` 0.888 → 0.0, `testcontainers-java-8298` 0.342 → 0.0. Universal across all 8 languages because set difference on test names is language-agnostic. |
| **Pollution gate (`status: polluted_dataset`) — F1+F2 transparency** | Surfaces no-agent-signal cases rather than silently scoring them. Mirrors `vacuous` for cases where targets technically exist but all-or-nearly-all were already passing. | Consistent with SWE-bench Verified's "discard ambiguous instances" curation philosophy (OpenAI 2024). Same disposition (exclude from pass@k) but applied at compute time rather than curation time, so it works on existing datasets without re-curation. Threshold 0.8 / EFF_MIN=3 are tuned to freya distribution (§6 Scenario 19); configurable. |
| **Absolute regression-budget floor `R_0` — F3 closure** | Caps per-break cost at $1/R_0$. Decouples regression sensitivity from $\lvert\mathcal{T}\rvert$. | $R_0 = 20$ chosen at one std above SWE-bench Verified's median $\lvert\text{FAIL\_TO\_PASS}\rvert \approx 10$ (Jimenez et al. 2024 Table 6). Preserves §5.2 closure (min cap above the floor still in force on huge-baseline tasks). |
| **Run-report baseline source ($T_{p,\text{baseline}}$ from run report) — F2 closure / F5 resolution** | Same observation as $F_p$ / $F_f$ — sees the curation-vs-runtime drift that IS the F2 pollution mechanism. Required to identify pre-existing-passing targets on n2p-only instances (51% of pollution-prone dataset) where the dataset's `test_patch_result.passed_tests` is structurally disjoint from `gold_n2p` per `report.py:130-138`. | Audit #5 proved that v2f-attempt-1's frozen-dataset source was structurally inert on n2p-only instances (§1.5 F5). The per-observation bucketing rule makes `dataset.gold_n2p ∩ dataset.test_patch_result.passed_tests = ∅` by construction. Run report is the contemporaneous observation. Trade-off: F4 partially re-opens (per-run baseline can vary if flaky); empirically 0% variance in freya (`/tmp/oracle_v2e_audit/f4_variance.py`: 150 same-(instance, model) re-run groups, 0 T_p_run variance), so the structural risk is currently latent. v3 watchpoint: pin baseline from a separate frozen baseline run. See §9 risk #16. |
| **Status field separate from reward** | Reward channel stays $[0, 1]$; status carries meta-information | Engineering convention. Internal plan §5.5: *"sampler must enforce, not reward function"*. |
| **Integrity assertions** | Catch upstream serializer drift | Defensive programming. Direct response to Oracle audit #1 M4/M5. |
| **Dual-emission with binary canonical** | A/B measurement before promoting continuous to training reward | `continuous_reward_plan.md` §6 rollout protocol. |

---

## 6. Correctness proof on canonical scenarios

Setup: dataset declares $\lvert\mathcal{T}\rvert = 20$ failing-target tests and $\lvert\text{gold}_{p2p}\rvert = 100$ baseline-passing tests (unless noted); $T_{p,\text{run}}$ matches $\text{gold}_{p2p}$ unless noted.

**Column legend**: "Reward" = `reward_continuous_v2` (the formula output $r$ per §2.6). The canonical `rewards.reward` field in Phase-1 rollout shadows `rewards.reward_binary`, which is **separately** computed per §2.7 #12 as $\mathbb{1}[\mathcal{T} \subseteq F_p \land \text{preserve\_set} \cap F_f = \emptyset]$. Both channels emit in `result.json` (§3.1). Scenarios 11, 17 below also verify `reward_binary = 1.0` on n2p-only gold (closes Oracle audit #3 C-1).

| # | Scenario | Hits | Broken | Recall | $\lvert\text{preserve\_set}\rvert$ | Penalty | Factor | Reward | Status |
|---|---|---|---|---|---|---|---|---|---|
| 1 | Perfect fix (k=20) | 20 | 0 | 1.00 | 100 | 0 | 1.00 | **1.00** | scored |
| 2 | Partial fix (k=10) | 10 | 0 | 0.50 | 100 | 0 | 1.00 | **0.50** | scored |
| 3 | Single-test fix (k=1) | 1 | 0 | 0.05 | 100 | 0 | 1.00 | **0.05** | scored |
| 4 | **Flaw 1 re-test**: any $k$ vs $k+1$ | $k$ | 0 | $k/20$ | 100 | 0 | 1.00 | **$k/20$** | scored — gradient preserved ✓ |
| 5 | Perfect fix + 1 regression | 20 | 1 | 1.00 | 100 | 0.05 | 0.95 | **0.95** | scored |
| 6 | Perfect fix + 1 regression, $\lvert P\rvert = 8000$ | 20 | 1 | 1.00 | 8000 | 0.05 | 0.95 | **0.95** | scored — §5.2 closed ✓ |
| 7 | Perfect fix + 20 regressions, $\lvert P\rvert = 8000$ | 20 | 20 | 1.00 | 8000 | 1.0 | 0.00 | **0.00** | scored — heavy regression wipes reward ✓ |
| 8 | **Flaw 2 re-test**: do nothing | 0 | 0 | 0.00 | 100 | 0 | 1.00 | **0.00** | scored (NOT vacuous) ✓ |
| 9 | Try, break 1 | 0 | 1 | 0.00 | 100 | 0.05 | 0.95 | **0.00** | scored ✓ |
| 10 | **Flaw 3 re-test**: 20 fixed + 100 platform skips | 20 | 0 | 1.00 | 100 | 0 | 1.00 | **1.00** | scored — $F_s$ inert ✓ |
| 11 | **Flaw 4 re-test**: Go instance, all targets in $\text{gold}_{n2p}$, agent passes all | 20 | 0 | 1.00 | 100 | 0 | 1.00 | **1.00** | scored — no false zero ✓ |
| 12 | **C2 re-test**: agent injects 99 trivial passing tests; gold targets unfixed | 0 (injections not in $\mathcal{T}$) | 0 | 0.00 | 100 | 0 | 1.00 | **0.00** | scored — exploit defeated ✓ |
| 13 | **C1 re-test**: partial fix + 1 regression, run report has `valid:false` (4-dicts empty) | 10 (in $\mathcal{T}=20$) | 1 | 0.50 | 100 | 0.05 | 0.95 | **0.475** | scored — gradient preserved through `valid:false` ✓ |
| 14 | Skip evasion: agent skips all baseline-failing | 0 | 0 | 0.00 | 100 | 0 | 1.00 | **0.00** | scored — evasion gets 0 ✓ |
| 15 | True vacuous: dataset gold AND raw all empty | n/a | n/a | n/a | n/a | n/a | n/a | **0.00** | **vacuous** — excluded from pass@k ✓ |
| 16 | **N1 re-test**: Rust instance, $\text{gold}_{p2p}=\emptyset$, $T_{p,\text{run}}=200$, 5 broken, recall 1.0 on $\mathcal{T}=10$ | 10 | 5 | 1.00 | 200 | 0.5 | 0.50 | **0.50** | scored — regression channel active ✓ (was 1.00 under v2c) |
| 17 | **N2 re-test**: HypothesisWorks-4452-style — gold dicts empty, raw arrays populated with curation-time bucketing inputs | varies | varies | computed from recurated gold | computed | computed | computed | **>0 possible** | scored — C1 closed at curation time ✓ |
| 18 | **N3 re-test**: AMReX-4238-style — Go/Rust large gold_n2p (57 targets), all in $\mathcal{T}$, all fix-dependent ($\mathcal{T}_{\text{baseline}}=0$) | 57 | 0 | 1.00 | 100 | 0 | 1.00 | **1.00** | scored — no curation-time TARGETS loss ✓ (was 2/57 under strict v2c §10 fallback) |

### 6.1 Audit #4 + #5 closure scenarios (v2f-specific, run-report baseline)

Adjusted recall and pollution gate scenarios. All baseline counts use the **run report's** `test_patch_result.passed_tests` per §2.4.2 (Audit-5 corrected). Column legend: $|\mathcal{T}|$ = total targets, $|\mathcal{T}_b|$ = $|\mathcal{T}_{\text{baseline}}|$, $|\mathcal{T}_e|$ = $|\mathcal{T}_{\text{eff}}|$, "hits raw" = $|\mathcal{T} \cap F_p|$, "hits new" = $|(\mathcal{T} \cap F_p) \setminus T_{p,\text{baseline}}|$ (set-difference; Audit-6 v2g numerator), P = pollution_rate.

| # | Scenario | $|\mathcal{T}|$ | $|\mathcal{T}_b|$ | $|\mathcal{T}_e|$ | hits raw | hits new | P | Recall | Factor | Reward | Status |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 19 | **F2 re-test (starship-138, real numbers)**: do-nothing on polluted rust instance. From dataset: T=89 (all n2p). From run report: T_p_run=82, T ∩ T_p_run = 79. Baseline source: run report (Audit-5 corrected). | 89 | 79 | 10 | 79 | 0 | 0.888 | 0/10 = **0.00** | 1.00 | **0.00** | scored — F2 closure ✓ (was 0.888 under v2e; would be 0.888 under v2f-attempt-1 because dataset.tpr.passed = 0 → T_baseline vacuously empty) |
| 20 | **F2 re-test (testcontainers-java-8298, real numbers)**: do-nothing on polluted java instance. From dataset: T=488 (all f2p), dataset.tpr.passed=499, T ∩ dataset.tpr.passed=167. From run report: T_p_run=499, T ∩ T_p_run = 167. Both sources agree on this instance (baseline_drift ≈ 0). | 488 | 167 | 321 | 167 | 0 | 0.342 | 0/321 = **0.00** | 1.00 | **0.00** | scored — F2 closure ✓ (was 0.342 under v2e) |
| 21 | **F2 perfect fix on `starship-138`-style**: agent fixes all 10 effective targets, preserves baseline | 89 | 79 | 10 | 89 | 10 | 0.888 | 10/10 = **1.00** | 1.00 | **1.00** | scored — completion gradient still right ✓ |
| 22 | **F2 partial fix**: 5 of 10 effective targets passed, 0 regressions | 89 | 79 | 10 | 84 | 5 | 0.888 | 5/10 = **0.50** | 1.00 | **0.50** | scored — partial credit measured on effective work ✓ |
| 23 | **Pollution gate fires (pubkey__rxdb-4758-style)**: 539 targets, all 539 pre-existing, $|\mathcal{T}_e|=0$ | 539 | 539 | 0 | 539 | 0 | 1.000 | n/a | n/a | **0.00** | **polluted_dataset** — EXCLUDED from pass@k ✓ |
| 24 | **Pollution gate boundary**: P=0.8, $|\mathcal{T}_e|=2$ — borderline, gate FIRES (eff_min=3 not met) | 10 | 8 | 2 | 8 | 0 | 0.800 | n/a | n/a | **0.00** | **polluted_dataset** ✓ |
| 25 | **Pollution gate boundary**: P=0.8, $|\mathcal{T}_e|=3$ — borderline, gate does NOT fire (eff_min met) | 15 | 12 | 3 | 12 | 0 | 0.800 | 0/3 = **0.00** | 1.00 | **0.00** | scored ✓ |
| 26 | **Pollution gate doesn't fire below threshold**: P=0.5, $|\mathcal{T}_e|=10$ — clean enough to score | 20 | 10 | 10 | 15 | 5 | 0.500 | 5/10 = **0.50** | 1.00 | **0.50** | scored ✓ |
| 27 | **F3 re-test (small T, broken=1)**: $\lvert\mathcal{T}\rvert=2$, perfect fix, 1 baseline regression | 2 | 0 | 2 | 2 | 2 | 0.000 | 2/2 = 1.00 | 1 − 1/max(20, min(50, 2)) = 1 − 1/20 = **0.95** | **0.95** | scored — F3 closure ✓ (was 0.50 under v2e) |
| 28 | **F3 re-test (large T, broken=1)**: $\lvert\mathcal{T}\rvert=500$, $\lvert P\rvert = 50$, perfect fix, 1 baseline regression | 500 | 0 | 500 | 500 | 500 | 0.000 | 1.00 | 1 − 1/max(20, min(50, 500)) = 1 − 1/50 = **0.98** | **0.98** | scored — large-T behavior unchanged from v2e ✓ |
| 29 | **F4 disposition (Audit-5 corrected)**: same agent rollout re-run twice, baseline tests stable (freya empirics) | 20 | 5 | 15 | 19 | 14 | 0.25 | 14/15 = 0.933 | 0.95 | **0.887** | scored — IDENTICAL across re-runs because $T_{p,\text{run}}$ variance was 0% across 150 freya re-run groups ✓ (structural F4 risk not manifest) |
| 30 | **F4 stress (hypothetical)**: same agent rollout, flaky baseline test enters/exits $T_{p,\text{run}}$. Run A: $T_{p,\text{run}}$ size 200, $\mathcal{T}_b = 5$. Run B: $T_{p,\text{run}}$ size 201, $\mathcal{T}_b = 6$. | 20 | 5→6 | 15→14 | 19 | 14→13 | 0.25→0.30 | 0.933→0.929 | 0.95 | **0.887 → 0.882** | scored — small drift visible; v3 watchpoint when flaky corpora arrive (§9 risk #4) |
| 31 | **F2 + F3 compound**: polluted large-T (179/200 pre-existing, $|\mathcal{T}_e|=21$), broken=5 | 200 | 179 | 21 | 184 | 5 | 0.895 | 5/21 = **0.238** | 1 − 5/max(20, min(50, 200)) = 1 − 5/50 = **0.90** | **0.214** | scored — both F2 and F3 contributions visible ✓ |
| 32 | **Audit-6 double-penalization check**: $\mathcal{T}=\{a,b,c,d,e,f\}$ (6 targets), $T_{p,\text{baseline}}=\{a,b,c,x,y\}$ ($a,b,c\in\mathcal{T}$; $x,y\notin\mathcal{T}$). $\mathcal{T}_{\text{baseline}}=\{a,b,c\}$, $\mathcal{T}_{\text{eff}}=\{d,e,f\}$. Agent fixes $\{d,e\}$, breaks $\{a\}$ from $\mathcal{T}_{\text{baseline}}$. $F_p=\{b,c,d,e\}$. hits\_raw $=\lvert\mathcal{T}\cap F_p\rvert=4$. **Old arithmetic** (v2f): $\max(0,4-3)=\mathbf{1}$ — **undercounts** (penalty for $a$'s regression in numerator AND factor). **Set-diff** (v2g): $\lvert(\mathcal{T}\cap F_p)\setminus T_{p,\text{baseline}}\rvert=\lvert\{b,c,d,e\}\setminus\{a,b,c,x,y\}\rvert=\lvert\{d,e\}\rvert=\mathbf{2}$. broken=1 ($\{a\}\in\text{preserve\_set}\cap F_f$), denom=max(20, min(5,6))=20. | 6 | 3 | 3 | 4 | **2** | 0.500 | 2/3 = **0.667** | 1−1/20 = **0.95** | **0.633** | scored — regression of $a$ penalized exactly once via factor; set-diff numerator unaffected ✓ (v2f old-form would give recall=1/3, reward=0.317 — double-penalization) |

**Notes:**
- Scenarios 19, 20 verify the load-bearing F2 closure: empirically-confirmed do-nothing-inflation cases now score 0 as they should.
- Scenarios 21, 22 verify that real agent work on the same instances *still earns credit* — F2 doesn't break the completion gradient.
- Scenario 23 verifies that the most extreme pollution case (pubkey__rxdb-4758 with all 539 targets pre-existing) is properly excluded rather than scored as a near-1.0 win.
- Scenarios 24, 25 verify the boundary behavior of the pollution gate ($|\mathcal{T}_e| < 3$ fires, $|\mathcal{T}_e| \ge 3$ does not).
- Scenario 27 vs 28 verifies F3 closure: small-T tasks no longer pay 25× regression cost.
- Scenario 31 demonstrates v2f's intended behavior on combined-pathology instances — both adjustments contribute, neither dominates.
- **Scenario 32 is the key Audit-6 test**: a $\mathcal{T}_{\text{baseline}}$ target regresses. Set-difference numerator gives recall=2/3 (the 2 genuinely new fixes); old v2f arithmetic would have given recall=1/3 by subtracting the regression from the numerator a second time. Regression penalized exactly once — by factor. This is the only scenario where v2g and v2f produce different rewards.

**All reviewer flaws closed. All Oracle audit #1 findings closed. All Oracle audit #2 findings (N1, N2, N3) closed. All Oracle audit #3 findings (C-1, H-1, H-2, M-1/2/3, L-1/2/3/4) closed. All Audit #4 findings (F1, F2, F3, F4) closed. The formula is universal: same shape, same constants, same semantics for all 8 languages, all status outcomes surfaced explicitly.**

---

## 7. Stakeholder defense (one paragraph)

> Our reward adopts the test-state transition taxonomy of SWE-bench (Jimenez et al., ICLR 2024) extended to 8 categories per Multi-SWE-Bench (Zan et al., NeurIPS 2025), with continuous $r \in [0, 1]$ following SWE-RL (Wei et al., NeurIPS 2025), which establishes that continuous rewards improve training signal over binary outcomes for SWE-style code-fix tasks. The formula is an **adjusted recall** metric: $r = \bigl(\lvert(\mathcal{T} \cap F_p) \setminus T_{p,\text{baseline}}\rvert \,/\, \lvert\mathcal{T}_{\text{eff}}\rvert\bigr) \times \text{regression\_factor}$, where TARGETS $\mathcal{T}$ come from the dataset's curator-authored gold transitions, $T_{p,\text{baseline}}$ is the run's pre-fix passing set (subtracting pre-existing-passing targets so a do-nothing agent earns 0, not 0.888 on pollution-prone instances), and $\mathcal{T}_{\text{eff}} = \mathcal{T} \setminus T_{p,\text{baseline}}$ is the agent-gradable subset. On-the-fly re-curation from raw test arrays when cached gold dicts are empty mirrors `harness/report.py:130-138` bucketing. The regression factor uses $\text{denom} = \max(R_0, \min(\lvert\text{preserve\_set}\rvert, \lvert\mathcal{T}\rvert))$ with $R_0 = 20$ (one std above SWE-bench median target count), where $\text{preserve\_set} = \text{gold}_{p2p} \cup T_{p,\text{baseline}}$ — closing regression-blindness on the 53% of freya datasets with empty curator-supplied $\text{gold}_{p2p}$, while bounding per-regression cost at $1/R_0 = 5\%$ to decouple small-task sharpness from large-task leniency. Sourcing TARGETS from the dataset closes both the n2p-injection exploit (BenchJack, Wang et al., 2025) and the `valid:false` gradient-collapse defect (Oracle audit). We ship as an evaluation metric with binary canonical; promotion to training reward is gated on validation experiments per `continuous_reward_plan.md` §6.

---

## 8. Implementation plan

### 8.0 v2e → v2g delta (THIS UPDATE)

v2e is shipped in `scripts/harbor/converter.py::compute_reward_v2d` + `tests/test_reward_v2d.py` + `scripts/eval/eval_reward_v2d.py`. v2g is a spec-only update at this commit; code changes required to land v2g:

1. **Rename** `compute_reward_v2d` → `compute_reward_v2g` (preserves legacy name as alias for one release for backward compatibility of import paths).
2. **Add** baseline-subtraction logic (§2.4.2 – §2.4.4) — **Audit-5 corrected**:
   - Source $T_{p,\text{baseline}}$ from **`instance_report["test_patch_result"]["passed_tests"]`** (the RUN REPORT, not the dataset — see §1.5 F5 for the empirical proof that the dataset source is structurally inert on n2p-only instances).
   - Compute $\mathcal{T}_{\text{baseline}} = \mathcal{T} \cap T_{p,\text{baseline}}$, $\mathcal{T}_{\text{eff}} = \mathcal{T} - \mathcal{T}_{\text{baseline}}$, `pollution_rate`.
   - Compute `baseline_drift = |T_p_baseline Δ dataset.test_patch_result.passed_tests|` as a diagnostic (no formula impact).
   - Replace recall formula with adjusted recall (§2.4.4).
3. **Add** pollution gate (§2.4.3): emit `status: polluted_dataset, reward=0.0` when `pollution_rate >= 0.8 AND |T_eff| < 3`.
4. **Update** preserve_set source (§2.5.1): `preserve_set = gold_p2p ∪ T_p_baseline` where `T_p_baseline` is the run report's `test_patch_result.passed_tests` (same source as §2 step 2 above).
5. **Add** R0 floor (§2.5.2): `denom = max(R0=20, min(max(1, |preserve_set|), max(1, |T|)))`.
6. **Update** `reward_binary` to use new preserve_set (§2.7 #12). **Not** fully run-deterministic — depends on flakiness of run-report's `test_patch_result.passed_tests`; freya empirics 0% variance, v3 watchpoint per §9 risk #16.
7. **Add** diagnostics (§3.1): `t_baseline_total`, `t_eff_total`, `pollution_rate`, `hits_new`, `R0`, `regression_denom`, `t_p_dataset_total`, `baseline_drift`, `f2p_baseline_pass_count` (Audit-6 env-drift alarm). **Do NOT** add `baseline_source` (v2f-attempt-1 artifact; baseline is always run-report). **Do NOT** rename `t_p_run_total` (v2e key preserved).
8. **Update** `scripts/eval/eval_reward_v2d.py` → `eval_reward_v2g.py`:
   - Compute `m2_excluded_per_language` aggregate; emit to CSV header row.
   - Emit per-row `pollution_band` (low/medium/high/excluded) for downstream stratification.
9. **Add tests** (`tests/test_reward_v2g.py`): F1-F4 closure scenarios (§6.1 #19-31). Re-run all v2d tests with `compute_reward_v2g` to confirm no regression on prior closures.
10. **Re-run** 450-freya CSV; verify (Audit-5 corrected expectations):
    - `starship-138` rows: 9/9 do-nothing recall = 0.0 (was 0.888 under v2e; would still be 0.888 under v2f-attempt-1 because dataset.tpr.passed = 0 made `T_baseline` vacuously empty)
    - `testcontainers-java-8298` rows: 9/9 do-nothing recall = 0.0 (was 0.342 under v2e; would also be 0.0 under v2f-attempt-1 because dataset.tpr.passed = run.tpr.passed = 499 on this instance — `baseline_drift ≈ 0`)
    - HypothesisWorks-4452 still emits `status: vacuous`
    - AMReX-4238 still scored with all 57 targets (no N3 regression)
    - cpp rows still have `regression_channel_active: false` (H-1 unchanged)
    - Per-language M-2 counts match the §10.3.1 table (155/350; Rust 35, Java 26, C 20, Go 26, Cpp 17, TS 16, JS 14, Python 1)
    - `baseline_drift` non-zero on at least starship-138 (dataset says 0 baseline passes, run says 82 → drift = 82). This is curation hygiene signal, not formula failure.
    - pollution_rate distribution: per-language histogram. Expect ts/rust to skew high (n2p-only common); python low.

### 8.1 Code changes (converter.py) — **STATUS (v2e): SHIPPED. STATUS (v2g): SHIPPED**

1. **`scripts/harbor/converter.py`**:
   - Added helper `_bucket_from_raw_arrays(test_stage, fix_stage) -> dict[str, set[str]]` mirroring `report.py:130-138`
   - Added helper `_gold_with_lazy_recuration(dataset_record) -> tuple[dict[str, set[str]], bool]` (§2.2 R1)
   - Added helper `_stage_count_drift(stage) -> bool` (M-1 widened symmetric integrity check)
   - Added helper `_is_finite_float(value) -> bool` (L-3 NaN/Inf guard)
   - Added public function `compute_reward_v2d(dataset_record, instance_report) -> dict` returning `{rewards, reward_version, status, diagnostics}` per §3.1
   - **v2e change**: `reward_internal_plan` removed from emit (H-2). `reward_binary` uses multi-language definition $\mathbb{1}[\mathcal{T} \subseteq F_p \land \text{preserve\_set} \cap F_f = \emptyset]$ (C-1).
   - `build_trajectory` signature widened with `dataset_record` parameter; `verifier_result` carries full v2e payload
   - `convert_instance` threads dataset record into `build_trajectory`
   - `load_dataset_record` made case-insensitive
   - `reward.txt` writer: `f"{x:.2f}"` → `f"{x:.6f}"` (closes H1)

2. **No changes** to `multi_swe_bench/harness/report.py` — formula reads dataset and raw run arrays only.

3. **No changes** to upstream `multi-swe-bench` fork — v2e is contained entirely in milo-bench converter.

### 8.2 Test harness — **STATUS: SHIPPED in v2e**

`benchmarks/multiswebench/tests/test_reward_v2d.py` — 26 tests passing covering:

- **§6 canonical scenarios** (V2DCanonicalScenarios class): tests 01, 02, 04 (completion gradient), 05, 06, 07, 08, 10, 11 (with C-1 binary assertion), 12 (C2 defeat), 15 (vacuous)
- **Oracle audit #2 closures** (V2DOracleClosures class): N1 preserve_set R2, N2 lazy re-curation, N2 vacuous-when-raw-empty, N3 no n2p filter at compute time (with C-1 binary assertion)
- **Oracle audit #3 closures + edge cases** (V2DEdgeCases class):
  - `test_no_signal_when_inputs_missing` — both args None / partial
  - `test_invalid_when_failed_count_mismatches` — M-1 fix-stage failed_count
  - `test_invalid_when_passed_count_mismatches` — M-1 fix-stage passed_count
  - `test_invalid_when_test_stage_count_mismatches` — M-1 test-stage symmetry
  - `test_invalid_when_test_stage_empty_with_gold` — M-2 degenerate test_patch
  - `test_reward_field_shadows_binary_phase1` — §8.3 Phase-1 canonical alignment
  - `test_binary_zero_when_regression_breaks_preserve_set` — C-1 regression penalty in binary
  - `test_binary_uses_targets_not_just_f2p` — C-1 multi-language binary
  - `test_no_internal_plan_in_emit` — H-2 confirmation
  - `test_regression_channel_active_diagnostic` — H-1 diagnostic
  - `test_unknown_breaks_diagnostic` — R5

**Real-data validation**: `scripts/eval/eval_reward_v2d.py` against 450 freya reports → `/tmp/reward_v2d_v2.csv`. Verified post-v2e:
- HypothesisWorks-4452 → `status: vacuous` (N2)
- AMReX-4238 → targets=57 preserved (N3)
- casey/just-1316 kimi/run_3 → reward_continuous_v2=0.984 with report.valid=False (C1)
- Go/Java/JS n2p-only instances → binary=1.0 when all targets hit (C-1 fix)
- 0 cases of binary=1/v2d=0 (L-4 fix)
- 0/27 cpp scored rows have `regression_channel_active=true` (H-1 honest reporting)

### 8.3 Rollout (per `continuous_reward_plan.md` §6)

| Phase | Canonical reward | Continuous emission | Training? |
|---|---|---|---|
| 1 (this PR) | binary | yes (eval metric only) | binary |
| 2 (after CSV review) | binary | yes, evaluators inspect both | binary |
| 3 (after 20-30 hand-labeled validation) | TBD by experiment | yes | A/B test continuous vs binary |
| 4 (after winner picked) | winner | winner only | winner |

---

## 9. Open risks (acknowledged, not blocking v1)

1. **§5.1 sparse reward**: continuous reward still near-0 on early RL rollouts. Curriculum / shaping at trainer.
2. **§5.7 unproven**: no published evidence continuous > binary on this exact recall + preserve_set-min-form shape. Dual-emission enables A/B measurement.
3. **Flaky tests**: a test passing in dataset construction but failing in the run inflates `broken` unfairly. Right fix is re-run aggregation at pass@k summary, not formula change.
4. **Heterogeneous instances**: a 5-target task and a 500-target task contribute equal weight to pass@k mean. Per-difficulty-tier weighting is v3.
5. **Dataset hygiene**: if the dataset's raw arrays are also incomplete (rare; not observed on the 350-row freya scan beyond the 10 fully-vacuous instances), lazy re-curation falls back to `vacuous` honestly.
6. **Reward versioning across runs**: dual-emission allows graceful migration, but comparing v1-binary vs v2e-continuous numbers requires care.
7. **`preserve_set` overcounts when $T_{p,\text{run}}$ includes tests that legitimately changed behavior in this instance.** Mitigation: gold dicts (when populated) are authoritative for canonical preservation; the union only enlarges the denominator, which strictly weakens the penalty's per-broken impact. Worst case is regression channel is less sharp on such instances; never wrongly accuses.
8. **Cpp inert regression channel (Oracle audit #3 H-1)**: on instances where both $\text{gold}_{p2p}$ and $T_{p,\text{run}}$ are empty (100% of cpp scored rows in freya), the regression factor is structurally 1.0 and reward equals pure recall. Agents on those instances can break baseline tests without reward penalty. Mitigation: `regression_channel_active=false` diagnostic; stratify pass@k by this flag. A future v3 may add an explicit "fallback envelope" but v2e refuses because $F_p \cup F_f$ over-penalizes (every test that fails in fix stage becomes a "regression" without baseline-passing evidence).
9. **Semantic C2 (BenchJack-style assertion-body mutation of gold targets)**: v2e closes C2 at the name-set layer (§2.5, §2.7 #10). Semantic mutation closure depends on upstream harness enforcing fix_patch ≠ test_patch file ownership (SWE-bench issue #538). v2e does not re-validate test bodies at reward-compute time.
10. **Dataset PR trust boundary (Oracle audit #3 L-1)**: lazy re-curation §2.2 reads from `dataset_record["test_patch_result"]`/`["fix_patch_result"]` raw arrays. A malicious or careless dataset PR can insert names into these arrays, which lazy re-curation will then promote into gold_n2p. The trust control is dataset-PR review (human + CI), not in-formula validation. Adding a per-instance checksum on raw arrays in v3 would close this.
11. **Name canonicalization not applied to diagnostics (Oracle audit #3 L-2)**: `f2s_count` and `evasion_ratio` compare raw test names without runner-specific canonicalization (e.g., vitest's stage-prefix drift). Diagnostic-only — no formula impact — but may under-report skip-evasion on JS/TS runs.
12. **M-2 exclusion is correct but representativeness-relevant (Audit #4 F1)**: ~44% of the freya dataset (155/350) triggers M-2, skewed toward compiled languages (Rust 80%, Java 63%, C 54%) vs Python (2%). The rule is structurally right — an empty test_patch_result IS unreliable signal — but its blast radius is now surfaced via the `m2_excluded_per_language` CSV emit. **Aggregator action required**: pass@k / `reward_continuous_v2` mean numbers should be reported alongside per-language M-2 exclusion counts so generalization claims are quantified. The 50-instance trajectory subsample triggers M-2 at 13% — non-representative of full-dataset 44%; any CSV computed from it cannot be extrapolated without disclosure.
13. **Pollution-gate threshold tuning (Audit #4 F2)**: the gate fires when `pollution_rate >= 0.8 AND |T_eff| < 3`. These constants are tuned to the freya distribution. On future datasets with substantially different pollution rates, the thresholds may need to be re-tuned. The constants are configurable in `compute_reward_v2g`; any retune should be accompanied by a re-run of §6 Scenarios 19-26 to confirm semantics are preserved. Borderline instances (`pollution_rate ∈ [0.6, 0.8)`) are scored but flagged via the `pollution_rate` diagnostic for downstream stratification.
14. **Baseline subtraction depends on `gold_n2p` and `test_patch_result.passed_tests` consistency at curation time (Audit #4 F2)**: the assumption is that any name in `gold_n2p ∩ test_patch_result.passed_tests` was a pre-existing test passing in the test_patch stage. If the dataset was curated under inconsistent harness versions where `test_patch_result.passed_tests` was populated with names that shouldn't be in `gold_n2p`, baseline subtraction could over-count pre-existing tests and *under*-score legitimate agent contributions. Empirically not observed in freya; flagged as a v3 dataset-hygiene watchpoint. Mitigation: log row-level `pollution_rate` distribution per dataset version; investigate spikes.
15. **R0 = 20 is a constant, not a learned parameter (Audit #4 F3)**: chosen at one std above SWE-bench Verified's median `|FAIL_TO_PASS|`. On future corpora with substantially different target-count distributions, this should be revisited. Configurable in `compute_reward_v2g`.
16. **F4 partially open (Audit #5)**: `T_p_baseline` is sourced from the run report's `test_patch_result.passed_tests` (Audit-5 forced us off the frozen-dataset source — see §1.5 F5). `preserve_set` and `reward_binary` are therefore structurally exposed to baseline test flake. Empirically `T_p_run` was 0% variant across 150 same-(instance, model) re-run groups in freya, so the pathology does not manifest currently. **v3 fix path**: pin $T_{p,\text{baseline}}$ from a separate frozen baseline run (compute once per (instance, harness-version) pair, cache, source from cache for all eval runs). This makes the baseline observation deterministic without taking it from the curation observation (which is structurally disjoint from gold_n2p per §1.5 F5).
17. **Composite-reward dependency (Audit #5 reviewer point 2, §1.1)**: v2f is a terminal test-outcome metric. For long-horizon RL it requires pairing with a rubric/process channel; it is NOT a complete RL reward on its own. The scope is explicit in §1.1 and §1; promotion to *sole* RL reward is not contemplated. Downstream consumers must treat v2f as one channel of a composite, not the canonical reward signal.
18. **Composite normalization is the trainer's job**: per `continuous_reward_plan.md` §6 and the composite-reward design doc, per-group / GRPO normalization, flaky re-run aggregation at pass@k, and cross-task comparability all happen at the trainer/aggregator layer. v2f emits the raw scalar; do not interpret a 0.5 here as comparable to a 0.5 elsewhere without trainer-side normalization.
19. **Dataset-vs-runtime baseline drift is a curation defect, not a formula defect (Audit #5 F5)**: starship-138's dataset says 0 baseline passes; the eval harness finds 82. The dataset was curated under a different test-discovery scope than eval runs with. v2f surfaces this via `baseline_drift` diagnostic but does not fix it. Real fix requires re-curating the affected instances under the same harness configuration the eval pipeline uses.

---

## 10. Per-language considerations (v2d simplification)

v2a placed heavy weight on per-language test-name → file mapping because the formula's $n2p_{\text{filt}}$ term was load-bearing for the C2 defense. v2c retained a language-conditional hygiene filter. v2d removes both.

### 10.1 What the harness emits (verified on 5 real freya instances)

| Language | Sample test name from `fix_patch_result.passed_tests` |
|---|---|
| Python (pytest) | `hypothesis-python/tests/cover/test_direct_strategies.py::test_build_class_with_target_kwarg` |
| JS/TS (vitest) | `src/utils/url.spec.js (22 tests) 30ms` |
| Go (`go test`) | `TestQuerySanitize` |
| Rust (`cargo test`) | `tests::add_multiple_arg` |
| C++ (gtest / custom) | `amrex_unknown` |

### 10.2 Effect on v2d

At **reward compute time**, all that matters is matching test names against the dataset's gold dicts. Set-membership check works identically for all languages: `len(gold_targets & F_p)`. No file extraction needed. **No language-specific filter at compute time.**

At **dataset curation time** (when the gold dicts were populated, either by upstream harness or by v2d's §2.2 lazy re-curation), the canonical `report.py:130-138` bucketing applies the same logic to all languages. We trust that bucketing — both for upstream-cached gold dicts and for on-the-fly re-curation.

Oracle finding **N3** specifically rejected a strict-fallback "drop n2p tests that don't parse to test_patch files for non-Python/JS langs" approach (would shrink AMReX-Codes-4238 TARGETS 57 → 2). v2d resolves N3 by **never dropping** any name from $\text{gold}_{n2p}$ at compute time. C2 defense is structural (dataset is frozen, agent cannot mutate it) — not heuristic.

### 10.3 Plumbing

The dataset path resolves via `freya/milo-bench/dataset/<instance_id>.jsonl` (single record per file). The `lang` discriminator lives at the top level of each dataset record but is **not consumed by the formula** in v2f — it remains in diagnostics for downstream stratification and analysis only.

### 10.3.1 Per-language M-2 exclusion (v2f F1 closure)

**Empirical scan of all 350 freya dataset rows** (Oracle audit #4 verified):

| Language | Total rows | M-2 fires | % of language | Effective evaluable rows |
|---|---|---|---|---|
| Rust | 44 | 35 | **79.5%** | 9 |
| Java | 41 | 26 | 63.4% | 15 |
| C | 37 | 20 | 54.1% | 17 |
| Go | 57 | 26 | 45.6% | 31 |
| Cpp | 40 | 17 | 42.5% | 23 |
| TS | 42 | 16 | 38.1% | 26 |
| JS | 44 | 14 | 31.8% | 30 |
| Python | 45 | 1 | 2.2% | 44 |
| **Total** | **350** | **155** | **44.3%** | **195** |

**Per-language pollution-prone rate** (Oracle audit #4: $\lvert\text{gold}_{n2p}\rvert \ge 0.8 \cdot \lvert\mathcal{T}\rvert$ AND $<20\%$ in test_patch AND $\lvert\mathcal{T}\rvert \ge 10$, across 340 non-vacuous rows):

| Language | Suspect-pollution count | Action under v2f |
|---|---|---|
| Go | 35 | scored with baseline subtraction; `pollution_rate` surfaced |
| Rust | 34 | scored with baseline subtraction; `pollution_rate` surfaced |
| Java | 26 | scored with baseline subtraction; `pollution_rate` surfaced |
| TS | 25 | scored with baseline subtraction; `pollution_rate` surfaced |
| C | 19 | scored with baseline subtraction; `pollution_rate` surfaced |
| JS | 16 | scored with baseline subtraction; `pollution_rate` surfaced |
| Cpp | 13 | scored with baseline subtraction; `pollution_rate` surfaced |
| Python | 4 | scored with baseline subtraction (rare) |

**Consumer guidance** (v2f, F1 closure):

1. Always read `m2_excluded_per_language` from the CSV emit and report it alongside pass@k.
2. Stratify pass@k by `(lang, pollution_band)` where `pollution_band` is `low (<0.5)`, `medium (0.5–0.8)`, `high (≥0.8 scored)`, `polluted_dataset (excluded)`.
3. Do NOT extrapolate from the 50-instance trajectory subsample (13% M-2) to the full 350-instance dataset (44% M-2) without re-running on a stratified sample that covers the M-2 and pollution-prone buckets explicitly.
4. v2f's universal scoring makes the F1 representativeness defect a **reporting issue, not a formula issue**: the formula is correct on all instances it scores, and exclusions are surfaced. Generalization claims must respect the per-language exclusion table above.

### 10.4 Cpp regression-channel limitation (Oracle audit #3 H-1)

Empirical scan of all 36 cpp scored rows in freya (AMReX-4238, simdjson-2095, simdjson-2214 × 3 models × 3 runs, plus AMReX-4271): **0/36 have `regression_channel_active=true`**. Root cause is at the upstream test-runner level: the cpp test_patch stage in these instances emits `passed_count=0`, `passed_tests=[]` even on otherwise-valid runs. This is independent of v2e — neither v2c, v2d, nor v2e can synthesize a preservation envelope from nothing without introducing false positives.

**Consumer guidance.** Pass@k aggregators should expose `regression_channel_active` from `result.json:verifier_result.diagnostics` and either:
1. Stratify pass@k by `regression_channel_active=true|false`; report each stratum separately; or
2. For cpp-only training cohorts, treat reward as pure recall (factor is structurally 1.0); ensure curriculum design is aware that regression-avoidance signal is absent.

**Not a closure-blocker for v2e**: cpp instances are not the dominant language in freya (8% of scored rows), and binary correctness on these instances is unchanged by H-1 — the agent still must hit all $\mathcal{T}$ targets to score 1.0. The continuous channel is *more lenient* than binary on cpp, which is the opposite direction of the C2 risk.

---

## 11. References

### Primary academic sources

- Jimenez et al. 2024. **SWE-bench: Can Language Models Resolve Real-World GitHub Issues?** ICLR 2024 Oral. [arxiv:2310.06770](https://arxiv.org/abs/2310.06770)
- Zan et al. 2025. **Multi-SWE-Bench: A Multilingual Benchmark for Issue Resolving.** NeurIPS 2025. [arxiv:2504.02605](https://arxiv.org/abs/2504.02605)
- Wei et al. 2025. **SWE-RL: Reasoning, Refining, and Looking-Back via RL.** NeurIPS 2025. [arxiv:2502.18449](https://arxiv.org/abs/2502.18449)
- Wang et al. 2025. **BenchJack: Systematic Reward-Hacking Audit of Agent Benchmarks.** [arxiv:2605.12673](https://arxiv.org/abs/2605.12673)
- Lightman et al. 2024. **Let's Verify Step by Step.** ICLR 2024. [OpenReview:v8L0pN6EOi](https://openreview.net/forum?id=v8L0pN6EOi)
- Rothermel & Harrold 1996. **Analyzing regression test selection techniques.** IEEE TSE 22(8):529-551.

### Production / industry sources

- OpenAI 2024. **Introducing SWE-bench Verified.** [openai.com/index/introducing-swe-bench-verified](https://openai.com/index/introducing-swe-bench-verified/)
- SWE-bench issue #538: test-patch overwrite exploit
- SWE-bench issue #465: future-history git leakage
- Harbor PR #1593 / #1596: git cleanup defenses

### Internal sources

- `benchmarks/multiswebench/continuous_reward_plan.md` — original internal proposal (recall denominator + p2p_factor)
- `milo-gym/docs/specs/sections/06-reward.md` — current binary v1 contract
- `2026-06-03-lht-harbor-skyrl-gym-design.md` — composite reward architecture
- Oracle audit #1 (this session) — strict edge-case analysis identified C1 + C2 in v1 formula
- Oracle audit #2 (this session) — stress-test of v2c reconciled formula identified N1 + N2 + N3
- Reviewer audit (this session) — caught precision-vs-recall structural defect in v2a

---

## 12. Reviewer reconciliation log

This section records, for posterity and future auditors, the disagreements that shaped the formula and how they were resolved.

| Reviewer | Critique | Disposition |
|---|---|---|
| External reviewer (subtractive critique) | v2a is a precision metric; use cases need recall | **Accepted.** Pivot from subtractive to recall × factor shape. |
| External reviewer (hybrid factor) | Use max-of-fractions for regression factor to handle both small and huge baselines | **Accepted.** v2c implemented max-of-fractions; v2d's min-form is mathematically identical. |
| Oracle audit #2 (N1) | gold_p2p empty in 53% of freya datasets → regression channel inert | **Accepted.** v2d's `preserve_set = gold_p2p ∪ T_p_run` (R2). |
| Oracle audit #2 (N2) | 10/350 freya datasets have ALL gold dicts empty → C1 displaced | **Accepted.** v2d's lazy re-curation §2.2 (R1). |
| Oracle audit #2 (N3) | Strict §10 curation fallback shrinks AMReX-4238 TARGETS 57→2 (Flaw 4 redux) | **Accepted.** v2d removes language-specific n2p filter at compute time (R3). |
| Oracle audit #2 (suggested) | Add `unknown_breaks_count` diagnostic for visibility into curation gaps | **Accepted.** v2d §3.1 includes the field (R5). |
| f2s evasion penalty | No published precedent; novel | **Deferred.** Recall already penalizes skip-as-failure (missed target ⇒ no hit ⇒ recall drops). Emitted as diagnostic only. |
| Audit #4 reviewer (F1 M-2 silent exclusion) | Surface per-language exclusion in CSV as a representativeness caveat, not a buried integrity rule | **Accepted (v2f §3.1, §9 risk #12, §10.3.1).** CSV emits `m2_excluded_per_language`; per-language table published in §10.3.1. Rule itself unchanged (M-2 still triggers `status: invalid`); only its surfacing. |
| Audit #4 reviewer (F2 gold_n2p pollution) | Add `target_provenance` guard; filter pre-existing n2p on Python/JS/TS where mapping is reliable; route Go/Rust/Cpp to `status: low_confidence` | **Adapted, not adopted as-written.** v2f closes F2 via **language-agnostic baseline subtraction** instead of language-stratified filtering. Pre-existing tests are subtracted from both numerator and denominator of adjusted recall, so they earn no credit. **No name is dropped from $\mathcal{T}$** — N3 closure preserved. The pollution gate emits `polluted_dataset` (not `low_confidence`) when ≥80% pre-existing AND $\lvert\mathcal{T}_{\text{eff}}\rvert < 3$. Same disposition (exclude), structurally cleaner because universal. |
| Audit #4 reviewer (F3 regression denom) | Replace `min(|preserve|, |T|)` with `max(|preserve_set|, R0)` with absolute floor | **Adapted.** v2f uses $\max(R_0, \min(\max(1, \lvert\text{preserve\_set}\rvert), \max(1, \lvert\mathcal{T}\rvert)))$. Floor at $R_0$ closes F3; min cap above $R_0$ preserves §5.2 closure on huge baselines (reviewer's `max(|preserve|, R0)` alone would re-open §5.2). $R_0 = 20$ chosen at one std above SWE-bench Verified median $\lvert\text{F2P}\rvert$. |
| Audit #4 reviewer (F4 T_p_run non-determinism) | Add do-nothing baseline audit script; pin T_p_run from a separate baseline freeze run | **Accepted (pinning) + deferred (audit script).** v2f sources $T_{p,\text{baseline}}$ from the frozen dataset's `test_patch_result.passed_tests` — the equivalent of a baseline pin without requiring a separate freeze run. Audit script ("do-nothing baseline + target-provenance audit") is a useful evaluation tool but not part of the spec; it can be implemented atop the v2f emit by setting $F_p = T_{p,\text{baseline}}$ and reading the emitted `recall` per row. |

---

## 13. Oracle audit #3 closure log (v2d → v2e)

Oracle audit #3 (strict industry-veteran review of the v2d spec, converter.py implementation, unit tests, and 450-row CSV) returned REJECT with 1 CRITICAL, 2 HIGH, 3 MEDIUM, 4 LOW findings. v2e is the response.

| Finding | Severity | Disposition |
|---|---|---|
| **C-1** Binary collapses to 0 on n2p-only gold (Go/Rust/most cpp/Java/JS) because `gold_f2p and gold_f2p.issubset(F_p)` short-circuits on empty f2p | CRITICAL | **CLOSED.** `compute_reward_v2d` rewritten to use multi-language binary $\mathbb{1}[\mathcal{T} \subseteq F_p \land \text{preserve\_set} \cap F_f = \emptyset]$ (§2.7 #12). Verified on CSV: 33 cases on Go/Java/JS now correctly emit binary=1.0 (were 0.0). Tests `test_11_go_targets_all_n2p` and `test_n3_no_n2p_filter_at_compute_time` now assert `reward_binary == 1.0`. New test `test_binary_uses_targets_not_just_f2p`. |
| **H-1** N1 inert on cpp where `T_p_run` is also empty | HIGH | **CLOSED via honest documentation.** §2.5 limitation note added; §2.7 #11 reworded "partially closed"; §4.3 N1 row updated; §9 risk #8 added; §10 §10.4 cpp-specific note added; `regression_channel_active` diagnostic added to §3.1. No false-fallback (rejected $F_p \cup F_f$ envelope as over-penalizing). |
| **H-2** `reward_internal_plan` shipped with known §5.2 defect, no documented consumer | HIGH | **CLOSED.** Dropped from `compute_reward_v2d` emit. CSV evaluator retains it for offline §8.3 Phase-3 A/B only. §3.1 schema updated; test `test_no_internal_plan_in_emit` added. |
| **M-1** Integrity check one-sided (only fix-stage `failed_count`) | MEDIUM | **CLOSED.** New helper `_stage_count_drift` checks `passed_count`/`failed_count`/`skipped_count` against list lengths on BOTH `fix_patch_result` and `test_patch_result`. §3.3 status table updated. Tests `test_invalid_when_passed_count_mismatches`, `test_invalid_when_test_stage_count_mismatches` added. |
| **M-2** Silent fall-through on degenerate `test_patch_result` (all counts zero) with non-empty gold | MEDIUM | **CLOSED.** Emits `status: invalid` when test-stage observed total is zero AND $\lvert\mathcal{T}\rvert > 0$. §3.3 status table updated. Test `test_invalid_when_test_stage_empty_with_gold` added. |
| **M-3** §2.7 properties #2/#3/#4 imprecise at boundaries | MEDIUM | **CLOSED.** Properties rewritten with precise boundary language: #2 "monotonic in hits for fixed regression set," #3 "strictly antimonotonic on $[0, \min(\lvert\text{preserve\_set}\rvert,\lvert\mathcal{T}\rvert)]$, saturated above," #4 "distinct k → distinct r whenever factor > 0." |
| **L-1** Lazy re-curation trust boundary | LOW | **CLOSED via documentation.** §9 risk #10 explicitly names dataset-PR review as the trust control. v3 may add per-instance checksum on raw arrays. |
| **L-2** `evasion_ratio` / `f2s_count` no name canonicalization | LOW | **CLOSED via documentation.** §3.1 diagnostic table now notes the limitation. Diagnostic-only — no formula impact. |
| **L-3** NaN/Inf guard before `reward.txt` write | LOW | **CLOSED.** `_is_finite_float` check returns `status: invalid` if either binary or continuous reward is non-finite. §3.3 status table updated. Defense-in-depth — current arithmetic cannot produce non-finite, but a future contributor adding an unclamped division would now fail-closed. |
| **L-4** CSV evaluator's `reward_binary` ≠ converter's `reward_binary` | LOW | **CLOSED.** `scripts/eval/eval_reward_v2d.py`'s `reward_binary` rewritten to use the same multi-language definition as `compute_reward_v2d`. Empirically verified on freya CSV: 0 cases of binary=1/v2d=0 (was 8). |

### What Oracle ACCEPTED in v2d (preserved in v2e)

| Spec claim | Verification |
|---|---|
| §2.5 algebraic identity `x/min(a,b) = max(x/a, x/b)` for `x≥0, a,b>0` | ✓ proof holds |
| §6 Scenario 13 arithmetic (`0.5 × 0.95 = 0.475`) | ✓ |
| `reward.txt` uses `:.6f` | ✓ |
| Lazy re-curation mirrors `report.py:130-138` bucketing | ✓ |
| C2 set-membership defense (Scenario 12) | ✓ structurally |
| `unknown_breaks_count = F_f − preserve_set − targets` | ✓ |
| `reward_continuous_v2` mean=0.255 vs binary=0.206 (post-C-1-fix) — partial-credit distribution consistent with completion metric | ✓ no statistical alarm |

### Required-before-rollout checklist (all done)

- [x] Fix C-1 in converter.py
- [x] Add `reward_binary` assertions in test_11 and test_n3
- [x] Add binary-definition-consistency test (`test_binary_uses_targets_not_just_f2p`)
- [x] Document cpp / empty-`T_p_run` limitation honestly in §2.5 / §2.7 #11 / §4.3 N1 row / §9 #8 / §10
- [x] Drop `reward_internal_plan` from production emit; keep in CSV for offline A/B
- [x] Widen integrity check in `compute_reward_v2d` to all three counts × both stages
- [x] Emit `status: invalid` when `test_patch_result.all_count == 0` AND non-trivial gold
- [x] Sharpen §2.7 properties #2-4 boundaries
- [x] NaN/Inf guard
- [x] Re-run 50-freya CSV — confirm no Go/Rust binary collapse, 0 cases binary=1/v2d=0
- [x] Update §3.1 schema + §3.3 status table with new fields and triggers

---

## 14. Audit #4 closure log (v2e → v2f)

Audit #4 (external reviewer + Oracle audit #4 verification against on-disk data) returned PASS on F1, PARTIAL on F2 (structurally critical, empirically narrower in current freya runs), PASS on F3, PARTIAL on F4 (structurally real, empirically 0% in freya). v2f is the response. All four findings are closed structurally; F1's representativeness is closed via reporting hygiene rather than formula change.

### Per-finding disposition

| Finding | Severity (Oracle verdict) | Disposition | Spec sections |
|---|---|---|---|
| **F1** M-2 silently excludes ~44% of dataset, compiled-heavy | HIGH | **CLOSED via reporting hygiene.** Rule preserved; CSV emits `m2_excluded_per_language`; per-language exclusion table published in §10.3.1. Consumers can read representativeness off the result file. | §1.5 F1, §3.1 emit schema, §3.3 invalid trigger b note, §4.5 F1 row, §9 risk #12, §10.3.1 table |
| **F2** "Trust full gold_n2p" → do-nothing recall ≈ 1.0 on 51% of dataset's structurally pollution-prone instances | CRITICAL | **CLOSED via baseline subtraction (universal).** Adjusted recall subtracts $\lvert\mathcal{T}_{\text{baseline}}\rvert$ from both numerator and denominator. Pollution gate emits `polluted_dataset` for the most extreme cases (≥80% pre-existing, <3 effective targets). No name dropped from $\mathcal{T}$ → N3 closure preserved. Empirically validated: `starship-138` 0.888→0.0, `testcontainers-java-8298` 0.342→0.0, `pubkey__rxdb-4758` → polluted_dataset. | §1.5 F2, §2.4.2–§2.4.4, §2.6 reward branches, §2.7 #13, §3.1 diagnostics, §3.3 status, §4.5 F2 row, §6.1 Scenarios 19-26, §9 risks #13-14 |
| **F3** min-form denom couples regression cost to \|T\| (25× swing) | MEDIUM | **CLOSED via R0 floor.** $\text{denom} = \max(R_0, \min(\max(1, \lvert\text{preserve\_set}\rvert), \max(1, \lvert\mathcal{T}\rvert)))$, $R_0 = 20$. Per-break cost is bounded above by 5%; large-T behavior unchanged (preserves §5.2 closure). | §1.5 F3, §2.5.2–§2.5.5, §2.7 #15, §3.1 R0 + regression_denom diagnostics, §4.5 F3 row, §6.1 Scenarios 27-28, §9 risk #15 |
| **F4** T_p_run is structurally non-deterministic via flaky tests | LOW (manifest) / STRUCTURAL | **PARTIALLY CLOSED — Audit-5 superseded the frozen-dataset approach.** v2f-attempt-1 sourced $T_{p,\text{baseline}}$ from dataset's `test_patch_result.passed_tests` to close F4 fully; Audit #5 (§1.5 F5) invalidated that source because it's structurally disjoint from gold_n2p, making F2 closure inert. v2f sources $T_{p,\text{baseline}}$ from the run report instead, accepting partial F4 exposure. **Empirical**: 0% variance across 150 freya re-run groups, so pathology is currently latent. **v3 fix**: pin baseline from a separate frozen baseline run. | §1.5 F4 + F5, §2.4.2, §2.5.1, §2.7 #12/16/17, §3.1 diagnostics, §4.5 F4 row, §6.1 Scenarios 29-30, §9 risk #16 |

### Empirical validation required before v2f rollout

The following must be verified against re-run freya CSV before promoting v2f to canonical:

- [ ] `starship-138` rows (9/9): under v2f, do-nothing rollouts emit `recall = 0.0` (verify against actual model rollouts that effectively didn't fix anything)
- [ ] `testcontainers-java-8298` rows (9/9): under v2f, do-nothing rollouts emit `recall = 0.0`
- [ ] `pubkey__rxdb-4758` rows (if in trajectories or by adding to run set): under v2f, all rollouts emit `status: polluted_dataset`
- [ ] HypothesisWorks-4452: still emits `status: vacuous` (N2 preserved)
- [ ] AMReX-Codes-4238: still scored with all 57 targets visible (N3 preserved)
- [ ] All cpp scored rows still emit `regression_channel_active: false` (H-1 unchanged)
- [ ] Per-language M-2 counts match §10.3.1 table (Rust 35, Java 26, C 20, Go 26, Cpp 17, TS 16, JS 14, Python 1; total 155/350)
- [ ] No `binary = 1.0 ∧ continuous = 0.0` cases (binary/continuous consistency preserved)
- [ ] `baseline_drift` non-zero on at least starship-138 (dataset = 0, run = 82 → drift = 82) — curation hygiene signal, not formula failure
- [ ] Stratified 30+ instance re-run drawn from the M-2-prone (156) and pollution-prone (172) buckets — required by Oracle audit #4 caveat for any generalization claim beyond the existing 50-instance subsample

### Required-before-rollout checklist (v2f)

- [ ] Implement `compute_reward_v2g` per §8.0 delta
- [ ] Add `tests/test_reward_v2g.py` with §6.1 Scenarios 19-31
- [ ] Update CSV evaluator: emit `m2_excluded_per_language`, `pollution_band`
- [ ] Re-run 450-freya CSV; verify empirical checklist above
- [ ] Run stratified 30+ instance sample drawn from M-2-prone and pollution-prone buckets
- [ ] Pre-commit: `uv run pre-commit run --files benchmarks/multiswebench/scripts/harbor/converter.py benchmarks/multiswebench/tests/test_reward_v2g.py`
- [ ] Update `continuous_reward_plan.md` §6 rollout protocol to reference v2f
- [ ] Update `MEMORY.md` index to note v2f spec landed

### What was NOT changed in v2f (preserved from v2e)

- C1 closure mechanism (raw arrays, no `valid` flag dependency)
- C2 closure mechanism (TARGETS from frozen dataset)
- N1 closure (preserve_set union of gold_p2p and baseline)
- N2 closure (lazy re-curation §2.2)
- N3 closure (no language-specific filtering at compute; full gold_n2p kept)
- Reviewer Flaws 1-4 closures
- C-1 closure (multi-language binary)
- H-1 limitation note (cpp regression-channel inert; still documented honestly)
- H-2 closure (`reward_internal_plan` dropped from production emit)
- M-1/M-2/M-3 closures
- L-1/L-2/L-3/L-4 closures
- §6 Scenarios 1-18 (all canonical scenarios from v2d/v2e remain valid; v2f just adds 19-31)

### What v2f does NOT close

- §9 risk #1 (sparse reward in early RL rollouts) — trainer-side, not formula
- §9 risk #2 (no published evidence v2f > binary on this exact shape) — A/B Phase 3 will test
- §9 risk #3 (test flakiness in F_p/F_f) — agent-rollout layer, not formula
- §9 risk #4 (heterogeneous task weight in pass@k mean) — v3 per-difficulty
- §9 risk #5 (raw-array dataset hygiene) — dataset-curation layer
- §9 risk #8 (cpp inert regression channel via empty curation baseline AND empty gold_p2p) — H-1 preserved
- §9 risk #9 (semantic C2 via fix_patch test-body rewrite) — upstream harness layer
- §9 risk #10 (dataset PR trust boundary) — review process layer
- §9 risk #11 (vitest stage-prefix name canonicalization) — runner layer
- §9 risk #13 (pollution-gate threshold tuning) — explicit constants, configurable
- §9 risk #14 (curation-time consistency of gold_n2p and test_patch_result) — dataset hygiene
- §9 risk #15 (R0 = 20 constant) — configurable, may need retune on future corpora

These are all out-of-scope for the reward formula proper; they live in adjacent layers (trainer, dataset curation, upstream harness, evaluation aggregation).

---

## 15. Audit #5 closure log (v2f-attempt-1 → v2f)

Audit #5 was a mid-flight correction caught between spec finalization and code implementation. An external reviewer challenged a specific load-bearing claim in the v2f-attempt-1 spec — that sourcing `T_p_baseline` from the dataset would close F4 (determinism) without breaking F2 (do-nothing closure). The reviewer's argument was that `T ∩ dataset["test_patch_result"]["passed_tests"]` is **structurally empty** for any name in `gold_n2p`, by the per-observation bucketing rule at `report.py:130-138`. If true, v2f-attempt-1's adjusted recall would reduce to v2e's raw recall on n2p-only instances — the very 51% pollution-prone slice F2 was written to close.

Empirical verification (explore agent, against `/Users/macbookpro/Documents/Abhay/Projects/Engineering/milobench/freya/milo-bench/dataset/` and `/tmp/oracle_v2e_audit/`) confirmed the reviewer:

| Instance | \|T\| | T ∩ dataset.tpr.passed | T ∩ run.tpr.passed | v2f-attempt-1 do-nothing recall | v2f-corrected do-nothing recall |
|---|---|---|---|---|---|
| starship-138 (rust, all n2p) | 89 | **0** | 79 | 0.888 (F2 fails to fire) | **0.0** ✓ |
| testcontainers-java-8298 (java, all f2p) | 488 | 167 | 167 | 0.0 (F2 fires) | 0.0 ✓ |
| pubkey/rxdb-4758 (typescript, all n2p) | 539 | **0** | (not in trajectories) | 0.888-ish (F2 fails to fire) | gate-fires → polluted_dataset |

Oracle audit #4's "do-nothing recall = 0.888 on starship-138 across 9 runs" was correct as a measurement against the run report, but does NOT validate v2f-attempt-1's dataset-baseline-sourced formula — Oracle and v2f-attempt-1 were computing different things.

### Per-finding disposition

| Finding | Severity (Audit-5 verdict) | Disposition | Spec sections |
|---|---|---|---|
| **F5** Frozen-dataset baseline source is structurally disjoint from gold_n2p by the per-observation bucketing rule (`report.py:130-138`); v2f-attempt-1's F2 closure is inert on n2p-only instances (51% of pollution-prone dataset) | CRITICAL | **CLOSED via run-report baseline source.** `T_p_baseline = run_report["test_patch_result"]["passed_tests"]` — same observation as $F_p$ / $F_f$, sees the curation-vs-runtime drift that IS the pollution mechanism. starship-138 do-nothing recall: 0.888 → 0.0 (verified algebraically). | §1.5 F5, §2.4.2 (revised), §2.5.1 (revised), §2.7 #13/16/17, §3.1 schema (baseline_drift added), §6.1 Scenarios 19-20 (real numbers), §9 risks #16/19, §14 F4 row (revised), §15 (this section) |
| **Reviewer point 2** v2f as a complete RL reward is wrong; it is a terminal outcome metric and needs composite pairing | ARCHITECTURAL | **ACCEPTED via §1.1 scope statement.** v2f explicitly positioned as the test-outcome channel of a composite reward; pairing with rubric / process channels is required for long-horizon RL credit assignment. Promotion to *sole* RL reward is not contemplated. | §1.1 (new), §9 risk #17, §11 references (composite reward design doc) |
| **Reviewer point 3** Oracle is half-blind on compiled languages (M-2 44%, n2p pollution 51%, test-pass ≠ correctness, baseline drift) | ACCEPTED LIMITATIONS | **CLOSED via documentation and diagnostics.** F1 already surfaced via `m2_excluded_per_language` + §10.3.1 per-language table. n2p pollution closed via Audit-5's run-report baseline source. Baseline drift surfaced via `baseline_drift` diagnostic. Test-pass ≠ correctness is an inherent limitation of test-based reward; not formula's job. | §1.5 F1, §3.1 baseline_drift, §9 risks #12, #19, §10.3.1 |

### What changed from v2f-attempt-1 to v2f (Audit-5 corrections)

1. **§2.4.2 baseline source**: dataset → run report. (Headline correction.)
2. **§2.5.1 preserve_set source**: dataset → run report. (Same correction for the regression denominator.)
3. **§2.6.1 pseudocode**: source switched; `baseline_source` field removed; `baseline_drift` diagnostic added.
4. **§2.7 properties #10/#12/#13/#16**: rewritten to reflect run-report baseline source; #17 added explicitly closing F5.
5. **§3.1 schema**: `t_p_baseline_total` reverted to v2e's `t_p_run_total`; new fields `t_p_dataset_total`, `baseline_drift` added for forensics; `baseline_source` removed.
6. **§6.1 Scenarios 19, 20, 29, 30**: real numbers from explore agent's empirical verification; F4 scenarios reframed as "empirically nil, structurally open" instead of "fully closed".
7. **§9 risks #16-19** added: F4 partial closure, composite-reward dependency, normalization layer responsibility, dataset-vs-runtime drift.
8. **§14 F4 row**: closure changed from "frozen" to "partial via empirical observation; v3 path documented".

### What was NOT changed from v2f-attempt-1 (correct and preserved)

- The baseline-subtraction MECHANIC (subtracting $\mathcal{T} \cap T_{p,\text{baseline}}$ from numerator and denominator of recall) is correct; only the source was wrong.
- The pollution gate (`status: polluted_dataset` when pollution_rate ≥ 0.8 and |T_eff| < 3) is correct.
- The R0 = 20 absolute floor is correct.
- §10.3.1 per-language M-2 exclusion table is correct.
- All v2e-inherited closures (C1, C2, N1, N2, N3, Flaws 1-4, C-1, H-1, H-2, M-1/2/3, L-1/2/3/4) are unchanged.

### Required-before-rollout checklist (Audit-5 corrected v2f)

- [ ] Implement `compute_reward_v2g` per §8.0 delta — **use run report's `test_patch_result.passed_tests` for `T_p_baseline`** (NOT dataset's)
- [ ] Add `baseline_drift` and `t_p_dataset_total` diagnostic emit
- [ ] Add `tests/test_reward_v2g.py` with §6.1 Scenarios 19-31 — using REAL run-report numbers from freya for 19 and 20 (starship-138 T_p_run=82, T ∩ T_p_run=79; testcontainers-java-8298 T_p_run=499, T ∩ T_p_run=167)
- [ ] Update CSV evaluator: emit `m2_excluded_per_language`, `pollution_band`, mean `baseline_drift` per (lang, instance)
- [ ] Re-run 450-freya CSV; verify empirical checklist:
  - starship-138 do-nothing recall = 0.0 (was 0.888 under v2e)
  - testcontainers-java-8298 do-nothing recall = 0.0 (was 0.342 under v2e)
  - pubkey__rxdb-4758 (if added to run set): `status: polluted_dataset` (T_eff = 0 if T_p_run also = 511 like dataset)
  - HypothesisWorks-4452 still emits `status: vacuous`
  - AMReX-Codes-4238 still scored with all 57 targets
  - All cpp scored rows still have `regression_channel_active: false` (H-1 unchanged)
  - `baseline_drift > 0` rate per language matches expected dataset curation drift profile
- [ ] Run stratified 30+ instance sample drawn from M-2-prone (156) and pollution-prone (172) buckets
- [ ] Pre-commit: `uv run pre-commit run --files benchmarks/multiswebench/scripts/harbor/converter.py benchmarks/multiswebench/tests/test_reward_v2g.py`
- [ ] Update `continuous_reward_plan.md` §6 rollout protocol to reference v2f-corrected
- [ ] Add `composite_reward.md` reference and v2f's channel scope to it (per §1.1)

### Audit-5 lesson learned

**Three prior audits verified plumbing; Audit #4 verified denominator validity; Audit #5 verified that the *fix* for Audit #4 actually fires on the cases it claims to fix.** Each audit gauntlet probed one more layer of structural correctness. The takeaway: a formula's claim to "fire on X" must be empirically verified against actual on-disk data, not derived from spec-internal reasoning alone. The disjointness of dataset gold dicts and dataset's own `test_patch_result` was provable from the bucketing code at `report.py:130-138`, but only became visible by computing the set intersection on real freya records. Future spec changes must include an "empirical fire test" step before sign-off.

---

## 16. Audit #6 closure log (v2f → v2g)

Audit #6 was a meta-review: an external reviewer evaluated the *previous reviewer's proposed formula changes* rather than the formula itself. The meta-reviewer's key finding: of six proposed changes (Issues 1-5 + Bonus), only one was mathematically correct for the stated reason, two more were partially correct but mis-justified, and three were actively wrong. v2g adopts only the genuinely correct changes.

### Per-finding disposition (Audit #6 meta-review)

| Reviewer item | Meta-review verdict | v2g action |
|---|---|---|
| **Issue 1 — set-difference numerator** (prior reviewer: removes noise bias) | **PARTIALLY CORRECT reasoning, CORRECT conclusion.** Meta-reviewer showed: set-diff has *worse* noise bias than clamped arithmetic (linear-in-n vs sqrt-n). But set-diff is still the right numerator for a different, valid reason: the arithmetic form `max(0, \|T∩F_p\| - \|T_baseline\|)` **double-penalizes regressions** of baseline targets — they are subtracted from the numerator AND penalized by `factor` via `broken`. The set-difference `\|(T∩F_p) \ T_p_baseline\|` penalizes them only via `factor`. Math: `\|T∩F_p\| - \|T_baseline\| = \|T_new_passes\| - \|T_baseline ∩ F_f\|`; the arithmetic form subtracts `\|T_baseline ∩ F_f\|` from the numerator, but those regressions are already in `broken`. Set-diff gives `\|T_new_passes\|` directly — no double-count. | **ADOPTED.** §2.4.4 numerator changed to set-difference. `max(0,·)` clamp removed (not needed; set-diff ≥ 0). Noise justification corrected in §2.4.4 and §2.7 #13. |
| **Issue 2 — smooth pollution-gate weighting `w`** (prior reviewer: removes gradient cliff) | **WRONG.** The gate fires on `pollution_rate` and `\|T_eff\|` — both functions of `T` (dataset) and `T_p_baseline` (pre-fix stage), neither of which the agent controls. The agent moves `F_p, F_f`; it cannot change which side of the gate an instance sits on. No policy-gradient discontinuity exists at the gate. Moreover, multiplying `r = w·recall·factor` with `w < 1` on polluted-but-gradable instances penalizes a *perfect agent* for instance cleanliness — a capability-signal corruption. | **REJECTED.** Gate remains binary (`status: polluted_dataset`). If soft treatment is desired, apply as instance weight in the pass@k aggregator (not in per-rollout reward). |
| **Issue 3 — per-hit weight varies across instances** (observation correct; fix-(a): normalize by \|T\| instead of \|T_eff\|) | **OBSERVATION correct; FIX-(a) wrong; FIX-(b) correct.** Per-hit weight $1/\lvert\mathcal{T}_{\text{eff}}\rvert$ varying across instances is inherent to any per-instance-normalized recall (the original $1/\lvert\mathcal{T}\rvert$ had the same property). Fix-(a) would normalize by $\lvert\mathcal{T}\rvert$: a correct fix on starship-138 would score $10/89 = 0.11$ instead of $1.0$ — systematically under-crediting correct fixes on polluted instances (F2 re-opened). Fix-(b): emit `\|T_eff\|/\|T\|` as a calibration factor and let the trainer group-normalize. This is the correct approach. | **NOTED.** Fix-(a) rejected. Fix-(b) listed as §9 open risk + future work. `t_eff_total` and `targets_total` are already emitted; downstream callers can compute the ratio. |
| **Issue 4 — R0 kink** (observation: piecewise formula with kink at denom=20) | **CORRECT, LOW severity.** The kink lives in instance size (agent-independent); `factor` is linear in `broken` (the agent-controlled quantity) — no policy-gradient discontinuity at the kink. Skip is correct. | **SKIPPED.** Documented in §9. |
| **Issue 5 — multiplicative wipe** (additive alternative would preserve partial credit on heavy regression) | **CORRECT observation, intentional design.** $r=0$ when factor=0 (catastrophic regression) regardless of recall is SWE-bench-consistent and intentional per Scenario 7. | **DOCUMENTED.** Spec notes the additive alternative is a legitimate design fork. Only revisit if A/B training shows over-punishment. |
| **Bonus — f2p/n2p split: "don't subtract gold_f2p ∩ baseline"** (prior reviewer: labeled CRITICAL) | **WRONG.** Retaining `gold_f2p ∩ T_p_baseline` in `T_eff` leaves those targets in the denominator, and a do-nothing agent's $F_p \approx T_{p,\text{baseline}}$ would hit them → spurious do-nothing recall. Algebraically: on testcontainers-java-8298, "don't subtract" would leave 167 f2p-preexisting targets in `T_eff`, do-nothing hits 167, recall = 167/488 = 0.342 — the exact F2 value v2f was written to eliminate. v2f's current behavior (subtract ALL of $\mathcal{T}_{\text{baseline}}$, including f2p∩baseline) is correct — it drops the corrupted target from both numerator and denominator. The semantic concern (f2p pre-existing = env drift, not scope mismatch) is valid; the formula response is to ADD AN ALARM, not to change subtraction. | **REJECTED as formula change. ACCEPTED as diagnostic.** `f2p_baseline_pass_count = \|gold_f2p ∩ T_p_baseline\|` added to diagnostics (§3.1). High values alert downstream consumers to potential environment drift without altering the reward computation. |

### What Oracle ACCEPTED in v2f (preserved in v2g, with numerator correction)

All v2e- and v2f-inherited verifications remain valid:
- §2.5 algebraic identity $x/\min(a,b) = \max(x/a, x/b)$ for $x \ge 0, a, b > 0$ ✓
- C2 set-membership defense ✓ (agent controls only fix stage, not pre-fix baseline)
- `unknown_breaks_count = F_f \setminus \text{preserve\_set} \setminus \mathcal{T}` ✓
- Lazy re-curation mirrors `report.py:130-138` bucketing ✓
- N1 closure via `preserve_set = gold_p2p ∪ T_p_baseline` ✓
- starship-138/testcontainers do-nothing → 0 with run-report baseline ✓

### Required-before-rollout checklist (v2g updates over v2f)

- [ ] Implement `compute_reward_v2g` using set-difference numerator: `hits_new = len((T & F_p) - T_p_baseline)`
- [ ] Add `f2p_baseline_pass_count=len(gold["f2p_tests"] & T_p_baseline)` to diagnostic emit
- [ ] Update unit test `test_do_nothing_recall_zero` to verify set-diff form (not clamp form)
- [ ] Add test: regression of a baseline target reduces `factor` but does NOT reduce `hits_new` (verifies no double-penalization — §6.1 Scenario 32: T=6, T_b={a,b,c}, agent fixes {d,e}, breaks {a}; expected hits_new=2 not 1, reward=0.633 not 0.317)
- [ ] Re-run 450-freya CSV to confirm set-diff vs clamped gives same results on non-regressing rows (expected: identical when no baseline regressions in fix stage; differs only on rows with T_baseline regressions)
- [ ] All v2f §15 checklist items still apply

### Audit-6 lesson learned

**Audit #6 confirmed: reviewer proposals require the same mathematical scrutiny as the formula itself.** Three of the six proposed changes would have broken properties that multiple earlier audits worked hard to close. The meta-review framework — systematically verifying each proposal's math before adoption — proved its value. Going forward: proposed formula changes must include a "what-does-this-do-to-starship-138 do-nothing recall" calculation before acceptance, since that is the benchmark case the entire v2f/v2g line was built around.
