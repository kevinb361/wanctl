# DRIFT-01 Source-vs-Runtime Delta Report

## Baseline

| Field | Value | Notes |
|---|---|---|
| baseline_tag | `v1.39` | Runtime baseline tag. |
| baseline_commit | `d1c26de6fb284686caf32bebcd0e7c93c7c70476` | Resolved by `git rev-list -n 1 v1.39`. |
| source_tag | `v1.47` | Source-floor tag. |
| source_commit | `bee343b0c2f16207101aec82007a5e55fa9b6407` | Audit upper bound; pinned v1.47-peeled commit. |
| audit_head | `2fccf547f8f07fc9ed53f80b6055537c5ec05e9c` | Diagnostics only — not the diff endpoint. |
| source_version | `1.45.0` | Read from `src/wanctl/__init__.py`. |
| audit_timestamp_utc | `2026-06-02T15:37:07Z` | Plan execution start timestamp. |

## Surface

- `src/wanctl/steering/__init__.py`
- `src/wanctl/steering/daemon.py`
- `src/wanctl/steering/health.py`
- `src/wanctl/steering/congestion_assessment.py`
- `src/wanctl/steering/steering_confidence.py`
- `src/wanctl/steering/cake_stats.py`
- `src/wanctl/check_steering_validators.py`
- `configs/steering.yaml`
- `deploy/systemd/steering.service`
- `src/wanctl/dashboard/widgets/steering_panel.py`

## Per-File Delta

| File | Added | Removed | Status | Semantic Category |
|---|---:|---:|---|---|
| `src/wanctl/steering/__init__.py` | 0 | 0 | unchanged | unchanged |
| `src/wanctl/steering/daemon.py` | 11 | 8 | modified | behavior-changing |
| `src/wanctl/steering/health.py` | 0 | 0 | unchanged | unchanged |
| `src/wanctl/steering/congestion_assessment.py` | 0 | 0 | unchanged | unchanged |
| `src/wanctl/steering/steering_confidence.py` | 0 | 0 | unchanged | unchanged |
| `src/wanctl/steering/cake_stats.py` | 0 | 0 | unchanged | unchanged |
| `src/wanctl/check_steering_validators.py` | 5 | 0 | modified | behavior-changing |
| `configs/steering.yaml` | 0 | 0 | unchanged | unchanged |
| `deploy/systemd/steering.service` | 0 | 0 | unchanged | unchanged |
| `src/wanctl/dashboard/widgets/steering_panel.py` | 0 | 0 | unchanged | unchanged |

## Per-Commit Detail

| SHA | Date | Subject | Files | Category | Rationale |
|---|---|---|---|---|---|
| `84ad6aa2d5bc7d03ef5069c0b65e7b1cdf930538` | 2026-04-24T08:56:47-05:00 | fix: harden steering and storage utility contracts | `src/wanctl/check_steering_validators.py`, `src/wanctl/steering/daemon.py` | behavior-changing | Tightens the steering contract guard in `RouterOSController.is_steering_active` to ignore non-dict parsed records and narrows `measure_current_rtt` to numeric autorate/IRTT values, changing which malformed inputs can drive the steering decision path. |

## Reproducibility

Run these read-only commands from the repository root:

```bash
git rev-list -n 1 v1.39
git rev-parse v1.47^{commit}
git rev-parse HEAD
git diff --numstat <baseline_commit>..<source_commit> -- <surface-path>
git diff --name-status <baseline_commit>..<source_commit> -- <surface-path>
git log --format=%H%x09%s%x09%ad --date=iso-strict <baseline_commit>..<source_commit> -- <surface paths...>
git show --stat --patch <commit-sha> -- <files-in-surface...>
```

All report values above are sourced from `delta-baseline.json`, `delta-files.json`, and `delta-commits.json`; no production-side data or network connection is required to render this report.
