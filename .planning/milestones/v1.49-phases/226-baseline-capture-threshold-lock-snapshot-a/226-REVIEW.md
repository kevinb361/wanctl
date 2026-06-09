---
phase: 226-baseline-capture-threshold-lock-snapshot-a
reviewed: 2026-06-04T12:57:17Z
depth: standard
files_reviewed: 11
files_reviewed_list:
  - .claude/context.md
  - scripts/phase226-baseline-capture.sh
  - scripts/phase226-baseline-summary.py
  - scripts/phase226-restore.sh
  - scripts/phase226-snapshot-a.sh
  - scripts/phase226-thresholds.json
  - tests/phase226/fixtures/health.window.ndjson
  - tests/phase226/fixtures/tc-qdisc.after.txt
  - tests/phase226/fixtures/tc-qdisc.before.txt
  - tests/phase226/fixtures/tc-qdisc.during.txt
  - tests/phase226/test_tc_qdisc_parser.py
findings:
  critical: 0
  warning: 6
  info: 0
  total: 6
status: issues_found
---

# Phase 226: Code Review Report

**Reviewed:** 2026-06-04T12:57:17Z
**Depth:** standard
**Files Reviewed:** 11
**Status:** issues_found

## Summary

Reviewed the Phase 226 baseline capture, baseline summary parser, Snapshot A capture, dry-run restore proof, threshold artifact, fixtures, and parser tests. The CAKE parser gap called out in earlier review context appears substantially addressed, but there are still evidence-correctness and safety issues that can misstate baseline/rollback proof quality or weaken the scripts' fail-closed posture.

## Warnings

### WR-01: DSCP neutrality proof is hardcoded instead of observed

**File:** `scripts/phase226-baseline-capture.sh:279`
**Issue:** The script writes `udp_observed_egress_dscp=0` and `tcp_observed_egress_dscp=0` as proof text without capturing or parsing packets. If the client, network stack, or path marks traffic unexpectedly, the retained evidence will still claim DSCP neutrality. That can invalidate the Phase 226 baseline used for tin-separation gates.
**Fix:** Capture a read-only observation and derive the proof from it, or explicitly downgrade the artifact name to “not requested by command-line options.” For example, run a bounded `tcpdump`/`tshark` capture on the local test host during the reference flows and fail unless parsed DSCP values are zero.

### WR-02: Health `floor_hit_cycles` are summed across samples

**File:** `scripts/phase226-baseline-summary.py:202-204,291-296`
**Issue:** `parse_health_window()` adds `floor_hit_cycles` for every health sample. If the health field is a cumulative counter or a current dwell counter, summing each sample overcounts the baseline window and can falsely trip UL-stability comparisons. The fixture currently encodes this summed behavior, so the test will preserve the overcount.
**Fix:** Treat counter-shaped fields as deltas over the window, or explicitly parse a documented total-delta field when available. Example:

```python
floor_values.append(int(upload.get("floor_hit_cycles") or spectrum.get("floor_hit_cycles") or 0))

# after iterating samples
floor_hits = max(0, max(floor_values, default=0) - min(floor_values, default=0))
```

If `/health` exposes both cumulative and instantaneous fields, prefer the cumulative total delta and update the fixture to assert that contract.

### WR-03: Numeric validation accepts zero despite requiring positive values

**File:** `scripts/phase226-baseline-capture.sh:191-193`
**Issue:** `--runs`, `--duration`, and `--health-interval` are validated with `^[0-9]+$`, so `0` is accepted even though the error says positive integers. `--runs 0` can create a hollow capture, and `--health-interval 0` can make the poller loop as fast as possible during live capture.
**Fix:** Reject zero after the regex check:

```bash
if ! [[ "$RUNS" =~ ^[0-9]+$ && "$DURATION" =~ ^[0-9]+$ && "$HEALTH_INTERVAL" =~ ^[0-9]+$ ]] \
    || (( RUNS < 1 || DURATION < 1 || HEALTH_INTERVAL < 1 )); then
    echo "ERROR: --runs, --duration, and --health-interval must be positive integers" >&2
    exit 2
fi
```

### WR-04: User-controlled SSH/interface parameters are not allowlisted

**File:** `scripts/phase226-baseline-capture.sh:58-61,162-173,253-278`; `scripts/phase226-restore.sh:168,175`; `scripts/phase226-snapshot-a.sh:188-200`
**Issue:** CLI-controlled values such as `--ssh-host`, `--router-iface`, and `--modem-iface` are interpolated into SSH/remote shell commands. Existing quoting handles normal values, but it does not provide a strong mutation-boundary guarantee for unexpected metacharacters or host values beginning with `-`.
**Fix:** Fail closed with simple allowlists before any SSH call:

```bash
validate_safe_name() {
    local label="$1" value="$2"
    if ! [[ "$value" =~ ^[A-Za-z0-9_.:-]+$ ]] || [[ "$value" == -* ]]; then
        echo "ERROR: unsafe $label: $value" >&2
        exit 2
    fi
}

validate_safe_name "ssh host" "$SSH_HOST"
validate_safe_name "router iface" "$ROUTER_IFACE"
validate_safe_name "modem iface" "$MODEM_IFACE"
```

### WR-05: Health evidence is labeled redacted but written unfiltered

**File:** `scripts/phase226-snapshot-a.sh:212`; `scripts/phase226-baseline-capture.sh:78-94,253,276`
**Issue:** Snapshot A writes `/health` to `snapshot-a-health.bound.redacted.json`, and baseline capture commits health before/window/after payloads, but the JSON is copied directly. If the health contract grows to include config echoes, keys, tokens, or private router metadata, committable evidence can leak sensitive values while appearing redacted.
**Fix:** Pipe health JSON and NDJSON samples through a recursive key-based redactor before writing committed artifacts:

```python
SECRET_KEYS = ("password", "token", "secret", "api_key", "apikey", "key")

def redact(value):
    if isinstance(value, dict):
        return {
            k: ("REDACTED" if any(s in k.lower() for s in SECRET_KEYS) else redact(v))
            for k, v in value.items()
        }
    if isinstance(value, list):
        return [redact(v) for v in value]
    return value
```

### WR-06: Snapshot config equality compares redacted bytes only

**File:** `scripts/phase226-snapshot-a.sh:241-247,285-289`
**Issue:** `config_equality` is set from SHA-256 values of `deployed-spectrum.redacted.yaml` and `repo-spectrum.redacted.yaml`. Two configs with different secret-bearing values can therefore report `verdict: equal` after both sides are replaced with `REDACTED`. The manifest also presents this as “Deployed Config Equality,” which can mislead rollback/evidence consumers.
**Fix:** Rename the current verdict to `redacted_config_equality`, and add a separate raw-byte comparison when safe. At minimum, emit both labels clearly:

```bash
redacted_config_equality="diff"
if [[ "$deployed_sha" == "$repo_sha" ]]; then
    redacted_config_equality="equal"
fi
raw_repo_sha="$(artifact_sha256 configs/spectrum.yaml)"
raw_config_equality="diff"
if [[ "$raw_config_sha" == "$raw_repo_sha" ]]; then
    raw_config_equality="equal"
fi
```

---

_Reviewed: 2026-06-04T12:57:17Z_
_Reviewer: the agent (gsd-code-reviewer)_
_Depth: standard_
