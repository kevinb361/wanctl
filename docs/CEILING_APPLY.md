# Ceiling Apply (adaptive evening cap, phase 3) — shipped disabled

`scripts/wanctl_ceiling_apply.py` turns the shadow per-hour table of
[`rrul_shadow_analyzer.py`](RRUL_SLOT.md#shadow-analyzer-phase-2) into the live Spectrum download ceiling.
**It ships disabled and nothing in this repository installs, enables or schedules it.** With no env file, or
`CEILING_APPLY_ENABLED` other than `1`, `tick` returns at once: it reads only its env file, creates no file and runs no
command. Enabling it is a separate decision with the prerequisites below.

## How the ceiling is set, and what is not known

From this repository's configuration (the running host and its installed versions were not inspected):

- Spectrum runs the external cake-autorate controller (`cake-autorate-spectrum.service`); its ceiling is
  `max_dl_shaper_rate_kbps` in `/etc/cake-autorate/config.spectrum.sh`, in kbps (780000 = 780 Mbit).
- cake-autorate copies its rate bounds from the config once at startup. One read of upstream `master` (not a pinned
  release) showed no signal or FIFO command that changes them later. **Whether the installed version has a runtime
  path was not checked**; until it is, the applier assumes none.
- A plain `tc` change is not a ceiling while the controller runs (it re-sets the rate within its own bounds), which is
  why `wanctl-sweep-cap` freezes the controller to hold a rate.
- wanctl's own SIGUSR1 reload does not reload rate ceilings, and `wanctl@spectrum` is not the Spectrum controller in
  this deployment mode.

So a new ceiling means: rewrite that one config line and restart the controller and its state bridge — the same
restart `wanctl-sweep-cap restore` performs. Each restart:

- passes through the Silicom fail-open bypass while the unit is inactive (unshaped traffic). **"About 1 s" is assumed
  from the sweep helper's notes, not measured**;
- restarts the download rate from the qdisc-init value (550 Mbit) and the controller's base (450 Mbit), ramping up to
  the ceiling: a throughput dip, not an outage.

That cost is why lowerings are limited to one per day.

## Rules

**Inputs.** The newest `shadow-YYYY-MM-DD.json` dated today or earlier (Central) in `CEILING_APPLY_TABLE_DIR`, and
`analyzer-status.json` beside it. The analyzer writes the status file after every run, failed runs included: whether
it succeeded, the date and sha256 of the table it wrote, the passive-evidence status, and every RRUL `breach-stop` row
that started in the 24 h before it finished. **Getting both files onto the shaper is not provided here.**

**The day is held at 780 Mbit** (fallback) when any of these holds:

| Condition | Note |
|---|---|
| no table, unreadable JSON, wrong schema, date not matching the file name, not 24 unique integer hours, control not 780 | |
| any recommendation outside 450-780 Mbit | the whole table is rejected, never clamped |
| table `generated` more than 36 h old, or more than 5 min in the future; a table file dated after today | clock or delivery problem |
| status missing, unreadable, `ok` false, older than 36 h or in the future | a failed analyzer run; a run killed outright writes nothing and shows only through age |
| status not naming this table's date and sha256 | the last run did not produce the table in use |
| any `breach-stop` in the status's 24 h | **assumed meaning of "breach"** (see Limits) |
| off switch file present | `CEILING_APPLY_OFF_FILE` |

`passive_status` is logged but does not invalidate a table: the recommendation does not depend on passive evidence.

**Plan.** Fixed once per Central day at the first `tick` whose inputs are valid, retried until 12:00; a table arriving
later is used the next day. Each later `tick` re-checks the same table and status; once they fail, the rest of the day
is at 780. From the table's 24 values the applier keeps **one** window: the longest run of hours below 780 among
00-22 (the earliest on a tie), at the **highest** recommendation in that run; every other hour is 780, and hour 23 is
always 780 so a window ends the same day. No hour is set below its own recommendation, but the substituted higher
values inside the window have no evidence of their own. The original and effective tables are both logged
(`plan-fixed`) and shown by `plan`.

**Timing and budget.** The timer runs at :00:30 and :30:30. A lowering happens only in the first 10 minutes of an hour
inside the window (a missed first boundary may be taken at a later in-window boundary, never at :30), and at most once
per Central day. Moves to 780 (window end, fallback, off switch, recovery) happen at any run. Normal operation is
therefore at most two restarts a day (down, then up by 23:00).

**Clean shaper only.** Every change, including fallback, off switch and `restore`, happens only while the applier holds
`wanctl-sweep-cap`'s lock (waiting up to 30 s), with no hold marker, no pending dead-man timer, and the controller
active and not frozen. Otherwise nothing is touched, the run is `deferred` (exit 75) and retried at the next run. A
sweep therefore never has its hold or timer disturbed, and its own `restore` restarts the controller from whatever the
config file says. **A deferral is not bounded**: `wanctl-sweep-cap restore` can fail and keep its marker. When a needed
move to 780 has been deferred for 60 minutes or more, every run logs `CRITICAL-deferred` and exits 1; recovering a
stuck sweep is the operator's job (`wanctl-sweep-cap status`). An inactive controller that the applier did not leave
that way is not touched (exit 1).

**Ownership.** The applier edits only a value it recognizes: 780000, its own last verified value, or either end of a
change it recorded as in progress. Anything else (an operator trial, a deploy of another value) is refused (exit 1).
A deploy resetting the file to 780000 is recognized and followed by a verified restart at 780. The check is repeated
on a fresh read under the sweep lock, right before the change, so a value written while the applier waited for the
lock is not overwritten (this narrows the window; it cannot serialize a writer that ignores the lock). **A state file
that is unreadable or not exactly valid means ownership is lost: no automatic action at all** (exit 6 every run) until
a person runs `restore --take-ownership`. Exactly valid means every field present with its type and range: counters,
dates, a last value and any in-progress target inside 450-780 Mbit, and a stored plan whose hours are exactly the
normalized form of its stored, in-bounds table. A stored plan therefore cannot carry a ceiling the table did not.

**Each change** (all under the applier's own lock and the sweep lock):

1. refuses any target outside 450-780 Mbit (a second, independent bound at the point of change), re-checks the
   ownership rule above, and checks the config has exactly one `min_`, `base_` and `max_dl_shaper_rate_kbps` line
   and `min <= base <= new max`;
2. records the intent in the state file, reserving the day's lowering or recovery **before** anything changes;
3. replaces the config atomically (temp file, same mode and owner, fsync, rename); only the one line differs, and the
   first original is kept as `<config>.ceiling-apply.prev`;
4. restarts the controller and its state bridge;
5. verifies, fail-closed: three consecutive checks 2 s apart within 20 s, each needing the controller active, running,
   not frozen, with the same non-zero MainPID, the bridge active, and `silicom-bypass status <pair>` exiting 0 with one
   line whose `bypass` says `non-Bypass` and `disc` says `non-Disconnect`. A command error, timeout or unexpected
   output is a failed check; the journal is not used as evidence. The 20 s is a hard window: each command gets only
   the time left (at most 10 s), and a check that completes after the window does not count;
6. records the new value as verified.

A failed change to anything but 780 is followed in the same run by one change to 780. If that fails too, the state
keeps the change as unverified and the run exits 6. A run that is killed between steps 2 and 6, or cannot record step
6, leaves the intent behind; the next run treats the running ceiling as **unknown** and recovers to 780 with a
verified restart, whatever the file says. Automatic recoveries are limited to two per Central day, counted at intent;
after that every run logs `CRITICAL-recovery-exhausted` and exits 6. The hard bound on automatic restarts is four per
day.

**"780" versus "verified 780".** Without any history, a config at 780000 is recorded as `baseline-assumed`: nothing has
observed the running controller. That is enough for a quiet no-op, and the off switch or a fallback then logs
`780 configured; running ceiling not verified`, never "restored". `restore` is satisfied only by a verified restart:
from `baseline-assumed` it restarts and verifies.

Exit codes: 0 ok, no-op or disabled; 1 error, refusal or a long deferral; 6 not verified or manual recovery required;
75 deferred.

Every change, deferral, fallback, refusal and recovery is one JSON line in `<state dir>/events.jsonl` and in the
journal (`logger -t wanctl-ceiling-apply`).

## Commands

```bash
wanctl-ceiling-apply plan                      # read-only: table, original and effective plan, or why not
wanctl-ceiling-apply status                    # read-only: state (verified=restart|baseline-assumed|false), config, off switch
wanctl-ceiling-apply tick                      # one scheduled decision; does nothing unless enabled
wanctl-ceiling-apply restore                   # 780 with a verified restart; works when disabled
wanctl-ceiling-apply restore --take-ownership  # after "state unreadable", once a person has checked the shaper
```

`restore --take-ownership` keeps the unreadable state file as `state.json.corrupt-<utc>`, writes 780000 whatever the
current value is (logged), restarts and verifies, and starts a new state with the day's lowering and automatic
recoveries used up. It still waits for a clean sweep state, but works with the controller stopped.

## Enable prerequisites (all open)

1. **Installed cake-autorate checked** for a runtime way to change bounds (pinned source of the installed version).
2. **Table delivery** from the measurement host to the shaper (table + `analyzer-status.json`), chosen and reviewed.
   It needs access that does not exist today.
3. **One attended restart** to measure the bypass blip and confirm the real `silicom-bypass status` text matches what
   the verification expects.
4. **The meaning of "breach"** confirmed (currently: any RRUL breach-stop in the analyzer's last 24 h, any mode).

## Enable (prepared, not done)

```bash
install -D -m 0755 scripts/wanctl_ceiling_apply.py /usr/local/sbin/wanctl-ceiling-apply
install -D -m 0644 docs/CEILING_APPLY.md /usr/local/share/doc/wanctl/CEILING_APPLY.md
install -D -m 0600 deploy/ceiling-apply/ceiling-apply.env.example /etc/wanctl/ceiling-apply.env
install -D -m 0644 deploy/ceiling-apply/wanctl-ceiling-apply.service /etc/systemd/system/wanctl-ceiling-apply.service
install -D -m 0644 deploy/ceiling-apply/wanctl-ceiling-apply.timer /etc/systemd/system/wanctl-ceiling-apply.timer
systemctl daemon-reload
wanctl-ceiling-apply plan          # with a delivered table: check the effective plan
# then set CEILING_APPLY_ENABLED=1 in /etc/wanctl/ceiling-apply.env
systemctl enable --now wanctl-ceiling-apply.timer
```

Before deploying with `scripts/deploy.sh --with-spectrum-cake-autorate`, which overwrites the whole config with the
repository copy (780000), set the off switch first; the applier then recognizes 780000.

## Rollback

```bash
touch /etc/wanctl/ceiling-apply.off           # holds 780 at every run
wanctl-ceiling-apply restore                  # 780 now, with a verified restart; check "verified": "restart"
wanctl-ceiling-apply status
systemctl disable --now wanctl-ceiling-apply.timer
rm /etc/systemd/system/wanctl-ceiling-apply.{service,timer} /usr/local/sbin/wanctl-ceiling-apply
systemctl daemon-reload
```

Independent of the applier: put `max_dl_shaper_rate_kbps=780000` back (or redeploy the repository config) and
restart `cake-autorate-spectrum` and its state bridge; `<config>.ceiling-apply.prev` holds the config as it was before
the first change.

## Limits

- **Breach.** Only RRUL breach-stops seen by the analyzer count. There is no live latency trigger between analyzer
  runs: the applier is an hourly one-shot, not a control loop (cake-autorate still cuts below the ceiling).
- **Failure visibility.** A killed analyzer, a dead host or an undelivered status shows only through age (36 h).
- **Running ceiling.** Known only through the applier's own verified restarts; a value set by anyone else is unknown.
- **Verification text.** The `silicom-bypass status` forms come from this repository's CLI and its tests, not from
  the hardware (prerequisite 3).
- **Measurement drift.** Single (adaptive) RRUL rows taken during a lowered window run under that ceiling; compare
  like with like (`max_dl_config_kbps`).
- **Nightly overlap.** The analyzer's 23:40 run replaces the status file, so the rest of hour 23 (always 780 anyway)
  is logged as a fallback.
