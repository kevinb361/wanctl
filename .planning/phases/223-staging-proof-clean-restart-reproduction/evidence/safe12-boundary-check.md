# SAFE-12 Boundary Check

## Invariant

Controller-path source must remain byte-identical to the v1.47 close baseline for `wan_controller.py`, `queue_controller.py`, `cake_signal.py`, `src/wanctl/backends/`, `alert_engine.py`, and `fusion*.py`. This Phase 223 check is read-only and covers committed diff, staged, unstaged, untracked, and porcelain status.

## Baseline

| Field | Value |
|---|---|
| Baseline tag | `v1.47` |
| Baseline commit | `bee343b0c2f16207101aec82007a5e55fa9b6407` |
| HEAD commit | `aac7e594c9bf2e8b8c23559a593b63f0165a07f3` |
| Audit timestamp UTC | `2026-06-02T18:04:31Z` |

## Allowlist

- `src/wanctl/wan_controller.py`
- `src/wanctl/queue_controller.py`
- `src/wanctl/cake_signal.py`
- `src/wanctl/backends/`
- `src/wanctl/alert_engine.py`
- `src/wanctl/fusion_healer.py`

## Committed Diff

| Path | Added | Removed | Status |
|---|---:|---:|---|
| `src/wanctl/wan_controller.py` | 0 | 0 | unchanged |
| `src/wanctl/queue_controller.py` | 0 | 0 | unchanged |
| `src/wanctl/cake_signal.py` | 0 | 0 | unchanged |
| `src/wanctl/backends/` | 0 | 0 | unchanged |
| `src/wanctl/alert_engine.py` | 0 | 0 | unchanged |
| `src/wanctl/fusion_healer.py` | 0 | 0 | unchanged |

## Dirty Tree

### Unstaged

(clean)

### Staged

(clean)

### Untracked

(clean)

### Porcelain Status

(clean)

## Verdict

PASSED — committed controller-path diff is empty and dirty-tree checks are clean.

## Reproducibility

Copy-paste commands used to re-verify against any future HEAD:

```bash
git rev-parse v1.47^{commit}
git rev-parse HEAD
git diff bee343b0c2f16207101aec82007a5e55fa9b6407 -- src/wanctl/wan_controller.py
git diff bee343b0c2f16207101aec82007a5e55fa9b6407 -- src/wanctl/queue_controller.py
git diff bee343b0c2f16207101aec82007a5e55fa9b6407 -- src/wanctl/cake_signal.py
git diff bee343b0c2f16207101aec82007a5e55fa9b6407 -- src/wanctl/backends/
git diff bee343b0c2f16207101aec82007a5e55fa9b6407 -- src/wanctl/alert_engine.py
git diff bee343b0c2f16207101aec82007a5e55fa9b6407 -- src/wanctl/fusion_healer.py
git diff -- src/wanctl/wan_controller.py
git diff -- src/wanctl/queue_controller.py
git diff -- src/wanctl/cake_signal.py
git diff -- src/wanctl/backends/
git diff -- src/wanctl/alert_engine.py
git diff -- src/wanctl/fusion_healer.py
git diff --cached -- src/wanctl/wan_controller.py
git diff --cached -- src/wanctl/queue_controller.py
git diff --cached -- src/wanctl/cake_signal.py
git diff --cached -- src/wanctl/backends/
git diff --cached -- src/wanctl/alert_engine.py
git diff --cached -- src/wanctl/fusion_healer.py
git ls-files --others --exclude-standard -- src/wanctl/wan_controller.py
git ls-files --others --exclude-standard -- src/wanctl/queue_controller.py
git ls-files --others --exclude-standard -- src/wanctl/cake_signal.py
git ls-files --others --exclude-standard -- src/wanctl/backends/
git ls-files --others --exclude-standard -- src/wanctl/alert_engine.py
git ls-files --others --exclude-standard -- src/wanctl/fusion_healer.py
git status --porcelain -- src/wanctl/wan_controller.py
git status --porcelain -- src/wanctl/queue_controller.py
git status --porcelain -- src/wanctl/cake_signal.py
git status --porcelain -- src/wanctl/backends/
git status --porcelain -- src/wanctl/alert_engine.py
git status --porcelain -- src/wanctl/fusion_healer.py
```

## Precedent

This follows the SAFE-07 / HRDN-01 dirty-tree precedent: committed diff alone is insufficient because staged, unstaged, or untracked controller-path files could otherwise pass silently. Phase 222 SAFE-12 also PASSED with this same schema and baseline commit.
