# Time-of-Day RRUL Measurement

`scripts/rrul-slot.sh` runs one 60 s flent `rrul` test against the measurement endpoint and appends one row to
`rrul.csv`. Run on a schedule, the rows map what the link actually delivered, and at what latency, by time of day. That
record is the input for a future per-hour download ceiling (see the design note below). The script is a measurement tool.
It does not change the controller, the shaper or the endpoint. Nothing in it adjusts a ceiling.

## Why RRUL, and what one row means

The earlier periodic proposal swept iperf3 download rates to find a "knee". Unpaced multi-stream iperf3 bursts build a
queue upstream of CAKE whatever the cap is, so the latency penalty did not track the rate, and a sweep could not locate a
knee. `rrul` runs 4 download and 4 upload TCP flows with DSCP markings plus ICMP/UDP pings, which is closer to real mixed
traffic, and its throughput comes from netperf's own per-flow results.

A row is one observation **with the controller live and nothing capped or held**:

- `dl_mbit`/`ul_mbit` are what the flows achieved through the controller at that moment. They are bounded by the shaped
  rate, so they describe "what the link delivered under the controller", not the line's fixed capacity.
- `shaped_*` show whether the controller cut during the window. A row whose shaped download fell far below its ceiling
  measured the controller's reaction to congestion, not spare capacity.
- One run in one slot is one sample. Household traffic, endpoint load and path changes confound it. Treat a single
  afternoon/evening difference as descriptive, not as the cause of anything.

## Safety and validity rules

The rules are carried over from `capacity-sweep.sh` where they still apply to a single RRUL run:

| Rule | RRUL behavior | Exit |
|---|---|---|
| Inputs | Label, endpoint, idle RTT 1-500 ms, wall 10-900 s, absolute data dir, executable flent/Prometheus commands | 2 |
| Run lock | One run at a time per data dir (`flock`); a second run exits at once and writes no row | 75 |
| Competing load | Any local `flent`, `netperf`, `iperf3 -c` or `irtt client` at start or right before the load: skip (detection only, never killed). Checked only before the load, since the run's own flent starts netperf and irtt | 75 |
| Failed competing-load check | `pgrep` missing, or exiting with anything other than 0 (found) or 1 (none): the run is invalid and no load starts. A check that could not run never counts as "no competing load" | 1 |
| Idle gate | Spectrum CAKE throughput (1 min rate) at every 15 s point of the last 2 minutes below 20 Mbit down **and** 3 Mbit up | 75 |
| Sustained breach | A separate `fping` (200 ms) watches during the load: 3 consecutive checks at most 2 s apart of the last 10 pings, each over the limit (loss >= 30% or median > idle + 250 ms), kills flent's process group at once | 3 |
| Watch telemetry | The watch `fping` exiting, stale (newest sample > 3 s old) or unparsable during the load: kill and stop | 1 |
| flent result | flent non-zero exit, not exactly one data file for this run, or a data file that fails validation (below) | 1 |
| Missing telemetry | A Prometheus range missing any point of its window, unordered points, a non-finite/negative value, or a shaper exporter sample older than 30 s | 1 |
| Path check | The Spectrum CAKE download byte increase over the run must be at least 80% of the flent download bytes, and the ATT increase at most 20% of them | 1 |
| Deadline | The script re-runs itself under `timeout`: at `--wall-sec` it gets TERM, tears down owned processes and ends as `deadline`; KILL follows 30 s later. The load is only started if its worst case (with defaults about 250 s) still fits | 124 / 1 |
| Signals | TERM/INT/HUP: owned process groups get TERM, then KILL, then the run ends as `aborted` | 143/130/129 |

Rules from the iperf3 sweep that do **not** carry over:

- **Knee stop** and **per-step rate ladder**: there is one run, no rate steps.
- **Floor stop**: in the sweep it stopped further steps. A single run has no further step, so a shaped download at the
  floor is recorded in `shaped_dl_min_mbit` instead. That is exactly the kind of observation the record needs.
- **Textfile output**: not provided; the CSV and run directory are the record.

Every child (watch fping, flent under `timeout`, the optional ssh read) starts in its own process group via `setsid`.
Teardown signals only those groups, never processes found by name.

## How the flent data file is read

Taken from flent 2.2.0 data files of the attended 2026-10-20 sessions, not assumed:

- **Throughput.** `metadata.SERIES_META["TCP download|upload <BE|BK|CS5|EF>"].MEAN_VALUE` is netperf's per-flow
  result in Mbit/s (it equals bytes x 8 / `ELAPSED_TIME` / 1e6). `dl_mbit`/`ul_mbit` are the sums over the four
  classes, which is flent's own "TCP download sum"/"TCP upload sum". The interpolated `results` series, which has nulls
  during flent's lead and trail, is not used. A flow that is missing, has no value, other units, or ran less than 55 s
  makes the run invalid. A missing value is never read as 0.
- **Load window.** The span of the four download flows' raw sample times (`raw_values["TCP download <class>"][].t`),
  about 60 s.
- **ICMP latency and loss.** flent's fping runner (`fping -D -p 200 -c N`) records one `raw_values["Ping (ms) ICMP"]`
  entry `{seq, t, val}` per reply; a lost probe simply has no entry. Probe *k* is sent at `base + k x 0.2 s`, where
  `base` is the median of `t - val/1000 - seq x 0.2` over the replies (stable to a few ms in the retained files).
  `icmp_sent` counts probes sent inside the load window, `icmp_lost` those with no reply, and the median/p99 are
  nearest-rank over the replies in the window: the value at 1-based rank ceil(n x q / 100) of the n sorted replies, so a
  p99 over 299 replies is the 297th. This is **not** the estimator `capacity-sweep.sh` uses for its p95/p99 (rank
  floor(n x q / 100)), which can miss a sparse slow tail: with 3 replies of 299 at 250 ms and the rest at 25 ms it
  reports 25 ms where nearest-rank reports 250 ms. Do not compare p99 across `sweeps.csv` and `rrul.csv`. The window
  must have been at least 90% probed. No replies at all, or none during the load, makes latency and loss unavailable (run invalid), not
  100% or 0.
- **Differences from flent's printed summary.** flent's summary is over the whole 70 s run, lead and trail included, and
  interpolates, which dilutes the tail with idle lead/trail samples. The load-window values here are higher. Checked
  offline against four retained runs: throughput matches flent's sums to 0.1 Mbit/s; window medians were 0.7-2.9 ms
  and nearest-rank p99s 5-30 ms above flent's whole-run figures. Do not mix the two in one comparison.
- **Validation.** Test name `rrul`, title equal to this run's id, host equal to the endpoint, `LENGTH` 60 and
  `FAILED_RUNNERS` 0.

## `rrul.csv` schema (`rrul-v1`)

One row per run that took the lock, whatever its outcome. Measurement columns are **empty unless every check of the run
passed**; empty means unavailable, never zero. Use only `status=complete` rows for analysis, and count the other rows
as coverage gaps.

| Column | Meaning |
|---|---|
| `schema` | `rrul-v1` |
| `label` | label given on the command line (`auto` from the timer) |
| `status`, `reason` | `complete`, `skipped`, `invalid`, `incomplete`, `breach-stop`, `deadline`, `aborted`, and the reason token |
| `start_utc` | Unix seconds (UTC) when flent was started; the run start if the load never started |
| `local_date`, `local_time`, `local_tz`, `dow` | the same instant in America/Chicago: `YYYY-MM-DD`, `HH:MM`, `CDT`/`CST`, `Mon`..`Sun` |
| `dl_mbit`, `ul_mbit` | achieved download/upload, Mbit/s (10^6 bit/s), sum of the four flows, 0.1 resolution |
| `icmp_median_ms`, `icmp_p99_ms` | ICMP RTT during the load window, ms, nearest-rank (ceil(n x q / 100)) |
| `icmp_loss_pct`, `icmp_sent`, `icmp_lost` | ICMP loss during the load window, percent and counts |
| `shaped_dl_min_mbit`, `shaped_dl_max_mbit` | controller's shaped download rate over the window, Mbit/s (Prometheus, 5 s grid) |
| `shaped_ul_min_mbit`, `shaped_ul_max_mbit` | the same for upload |
| `max_dl_config_kbps` | the shaper's configured download ceiling at run time when `--shaper-ssh` is set, else empty |
| `run` | run directory name under `runs/` |

A run skipped because the lock was held writes no row; its record is the unit's journal. If an existing `rrul.csv` does
not start with this header, nothing is appended to it; the row stays in `runs/<run>/row` and the run exits 1.

The file is append-only: the script never rewrites or deletes rows. The data dir (default `~/.local/share/wanctl-rrul`)
is separate from the iperf3 sweep's, so an existing `sweeps.csv` is never touched; even in a shared directory the script
only writes `rrul.csv`, `runs/` and `.lock`.

## Configuration

Site details are not stored in this repository. In order of precedence: command-line options, `RRUL_SLOT_*`
environment variables, then `~/.config/wanctl-rrul/env` (override with `RRUL_SLOT_CONFIG`). The file holds
`RRUL_SLOT_KEY=VALUE` lines, is parsed rather than sourced, and must not be readable by group or others.
`deploy/rrul-slot/env.example` lists the keys with placeholders.

The endpoint must run a forking `netserver` and an `irtt` server, and answer ICMP. The measurement host needs bash,
flent (with netperf, irtt and fping), jq, gzip, GNU awk, coreutils, util-linux (`flock`, `setsid`), procps (`pgrep`) and a
read-only Prometheus query command. jq 1.8 changed `as`-binding precedence; the script's jq is written so it parses the
same under 1.7 and 1.8 (`tests/test_shell_jq_bindings.py` checks the source form), but it has only been run under 1.8.1.
An empty flent data file is recorded as `invalid` with reason `flent-parse:no-result` whatever exit status the installed
jq gives `-e` on empty input; the script checks for an empty parse result itself rather than relying on jq for it.

## Install and use (measurement host, user account)

```bash
install -D -m 0755 scripts/rrul-slot.sh ~/.local/bin/wanctl-rrul-slot
install -D -m 0600 deploy/rrul-slot/env.example ~/.config/wanctl-rrul/env   # then edit real values
install -D -m 0644 docs/RRUL_SLOT.md ~/.local/share/doc/wanctl/RRUL_SLOT.md

# one attended run
wanctl-rrul-slot --idle-ms 22 manual
echo "exit=$?"; tail -n 2 ~/.local/share/wanctl-rrul/rrul.csv
```

**Rollback:** remove `~/.local/bin/wanctl-rrul-slot`, `~/.config/wanctl-rrul/env` and the doc copy. The data dir is kept
unless its owner deletes it. Nothing outside the user's home is touched.

## Scheduled runs (proposal, not enabled)

`deploy/rrul-slot/wanctl-rrul-slot.{service,timer}` are systemd `--user` units. They are a proposal and replace the
earlier `wanctl-capacity-sweep` timer proposal, which should not be installed. Do not install, enable or start the timer
until the schedule and the transfer budget below have been confirmed.

- **Timing.** About 2 s lead, 70 s of flent (60 s of load), 20 s wait for the Prometheus scrape and a few seconds of
  queries: under 2 minutes typical. `--wall-sec 300` with a 30 s kill grace means a run always ends within 330 s.
- **Start minute and hours** (Central): 06, 10, 14 and 17 at :05:30, ending by :11:00, between the endpoint's sysstat
  runs at :05 and :15, and outside its 03:00-03:59 and 21:00-22:59 maintenance windows. An evening slot (for example
  19:35:30 or 20:05:30) would add the most useful data, since evening is where congestion was seen, but only with the
  household's agreement: a run loads the link for 60 s.
- **Missed runs and concurrency.** `Persistent=false` skips a missed run. systemd does not start a oneshot that is still
  active, and `flock` refuses a second run (exit 75, counted as success through `SuccessExitStatus=75`). A failed run
  (exit 1 or 3) leaves the unit failed and visible in `systemctl --user --failed`.
- **Lingering.** User timers run without a login session only with lingering enabled
  (`loginctl show-user $USER -p Linger`).
- **Command lookup.** The user manager's default `PATH` does not include `~/.local/bin`, so the service sets
  `Environment=PATH=%h/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin`. A bare
  `RRUL_SLOT_PROM_CMD` (default `prom-ro`) or `RRUL_SLOT_FLENT_CMD` is resolved in that `PATH`; give an absolute path
  for a command installed anywhere else. If the command cannot be found, the script exits 2 before any load with
  `RRUL_SLOT_PROM_CMD '<value>' is not an executable command` (or the `FLENT_CMD` equivalent).
- **Memory.** `MemoryMax=1G`: flent was OOM-killed while starting its runners under 256M, and a full run peaks near
  370M.
- **fping capability.** `NoNewPrivileges=no`: fping normally gets `CAP_NET_RAW` from a file capability, and
  `NoNewPrivileges=yes` makes execve ignore file capabilities, so both the breach-watch fping and flent's ICMP runner
  would fail.

Install and activate, once confirmed:

```bash
install -D -m 0644 deploy/rrul-slot/wanctl-rrul-slot.service ~/.config/systemd/user/wanctl-rrul-slot.service
install -D -m 0644 deploy/rrul-slot/wanctl-rrul-slot.timer ~/.config/systemd/user/wanctl-rrul-slot.timer
systemctl --user daemon-reload
systemd-analyze calendar --iterations=4 '*-*-* 06,10,14,17:05:30 America/Chicago'
systemctl --user enable --now wanctl-rrul-slot.timer
```

Rollback: `systemctl --user disable --now wanctl-rrul-slot.timer`, remove both unit files, then
`systemctl --user daemon-reload`.

### Transfer estimate

Endpoint egress is dominated by the download flows: `dl_mbit x 60 s / 8`. Upload (endpoint ingress) is a few percent of
that, and pings are negligible.

| Assumption | Per run | 4 runs/day, 30.4-day month |
|---|---|---|
| Observed range of rrul download sums (about 600-780 Mbit/s) | 4.5-5.9 GB | 0.55-0.71 TB |
| Download pinned at a 780 Mbit/s ceiling, +5% TCP/IP overhead | 6.1 GB | 0.75 TB |
| Download at a 900 Mbit/s ceiling, +5% overhead (upper bound) | 7.1 GB | 0.86 TB |

Upload adds roughly 0.2 GB per run (about 25 Mbit/s for 60 s), counted against the endpoint's inbound traffic.

**Quota: unknown.** The endpoint's plan and transfer allowance are not in the evidence this estimate was made from, and
no account or billing data was queried. Before enabling, compare 0.9 TB/month (the upper bound) with the plan's
monthly transfer allowance and with whatever else the endpoint sends, such as attended flent sessions (roughly 6 GB per
rrul or download test) and any iperf3 sweeps. **If the allowance is 1 TB or less, this schedule alone would use most of
it and leave little room for attended testing; reduce to 2-3 slots/day, or confirm the allowance first.** The schedule
stays a proposal until that comparison is made.

Raw data per run is about 0.3 MB (flent data file plus fping log), under 0.5 GB/year at 4 runs/day. Keep `rrul.csv`
indefinitely; prune raw `runs/` by hand after any analysis that needs them. The script never deletes data.

## Design note: deriving a per-hour download ceiling (not implemented)

The aim is a table hour -> `max_dl` ceiling that the controller could one day use, so the shaper stays the bottleneck
when the line is worse, without starving it when the line is better. This section only describes how such a table could
be derived from `rrul.csv`. Nothing reads the CSV automatically, nothing changes a controller setting, and turning a
table into live configuration is a separate, reviewed controller change with its own approval and rollback.

**Inputs.** Only `status=complete` rows whose `shaped_dl_max_mbit` reached the configured ceiling during the window
(`max_dl_config_kbps`, when recorded). A row whose shaped rate never approached the ceiling says little about headroom.

**Coverage before any number.** Per hour of day (Central, `local_time`):

- at least about 10 complete rows from at least 3 different weeks before the hour gets a value. Four fixed slots cover
  only four hours; other hours need deliberately placed slots or stay "no data";
- weekdays and weekends kept apart until the data shows they behave the same;
- invalid, skipped and breach-stop rows counted per hour. A high share of skips (link not idle) means the hour is
  under-sampled exactly when it is busy. A cluster of breach-stops is itself evidence the hour is congested, not missing
  data to ignore.

**Time zone and seasonality.** Group by Central local time (`local_tz` shows CDT/CST), since household and ISP-side load
follow local clocks. Keep the date so the table can be rebuilt per season. Evening load, school terms and holidays shift.
A table from October is not evidence for July.

**Conservative interpretation.**

- Use a low percentile (for example the 25th) of `dl_mbit` among rows in that hour where latency stayed acceptable
  (`icmp_p99_ms` within an agreed bound over idle, low `icmp_loss_pct`), not the mean or best case.
- Never raise an hour above the current global ceiling on this evidence. The table can only lower the ceiling for hours
  that are consistently worse.
- Hours without enough coverage keep the global ceiling.
- Re-derive periodically and compare with the previous table before any change. Because rows are measured with the
  controller live, a ceiling change shifts future rows; compare like with like (same `max_dl_config_kbps`).

**Known limits.** One endpoint and one path; a single 60 s run per slot; the RRUL mix is not the household's traffic;
the controller's own cuts shape the result. The record says what happened at those times, not why.
