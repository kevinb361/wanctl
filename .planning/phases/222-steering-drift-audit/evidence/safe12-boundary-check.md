# SAFE-12 Boundary Check

## SAFE-12 Invariant

Controller-path source must remain byte-identical to the v1.47 close baseline for `wan_controller.py`, `queue_controller.py`, `cake_signal.py`, `src/wanctl/backends/`, `alert_engine.py`, and `fusion*.py` (represented here by `fusion_healer.py`).

This check is fail-closed against committed history AND the index AND the working tree AND untracked files. The dirty-tree pattern cites `scripts/check-safe07-source-diff.sh` (HRDN-01 / SAFE-07 precedent) as the source-of-truth precedent: committed diff alone is insufficient because staged, unstaged, or untracked controller-path files could otherwise pass silently.

## Baseline

| Field | Value |
|-------|-------|
| Baseline tag | `v1.47` |
| Baseline commit | `bee343b0c2f16207101aec82007a5e55fa9b6407` |
| HEAD commit | `26ab23e5f048500fbaed4275543444edb68171cb` |
| Audit timestamp UTC | `2026-06-02T15:45:18Z` |

## Allowlist

- `src/wanctl/wan_controller.py`
- `src/wanctl/queue_controller.py`
- `src/wanctl/cake_signal.py`
- `src/wanctl/backends/`
- `src/wanctl/alert_engine.py`
- `src/wanctl/fusion_healer.py`

## Committed Diff

| Path | Added | Removed | Status |
|------|------:|--------:|--------|
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

Commands used:

```bash
git rev-parse v1.47^{commit}
git rev-parse HEAD
git diff --numstat bee343b0c2f16207101aec82007a5e55fa9b6407..26ab23e5f048500fbaed4275543444edb68171cb -- src/wanctl/wan_controller.py
git diff --numstat bee343b0c2f16207101aec82007a5e55fa9b6407..26ab23e5f048500fbaed4275543444edb68171cb -- src/wanctl/queue_controller.py
git diff --numstat bee343b0c2f16207101aec82007a5e55fa9b6407..26ab23e5f048500fbaed4275543444edb68171cb -- src/wanctl/cake_signal.py
git diff --numstat bee343b0c2f16207101aec82007a5e55fa9b6407..26ab23e5f048500fbaed4275543444edb68171cb -- src/wanctl/backends/
git diff --numstat bee343b0c2f16207101aec82007a5e55fa9b6407..26ab23e5f048500fbaed4275543444edb68171cb -- src/wanctl/alert_engine.py
git diff --numstat bee343b0c2f16207101aec82007a5e55fa9b6407..26ab23e5f048500fbaed4275543444edb68171cb -- src/wanctl/fusion_healer.py
git diff --numstat bee343b0c2f16207101aec82007a5e55fa9b6407..HEAD -- src/wanctl/wan_controller.py \
  src/wanctl/queue_controller.py \
  src/wanctl/cake_signal.py \
  src/wanctl/backends/ \
  src/wanctl/alert_engine.py \
  src/wanctl/fusion_healer.py
git diff --cached --numstat -- src/wanctl/wan_controller.py \
  src/wanctl/queue_controller.py \
  src/wanctl/cake_signal.py \
  src/wanctl/backends/ \
  src/wanctl/alert_engine.py \
  src/wanctl/fusion_healer.py
git diff --numstat -- src/wanctl/wan_controller.py \
  src/wanctl/queue_controller.py \
  src/wanctl/cake_signal.py \
  src/wanctl/backends/ \
  src/wanctl/alert_engine.py \
  src/wanctl/fusion_healer.py
git ls-files --others --exclude-standard -- src/wanctl/wan_controller.py \
  src/wanctl/queue_controller.py \
  src/wanctl/cake_signal.py \
  src/wanctl/backends/ \
  src/wanctl/alert_engine.py \
  src/wanctl/fusion_healer.py
git status --porcelain -- src/wanctl/wan_controller.py \
  src/wanctl/queue_controller.py \
  src/wanctl/cake_signal.py \
  src/wanctl/backends/ \
  src/wanctl/alert_engine.py \
  src/wanctl/fusion_healer.py
```

Recorded outputs are encoded in `safe12-boundary-check.json`: `per_path_diff` for committed history and `dirty_tree` for staged, unstaged, untracked, and porcelain status checks.
