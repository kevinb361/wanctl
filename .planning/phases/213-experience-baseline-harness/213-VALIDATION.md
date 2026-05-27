---
phase: 213
slug: experience-baseline-harness
status: ready
nyquist_compliant: true
wave_0_complete: false
created: 2026-05-27
filled: 2026-05-27
---

# Phase 213 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (existing) |
| **Config file** | `pyproject.toml` (existing pytest config) |
| **Quick run command** | `.venv/bin/pytest tests/test_phase213_classify.py tests/test_phase213_ndjson_schema.py tests/test_phase213_manifest_schema.py tests/test_phase213_mutation_boundary.py -q` |
| **Full suite command** | `.venv/bin/pytest tests/ -q` |
| **Estimated runtime** | ~5-10 seconds (quick); ~2-3 minutes (full) |

---

## Sampling Rate

- **After every task commit:** Run quick command (four phase213 test files)
- **After every plan wave:** Run full suite
- **Before `/gsd:verify-work`:** Full suite must be green AND at least one end-to-end dry-run completed AND one real RUN-<ts>/ evidence tree committed
- **Max feedback latency:** < 30s for quick command (offline tests, no network)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 01-1 | 213-01 | 1 | BASE-01, BASE-02, BASE-03 | T-213-01 | Fixture copy preserves Phase 212 redaction; no re-probe of production (D-19) | unit (fixture validation) | `.venv/bin/python -c "import json; d=json.loads(open('tests/fixtures/phase213/ndjson-row-expected-keys.json').read()); assert len(d['required_keys']) >= 50"` | ❌ Wave 0 dependency | ⬜ pending |
| 01-2 | 213-01 | 1 | BASE-01, BASE-02, BASE-03 | T-213-02, T-213-05 | mutation-boundary grep guard enforces D-10; D-14 source-grep gate enforces threshold-name-non-interpretation | unit (pytest) | `.venv/bin/pytest tests/test_phase213_mutation_boundary.py tests/test_phase213_classify.py tests/test_phase213_manifest_schema.py tests/test_phase213_ndjson_schema.py -q` | ❌ Wave 0 dependency | ⬜ pending |
| 02-1 | 213-02 | 2 | BASE-02 | T-213-01, T-213-04 | jq projection is explicit allow-list (never `'.'` dump); 1Hz cadence per soak precedent | unit (jq projection schema) | `.venv/bin/pytest tests/test_phase213_ndjson_schema.py -q` AND `bash -n scripts/phase213-health-poller.sh` | ❌ Wave 2 | ⬜ pending |
| 02-2 | 213-02 | 2 | BASE-01 | T-213-02, T-213-04 | curl --interface source-bind; no HRDN-02 abort on per-row failures (failure data is signal) | smoke (live curl loop, 4-second window against 127.0.0.1) | `bash scripts/phase213-browse-loop.sh --output /tmp/p213-smoke.csv --duration 4 --local-bind 127.0.0.1 --sites "https://example.com/"; head -1 /tmp/p213-smoke.csv` | ❌ Wave 2 | ⬜ pending |
| 03-1 | 213-03 | 2 | BASE-02 | T-213-02, T-213-03 | SQLite URI mode=ro (not immutable=1) against live writer; existence probe for steering metrics.db (D-07 "if present") | source assertion + mutation-boundary | `bash -n scripts/phase213-alert-window.sh && grep -F "mode=ro" scripts/phase213-alert-window.sh && (grep -F "immutable=1" scripts/phase213-alert-window.sh && exit 1 || echo ok)` | ❌ Wave 2 | ⬜ pending |
| 03-2 | 213-03 | 2 | BASE-02 | T-213-01, T-213-05 | D-08 recursive redactor; D-14 invariant — no comparison to v1.39 threshold field names | source assertion + mutation-boundary | `bash -n scripts/phase213-steering-snapshot.sh && grep -F "password\|secret\|token\|credential\|auth\|key\|private" scripts/phase213-steering-snapshot.sh && (grep -E "if .*green_rtt_ms" scripts/phase213-steering-snapshot.sh && exit 1 || echo ok)` | ❌ Wave 2 | ⬜ pending |
| 04-1 | 213-04 | 3 | BASE-01 | T-213-02, T-213-04 | D-11 per-WAN sequencing; egress probe gate refuses Spectrum if egress != 70.123.224.169; SSH ControlMaster multiplexing | smoke (orchestrator --help + --dry-run) | `bash -n scripts/phase213-baseline-capture.sh && bash scripts/phase213-baseline-capture.sh --help \| grep -c -E "\-\-(local-bind\|host\|flent-duration\|browse-duration\|pre-buf\|post-buf\|wans\|tests\|evidence-root\|dry-run\|help)"` | ❌ Wave 3 | ⬜ pending |
| 04-2 | 213-04 | 3 | BASE-03 | T-213-05 | D-14 enforced by source-grep test_bucket_4_steering_drift_no_threshold_name_compare; D-15 ranked recommendation with primary ∈ {214,215,216} and ≥1 runner-up | unit (pytest, all four golden-file cases) | `.venv/bin/pytest tests/test_phase213_classify.py -q` | ❌ Wave 3 | ⬜ pending |
| 04-3 | 213-04 | 3 | BASE-01 | T-213-01 | docs + evidence/README.md mirror Phase 212 6-column command-index; no D-10 forbidden tokens in code blocks | docs sanity (grep) | `grep -F "bash scripts/phase213-baseline-capture.sh" docs/RUNBOOKS/baseline.md && grep -F "\| Timestamp (UTC) \| Source host \| Command purpose \| Redaction method \| Output file \| Mutation posture \|" .planning/phases/213-experience-baseline-harness/evidence/README.md` | ❌ Wave 3 | ⬜ pending |
| 05-1 | 213-05 | 4 | BASE-01, BASE-02, BASE-03 | T-213-02 | Dry-run prerequisite gates fire; manifest schema GREEN; no raw state.json committed | smoke + manifest-schema + redaction grep | `.venv/bin/pytest tests/test_phase213_*.py -q && find .planning/phases/213-experience-baseline-harness/evidence -name "*.raw.json"` (must be empty) | ❌ Wave 4 | ⬜ pending |
| 05-2 | 213-05 | 4 | BASE-01, BASE-02 | T-213-01, T-213-04 | D-11 sequencing held; full per-WAN suite ran to completion; redaction audit GREEN | manual (operator-checkpoint) | Per Manual-Only row below | ❌ Wave 4 | ⬜ pending |
| 05-3 | 213-05 | 4 | BASE-03 | T-213-05 | D-13 bucket verdicts cite signal-sheet evidence rows; D-14 BUCKET 4 verdict expressed as raw counter deltas only; D-15 ranked recommendation with ≥1 runner-up | source assertion (grep) | `grep -F "## Per-Bucket Verdict" 213-REPORT.md && grep -F "## Recommended Next Phase" 213-REPORT.md && grep -E "Phase 21[456]" 213-REPORT.md && grep -Eo "evidence/RUN-[A-Z0-9]+" 213-REPORT.md \| head -3` | ❌ Wave 4 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [x] `tests/test_phase213_classify.py` — six-bucket signal-sheet emission against Phase 212 evidence JSON fixtures (planned in Plan 01 Task 2; turns GREEN in Plan 04 Task 2)
- [x] `tests/test_phase213_ndjson_schema.py` — per-row NDJSON schema validation against `tests/fixtures/phase213/ndjson-row-expected-keys.json` (planned in Plan 01 Task 2; turns GREEN in Plan 02 Task 1)
- [x] `tests/test_phase213_manifest_schema.py` — per-run manifest schema against `tests/fixtures/phase213/manifest-expected-keys.json` (planned in Plan 01 Task 2; turns GREEN in Plan 04 Task 1 via `--dry-run`)
- [x] `tests/test_phase213_mutation_boundary.py` — grep guard: PHASE213_SCRIPTS scanned for 9 forbidden patterns (planned in Plan 01 Task 2; GREEN at Wave 0 commit because all scripts skip-with-reason; fully exercised by Wave 2)
- [x] `tests/fixtures/phase213/` — 8 fixture artifacts (3 health JSONs verbatim from Phase 212 + 2 expected-key JSONs + 1 SQLite DB built procedurally + 2 signal-sheet golden files); planned in Plan 01 Task 1
- [x] `tests/conftest.py` — three new session fixtures `phase212_health_{spectrum,att,steering}` (planned in Plan 01 Task 1)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Real per-WAN baseline capture run (Plan 05 Task 2) | BASE-01, BASE-02 | Loads production WAN with flent + curl-browse; cannot be CI-automated. D-11 per-WAN sequencing must be operator-verified live. | Per-step instructions in Plan 05 Task 2 `<how-to-verify>` block (10 steps including dev-VM-IP confirmation, cake-shaper SSH probe, autorate /health probe, no-concurrent-operator check, orchestrator invocation, artifact-tree count, signal-sheet existence, redaction audit grep). Operator types "approved" when audit passes. |
| Operator bucket verdict + next-phase recommendation (Plan 05 Task 3) | BASE-03 (success criteria 3 + 4), D-13, D-15 | Final bucket assignment + ranked 214/215/216 recommendation is human judgment cited from signal-sheet rows. | Operator authors `213-REPORT.md` per the 5-section outline in Plan 05 Task 3 `<interfaces>` block. Reviewer confirms each bucket has a verdict citing at least one `evidence/RUN-<ts>/...` path AND the Recommended Next Phase section names one of Phase 214/215/216 with at least one runner-up. |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies (Wave 0 covers classifier, NDJSON schema, manifest schema, mutation-boundary grep)
- [x] Sampling continuity: no 3 consecutive tasks without automated verify (every plan's tasks have automated verify gates; the one checkpoint:human-verify in Plan 05 is bracketed by automated dry-run gate before and automated report-grep gate after)
- [x] Wave 0 covers all MISSING references: classifier behavior (test_phase213_classify), NDJSON schema (test_phase213_ndjson_schema), manifest schema (test_phase213_manifest_schema), mutation-boundary grep enforcement of D-10 (test_phase213_mutation_boundary)
- [x] No watch-mode flags (every command exits)
- [x] Feedback latency < 30s (quick command runs four small offline test files)
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** ready — per-task verification map filled with 12 rows covering all 5 plans; threat refs T-213-01..T-213-05 mapped to specific mitigations per task; manual rows specify exact operator instructions.
