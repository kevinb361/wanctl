# Phase 212: Production Inventory And Drift Audit - Pattern Map

**Mapped:** 2026-05-27
**Files analyzed:** 16
**Analogs found:** 16 / 16

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `.planning/phases/212-production-inventory-and-drift-audit/evidence/README.md` | docs | file-I/O | `.planning/phases/212-production-inventory-and-drift-audit/212-VALIDATION.md` | role-match |
| `.planning/phases/212-production-inventory-and-drift-audit/evidence/repo-expected-summary.json` | config/artifact | transform | `configs/spectrum.yaml`, `configs/att.yaml`, `configs/steering.yaml` | role-match |
| `.planning/phases/212-production-inventory-and-drift-audit/evidence/systemd-spectrum.txt` | artifact | request-response | `deploy/systemd/wanctl@.service` | exact |
| `.planning/phases/212-production-inventory-and-drift-audit/evidence/systemd-att.txt` | artifact | request-response | `deploy/systemd/wanctl@.service` | exact |
| `.planning/phases/212-production-inventory-and-drift-audit/evidence/systemd-steering.txt` | artifact | request-response | `deploy/systemd/steering.service` | exact |
| `.planning/phases/212-production-inventory-and-drift-audit/evidence/health-spectrum.json` | artifact | request-response | `src/wanctl/health_check.py` | exact |
| `.planning/phases/212-production-inventory-and-drift-audit/evidence/health-att.json` | artifact | request-response | `src/wanctl/health_check.py` | exact |
| `.planning/phases/212-production-inventory-and-drift-audit/evidence/health-steering.json` | artifact | request-response | `src/wanctl/steering/health.py` | exact |
| `.planning/phases/212-production-inventory-and-drift-audit/evidence/config-spectrum.redacted.yaml` | artifact | file-I/O + transform | `src/wanctl/config_base.py` | role-match |
| `.planning/phases/212-production-inventory-and-drift-audit/evidence/config-att.redacted.yaml` | artifact | file-I/O + transform | `src/wanctl/config_base.py` | role-match |
| `.planning/phases/212-production-inventory-and-drift-audit/evidence/config-steering.redacted.yaml` | artifact | file-I/O + transform | `src/wanctl/config_base.py` | role-match |
| `.planning/phases/212-production-inventory-and-drift-audit/evidence/steering-state.redacted.json` | artifact | file-I/O + transform | `src/wanctl/state_manager.py` | role-match |
| `.planning/phases/212-production-inventory-and-drift-audit/212-production-inventory.md` | report | transform | `src/wanctl/operator_summary.py` | role-match |
| `.planning/phases/212-production-inventory-and-drift-audit/212-REPORT.md` | report | transform | `src/wanctl/operator_summary.py` | role-match |
| `scripts/phase212-inventory-audit.py` *(optional if helper code is added)* | utility | file-I/O + request-response + transform | `scripts/phase198-loaded-window-audit.py`, `scripts/phase206-gate-check.py` | role-match |
| `tests/test_phase212_inventory.py` *(optional if helper code is added)* | test | batch | `tests/test_phase206_predeploy_gate.py`, `tests/test_check_config.py` | role-match |

## Pattern Assignments

### Evidence markdown: `evidence/README.md` (docs, file-I/O)

**Analog:** `.planning/phases/212-production-inventory-and-drift-audit/212-VALIDATION.md`

**Markdown contract pattern** (lines 16-24):
```markdown
## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest 9.0.2 in `.venv` |
| **Config file** | `pyproject.toml` |
| **Quick run command** | `.venv/bin/pytest -o addopts='' tests/test_health_check.py tests/test_check_config.py -q` |
```

Apply this table-first style to record command timestamp, host/source, redaction method, and whether output is raw, summarized, or redacted.

---

### Repo expected summary: `evidence/repo-expected-summary.json` (config/artifact, transform)

**Analogs:** `configs/spectrum.yaml`, `configs/att.yaml`, `configs/steering.yaml`

**Autorate endpoint + non-secret operating keys** (`configs/spectrum.yaml` lines 5-27):
```yaml
wan_name: "spectrum"
health_check:
  host: "10.10.110.223"
  port: 9101
router:
  transport: "linux-cake-netlink"
  host: "10.10.99.1"
  user: "admin"
  ssh_key: "/etc/wanctl/ssh/router.key"
  password: "${ROUTER_PASSWORD}"
```

**ATT endpoint pattern** (`configs/att.yaml` lines 11-31):
```yaml
health_check:
  host: "10.10.110.227"
  port: 9101
router:
  transport: "linux-cake-netlink"
  host: "10.10.99.1"
  user: "admin"
  ssh_key: "/etc/wanctl/ssh/router.key"
  password: "${ROUTER_PASSWORD}"
```

**Steering source/state keys** (`configs/steering.yaml` lines 7-30, 93-96):
```yaml
topology:
  primary_wan: "spectrum"
  primary_wan_config: "/etc/wanctl/spectrum.yaml"
  alternate_wan: "att"
cake_state_sources:
  primary: "/var/lib/wanctl/spectrum_state.json"
state:
  file: "/var/lib/wanctl/steering_state.json"
  history_size: 240
```

Preserve proof-relevant values, but redact `password`, `ssh_key` if policy treats private-key path as sensitive, and any secret-like values.

---

### Systemd evidence: `evidence/systemd-spectrum.txt`, `evidence/systemd-att.txt` (artifact, request-response)

**Analog:** `deploy/systemd/wanctl@.service`

**Service contract** (lines 9-22):
```ini
[Service]
Type=simple
User=wanctl
Group=wanctl
WorkingDirectory=/opt/wanctl
ExecStart=/usr/bin/python3 /opt/wanctl/autorate_continuous.py --config /etc/wanctl/%i.yaml
Restart=on-failure
RestartSec=5s
WatchdogSec=30s
Environment=PYTHONPATH=/opt
Environment=WANCTL_STATE_DIR=/var/lib/wanctl
Environment=WANCTL_LOG_DIR=/var/log/wanctl
Environment=WANCTL_RUN_DIR=/run/wanctl
EnvironmentFile=-/etc/wanctl/secrets
```

Capture `ActiveState`, `SubState`, `ExecMainStartTimestamp`, `ExecMainPID`, `NRestarts`, `ExecStart`, `FragmentPath`, `WatchdogUSec`, and config path. Do not save raw secret-bearing environment values.

---

### Systemd evidence: `evidence/systemd-steering.txt` (artifact, request-response)

**Analog:** `deploy/systemd/steering.service`

**Service contract** (lines 9-22):
```ini
[Service]
Type=simple
User=wanctl
Group=wanctl
WorkingDirectory=/opt/wanctl
ExecStart=/usr/bin/python3 -m wanctl.steering.daemon --config /etc/wanctl/steering.yaml
Restart=on-failure
RestartSec=5s
WatchdogSec=30s
Environment=PYTHONPATH=/opt
Environment=WANCTL_STATE_DIR=/var/lib/wanctl
Environment=WANCTL_LOG_DIR=/var/log/wanctl
Environment=WANCTL_RUN_DIR=/run/wanctl
EnvironmentFile=-/etc/wanctl/secrets
```

Use this to compare live `systemctl show` output against expected unit path, config path, watchdog, restart policy, and service identity.

---

### Autorate health artifacts: `evidence/health-spectrum.json`, `evidence/health-att.json` (artifact, request-response)

**Analog:** `src/wanctl/health_check.py`

**HTTP response pattern** (lines 170-187):
```python
def do_GET(self) -> None:
    """Handle GET requests."""
    if self.path == "/health" or self.path == "/":
        health = self._get_health_status()
        status_code = 200 if health["status"] == "healthy" else 503

        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(health, indent=2).encode())
```

**Top-level health fields** (lines 194-204, 230-235):
```python
health: dict[str, Any] = {
    "status": "healthy",
    "uptime_seconds": round(uptime, 1),
    "version": __version__,
    "consecutive_failures": self.consecutive_failures,
}
is_healthy = self.consecutive_failures < 3 and all_routers_reachable and not disk_warning
health["status"] = "healthy" if is_healthy else "degraded"
health["summary"] = self._build_summary_section(health)
```

**Per-WAN fields to cite** (lines 246-257, 290-292):
```python
wan_health: dict[str, Any] = {
    "name": config.wan_name,
    "baseline_rtt_ms": round(wan_controller.baseline_rtt, 2),
    "load_rtt_ms": round(wan_controller.load_rtt, 2),
    "download": self._build_rate_hysteresis_section(...),
    "upload": self._build_rate_hysteresis_section(...),
    "router_connectivity": wan_controller.router_connectivity.to_dict(),
}
wan_health["tuning"] = self._build_tuning_section(health_data, wan_controller)
wan_health["storage"] = self._build_storage_section(health_data)
wan_health["runtime"] = self._build_runtime_section(...)
```

Do not treat `status == healthy` or `GREEN` as user-experience proof; report it as daemon-state evidence only.

---

### Steering health artifact: `evidence/health-steering.json` (artifact, request-response)

**Analog:** `src/wanctl/steering/health.py`

**HTTP response pattern** (lines 110-124):
```python
def do_GET(self) -> None:
    """Handle GET requests."""
    if self.path == "/health" or self.path == "/":
        health = self._get_health_status()
        status_code = 200 if health["status"] == "healthy" else 503
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(health, indent=2).encode())
```

**Steering fields to capture** (lines 135-154, 164-183):
```python
health: dict[str, Any] = {
    "status": "healthy",
    "uptime_seconds": round(uptime, 1),
    "version": __version__,
}
health["steering"] = self._build_steering_status_section(state)
health["congestion"] = self._build_congestion_section(state)
health["decision"] = self._build_decision_section(state, uptime)
health["counters"] = self._build_counters_section(state)
health["thresholds"] = self._build_thresholds_section()
health["router_connectivity"] = self.daemon.router_connectivity.to_dict()
health["pid"] = os.getpid()
```

**Folded todo timestamp handling** (lines 51-67, 262-283):
```python
def _parse_transition_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    normalized = value.replace("Z", "+00:00") if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    return parsed.astimezone(UTC) if parsed.tzinfo else parsed.replace(tzinfo=UTC)

return {
    "last_transition_time": _format_iso_timestamp(last_transition, self.start_time),
    "time_in_state_seconds": time_in_state,
}
```

---

### Redacted deployed configs: `config-*.redacted.yaml` (artifact, file-I/O + transform)

**Analog:** `src/wanctl/config_base.py`

**YAML parse + error pattern** (lines 403-414):
```python
self.config_file_path = config_path
with open(config_path) as f:
    try:
        self.data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        if hasattr(e, "problem_mark") and e.problem_mark is not None:
            mark = e.problem_mark
            raise ConfigValidationError(
                f"YAML parse error in {config_path} at line {mark.line + 1}, "
                f"column {mark.column + 1}: {e.problem}"
            ) from e
        raise ConfigValidationError(f"YAML parse error in {config_path}: {e}") from e
```

**Shared config fields** (lines 427-445):
```python
self.wan_name = self.validate_identifier(self.data["wan_name"], "wan_name")
router = self.data["router"]
self.router_transport = router.get("transport", "rest")
self.router_host = router["host"]
self.router_user = router["user"]
self.ssh_key = router["ssh_key"]
self.lock_file = Path(self.data["lock_file"])
self.lock_timeout = self.data["lock_timeout"]
```

For Phase 212 helper code, parse YAML structurally with `yaml.safe_load()`, redact recursively, then emit stable sorted YAML. Do not regex raw YAML except as a last-resort artifact review check.

---

### Steering state artifact: `evidence/steering-state.redacted.json` (artifact, file-I/O + transform)

**Analog:** `src/wanctl/state_manager.py`

**Safe state load pattern** (lines 351-389):
```python
loaded = safe_json_load_file(
    self.state_file, logger=self.logger, default=None, error_context=self.context
)
if loaded is None:
    backup_file = self._get_backup_path()
    if backup_file.exists():
        self.logger.warning(
            f"{self.context}: Primary state corrupted, attempting backup recovery"
        )
        loaded = safe_json_load_file(...)
...
self.state = self.schema.validate_state(loaded, logger=self.logger)
self.logger.debug(f"{self.context}: Loaded state from {self.state_file}")
```

**Steering-specific state shape** (lines 455-463, 558-572, 658-668):
```python
class SteeringStateManager(StateManager):
    """Specialized state manager for steering daemon.
    - Deque-based bounded history (automatic eviction)
    - Legacy state name migration
    - File-level locking for concurrent access
    - State file backups (.backup and .corrupt)
    """

history_keys = ["history_rtt", "history_delta", "cake_drops_history", "queue_depth_history"]

transition = {
    "timestamp": datetime.datetime.now().isoformat(),
    "from": old_state,
    "to": new_state,
    "bad_count": self.state.get("bad_count", 0),
    "good_count": self.state.get("good_count", 0),
}
```

For the audit, read state as evidence only. If invalid/corrupt, report that fact; do not run recovery, backup, or mutation paths.

---

### Inventory/report markdown: `212-production-inventory.md`, `212-REPORT.md` (report, transform)

**Analog:** `src/wanctl/operator_summary.py`

**Source ingestion pattern** (lines 23-35):
```python
def _decode_payload(raw: str, source: str) -> dict[str, Any]:
    payload = json.loads(raw)
    if not isinstance(payload, dict):
        raise TypeError(f"Source '{source}' did not decode to a JSON object")
    return cast(dict[str, Any], payload)

def _read_source(source: str) -> dict[str, Any]:
    if source.startswith(("http://", "https://")):
        with urlopen(source, timeout=5) as response:
            return _decode_payload(response.read().decode(), source)
    return _decode_payload(Path(source).read_text(), source)
```

**Operator table pattern** (lines 44-92):
```python
def _build_table_rows(source: str, payload: dict[str, Any]) -> list[list[str]]:
    summary = payload.get("summary")
    if not isinstance(summary, dict):
        raise TypeError(f"Source '{source}' does not include a summary section")
    service = str(summary.get("service", "unknown"))
    ...
    headers = ["Service", "Name", "Status", "State", "Storage", "Runtime", "Alerts", "Notes"]
    return str(tabulate(rows, headers=headers, tablefmt="simple"))
```

Phase 212 report tables should use the requested columns: expected value, live value, verdict, evidence path, and impact on later phases.

---

### Optional helper: `scripts/phase212-inventory-audit.py` (utility, file-I/O + request-response + transform)

**Analogs:** `scripts/phase198-loaded-window-audit.py`, `scripts/phase206-gate-check.py`

**Imports + stdlib helper shape** (`scripts/phase198-loaded-window-audit.py` lines 16-25):
```python
from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any
```

**Nested JSON extraction pattern** (`scripts/phase198-loaded-window-audit.py` lines 33-39):
```python
def _nested_get(obj: dict[str, Any], dotted: str) -> Any:
    cur: Any = obj
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur
```

**Read/validate JSON pattern** (`scripts/phase206-gate-check.py` lines 62-67):
```python
def _read_json(path: str) -> dict:
    with Path(path).open(encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise TypeError(f"JSON root is not an object: {path}")
    return data
```

**Drift classifier style** (`scripts/phase206-gate-check.py` lines 78-119):
```python
def check_rrul_p99(baseline: dict, candidate: dict, threshold_pct: float) -> tuple[bool, str]:
    meta_base = baseline.get("meta", {}) if isinstance(baseline, dict) else {}
    meta_cand = candidate.get("meta", {}) if isinstance(candidate, dict) else {}
    ...
    if pct > threshold_pct:
        return False, (
            f"RRUL p99 regression: baseline={pre:.2f} current={cur:.2f} "
            f"delta=+{pct:.1f}% > {threshold_pct}% (source: {src_pre})"
        )
    return True, f"RRUL p99: {pct:+.1f}% (within +/-{threshold_pct}%) (source: {src_pre})"
```

Adapt this to return `(verdict, reason, downstream_impact)` where verdict is one of `not drift`, `expected staging`, `accidental drift`, or `unknown drift`.

**CLI parser pattern** (`scripts/phase206-gate-check.py` lines 225-240):
```python
def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Phase 206 rollback gate core")
    parser.add_argument("--baseline", required=True)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--soak-ndjson")
    ...
    return parser
```

Keep helper read-only: no deploy, no restart, no RouterOS writes, no source config writes.

---

### Optional tests: `tests/test_phase212_inventory.py` (test, batch)

**Analogs:** `tests/test_phase206_predeploy_gate.py`, `tests/test_check_config.py`, `tests/test_operator_summary.py`

**Subprocess/fixture pattern** (`tests/test_phase206_predeploy_gate.py` lines 18-31, 34-41):
```python
def _run_gate(
    args: list[str], extra_env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[bytes]:
    assert GATE_SCRIPT.exists(), GATE_SCRIPT
    env = {"PATH": "/usr/bin:/bin", "VENV_PY": str(VENV_PY)}
    if extra_env:
        env.update(extra_env)
    return subprocess.run([...], env=env, capture_output=True, timeout=15, check=False)

def _make_candidate(tmp_path: Path, **post_overrides: object) -> Path:
    baseline = json.loads(BASELINE.read_text())
    candidate = copy.deepcopy(baseline)
    ...
    out.write_text(json.dumps(candidate, indent=2))
    return out
```

**Config fixture pattern** (`tests/test_check_config.py` lines 55-110):
```python
def _valid_config_data() -> dict:
    return {
        "wan_name": "test",
        "router": {
            "host": "10.0.0.1",
            "user": "admin",
            "ssh_key": "/tmp/fake_key",
            "transport": "rest",
            "password": "secret",
        },
        ...
    }

def _write_config(tmp_path, config_data: dict) -> str:
    config_path = tmp_path / "test_config.yaml"
    config_path.write_text(yaml.dump(config_data))
    return str(config_path)
```

**Report assertion pattern** (`tests/test_operator_summary.py` lines 17-78):
```python
table = format_operator_summary([("a.json", autorate), ("s.json", steering)])
assert "Service" in table
assert "spectrum" in table
assert "att" in table
assert "steering" in table
assert "DL GREEN/UL GREEN" in table
assert "SPECTRUM_GOOD / GREEN" in table
```

Test only if helper code is added. Required checks: recursive redaction of secret-like keys, drift verdict vocabulary, no mutation command strings, and preservation of proof-relevant non-secret fields.

## Shared Patterns

### Read-only production boundary

**Source:** Phase context decisions and systemd/service analogs.
**Apply to:** All helper commands, evidence captures, and report actions.

Do not include `systemctl restart`, deploy scripts, config writes, RouterOS write operations, or automatic state recovery in Phase 212 execution. If alignment is needed, create an explicit operator approval checkpoint and carry unresolved drift forward without mutation.

### Secret redaction

**Source:** `212-CONTEXT.md` D-08/D-09 and `src/wanctl/config_base.py` YAML parse pattern.
**Apply to:** `config-*.redacted.yaml`, `steering-state.redacted.json`, systemd environment summaries, report excerpts.

Use recursive structured parsing. Redact keys matching `password`, `secret`, `token`, `credential`, `auth`, `key`, or `private`; preserve non-secret proof fields such as WAN name, transport, router host identity, queue names, health/metrics ports, floors/ceilings/setpoints, thresholds, state paths, and cooldowns.

### Health endpoint discovery

**Source:** `configs/spectrum.yaml` lines 7-10, `configs/att.yaml` lines 11-14, `src/wanctl/health_check.py` response fields.
**Apply to:** Autorate health captures and report endpoint table.

Derive endpoints from deployed config before probing. Do not assume loopback. Spectrum repo default is `10.10.110.223:9101`; ATT repo default is `10.10.110.227:9101`; steering must be discovered from deployed config/service facts.

### Drift classification

**Source:** `scripts/phase206-gate-check.py` check functions and Phase 212 D-01/D-02.
**Apply to:** Version, config, endpoint, service, health, and steering-state comparisons.

Each mismatch must include expected value, live value, verdict, evidence path, and downstream impact. Allowed classify-only verdicts: `not drift`, `expected staging`, `accidental drift`, `unknown drift`; use `resolved by approved deployment` only if a separate approved alignment step occurs outside the default audit path.

### Operator-first tables

**Source:** `src/wanctl/operator_summary.py` lines 87-92.
**Apply to:** `212-production-inventory.md` and `212-REPORT.md`.

Use compact tables over prose dumps. Link every row to stable saved evidence artifacts so later phases can cite facts without re-running production probes.

## No Analog Found

No files lacked a usable codebase analog. The optional Phase 212 helper is new by phase number, but existing phase scripts provide the same utility + evidence-transform + test pattern.

## Metadata

**Analog search scope:** `src/wanctl/**/*.py`, `scripts/*.{py,sh}`, `tests/*.py`, `deploy/systemd/*.service`, `configs/*.yaml`, Phase 212 planning artifacts.
**Files scanned:** 100+ Python files from `src/wanctl`, 30+ scripts, 90+ tests, configs, and systemd units.
**Project skills:** No project-local `.claude/skills/` or `.agents/skills/` directories found.
**Pattern extraction date:** 2026-05-27
