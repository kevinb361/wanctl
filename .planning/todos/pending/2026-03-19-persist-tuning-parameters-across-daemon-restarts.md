---
created: 2026-03-19T20:26:25.096Z
title: Persist tuning parameters across daemon restarts
area: infrastructure
files:
  - src/wanctl/autorate_continuous.py:1669
  - src/wanctl/tuning/models.py
  - src/wanctl/storage/reader.py
---

## Problem

Tuning parameter adjustments (hampel_sigma, window_size, etc.) are in-memory WANController attributes. On daemon restart, all values reset to YAML defaults and the tuning engine must re-derive after 1-hour warmup. With 10% max step and 4-hour layer rotation, convergence from defaults can take 1-3 days. A simple restart wipes hours/days of gradual optimization.

The tuning_params SQLite table already stores every adjustment with timestamps, but nothing reads it back on startup.

## Solution

On WANController startup (after `_load_tuning_config`):
1. Query `tuning_params` for the most recent adjustment per parameter for this WAN
2. Apply those values via `_apply_tuning_to_controller` (same path as live tuning)
3. Log restored values at INFO level

On shutdown/SIGTERM: no additional work needed — values are already in SQLite from when they were applied.

Key detail: only restore if tuning is enabled in config. If operator disables tuning, parameters should revert to YAML defaults (not silently persist old tuning state).
