# Phase 113 Plan 01: CAKE Configuration & DSCP Classification Findings

**Date:** 2026-03-26
**VM:** cake-shaper (10.10.110.223)
**Router:** MikroTik RB5009 (10.10.99.1)

---

## NETENG-01: CAKE Parameter Verification

### Methodology

1. Read production YAML configs (`/etc/wanctl/{spectrum,att}.yaml`) to extract expected CAKE parameters
2. Merged config values with direction-aware defaults from `cake_params.py` (UPLOAD_DEFAULTS, DOWNLOAD_DEFAULTS, TUNABLE_DEFAULTS)
3. Read actual CAKE qdisc state via `tc -j qdisc show` on the production VM
4. Compared expected vs actual for each WAN and each direction

**Note on wanctl-check-cake:** The `wanctl-check-cake` CLI tool was designed for the original MikroTik RouterOS deployment (REST/SSH transport). It does not support the `linux-cake` transport used on the cake-shaper VM. The tool exits with `Error: failed to create router client: Unsupported transport: linux-cake`. For linux-cake deployments, direct `tc -j qdisc show` readback is the correct verification method. The `LinuxCakeBackend.validate_cake()` method performs this same readback comparison programmatically at daemon startup.

### Spectrum WAN

**Config source:** `/etc/wanctl/spectrum.yaml`
- `cake_params.overhead: "docsis"`
- `cake_params.memlimit: "32mb"`
- `cake_params.rtt: "100ms"`
- `cake_params.download_interface: "ens17"`
- `cake_params.upload_interface: "ens16"`

#### Spectrum Upload (ens16)

Defaults applied: UPLOAD_DEFAULTS (ack-filter=True, ingress=False, ecn=False) + TUNABLE_DEFAULTS

| Parameter | Expected (config+defaults) | Actual (tc readback) | Match |
|-----------|---------------------------|---------------------|-------|
| diffserv | diffserv4 | diffserv4 | YES |
| overhead | 18 (docsis) | 18 | YES |
| atm | noatm (docsis) | noatm | YES |
| ack-filter | enabled | enabled | YES |
| split_gso | true | true | YES |
| ingress | false | false | YES |
| memlimit | 33554432 (32mb) | 33554432 | YES |
| rtt | 100000 (100ms) | 100000 | YES |
| mpu | (not configured) | 64 | N/A (tc default) |
| nat | (not configured) | false | N/A (tc default) |
| wash | (not configured) | false | N/A (tc default) |
| flowmode | (not configured) | triple-isolate | N/A (tc default) |
| bandwidth | (runtime-managed) | 4750000 | N/A (dynamic) |

#### Spectrum Download (ens17)

Defaults applied: DOWNLOAD_DEFAULTS (ack-filter=False, ingress=True, ecn=True) + TUNABLE_DEFAULTS

| Parameter | Expected (config+defaults) | Actual (tc readback) | Match |
|-----------|---------------------------|---------------------|-------|
| diffserv | diffserv4 | diffserv4 | YES |
| overhead | 18 (docsis) | 18 | YES |
| atm | noatm (docsis) | noatm | YES |
| ack-filter | disabled | disabled | YES |
| split_gso | true | true | YES |
| ingress | true | true | YES |
| memlimit | 33554432 (32mb) | 33554432 | YES |
| rtt | 100000 (100ms) | 100000 | YES |
| mpu | (not configured) | 64 | N/A (tc default) |
| nat | (not configured) | false | N/A (tc default) |
| wash | (not configured) | false | N/A (tc default) |
| flowmode | (not configured) | triple-isolate | N/A (tc default) |
| bandwidth | (runtime-managed) | 117500000 | N/A (dynamic) |

**Note on ECN:** DOWNLOAD_DEFAULTS specifies `ecn: True`, but `LinuxCakeBackend.initialize_cake()` does not pass the `ecn` flag to `tc`. Comment in code: "ecn is excluded -- not supported by iproute2-6.15.0's tc, and CAKE enables ECN by default on all tins anyway." This is correct behavior -- CAKE's default is ECN-enabled, so omitting the flag achieves the desired result. The tc JSON readback does not expose ECN state directly in the options block (it is per-tin), so this is consistent.

### ATT WAN

**Config source:** `/etc/wanctl/att.yaml`
- `cake_params.overhead: "bridged-ptm"`
- `cake_params.memlimit: "32mb"`
- `cake_params.rtt: "100ms"`
- `cake_params.download_interface: "ens28"`
- `cake_params.upload_interface: "ens27"`

#### ATT Upload (ens27)

Defaults applied: UPLOAD_DEFAULTS (ack-filter=True, ingress=False, ecn=False) + TUNABLE_DEFAULTS

| Parameter | Expected (config+defaults) | Actual (tc readback) | Match |
|-----------|---------------------------|---------------------|-------|
| diffserv | diffserv4 | diffserv4 | YES |
| overhead | 22 (bridged-ptm) | 22 | YES |
| atm | ptm (bridged-ptm) | ptm | YES |
| ack-filter | enabled | enabled | YES |
| split_gso | true | true | YES |
| ingress | false | false | YES |
| memlimit | 33554432 (32mb) | 33554432 | YES |
| rtt | 100000 (100ms) | 100000 | YES |
| nat | (not configured) | false | N/A (tc default) |
| wash | (not configured) | false | N/A (tc default) |
| flowmode | (not configured) | triple-isolate | N/A (tc default) |
| bandwidth | (runtime-managed) | 2250000 | N/A (dynamic) |

**Note:** ATT upload (ens27) does not have `mpu` in the tc readback, unlike Spectrum interfaces which show `mpu: 64`. This is cosmetic -- the field is absent from the JSON entry but the default kernel behavior applies regardless.

#### ATT Download (ens28)

Defaults applied: DOWNLOAD_DEFAULTS (ack-filter=False, ingress=True, ecn=True) + TUNABLE_DEFAULTS

| Parameter | Expected (config+defaults) | Actual (tc readback) | Match |
|-----------|---------------------------|---------------------|-------|
| diffserv | diffserv4 | diffserv4 | YES |
| overhead | 22 (bridged-ptm) | 22 | YES |
| atm | ptm (bridged-ptm) | ptm | YES |
| ack-filter | disabled | disabled | YES |
| split_gso | true | true | YES |
| ingress | true | true | YES |
| memlimit | 33554432 (32mb) | 33554432 | YES |
| rtt | 100000 (100ms) | 100000 | YES |
| nat | (not configured) | false | N/A (tc default) |
| wash | (not configured) | false | N/A (tc default) |
| flowmode | (not configured) | triple-isolate | N/A (tc default) |
| bandwidth | (runtime-managed) | 11875000 | N/A (dynamic) |

### wanctl-check-cake Tool Status

The `wanctl-check-cake` CLI tool does not support the `linux-cake` transport. When invoked:

```
$ sudo PYTHONPATH=/opt ROUTER_PASSWORD=*** python3 -m wanctl.check_cake /etc/wanctl/spectrum.yaml --json
Error: failed to create router client: Unsupported transport: linux-cake
```

This is expected behavior -- the tool was built for MikroTik RouterOS REST/SSH backends to verify CAKE queue trees on the router. With the v1.21 migration to linux-cake (CAKE on the VM itself), the correct verification method is:

1. **At daemon startup:** `LinuxCakeBackend.validate_cake()` performs tc readback verification automatically
2. **For manual audits:** `tc -j qdisc show` provides machine-readable JSON readback (used in this audit)

**Recommendation:** A future enhancement could extend `wanctl-check-cake` to support linux-cake transport by reading `tc -j qdisc show` locally instead of querying the router. This is not a correctness issue -- the validation happens at startup via the backend code.

### CAKE Parameter Verification Verdict

**PASS** -- All CAKE parameters for both WANs (Spectrum and ATT) match their expected values from config YAML merged with direction-aware defaults from `cake_params.py`. Verified parameters: diffserv, overhead, atm mode, ack-filter, split-gso, ingress, memlimit, and rtt. No discrepancies found.

### Raw tc JSON Readback

<details>
<summary>Full tc -j qdisc show output (click to expand)</summary>

```json
[
  {"kind":"noqueue","handle":"0:","dev":"lo","root":true,"refcnt":2,"options":{}},
  {"kind":"fq_codel","handle":"0:","dev":"ens18","root":true,"refcnt":2,"options":{"limit":10240,"flows":1024,"quantum":1514,"target":4999,"interval":99999,"memory_limit":33554432,"ecn":true,"drop_batch":64}},
  {"kind":"cake","handle":"8007:","dev":"ens16","root":true,"refcnt":9,"options":{"bandwidth":4750000,"diffserv":"diffserv4","flowmode":"triple-isolate","nat":false,"wash":false,"ingress":false,"ack-filter":"enabled","split_gso":true,"rtt":100000,"raw":false,"atm":"noatm","overhead":18,"mpu":64,"memlimit":33554432,"fwmark":"0"}},
  {"kind":"cake","handle":"800a:","dev":"ens17","root":true,"refcnt":9,"options":{"bandwidth":117500000,"diffserv":"diffserv4","flowmode":"triple-isolate","nat":false,"wash":false,"ingress":true,"ack-filter":"disabled","split_gso":true,"rtt":100000,"raw":false,"atm":"noatm","overhead":18,"mpu":64,"memlimit":33554432,"fwmark":"0"}},
  {"kind":"cake","handle":"8005:","dev":"ens27","root":true,"refcnt":9,"options":{"bandwidth":2250000,"diffserv":"diffserv4","flowmode":"triple-isolate","nat":false,"wash":false,"ingress":false,"ack-filter":"enabled","split_gso":true,"rtt":100000,"raw":false,"atm":"ptm","overhead":22,"memlimit":33554432,"fwmark":"0"}},
  {"kind":"cake","handle":"8004:","dev":"ens28","root":true,"refcnt":9,"options":{"bandwidth":11875000,"diffserv":"diffserv4","flowmode":"triple-isolate","nat":false,"wash":false,"ingress":true,"ack-filter":"disabled","split_gso":true,"rtt":100000,"raw":false,"atm":"ptm","overhead":22,"memlimit":33554432,"fwmark":"0"}},
  {"kind":"noqueue","handle":"0:","dev":"br-att","root":true,"refcnt":2,"options":{}},
  {"kind":"noqueue","handle":"0:","dev":"br-spectrum","root":true,"refcnt":2,"options":{}}
]
```

</details>

---
