# Leg B Manifest — Ceiling 20

- Harness args: `--bind-map spectrum=10.10.110.226 --wans spectrum --tests tcp_upload --flent-duration 120 --evidence-root .planning/phases/215-spectrum-upload-reclaim-canary/evidence/leg-b-ceiling20`
- Same bind/host/duration as leg A: yes (`spectrum=10.10.110.226`, host `dallas`, 120s).
- Attempts: 3

- `RUN-20260529T145701Z`: 2026-05-29T14:57:01+00:00 to 2026-05-29T14:59:38+00:00
- `RUN-20260529T150034Z`: 2026-05-29T15:00:34+00:00 to 2026-05-29T15:03:11+00:00
- `RUN-20260529T150330Z`: 2026-05-29T15:03:30+00:00 to 2026-05-29T15:06:07+00:00

## Final scored attempt

- Extract: `evidence/leg-b-ceiling20/leg-b-extract.json`
- p95 latency: 45.6 ms
- p99 latency: 57.6 ms
- upload median: 15.29909187886127 Mbps
- Gate verdict: `void` (rc 2) — collapsed_measurement_window
