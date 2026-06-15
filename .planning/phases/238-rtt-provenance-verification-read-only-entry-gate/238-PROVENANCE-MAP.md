# Phase 238 Provenance Map: Live Steering RTT Source

**Captured:** 2026-06-14T22:30Z  
**Production host:** `cake-shaper`  
**Posture:** read-only evidence only. The live captures below used `curl` GETs, `sha256sum`, and earlier `ip rule` / `ip route get` reads. No production config, service, routing, CAKE mode, or controller source was mutated.

## Verdict Shape

This artifact records the PROV-01 evidence and PROV-02 recommendation. It does **not** pre-bake the binding A/B verdict.

**Operator ratification slot:**

- Selection: A
- Ratifier: Kevin
- Ratification note: operator approved Interpretation A after reviewing this map.

## Live RTT Source — Verified Code-Path Trace

Fresh source check was re-run against current checkout before this transcription.

### Steering consumes autorate `/health` measurement, not `RTTMeasurement`

1. `src/wanctl/steering/daemon.py:2080-2089` — `run_cycle()` enters `PerfTimer("steering_rtt_measurement")` and calls `current_rtt = self._measure_current_rtt_with_retry()`; if no RTT is available the cycle is skipped.
2. `src/wanctl/steering/daemon.py:1769-1815` — `_measure_current_rtt_with_retry()` wraps `self.measure_current_rtt` with retry and optional `history_fallback`.
3. `src/wanctl/steering/daemon.py:1755-1767` — `measure_current_rtt()` first calls `self.baseline_loader.load_live_rtt()` and labels success as `autorate_health`; only then does it try `load_live_irtt_rtt()`.
4. `src/wanctl/steering/daemon.py:1000-1024` — `BaselineLoader.load_live_rtt()` reads the target WAN's `measurement` object and accepts only `available is True` with numeric `raw_rtt_ms` and `staleness_sec` below `STALE_AUTORATE_MEASUREMENT_THRESHOLD_SECONDS`.
5. `src/wanctl/steering/daemon.py:1052-1076` — `_load_target_wan_health()` opens `self.config.primary_health_url`, parses JSON, and selects the WAN entry whose `name` matches `self.config.primary_wan`.

### Constructed `RTTMeasurement` is dead in this topology

- `src/wanctl/steering/daemon.py:2554-2559` constructs `RTTMeasurement(logger, timeout_ping=config.timeout_ping, aggregation_strategy=RTTAggregationStrategy.MEDIAN, log_sample_stats=False)` with **no `source_ip=` argument**.
- `src/wanctl/steering/daemon.py:1137` stores that object as `self.rtt_measurement`.
- Fresh grep of `src/wanctl/steering/daemon.py` found `self.rtt_measurement` only at the assignment site; no `.ping_host` or measurement call is made through it.
- `src/wanctl/rtt_measurement.py:139-172` accepts `source_ip`; `src/wanctl/rtt_measurement.py:199-207` passes it to `icmplib.ping(..., source=self.source_ip)`, the `-S`-equivalent binding. The dead steering construction leaves this unset.

## Production raw_rtt_ms Producer — Bridge, With Load-Bearing Crux

The live producer is the deployed bridge executable named in systemd, not an in-process wanctl Python module:

- `deploy/systemd/cake-autorate-spectrum-state-bridge.service:17` — `ExecStart=/usr/local/sbin/cake-autorate-spectrum-state-bridge`.
- `deploy/systemd/cake-autorate-att-state-bridge.service:17` — `ExecStart=/usr/local/sbin/cake-autorate-att-state-bridge`.
- Repo source for both deployed copies is `deploy/scripts/cake-autorate-{spectrum,att}-state-bridge`.

The important refinement: bridge `raw_rtt_ms` is **not a fresh path RTT sample**.

- `deploy/scripts/cake-autorate-spectrum-state-bridge:65-73` — `rates_from_row()` parses DL/UL rates and status only; no RTT value is parsed from the cake-autorate log row.
- `deploy/scripts/cake-autorate-spectrum-state-bridge:96-104` — `old_rtt()` carries `ewma.baseline_rtt` and `ewma.load_rtt` forward from the existing state file, defaulting to `DEFAULT_BASELINE_RTT` (`:23`).
- `deploy/scripts/cake-autorate-spectrum-state-bridge:191-218` — `build_state()` writes `ewma: {baseline_rtt: baseline, load_rtt: load}` using the carried-forward `old_rtt()` values.
- `deploy/scripts/cake-autorate-spectrum-state-bridge:249-271` — `health_payload()` sets `measurement.raw_rtt_ms` from `ewma.get("load_rtt")` and exposes it with `available` and `staleness_sec`.

Therefore, in the current external cake-autorate topology, steering's accepted `raw_rtt_ms` is carried-forward `ewma.load_rtt` / `DEFAULT_BASELINE_RTT`, not the real per-cycle ICMP RTT. The real RTT signal lives upstream in bash cake-autorate, outside the wanctl Python `RttBackend` seam.

## Live /health Measurement Blocks

These are production `/health` captures supplied by the operator. Steering consumes only `measurement.available`, `measurement.raw_rtt_ms`, and `measurement.staleness_sec`; `src/wanctl/health_check.py` emits a richer native shape for wanctl@ mode, so Phase 244 must preserve those three fields byte-for-byte.

### Spectrum production capture

- Command: `ssh cake-shaper 'curl -fsS --max-time 5 http://10.10.110.223:9101/health' | python3 -m json.tool`
- Host: `cake-shaper`
- Timestamp: 2026-06-14T22:30Z
- Provenance: production bridge `/health` GET, read-only

```json
{
  "name": "spectrum",
  "measurement": {
    "available": true,
    "raw_rtt_ms": 22.60283333286988,
    "staleness_sec": 0.23070859909057617
  },
  "irtt": {
    "available": false
  },
  "download": {
    "state": "GREEN",
    "current_rate_mbps": 524.869,
    "qdisc_bandwidth": "525Mbit"
  },
  "upload": {
    "state": "GREEN",
    "current_rate_mbps": 18.0,
    "qdisc_bandwidth": "18Mbit"
  },
  "congestion": {
    "dl_state": "GREEN",
    "ul_state": "GREEN"
  },
  "last_applied": {
    "dl_rate": 524869000,
    "ul_rate": 18000000
  }
}
```

### ATT production capture

- Command: `ssh cake-shaper 'curl -fsS --max-time 5 http://10.10.110.227:9101/health' | python3 -m json.tool`
- Host: `cake-shaper`
- Timestamp: 2026-06-14T22:30Z
- Provenance: production bridge `/health` GET, read-only

```json
{
  "name": "att",
  "measurement": {
    "available": true,
    "raw_rtt_ms": 28.19181289136989,
    "staleness_sec": 1.0113909244537354
  },
  "irtt": {
    "available": false
  },
  "download": {
    "state": "GREEN",
    "current_rate_mbps": 95.0,
    "qdisc_bandwidth": "95Mbit"
  },
  "upload": {
    "state": "GREEN",
    "current_rate_mbps": 19.0,
    "qdisc_bandwidth": "19Mbit"
  },
  "congestion": {
    "dl_state": "GREEN",
    "ul_state": "GREEN"
  },
  "last_applied": {
    "dl_rate": 95000000,
    "ul_rate": 19000000
  }
}
```

## Deployed Bridge Identity + Repo-vs-Prod Reconciliation

### Captured SHA-256 values

- Production command: `ssh cake-shaper 'sha256sum /usr/local/sbin/cake-autorate-spectrum-state-bridge /usr/local/sbin/cake-autorate-att-state-bridge'`
- Production host: `cake-shaper`
- Production timestamp: 2026-06-14T22:30Z
- Repo command: `sha256sum deploy/scripts/cake-autorate-spectrum-state-bridge deploy/scripts/cake-autorate-att-state-bridge`
- Repo host: local checkout `/home/kevin/projects/wanctl`
- Repo timestamp: 2026-06-14T22:30Z

| Source     | Path                                                  | SHA-256                                                            |
| ---------- | ----------------------------------------------------- | ------------------------------------------------------------------ |
| production | `/usr/local/sbin/cake-autorate-spectrum-state-bridge` | `cde33afc0a889c8a431dcccf1c1b51e4dc10db4611a0ce454ac3dc4aaf495bee` |
| production | `/usr/local/sbin/cake-autorate-att-state-bridge`      | `cde33afc0a889c8a431dcccf1c1b51e4dc10db4611a0ce454ac3dc4aaf495bee` |
| repo       | `deploy/scripts/cake-autorate-spectrum-state-bridge`  | `cde33afc0a889c8a431dcccf1c1b51e4dc10db4611a0ce454ac3dc4aaf495bee` |
| repo       | `deploy/scripts/cake-autorate-att-state-bridge`       | `cde33afc0a889c8a431dcccf1c1b51e4dc10db4611a0ce454ac3dc4aaf495bee` |

**Reconciliation:** all four bridge-file entries match exactly. The deployed production bridge executables are byte-identical to the repo bridge scripts at this checkout. This confirms the code-path trace above applies to the production `raw_rtt_ms` producer.

Auxiliary transcript digests, included only to make capture provenance auditable and distinct from the bridge-file identity rows above:

- spectrum health transcript digest: `bd6bc68a6b62ca00e25b0e18393101f0a76d0d315dd99327e66e0e2450872d92`
- att health transcript digest: `0b3e6a9c87192f5f66a6f497dce20c1012056592729dc68ef766201484c77869`
- deployed sha transcript digest: `6dc4b271b4d56840934fe95c733a914ebc8f09e09058b65c42055688ab26f675`
- repo sha transcript digest: `4080d212ae44c544382d0bb24e30be3fe8c14be6654ed4c543a2bb7e258b9ef4`

## PROV-03 Cross-Reference: Egress Proof PASSES (Corrected Criterion)

PROV-03 is satisfied. The Plan 02 proof originally returned non-pass against an **invalid expected-dev criterion**; Plan 04 corrected the criterion to match this topology and re-ran the read-only proof, which now PASSES for both WANs.

**Criterion correction (the real root cause was a plan-level criterion error, not topology drift):**
PROV-03 only requires proving `fping -S <source_ip>` would egress the intended WAN under the host's current `ip rule` policy routing. The shaper host's `ip route get` always resolves egress device `ens18` (the host NIC toward the router); WAN separation is expressed by the **source-bound router-hop** — source IP plus the distinct source-bound route key — not by a named modem device. The original criterion expected `dev spec-modem` / `dev att-modem`, but those are cake-autorate **downstream `ul_if` labels** from `configs/cake-autorate/config.{spectrum,att}.sh`; they live below the host route lookup and cannot appear in `ip route get` output in this topology. They were never valid expected host-route devs.

The corrected PASS criterion is: Spectrum `src 10.10.110.223 + dev ens18`; ATT `from/src 10.10.110.227 + dev ens18`; distinct source-bound route keys between the two WANs. This is a source-bound router-hop proof — it validates source-bound egress toward the router, **not** downstream modem-interface labels.

- Evidence artifact: `.planning/phases/238-rtt-provenance-verification-read-only-entry-gate/evidence/egress-proof-live-20260614T222118Z.json`
- Capture timestamp: 2026-06-15T11:31:32Z (corrected-criterion re-run)
- Host: `cake-shaper`
- Provenance: production read-only `ip rule` and `ip route get` queries via committed proof script
- Verdict: PASS for both WANs (every reflector `pass:true`, `distinct_paths_check.pass:true`)

### ip rule block

```text
0:      from all lookup local
32766:  from all lookup main
32767:  from all lookup default
```

### Spectrum ip route get output

Corrected criterion: default route from `10.10.110.223`, expected host egress dev `ens18`. Observed `src 10.10.110.223 dev ens18` → PASS. (Source-bound router-hop egress confirmed; `spec-modem` is a downstream `ul_if` label, not a host route dev.)

```text
1.1.1.1 via 10.10.110.1 dev ens18 src 10.10.110.223 uid 1000
    cache

9.9.9.9 via 10.10.110.1 dev ens18 src 10.10.110.223 uid 1000
    cache

208.67.222.222 via 10.10.110.1 dev ens18 src 10.10.110.223 uid 1000
    cache
```

### ATT ip route get output

Corrected criterion: `from 10.10.110.227`, expected host egress dev `ens18`. Observed `from 10.10.110.227 dev ens18` → PASS (the `from` token supplies the source when Linux omits a separate `src`). Source-bound router-hop egress confirmed; `att-modem` is a downstream `ul_if` label, not a host route dev.

```text
1.1.1.1 from 10.10.110.227 via 10.10.110.1 dev ens18 uid 1000
    cache

8.8.8.8 from 10.10.110.227 via 10.10.110.1 dev ens18 uid 1000
    cache

151.101.1.57 from 10.10.110.227 via 10.10.110.1 dev ens18 uid 1000
    cache
```

**PROV-03 truth:** PASS under the corrected source-bound router-hop criterion — distinct path classification passes and both WANs resolve the expected source IP on host egress dev `ens18`. The proof validates that `fping -S <source_ip>` egresses the intended WAN toward the router; it does **not** assert egress on a named modem interface. Downstream Phase 245 must read PROV-03 as a source-bound router-hop guarantee (correct source IP + distinct route key), not as a claim about downstream `ul_if` modem labels (`spec-modem` / `att-modem`).

## A/B Target Recommendation for Operator Ratification

### Interpretation A — revive steering's own pinger as the live RTT source

Interpretation A treats the relevant A/B target as steering's currently-dead `RTTMeasurement` path. Phase 239 would place the backend seam behind that pinger, Phase 241 would add fping, and Phase 245 would compare icmplib-vs-fping on a real steering-consumed RTT path.

**Why A is viable:** it is reachable within v1.53 and produces a real per-cycle ICMP RTT for the live steering cycle. That is the only target in this milestone that can generate a trustworthy icmplib-vs-fping comparison on real traffic.

**Tradeoff:** A touches the steering RTT consumption path, so it has higher SAFE-17 and operational blast radius than leaving steering on `/health`. It also requires source binding to be designed correctly: `daemon.py:2554` currently passes no `source_ip`, while `rtt_measurement.py:206` needs `source=self.source_ip` for the `-S`-equivalent binding.

### Interpretation B — evaluate at the autorate/bridge producer

Interpretation B treats the relevant A/B target as the producer of `/health measurement.raw_rtt_ms`.

**Why B is attractive:** it has lower immediate steering-path blast radius if the producer can be swapped or evaluated before steering consumes the value.

**Why B is not viable for high-fidelity v1.53 evidence in the current topology:** the live producer is external bash cake-autorate plus the bridge. The bridge value is carried-forward `ewma.load_rtt` / `DEFAULT_BASELINE_RTT`, not a fresh RTT sample, and the real bash cake-autorate pinger is outside the wanctl Python `RttBackend` seam. The wanctl-owned native autorate producer is not live, and standing it up is deferred out of v1.53.

### Recommendation: lean Interpretation A on evidence fidelity

Using the D-03 rubric, fidelity wins over minimal blast radius. A is the only v1.53-reachable path that can make Phase 245's icmplib-vs-fping verdict meaningful on real steering RTT. B would be lower touch, but in the live topology it compares against a carried-forward baseline rather than a real RTT signal.

This is a recommendation, not the binding verdict. The binding selection is the ratification line at the top of this artifact.

## Requirements Mapping

| Requirement | Evidence in this map                                                                   | Status                                               |
| ----------- | -------------------------------------------------------------------------------------- | ---------------------------------------------------- |
| PROV-01     | Verified steering consumption trace, live `/health` captures, deployed bridge identity | Satisfied by read-only evidence                      |
| PROV-02     | Both A/B interpretations, fidelity-rubric recommendation, explicit ratification slot   | Satisfied by operator Selection: A                   |
| PROV-03     | Corrected source-bound router-hop egress proof, both WANs PASS on `ens18`              | Satisfied by corrected read-only host-route evidence |
| SAFE-17     | Lightweight read-only boundary gate re-run after Plan 04 gap closure                   | Satisfied — `safe17-boundary-238.json` passed:true, zero controller-path diff |

|
