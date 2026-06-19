---
phase: "247"
plan: "04"
status: checkpoint_human_action
updated_at: "2026-06-19T11:10:00Z"
preflight_log: .planning/phases/247-fping-shadow-capture-phase-245-evidence-review/evidence/phase247-preflight-20260619T110901Z.log
resolved_soak_output: /var/lib/wanctl/phase247-fping-shadow.ndjson
config_path: /etc/cake-autorate/config.spectrum.sh
run_user: wanctl
---

# Plan 247-04 Checkpoint — Overnight fping Shadow Soak

## Preflight status

Preflight passed and is recorded in:

`.planning/phases/247-fping-shadow-capture-phase-245-evidence-review/evidence/phase247-preflight-20260619T110901Z.log`

Observed production shape differs from the original plan assumptions:

- cake-shaper uses a flat `/opt/wanctl` Python package layout, not `/opt/wanctl/src/wanctl`.
- cake-shaper has no `/opt/wanctl/.venv`; `python3` with `PyYAML` is available.
- The active Spectrum service is external cake-autorate:
  - `ExecStart=/opt/cake-autorate/cake-autorate.sh /etc/cake-autorate/config.spectrum.sh`
- `/var/lib/wanctl` is writable by the `wanctl` user, not the SSH user. Run the soak with `sudo -n -u wanctl`.
- The shadow script has been transferred to `/opt/wanctl/scripts/phase247-fping-shadow.py` and passed `--help` under the `wanctl` user.
- The 2-cycle dry-run used the active service config and produced 3 `probe_cycle` records and 1 `run_start` record.
- Output path collision check returned `absent`, so the resolved soak path is `/var/lib/wanctl/phase247-fping-shadow.ndjson`.

## Start the soak

Run this on the dev machine when ready to start the overnight capture:

```bash
ssh cake-shaper "cd /opt/wanctl && sudo -n -u wanctl nohup python3 scripts/phase247-fping-shadow.py --config /etc/cake-autorate/config.spectrum.sh --output /var/lib/wanctl/phase247-fping-shadow.ndjson --stats-interval 100 > /var/log/wanctl/phase247-shadow.log 2>&1 & echo \$!"
```

Target duration: 12h overnight. Minimum usable evidence: >=3h, recorded as partial.

## Monitor progress

```bash
ssh cake-shaper 'wc -l /var/lib/wanctl/phase247-fping-shadow.ndjson'
ssh cake-shaper 'grep -c "probe_cycle" /var/lib/wanctl/phase247-fping-shadow.ndjson'
ssh cake-shaper 'tail -5 /var/lib/wanctl/phase247-fping-shadow.ndjson'
ssh cake-shaper 'tail -50 /var/log/wanctl/phase247-shadow.log'
```

## Stop cleanly

Use SIGINT so the script writes `probe_stats_final`:

```bash
ssh cake-shaper "pgrep -af phase247-fping-shadow.py"
ssh cake-shaper "sudo -n pkill -INT -f 'python3 scripts/phase247-fping-shadow.py'"
ssh cake-shaper "pgrep -af phase247-fping-shadow.py || true"
ssh cake-shaper "tail -1 /var/lib/wanctl/phase247-fping-shadow.ndjson"
```

The final NDJSON line should be `type="probe_stats_final"`.

## Resume signal

After the soak has run and has been stopped cleanly, resume Phase 247 with:

`/gsd:execute-phase 247`

Provide:

- exact output path used: `/var/lib/wanctl/phase247-fping-shadow.ndjson`
- approximate duration
- whether the final line is `probe_stats_final`

The next task will collect the NDJSON, compute `phase247-shadow-summary.json`, rerun SAFE-18, then create `247-04-SUMMARY.md`.
