---
pending: true
staging_host_redacted: unavailable-in-current-execution-context
start_ts: null
end_ts: null
duration_seconds: null
budget_seconds: 300
within_budget: false
---

# Phase 224 Rollback Rehearsal Budget

Staging rollback rehearsal is pending because no staging SSH target or operator-private raw
Snapshot A artifact directory is available in this execution context. Plan 03 must continue to
hard-block while `pending: true`.

## Operator Checklist

1. Capture a staging Snapshot A with raw artifacts outside the git tree:
   `scripts/phase224-snapshot-a.sh --ssh-host <staging-host> --output-dir .planning/phases/224-production-canary-rollback-discipline/evidence/snapshot-a/<TS> --raw-dir <operator-private-path>`
2. Run the rollback rehearsal in dry-run mode first:
   `scripts/phase224-rollback.sh --snapshot .planning/phases/224-production-canary-rollback-discipline/evidence/snapshot-a/<TS> --raw-dir <operator-private-path> --ssh-host <staging-host> --target-wan spectrum --dry-run`
3. Execute the rollback against staging only:
   `scripts/phase224-rollback.sh --snapshot .planning/phases/224-production-canary-rollback-discipline/evidence/snapshot-a/<TS> --raw-dir <operator-private-path> --ssh-host <staging-host> --target-wan spectrum`
4. Record the emitted `ROLLBACK_DURATION_SECONDS=<n>` here with `pending: false`, ISO start/end
   timestamps, and `within_budget: true` only if `n <= 300`.

Do not run the rollback wrapper against production during Plan 01 rehearsal.
