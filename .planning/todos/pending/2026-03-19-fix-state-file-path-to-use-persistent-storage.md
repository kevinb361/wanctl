---
created: 2026-03-19T20:26:25.096Z
title: Fix state file path to use persistent storage
area: infrastructure
files:
  - src/wanctl/autorate_continuous.py:485-490
  - configs/spectrum.yaml:82
  - configs/att.yaml
---

## Problem

State file (baseline_rtt, load_rtt, congestion state) is derived from lock_file path in `_load_state_config()` — lock is at `/run/wanctl/att.lock` so state ends up at `/run/wanctl/att_state.json`. `/run/` is tmpfs, wiped on container reboot. Baseline RTT cold-starts from `baseline_rtt_initial` in YAML after every reboot, taking minutes to reconverge.

The YAML configs already have `state_file: "/var/lib/wanctl/spectrum_state.json"` but the code ignores this key entirely.

## Solution

Change `_load_state_config()` to check `self.data.get("state_file")` first, fall back to lock-derived path if absent. 3-line fix:

```python
def _load_state_config(self) -> None:
    explicit = self.data.get("state_file")
    if explicit:
        self.state_file = Path(explicit)
    else:
        lock_stem = self.lock_file.stem
        self.state_file = self.lock_file.parent / f"{lock_stem}_state.json"
```

After deploy, migrate existing state: `sudo cp /run/wanctl/att_state.json /var/lib/wanctl/att_state.json`
