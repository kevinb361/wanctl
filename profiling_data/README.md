# Profiling Data

This directory contains profiling data collected from production systems.

## Files

- **DAY_1_RESULTS.md** - Initial 24-hour baseline (Jan 8-9, 2026)
- **REMINDER_DAY_7.md** - Checklist for Day 7 review (Jan 15, 2026)
- **REMINDER_DAY_14.md** - Checklist for Day 14 final review (Jan 22, 2026)
- **\*.log** - Raw log files (excluded from git via .gitignore)

## Collection Schedule

| Checkpoint | Date    | Status      | Purpose                             |
| ---------- | ------- | ----------- | ----------------------------------- |
| Day 1      | Jan 8-9 | ✅ Complete | Initial baseline                    |
| Day 7      | Jan 15  | ⏳ Pending  | Mid-point analysis, weekly patterns |
| Day 14     | Jan 22  | ⏳ Pending  | Final baseline, Phase 2 decision    |

## Quick Commands

```bash
# Collect logs from containers
ssh cake-spectrum 'sudo cp /var/log/wanctl/spectrum_debug.log /tmp/ && sudo chmod 644 /tmp/spectrum_debug.log'
scp cake-spectrum:/tmp/spectrum_debug.log ./spectrum_dayN.log

# Analyze profiling data
cd ~/projects/wanctl
python3 scripts/profiling_collector.py profiling_data/spectrum_dayN.log --all
```
