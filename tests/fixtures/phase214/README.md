# Phase 214 flent extractor fixtures

`sample-tcp_12down.flent.gz` is a verbatim copy of the repo-root artifact
`tcp_ndown-2026-04-16T035903.274492.prod-tcp-ndown12-hammer-2026-04-16T0359.flent.gz`,
copied on 2026-05-28. Direct schema inspection verified 647
`raw_values['Ping (ms) ICMP']` entries with `{seq, t, val}` records.

`sample-no-raw-values.flent.gz` is a synthesized negative fixture used to drive
the fail-closed `FlentExtractionError` path. Recipe:

```bash
.venv/bin/python3 -c 'import gzip,json; from pathlib import Path; p=Path("tests/fixtures/phase214/sample-no-raw-values.flent.gz"); payload={"metadata":{"T0":"2026-04-16T08:59:03.512987Z","TOTAL_LENGTH":30},"raw_values":{},"results":{},"version":"phase214-negative-fixture","x_values":[]}; gzip.open(p,"wt",encoding="utf-8").write(json.dumps(payload,sort_keys=True)+"\n")'
```

Do not modify these fixtures without a paired test update. `.gitignore` carries
`!tests/fixtures/phase214/*.flent.gz` below the blanket `*.flent.gz` rule so new
Phase 214 flent fixtures under this directory are not silently ignored.

`sample-bad-p99-health.ndjson` is a synthesized 30-second `/health` fixture
matching the live Phase 213 poller key set. Recipe: start at epoch `1779920851`,
emit 1Hz `t_wall` rows, hold `status=healthy` / `download_state=GREEN`, and cycle
`measurement_successful_count` as `0,0,0,2` to model collapse-while-GREEN.
