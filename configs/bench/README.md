# Phase 243 benchmark configs

`gen-bench-configs.sh` is the committed reproducibility artifact for the Phase 243
cycle-budget benchmark. It emits four bench-only configs:

| WAN | Backend | Reused for load arms |
| --- | --- | --- |
| spectrum | icmplib | idle + under-load |
| spectrum | fping | idle + under-load |
| att | icmplib | idle + under-load |
| att | fping | idle + under-load |

The idle/under-load dimension is owned by `scripts/phase243-bench-run.sh`; the YAML
only selects the WAN and RTT backend, so four configs cover the eight benchmark arms.

## Isolation contract

These configs are **bench-only**. They must never be installed as live shapers.

- `router.transport` is `linux-cake`, so CAKE construction targets only the YAML
  `cake_params` interfaces.
- `cake_params.download_interface` / `upload_interface` are throwaway names:
  `bench-<wan>-dl` and `bench-<wan>-ul`. They are intentionally not the live
  `spec-router`, `spec-modem`, `ens28`, or `ens27` interfaces.
- Health and metrics ports are unique bench ports, never live `9101` or `9100`.
- `metrics.enabled` is `false` and `storage.db_path` points under
  `/var/tmp/wanctl-bench`, so the benchmark does not write production metrics DBs.
- `lock_file` and `state_file` contain `bench` and are separate from live
  `/run/wanctl/<wan>.lock` and `/var/lib/wanctl/<wan>_state.json`.
- `ping_source_ip` is the real per-WAN source-binding input for RTT probing.

## Operator netdev setup

Before running a throwaway-interface benchmark posture, the operator creates the
named bench netdevs on the live host and confirms the preflight passes. The exact
device type is an operator choice for the host, but the names must match the YAML:

- `bench-spectrum-dl`
- `bench-spectrum-ul`
- `bench-att-dl`
- `bench-att-ul`

The fail-closed preflight refuses to launch if any bench interface equals a live
shaping interface or if the bench config points at a RouterOS REST/SSH writer.

Generate runtime copies with:

```bash
configs/bench/gen-bench-configs.sh --output-dir /etc/wanctl/bench
```

Do not commit `/etc/wanctl/bench` runtime copies; the generator and tests are the
source of truth.
