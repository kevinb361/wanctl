---
phase: 228
reviewers: [codex]
reviewed_at: 2026-06-04T17:43:37Z
plans_reviewed: [228-01-PLAN.md, 228-02-PLAN.md, 228-03-PLAN.md, 228-04-PLAN.md]
---

# Cross-AI Plan Review — Phase 228

> Reviewer set: Codex (`codex-cli 0.135.0`). Claude skipped (self — review ran inside Claude Code).
> Load-bearing factual claims in the Codex review were independently verified against the repo
> before this file was written; verification notes are inline under **[Verified]**.

## Codex Review

## Summary

The phase decomposition is mostly sound: verdict first, rollback second, closeout last, with SAFE-13 kept explicit. The biggest issue is Plan 228-01 rests on a false current-state assumption: the authoritative diffserv4 candidate summary currently has `interfaces: {}` because the existing parser recognizes `Tin 0` style output, while diffserv4 CAKE output is columnar (`Bulk / Best Effort / Video / Voice`). Without fixing and testing that parser path, the tin-separation gate will be weak or fail-closed for the wrong reason.

## PLAN 228-01

### Strengths

- Correctly keeps tin separation as an additive derived summary field, not embedded ad hoc inside gate evaluation.
- Good single-source discipline for `NOISE_BAND_MS`.
- Handles besteffort single-tin as valid "no separation," which is important for Snapshot A.
- Tests are aimed at the right invariants: threshold source, multi-tin behavior, single-tin guard, additive preservation.

### Concerns

- **HIGH:** Existing candidate summary has `interfaces: {}`. Raw diffserv4 `tc` output is columnar, not `Tin N` blocks, so current `parse_tc_qdisc()` will not populate tins for candidate data. The plan must explicitly add/test columnar CAKE parsing or tin separation will not be evidence-based.
- **HIGH:** The plan assumes tin ids `0..3`, but diffserv4 output uses names/columns: `Bulk`, `Best Effort`, `Video`, `Voice`. "BE tin is 0" is true for besteffort output, not for columnar diffserv4 text unless normalized deliberately.
- **MEDIUM:** Re-emitting summaries changes `baseline-summary.json` and `BASELINE-SUMMARY.md`; existing `artifact-sha256.txt` files include hashes for those files, so provenance manifests may become stale unless explicitly handled.
- **LOW:** "Only additive diff" is too narrow if parser support causes `interfaces` to change from `{}` to real tins. That is a desired correction, but the plan currently frames any pre-existing numeric change as suspect.

### Suggestions

- Add a required real-fixture test using the committed candidate `tc-qdisc-spec-router.during.txt` and assert all four diffserv4 tins parse.
- Normalize tin ids with both stable ids and cake names, e.g. `be_tin: {"id": "besteffort", "cake_name": "Best Effort"}`.
- Add a `parser_correction` note/provenance field if candidate `interfaces` changes from empty to populated.
- Either update `artifact-sha256.txt` after re-emit or create a separate `phase228-reemit-sha256.txt` and have Plan 228-02 pin both original capture manifest and re-emitted summary hashes.

### Risk Assessment

**HIGH** until columnar CAKE parsing is made explicit and tested against the authoritative candidate artifacts. After that, risk drops to **LOW/MEDIUM**.

## PLAN 228-02

### Strengths

- Good pre-registration posture: thresholds JSON is the source of gate literals.
- Evaluates all intended gate families and separates headline vs corroborating gates.
- Good fail-fast intent with `GateEvalError`.
- Accept path testing is a strong guard against reverse-fit logic.

### Concerns

- **HIGH:** It depends on 228-01 producing trustworthy `tin_separation`; given the parser issue, this plan can produce a reject for the wrong tin-separation reason.
- **MEDIUM:** Percent increase gates need defined zero-baseline behavior. `restart_rate` is currently `0.0` for both baseline and candidate; future candidate >0 would otherwise risk divide-by-zero or ambiguous infinity.
- **MEDIUM:** `gate_ul_stability` says "if a UL p99 field is present," but current summaries do not appear to expose a UL p99 field. The verdict should explicitly mark that subcheck `not_observed`/`not_applicable`, not silently imply full UL p99 coverage.
- **MEDIUM:** "Primary interface" for tin separation is not defined. For Spectrum, `spec-router` vs `spec-modem` maps to different directions; the gate should state whether it requires download, upload, or both.
- **LOW:** `safe13_lift:false` is appropriate for the authoritative reject, but the evaluator should not make that look like an automatic result for every hypothetical accept unless that is intentional.

### Suggestions

- Define percent-gate math for baseline zero: candidate zero passes; candidate nonzero fails with `regression_pct: null` and `regression_relation: "baseline_zero_candidate_positive"`.
- Make `gate_ul_stability` a structured composite with each metric labeled `pass`, `fail`, or `not_observed`.
- Define tin-separation interface semantics: both NICs required, or `spec-router` primary with `spec-modem` corroborating.
- Include current hashes of the re-emitted summary JSONs in verdict provenance, not only `artifact-sha256.txt` contents.

### Risk Assessment

**MEDIUM/HIGH** because verdict integrity depends on the parser/provenance fixes. The gate framework itself is well-scoped.

## PLAN 228-03

### Strengths

- Correctly marks the live rollback as `autonomous:false`.
- Uses the existing `phase227-rollback.sh --confirm` mutation path instead of inventing a new deploy path.
- Triple proof is the right shape: repo, production qdisc on both NICs, health.
- File-fed proof tests are appropriate and avoid live-host dependency.

### Concerns

- **HIGH:** The example real rollback command omits `--out`, so `phase227-rollback.sh` will write to its Phase 227 default proof path. That pollutes prior phase evidence and weakens Phase 228 traceability.
- **MEDIUM:** Replacing the `configs/spectrum.yaml` annotation after deploy means repo and deployed file comments can drift. Behavior is unchanged, but it conflicts with the "Snapshot A byte restore" language.
- **MEDIUM:** Repo proof only compares selected lines. That can miss unrelated Spectrum config drift introduced during rollback.
- **MEDIUM:** Health wording says `GREEN`, while existing health scripts use `status == "healthy"`. The proof should normalize/define accepted health states.
- **LOW:** The new proof generator should either reuse the rollback script's qdisc proof or include bounded retry; a single immediate qdisc read after restart can be racy.

### Suggestions

- Change the rollback command to pass `--out .planning/phases/228-verdict-evidence-gated-decision-closeout/evidence/phase227-rollback-run-proof.json`.
- Decide whether `configs/spectrum.yaml` should be byte-identical to Snapshot A or semantically restored plus annotated. Do not claim both.
- Prefer full redacted config comparison against Snapshot A, with secret-safe redaction, plus explicit key checks.
- Have proof JSON include `rollback_script_proof`, `phase228_qdisc_verify`, and health payload summary.

### Risk Assessment

**MEDIUM/HIGH** because this is the only production-mutating plan. The gating posture is good, but the `--out` omission and byte-restore ambiguity should be fixed before execution.

## PLAN 228-04

### Strengths

- Good closeout discipline: durable SAFE-13 decision, docs, changelog, todo closure, EF seed.
- Correctly defers milestone archival.
- SAFE-13 boundary check uses the existing read-only script and anchor.
- The "no lift" decision is explicitly recorded, not implied.

### Concerns

- **MEDIUM:** Depends on 228-03 proof semantics. If rollback proof is only partial repo comparison, closeout may overstate "restored to Snapshot A."
- **MEDIUM:** The todo close convention is ambiguous because `.planning/todos/` has `closed`, `completed`, and `done`. The plan says check convention, which is good, but execution must choose deliberately.
- **LOW:** Docs should cite `phase228-verdict.json` and `phase228-rollback-proof.json`; avoid copying the full verdict into public-facing docs.
- **LOW:** SAFE-13 boundary check proves controller/ATT only. That is correct for SAFE-13, but closeout should not imply it verifies Spectrum config restoration.

### Suggestions

- In the SAFE-13 decision record, separate "controller no-lift proof" from "Spectrum rollback proof."
- In docs, use one headline number and link/cite evidence; keep detailed values in JSON.
- For the todo, prefer the repo's newest active convention, and include a clear moved-from/moved-to trail.

### Risk Assessment

**LOW/MEDIUM**. Mostly documentation and read-only verification; risk comes from depending on earlier evidence being precise.

## Overall Recommendation

Fix Plan 228-01 before execution: add columnar diffserv4 CAKE parsing and real artifact tests. Then tighten Plan 228-02 provenance/zero-denominator semantics and Plan 228-03's rollback `--out` plus Snapshot A proof language. With those changes, the phase plan is coherent and should achieve verdict integrity, rollback safety, and SAFE-13 no-lift closeout.

---

## Consensus Summary

Single external reviewer (Codex) this cycle; "consensus" is Codex + Claude's independent
repo verification of the load-bearing claims.

### Agreed Strengths

- Verdict-first → operator-gated rollback → closeout sequencing is correct and auditable.
- Pre-registration discipline is preserved: gate literals live only in `phase226-thresholds.json`; the verdict is a machine output that can reach `accept` (no reverse-fit).
- The triple restoration proof (repo + both-NIC production qdisc + health) is the right fail-closed shape, and the live rollback is correctly `autonomous:false` / operator-at-keyboard.
- SAFE-13 no-lift is recorded as an explicit decision, not implied; boundary check reuses the existing read-only script.

### Agreed Concerns (highest priority)

- **[HIGH — VERIFIED] diffserv4 columnar tc output is not parsed.** The authoritative candidate summary has `interfaces: {}`. **[Verified]** `scripts/phase226-baseline-summary.py` `TIN_RE = re.compile(r"^\s*Tin\s+(?P<name>\S+)")` only matches `Tin N` block output; the candidate `tc-qdisc-*.during.txt` artifacts are columnar (`Bulk / Best Effort / Video / Voice`), so no tins parse and `interfaces` is empty. Plan 228-01's must-have ("candidate carries tins 0..3") and the 228-02 `gate_tin_separation` family are therefore NOT evidence-based as written — the tin-separation gate would fail-closed on missing data rather than on a real "no useful separation" finding. The tin-id-`0..3` assumption is also wrong for columnar output (named tins, BE is not id `0`).
  - **Scope/severity note:** The *overall reject verdict is not at risk.* **[Verified]** the headline `gate_rrul_p99` reads `rrul_p99_latency_under_load_ms_mean` (345.15 → 384.91 = +11.5%, past the +5% gate) and is fully populated in both summaries — the reject stands on the headline gate alone. The HIGH is about *one of five gate families being non-evidence-based*, which weakens the "all five families evaluated against real data" guarantee D-01 claims, not about flipping the outcome.

### Other notable concerns (MEDIUM)

- **[VERIFIED] Zero-baseline percent math.** `restart_rate` is `0.0` for both baseline and candidate; `gate_restart_rate` percent-increase math needs an explicit zero-denominator rule (candidate-zero passes; candidate-nonzero fails with a labeled relation) to avoid div-by-zero / ambiguous infinity.
- **UL p99 not exposed** in the summaries — `gate_ul_stability`'s "if a UL p99 field is present" branch should explicitly emit `not_observed` rather than implying coverage.
- **Re-emit vs `artifact-sha256.txt`** — re-emitting summaries changes hashed files; provenance manifests go stale unless the plan handles it (update, or pin a separate re-emit manifest).
- **Rollback `--out` omission** (228-03) writes to the Phase 227 default proof path, polluting prior-phase evidence; pass an explicit 228 `--out`.
- **"Snapshot A byte-restore" vs annotation rewrite** (228-03) — the plan both claims byte-identical restore and rewrites the annotation comment; pick one framing. Repo proof compares only selected lines (could miss unrelated drift).
- **Health "GREEN" vs `status == "healthy"`** (228-03) — normalize accepted health states to the existing health-script vocabulary.
- **Todo close convention ambiguous** (228-04) — `.planning/todos/` has `closed`, `completed`, and `done`; execution must pick deliberately with a moved-from/moved-to trail.

### Divergent Views

None — single reviewer. Claude's independent verification agrees with every load-bearing Codex claim it checked (empty candidate `interfaces`, columnar tc format, `Tin`-only parser regex, zero restart_rate, populated RRUL p99 inputs).
