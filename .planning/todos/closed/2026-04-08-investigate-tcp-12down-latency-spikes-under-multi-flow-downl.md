---
created: 2026-04-08T00:55:13.688Z
title: Investigate tcp_12down latency spikes under multi-flow download
area: tuning
resolves_phase: 221
files:
  - src/wanctl/wan_controller.py
  - src/wanctl/fusion_healer.py
  - src/wanctl/health_check.py
closed_by_phase: 221
verdict: carried_narrower_with_close_with_prejudice_rule
close_with_prejudice: true
---

## Problem

The original catastrophic tcp_12down failure from 2026-04-07 reappeared on current production during a fresh live validation run on 2026-04-15.

Fresh live validation on 2026-04-14 (Spectrum v1.35.0, 30s `flent tcp_12down` to Dallas) produced:
- Ping avg `45.55ms`, median `40.60ms`, p99 `159.42ms`
- TCP download sum `273.81 Mbit/s`
- No `SOFT_RED`/`RED` burst-clamp activation
- No burst trigger in `/health` (`trigger_count: 0`)

That means the old "multi-second p99 burst because the controller cannot react quickly enough" problem is no longer the active issue.

What still showed up under the same run:
- repeated protocol-correlation flips (`ICMP deprioritized` and `UDP deprioritized`)
- intermittent reflector misses (`Ping to 1.1.1.1 failed`, `Ping to 151.101.1.57 failed`, `Ping to 208.67.222.222 failed`)
- one fusion-healer suspension event before the flent run window

So the remaining tcp_12down concern is now measurement-path behavior under heavy multi-flow load, not missing burst-clamp control logic.

Fresh live validation on 2026-04-15 at `02:45 CDT` produced materially worse results:
- Ping avg `201.45ms`, median `52.60ms`, p99 `3059.16ms`
- TCP download sum `301.80 Mbit/s`
- Spectrum remained `healthy`, `GREEN`, and post-run `burst.trigger_count` stayed `0`
- Spectrum autorate `overrun_count` increased from `174` to `177`
- Steering remained `healthy`, `rtt_source.current=autorate_health`, `history_fallback=58`, `overrun_count=84`
- VM steal over a fresh 10-second `/proc/stat` delta was only `1.58%`

What did show up during the bad run:
- `ICMP deprioritized` at `02:45:49 CDT` with ratio `2.21`
- `UDP deprioritized` at `02:46:07 CDT` with ratio `0.58`
- repeated reflector misses starting at `02:45:50 CDT`
- full three-reflector miss bursts at `02:46:13` through `02:46:17 CDT`

That means the current live problem is not "steering fell over" or "the VM was starved." The active concern is that heavy multi-flow download can still collapse the measurement path badly enough to recreate multi-second `tcp_12down` tail latency while the controller remains superficially healthy.

## Historical A/B Result (2026-04-07 evening)

RED floor sweep — 30s tcp_12down runs, Spectrum evening congestion:

| RED Floor | Ping Median | Ping p99 | RTT at Floor | DL Throughput |
|-----------|-------------|----------|--------------|---------------|
| 200M (old)| 88.6ms      | 3,192ms  | 252ms        | 258 Mbps      |
| 100M      | 93.9ms      | 3,160ms  | 267ms        | 227 Mbps      |
| 75M       | 62.0ms      | 3,018ms  | 236ms        | 202 Mbps      |
| **50M**   | **43.5ms**  | **823ms**| **59ms**     | 159 Mbps      |
| 50M (cfm) | 53.6ms      | 1,651ms  | 218ms        | 211 Mbps      |

**Cliff between 75M and 50M.** At 75M+ the controller is floor-trapped (230ms+ RTT at floor). At 50M, CAKE can finally drain queues — each of 12 flows gets ~4Mbps, small enough CWND for AQM to work.

## Current conclusion

The tcp_12down item remains an active production reliability investigation.

The current question is:
- whether reflector collapse during multi-flow load is the primary cause of the `p99` spike
- whether protocol-correlation churn is a symptom of that collapse or a parallel issue
- whether the controller is missing a clearer degraded-state signal when measurement quality collapses but `burst` never triggers
- whether the production path is time-of-day sensitive enough that a single clean run on 2026-04-14 was a false sense of closure

## Remaining investigation
- run a small bounded reproduction matrix at different times of day and compare p99 plus reflector-loss behavior
- inspect whether the worst runs align more strongly with reflector loss, protocol divergence, or both
- verify whether repeated reflector misses occur before, during, or only after the worst ping tail growth
- decide whether any operator-facing alerting should trigger when measurement quality collapses without a burst trigger

Reference data:
- Historical: `/tmp/tcp_12down-2026-04-07T19*.flent.gz`, `/tmp/rrul-2026-04-07T194733*.flent.gz`
- Current: flent summary from `2026-04-14 17:45 CDT` (`avg 45.55ms`, `median 40.60ms`, `p99 159.42ms`)
- Current: flent artifact from `2026-04-15 02:45 CDT` at `/tmp/tcp_12down-2026-04-15T024543.818291.todo-check-2026-04-15T0246.flent.gz`

## Follow-up Notes — 2026-04-14

A second live validation run after the protocol/fusion observability fixes
improved further:

- `flent tcp_12down` at `2026-04-14 17:52 CDT`
- Ping avg `39.15ms`, median `38.80ms`, p99 `105.04ms`
- TCP download sum `297.22 Mbit/s`
- no burst trigger
- no fusion suspension
- post-run `/health` showed fusion active with `active_source=fused`

Current interpretation:
- this run looked temporarily closed on 2026-04-14
- that closure did not hold through the next live production validation

## Follow-up Notes — 2026-04-15

Direct live production re-test from the dev machine to Dallas at `02:45 CDT` reopened this todo.

Observed flent summary:
- Ping avg `201.45ms`, median `52.60ms`, p99 `3059.16ms`
- TCP download sum `301.80 Mbit/s`

Observed production behavior:
- Spectrum post-run `/health` remained `healthy`
- Spectrum remained `GREEN`
- Spectrum `burst.trigger_count` remained `0`
- Spectrum `overrun_count` moved `174 -> 177`
- steering stayed on `autorate_health`
- steering `history_fallback` stayed flat at `58`
- steering `overrun_count` stayed flat at `84`
- steal CPU stayed low enough that it does not explain the event

Observed log evidence:
- repeated reflector failures on `208.67.222.222`, `1.1.1.1`, and `151.101.1.57`
- protocol correlation flipped in both directions during the same run

Current interpretation:
- the active issue is back
- the likely failure surface is measurement resilience under multi-flow load
- steering and Proxmox steal are not the leading suspects from this run

## Reproduction Plan

Use the exact same bounded live method so runs are comparable:

1. Pre-check production state:
   - `./scripts/soak-monitor.sh --ssh kevin@10.10.110.223 --json`
   - `ssh kevin@10.10.110.223 'curl -s http://127.0.0.1:9102/health | python3 -m json.tool'`
   - `ssh kevin@10.10.110.223 'python3 - <<\"PY\"`
     `import time`
     `def snap(): return list(map(int, open(\"/proc/stat\").readline().split()[1:9]))`
     `s1=snap(); time.sleep(10); s2=snap(); d=[b-a for a,b in zip(s1,s2)]; t=sum(d); print(round((d[7]/t*100) if t else 0, 2))`
     `PY'`
2. Run one 30-second download stress test from the dev machine:
   - `flent tcp_12down -H 104.200.21.31 -l 30 -t '<label>' -o /tmp/<label>.flent.gz`
3. Pull post-run production evidence immediately:
   - `./scripts/soak-monitor.sh --ssh kevin@10.10.110.223 --json`
   - `ssh kevin@10.10.110.223 'curl -s http://127.0.0.1:9102/health | python3 -m json.tool'`
   - `ssh kevin@10.10.110.223 'sudo -n journalctl -u wanctl@spectrum -u steering --since "<run start>" --no-pager'`
4. Extract the flent summary:
   - `flent -i /tmp/<label>.flent.gz -f summary`

Minimum matrix:
- 1 run off-peak
- 1 run daytime
- 1 run prime-time
- only one run per window unless the first result is ambiguous

Pass/fail gates for the todo:
- pass candidate:
  - ping `p99 < 500ms`
  - no full three-reflector miss burst
  - no unexpected steering fallback growth
  - no burst trigger and no sustained autorate distress
- fail candidate:
   - ping `p99 > 1000ms`
   - repeated three-reflector miss bursts
   - protocol churn plus reflector collapse in the same run
   - steering remains healthy while user-visible latency is still catastrophically bad

## Phase 214 narrower next steps (2026-05-29)

Phase 214 completed the official three-window Spectrum `tcp_12down` matrix and produced `.planning/phases/214-measurement-collapse-investigation/evidence/matrix-summary.json` with verdict `ambiguous`.

Official Spectrum/Dallas results:

- daytime `RUN-20260528T150507Z`: p50 `37.0ms`, p95 `267.0ms`, p99 `606.0ms`, verdict `ambiguous`, primary driver `reflector_loss`
- prime-time `RUN-20260529T000507Z`: p50 `37.0ms`, p95 `106.0ms`, p99 `560.0ms`, verdict `ambiguous`, primary driver `reflector_loss`
- off-peak `RUN-20260529T060507Z`: p50 `32.7ms`, p95 `62.2ms`, p99 `120.0ms`, verdict `pass`, primary driver `external_path`

Disposition: keep this todo open. The historical catastrophic `p99 > 1000ms` case did not reproduce in the official matrix, but daytime and prime-time still showed elevated tail latency while `/health` stayed healthy and each had one in-window zero-success measurement cycle. Supplemental off-peak Vultr Dallas/Chicago runs showed severe loaded latency (`p99 767ms` and `701ms`), which keeps target/path sensitivity in scope.

Narrower follow-up:

- repeat only when official Dallas, Vultr Dallas, and Vultr Chicago can be captured in the same time band with comparable source bind and artifact extraction
- require direct journal corroboration for reflector fail bursts or protocol divergence before attributing a future severe p99 run to reflector/protocol collapse
- preserve the Phase 214 distinction between canonical matrix evidence and supplemental target/path evidence
- do not close this todo from `/health.status=healthy`, `GREEN`, or one clean off-peak official run alone

## Phase 221 Closeout

**Verdict:** carried_narrower_with_close_with_prejudice_rule
**Summary:** Phase 221 produced a post-BGP-overlay carried-narrower verdict under the close-with-prejudice rule; raw defect evidence became path-ambiguous under D-10 BGP exclusion or otherwise failed the locked corroboration branch.

**Report:** See `.planning/phases/221-matrix-evidence-closeout-scope-a2/221-CLOSEOUT.md`
**Matrix base_sha:** `50f3d5136830c284b190b29de939a84406531ecc`
**Phase 220 YAML SHA:** `62f5532095f9c4e34fe485b3a0510ad26e3cf2ea`
**Closeout written:** 2026-06-02T12:30:57Z

### Close-With-Prejudice Rule (CRITERIA-02, verbatim from REQUIREMENTS.md)

> - [x] **CRITERIA-02**: Close-with-prejudice rule documented: if matrix verdict is again `ambiguous`, the folded `2026-04-08-investigate-tcp-12down` todo is closed-with-prejudice and no v1.48+ follow-up may reopen the thread without independent new evidence (e.g., a real production p99 incident captured in DB).
