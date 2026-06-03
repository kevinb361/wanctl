# Phase 222 Steering Drift Audit Evidence

## Audit Surface

The audit surface follows `222-RESEARCH.md` Section 3 exactly. No source path outside this surface is included in Plan 222-01 evidence:

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

Extending this surface requires an explicit note here before any downstream artifact is regenerated.

## Baseline Rationale

The baseline is the `v1.39` git tag resolved by:

```bash
git rev-list -n 1 v1.39
```

Resolved baseline commit: `d1c26de6fb284686caf32bebcd0e7c93c7c70476`.

Phase 212 proves the live steering runtime reports `1.39.0`, but it does not identify a more specific deployed-binary commit. Because deployed-binary commit evidence is not available, the conservative baseline is the `v1.39` tag. If later evidence identifies the deployed binary's exact commit, it should supersede this baseline only through an explicit reviewed deviation.

## Source-Floor Anchor (v1.47-peeled)

The audit upper bound is the peeled `v1.47` commit resolved once by:

```bash
git rev-parse v1.47^{commit}
```

Resolved `source_commit`: `bee343b0c2f16207101aec82007a5e55fa9b6407`.

This SHA is the audit upper bound for every diff and log command in Plan 222-01. It is **not** replaced with current `HEAD`. The current `audit_head` is recorded separately for diagnostics only and is never used as the diff endpoint. This preserves the v1.47 source-floor anchor from the Phase 220 `base_sha` precedent and prevents silent scope expansion if steering edits land between planning and execution.

## Milestone Bucketing (incl. v1.45 synthetic bucket)

Milestone buckets use peeled tag commits from:

```bash
git rev-list -n 1 <tag>
```

The repo has no `v1.45` tag; tags jump from `v1.44` to `v1.46`. Commits whose nearest preceding tag is `v1.44` and nearest following tag is `v1.46` are assigned the synthetic bucket `v1.44..v1.46`. This matches source-version `1.45.0` evidence while preserving tag-based reproducibility.

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

Downstream artifacts are reproducible from these commands and the pinned `baseline_commit` / `source_commit` in `delta-baseline.json`.

## Posture

Plan 222-01 is read-only and artifact-producing. It runs no production probe, reads no `/etc/wanctl/secrets`, touches no router credentials, performs no deploy, and mutates no source/runtime behavior. Evidence is limited to local git history and committed planning artifacts.
