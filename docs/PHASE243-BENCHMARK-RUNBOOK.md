# Phase 243 Benchmark Runbook

This runbook is for the operator-gated eight-arm live benchmark. It is not run from
the development VM unless that VM is also the approved WAN host.

## 1. Scope and gate

The benchmark is a hard precondition for Phase 245. It compares `icmplib` and
`fping` under a real transient systemd unit with journal-pipe stdout, CPUAccounting,
and the same network capabilities needed by the production wanctl controller.

The eight arms are:

1. spectrum / icmplib / idle
2. spectrum / fping / idle
3. spectrum / icmplib / under-load
4. spectrum / fping / under-load
5. att / icmplib / idle
6. att / fping / idle
7. att / icmplib / under-load
8. att / fping / under-load

Each arm must run for at least the frozen D-04c floor: max(10k cycles, 30 minutes).

## 2. Isolation setup

Choose exactly one isolation posture before launching arms:

- Throwaway-interface posture: create the bench-only netdevs named by
  `configs/bench/gen-bench-configs.sh` (`bench-spectrum-dl`, `bench-spectrum-ul`,
  `bench-att-dl`, `bench-att-ul`).
- Maintenance-window posture: run only in an operator-approved isolated window where
  the live shapers are inactive for the benchmark duration.

The launcher calls `scripts/phase243-bench-preflight.sh` first. The preflight must
PASS for every arm. It proves the bench config uses throwaway CAKE interfaces,
unique health/metrics ports, isolated lock/state/storage paths, and a linux-cake
writer instead of a production RouterOS writer. It also snapshots stable live qdisc
ownership fields for the post-run untouched proof.

## 3. Capability grant

The transient bench unit must carry both:

- `AmbientCapabilities=CAP_NET_RAW CAP_NET_ADMIN`
- `CapabilityBoundingSet=CAP_NET_RAW CAP_NET_ADMIN`

This mirrors `deploy/systemd/wanctl@.service`, not `deploy/systemd/steering.service`.
Without `CAP_NET_ADMIN`, construction-time CAKE setup on the throwaway interfaces
cannot run as the unprivileged `wanctl` user. Without `CAP_NET_RAW`, the ICMP raw
socket backend does not match production behavior. The pytest launcher contract
asserts these properties are in the executable `systemd-run` argument block.

## 4. Host prechecks

On the approved Spectrum and ATT WAN hosts, confirm:

- `fping --version` works.
- netperf reachability to Dallas Linode `104.200.21.31` works.
- `ip route get 104.200.21.31 from <source_ip>` egresses the expected WAN route key.
- Runtime copies of the bench configs were generated from
  `configs/bench/gen-bench-configs.sh` and not hand-edited into live shaper configs.

## 5. Per-arm launch

Use `scripts/phase243-bench-run.sh` for each arm. The launcher uses a unique
`wanctl-bench-<wan>-<backend>-<load>-<timestamp>` transient unit, `--collect`,
`CPUAccounting=yes`, `WANCTL_LOG_FORMAT=json`, `RuntimeMaxSec`, `User=wanctl`, and
`WorkingDirectory=/opt/wanctl`.

If production `/opt/wanctl` has not yet been updated with the fping backend, stage
the current checkout under a temporary directory on the production host and run the
launcher with `WANCTL_BENCH_CODE_DIR=/var/tmp/wanctl-phase243/wanctl`. This leaves
the installed `/opt/wanctl` tree untouched while still running on the production
host with the production source IPs, qdisc devices, capabilities, and systemd
execution path.

Do not allocate a TTY. The benchmark exists to catch journal-pipe buffering and
cycle-gap behavior. The under-load arm uses the established flent RRUL over netperf
path to `104.200.21.31`; do not substitute synthetic CPU load or another traffic
tool during this gate.

The launcher starts `scripts/phase243-hygiene-sampler.sh` at 1Hz and records
`CPUUsageNSec` start/end/delta into each arm's profile JSON.

Before spending a full 8-arm run, run one short smoke arm with a small
`DURATION_SEC` value on the approved benchmark host. The launcher now fails the
arm immediately if durable cycle evidence is below `DURATION_SEC * CYCLE_HZ` or
if the captured timestamp span is shorter than the requested window. This catches
debug-log retention or evidence plumbing failures before a multi-hour run.

For fping benchmark arms, keep `measurement.fping.cadence_sec` below the
controller's 5s RTT stale limit. The generated Phase 243 fping configs use 2s;
using the historical 10s fping cadence drives the controller into stale-data
fallback cycles and invalidates the cycle-budget comparison.

Load arms get a larger transient unit runtime margin than idle arms because
`flent rrul` can overrun the requested test window while netperf children drain
or time out. If systemd has already collected the transient unit before CPU
accounting is read, the launcher must fail with a CPU evidence error rather than
writing a profile with missing CPU fields.

## 6. Evidence checks before gate evaluation

Before running `scripts/phase243-gate-eval.py`, verify every arm has:

- a non-empty profile JSON with `autorate_cycle_total` count, avg, and p99;
- `cycle.ndjson` copied from the per-arm bench debug log, not reconstructed from
  the retained journald tail;
- `cpu_nsec_start`, `cpu_nsec_end`, `cpu_nsec_delta`, `window_wall_sec`, `n_cores`,
  and `invocation_id`;
- a hygiene NDJSON with fd, zombie, Tasks, and cpu_nsec rows;
- an invocation-scoped journal drain verified from `_SYSTEMD_INVOCATION_ID` JSON
  records before conversion to cycle NDJSON.

## 7. Representativeness and verdict

The same-run icmplib controls must land inside the frozen
`ICMPLIB_REPRESENTATIVE_*_TOL_MS` band. If they do not, treat the run as
`input_error` and rerun on a representative host before trusting any fping result.

Run `scripts/phase243-gate-eval.py` with all eight arms. It writes
`.planning/phases/243-cycle-budget-benchmark-gate/evidence/243-BENCHMARK-VERDICT.json`
against `scripts/phase243-thresholds.json` and embeds preregistration provenance.

`keep icmplib` is a valid passing close. This gate blocks Phase 245 only on a
regression or invalid input; it does not require fping to win.

## 8. Teardown proof

Confirm no `wanctl-bench-*` unit remains active, no bench lock remains, and no stray
flent/netperf/fping child remains from the arm. Confirm the post-run stable qdisc
ownership reduction matches the preflight snapshot for live interfaces; counter churn
is expected and intentionally ignored.

Commit the verdict JSON and per-arm evidence after the operator has reviewed the
outcome.
