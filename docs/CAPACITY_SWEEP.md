# Download Capacity Sweep

`scripts/capacity-sweep.sh` measures how download latency and loss respond to paced load at a series of target rates,
so the usable download rate can be compared across times of day. It is a measurement tool. It does not change the
controller, the shaper, or the endpoint.

## What one sweep measures, and what it does not

For each target rate, the endpoint sends 8 paced TCP streams (`iperf3 -R`, fq socket pacing by default) for
`--step-sec` seconds after a 3 s slow-start omit period, while `fping` samples RTT every 200 ms. Each valid step appends
one CSV row: goodput, retransmits, RTT median/p95/p99 and loss during load, the shaped download range and the CAKE peak
delay from Prometheus.

The **knee** is the first step where loss exceeds 20% or the median RTT exceeds idle + 150 ms. A knee is one
time-of-day observation, not the line's fixed capacity. Treat these as confounders, not as findings about the line:

- **Controller cuts.** The shaper (cake-autorate) reacts to the load. `shaped_dl_min`/`shaped_dl_max` show whether it cut
  during the step; a step whose shaped rate fell below the target measured the controller, not the line.
- **Path.** Each step must pass the path check below, or it is invalid.
- **Endpoint or local CPU.** A small endpoint may saturate near 1 Gbit. Check endpoint CPU before believing a low knee.
- **Household traffic** that starts during the sweep. The idle gate only covers the start of the run.
- **Shaper ceiling.** Targets above the live `max_dl_shaper_rate_kbps` measure CAKE, not the line. The
  `max_dl_config_kbps` column records the live value when `--shaper-ssh` is set.

## Safety and validity rules

| Rule | Behavior | Exit |
|---|---|---|
| Inputs | Label, endpoint, 1-12 strictly ascending integer rates (10-2000 Mbit), step 2-60 s; planned load (steps x (step + 3 s)) at most 360 s | 2 |
| Run lock | One sweep at a time per data dir (`flock`); a second run exits at once | 75 |
| Competing load | Any local `iperf3 -c`, `flent`, `netperf` or `irtt client` before the run or a step: skip/stop (detection only, never killed) | 75 / 1 |
| Failed competing-load check | `pgrep` missing or exiting with anything but 0 (found) / 1 (none): run invalid, no load started | 1 |
| Idle gate | Spectrum CAKE throughput (1 min rate) at every 15 s point of the last 2 minutes must stay below 20 Mbit down **and** 3 Mbit up | 75 |
| Missing telemetry | A Prometheus range that misses any point of its window, has unordered points, or has a non-finite/negative value; a shaper exporter sample older than 30 s; `fping` exiting, stale (newest sample > 3 s old), unparsable, or not covering the step: stop at once, run invalid | 1 |
| Sustained breach | During load, 3 consecutive checks at most 2 s apart of the last 10 pings, each over the limit (loss >= 30% or median > idle + 250 ms): kill the step's load at once | 3 |
| Floor | Shaped download at or below 100 Mbit during a step | 3 |
| Knee | After a valid step: loss > 20% or median > idle + 150 ms ends the sweep normally | 0 |
| Path check | The Spectrum CAKE download byte increase over the step must be at least 80% of the iperf3 bytes received, and the ATT increase at most 20% of them | 1 |
| Tool/parser failure | iperf3 non-zero exit or error JSON, unparsable result | 1 |
| Deadline | The script re-runs itself under `timeout`: at `--wall-sec` it gets TERM, tears down its owned load and ends as `deadline`; KILL follows 30 s later. A step whose worst case (all timeouts included) cannot finish before the deadline is not started (`incomplete`) | 124 / 1 |
| Signals | TERM/INT/HUP: owned process groups get TERM, then KILL, then the run ends as `aborted` | 143/130/129 |
| Option without value | e.g. a trailing `--host`: usage error | 2 |

The breach and knee rules are the ones used in the attended 2026-10-20 sessions. Every child (fping, iperf3 under
`timeout`) starts in its own process group via `setsid`; teardown signals only those groups, never processes found by
name.

Only valid steps are written to the CSV, so a row always means a complete measurement. Every run also leaves
`runs/<label>-<UTC>/result` with `status=` (`complete`, `knee`, `skipped`, `invalid`, `incomplete`, `breach-stop`,
`floor-stop`, `deadline`, `aborted`), the exit code, valid/planned step counts and the reason, plus `sweep.log` and the raw
`fping`/`iperf3` files of every step, valid or not.

## Configuration

Site details are not stored in this repository. In order of precedence: command-line options, `CAPACITY_SWEEP_*`
environment variables, then `~/.config/wanctl-sweep/env` (override with `CAPACITY_SWEEP_CONFIG`). The file holds
`CAPACITY_SWEEP_KEY=VALUE` lines, is parsed rather than sourced, and must not be readable by group or others.
`deploy/capacity-sweep/env.example` lists the keys with placeholders.

The endpoint must run a forking iperf3 server and answer ICMP. An endpoint known to bottleneck below the line rate can
be listed in `CAPACITY_SWEEP_UNSUITABLE_HOSTS` so it is refused.

## Install and use (measurement host, user account)

The host needs bash, iperf3, fping, jq, GNU awk (`awk` must support `asort`; mawk does not), coreutils, util-linux
(`flock`, `setsid`), procps (`pgrep`) and a read-only Prometheus query command (`prom-ro` or `CAPACITY_SWEEP_PROM_CMD`).

jq 1.7 and 1.8 parse `as` bindings next to arithmetic differently (jq 1.8.0 NEWS, "Fix precedence of binding
syntax", #3053): `X + 1 as $n | ...` binds `$n` to `X + 1` under 1.8 but to `1` under earlier releases. The script
keeps the left side of every jq binding a single term, such as a parenthesized expression, so both read it alike;
`tests/test_shell_jq_bindings.py` checks the source form. The script has only been run under jq 1.8.1. A CI failure
with the earlier form ("expected 1 points, got 9") is attributed to an older runner jq by inference: the runner's jq
version was not recorded, and no pre-1.8 jq was available to reproduce it.

```bash
install -D -m 0755 scripts/capacity-sweep.sh ~/.local/bin/wanctl-capacity-sweep
install -D -m 0600 deploy/capacity-sweep/env.example ~/.config/wanctl-sweep/env   # then edit real values
install -D -m 0644 docs/CAPACITY_SWEEP.md ~/.local/share/doc/wanctl/CAPACITY_SWEEP.md

# one attended run
wanctl-capacity-sweep --idle-ms 22 SW3-manual "400 500 600 650 700 750"
echo "exit=$?"; tail -n 7 ~/.local/share/wanctl-sweeps/sweeps.csv
```

Raw data stays outside the repository, under the data dir (default `~/.local/share/wanctl-sweeps`): `sweeps.csv`,
`runs/`, `.lock`.

**Rollback:** remove `~/.local/bin/wanctl-capacity-sweep`, `~/.config/wanctl-sweep/env` and the doc copy. The data dir is
kept unless its owner deletes it. Nothing outside the user's home is touched.

## Scheduled runs (superseded proposal)

**Superseded.** Unpaced multi-stream iperf3 builds a queue upstream of CAKE whatever the cap, so a sweep cannot locate a
knee. Periodic time-of-day measurement is now proposed as one flent RRUL run per slot: see [RRUL_SLOT.md](RRUL_SLOT.md).
Do not install the units below; this section is kept as the record of the earlier proposal.

`deploy/capacity-sweep/wanctl-capacity-sweep.{service,timer}` are systemd `--user` units. They are a proposal. Do not
install, enable or start the timer until the schedule has been confirmed.

**Timing.** The default service runs 6 steps. Each step takes about 48 s: 2 s lead, 23 s load, 20 s wait for the
15 s Prometheus scrape (which also serves as the idle gap between steps), and a few seconds of queries. That gives
about 138 s of actual load and about 5 minutes of wall time. The service passes `--wall-sec 510`. The script enforces
it with `timeout`: TERM at 510 s (owned load torn down at once), KILL at 540 s, so a run always ends within 540 s of
its start. A step is started only if its worst case (187 s with defaults, every timeout and kill grace included) still
fits before 510 s, so in the normal case the deadline never fires. `TimeoutStartSec=570` is only a backstop.

**Start minute.** The endpoint runs sysstat `sa1` at :05, :15, …, :55. Starting at HH:05:30 puts the whole run, worst
case included (start + 540 s), between HH:05:30 and HH:14:30, 30 s clear of both `sa1` runs. Starting at HH:35:30 works the same way.

**Hours** (Central). The proposal is 06, 10, 14 and 17 (4 runs/day), chosen to avoid:
- 03:00-03:59 and 21:00-22:59: the endpoint's `e2scrub` (03:10 daily, 03:30 Sunday), whether its cron uses Central or
  UTC;
- the household evening gaming peak. An evening slot (for example 19:35:30 or 20:05:30) would add the most useful
  time-of-day data, but only with the household's agreement;
- attended measurement sessions. Pause the timer (`systemctl --user stop wanctl-capacity-sweep.timer`) around them.

**Missed runs and concurrency.** `Persistent=false` skips a missed run instead of catching it up late at an unchecked
time. systemd does not start a oneshot that is still active, and the script's `flock` refuses a second run (exit 75,
counted as success through `SuccessExitStatus=75`). A failed run (exit 1 or 3) leaves the unit failed, so it shows up in
`systemctl --user --failed`.

**Lingering.** User timers run without a login session only when lingering is enabled for the account
(`loginctl show-user $USER -p Linger`).

**Transfer budget.** 138 s at roughly 600 Mbit average is about 10 GB of endpoint egress per run, so about 40 GB/day at
4 runs (about 1.2 TB/month). Check the endpoint's transfer quota before enabling. Fewer steps or runs reduce this
proportionally.

Install and activate, once the schedule is confirmed:

```bash
install -D -m 0644 deploy/capacity-sweep/wanctl-capacity-sweep.service ~/.config/systemd/user/wanctl-capacity-sweep.service
install -D -m 0644 deploy/capacity-sweep/wanctl-capacity-sweep.timer ~/.config/systemd/user/wanctl-capacity-sweep.timer
systemctl --user daemon-reload
systemd-analyze calendar --iterations=4 '*-*-* 06,10,14,17:05:30 America/Chicago'
systemctl --user enable --now wanctl-capacity-sweep.timer
```

Rollback: `systemctl --user disable --now wanctl-capacity-sweep.timer`, remove both unit files, then
`systemctl --user daemon-reload`.

### Data retention (proposal, nothing deleted automatically)

Each run writes about 0.2-0.5 MB of raw files (fping logs and iperf3 JSON). At 4 runs/day that is under 1 GB/year.
Proposal: keep `sweeps.csv` indefinitely, since it is the time-of-day record and a few KB per day. Keep raw `runs/`
directories for 90 days, then archive or delete them by hand after any analysis that needs them. The script itself never
deletes data.

## Prometheus textfile output

With `--textfile /path/wanctl_capacity_sweep.prom` (or `CAPACITY_SWEEP_TEXTFILE`), the script rewrites that one file
after each valid step and at the end of the run. It writes a temp file in the same directory, sets mode 0644 and
renames it into place, so the collector never reads a partial file. The file holds the latest run only:

| Metric | Labels | Meaning |
|---|---|---|
| `wanctl_capacity_sweep_run_start_timestamp_seconds` | — | start of the latest run |
| `wanctl_capacity_sweep_run_status` | `status`, `pace` | 1 for the run's current status (`running` while in progress) |
| `wanctl_capacity_sweep_valid_steps` | — | valid steps so far |
| `wanctl_capacity_sweep_step_{achieved_mbps,retransmits,rtt_median_ms,rtt_p95_ms,rtt_p99_ms,loss_percent,shaped_dl_max_mbps,end_timestamp_seconds}` | `target_mbit` | per valid step |

Cardinality is bounded: at most 12 `target_mbit` values per metric, replaced on every run. Times are carried as
`*_timestamp_seconds` values, not sample timestamps, which the textfile collector does not accept. Runs that are skipped
before any load leave the file untouched. Their record is the run's `result` file and the unit's journal.

The script writes only the one named file in a directory that must already exist. It never creates or changes collector
configuration. A node_exporter with the textfile collector enabled (`--collector.textfile.directory=<dir>`), and that
directory writable by the sweep's user, is a separate host change that needs its own approval.

## Fixed-rate sweep mode (design only, not implemented)

The current sweep measures the line *with* the adaptive controller in the loop, which is why controller cuts are a
confounder. A fixed-rate mode would hold the shaper at a known rate for the duration of a sweep so the knee reflects the
line and the CAKE queue alone. Two ways to do it:

1. **Pause cake-autorate.** Stop `cake-autorate-spectrum.service` (and its state bridge), set the CAKE `bandwidth` on
   both shaper interfaces to a fixed value with `tc qdisc change`, run the sweep, then restart the pair, which restores
   adaptive shaping. Risk: while paused, nothing reacts to real congestion, so household traffic during the sweep sees
   whatever the fixed rate gives. Steering consumes the bridge's state, so it sees stale or missing state.
2. **Native sweep mode in the controller.** A controller-side mode that pins the rate for a bounded time and reverts by
   itself. It is safer because the revert does not depend on a remote script surviving, but it is a controller change
   and needs the usual review, tests and deploy approval.

Required in either form:
- **Scope.** One WAN, download only, a bounded duration (one sweep, under 10 minutes), attended.
- **Ceiling input.** A per-hour `max_dl` ceiling map (hour → kbps) taken from earlier adaptive sweeps, so the fixed rate
  never exceeds the best clean rate seen at that hour.
- **Rollback.** A revert path that runs even if the sweep host dies: a shaper-side watchdog that restarts cake-autorate
  after N minutes, or the controller's own timeout. Plus a verification read of the restored `tc` bandwidth and service
  state afterwards.
- **Approval.** Every step above writes to the shaper host and is a live network change. It needs explicit approval of
  the exact commands and the rollback before anyone runs it. Nothing in this repository implements it today.
