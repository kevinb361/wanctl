---
path: /home/kevin/projects/wanctl/src/wanctl/rate_utils.py
type: util
updated: 2026-01-21
status: active
---

# rate_utils.py

## Purpose

Rate limiting and bandwidth bounds enforcement utilities. Provides RateLimiter class to throttle router API calls (protects against oscillation), and enforce_rate_bounds to clamp rates within floor/ceiling. Critical for preventing flash wear on router NAND and API overload during instability.

## Exports

- `RateLimiter` - Sliding window rate limiter (default: 10 changes/60s)
- `can_change() -> bool` - Check if change allowed within window
- `record_change()` - Record a change event
- `time_until_available() -> float` - Seconds until next slot
- `enforce_rate_bounds(rate, floor, ceiling)` - Clamp rate within bounds
- `enforce_floor(rate, floor)` - Ensure rate >= floor
- `enforce_ceiling(rate, ceiling)` - Ensure rate <= ceiling

## Dependencies

- time - Timestamp tracking
- collections.deque - Sliding window storage

## Used By

- [[src-wanctl-autorate_continuous]] - Rate limiting router updates
