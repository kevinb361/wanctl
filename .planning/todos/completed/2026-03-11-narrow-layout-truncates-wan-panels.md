---
created: 2026-03-11T00:00:00Z
title: Fix narrow layout WAN panel truncation
area: ui
files:
  - src/wanctl/dashboard/app.py:38
  - src/wanctl/dashboard/dashboard.tcss:36
  - tests/dashboard/test_layout.py:60
---

## Problem

In the dashboard's narrow/stacked layout (`<120` columns), the WAN panels get
height-squeezed and some important lines such as UL rate, RTT, and Router OK are
not visible. The underlying health data is still present; the problem is purely
presentation in the narrow layout.

This is low-priority UI debt, but it makes the dashboard less useful on smaller
terminals during live operations.

## Solution

Keep this scoped to layout/rendering only.

Possible approaches:
- Enforce a larger minimum height for `WanPanelWidget` in narrow mode.
- Add scrolling around the WAN column when stacked vertically.
- Introduce a compact narrow-mode rendering that preserves the most important
  WAN status lines in fewer rows.

Wide layout (`>=120` columns) already behaves correctly, so this should remain a
targeted narrow-layout fix rather than a larger dashboard redesign.

## Resolution — 2026-04-14

Completed in the local working tree during the soak-prep pass.

What changed:
- narrow stacked layout now enforces taller WAN panels (`min-height: 8`)
- narrow WAN columns now reserve usable vertical space instead of squeezing the
  panel region
- dashboard layout test coverage now asserts narrow-mode WAN panel height
