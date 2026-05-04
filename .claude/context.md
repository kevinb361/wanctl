# wanctl - Technical Context

Current project-specific operational context for local work.

## Core Runtime

`wanctl` is a production, long-running adaptive CAKE controller for MikroTik RouterOS with optional WAN steering.

Current assumptions:
- Python `>=3.11`
- Code installs to `/opt/wanctl`
- Config lives in `/etc/wanctl`
- State lives in `/var/lib/wanctl`
- Logs live in `/var/log/wanctl`
- Runtime files live in `/run/wanctl`
- Active systemd units are `wanctl@<wan>.service` and optional `steering.service`

## Router Access

### MikroTik Router

**Router:** RB5009 at `10.10.99.1`

**REST API:** preferred transport
- Host: `10.10.99.1`
- Port: `443`
- Password source: `/etc/wanctl/secrets` via `ROUTER_PASSWORD`

**SSH Access:** still supported
```bash
ssh -i ~/.ssh/mikrotik_cake admin@10.10.99.1
```

**Key Location:** `~/.ssh/mikrotik_cake`

## Active Operational Flow

Primary scripts:
- `scripts/install.sh`
- `scripts/deploy.sh`
- `scripts/install-systemd.sh`

Primary unit files:
- `deploy/systemd/wanctl@.service`
- `deploy/systemd/steering.service`

Legacy timer-era helper scripts in `scripts/` are intentionally stubbed and should not be used as active deployment guidance.

## Development Commands

```bash
.venv/bin/pytest tests/ -v
.venv/bin/ruff check src/ tests/
.venv/bin/mypy src/wanctl/
.venv/bin/ruff format src/ tests/
```

Focused hot-path regression slice:

```bash
.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q
```

## Useful Operational Checks

```bash
./scripts/soak-monitor.sh
ssh <host> 'journalctl -u wanctl@<wan> -f'
ssh <host> 'curl -s http://127.0.0.1:9101/health | python3 -m json.tool'
```

## Change Constraints

- Change conservatively; this is production network-control software.
- Do not alter control logic, thresholds, timing, or safety bounds without explicit approval.
- Keep the controller link-agnostic; deployment-specific behavior belongs in YAML.
- Keep docs and scripts aligned with the current service-based deployment model.

## Current References

Use these as the primary current docs:
- `README.md`
- `CLAUDE.md`
- `AGENTS.md`
- `docs/GETTING-STARTED.md`
- `docs/CONFIGURATION.md`
- `docs/DEPLOYMENT.md`
- `docs/TESTING.md`
- `docs/STEERING.md`
- `docs/SILICOM-BYPASS.md`

## Current Hardware Mapping

- `cake-shaper` uses the Silicom `PE2G4BPI35A-SD REV:1.1` passthrough NIC for both inline WAN pairs.
- ATT uses `att-modem` / `att-router`.
- Spectrum uses `spec-modem` / `spec-router`; these names now refer to the Silicom ports, while the old Supermicro ports are `old-spec-modem` / `old-spec-router`.
- The Silicom card supports powered bypass, but verified unpowered fail-open does not work on `odin`; do not rely on it for chassis-power-loss continuity.

## Current Validation Note

- v1.42 Phase 201 Plan 201-08 canary extension is in progress: `scripts/phase200-saturation-canary.sh` now fails closed unless Phase 201 runs explicitly set `PHASE201_DOCSIS_MODE=true` and `PHASE201_SETPOINT_MBPS=12`, while legacy A/B compatibility requires `PHASE201_LEGACY_MODE=true`; the canary also cross-checks DOCSIS/setpoint YAML, probes `/health.wans[0].upload.docsis_mode_active`, verifies remote python3+pyyaml, and gates verdicts on `floor_hit_cycles_total` counter deltas as the primary VALN-06 evidence path.
- v1.42 Phase 201 Plan 201-07 is complete: `scripts/deploy.sh` invokes the Spectrum-scoped predeploy gate before `/opt/wanctl` rsync, derives `REMOTE_SSH_TARGET` from `TARGET_HOST` and `REMOTE_YAML_PATH` from `/etc/wanctl/${WAN_NAME}.yaml` when unset, fails closed on gate errors, and skips ATT/non-Spectrum deploys without inspecting Spectrum YAML.
- v1.42 Phase 201 Plan 201-06 is complete: Spectrum repo YAML opts into DOCSIS upload mode with `setpoint_mbps: 12` as an explicit canary-validated assumption, v1.42.0 version surfaces are aligned, and CHANGELOG/CONFIGURATION document restart-required migration plus the fallback preference of 10 before 14 on setpoint-specific canary failure.
- v1.42 Phase 201 Plan 201-05 is complete: WANController pins restart-required DOCSIS keys and per-WAN `self.logger` INFO emission; `/health.wans[].upload` exposes six additive DOCSIS runtime fields via the HealthCheckHandler rate/hysteresis builder; VALN-06 remains open for Plan 201-11 live canary proof.
- v1.42 Phase 201 controller-core replay (Plan 201-04, complete) treats the Phase 200 Attempt 3 hold-last-expanded corpus as a safety diagnostic, not a synthetic VALN-06 proof: exact RED fast-trip plus post-bounds floor-hit accounting records 1003 floor-hit cycles. The zero-floor VALN-06 gate remains the live Plan 201-11 canary.
- v1.41 Phase 200 is active for per-direction upload RTT bloat thresholds. Plan 200-02 intentionally superseded the v1.40 SAFE-05 replay count pins for `warn_bloat` and `target_bloat` only, using the live post-Plan-01 `wan_controller.py` counts (`warn_bloat=12`, `target_bloat=14`) while preserving the seven non-UL count pins.
- Phase 196 Spectrum cake-primary documented B-leg exceptions were accepted for continuation, but the follow-up tcp_12down throughput check failed at 73.92243773827883 Mbps versus the 532 Mbps acceptance threshold; the A/B comparison remains blocked until passing throughput evidence exists.
- Spectrum Silicom remains on CAKE for normal operation: `spec-modem` upload at 28Mbit, `spec-router` download at 940Mbit, `rtt: "100ms"`, WAN-path reflectors, IRTT disabled provisionally. Gateway-only RTT and `rtt: "1s"` are diagnostic controls only.
- `deploy/systemd/wanctl@.service` must keep `/proc/net` visible because `tc` reads `/proc/net/psched` for HTB timing and burst accounting; do not reintroduce `ProcSubset=pid` while Linux shapers may use HTB.
- `upload_qdisc: "htb_fq_codel"` is an experimental escape hatch. Static tests looked promising, but managed Spectrum testing preserved `256Kb` burst yet still underperformed and drove upload to the 8Mbit floor, so HTB/fq_codel is not the live Spectrum mode.
