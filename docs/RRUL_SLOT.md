# Time-of-Day RRUL Measurement

`scripts/rrul-slot.sh` runs 60 s flent `rrul` tests against the measurement endpoint and appends one row per test to
`rrul-v2.csv`. Run on a schedule, the rows map what the link actually delivered, and at what latency, by time of day.
It has two modes:

- **single** (day slots): one run with the controller live and nothing held. This is the original behavior.
- **sweep** (evening slots): one run per download cap, the 780 Mbit control plus the configured caps (default 620 and
  480) in random order, each with the cap held on the shaper by `wanctl-sweep-cap`. See [Sweep mode](#sweep-mode).

`--mode auto`, the default, picks sweep when the run starts within 10 minutes after one of `RRUL_SLOT_SWEEP_SLOTS`
(Central time, default `19:35 21:05 22:35`) and single otherwise.

`scripts/rrul_shadow_analyzer.py` turns the rows into a daily **shadow** recommendation, a per-hour table with reasons
(see [Shadow analyzer](#shadow-analyzer-phase-2)). Neither script applies anything to the live ceiling. A sweep holds a
cap only for its own runs and restores the controller afterwards. Applying a table to the ceiling would be a separate,
reviewed change (phase 3).

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

## Sweep mode

Evening rows at the fixed 780 ceiling delivered less than 780 Mbit, so that ceiling was not what limited them, while
loaded p99 reached 150-230 ms. The hypothesis is that a ceiling below what the line delivers in the evening keeps the
queue in CAKE instead of upstream. A sweep tests it directly: the same slot, minutes apart, with the download held at
the control and at lower caps.

**Shaper helper.** `wanctl-sweep-cap` runs on the shaper (installed separately as root at
`/usr/local/sbin/wanctl-sweep-cap`; it is not part of this change). The protocol used here is that of its reviewed r2:

| Call | What it does | Exit |
|---|---|---|
| `hold <mbit>` (400-900) | Freezes `cake-autorate-spectrum` and sets the Spectrum CAKE download bandwidth. The **first** hold arms a transient timer that runs `restore` 600 s later (the dead-man); later holds keep that deadline | 0; 2 usage, 3 refused (no freezer support, unit inactive), 4 lock busy, 5 dead-man not armed, 6 freeze failed (it attempted a restore and discards that attempt's result, so whether the controller recovered is unknown), 7 rate check failed (still frozen) |
| `restore` | Thaws and restarts the controller and its state bridge (about 1 s of Silicom bypass), verifies it is active, unfrozen and inline, then cancels the timer. Waits for the lock without limit; up to three attempts | 0 (also "nothing held"); 8 failed, marker kept |
| `status` | Read-only `unit=.. freezer=.. rate=.. hold_since=.. dead_man_pending=yes/no` | 0 |

**Sequence of one sweep.**

1. Start checks as in single mode (lock, competing load, idle gate, the optional `max_dl_shaper_rate_kbps` read), and
   a wall check: the 600 s dead-man window, the restore (up to 480 s) and two status reads must fit before the run's
   deadline, so the deadline can never fall inside a hold.
2. `status` must show a clean shaper: unit active, controller running, no hold marker, **no pending dead-man timer**.
   An earlier hold's timer would keep its own, earlier deadline, which this run cannot see, so anything else stops the
   sweep before any hold (`shaper-not-ready`).
3. For each cap, in the random order: if this held run could, at its worst (about 295 s: hold 120 s, two status reads,
   flent 110 s), end later than 30 s before the dead-man deadline counted from just before the first hold, the
   remaining caps are not run (`dead-man-budget`). Otherwise `hold <cap>`, then `status` must show the cap
   (`rate=<cap>Mbit`, frozen, dead-man pending), then the load with the usual breach watch, then `status` again: the cap
   must still be held, or the row did not measure it (`hold-lost`). Runs are 10 s apart.
4. One `restore` after the last run, then `status` must show the controller active, unfrozen, with no marker and no
   pending timer.
5. Prometheus is read after the restore for every measured row (validity checks and context, below), so the hold
   lasts only as long as the loads.

**Any failure restores at once.** A failed or unverified hold, a breach, a flent or parse failure, a lost hold,
competing load before a later cap, TERM/INT/HUP, or the deadline: owned processes are torn down, `restore` runs, rows
already measured are still validated (not after a signal or the deadline), the failing row records the reason, and caps
not run are written as `skipped` with `sweep-stopped:<reason>`. A signal that arrives while the restore runs is recorded
and handled after it; the restore is never interrupted.

**A restore that fails is a failure, never a recovery.** `restore` exiting non-zero (`failed:rc=N`), or a `status`
afterwards that is unreadable or still shows a hold (`unverified:...`), ends the run with exit 6 and
`status=restore-failed`, puts that state in every row's `restore` column, and logs `RESTORE NOT CONFIRMED`. The shaper
may then still hold a cap. Its dead-man timer, if it was armed, only **starts** another `restore` attempt about 600 s
after the first hold; that attempt waits for the helper's lock without limit and can itself fail (exit 8, marker kept).
Neither elapsed time nor any helper exit status other than a clean `status` means the controller recovered. Check by
hand with `wanctl-sweep-cap status` right away.

**Backstops outside the script.** If the script itself is killed (KILL, OOM, power loss), the dead-man timer starts a
restore attempt about 600 s after the first hold; its outcome is not observed by anything here.

**Why the run's deadline cannot fall inside a hold.** The deadline is fixed when the run starts (default 1500 s for a
sweep). Before the clean-shaper check, the sweep requires `now + 2 x 20 s + 10 s + 600 s + 480 s + 15 s` to fit before
it: 50 s for the work done before the first hold (one status read, 25 s with its kill grace, and the competing-load
check, with margin), the dead-man window, and the restore with its status check (450 + 5 + 20 + 5 s). Every held run starts only if its worst case
(295 s) ends 30 s before the dead-man attempt, so the last held run ends within 600 s of the first hold, and the restore
then ends within 480 s more. The deadline TERM can therefore only arrive while Prometheus is being read after the
restore; those rows are then recorded as `deadline` with `telemetry-not-read`. If a TERM ever did arrive during the
restore, the restore is not interrupted (signals are recorded and handled afterwards), but the watchdog sends KILL
30 s later; the restore's ssh runs in its own session and survives that, while its outcome would go unrecorded. Under
systemd, `TimeoutStartSec=1560` stops the whole unit only after the script's own deadline and grace.

**What a held row means.** `tested_cap` is the CAKE download bandwidth during that run. While frozen, the controller
does not adapt in either direction (upload keeps its last rate). `shaped_*`, `rtt_delta_*` and `nongreen_frac` come from
the controller's own state and may only repeat its last values during a hold; CAKE tin counters (`dl_drops`,
`peak_delay_ms`, household traffic) come from the qdisc and stay live. The `pre_*` window of the second and third runs
includes the previous held run.

**Shaper access.** The alias in `RRUL_SLOT_SHAPER_SSH` must be able to run `wanctl-sweep-cap` as root: either it logs in
as root, or set `RRUL_SLOT_SWEEP_CAP_CMD="sudo -n /usr/local/sbin/wanctl-sweep-cap"` with a NOPASSWD rule limited to
that command. Which one the site uses is not recorded here; confirm it with one attended `status` call before enabling.

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
| Deadline | A watchdog in its own session sends the script TERM at `--wall-sec`: it tears down owned processes (and restores a held cap) and ends as `deadline`; KILL follows 30 s later. The watchdog checks the process start time, so it never signals a reused pid. The script is not run under `timeout(1)`, so signals sent to it reach its own traps (uutils' `timeout` KILLs its child on INT/HUP). The load is only started if its worst case (with defaults about 250 s) still fits | 124 / 1 |
| Signals | TERM/INT/HUP: owned process groups get TERM, then KILL, then the run ends as `aborted` (a sweep restores first) | 143/130/129 |
| Sweep: shaper not clean | `status` unreadable, or not active/unfrozen/unheld/no pending dead-man timer: nothing is held | 1 |
| Sweep: hold | `hold` non-zero or timed out (120 s), or `status` not showing the cap frozen with the dead-man pending: restore | 1 |
| Sweep: hold lost | `status` after a load not showing the same cap still held: that row is invalid, restore | 1 |
| Sweep: dead-man budget | The next held run could outlast the dead-man window minus 30 s: remaining caps not run, restore | 1 |
| Sweep: restore | `restore` non-zero/timed out (450 s), or `status` afterwards unreadable or not clean | 6 |

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

## `rrul-v2.csv` schema (`rrul-v2`)

One row per run (a sweep writes one per cap) for every invocation that took the lock, whatever its outcome. Measurement
columns are **empty unless every check of the row passed**; empty means unavailable, never zero. Use only
`status=complete` rows for analysis, and count the other rows as coverage gaps.

**Migration from `rrul-v1`.** v2 keeps the 22 v1 columns, in the same order and with the same meaning, and appends 17.
v2 rows go to a new file, `rrul-v2.csv`; this version never writes `rrul.csv`, so the v1 history stays exactly as it was
recorded (nothing is rewritten or converted). A v1 row reads as a v2 row with `mode=single`, `tested_cap=adaptive` and
empty context; the shadow analyzer reads both files that way. If `rrul-v2.csv` exists with another header, nothing is
appended to it (rows stay in `runs/<run>/row`, exit 1).

The v1 columns:

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
| `run` | run directory name under `runs/` (a sweep: one directory, one subdirectory `c<N>` per cap) |

Appended in v2:

| Column | Meaning |
|---|---|
| `mode` | `single` or `sweep` |
| `tested_cap` | `adaptive` (single: controller live) or the held download cap in Mbit (sweep) |
| `sweep_id`, `sweep_order` | sweep: the run id shared by its rows, and this row's position `N/M` in the random order |
| `restore` | sweep: `ok`, `failed:rc=N`, `unverified:<state>`, or `none` when nothing was held |
| `household_dl_mbit` | Spectrum CAKE download bytes over the load window + 15 s minus flent's download goodput, as Mbit/s (clamped at 0); an upper bound, see below |
| `pre_dl_mbit` | Spectrum CAKE download rate over the 5 min before the load (all traffic); in a sweep, the first run's is the pre-sweep household rate |
| `rtt_delta_avg_ms`, `rtt_delta_max_ms` | controller RTT delta over the load window; `pre_*`: the 5 min before |
| `nongreen_frac` | fraction of 15 s samples with download congestion state above GREEN; `pre_*` likewise |
| `dl_drops` | CAKE download drops over the load window; `pre_*` likewise |
| `peak_delay_ms` | highest CAKE download tin peak delay over the load window; `pre_*` likewise |

The context columns after `household_dl_mbit` are descriptive. A context query that fails leaves its column empty and
adds `;context-missing:<names>` to the reason, but does not invalidate the row; context queries have a 5 s limit each
and are skipped when the run's deadline is near. `household_dl_mbit` is computed from the path-check query, so a
complete row always has it.

`household_dl_mbit` does not cleanly exclude the test. CAKE counts every byte it sends, including the test's own
retransmissions and protocol overhead, while flent reports goodput, so under load the difference holds part of the
test as well as household traffic and can read tens to over a hundred Mbit/s with a quiet household. Use it as an
upper bound only. `pre_dl_mbit` is measured before the run's own load. In a sweep only the first run's
(`sweep_order` `1/M`) describes the household: the 5 min before each later run include the previous held run. Even the
first run's can include an earlier test that ended within those 5 min, since the idle gate checks a shorter span; that
can only raise it.

A run skipped because the lock was held writes no row; its record is the unit's journal.

The file is append-only: the script never rewrites or deletes rows. The data dir (default `~/.local/share/wanctl-rrul`)
is separate from the iperf3 sweep's, so an existing `sweeps.csv` is never touched; even in a shared directory the script
only writes `rrul-v2.csv`, `runs/` and `.lock`, and the analyzer only `shadow/`.

## Configuration

Site details are not stored in this repository. In order of precedence: command-line options, `RRUL_SLOT_*`
environment variables, then `~/.config/wanctl-rrul/env` (override with `RRUL_SLOT_CONFIG`). The file holds
`RRUL_SLOT_KEY=VALUE` lines, is parsed rather than sourced, and must not be readable by group or others.
`deploy/rrul-slot/env.example` lists the keys with placeholders, including the sweep keys `RRUL_SLOT_SWEEP_SLOTS`,
`RRUL_SLOT_SWEEP_CAPS` (1-3 caps, 450-900 Mbit), `RRUL_SLOT_SWEEP_CONTROL` (default 780) and
`RRUL_SLOT_SWEEP_CAP_CMD`.

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
install -D -m 0755 scripts/rrul_shadow_analyzer.py ~/.local/bin/wanctl-rrul-analyze

# one attended run
wanctl-rrul-slot --idle-ms 22 --mode single manual
echo "exit=$?"; tail -n 2 ~/.local/share/wanctl-rrul/rrul-v2.csv

# one attended sweep (holds caps on the shaper; check its state first and afterwards)
ssh <shaper-alias> /usr/local/sbin/wanctl-sweep-cap status
wanctl-rrul-slot --mode sweep manual-sweep
echo "exit=$?"; tail -n 4 ~/.local/share/wanctl-rrul/rrul-v2.csv
ssh <shaper-alias> /usr/local/sbin/wanctl-sweep-cap status
```

**Rollback:** remove `~/.local/bin/wanctl-rrul-slot`, `~/.local/bin/wanctl-rrul-analyze`, `~/.config/wanctl-rrul/env`
and the doc copy. To go back to single runs only, without removing anything, set `RRUL_SLOT_SWEEP_SLOTS=""`. The data dir is kept
unless its owner deletes it. Nothing outside the user's home is touched.

## Scheduled runs (proposal, not enabled)

`deploy/rrul-slot/wanctl-rrul-slot.{service,timer}` are systemd `--user` units. They are a proposal and replace the
earlier `wanctl-capacity-sweep` timer proposal, which should not be installed. Do not install, enable or start the timer
until the schedule and the transfer budget below have been confirmed.

- **Timing.** Single: about 2 s lead, 70 s of flent (60 s of load), 20 s wait for the Prometheus scrape and a few
  seconds of queries, under 2 minutes typical; the default 300 s deadline with a 30 s kill grace means a run always ends
  within 330 s. Sweep: three held runs of about 75 s, 10 s apart, one restore (about 15 s including the controller
  restart), then the queries: about 6 minutes typical; the default 1500 s deadline means it ends within 1530 s. The
  service passes no `--wall-sec`, so each mode gets its own default, and `TimeoutStartSec=1560` sits above both.
- **Evening slots.** 19:35:30, 21:05:30 and 22:35:30 Central are sweeps (`RRUL_SLOT_SWEEP_SLOTS` must list the same
  times). They cross the endpoint's sa1 runs, and 21:05 and 22:35 fall inside the 21:00-22:59 window kept free for the
  endpoint's Sunday e2scrub when that host runs UTC. This was accepted for the evening evidence; check those rows on
  Sundays.
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

**Sweeps: about 3 runs per sweep slot.** Each evening slot transfers three runs' worth instead of one (at most 780 + 620
+ 480 Mbit for 60 s: 14.1 GB, 14.8 GB with 5% overhead). With the four day slots (up to 6.1 GB each) and three sweep
slots that is 13 runs and at most about 69 GB a day, about 2.1 TB in a 30.4-day month, roughly 2.5 times the
four-slot single-run schedule below. The quota comparison below applies with that figure.

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

## Shadow analyzer (phase 2)

`scripts/rrul_shadow_analyzer.py` reads `rrul.csv` (v1) and `rrul-v2.csv` and writes
`<data dir>/shadow/shadow-YYYY-MM-DD.{json,md}`: one line per hour of day (Central) with the recommended cap, its basis
and the reasons. **It is a shadow output only**: nothing reads it, and it changes no setting. With `--prom-cmd`
(default `RRUL_SLOT_PROM_CMD` or `prom-ro`) it adds passive evidence per hour from the controller's 15 s metrics over
the last `--passive-days` (default 28): household traffic, RTT delta average and maximum, minimum shaped rate,
non-green fraction and CAKE peak delay, as p50/p95 of 5-minute aggregates. A failing or missing query command is
reported as `unavailable` and the table is still written; `--no-passive` skips it.

Rule per hour, over sweep rows of the last `--window-days` (default 14):

- **Usable rows** are complete, from a sweep whose restore was `ok` and whose pre-sweep household rate is known and at
  most `--max-household-mbit` (default 20). The pre-sweep household rate is `pre_dl_mbit` of the sweep's first run
  (`sweep_order` `1/M`), and applies to every row of that sweep; a sweep whose first run is missing or has no
  `pre_dl_mbit` has no household context. A household change during the sweep is not detected.
  `household_dl_mbit` is not used (see the v2 columns above). Every other row
  is counted by cause (`high-household`, `no-household-context`, `restore-not-ok`, `status-<status>`, `no-p99`) and
  named in the reasons.
- **Paired comparison.** A cap is compared only with the control of the **same sweep**. Over the `--last-n` (default 5)
  most recent sweeps where both are usable, the cap wins a sweep when its p99 is at least `--win-frac` (default 30%)
  lower than the control's.
- **A cap qualifies** with at least `--min-wins` (default 2) wins, a median p99 over those sweeps at most
  `--p99-target-ms` (default 100), no breach-stop at that cap in the window, and a value within `--cap-min`..`--cap-max`
  (default 450-780) and below the control.
- **Recommendation:** the highest qualifying cap; otherwise the control (780), with the reasons. Hours without sweep
  evidence stay at the control. Adaptive (single) runs are summarized per hour for context but never decide.

Install as above (`~/.local/bin/wanctl-rrul-analyze`); an attended run is `wanctl-rrul-analyze --date YYYY-MM-DD`.
`deploy/rrul-slot/wanctl-rrul-analyze.{service,timer}` are proposed `--user` units that would run it nightly at 23:40
Central, after the last sweep. They are not installed or enabled by anything in this repository; enabling them is an
operator decision, and the rollback is `systemctl --user disable --now wanctl-rrul-analyze.timer` plus removing the two
unit files. The recommendation files are kept; delete `shadow/` by hand if wanted.

## Design note: deriving a per-hour download ceiling (not implemented)

The shadow analyzer above implements a first, descriptive version of this from sweeps. The note still describes the
cautions for turning any such table into live configuration.

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
