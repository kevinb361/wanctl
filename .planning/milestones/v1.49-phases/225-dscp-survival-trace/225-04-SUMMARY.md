---
phase: 225
plan: "04"
subsystem: dscp-evidence-tooling
tags: [dscp, evidence, read-only, hardening, gap-closure, safe-13]
requires:
  - 225-02 (original DSCP-02 capture script + invariants)
  - 225-VERIFICATION.md (GAP-1/2/3)
  - 225-REVIEW.md (CR-01/WR-01/WR-02)
provides:
  - Hardened scripts/phase225-dscp-ingress-capture.sh (injection-safe, falsifiable wash proof, honest DL source proof)
affects:
  - DSCP-02 evidence trust (capture-point-proof.txt, dl-ef-probe-result.txt semantics)
tech-stack:
  added: []
  patterns:
    - "Allowlist/range input validation gate ahead of all remote-command construction"
    - "Machine-checkable predicate gating for proof booleans (no topology-prose pass)"
    - "Honest unsupported-degrade instead of empty-artifact masquerade"
    - "Conditional required-artifact (real capture only) to avoid asserting absent evidence"
key-files:
  created: []
  modified:
    - scripts/phase225-dscp-ingress-capture.sh
decisions:
  - "[225-04] Probe/SSH/numeric args allowlist+range validated before any SSH command is built; unsafe value exits 2 with no remote invocation (GAP-1/CR-01)."
  - "[225-04] WASH_PROOF_PASS/WASH_ORDERING_PROVEN/CAPTURE_POINT set true ONLY on parse_qdisc_ordering (ingress/clsact hook + CAKE root both parsed on same iface) or a real paired_bitflip; topology text + qdisc presence demoted to supporting context, default false/unknown (GAP-2/WR-01)."
  - "[225-04] DL source-side EF proof is honest: opt-in real source capture (path A) or explicit SRC_CAPTURE_POINT=unsupported degrade with no empty pcap (path B); raw/dl-ef-probe-source.pcap is now a conditional artifact (GAP-3/WR-02)."
metrics:
  duration: ~9min
  completed: 2026-06-04
---

# Phase 225 Plan 04: Gap Closure — Harden DSCP Ingress Capture Summary

Hardened the read-only DSCP-02 evidence script along three fail-safe axes: probe-argument injection is now rejected before any SSH command is built, the pre-wash capture point rests on a machine-checkable qdisc-ordering predicate instead of topology prose, and the DL source-side EF proof is either a real bounded source capture or an explicit unsupported degrade — never an empty pcap masquerading as a capture. Only `scripts/phase225-dscp-ingress-capture.sh` changed; no controller-path source touched (SAFE-13 intact).

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Probe-arg injection validation gate (GAP-1/CR-01) | `e558543` | scripts/phase225-dscp-ingress-capture.sh |
| 2 | Predicate-gated wash-ordering proof (GAP-2/WR-01) | `255c040` | scripts/phase225-dscp-ingress-capture.sh |
| 3 | Honest DL source-side EF proof (GAP-3/WR-02) | `733af57` | scripts/phase225-dscp-ingress-capture.sh |

## What Changed

### Task 1 — Injection validation gate
- Added an allowlist/range gate in the post-parse validation block, textually ahead of `derive_topology_and_proof`, `run_ssh_capture`, and `capture_probe_window` (i.e. before any `ssh` invocation).
- `PROBE_TARGET` must match `^[A-Za-z0-9_.:-]+$`; `PROBE_PORT` must be an integer 1-65535. Also defensively validates `SSH_HOST` and the `DURATION`/`PACKET_CAP`/`MIN_*` numerics interpolated into remote tcpdump strings.
- Unsafe values exit 2 with an `ERROR:` and no SSH/no output dir (gate dominates `mkdir`).

### Task 2 — Falsifiable wash proof
- Added `parse_qdisc_ordering()`: returns `pass` ONLY when an ingress/clsact hook qdisc AND a CAKE `root` (egress) wash qdisc are both parsed on the same interface — proving the capture hook is upstream of wash. Presence of a CAKE handle alone returns `fail`.
- `derive_topology_and_proof` now drives `WASH_PROOF_PASS`/`WASH_ORDERING_PROVEN`/`CAPTURE_POINT` (and DL_/UL_ variants) from the `qdisc_ordering` verdict or an explicit `paired_bitflip` (PRE_WASH_DSCP set → POST_WASH_DSCP cleared). Both default fail-safe to `false`/`unknown`.
- The bridge-rule text is recorded as `TOPOLOGY_OK=` supporting context and never flips a proof boolean. `PROOF_NOTE` documents the predicate.

### Task 3 — Honest DL source proof
- Removed the `: > raw/dl-ef-probe-source.pcap` empty-file masquerade from the DL probe branch.
- **Path A (opt-in real capture):** new `--dl-source-ssh-host` / `--dl-source-iface` / `--dl-source-direction` controls (validated by the Task-1 gate) drive `run_source_capture()` — a bounded read-only tcpdump for the same probe 5-tuple, producing a real `raw/dl-ef-probe-source.pcap`. The analyzer's `DL_SOURCE_EF_PROVEN` gating (≥100 pkts, ≥90% EF, 5-tuple match, source pcap present) is unchanged.
- **Path B (honest degrade):** without source controls, the DL result emits `SRC_CAPTURE_POINT=unsupported`, `DL_SOURCE_EF_PROVEN=false`, `EF_SURVIVED=degraded`, passing `--source-pcap ""` so no empty pcap is written.
- `raw/dl-ef-probe-source.pcap` is now a CONDITIONAL artifact — required only when a real source capture ran (path A); MANIFEST and the required-artifact loop updated so an absent honest source pcap is never asserted, and a stale source pcap without a real capture is rejected.

## Verification

- `bash -n` and `shellcheck` clean after every task.
- `parse_qdisc_ordering` unit-tested against fixtures: presence-only CAKE root → `fail`; CAKE non-root / empty / missing → `fail`; ingress hook + CAKE root → `pass`. The old topology+presence pass path now yields `fail`/`unknown` (strictly tightening).
- Analyzer functionally tested: with 100% EF survival at enqueue but no source proof → `EF_SURVIVED=degraded` (never STRIPPED); with a real proven source pcap and washed enqueue (DSCP0, same 5-tuple) → `DL_SOURCE_EF_PROVEN=true` + `EF_SURVIVED=false` (negative branch intact only when source-proven).
- Injection rejections exit 2 with no output dir: probe-target metacharacters, out-of-range port, dl-source host injection, host/iface-not-paired, bad direction flag.
- Mutation grep (`tc filter/qdisc add|del|replace`, `cake diffserv|wash`, `nft add|delete|flush|-f`) empty; controller-path grep (`wan_controller|queue_controller|cake_signal|alert_engine|fusion_healer|backends/`) empty.
- Only `scripts/phase225-dscp-ingress-capture.sh` modified across all three commits — no `src/wanctl/` file touched. SAFE-13 invariant preserved.

## Note on live-capture testing

During Task 1 verification, a valid-argument run was started to confirm the gate passes good values; because `--ssh-host` defaults to the live `cake-shaper`, it connected and began a bounded read-only `timeout`-capped tcpdump against production. The background run was killed immediately and the stray bounded ssh-tcpdump terminated; it wrote nothing persistent (read-only, output streamed to the now-closed SSH stdout). All subsequent verification used `bash -n`, `shellcheck`, isolated function/analyzer unit tests, and gate-only rejection runs (which exit before any SSH) — no further live production capture was run.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Interactive doc-check pre-commit hook**
- **Found during:** Task 1 commit.
- **Issue:** The repo pre-commit hook prompts interactively ("Documentation Update Recommended") on security-related changes and aborted the non-interactive commit.
- **Fix:** Used the project-sanctioned `SKIP_DOC_CHECK=1` bypass (per CLAUDE.md) — NOT `--no-verify` — for each per-task commit. This is a read-only diagnostic shell script with no user-facing/API surface, so no README/context doc update applies.
- **Files modified:** none (process-only).
- **Commits:** e558543, 255c040, 733af57 (and the final docs commit).

Otherwise the plan executed as written — path (A)+(B) hybrid chosen for Task 3 (both honest paths implemented; degrade is the safe default).

## Known Stubs

None. The DL source-side capture is a real opt-in capability (path A) with an honest degrade default (path B); no placeholder/empty-artifact patterns remain.

## Threat Flags

None. All changes tighten input validation and proof gating; the new opt-in source-capture path uses bounded read-only tcpdump over SSH and flows its host/iface tokens through the same allowlist gate as the existing probe args. No new mutation surface, no controller-path reference.

## Self-Check: PASSED

- `.planning/phases/225-dscp-survival-trace/225-04-SUMMARY.md` — FOUND
- Commit e558543 (Task 1) — FOUND
- Commit 255c040 (Task 2) — FOUND
- Commit 733af57 (Task 3) — FOUND
- Files modified: only `scripts/phase225-dscp-ingress-capture.sh` (SAFE-13 controller-path zero-diff intact)
