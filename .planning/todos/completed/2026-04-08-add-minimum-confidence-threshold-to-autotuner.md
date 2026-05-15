---
created: 2026-04-08T23:35:04.832Z
title: Add minimum confidence threshold to autotuner
area: tuning
files:
  - src/wanctl/tuning/
---

## Problem

Last autotuner change (2026-03-28) accepted hampel_window_size 15->13.5 with confidence 0.091 — only 138 samples. The max_step_pct guard limits change magnitude but nothing prevents accepting statistically dubious changes. A 9% confidence adjustment to the Hampel outlier filter window could make the signal chain more noise-sensitive.

## Solution

- Add a configurable `min_confidence` parameter to the tuner (default ~0.3)
- Reject proposed changes below the threshold and log them as "skipped: low confidence"
- The existing exclude_params and max_step_pct guards limit what and how much changes, but min_confidence limits the statistical quality of the evidence

## Resolution — 2026-04-14

Completed in commit `82dfaca`.

What shipped:
- `TuningConfig.min_confidence` added with default `0.3`
- low-confidence tuning proposals are skipped instead of applied
- focused tuning regression suite passed before push
