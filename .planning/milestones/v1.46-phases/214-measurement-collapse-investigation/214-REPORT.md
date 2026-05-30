# Phase 214 - Measurement Collapse Investigation REPORT

## TL;DR

- Matrix verdict: `ambiguous`
- Folded-todo decision: carried-narrower in `.planning/todos/pending/2026-04-08-investigate-tcp-12down-latency-spikes-under-multi-flow-downl.md`
- Signal disposition: `none`; observational signal not yet justified from the official matrix
- Safety attestation: no `src/wanctl/` edits; no production mutation

## Matrix Verdict

Canonical matrix summary: `.planning/phases/214-measurement-collapse-investigation/evidence/matrix-summary.json`.

| Window | Run Dir | p50_ms | p95_ms | p99_ms | Verdict | Primary Driver |
|---|---|---:|---:|---:|---|---|
| daytime | `RUN-20260528T150507Z` | 37.0 | 267.0 | 606.0 | ambiguous | reflector_loss |
| prime-time | `RUN-20260529T000507Z` | 37.0 | 106.0 | 560.0 | ambiguous | reflector_loss |
| off-peak | `RUN-20260529T060507Z` | 32.7 | 62.2 | 120.0 | pass | external_path |

The official Spectrum/Dallas matrix did not reproduce the historical catastrophic `p99 > 1000ms` condition. It also did not cleanly close the issue because daytime and prime-time both stayed in the ambiguous band with high tail latency and reflector-loss indicators. The aggregate verdict is therefore `ambiguous`, with `reflector_loss` as the primary driver and `signal_disposition=none`.

Supplemental evidence, not part of the canonical matrix, shows the problem remains target/path sensitive: off-peak Vultr Dallas (`zylone.org`) produced p50 `745 ms`, p95 `761 ms`, p99 `767 ms`, and median throughput `277.6 Mbit/s`; off-peak Vultr Chicago (`planetcaravan.org`) produced p50 `651 ms`, p95 `689 ms`, p99 `701 ms`, and median throughput `277.9 Mbit/s`. LibreQoS CLI corroboration against its Dallas endpoint produced download-side bufferbloat `+49.9 ms` with grade `B`. These supplemental runs support continued investigation but do not alter the official three-window verdict.

## Driver Classification

Primary driver: `reflector_loss`.

Ranked drivers from `matrix-summary.json`: `reflector_loss`.

Daytime evidence:

- `RUN-20260528T150507Z/spectrum/tcp_12down/signal-sheet.md` reports one zero-success cycle and max low-success run `1` while flent latency reached p99 `606 ms` and max `806 ms`.
- In `RUN-20260528T150507Z/spectrum/tcp_12down/aligned-window.json`, row 33 at `t_unix=1779980741` was inside the flent window with `download_state=YELLOW`, `health_status=healthy`, `measurement_state=collapsed`, `measurement_successful_count=0`, `measurement_stale=true`, `measurement_staleness_sec=1.151`, and `cake_dl_peak_delay_us=1395`.
- Row 45 at `t_unix=1779980753` was inside the flent window with `download_state=GREEN`, `health_status=healthy`, `measurement_successful_count=3`, `signal_outlier_rate=0.933`, and `load_rtt_ms=53.03`.

Prime-time evidence:

- `RUN-20260529T000507Z/spectrum/tcp_12down/signal-sheet.md` reports one zero-success cycle and max low-success run `1` while flent latency reached p99 `560 ms` and max `762 ms`.
- In `RUN-20260529T000507Z/spectrum/tcp_12down/aligned-window.json`, row 42 at `t_unix=1780013150` was inside the flent window with `download_state=YELLOW`, `health_status=healthy`, `measurement_state=collapsed`, `measurement_successful_count=0`, `measurement_stale=true`, `measurement_staleness_sec=1.103`, and `cake_dl_peak_delay_us=1060`.
- Row 16 at `t_unix=1780013124` was inside the flent window with `download_state=GREEN`, `health_status=healthy`, `measurement_successful_count=3`, `signal_outlier_rate=0.733`, and `load_rtt_ms=58.22`.

Off-peak evidence:

- `RUN-20260529T060507Z/spectrum/tcp_12down/signal-sheet.md` reports verdict `pass`, p99 `120 ms`, max `141 ms`, and no ranked driver evidence.
- In `RUN-20260529T060507Z/spectrum/tcp_12down/aligned-window.json`, row 27 at `t_unix=1780034735` was inside the flent window with `download_state=GREEN`, `health_status=healthy`, `measurement_successful_count=3`, `measurement_stale=false`, and `signal_outlier_rate=0.733`.
- Row 45 at `t_unix=1780034753` was inside the flent window with `download_state=YELLOW`, `health_status=healthy`, `measurement_state=healthy`, `measurement_successful_count=3`, and `cake_dl_peak_delay_us=967`.

Missing evidence and limits:

- No official window captured the historical `p99 > 1000ms` failure gate from the folded todo.
- The official signal sheets found zero reflector fail journal events and zero reflector deprioritization events, so `reflector_loss` is based on aligned measurement-quality collapse rather than direct log evidence in these runs.
- ICMP/UDP divergence did not fire as a ranked driver in the official matrix. The v1.45.0 regex strings were verified during Phase 214 research, but this matrix did not produce matching in-window evidence.
- The off-peak Dallas run logged repeated netperf no-data warnings while still writing a flent artifact and producing a pass verdict from ping latency. That warning should be carried as target-quality context, not treated as a controller finding.

## Signal Disposition

Signal disposition is `none` for Phase 214.

Observational signal not yet justified; carry the folded todo with narrower next steps. The official matrix shows elevated daytime and prime-time p99 while `/health` stayed healthy, but it does not reproduce the historical catastrophic p99 threshold, does not provide direct in-window journal corroboration for reflector fail bursts, and has a clean off-peak official window. Form B and Form C are therefore deferred rather than recommended from this phase. Form A (`/health` degraded-quality style field) remains a future-phase candidate only if a follow-up matrix produces stronger evidence.

Phase 214 did not implement any signal or controller behavior. The classifier and matrix summary remain observational artifacts.

## Folded Todo Decision

Reference: `.planning/todos/pending/2026-04-08-investigate-tcp-12down-latency-spikes-under-multi-flow-downl.md`.

Decision: carried-narrower.

Reason: verdict is `ambiguous`, not `pass`. The todo remains open because official daytime and prime-time windows still showed elevated tail latency and one-cycle measurement collapse while health remained healthy. The next investigation should target the unresolved gap: conditions that produce severe user-visible p99 without direct journal corroboration, and the target/path sensitivity shown by Vultr supplemental evidence.

## v1.46 Safety Attestation

- Zero `src/wanctl/` edits across the phase.
- Zero RouterOS writes.
- Zero production service restarts.
- Zero steering toggles.
- Zero `/etc/wanctl/*.yaml` edits.
- `PHASE214_BASE_SHA`: `471b98927039bcb4c05c02fd63b9bdc98d3e2ca6`.
- Mutation-boundary pytest result: PASS; post-report targeted guard passed with `2 passed in 0.14s`, and full Phase 214 suite passed with `52 passed in 1.94s`.

## Open Questions Carried

- A1 fusion-suspension field: resolved during Phase 214 research. Structured `/health` carries `wan_health.fusion.heal_state`, but the Phase 213 flat NDJSON projection does not include it. Phase 214 did not back-edit Phase 213 scripts. Carry only as a future projection candidate if a later observational phase needs richer fusion evidence.
- A2 journal log regex stability: resolved during Phase 214 research. v1.45.0 source strings still match `Ping to \S+ failed`, `ICMP deprioritized`, `UDP deprioritized`, and `Fusion healer .* -> suspended` expectations.
- Q3 ATT contrast windowing: not run. Instead, supplemental non-ATT Vultr Dallas and Chicago runs were captured after the off-peak official window to test target/path sensitivity. ATT contrast remains available if a future phase needs Spectrum-versus-ATT isolation.
- Q4 matrix-summary schema: resolved by `.planning/phases/214-measurement-collapse-investigation/evidence/matrix-summary.json`; Phase 215 can consume the schema without renegotiation.

## Provenance

- Phase commit range: `471b98927039bcb4c05c02fd63b9bdc98d3e2ca6..471b98927039bcb4c05c02fd63b9bdc98d3e2ca6`.
- Official live runs: `RUN-20260528T150507Z`, `RUN-20260529T000507Z`, `RUN-20260529T060507Z`.
- Supplemental runs: `supplemental-zylone-offpeak-20260529T061507Z`, `supplemental-planetcaravan-offpeak-20260529T062507Z`; LibreQoS CLI session `6901cfb9-6ed4-4d6a-8557-e97160eed1d1`.
- Analyzer scripts: `scripts/phase214-flent-matrix.sh`, `scripts/phase214-extract.py`, `scripts/phase214-align.py`, `scripts/phase214-classify.py`, `scripts/phase214-matrix-summary.py`.
- Journal command, daytime: `sudo -n journalctl --since=@1779980717 --until=@1779980764 -u wanctl@spectrum -o json`.
- Journal command, prime-time: `sudo -n journalctl --since=@1780013117 --until=@1780013164 -u wanctl@spectrum -o json`.
- Journal command, off-peak: `sudo -n journalctl --since=@1780034717 --until=@1780034764 -u wanctl@spectrum -o json`.
- Flent path resolution method: `find <test_dir>/flent -maxdepth 1 -name '*.flent.gz'`.
- Percentile method: `scripts/phase214-extract.py` computes percentiles from sorted raw `raw_values['Ping (ms) ICMP']` samples using p50 index `n//2`, p95 index `min(n-1, int(n*0.95))`, and p99 index `min(n-1, int(n*0.99))`, without interpolation.
- Test suite snapshot after writing this report: `PHASE214_BASE_SHA=471b98927039bcb4c05c02fd63b9bdc98d3e2ca6 .venv/bin/pytest tests/test_phase214_*.py -q` -> `52 passed in 1.94s`.

## Phase 215 Hand-off

Phase 215 can read these `matrix-summary.json` fields directly: `phase`, `verdict`, `primary_driver`, `ranked_drivers`, `signal_disposition`, `windows[].window`, `windows[].run_dir`, `windows[].p50_ms`, `windows[].p95_ms`, `windows[].p99_ms`, `windows[].verdict`, `windows[].primary_driver`, `started_utc`, `ended_utc`, `git_head_sha`, and `mutation_posture`.

Read-only operating-point annotations for downstream planning:

- The official Spectrum/Dallas off-peak window was clean enough for `pass` with p99 `120 ms`.
- Daytime and prime-time official windows remained ambiguous with p99 `606 ms` and `560 ms` and one zero-success measurement cycle each.
- Supplemental Vultr runs in the same off-peak period showed severe loaded latency, so target/path sensitivity remains a live hypothesis.
- Phase 214 makes no rate, threshold, queue, RouterOS, service, or steering recommendation. Phase 215 owns any independent operating-point decision.
