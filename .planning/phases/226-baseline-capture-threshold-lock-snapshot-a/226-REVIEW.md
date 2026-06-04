---
phase: 226-baseline-capture-threshold-lock-snapshot-a
reviewed: 2026-06-04T11:58:42Z
depth: standard
files_reviewed: 6
files_reviewed_list:
  - scripts/phase226-baseline-capture.sh
  - scripts/phase226-baseline-summary.py
  - scripts/phase226-restore.sh
  - scripts/phase226-snapshot-a.sh
  - scripts/phase226-thresholds.json
  - tests/phase226/test_tc_qdisc_parser.py
findings:
  critical: 0
  warning: 5
  info: 0
  total: 5
status: issues_found
---

# Phase 226: Code Review Report

**Reviewed:** 2026-06-04T11:58:42Z
**Depth:** standard
**Files Reviewed:** 6
**Status:** issues_found

## Summary

Reviewed the Phase 226 baseline capture, summary, restore, snapshot, thresholds, and parser tests. The largest production-safety concern is that the summary parser appears to parse the synthetic test counter lines rather than the real CAKE per-tin fields emitted by `tc -s qdisc`, which can silently turn baseline evidence into zero/partial metrics. The shell wrappers are mostly conservative/read-only, but they need tighter input validation around numeric values and remote-command parameters, and evidence redaction should be made explicit for health JSON.

## Warnings

### WR-01: CAKE parser misses real `tc -s qdisc` per-tin fields

**File:** `scripts/phase226-baseline-summary.py:24-80`
**Issue:** `parse_tc_qdisc()` only recognizes synthetic-style `Sent ... pkt`, `Dropped`, `Backlog`, `Avge delay`, and `Peak delay` lines after a `Tin` header. Real CAKE output commonly exposes per-tin counters as rows like `pkts`, `drops`, `backlog 1000b`, `av_delay`, and `pk_delay` (the fixture itself includes these at `tests/phase226/fixtures/tc-qdisc.before.txt:14-23`). Those real rows are ignored, so Snapshot A summaries can report zero or stale deltas for packets/drops/backlog/delay.
**Fix:** Teach the parser the real CAKE row labels and units before relying on the generated baseline. For example:

```python
ROW_RE = re.compile(r"^\s*(?P<label>pkts|drops|backlog|av_delay|pk_delay)\s+(?P<value>\S+)", re.I)
BYTE_RE = re.compile(r"^(?P<value>[0-9.]+)(?P<unit>b|kb|mb)?$", re.I)

def _bytes(value: str) -> int:
    match = BYTE_RE.match(value)
    if not match:
        return 0
    raw = float(match.group("value"))
    unit = (match.group("unit") or "b").lower()
    return int(raw * {"b": 1, "kb": 1000, "mb": 1000_000}[unit])

# inside the current-tin block
row_match = ROW_RE.match(line)
if row_match:
    label = row_match.group("label").lower()
    value = row_match.group("value")
    if label == "pkts":
        tins[current]["packets"] = int(value)
    elif label == "drops":
        tins[current]["drops"] = int(value)
    elif label == "backlog":
        tins[current]["backlog_bytes"] = _bytes(value)
    elif label == "av_delay":
        tins[current]["avg_delay_ms"] = _to_ms(*split_delay(value))
    elif label == "pk_delay":
        tins[current]["peak_delay_ms"] = _to_ms(*split_delay(value))
```

### WR-02: Parser test fixtures mask the real-format parser gap

**File:** `tests/phase226/test_tc_qdisc_parser.py:20-31`
**Issue:** The test asserts against synthetic `Sent`/`Dropped`/`Backlog` lines appended to the fixture rather than asserting that the parser handles the real CAKE rows (`pkts`, `drops`, `backlog`, `av_delay`, `pk_delay`). This gives false confidence and would not catch the zero-metric baseline failure in WR-01.
**Fix:** Add a test using only real CAKE row labels, with no synthetic helper lines:

```python
def test_tc_qdisc_parser_handles_real_cake_per_tin_rows() -> None:
    text = """
                   Tin 0
  pkts             1000
  drops              10
  backlog         1000b
  av_delay        0.5ms
  pk_delay        1.0ms
"""
    tin = summary.parse_tc_qdisc(text)["0"]
    assert tin.packets == 1000
    assert tin.drops == 10
    assert tin.backlog_bytes == 1000
    assert tin.avg_delay_ms == 0.5
    assert tin.peak_delay_ms == 1.0
```

### WR-03: Numeric validation accepts zero despite requiring positive values

**File:** `scripts/phase226-baseline-capture.sh:191-193`
**Issue:** `--runs`, `--duration`, and `--health-interval` are validated with `^[0-9]+$`, so `0` is accepted even though the error says positive integers. `--runs 0` can create an apparently valid capture with no run evidence, and `--health-interval 0` can make the poller loop as fast as possible during a live capture.
**Fix:** Check integer values after the regex and reject zero:

```bash
if ! [[ "$RUNS" =~ ^[0-9]+$ && "$DURATION" =~ ^[0-9]+$ && "$HEALTH_INTERVAL" =~ ^[0-9]+$ ]] \
    || (( RUNS < 1 || DURATION < 1 || HEALTH_INTERVAL < 1 )); then
    echo "ERROR: --runs, --duration, and --health-interval must be positive integers" >&2
    exit 2
fi
```

### WR-04: User-controlled remote-command parameters are not constrained

**File:** `scripts/phase226-baseline-capture.sh:58-61,162-173,253-278`; `scripts/phase226-restore.sh:168,175`; `scripts/phase226-snapshot-a.sh:188-200`
**Issue:** CLI-controlled values such as `--ssh-host`, `--router-iface`, and `--modem-iface` are interpolated into SSH/remote shell commands. Quoting covers ordinary names, but it does not provide a mutation-boundary guarantee if a value contains shell metacharacters or if an SSH host value is parsed as an option. These scripts are operator tools, but this is still a production network control system and the wrappers should fail closed on unsafe identifiers.
**Fix:** Add strict allowlists before any SSH call and use fixed command constructors. For example:

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

**File:** `scripts/phase226-snapshot-a.sh:212`; `scripts/phase226-baseline-capture.sh:253,276,78-94`
**Issue:** Snapshot A writes the health payload to `snapshot-a-health.bound.redacted.json`, and baseline capture stores `health.before.json`, `health.after.json`, and `health.window.ndjson`, but the JSON is copied directly from `/health` without recursive redaction. If the health contract grows to include config echoes, tokens, SSH metadata, or private router fields, committable evidence can leak sensitive values while appearing redacted.
**Fix:** Pipe all health JSON/NDJSON through a recursive key-based redactor before writing committable evidence, or rename only truly unredacted private artifacts. Example redactor logic:

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

---

_Reviewed: 2026-06-04T11:58:42Z_
_Reviewer: the agent (gsd-code-reviewer)_
_Depth: standard_
