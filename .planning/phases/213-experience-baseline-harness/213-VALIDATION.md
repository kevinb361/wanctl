---
phase: 213
slug: experience-baseline-harness
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-05-27
---

# Phase 213 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (existing) |
| **Config file** | `pyproject.toml` (existing pytest config) |
| **Quick run command** | `.venv/bin/pytest tests/test_phase213_classify.py tests/test_phase213_schema.py -q` |
| **Full suite command** | `.venv/bin/pytest tests/ -q` |
| **Estimated runtime** | ~{TBD by planner — Wave 0} seconds |

---

## Sampling Rate

- **After every task commit:** Run quick command (classifier + schema unit tests)
- **After every plan wave:** Run full suite
- **Before `/gsd:verify-work`:** Full suite must be green AND at least one end-to-end dry-run completed
- **Max feedback latency:** {TBD by planner — target < 30s for quick}

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| {TBD by planner — one row per task} | | | | | | | | | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `tests/test_phase213_classify.py` — six-bucket signal-sheet emission against Phase 212 evidence JSON fixtures
- [ ] `tests/test_phase213_ndjson_schema.py` — per-row NDJSON schema validation (timestamp, wan, status, cake_signal snapshot, outlier_rate, confidence, successful_count, current_rates)
- [ ] `tests/test_phase213_manifest_schema.py` — per-run manifest schema (test list, start/end timestamps, source IP, netperf host, flent version, wanctl version per WAN, redaction posture)
- [ ] `tests/test_phase213_mutation_boundary.py` — grep guard: orchestrator/poller/snapshot scripts contain NO `systemctl restart`, NO writes to `/etc/wanctl/`, NO RouterOS write commands, NO steering toggle (enforces D-10)
- [ ] `tests/fixtures/phase213/` — fixture JSONs/NDJSON lines copied from Phase 212 evidence + synthetic edge cases
- [ ] `tests/conftest.py` — shared fixtures (`phase212_health_spectrum`, `phase212_health_att`, `phase212_health_steering`) loading the fixture files

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Real WAN baseline capture run | BASE-01, BASE-02 | Loads production WAN with flent + curl-browse; cannot be automated in CI without traffic generation against live hops | Run `scripts/phase213-baseline-capture.sh --wan spectrum && scripts/phase213-baseline-capture.sh --wan att`; verify per-run dir + manifest + signal sheet emitted; confirm redaction posture against Phase 212 D-08/D-09/D-10 policy |
| Operator bucket verdict + next-phase recommendation | BASE-03 (success criteria 3 + 4) | Final bucket assignment + 214/215/216 recommendation is a human judgment cited from the signal sheet rows | Operator authors `213-REPORT.md` citing signal-sheet rows; reviewer confirms each bucket call is row-cited and runners-up are explicit |
| cake-shaper SSH steering snapshot | BASE-02 (D-08) | Requires live SSH access to cake-shaper and a live steering daemon at 127.0.0.1:9102 | Run `scripts/phase213-steering-snapshot.sh` pre/post a test window; verify snapshot JSON shape matches Phase 212 `health-steering.json` schema and `steering_state.json` captured atomically |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies (Wave 0 covers classifier, NDJSON schema, manifest schema, mutation-boundary grep)
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references (classifier behavior, schema shape, mutation-boundary grep enforcement of D-10)
- [ ] No watch-mode flags
- [ ] Feedback latency < 30s (quick command)
- [ ] `nyquist_compliant: true` set in frontmatter once planner fills the verification map

**Approval:** pending — planner to fill the per-task verification map and operator manual rows during plan synthesis.
