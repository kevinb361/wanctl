# DRIFT-02 Steering Contract Diff

## Steering Spine Contract

Every in-scope steering diff is evaluated against the three Phase 222 spine invariants from `222-RESEARCH.md` Section 5:

1. **Binary on/off** — steering is enabled or disabled; no partial, weighted, or blended modes.
2. **Only new latency-sensitive connections rerouted** — existing connections are not torn down; only new flows tagged latency-sensitive get steered.
3. **Autorate baseline RTT remains authoritative** — steering defers to the autorate-frozen baseline RTT and does not mint its own baseline.

## Methodology

Each commit from `evidence/delta-commits.json.commits` was inspected with `git show <sha> -- <files_in_surface>` and assigned a `yes`, `no`, or `ambiguous` verdict for each invariant. The overall verdict is `preserves` when all three invariant verdicts are `yes`, `breaks` when any invariant verdict is `no`, and `ambiguous` when at least one invariant verdict is `ambiguous` and none are `no`.

## Verdict Table

| SHA | Subject | Category | Binary On/Off | New-Only Rerouting | Autorate Baseline RTT | Verdict |
|---|---|---|---|---|---|---|
| `84ad6aa` | fix: harden steering and storage utility contracts | behavior-changing | yes | yes | yes | preserves |

## Invariant Notes

### 84ad6aa — fix: harden steering and storage utility contracts

- **Binary On/Off (`yes`):** The RouterOSController.get_rule_status diff only adds an isinstance(item, dict) guard and preserves the enabled/disabled boolean return path for matching mangle-rule records.
- **New-Only Rerouting (`yes`):** The inspected diff touches parsed rule-status handling and SteeringDaemon.measure_current_rtt source validation only; it does not alter mangle rule matching, connection marks, or any existing-flow rerouting behavior.
- **Autorate Baseline RTT (`yes`):** The SteeringDaemon.measure_current_rtt diff narrows accepted current RTT values from autorate health and autorate IRTT to numeric values, while BaselineLoader.load_baseline_rtt remains the unchanged authority for baseline RTT.

## Summary Counts

| Verdict | Count |
|---|---:|
| preserves | 1 |
| breaks | 0 |
| ambiguous | 0 |
