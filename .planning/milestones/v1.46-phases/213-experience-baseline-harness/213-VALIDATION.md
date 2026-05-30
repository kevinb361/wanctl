---
phase: 213
slug: experience-baseline-harness
status: ready
nyquist_compliant: true
wave_0_complete: false
created: 2026-05-27
filled: 2026-05-27
revised: 2026-05-27
revision_reason: "Codex cross-AI review patches landed (HIGH-1..HIGH-5, MEDIUM-1..MEDIUM-7, LOW-1). Added rows for parametrized mutation-boundary, per-bucket classifier (2/3/5/6), --check-manifest offline mode, alert-window --local-db behavioral test."
---

# Phase 213 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 7.x (existing) |
| **Config file** | `pyproject.toml` (existing pytest config) |
| **Quick run command** | `.venv/bin/pytest tests/test_phase213_classify.py tests/test_phase213_ndjson_schema.py tests/test_phase213_manifest_schema.py tests/test_phase213_mutation_boundary.py tests/test_phase213_alert_window.py -q` |
| **Full suite command** | `.venv/bin/pytest tests/ -q` |
| **Estimated runtime** | ~8-12 seconds (quick — five test files); ~2-3 minutes (full) |

---

## Sampling Rate

- **After every task commit:** Run quick command (five phase213 test files)
- **After every plan wave:** Run full suite
- **Before `/gsd:verify-work`:** Full suite must be green AND at least one offline `--check-manifest` AND one live `--check-prereqs` completed AND one real RUN-<ts>/ evidence tree committed
- **Max feedback latency:** < 30s for quick command (offline tests, no network)

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 01-1 | 213-01 | 1 | BASE-01, BASE-02, BASE-03 | T-213-01 | Fixture copy preserves Phase 212 redaction; no re-probe of production (D-19); manifest schema includes `bind_map` (codex HIGH-1); four per-bucket RUN fixtures created (codex MEDIUM-1); two mutation-fixture scripts created (codex HIGH-5) | unit (fixture validation) | `.venv/bin/python -c "import json; d=json.loads(open('tests/fixtures/phase213/ndjson-row-expected-keys.json').read()); assert len(d['required_keys']) >= 50; m=json.loads(open('tests/fixtures/phase213/manifest-expected-keys.json').read()); assert 'bind_map' in m['required_top_level_keys']"` + `ls -d tests/fixtures/phase213/RUN-bucket-{2,3,5,6}` + `test -f tests/fixtures/phase213/mutation-fixtures/{legitimate-doc,forbidden-restart}.sh` | ❌ Wave 0 dependency | ⬜ pending |
| 01-2 | 213-01 | 1 | BASE-01, BASE-02, BASE-03 | T-213-02, T-213-05, T-213-06 | Parametrized mutation-boundary grep enforces tightened D-10 (codex HIGH-5 — per-script independent skip + word-boundary regex + heredoc/comment filter); D-14 source-grep gate enforces threshold-name-non-interpretation; MEDIUM-2 source-grep gate enforces no `setpoint_mbps + 6` arithmetic; HIGH-3 offline-mode source-grep gate enforces no SSH in --check-manifest; positive (legitimate-doc) and negative (forbidden-restart) mutation-fixture tests | unit (pytest) | `.venv/bin/pytest tests/test_phase213_mutation_boundary.py tests/test_phase213_classify.py tests/test_phase213_manifest_schema.py tests/test_phase213_ndjson_schema.py tests/test_phase213_alert_window.py -q` | ❌ Wave 0 dependency | ⬜ pending |
| 02-1 | 213-02 | 2 | BASE-02 | T-213-01, T-213-04 | jq projection is explicit allow-list (never `'.'` dump); 1Hz cadence per soak precedent | unit (jq projection schema) | `.venv/bin/pytest tests/test_phase213_ndjson_schema.py -q` AND `bash -n scripts/phase213-health-poller.sh` | ❌ Wave 2 | ⬜ pending |
| 02-2 | 213-02 | 2 | BASE-01 | T-213-02, T-213-04 | curl --interface source-bind; no HRDN-02 abort on per-row failures (failure data is signal) | smoke (live curl loop, 4-second window against 127.0.0.1) | `bash scripts/phase213-browse-loop.sh --output /tmp/p213-smoke.csv --duration 4 --local-bind 127.0.0.1 --sites "https://example.com/"; head -1 /tmp/p213-smoke.csv` | ❌ Wave 2 | ⬜ pending |
| 03-1 | 213-03 | 2 | BASE-02 | T-213-02, T-213-03, T-213-06 | SQLite URI mode=ro (not immutable=1) against live writer; existence probe for steering metrics.db (D-07); `--local-db` offline mode (codex MEDIUM-6) skips SSH entirely for pytest fixture exercise | source assertion + mutation-boundary + alert-window behavioral | `bash -n scripts/phase213-alert-window.sh && grep -F "mode=ro" scripts/phase213-alert-window.sh && (grep -F "immutable=1" scripts/phase213-alert-window.sh && exit 1 \|\| echo ok) && grep -F -- "--local-db" scripts/phase213-alert-window.sh && .venv/bin/pytest tests/test_phase213_alert_window.py -q` | ❌ Wave 2 | ⬜ pending |
| 03-2 | 213-03 | 2 | BASE-02 | T-213-01, T-213-05 | D-08 recursive redactor; D-14 invariant; codex HIGH-2 raw-state pattern: `RAW_TMP=$(mktemp ...)` outside evidence/, `trap 'rm -f "$RAW_TMP"' EXIT INT TERM`, zero `*.raw.json` under evidence/ | source assertion + mutation-boundary | `bash -n scripts/phase213-steering-snapshot.sh && grep -E "trap .*RAW_TMP.*EXIT" scripts/phase213-steering-snapshot.sh && grep -E "mktemp.*phase213-steering" scripts/phase213-steering-snapshot.sh && grep -F "password\|secret\|token\|credential\|auth\|key\|private" scripts/phase213-steering-snapshot.sh && (grep -E "if .*green_rtt_ms" scripts/phase213-steering-snapshot.sh && exit 1 \|\| echo ok)` | ❌ Wave 2 | ⬜ pending |
| 04-1 | 213-04 | 3 | BASE-01 | T-213-02, T-213-04, T-213-07, T-213-08 | D-11 SERIALIZED per-WAN order (codex MEDIUM-7); per-WAN bind map (codex HIGH-1) — `--bind-map spectrum=<ip>,att=<ip>`; egress probe per WAN; dual offline/live mode split (codex HIGH-3) — `--check-manifest` offline + `--check-prereqs` live; trap-based poller cleanup (codex HIGH-4) — `trap cleanup_pollers EXIT INT TERM`; SSH ControlMaster multiplexing; flent path normalization (codex MEDIUM-3) | smoke (orchestrator --help + offline --check-manifest + source assertions) | `bash -n scripts/phase213-baseline-capture.sh && FLAG_COUNT=$(bash scripts/phase213-baseline-capture.sh --help \| grep -c -E -- "--(bind-map\|host\|flent-duration\|browse-duration\|pre-buf\|post-buf\|wans\|tests\|evidence-root\|check-manifest\|check-prereqs\|help)") && [[ $FLAG_COUNT -ge 12 ]] && grep -E "^trap .*cleanup_pollers.*EXIT" scripts/phase213-baseline-capture.sh && grep -F -- "--bind-map" scripts/phase213-baseline-capture.sh` | ❌ Wave 3 | ⬜ pending |
| 04-2 | 213-04 | 3 | BASE-03 | T-213-05, T-213-09 | D-14 enforced by source-grep test_bucket_4_steering_drift_no_threshold_name_compare; D-15 ranked recommendation with primary ∈ {214,215,216} and ≥1 runner-up; MEDIUM-1 per-bucket flag tests for buckets 1/2/3/5/6 (six buckets total, none can regress silently); MEDIUM-2 ceiling-from-config source-grep enforces no `setpoint_mbps + 6`; MEDIUM-5 signal-sheet inside RUN dir | unit (pytest, all eight classifier tests) | `.venv/bin/pytest tests/test_phase213_classify.py -q` | ❌ Wave 3 | ⬜ pending |
| 04-3 | 213-04 | 3 | BASE-01 | T-213-01 | docs + evidence/README.md mirror Phase 212 6-column command-index; documents `--bind-map`, `--check-manifest`, `--check-prereqs`; D-11 described as "serialized" (codex MEDIUM-7); signal-sheet path `evidence/RUN-<ts>/signal-sheet.{json,md}` (codex MEDIUM-5) | docs sanity (grep) | `grep -F "bash scripts/phase213-baseline-capture.sh" docs/RUNBOOKS/baseline.md && grep -F -- "--bind-map" docs/RUNBOOKS/baseline.md && grep -F -- "--check-manifest" docs/RUNBOOKS/baseline.md && grep -E "serialized" docs/RUNBOOKS/baseline.md && grep -F "evidence/RUN-" docs/RUNBOOKS/baseline.md && grep -F "\| Timestamp (UTC) \| Source host \| Command purpose \| Redaction method \| Output file \| Mutation posture \|" .planning/phases/213-experience-baseline-harness/evidence/README.md` | ❌ Wave 3 | ⬜ pending |
| 05-1 | 213-05 | 4 | BASE-01, BASE-02, BASE-03 | T-213-02, T-213-06 | `--check-manifest` offline gate fires; `--check-prereqs` live gate fires; manifest schema GREEN (includes bind_map per HIGH-1); no raw state.json under evidence/ (HIGH-2 invariant) | smoke + manifest-schema + redaction grep | `.venv/bin/pytest tests/test_phase213_*.py -q && find .planning/phases/213-experience-baseline-harness/evidence -name "*.raw.json"` (must be empty) | ❌ Wave 4 | ⬜ pending |
| 05-2 | 213-05 | 4 | BASE-01, BASE-02 | T-213-01, T-213-04, T-213-08 | D-11 SERIALIZED sequencing held (NOT concurrent — MEDIUM-7); full per-WAN suite ran to completion; redaction audit GREEN; HIGH-4 orphan-poller check (`pgrep -af phase213-health-poller` empty after run); signal-sheet INSIDE RUN dir (MEDIUM-5) | manual (operator-checkpoint) | Per Manual-Only row below | ❌ Wave 4 | ⬜ pending |
| 05-3 | 213-05 | 4 | BASE-03 | T-213-05, T-213-10 | D-13 bucket verdicts cite signal-sheet evidence rows; D-14 BUCKET 4 verdict expressed as raw counter deltas only; D-15 ranked recommendation with ≥1 runner-up; bind_map referenced in §Run Metadata (HIGH-1 provenance); MEDIUM-4 pre-commit redaction grep gate clean + `git add -f` succeeded against `.planning/` gitignore | source assertion (grep) + git ls-files check | `grep -F "## Per-Bucket Verdict" 213-REPORT.md && grep -F "## Recommended Next Phase" 213-REPORT.md && grep -E "Phase 21[456]" 213-REPORT.md && grep -Eo "evidence/RUN-[A-Z0-9_-]+" 213-REPORT.md \| head -3 && grep -F "bind_map" 213-REPORT.md && git ls-files --stage -- .planning/phases/213-experience-baseline-harness/213-REPORT.md \| grep -q .` | ❌ Wave 4 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [x] `tests/test_phase213_classify.py` — six-bucket signal-sheet emission with per-bucket golden-file fixtures for buckets 1/2/3/5/6 (codex MEDIUM-1), D-14 source-grep for bucket 4, MEDIUM-2 ceiling-source source-grep (planned in Plan 01 Task 2; turns GREEN in Plan 04 Task 2)
- [x] `tests/test_phase213_ndjson_schema.py` — per-row NDJSON schema validation (planned in Plan 01 Task 2; turns GREEN in Plan 02 Task 1)
- [x] `tests/test_phase213_manifest_schema.py` — per-run manifest schema (now invokes `--check-manifest` offline mode per codex HIGH-3, includes `bind_map` per HIGH-1) + `test_check_manifest_is_offline` source-grep gate (planned in Plan 01 Task 2; turns GREEN in Plan 04 Task 1)
- [x] `tests/test_phase213_mutation_boundary.py` — parametrized per-script forbidden-pattern grep (codex HIGH-5: tightened regex + per-script independent skip + comment/heredoc filter) + positive (legitimate-doc) + negative (forbidden-restart) mutation-fixture tests (planned in Plan 01 Task 2; GREEN at Wave 0 commit because all scripts skip-with-reason; fully exercised by Wave 2/3)
- [x] `tests/test_phase213_alert_window.py` — NEW per codex MEDIUM-6: behavioral SQL window/group-by test against `tests/fixtures/phase213/alerts-test.db` via the `--local-db` offline mode (planned in Plan 01 Task 2; turns GREEN in Plan 03 Task 1)
- [x] `tests/fixtures/phase213/` — base fixtures (3 health JSONs verbatim from Phase 212 + 2 expected-key JSONs + 1 SQLite DB + 2 signal-sheet golden files) + four per-bucket RUN fixtures (codex MEDIUM-1: RUN-bucket-{2,3,5,6}/) + two mutation-fixture scripts (codex HIGH-5: legitimate-doc.sh + forbidden-restart.sh); planned in Plan 01 Task 1
- [x] `tests/conftest.py` — three new session fixtures `phase212_health_{spectrum,att,steering}` (planned in Plan 01 Task 1)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Live `--check-prereqs` against cake-shaper (Plan 05 Task 1) | BASE-01 | Probes live SSH + sudo + per-WAN egress; requires network reachability to production. | Operator runs `bash scripts/phase213-baseline-capture.sh --check-prereqs --bind-map spectrum=10.10.110.226,att=10.10.110.233 --host dallas --evidence-root .planning/phases/213-experience-baseline-harness/evidence`. Must print `CHECK_PREREQS OK`. Failure modes (missing IP on dev VM, cake-shaper unreachable, egress mismatch) require operator intervention before Task 2. |
| Real per-WAN baseline capture run (Plan 05 Task 2) | BASE-01, BASE-02 | Loads production WAN with flent + curl-browse; cannot be CI-automated. D-11 SERIALIZED per-WAN sequencing must be operator-verified live (codex MEDIUM-7: NOT "concurrent"). | Per-step instructions in Plan 05 Task 2 `<how-to-verify>` block (10 steps including dev-VM-IP confirmation, cake-shaper SSH probe, autorate /health probe, no-concurrent-operator check, orchestrator invocation with `--bind-map`, artifact-tree count, signal-sheet existence INSIDE RUN-<ts>/, redaction audit grep, HIGH-4 `pgrep -af phase213-health-poller` empty check). Operator types "approved" when audit passes. |
| Operator bucket verdict + next-phase recommendation + `git add -f` commit (Plan 05 Task 3) | BASE-03 (success criteria 3 + 4), D-13, D-15, codex MEDIUM-4 | Final bucket assignment + ranked 214/215/216 recommendation is human judgment cited from signal-sheet rows. `.planning/` is gitignored so explicit `git add -f` is required; pre-commit D-08 redaction grep gate fails closed on any unredacted secret-bearing key. | Operator authors `213-REPORT.md` per the 5-section outline in Plan 05 Task 3 `<interfaces>` block (must include `bind_map` in §Run Metadata per HIGH-1). Pre-commit grep gate: `find <RUN-DIR> -type f \( -name '*.json' -o -name '*.md' -o ... \) -exec grep -l -E -i '"(password\|secret\|token\|credential\|auth\|key\|private)":\s*[^<]' {} \;` returns empty. Reviewer confirms each bucket has a verdict citing at least one `evidence/RUN-<ts>/...` path AND the Recommended Next Phase section names one of Phase 214/215/216 with at least one runner-up. |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies (Wave 0 covers classifier per-bucket, NDJSON schema, manifest schema offline, mutation-boundary parametrized + mutation-fixture, alert-window behavioral)
- [x] Sampling continuity: no 3 consecutive tasks without automated verify (every plan's tasks have automated verify gates; the one checkpoint:human-verify in Plan 05 is bracketed by automated dry-run gate before and automated report-grep gate after)
- [x] Wave 0 covers all MISSING references: classifier behavior across all six buckets (test_phase213_classify with five flag tests + recommendation + D-14 + MEDIUM-2 source-grep), NDJSON schema (test_phase213_ndjson_schema), manifest schema offline (test_phase213_manifest_schema with HIGH-3 source-grep), mutation-boundary parametrized (test_phase213_mutation_boundary with positive+negative mutation fixtures), alert-window behavioral (test_phase213_alert_window — NEW per MEDIUM-6)
- [x] No watch-mode flags (every command exits)
- [x] Feedback latency < 30s (quick command runs five small offline test files)
- [x] `nyquist_compliant: true` set in frontmatter
- [x] Codex cross-AI review patches reflected: HIGH-1 (bind_map), HIGH-2 (raw-state /tmp + EXIT trap), HIGH-3 (offline `--check-manifest` + live `--check-prereqs` split), HIGH-4 (trap cleanup_pollers + orphan-poller check), HIGH-5 (parametrized mutation test + tightened regex + mutation-fixtures), MEDIUM-1 (per-bucket golden fixtures), MEDIUM-2 (ceiling-from-config source-grep), MEDIUM-3 (flent path normalization), MEDIUM-4 (`git add -f` + redaction gate), MEDIUM-5 (signal-sheet inside RUN dir), MEDIUM-6 (alert-window --local-db behavioral test), MEDIUM-7 ("serialized" wording).

**Approval:** ready — per-task verification map refilled with 12 rows (1 added: alert-window behavioral test under Plan 03 row 03-1, plus revised bucket coverage under 04-2); threat refs T-213-01..T-213-10 mapped to specific mitigations per task; manual rows specify exact operator instructions including the new `--check-prereqs` mode and `git add -f` redaction gate.
