---
created: 2026-04-08T23:35:04.832Z
title: Investigate ATT peak memory spike near cgroup limit
area: operations
files:
  - /var/lib/wanctl/metrics.db
  - /etc/systemd/system/wanctl@.service
---

## Problem

ATT wanctl process peaked at 481M memory vs 640M cgroup max (75% of limit). Current usage is 156M so the spike was transient. Likely caused by hourly maintenance cycle (VACUUM + downsample) loading the 404MB metrics.db into memory. As the DB grows, maintenance memory pressure increases and risks OOM kill.

## Solution

- Profile memory during a maintenance VACUUM cycle (watch RSS during the hourly window)
- Check if retention/downsample policy is aggressive enough to bound DB growth
- Consider incremental VACUUM or WAL checkpointing strategies
- May need to increase cgroup limit or reduce DB size via more aggressive retention
