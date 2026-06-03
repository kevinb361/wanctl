# Phase 222 Research — Steering Drift Audit

**Phase:** 222 — Steering Drift Audit
**Milestone:** v1.48 Steering Runtime Drift Closure
**Date:** 2026-06-02
**Scope:** Read-only audit. No source mutation, no production touch.

---

## 1. Problem Framing

The live steering daemon on production reports runtime version `1.39` while
`src/wanctl/__init__.py` declares `__version__ = "1.45.0"`. Six milestones
(v1.40 → v1.45) of steering-relevant source evolution have not been absorbed
into the running daemon. Phase 222 must produce the evidence artifacts the
operator needs to understand exactly what changed, classify each change by
behavioral impact against the steering spine contract, and recommend a
disposition (go / mitigate / no-go) per finding before any v1.48 mutation lands.

Phase 222 itself is **planning-artifact only**. No deploy, no source mutation,
no production touch. SAFE-12 controller-path zero-diff invariant is verified
at the phase boundary.

---

## 2. Version Semantics

- **Runtime `1.39`** = the steering daemon's reported version on the running
  production host (read from steering `/health` endpoint or the binary
  artifact deployed at the time the v1.39 git tag was cut).
- **Source `1.45`** = `src/wanctl/__init__.py.__version__`. Note: `v1.45` is
  NOT a git tag in this repo (tags jump v1.44 → v1.46). The "source 1.45"
  reference point is the current working tree as of v1.47 close
  (commit `bee343b chore: remove REQUIREMENTS.md for v1.47 milestone`),
  which carries `__version__ = "1.45.0"`.

**Implication for the audit:** the source-of-truth comparison is
`v1.39 git tag` (runtime baseline) vs `v1.47 close HEAD` (source as the
audit sees it), restricted to steering-relevant paths. Where any v1.40 → v1.44
tag intersects steering source, the per-milestone classification (DRIFT-03)
must attribute changes to the correct milestone.

---

## 3. Steering Source Surface

The steering daemon source surface (in scope for the delta report and
classification) is:

```
src/wanctl/steering/
  __init__.py
  daemon.py                  # main loop, decision pipeline
  health.py                  # /health endpoint, version surface
  congestion_assessment.py
  steering_confidence.py
  cake_stats.py
src/wanctl/check_steering_validators.py
configs/steering.yaml         # schema; deployed config is operator-owned
deploy/systemd/steering.service
src/wanctl/dashboard/widgets/steering_panel.py  # observability surface
```

The phase 212 (v1.46) drift inventory established that steering version drift
is a known unaligned surface; that artifact set lives at
`.planning/milestones/v1.46-phases/212-production-inventory-and-drift-audit/`
and is the canonical predecessor evidence.

---

## 4. Controller-Path SAFE-12 Allowlist

These files are OUT of scope for steering mutation across all of v1.48 and
must remain byte-identical to v1.47 close:

- `src/wanctl/wan_controller.py`
- `src/wanctl/queue_controller.py`
- `src/wanctl/cake_signal.py`
- `src/wanctl/backends/` (all)
- `src/wanctl/alert_engine.py`
- `src/wanctl/fusion*.py` (e.g., `fusion_healer.py`)

SAFE-12 verification at the phase 222 boundary is a `git diff` against the
v1.47 close commit restricted to those paths, expected to be empty.

---

## 5. Steering Spine Contract (Invariants)

Per `CLAUDE.md` and `.planning/REQUIREMENTS.md`, every diff in scope must be
evaluated against three invariants:

1. **Binary on/off** — steering is enabled or disabled; no partial / weighted
   / blended modes.
2. **Only new latency-sensitive connections rerouted** — existing connections
   are not torn down; only new flows tagged latency-sensitive get steered.
3. **Autorate baseline RTT remains authoritative** — steering MUST defer to
   the autorate-frozen baseline RTT; it cannot mint its own baseline.

A change is contract-preserving if and only if every behavior-affecting line
is consistent with all three invariants. A change is contract-affecting if
any line could alter the binary nature of steering, the new-only-flow
rerouting semantics, or the authority of the autorate baseline RTT.

---

## 6. Per-Milestone Change Classification (DRIFT-03)

Each commit in the v1.40 → v1.47-close range touching steering source must be
classified as one of:

| Category | Definition | Default disposition (DRIFT-04) |
|----------|------------|-------------------------------|
| **behavior-changing** | Alters decision threshold, branching, rerouting trigger, restart/state recovery, autorate coupling, or any observable steering decision under any input | go/mitigate/no-go decided per-finding |
| **behavior-preserving** | Refactor, rename, type annotation, mypy/ruff cleanup, dead code removal, log-text rephrase, comment-only — no decision-affecting branch change | default **go** (low risk) |
| **observability-only** | New/changed log, metric, `/health` field, dashboard widget — purely additive surface; cannot alter decisions | default **go** (low risk) |

Edge cases:
- A log-throttle change that suppresses output but cannot affect decisions →
  observability-only.
- A type annotation that narrowed a runtime path → behavior-preserving only
  if mypy-strict was already passing the same code; otherwise behavior-
  changing.
- A `# fix(172)` storage maintenance change inside steering → behavior-
  changing (it changes when DB maintenance fires, which can affect cycle
  budget).

---

## 7. Methodology: Delta Report (DRIFT-01)

The delta report is produced by:

1. Identify the runtime baseline commit. Preferred: the commit tagged `v1.39`.
   If the deployed binary's commit can be identified from Phase 212 evidence
   (`evidence/health-steering.json` version, or systemd `ExecMainStartTimestamp`
   cross-referenced with build metadata), prefer that. Otherwise document the
   choice of `v1.39` git tag as the baseline and the rationale.
2. Identify the source HEAD commit = `git rev-parse HEAD` at audit time.
3. Restrict to steering-relevant paths (Section 3 above).
4. For each file in the surface, capture:
   - lines added / removed / context
   - commit list touching the file in range (`git log --follow`)
   - semantic category (per Section 6 above, decided by reading the diff,
     not by commit message alone)

The output is a markdown table + per-file diff appendix saved under
`.planning/phases/222-steering-drift-audit/evidence/`.

---

## 8. Methodology: Contract Diff (DRIFT-02)

For each file from the delta report, the auditor reads the diff and answers
three yes/no questions per the spine invariants (Section 5). A "no" on any
question marks the diff as contract-affecting and requires a per-finding
disposition.

The contract diff artifact is a markdown table:

| File | Commit | Invariant 1 (binary on/off) | Invariant 2 (new-only rerouting) | Invariant 3 (autorate baseline RTT) | Verdict |

A "Verdict" of `preserves` means all three invariants hold; `breaks` means at
least one is violated; `ambiguous` means the reader cannot determine without
runtime evidence.

---

## 9. Methodology: Per-Finding Recommendation (DRIFT-04)

For every diff that is `behavior-changing` (Section 6) OR `contract-affecting`
(Section 8), the auditor produces one of:

- **go** — change is safe to absorb into the live runtime. Rationale must
  cite the contract diff row(s) that confirm spine preservation.
- **mitigate** — change is safe to absorb only with an additional guard /
  config flag / staging soak. Rationale must specify the mitigation.
- **no-go** — change must not be absorbed into v1.48 alignment. Rationale
  must cite the contract violation or unresolved risk.

Default disposition for `behavior-preserving` and `observability-only`
changes is `go`; they are listed in the recommendations artifact for
completeness but do not need per-finding rationale beyond the category.

---

## 10. Methodology: SAFE-12 Boundary Check

At the phase boundary (end of Phase 222 work), run:

```
git diff bee343b -- \
  src/wanctl/wan_controller.py \
  src/wanctl/queue_controller.py \
  src/wanctl/cake_signal.py \
  src/wanctl/backends/ \
  src/wanctl/alert_engine.py \
  src/wanctl/fusion_healer.py
```

Expected: empty output. Any non-empty output is a SAFE-12 violation and
blocks phase closure. Result captured as an evidence artifact with the exact
git command, working tree commit, and diff (expected to be empty) saved for
audit.

The v1.47 close baseline commit is `bee343b chore: remove REQUIREMENTS.md for
v1.47 milestone`. The planner should confirm this is the correct baseline
before locking it into the SAFE-12 check.

---

## 11. Risks / Open Questions

| Risk | Mitigation |
|------|------------|
| The deployed runtime binary's exact commit cannot be reconstructed from on-host evidence | Document the choice of `v1.39` git tag as the conservative baseline; record the rationale and any deviation in the delta-report README. |
| Some commits touch both steering and controller-path files in the same change | Split the per-commit classification by file; controller-path changes must be byte-identical to v1.47 close per SAFE-12, so any cross-cutting commit is flagged for re-evaluation. |
| Log/metric changes inside the steering decision loop that look observability-only but affect cycle budget under contention | Classify as behavior-changing unless the change can be proven to be inside an unconditional branch with no early-return / no flush-blocking property. |
| Operator-side steering YAML schema drift (configs/steering.yaml vs deployed `/etc/wanctl/steering.yaml`) | Out of scope for source delta; Phase 212 evidence already captured deployed config snapshot. Cross-reference but do not re-probe. |

---

## 12. Validation Architecture

The audit is read-only and produces documents only. Validation for Phase 222
is:

- **Source assertions** — every claimed file path exists in the working tree.
- **Schema assertions** — each evidence JSON parses with `json.tool`; each
  markdown table has the expected column count.
- **Coverage assertions** — every commit in the v1.40 → v1.47-close range
  that touched steering source appears in the per-milestone classification
  exactly once.
- **SAFE-12 assertion** — the controller-path `git diff` against the v1.47
  close baseline produces empty output, captured as a saved evidence
  artifact.

No new helper code is expected. If any helper is introduced, it must ship
with `tests/test_phase222_drift_audit.py` covering the helper's contract
before any plan task depends on it.

---

## RESEARCH COMPLETE
