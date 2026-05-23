---
phase: 206
slug: a-b-replay-harness-rollback-gates
status: verified
threats_open: 0
threats_total: 33
threats_closed: 33
asvs_level: 2
created: 2026-05-23
register_authored_at_plan_time: true
auditor: gsd-security-auditor
audit_mode: plan-time-verify
---

# Phase 206 — Security

> Per-phase security contract: threat register, accepted risks, and audit trail.
> Phase 206 delivered the A/B replay harness, predeploy rollback gate, and operator
> documentation. The runtime control path (`src/wanctl/`) was bounded by SAFE-09
> to the Phase 205 five-file allowlist; all Phase 206 work landed in `scripts/`,
> `tests/`, and `.planning/`.

---

## Trust Boundaries

| Boundary | Description | Data Crossing |
|----------|-------------|---------------|
| operator → harness CLI | Operator supplies `--fixture`, `--out`, `--flent-gz-pre`, `--flent-gz-post` paths | filesystem paths; gzipped flent RRUL JSON |
| operator → gate wrapper | Operator supplies `--baseline`, `--candidate`, `--soak-ndjson`, `--ssh-target`, restart-counter values, window-hours | filesystem paths; SSH target literal; integer counters; float window |
| gate wrapper → production host | SSH to cake-shaper to read `systemctl show -p NRestarts` (wrapper-only post-M7) | SSH BatchMode connection; reads systemd unit property |
| wrapper → Python core | Wrapper exec()s the Python core with argv array (no shell expansion) | argv array; environment with `PHASE206_LOCAL_BASELINE_OVERRIDE` cleared in production |
| baseline JSON → gate math | Baseline file declares `meta.metric_source`, `gate_baseline`, post-block p99 keys; comparison fails closed on mismatch | JSON object with schema_version + provenance text |
| flent JSON → parser | `_parse_flent_rrul` consumes operator-supplied `.flent.gz`; malformed input → rc=2 | gzipped flent RRUL ping series |
| committed golden NDJSON → VCS | Fixture is committed; risk of operator-identifying data leaking into repo history | five scrubbed fields per row; no IPs/hostnames |
| docs → operator decisions | `PHASE-205-ROLLBACK-GATES.md` thresholds drive deploy/abort calls; doc/JSON drift would mislead | inline numeric thresholds (5.0/10.0/10.0) with JSON as source of truth |
| git tree → SAFE-09 verifier | Four-surface boundary check (committed/staged/unstaged/untracked) trusts `git diff/ls-files/status` against `6508d68` | git index + worktree state |

---

## Threat Register

| Threat ID | Category | Component | Disposition | Mitigation | Status |
|-----------|----------|-----------|-------------|------------|--------|
| T-206-01a (P01) | Tampering | `scripts/phase206-ab-replay.py` argparse | mitigate | `_resolve_existing` uses `Path.resolve()` + `exists()` + `is_file()`; `main()` catches `OSError`/`TypeError`/`ValueError`/`JSONDecodeError` → rc=2 | closed |
| T-206-02 (P01) | Info Disclosure | `tests/fixtures/phase206_golden_capture.ndjson` | mitigate | Generator scrubs to 5 fields (`ts`, `baseline_rtt_ms`, `load_rtt_ms`, `cake_avg_delay_us`, `cake_base_delay_us`); 0 IPv4-shaped strings across 350 rows | closed |
| T-206-04 (P01) | Tampering | `tests.test_phase_193_replay._replay` import | accept | Phase 193 reuse-by-import is canonical; primitives stable since Phase 193, exercised by 194/195/197/201/202/203/204. Acceptance defensible. | closed |
| T-206-11 (P01) | Tampering | `_parse_flent_rrul` | mitigate | All parse failures (gzip, JSON, missing ping series) raise `ValueError`; `main` returns rc=2 with named bad file | closed |
| T-206-12 (P01) | Info Disclosure | `tests.*` import from `scripts/` | accept | CI-only invocation documented in module docstring; migrates to `wanctl.testing.replay` if ever packaged. Not present in `/opt/wanctl` runtime. | closed |
| T-206-01 (P02) | Tampering | `scripts/phase206-gate-check.py` threshold math | mitigate | Adversarial unit tests bracket each threshold (5.0% strict-> boundary, 10% restart, zero-baseline policy); 54 tests in focused slice | closed |
| T-206-01a (P02) | Tampering | `scripts/phase206-predeploy-gate.sh` argparse | mitigate | `[[ -r "$BASELINE" ]]` + `[[ -r "$CANDIDATE" ]]` readability guards; `exec "$VENV_PY" ... "${PY_ARGS[@]}"` array form (no shell expansion) | closed |
| T-206-02 (P02) | Info Disclosure | `tests/fixtures/phase206_baseline_v143.json` | mitigate | Real v1.43 numerics (transition=77.17/h, restart=0.0/h) with documented `_provenance`; no placeholders/IPs/hostnames/usernames | closed |
| T-206-03 (P02) | Tampering | `--ssh-target` argument | mitigate | Wrapper regex `^[A-Za-z0-9._-]+$` blocks injection; SSH uses `BatchMode=yes -o ConnectTimeout=5`; `test_invalid_ssh_target_aborts` covers `evil;rm -rf /` | closed |
| T-206-05 (P02) | DoS | SSH failure + input/baseline mismatch | mitigate | Two fail-closed paths: SSH errors → `log_abort` rc=2 (ConnectTimeout=5 cap); Python core rc=2 on baseline/input mismatch with byte-exact TOPO-05 message | closed |
| T-206-06 (P02) | Tampering | NDJSON `last_zone` adjacency loop | accept | Operator-internal soak telemetry; malformed lines skipped via try/except; degenerate-rate is low-impact. | closed |
| T-206-13 (P02) | Tampering (drift) | `scripts/phase206-thresholds.json` | mitigate | `load_thresholds()` reads JSON at module import; no numeric literal duplicated in Python module; Plan 04 drift-check verifies doc inline values | closed |
| T-206-07 (P03) | Tampering (drift) | `PHASE-205-ROLLBACK-GATES.md` vs JSON | mitigate | Doc declares JSON authoritative; Plan 04 drift loop verified 5.0/10.0/10.0 match between doc and JSON | closed |
| T-206-02 (P03) | Info Disclosure | `golden-fixture-provenance.md` local flent path | accept | Operator-side local filesystem path; not a network identifier. Operator’s own repo/filesystem. | closed |
| T-206-14 (P03) | Tampering | `gate_baseline._provenance` strings | accept | Operator narrative documenting how numerics were derived; tampering misleads auditors but does not change math. Plan 04 verifies non-empty. | closed |
| T-206-08 (P04) | Tampering | SAFE-09 boundary check | mitigate | Four-surface check (committed + staged + unstaged + untracked) closes single-surface fail-open hole; surface diff matches Phase 205 allowlist exactly | closed |
| T-206-09 (P04) | Tampering | Baseline SHA `6508d68` | accept | Stable repo invariant; verified in ROADMAP and Phase 205 VERIFICATION.md. | closed |
| T-206-10 (P04) | Tampering (drift) | Threshold constants doc ↔ JSON | mitigate | Plan 04 Task 2 Python drift-check loads JSON and asserts inline doc values; surfaces drift immediately | closed |
| T-206-15 (P04) | Tampering (race) | Worktree unstaged surface | mitigate | Surface 3 asserts `wc -l == 0`; operator-edit-without-commit/revert path correctly aborts Plan 04 | closed |
| T-206-G1-01 (P05) | Tampering | `check_zone_transitions` on empty/malformed NDJSON | mitigate | Typed `MalformedSoakInput`/`InsufficientSoakSamples` exceptions; `main()` → rc=2; 5 regression tests | closed |
| T-206-G1-02 (P05) | Info Disclosure | `check_zone_transitions` on single-sample NDJSON | mitigate | `len(timed_samples) < 2` guard raises `InsufficientSoakSamples` | closed |
| T-206-G2-01 (P05) | Tampering | Swapped restart counters | mitigate | `end < start` monotonicity guard executes before division; structured ABORT with both values; 3 regression tests | closed |
| T-206-G2-02 (P05) | DoS | Zero/negative window-hours | accept | Existing `window_hours <= 0` guard preserved and strengthened (extended in Phase 209 with `math.isfinite`). | closed |
| T-206-G3-01 (P06) | Repudiation/Tampering | Wrapper missing-value handler | mitigate | `require_value()` exits rc=2 with structured ABORT line BEFORE `shift 2`; 11 regression tests cover all value-consuming options | closed |
| T-206-G3-02 (P06) | Tampering | Next-token confusion | mitigate | `require_value` rejects values starting with `--`; surfaces offending token; `test_option_followed_by_another_option_aborts` covers `--baseline --candidate /tmp/x.json` | closed |
| T-206-G3-03 (P06) | DoS | Parser hangs | accept | `set -euo pipefail` + explicit `exit $EXIT_ABORT` means malformed input fails fast. | closed |
| T-206-G4-01 (P07) | Info Disclosure | `check_rrul_p99` mismatched post-block keys | mitigate | Secondary post-block-key guard raises `ValueError` before numeric comparison; integration test pins behavior on today's committed fixtures | closed |
| T-206-G4-02 (P07) | Tampering | `check_rrul_p99` `meta.metric_source` divergence | mitigate | Primary `meta.metric_source` guard runs before any p99 read; future-proofs against flent-sourced baselines | closed |
| T-206-G4-03 (P07) | Phase boundary | SAFE-09 src/wanctl/ | accept | Verified empty unstaged + untracked surface; Phase 206 work confined to scripts/tests. | closed |
| T-206-CLOSE-01 (P08) | Tampering | `206-VERIFICATION.md` status flip | mitigate | Spot-check rc gate runs BEFORE frontmatter edit; gap-found state preserved with explicit `re_verification:` block | closed |
| T-206-CLOSE-02 (P08) | Tampering | SAFE-09 silently breached during gap closure | mitigate | Plan 08 re-runs all four surfaces; acceptance criteria assert exact line counts + Surface 1 file-set match | closed |
| T-206-CLOSE-03 (P08) | Info Disclosure | `<PASTE>` placeholder leak | mitigate | `grep -c '<PASTE'` against verification report → 0 (matches in 08-SUMMARY are meta-references to the policy itself) | closed |
| T-206-CLOSE-04 (P08) | Repudiation | `re_verified` timestamp lost | mitigate | ISO8601 stamp grep enforced; original `Verified: 2026-05-15T02:48:44Z` preserved alongside re-verification stamp | closed |

*Status: open · closed*
*Disposition: mitigate (implementation required) · accept (documented risk) · transfer (third-party)*

---

## Accepted Risks Log

| Risk ID | Threat Ref | Rationale | Accepted By | Date |
|---------|------------|-----------|-------------|------|
| AR-206-01 | T-206-04 (P01) | Phase 193 reuse-by-import is the canonical reuse pattern; primitives stable since Phase 193 and exercised by every downstream replay phase (194/195/197/201/202/203/204) | Kevin (plan-time) | 2026-05-15 |
| AR-206-02 | T-206-12 (P01) | `tests.*` import from `scripts/phase206-ab-replay.py` is CI-only and documented in the module docstring; would migrate to `wanctl.testing.replay` if ever packaged for `/opt/wanctl` | Kevin (plan-time) | 2026-05-15 |
| AR-206-03 | T-206-06 (P02) | NDJSON `last_zone` adjacency operates on operator-internal soak telemetry; malformed lines skipped; worst case is degenerate rate computation — low impact | Kevin (plan-time) | 2026-05-15 |
| AR-206-04 | T-206-02 (P03) | `golden-fixture-provenance.md` cites Kevin's local flent results path; operator-side identifier, not a network identifier | Kevin (plan-time) | 2026-05-15 |
| AR-206-05 | T-206-14 (P03) | `gate_baseline._provenance` strings are operator narrative; tampering would mislead auditors but cannot change gate math; Plan 04 verifies non-empty | Kevin (plan-time) | 2026-05-15 |
| AR-206-06 | T-206-09 (P04) | Baseline anchor SHA `6508d68` is a stable repo invariant verified in Phase 205 closeout | Kevin (plan-time) | 2026-05-15 |
| AR-206-07 | T-206-G2-02 (P05) | `window_hours <= 0` guard already present; extended in Phase 209 with `math.isfinite` for NaN/Inf rejection | Kevin (plan-time) | 2026-05-15 |
| AR-206-08 | T-206-G3-03 (P06) | Bash `set -euo pipefail` + explicit `exit $EXIT_ABORT` in `require_value` ensures fail-fast on malformed input | Kevin (plan-time) | 2026-05-15 |
| AR-206-09 | T-206-G4-03 (P07) | Plan 07 work confined to `scripts/` and `tests/`; SAFE-09 four-surface check confirms zero `src/wanctl/` deltas | Kevin (plan-time) | 2026-05-15 |

---

## Security Audit Trail

| Audit Date | Threats Total | Closed | Open | Run By |
|------------|---------------|--------|------|--------|
| 2026-05-23 | 33 | 33 | 0 | gsd-security-auditor (plan-time verify mode) |

### Audit 2026-05-23 — Notes

- Register origin: `register_authored_at_plan_time: true` (8 of 9 plans contributed `<threat_model>` blocks; Plan 09 is gap-closure that inherits T-206-G1/G2/G3/G4 threat IDs, no new register entries needed).
- Mode: plan-time verify (do not scan for new threats; confirm declared mitigations are present and effective).
- Evidence base: focused pytest slice (54 passed in 2.45s), four-surface SAFE-09 boundary check, doc/JSON drift loop, golden fixture IP-grep, SSH wrapper validation tests, and per-threat file:line evidence captured by the auditor.
- All nine plan SUMMARY files reported "Threat Flags: None beyond the plan threat model" — no unregistered flags.
- Phase 209-02 commit `d70112f` strengthened T-206-G2-02 with `math.isfinite()` (NaN/Inf rejection) on `--window-hours`; this is a forward-compatible hardening and does not invalidate the Phase 206 acceptance.

---

## Sign-Off

- [x] All threats have a disposition (mitigate / accept / transfer)
- [x] Accepted risks documented in Accepted Risks Log
- [x] `threats_open: 0` confirmed
- [x] `status: verified` set in frontmatter

**Approval:** verified 2026-05-23
