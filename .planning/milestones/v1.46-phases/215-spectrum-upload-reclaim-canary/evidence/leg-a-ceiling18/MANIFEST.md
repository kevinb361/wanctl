# Leg A Manifest — Ceiling 18

- Captured UTC: 2026-05-29T14:51:58+00:00 to 2026-05-29T14:54:36+00:00
- Run directory: `.planning/phases/215-spectrum-upload-reclaim-canary/evidence/leg-a-ceiling18/RUN-20260529T145158Z`
- Harness: `scripts/phase213-baseline-capture.sh`
- Args: `--bind-map spectrum=10.10.110.226 --wans spectrum --tests tcp_upload --flent-duration 120 --evidence-root .planning/phases/215-spectrum-upload-reclaim-canary/evidence/leg-a-ceiling18`
- Host: `dallas`
- Bind map: `{'att': 'fixture', 'spectrum': '10.10.110.226'}`
- Egress observed: `{'spectrum': '70.123.224.169'}`
- Test start/end unix: `1780066328` / `1780066459`
- Health NDJSON: `.planning/phases/215-spectrum-upload-reclaim-canary/evidence/leg-a-ceiling18/RUN-20260529T145158Z/spectrum/tcp_upload/health-spectrum.ndjson`
- Flent artifact: `.planning/phases/215-spectrum-upload-reclaim-canary/evidence/leg-a-ceiling18/RUN-20260529T145158Z/spectrum/tcp_upload/flent`
- Extract JSON: `.planning/phases/215-spectrum-upload-reclaim-canary/evidence/leg-a-ceiling18/leg-a-extract.json`

## Extract Summary

- p95 latency: 45.9 ms
- p99 latency: 56.3 ms
- upload throughput median: 13.74262903532971 Mbps
- upload throughput key: `TCP upload`

## Leg-B Reuse Contract

Leg B must reuse the same bind/host/test/duration arguments except for `--evidence-root`, replacing `leg-a-ceiling18` with `leg-b-ceiling20`.
