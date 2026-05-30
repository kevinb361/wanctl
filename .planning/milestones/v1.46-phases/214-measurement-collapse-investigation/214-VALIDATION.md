---
phase: 214
slug: measurement-collapse-investigation
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-27
---

# Phase 214 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> Source: §"Validation Architecture" of `214-RESEARCH.md`.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (per `pyproject.toml`) |
| **Config file** | `pyproject.toml` (existing) |
| **Quick run command** | `.venv/bin/pytest tests/test_phase214_flent_extract.py tests/test_phase214_align.py tests/test_phase214_classify.py -x -q` |
| **Full suite command** | `.venv/bin/pytest tests/ -q` |
| **Estimated runtime** | ~30 seconds (quick); ~3 minutes (full) |

---

## Sampling Rate

- **After every task commit:** Run quick run command above.
- **After every plan wave:** Run full suite.
- **Before `/gsd:verify-work`:** Full suite green AND structural checks pass. Live matrix capture is a separate operator step recorded in `214-REPORT.md`.
- **Max feedback latency:** ~30 seconds.

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 214-XX-01 | matrix wrapper | 1 | MEAS-01 | — | Refuses out-of-window hours; honors `--dry-run` | unit (bash) | `bash scripts/phase214-flent-matrix.sh --dry-run --test-hour 14 daytime` | ❌ W0 | ⬜ pending |
| 214-XX-02 | flent extractor | 1 | MEAS-01 | — | Returns p50/p95/p99 from known-good fixture | unit | `.venv/bin/pytest tests/test_phase214_flent_extract.py::test_extract_known_good -x` | ❌ W0 | ⬜ pending |
| 214-XX-03 | flent extractor | 1 | MEAS-01 | — | Fails closed on missing `raw_values` key | unit | `.venv/bin/pytest tests/test_phase214_flent_extract.py::test_extract_missing_raw_fails_closed -x` | ❌ W0 | ⬜ pending |
| 214-XX-04 | flent extractor | 1 | MEAS-01 | — | Returns median/p95 throughput from `TCP download sum` | unit | `.venv/bin/pytest tests/test_phase214_flent_extract.py::test_extract_throughput -x` | ❌ W0 | ⬜ pending |
| 214-XX-05 | aligner | 1 | MEAS-01 | — | One row per second across window±buffer; correct `in_flent_window` flag | unit | `.venv/bin/pytest tests/test_phase214_align.py::test_align_basic -x` | ❌ W0 | ⬜ pending |
| 214-XX-06 | aligner | 1 | MEAS-01 | — | Buckets raw_values pings into per-second `ping_max_ms`/`ping_mean_ms` | unit | `.venv/bin/pytest tests/test_phase214_align.py::test_align_ping_bucketing -x` | ❌ W0 | ⬜ pending |
| 214-XX-07 | classifier | 2 | MEAS-02 | — | Identifies `reflector_loss` from `measurement_successful_count==0` cycles | unit | `.venv/bin/pytest tests/test_phase214_classify.py::test_classify_reflector_loss -x` | ❌ W0 | ⬜ pending |
| 214-XX-08 | classifier | 2 | MEAS-02 | — | Identifies `icmp_udp_divergence` from journal fixture | unit | `.venv/bin/pytest tests/test_phase214_classify.py::test_classify_protocol_divergence -x` | ❌ W0 | ⬜ pending |
| 214-XX-09 | classifier | 2 | MEAS-02 | — | Returns ranked-list when multiple drivers fire | unit | `.venv/bin/pytest tests/test_phase214_classify.py::test_classify_multi_driver_ranking -x` | ❌ W0 | ⬜ pending |
| 214-XX-10 | verdict gate | 2 | MEAS-02 | — | Emits `ambiguous` for 500–1000ms p99 zone | unit | `.venv/bin/pytest tests/test_phase214_classify.py::test_verdict_ambiguous_zone -x` | ❌ W0 | ⬜ pending |
| 214-XX-11 | report scaffolding | 3 | MEAS-03 | — | Report includes signal-disposition section; observational-first language | structural (grep) | `grep -q 'Signal Disposition\|observational' .planning/phases/214-measurement-collapse-investigation/214-REPORT.md` | Manual | ⬜ pending |
| 214-XX-12 | mutation guard | 3 | MEAS-03 | — | Zero changes under `src/wanctl/` for this phase | structural (git) | `test "$(git diff --name-only <phase-base-sha>..HEAD -- src/wanctl/ \| wc -l)" -eq 0` | Manual (verify gate) | ⬜ pending |
| (live) | matrix runner | N | MEAS-01 | — | Three Spectrum `tcp_12down` windows produce RUN dirs + matrix-summary.json | manual | Operator runs `scripts/phase214-flent-matrix.sh <window>` across calendar | Manual-only | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*
*Task IDs above are placeholders (`XX`) — `gsd-planner` will replace with real plan numbers.*

---

## Wave 0 Requirements

- [ ] `tests/test_phase214_flent_extract.py` — MEAS-01 extractor with known-good + missing-series fixtures
- [ ] `tests/test_phase214_align.py` — MEAS-01 time-aligned cycle joiner with synthesized health NDJSON
- [ ] `tests/test_phase214_classify.py` — MEAS-02 driver classification + verdict gate
- [ ] `tests/fixtures/phase214/sample-tcp_12down.flent.gz` — copy of a known-good real artifact (researcher verified `raw_values` shape)
- [ ] `tests/fixtures/phase214/sample-bad-p99-health.ndjson` — synthesized 30s NDJSON, `download_state=GREEN`, `measurement_successful_count` cycling 0/0/0/2
- [ ] `tests/fixtures/phase214/sample-journal-window.ndjson` — synthesized `ICMP deprioritized` and `Ping to .* failed` lines
- [ ] `scripts/phase214-flent-matrix.sh --dry-run --test-hour <H> <window>` hook (mirror `scripts/phase198-rerun-flent-3run.sh` pattern)
- [ ] pytest framework install: not needed (already present)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live three-window Spectrum `tcp_12down` matrix capture | MEAS-01 | Requires real WAN, real time-of-day windows, real flent artifacts | Operator runs `bash scripts/phase214-flent-matrix.sh off-peak`, `... daytime`, `... prime-time` across the calendar. Each must produce a `RUN-<UTC>/` directory containing flent `.flent.gz`, 1Hz `/health` NDJSON, journal snapshot, steering pre/post, and `phase214-window.json` sidecar |
| Optional ATT contrast run (per D-04) | MEAS-01 | Conditional on Spectrum being inconclusive or reproducing collapse | Same flow with ATT bind `10.10.110.233` in the same window as the triggering Spectrum run |
| Report narrative correctly explains or closes the bad-p99-while-GREEN case | MEAS-02 / MEAS-03 | Requires interpretation of real evidence; not mechanically verifiable | Reviewer reads `214-REPORT.md` and confirms: (a) classifier verdict cited per window, (b) driver evidence references aligned-rows file, (c) signal-disposition is observational-first, (d) folded todo `2026-04-08-investigate-tcp-12down-...` is explicitly closed or carried with narrower next steps |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or a Wave 0 dependency
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s
- [ ] `nyquist_compliant: true` set in frontmatter once all of the above are true

**Approval:** pending
