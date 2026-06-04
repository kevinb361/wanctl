---
phase: 227
cycle: 2
reviewers: [codex]
reviewed_at: 2026-06-04T14:05:00Z
plans_reviewed: [227-01-PLAN.md, 227-02-PLAN.md, 227-03-PLAN.md, 227-04-PLAN.md]
external_cli: codex-cli 0.135.0
prior_cycle: 1
prior_cycle_high: 6
current_cycle_high: 0
---

# Cross-AI Plan Review — Phase 227 (Cycle 2)

This is **cycle 2** of the plan-convergence loop. The 4 plans were replanned (commit 332c454)
specifically to resolve the 6 HIGH concerns from cycle 1. Codex CLI re-reviewed the replanned
text with the cycle-1 fixes called out explicitly; this Claude Code session independently
verified the load-bearing source facts before recording the verdict (notes inline under "Claude
verification"). Phase 227 deploys candidate `diffserv4 wash` on Spectrum under the Snapshot A
anchor and captures a matched 226-vs-227 dataset (incl. a marked-EF realtime-protection arm) for
the Phase 228 verdict, under the SAFE-13 controller-path-freeze invariant.

## Cycle-1 → Cycle-2 HIGH Disposition (at a glance)

| # | Cycle-1 HIGH | Fix landed in | Cycle-2 verdict |
|---|--------------|---------------|-----------------|
| 1 | D-09 armed abort not real (relied on dry-run-only phase226-restore.sh) | 227-03 (`scripts/phase227-rollback.sh`) | **RESOLVED** |
| 2 | SAFE-13 hole — `wan_controller_state.py` unprotected | 227-04 Task 0 (`controller_targets`) | **RESOLVED** |
| 3 | Summary parser did not parse iperf JSON (jitter/loss/throughput) | 227-01 Task 2 (BUILT parsing) | **RESOLVED** |
| 4 | iperf concurrency — third flow collides on same REF_PORT | 227-01 (distinct `--ef-ref-port` = REF_PORT+2) | **RESOLVED** |
| 5 | qdisc-gate bare-grep false-pass | 227-02 (tokenize cake line, fail-closed proof states, bounded timeout) | **RESOLVED** |
| 6 | Health-endpoint ambiguity + vague abort triggers | 227-03 (single SoT `10.10.110.223:9101/health` + concrete triggers) | **RESOLVED** |

All 6 are addressed in the replanned text. No HIGH concern remains unresolved this cycle.

## Codex Review

### 227-01 — Marked-EF Arm + Summary Parsing

**Summary** — Materially fixes the AB-04 evidence gap: marked EF is additive, default-off, uses a
separate EF port, and the summary generator is explicitly required to BUILD iperf-JSON parsing for
unmarked UDP, unmarked TCP, and marked EF. Text is specific enough that an executor will not
confuse "existing summary field" with "new parsing required."

**Cycle-1 HIGH verification**
- **#3 Summary parser did not parse iperf JSON — RESOLVED.** Plan repeatedly states this must be
  built, names the artifact files, required fields, validity behavior, and tests valid/error fixtures.
- **#4 iperf concurrency / same-port collision — RESOLVED.** Marked-EF arm uses `--ef-ref-port`
  (default `REF_PORT+2`); tests assert EF port differs from `REF_PORT`.

**Strengths** — Preserves D-03 (opt-in additive); validity checks on ALL iperf JSON, not just EF;
cleanly separates GATE-01 matched-load use from AB-04 marked-vs-unmarked comparison; regression
tests cover port separation, default-off, summary parsing, invalid JSON.

**Concerns**
- **MEDIUM (NEW):** `EF_CLEAN_MARK` proof is still soft — action text drifts toward "successful
  `--dscp`/`--tos` set" rather than observed DSCP evidence. Close by requiring a concrete per-run
  DSCP observation or explicitly setting `clean_mark=false` unless observed.
- **MEDIUM (NEW):** EF reflector port availability is documented but not preflighted. Add a cheap
  `iperf3` probe against `REF_HOST:EF_REF_PORT` before the off-peak capture.
- **LOW (NEW):** iperf-JSON key expectations may be version-sensitive; accept known UDP/TCP summary
  variants while still failing closed on errors.

**Suggestions** — Add `ef_ref_port_reachable=true|false` to the manifest; make
`ref-ef-marking.NN.txt` structured (key/value or JSON) so 227-04 can consume it deterministically.

**Risk Assessment: MEDIUM.** Carried HIGHs fixed; residual is evidence-quality risk around proving
the EF mark is actually present and avoiding a wasted window if port 5203 is not listening.

> **Claude verification:** CONFIRMED against source. `phase226-baseline-summary.py` today parses
> ONLY CAKE tin counters + health restart/transition rates — zero iperf-JSON parsing (grep for
> `iperf|jitter|end.sum|ref_udp` = 0 hits). The plan's "must be BUILT, not surfaced" framing is
> accurate, and the must-haves + Task 3 fixtures lock it. Harness `REF_PORT` default is 5201
> (single port today), so the distinct `REF_PORT+2` EF port genuinely removes the collision. The
> two MEDIUM evidence-quality concerns are real but are quality hardening, not HIGH blockers.

### 227-02 — qdisc Verify Gate

**Summary** — Closes the qdisc false-pass cleanly. Replaces bare-grep behavior with strict parsing
of exactly one `qdisc cake` line, a closed mode-token set, explicit proof states, and bounded SSH.

**Cycle-1 HIGH verification**
- **#5 qdisc-gate false-pass — RESOLVED.** Plan requires tokenizing only the cake line, exactly one
  allowed mode token, explicit `missing|ssh_failed|no_cake|ambiguous|<mode>` states, non-zero on
  every mismatch, and SSH timeout bounds.

**Strengths** — Fail-closed behavior concrete; tests cover success, wrong mode, missing device, no
cake, ambiguity, SSH failure; reusable for both `besteffort` precheck and `diffserv4` verify;
read-only target posture explicit.

**Concerns**
- **LOW (NEW):** Test-only input hooks should be clearly isolated from operator use (named
  test-only flags/env; dry-run/operator paths cannot use stale fixture input).
- **LOW (NEW):** Wrong-mode proof state should preserve the actual wrong token, not collapse into
  generic mismatch; tests should assert it.

**Suggestions** — Emit the raw isolated cake line in JSON proof for auditability alongside the
resolved token; include exact SSH timeout settings in `--dry-run`.

**Risk Assessment: LOW.** Previous HIGH genuinely addressed; main risk is implementation
sloppiness, not plan ambiguity.

> **Claude verification:** The plan's interfaces block specifies the closed mode-token set,
> per-NIC proof-state resolution, and concrete SSH timeout flags (`ConnectTimeout=5` + `timeout 8`)
> — these were the exact cycle-1 gaps and are now in plan text. Confirmed RESOLVED.

### 227-03 — Capture Sequence + Flip + Rollback

**Summary** — The production-touching plan. Now defines a real `phase227-rollback.sh`, keeps the
live flip operator-gated, uses the standard deploy path, verifies qdisc mode before candidate
capture, leaves diffserv4 live for Phase 228, and explicitly excludes the dry-run-only
`phase226-restore.sh` from the live abort path.

**Cycle-1 HIGH verification**
- **#1 Armed abort not real — RESOLVED.** Plan creates `scripts/phase227-rollback.sh`, requires
  `--confirm` for mutation, reapplies Snapshot A besteffort bytes, deploys, restarts, verifies
  besteffort on both NICs, checks health, records proof. It does not call `phase226-restore.sh`.
- **#6 Health-endpoint ambiguity / vague abort triggers — RESOLVED (with one precision
  suggestion).** Endpoint consistently `http://10.10.110.223:9101/health`, not localhost. Abort
  triggers concrete: qdisc-verify failure, health fetch/status failure, systemd active/restart-
  counter checks. Remaining wording precision: spell the health predicate as top-level
  `.status == "healthy"`.

**Strengths** — Correct D-07 order (fresh besteffort+EF before flip, then candidate+EF); production
mutation checkpoint-gated; rollback proof includes config hashes, qdisc proof, systemctl state,
restart counters, journal excerpt; explicitly leaves diffserv4 live for Phase 228.

**Concerns**
- **MEDIUM (NEW):** Rollback raw-dir readiness is assumed at the checkpoint but not mechanically
  preflighted before the flip. Add `precheck --rollback-raw-dir <dir>` to verify
  `deployed-spectrum.yaml`, hash it, confirm `diffserv: besteffort`, and dry-run the rollback
  command before mutation.
- **MEDIUM (NEW):** The "exactly one line" `spectrum.yaml` flip is operator-instruction only. Add a
  predeploy diff guard permitting only `diffserv: besteffort -> diffserv4` and rejecting DL/UL/
  `allow_wash`/`docsis_mode` drift.
- **LOW (NEW):** Directory naming inconsistent — some text says `baseline-<UTC>`/`candidate-<UTC>`,
  task action mentions `<evidence>/besteffort`/`<evidence>/candidate`. Standardize on timestamped
  names.

**Suggestions** — Add a `status` subcommand (current mode, health status, service active,
`NRestarts`, rollback raw-dir readiness); in the rollback script define the Snapshot A comparison
source explicitly (recorded hash/proof file or the raw-dir artifact).

**Risk Assessment: MEDIUM.** Carried rollback + health HIGHs fixed in plan text. Because this
touches production WAN shaping, residual risk is mostly human-edit drift and rollback-preflight
discipline.

> **Claude verification:** CONFIRMED against source. `phase226-restore.sh` hard-errors on any
> non-dry-run invocation (line 138: "Phase 226 restore proof is dry-run only; mutation-capable
> restore behavior is deferred to Phase 228."). `phase227-rollback.sh` does not exist yet — correct,
> 227-03 Task 1b creates it; the plan's key_links and must-haves wire the runbook abort to it (NOT
> phase226-restore.sh). Harness `HEALTH_URL` default is `http://10.10.110.223:9101/health` (line 8),
> so the single-source-of-truth choice matches the 226 harness exactly and the 127.0.0.1:9101
> ambiguity is removed. The two MEDIUM preflight/diff-guard concerns are sensible production-safety
> hardening and worth folding before the operator checkpoint, but they are not HIGH — the armed
> abort and health contracts are both now real.

### 227-04 — SAFE-13 + Evidence Completeness

**Summary** — Closes the confirmed SAFE-13 protection hole by adding `wan_controller_state.py` to
the protected controller-target list, runs the boundary check against `v1.48`, and adds a readiness
gate so Phase 228 does not discover missing evidence late.

**Cycle-1 HIGH verification**
- **#2 SAFE-13 hole for `wan_controller_state.py` — RESOLVED.** Plan explicitly adds
  `src/wanctl/wan_controller_state.py` to `controller_targets`, adds a regression test, and requires
  the boundary proof to include it in `expanded_protected_files`.
- **#3 Summary-parser signals for AB-04 — RESOLVED as a dependency.** 227-04 does not build the
  parser but requires the new unmarked/marked iperf fields from 227-01 before verdict readiness
  passes.

**Strengths** — Minimal SAFE-13 fix (adds the missing file without broadening behavior); boundary
proof requires both controller diff count AND ATT diff count to be zero; correctly allows
`spectrum.yaml`/bridge nft changes while freezing controller path; completeness gate is schema-aware
rather than demanding identical tin names.

**Concerns**
- **MEDIUM (NEW):** Completeness checker lacks an exact threshold-to-summary path map. "UL
  stability" and "per-tin separation inputs" should map to concrete JSON paths so Phase 228 and the
  readiness gate cannot disagree. Close with a `threshold key -> required summary path(s) -> allowed
  mode-dependent exceptions` table.
- **MEDIUM (NEW):** Canonical iperf-validity source not fully specified (summary flag vs per-run
  validity record vs marking file). Define one machine-readable validity schema from 227-01 and
  require 227-04 to consume it.
- **LOW (NEW):** Source-parsing the SAFE-13 script for tests is brittle; prefer invoking/exporting
  the expanded target list if practical.

**Suggestions** — Add fixture tests mimicking both besteffort and diffserv4 tin names while
preserving stable top-level fields; make completeness failure messages include exact missing JSON
paths.

**Risk Assessment: MEDIUM.** SAFE-13 fixed. Evidence readiness is directionally right, but the
field mapping should be pinned before implementation so the checker does not pass different signals
than Phase 228 consumes.

> **Claude verification:** CONFIRMED against source. `wan_controller.py` line 64 imports
> `WANControllerState` from `wanctl.wan_controller_state` — it is controller-path. The current
> `controller_targets` list (lines 67-72) contains wan_controller.py, queue_controller.py,
> cake_signal.py, alert_engine.py, fusion_healer.py (+ att.yaml) but NOT wan_controller_state.py,
> and `expand_protected_files()` only expands targets ending in "/" (line 110) — so the bare file is
> never auto-discovered. The hole is real and 227-04 Task 0's explicit-add fix is exactly the right
> shape. The two MEDIUM mapping/validity-schema concerns are real implementation-precision risks
> (the readiness gate and the 228 verdict must read the same paths) but are not HIGH blockers.

## Overall Risk

**MEDIUM.** Codex's verdict: the six cycle-1 HIGH concerns are resolved in the replanned text; no
still-unresolved HIGH remains after this cycle. Residual issues are implementation precision and
production-run preflight gaps (MEDIUM/LOW), not plan-level blockers. This Claude Code session
independently verified all six load-bearing source facts (dry-run-only restore script, missing
SAFE-13 entry + expand semantics, controller-path import, zero iperf parsing today, harness health
URL + single REF_PORT) and concurs.

## Consensus Summary

Single external reviewer (Codex) this cycle, cross-checked against repository source by the
executing Claude Code session. The review is grounded — every cycle-1 HIGH disposition was checked
against the actual code, not taken on faith.

### Agreed Strengths
- All six cycle-1 HIGH fixes landed in the replanned text and are source-consistent: a genuine
  mutation-capable rollback (227-03), the SAFE-13 protected-file hole closed (227-04), built
  iperf-JSON parsing (227-01), distinct EF reflector port (227-01), fail-closed qdisc parsing with
  explicit proof states (227-02), and a single health-endpoint source of truth + concrete abort
  triggers (227-03).
- Production safety posture is sound: the live flip stays operator-gated, the rollback requires
  `--confirm`, predeploy + qdisc-verify gates fail-closed, and diffserv4 is left live for the 228
  verdict (single deploy).

### Agreed Concerns (residual — none HIGH)
- **EF marking proof quality (227-01, MEDIUM).** `EF_CLEAN_MARK` should rest on observed DSCP
  evidence, not iperf accepting `--dscp`/`--tos`; reflector port should be preflighted.
- **Rollback / flip preflight discipline (227-03, MEDIUM).** Mechanically preflight the rollback
  raw-dir before the flip; add a predeploy diff guard that allows only the one diffserv line to change.
- **Threshold→summary path map + canonical validity schema (227-04, MEDIUM).** Pin the exact JSON
  paths the completeness gate and the Phase 228 verdict both read, and a single iperf-validity schema.

### Divergent Views
None — single external reviewer; no reviewer-vs-reviewer disagreement. Codex's HIGH dispositions
matched the executing session's independent source verification on all six items.

### Recommended Action
Convergence reached: **0 HIGH concerns remain.** The plans are ready to execute. The residual
MEDIUMs (EF marking proof, rollback/flip preflight, completeness path-map) are worth folding as
in-plan hardening before Wave 2 executes, but they do not block the loop. If folding them, they can
be absorbed into the existing plan tasks without restructuring.
