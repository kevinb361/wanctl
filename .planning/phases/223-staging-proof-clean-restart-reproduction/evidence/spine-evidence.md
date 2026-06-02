# PROOF-03 Spine Evidence

## Methodology

Verdicts are computed only from Plan 01/02 observable replay output: FakeRouterTransport steering_interactions, effective_steering_state_per_cycle, daemon_io_paths_exercised, baseline_rtt_per_cycle provenance, and the clean-restart-reproduction outcome. Invariant 1 checks that requested and effective steering states are strictly boolean. Invariant 2 is a daemon-side surrogate: the harness proves the daemon only calls documented steering-rule methods and does not invoke conntrack-mutation methods; RouterOS mangle-rule configuration is outside this harness. Invariant 3 checks that the baseline loader was called, reads came from the staging workspace rather than production runtime paths, baseline values stayed at the seeded fixture value, and the evidence did not record spectrum-state writes. restart_persistence_verdict is reported separately from the three spine invariants because a pre-enabled rule plus persisted DEGRADED state is still binary; the symptom is which authority wins (persisted state versus fresh measurement).

The verdicts below are computed from `replay-results.json` and `clean-restart-reproduction.json` only; the harness was not re-run for this report.

## Per-Fixture Verdict Table

| fixture | harness_mode | invariant_1 | invariant_2 | invariant_3 | restart_persistence | overall_verdict |
|---|---|---|---|---|---|---|
| `cake-read-failure` | `hysteresis-only` | preserves | preserves | breaks | not-applicable | **breaks** |
| `onset-degraded-confidence` | `confidence` | preserves | preserves | breaks | not-applicable | **breaks** |
| `onset-degraded-from-phase212` | `hysteresis-only` | preserves | preserves | breaks | not-applicable | **breaks** |
| `onset-degraded` | `hysteresis-only` | preserves | preserves | breaks | not-applicable | **breaks** |
| `recovery` | `hysteresis-only` | preserves | preserves | breaks | not-applicable | **breaks** |
| `steady-good` | `hysteresis-only` | preserves | preserves | breaks | not-applicable | **breaks** |
| `clean-restart-degraded` | `hysteresis-only` | preserves | preserves | breaks | breaks | **breaks** |

## Corpus Verdict

**BREAKS** — 7 breaking fixture(s), 0 ambiguous fixture(s), 7 total fixture(s).

### `cake-read-failure`

- Invariant 1 (binary on/off): **preserves** — all effective steering states and enable/disable results are strict booleans
- Invariant 2 (new-only surrogate): **preserves** — fake transport log contains only get_rule_status/enable_steering/disable_steering daemon calls
- Invariant 3 (autorate baseline authority): **breaks** — cycle 0: spectrum_state_write_attempted=True; cycle 1: spectrum_state_write_attempted=True; cycle 2: spectrum_state_write_attempted=True; cycle 3: spectrum_state_write_attempted=True; cycle 4: spectrum_state_write_attempted=True; cycle 5: spectrum_state_write_attempted=True; ... 8 total
- Restart-Persistence: **not-applicable** — fixture does not meet persisted-DEGRADED + pre-enabled-rule clean-restart precondition
- FULL I/O SEAL audit: **preserves** — FULL I/O SEAL covered baseline_rtt, cake_stats, and state_save on every cycle

### `onset-degraded-confidence`

- Invariant 1 (binary on/off): **preserves** — all effective steering states and enable/disable results are strict booleans
- Invariant 2 (new-only surrogate): **preserves** — fake transport log contains only get_rule_status/enable_steering/disable_steering daemon calls
- Invariant 3 (autorate baseline authority): **breaks** — cycle 0: spectrum_state_write_attempted=True; cycle 1: spectrum_state_write_attempted=True; cycle 2: spectrum_state_write_attempted=True; cycle 3: spectrum_state_write_attempted=True; cycle 4: spectrum_state_write_attempted=True; cycle 5: spectrum_state_write_attempted=True; ... 700 total
- Restart-Persistence: **not-applicable** — fixture does not meet persisted-DEGRADED + pre-enabled-rule clean-restart precondition
- FULL I/O SEAL audit: **preserves** — FULL I/O SEAL covered baseline_rtt, cake_stats, and state_save on every cycle

### `onset-degraded-from-phase212`

- Invariant 1 (binary on/off): **preserves** — all effective steering states and enable/disable results are strict booleans
- Invariant 2 (new-only surrogate): **preserves** — fake transport log contains only get_rule_status/enable_steering/disable_steering daemon calls
- Invariant 3 (autorate baseline authority): **breaks** — cycle 0: spectrum_state_write_attempted=True; cycle 1: spectrum_state_write_attempted=True; cycle 2: spectrum_state_write_attempted=True; cycle 3: spectrum_state_write_attempted=True; cycle 4: spectrum_state_write_attempted=True; cycle 5: spectrum_state_write_attempted=True; ... 15 total
- Restart-Persistence: **not-applicable** — fixture does not meet persisted-DEGRADED + pre-enabled-rule clean-restart precondition
- FULL I/O SEAL audit: **preserves** — FULL I/O SEAL covered baseline_rtt, cake_stats, and state_save on every cycle

### `onset-degraded`

- Invariant 1 (binary on/off): **preserves** — all effective steering states and enable/disable results are strict booleans
- Invariant 2 (new-only surrogate): **preserves** — fake transport log contains only get_rule_status/enable_steering/disable_steering daemon calls
- Invariant 3 (autorate baseline authority): **breaks** — cycle 0: spectrum_state_write_attempted=True; cycle 1: spectrum_state_write_attempted=True; cycle 2: spectrum_state_write_attempted=True; cycle 3: spectrum_state_write_attempted=True; cycle 4: spectrum_state_write_attempted=True; cycle 5: spectrum_state_write_attempted=True; ... 15 total
- Restart-Persistence: **not-applicable** — fixture does not meet persisted-DEGRADED + pre-enabled-rule clean-restart precondition
- FULL I/O SEAL audit: **preserves** — FULL I/O SEAL covered baseline_rtt, cake_stats, and state_save on every cycle

### `recovery`

- Invariant 1 (binary on/off): **preserves** — all effective steering states and enable/disable results are strict booleans
- Invariant 2 (new-only surrogate): **preserves** — fake transport log contains only get_rule_status/enable_steering/disable_steering daemon calls
- Invariant 3 (autorate baseline authority): **breaks** — cycle 0: spectrum_state_write_attempted=True; cycle 1: spectrum_state_write_attempted=True; cycle 2: spectrum_state_write_attempted=True; cycle 3: spectrum_state_write_attempted=True; cycle 4: spectrum_state_write_attempted=True; cycle 5: spectrum_state_write_attempted=True; ... 20 total
- Restart-Persistence: **not-applicable** — fixture does not meet persisted-DEGRADED + pre-enabled-rule clean-restart precondition
- FULL I/O SEAL audit: **preserves** — FULL I/O SEAL covered baseline_rtt, cake_stats, and state_save on every cycle

### `steady-good`

- Invariant 1 (binary on/off): **preserves** — all effective steering states and enable/disable results are strict booleans
- Invariant 2 (new-only surrogate): **preserves** — fake transport log contains only get_rule_status/enable_steering/disable_steering daemon calls
- Invariant 3 (autorate baseline authority): **breaks** — cycle 0: spectrum_state_write_attempted=True; cycle 1: spectrum_state_write_attempted=True; cycle 2: spectrum_state_write_attempted=True; cycle 3: spectrum_state_write_attempted=True; cycle 4: spectrum_state_write_attempted=True; cycle 5: spectrum_state_write_attempted=True; ... 10 total
- Restart-Persistence: **not-applicable** — fixture does not meet persisted-DEGRADED + pre-enabled-rule clean-restart precondition
- FULL I/O SEAL audit: **preserves** — FULL I/O SEAL covered baseline_rtt, cake_stats, and state_save on every cycle

### `clean-restart-degraded`

- Invariant 1 (binary on/off): **preserves** — all effective steering states and enable/disable results are strict booleans
- Invariant 2 (new-only surrogate): **preserves** — fake transport log contains only get_rule_status/enable_steering/disable_steering daemon calls
- Invariant 3 (autorate baseline authority): **breaks** — cycle 0: spectrum_state_write_attempted=True; cycle 1: spectrum_state_write_attempted=True; cycle 2: spectrum_state_write_attempted=True; cycle 3: spectrum_state_write_attempted=True; cycle 4: spectrum_state_write_attempted=True; cycle 5: spectrum_state_write_attempted=True; ... 35 total
- Restart-Persistence: **breaks** — PROOF-02 outcome=reproduced-bug; effective_steering remained true during recovery-window cycles [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13] from pre-enabled boot rule; this violates the binary-on/off + autorate-baseline-authoritative spine contract because persisted DEGRADED kept traffic effectively steered before fresh GOOD-consistent measurements recovered the daemon at cycle 14.
- FULL I/O SEAL audit: **preserves** — FULL I/O SEAL covered baseline_rtt, cake_stats, and state_save on every cycle

## Invariant-2 Caveat

Invariant 2 is a daemon-side surrogate. The fake transport proves the daemon only called `get_rule_status`, `enable_steering`, and `disable_steering`; it did not call conntrack flush/clear or any undocumented RouterOSController-shaped method. The actual "only new connections rerouted" property is enforced by the RouterOS mangle rule definition, which this offline harness does not verify. Stronger evidence would require exported RouterOS mangle-rule configuration, out of scope for Phase 223.

## Restart-Persistence

`restart_persistence_verdict` is separate from the three spine invariants. A pre-enabled rule plus persisted `SPECTRUM_DEGRADED` on clean restart is still a binary state; mapping `reproduced-bug` directly to invariant 1 would conflate binary state shape with authority. The reproduced bug means persisted state kept effective steering true while fresh GOOD-consistent measurements were arriving, which is a restart-persistence / measurement-authority concern related to invariant 3 but not identical to it.

For `clean-restart-degraded`, PROOF-02 outcome `reproduced-bug` maps to `restart_persistence_verdict = breaks`. Evidence: cycle 1 observed state `SPECTRUM_DEGRADED`, cycle 1 effective steering `True`, recovery to GOOD at cycle `14`.

## Phase 224 Readiness

**Phase 224 BLOCKED unless fix lands or operator accepts risk.**

Breaking fixtures/dimensions:

- `cake-read-failure`: invariant 3. Remediation path: Phase 224 pre-canary gate must either land a steering/source evidence fix before production canary or record explicit operator risk acceptance; otherwise route to a follow-up phase before deploy.
- `onset-degraded-confidence`: invariant 3. Remediation path: Phase 224 pre-canary gate must either land a steering/source evidence fix before production canary or record explicit operator risk acceptance; otherwise route to a follow-up phase before deploy.
- `onset-degraded-from-phase212`: invariant 3. Remediation path: Phase 224 pre-canary gate must either land a steering/source evidence fix before production canary or record explicit operator risk acceptance; otherwise route to a follow-up phase before deploy.
- `onset-degraded`: invariant 3. Remediation path: Phase 224 pre-canary gate must either land a steering/source evidence fix before production canary or record explicit operator risk acceptance; otherwise route to a follow-up phase before deploy.
- `recovery`: invariant 3. Remediation path: Phase 224 pre-canary gate must either land a steering/source evidence fix before production canary or record explicit operator risk acceptance; otherwise route to a follow-up phase before deploy.
- `steady-good`: invariant 3. Remediation path: Phase 224 pre-canary gate must either land a steering/source evidence fix before production canary or record explicit operator risk acceptance; otherwise route to a follow-up phase before deploy.
- `clean-restart-degraded`: invariant 3, restart-persistence. Remediation path: Phase 224 pre-canary gate must either land a steering/source evidence fix before production canary or record explicit operator risk acceptance; otherwise route to a follow-up phase before deploy.

## Evidence Row Citations

- `replay-results.json`: per-fixture `steering_interactions`, `effective_steering_state_per_cycle`, `baseline_rtt_per_cycle`, `daemon_io_paths_exercised`.
- `clean-restart-reproduction.json`: `outcome`, `cycle_1_observed_state`, `cycle_1_effective_steering_state`, `recovery_cycle_to_GOOD`, and per-cycle recovery window rows for `clean-restart-degraded`.
