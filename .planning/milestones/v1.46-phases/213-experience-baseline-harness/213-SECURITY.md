---
phase: 213
slug: experience-baseline-harness
status: verified
threats_open: 0
asvs_level: 1
created: 2026-05-27
---

# Phase 213 — Security

Per-phase security contract for the experience baseline harness, including the read-only dev-VM capture scripts, live serialized evidence run, classifier, committed evidence, and operator report.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| Phase 212 evidence -> Phase 213 fixtures | Already-redacted health snapshots copied into deterministic pytest fixtures. | Redacted `/health` JSON only. |
| Pytest -> harness scripts | Offline tests invoke check-manifest/local-db modes only. | Local fixture data and temporary manifest files. |
| Dev VM -> autorate `/health` | `phase213-health-poller.sh` polls bound health endpoints and emits an explicit 52-key projection. | Read-only daemon-state telemetry. |
| Dev VM -> public internet | `phase213-browse-loop.sh` emits source-bound curl timing rows. | HTTP timing metadata and response status/size. |
| Dev VM -> cake-shaper SSH | Alert-window and steering snapshot scripts use `BatchMode=yes` and `sudo -n` for read-only commands. | SQLite alert aggregates and steering health/state snapshots. |
| cake-shaper -> live SQLite DBs | Alert-window reads metrics DBs via `file:...?mode=ro`. | Read-only alert rows. |
| Steering raw state -> evidence | Raw steering state is temporary `/tmp` data; only redacted JSON is committed. | Secret-bearing raw JSON transiently, redacted JSON in evidence. |
| Operator -> orchestrator CLI | Baseline capture is explicit and serialized through `--bind-map`, `--check-prereqs`, and per-WAN test lists. | Operator-supplied host, WAN list, bind map, durations. |
| Classifier -> run-dir filesystem | `phase213-classify.py` reads committed evidence/config and writes signal sheet files. | Local evidence rows and classifier output. |
| Evidence staging -> git index | `.planning/` artifacts require explicit `git add -f` after redaction checks. | Committed manifest, NDJSON, CSV, JSON, Markdown evidence. |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| 213-01/T-213-01 | Information disclosure | Phase 212 health evidence fixtures | mitigate | Phase 212 snapshots were already redacted and copied byte-for-byte; Phase 213 redaction/UAT checks found no secret-like evidence hits. | closed |
| 213-01/T-213-02 | Tampering | Synthetic `alerts-test.db` fixture | accept | Local synthetic fixture generated from repository schema only; no production DB content. | closed |
| 213-01/T-213-03 | Information disclosure | SQLite read-only fixture path | mitigate | Live SQLite handling implemented in Plan 03 with `mode=ro`; offline local DB mode is test-only. | closed |
| 213-01/T-213-04 | Denial of service | Wave 0 pytest duration | accept | Offline tests are bounded and completed quickly; no network or production access. | closed |
| 213-01/T-213-05 | Elevation of privilege | Steering threshold-name interpretation | mitigate | Classifier source-grep tests enforce no v1.39 threshold-name comparisons. | closed |
| 213-01/T-213-06 | Tampering | Offline pytest accidentally SSH/curl | mitigate | `--check-manifest` branch is source-grep tested for no `ssh`/`curl`; UAT offline manifest check passed without production access. | closed |
| 213-02/T-213-01 | Information disclosure | `/health` NDJSON output | mitigate | Health poller emits explicit allow-list projection; schema test verifies the expected 52-key contract. | closed |
| 213-02/T-213-02 | Tampering | Health/browse scripts under D-10 boundary | mitigate | `tests/test_phase213_mutation_boundary.py` passes for all Phase 213 scripts. | closed |
| 213-02/T-213-04a | Denial of service | 1Hz `/health` polling | accept | Matches existing soak cadence; bounded-failure sidecar and short Phase 213 windows limit impact. | closed |
| 213-02/T-213-04b | Denial of service | Browse-loop public traffic | accept | Single fetch every two seconds in short windows; live run serialized by WAN. | closed |
| 213-03/T-213-01 | Information disclosure | Raw `steering_state.json` | mitigate | Raw state uses `/tmp/phase213-steering-raw.*` with `EXIT/INT/TERM` cleanup; committed evidence contains zero `*.raw.json`. | closed |
| 213-03/T-213-02 | Tampering | cake-shaper SSH commands | mitigate | Scripts use read-only SSH commands with `BatchMode=yes` and `sudo -n`; no service/config/router mutation commands are present. | closed |
| 213-03/T-213-03 | Information disclosure | Concurrent SQLite live DB read | mitigate | Alert-window script uses `file:DB?mode=ro`; verification found `mode=ro` present and `immutable=1` absent. | closed |
| 213-03/T-213-05 | Elevation of privilege | Steering threshold-field interpretation | mitigate | Steering snapshot only captures JSON; classifier threshold-name grep test covers interpretation. | closed |
| 213-03/T-213-06 | Tampering | Offline alert-window tests triggering SSH | mitigate | `--local-db` mode avoids SSH and is covered by tests. | closed |
| 213-04/T-213-01 | Information disclosure | Evidence README/command log | mitigate | Evidence README documents D-08 posture; orchestrator logs command purpose/timestamps, not secrets. | closed |
| 213-04/T-213-02 | Tampering | Orchestrator leaf-script calls | mitigate | Orchestrator invokes evidence-only scripts and dev-VM traffic generation; mutation-boundary tests pass. | closed |
| 213-04/T-213-03 | Information disclosure | Alert-window SQLite calls through orchestrator | mitigate | Inherits Plan 03 `mode=ro` gate; verified post-implementation. | closed |
| 213-04/T-213-04 | Denial of service | Serialized full-suite runtime | accept | Duration is bounded and serialized by WAN; manifest records start/end timestamps. | closed |
| 213-04/T-213-05 | Elevation of privilege | Steering drift classifier behavior | mitigate | Source-grep test verifies classifier avoids threshold-name comparisons. | closed |
| 213-04/T-213-06 | Tampering | Check-manifest accidentally reaching production | mitigate | Offline check-manifest source-grep and UAT run passed. | closed |
| 213-04/T-213-07 | Tampering | WAN/source-bind mislabeling | mitigate | `--bind-map` is required; live manifest records Spectrum/ATT bind IPs and observed egress. | closed |
| 213-04/T-213-08 | Denial of service | Background poller leak | mitigate | `POLLER_PIDS` cleanup/trap exists; live verification found no orphaned pollers. | closed |
| 213-04/T-213-09 | Elevation of privilege | Spectrum-specific `setpoint + 6` ceiling arithmetic | mitigate | Classifier reads config ceilings; verification found no `setpoint_mbps + 6` pattern and no `wanctl` import. | closed |
| 213-05/T-213-01 | Information disclosure | Committed live evidence tree | mitigate | Redaction scan passed; zero `*.raw.json`; committed artifacts contain no unredacted sensitive fields. | closed |
| 213-05/T-213-02 | Tampering | Real-run evidence-dir mutation scope | mitigate | Phase 213 only mutates evidence/report/tracking artifacts; controller source diff remains empty. | closed |
| 213-05/T-213-04 | Denial of service | Live 25-30 minute dev-VM traffic | accept | Operator approved live run; WANs ran serialized and the manifest records bounded timestamps. | closed |
| 213-05/T-213-05 | Elevation of privilege | Operator report threshold interpretation | mitigate | Report verdicts cite raw signal-sheet buckets and avoid v1.39 threshold-field comparisons. | closed |
| 213-05/T-213-08 | Denial of service | Orphaned health poller after live run | mitigate | Live verification/UAT found no persistent poller and all Phase 213 tests passed. | closed |
| 213-05/T-213-10 | Information disclosure | Forced-add of ignored `.planning/` evidence | mitigate | Evidence was force-added only after redaction checks; `git ls-tree`/UAT confirm evidence committed. | closed |

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-213-01 | 213-01/T-213-02 | Synthetic SQLite fixture drift is acceptable because it is local-only and schema drift fails tests. | phase plan | 2026-05-27 |
| AR-213-02 | 213-01/T-213-04 | Offline Wave 0 pytest runtime is negligible and has no production reachability. | phase plan | 2026-05-27 |
| AR-213-03 | 213-02/T-213-04a | 1Hz `/health` polling matches established soak cadence and is bounded. | phase plan | 2026-05-27 |
| AR-213-04 | 213-02/T-213-04b | Browse-loop traffic is low-volume and short-duration compared with flent. | phase plan | 2026-05-27 |
| AR-213-05 | 213-04/T-213-04 | Full-suite duration is accepted because execution is serialized and auditable. | phase plan | 2026-05-27 |
| AR-213-06 | 213-05/T-213-04 | Live traffic generation was explicitly approved at checkpoint and stayed serialized. | operator checkpoint | 2026-05-27 |

---

## Verification Evidence

| Check | Result |
|-------|--------|
| Shell syntax | `bash -n scripts/phase213-*.sh` passed. |
| Python syntax | `python -m py_compile scripts/phase213-classify.py` passed. |
| Phase 213 tests | `.venv/bin/pytest tests/test_phase213_*.py -q` -> `23 passed`. |
| Redaction scan | `RUN-20260527T222043Z` contains zero `*.raw.json` and no unredacted sensitive fields. |
| SQLite read safety | `mode=ro` present, `immutable=1` absent in `phase213-alert-window.sh`. |
| Portable classifier | No `setpoint_mbps + 6` pattern and no `wanctl` import in `phase213-classify.py`. |
| UAT | `213-UAT.md` complete: 5 passed, 0 issues. |
| Verification | `213-VERIFICATION.md` passed: 15/15 must-haves. |

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-05-27 | 30 | 30 | 0 | gsd-secure-phase |

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-05-27
