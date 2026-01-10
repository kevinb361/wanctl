# Security Review: cake_stats.py
**File:** `/home/kevin/projects/wanctl/src/wanctl/steering/cake_stats.py`  
**Reviewed:** 2026-01-08  
**Lines of Code:** 179  
**Complexity:** Medium

## Executive Summary

CAKE statistics reader for RouterOS queue monitoring. Contains **1 CRITICAL issue**, **3 WARNINGS**, and **2 SUGGESTIONS**. The critical issue is command injection via queue names. Overall structure is good but needs hardening.

---

## CRITICAL Issues

### C1: Command Injection via Queue Names (Lines 62, 158, 170)
**Location:** `read_stats()`, `reset_counters()`, `reset_all_counters()`  
**Risk:** HIGH - Arbitrary RouterOS command execution

**Problem:**
```python
# Line 62
cmd = f'/queue/tree print stats detail where name="{queue_name}"'

# Line 158
cmd = f'/queue/tree reset-counters [find name="{queue_name}"]'

# Line 170  
cmd = '/queue/tree reset-counters [find name~"WAN-"]'
```

Queue names are interpolated into commands without escaping. If an attacker modifies config, they can inject commands:

**Attack scenario:**
```yaml
cake_queues:
  primary_download: 'WAN-Download-X"] ; /system reset-configuration ; #'
```

**Solution:**
1. Validate queue names with regex: `^[A-Za-z0-9_-]+$`
2. Reject special characters: `"`, `]`, `;`, `#`
3. Add validation in `SteeringConfig._load_specific_fields()` (daemon.py lines 172-182)

```python
def validate_queue_name(self, name: str, field: str) -> str:
    """Validate queue name for safe RouterOS interpolation"""
    if not re.match(r'^[A-Za-z0-9_-]+$', name):
        raise ConfigValidationError(
            f"{field} contains unsafe characters. "
            "Allowed: A-Z, a-z, 0-9, underscore, hyphen"
        )
    if len(name) > 50:
        raise ConfigValidationError(f"{field} too long (max 50 chars)")
    return name
```

---

## WARNING Issues

### W1: No Timeout on RouterOS Commands (Lines 63, 159, 171)
**Location:** All `run_cmd()` calls  
**Risk:** Reader hangs on network failure

**Problem:**
```python
# Line 63
rc, out, err = self.client.run_cmd(cmd, capture=True)
```

No timeout specified. If RouterOS hangs, reader waits forever.

**Solution:**
```python
rc, out, err = self.client.run_cmd(cmd, capture=True, timeout=10)
```

---

### W2: JSON Parsing Without Validation (Lines 74-92)
**Location:** `read_stats()` - REST API response parsing  
**Risk:** Malformed JSON crashes reader

**Problem:**
```python
# Line 76-77
data = json.loads(out)
# REST API returns a list of matching queues
if isinstance(data, list) and len(data) > 0:
    q = data[0]
elif isinstance(data, dict):
    q = data
```

No try/except around `json.loads()`. Malformed response crashes reader.

**Solution:**
```python
try:
    data = json.loads(out)
except json.JSONDecodeError as e:
    self.logger.error(f"Invalid JSON from RouterOS: {e}")
    return None

if isinstance(data, list) and len(data) > 0:
    q = data[0]
elif isinstance(data, dict):
    q = data
else:
    self.logger.warning(f"Unexpected JSON structure: {type(data)}")
    return None
```

---

### W3: Counter Reset Race Condition (Lines 882-884 in daemon.py)
**Location:** `run_cycle()` calls `reset_counters()` before `read_stats()`  
**Risk:** Lost drop events between reset and read

**Problem:**
```python
# In daemon.py lines 882-884
if self.config.reset_counters:
    self.cake_reader.reset_counters(self.config.primary_download_queue)

# Read CAKE statistics
stats = self.cake_reader.read_stats(self.config.primary_download_queue)
```

If packets drop between reset and read, they're not counted. This is a 10-20ms window but could miss congestion spikes.

**Impact:** Underreported drops, delayed RED state detection

**Solution:**
1. Read, then reset (capture drops since last cycle)
2. Use `read_stats()` delta tracking (lines 122-142) which doesn't require resets

**Recommendation:** Remove `reset_counters` config option, always use delta tracking (safer).

---

## SUGGESTIONS

### S1: Regex Parsing is Fragile (Lines 101-120)
**Location:** `read_stats()` - SSH output parsing  
**Issue:** Relies on specific RouterOS output format

**Current:**
```python
match = re.search(r'packets=(\d+)', out)
if match:
    current.packets = int(match.group(1))
```

**Problem:** RouterOS version changes could break parsing.

**Improvement:**
1. Prefer REST API (JSON is structured)
2. Add format version detection
3. Test against multiple RouterOS versions

---

### S2: Delta Tracking State Not Persisted (Line 50)
**Location:** `self.previous_stats = {}`  
**Issue:** Delta tracking resets on reader restart

**Problem:**
If daemon restarts, first `read_stats()` returns cumulative totals (not delta), causing false RED state.

**Solution:**
Persist `previous_stats` to disk:
```python
def save_previous_stats(self, state_file: Path):
    """Persist delta tracking state"""
    with open(state_file, 'w') as f:
        json.dump(self.previous_stats, f)

def load_previous_stats(self, state_file: Path):
    """Load delta tracking state"""
    if state_file.exists():
        with open(state_file, 'r') as f:
            self.previous_stats = json.load(f)
```

---

## Estimated Effort
- **C1** (Queue name validation): 2 hours
- **W1** (Timeouts): 30 minutes
- **W2** (JSON error handling): 1 hour
- **W3** (Reset race condition): 2 hours (redesign reset logic)
- **S1-S2** (Suggestions): 2-3 hours
- **Total:** 7-10 hours

---

## Conclusion

**Critical fix needed:** Queue name validation (C1) to prevent command injection. Warning issues (W1-W3) improve reliability but aren't security-critical. Module is well-designed with delta tracking, but needs hardening for production use.

**Risk assessment:** MEDIUM-HIGH due to command injection. Attack requires config modification, but impact is full RouterOS compromise.
