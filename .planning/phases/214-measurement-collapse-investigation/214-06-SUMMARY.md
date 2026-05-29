---
phase: 214-measurement-collapse-investigation
plan: 06
status: complete
completed: 2026-05-29
tags: [report, matrix, closure, todo-closure, observational]
---

# 214-06 Summary

## Outcome

Closed the Phase 214 calendar-gated matrix/report step.

The official three-window Spectrum `tcp_12down` matrix is complete and aggregated in `.planning/phases/214-measurement-collapse-investigation/evidence/matrix-summary.json`.

Final matrix verdict: `ambiguous`.

Primary driver: `reflector_loss`.

Signal disposition: `none`.

Folded todo decision: carried-narrower; the todo remains in `.planning/todos/pending/` with a Phase 214 follow-up section.

## Official Windows

| Window | Run Dir | p50_ms | p95_ms | p99_ms | Verdict | Primary Driver |
|---|---|---:|---:|---:|---|---|
| daytime | `RUN-20260528T150507Z` | 37.0 | 267.0 | 606.0 | ambiguous | reflector_loss |
| prime-time | `RUN-20260529T000507Z` | 37.0 | 106.0 | 560.0 | ambiguous | reflector_loss |
| off-peak | `RUN-20260529T060507Z` | 32.7 | 62.2 | 120.0 | pass | external_path |

## Artifacts

- `.planning/phases/214-measurement-collapse-investigation/214-REPORT.md`
- `.planning/phases/214-measurement-collapse-investigation/evidence/matrix-summary.json`
- `.planning/phases/214-measurement-collapse-investigation/evidence/RUN-20260528T150507Z/`
- `.planning/phases/214-measurement-collapse-investigation/evidence/RUN-20260529T000507Z/`
- `.planning/phases/214-measurement-collapse-investigation/evidence/RUN-20260529T060507Z/`
- `.planning/phases/214-measurement-collapse-investigation/evidence/supplemental-vultr/`
- `.planning/todos/pending/2026-04-08-investigate-tcp-12down-latency-spikes-under-multi-flow-downl.md`

## Supplemental Evidence

Supplemental Vultr runs were captured after the official off-peak window. They are not part of the canonical matrix, but they support target/path sensitivity as a live hypothesis.

- `zylone.org`: p50 `745 ms`, p95 `761 ms`, p99 `767 ms`, median throughput `277.6 Mbit/s`
- `planetcaravan.org`: p50 `651 ms`, p95 `689 ms`, p99 `701 ms`, median throughput `277.9 Mbit/s`
- LibreQoS CLI session `6901cfb9-6ed4-4d6a-8557-e97160eed1d1`: Dallas endpoint, download-side bufferbloat `+49.9 ms`, total grade `B`

## Verification

- `PHASE214_BASE_SHA=471b98927039bcb4c05c02fd63b9bdc98d3e2ca6 .venv/bin/pytest tests/test_phase214_mutation_boundary.py::test_report_has_no_mutation_recommendation_tokens tests/test_phase214_mutation_boundary.py::test_no_src_wanctl_diff -x -q` -> `2 passed in 0.11s`
- `PHASE214_BASE_SHA=471b98927039bcb4c05c02fd63b9bdc98d3e2ca6 .venv/bin/pytest tests/test_phase214_*.py -q` -> `52 passed in 1.96s`

## Safety

- No `src/wanctl/` edits.
- No RouterOS writes.
- No production service restarts.
- No steering toggles.
- No `/etc/wanctl/*.yaml` edits.
