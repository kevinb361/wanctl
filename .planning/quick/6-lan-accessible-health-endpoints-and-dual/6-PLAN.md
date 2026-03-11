---
phase: quick-6
plan: 1
type: execute
wave: 1
depends_on: []
files_modified:
  - src/wanctl/steering/daemon.py
  - src/wanctl/dashboard/config.py
  - src/wanctl/dashboard/app.py
  - tests/test_dashboard/test_config.py
  - tests/test_dashboard/test_app.py
autonomous: true
requirements: []
must_haves:
  truths:
    - "Steering health server binds to host/port from YAML config instead of hardcoded 127.0.0.1:9102"
    - "Dashboard supports secondary_autorate_url config and CLI arg"
    - "When secondary_autorate_url is empty, dashboard preserves exact current single-poller behavior"
    - "When secondary_autorate_url is set, WAN 1 data comes from primary and WAN 2 from secondary"
  artifacts:
    - path: "src/wanctl/steering/daemon.py"
      provides: "_load_health_check_config method and config-driven health server bind"
      contains: "_load_health_check_config"
    - path: "src/wanctl/dashboard/config.py"
      provides: "secondary_autorate_url field in DashboardConfig and DEFAULTS"
      contains: "secondary_autorate_url"
    - path: "src/wanctl/dashboard/app.py"
      provides: "Dual-poller mode when secondary URL configured"
      contains: "_secondary_autorate_poller"
  key_links:
    - from: "src/wanctl/steering/daemon.py:_load_specific_fields"
      to: "_load_health_check_config"
      via: "method call in orchestration chain"
    - from: "src/wanctl/steering/daemon.py:run_steering_daemon"
      to: "config.health_check_host, config.health_check_port"
      via: "start_steering_health_server call uses config values"
    - from: "src/wanctl/dashboard/app.py:DashboardApp.__init__"
      to: "EndpointPoller for secondary autorate"
      via: "conditional creation when secondary_autorate_url is non-empty"
---

<objective>
Add config-driven health server binding for steering daemon and dual-WAN autorate polling for the dashboard.

Purpose: Enable LAN-accessible health endpoints (bind to 0.0.0.0 via config) and allow dashboard to poll two separate autorate containers for true dual-WAN monitoring.
Output: Modified steering daemon config, updated dashboard config/app with secondary autorate support.
</objective>

<execution_context>
@./.claude/get-shit-done/workflows/execute-plan.md
@./.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@src/wanctl/steering/daemon.py (SteeringConfig._load_specific_fields at line 495, run_steering_daemon at line 2013)
@src/wanctl/autorate_continuous.py (_load_health_check_config at line 482 — pattern to follow)
@src/wanctl/dashboard/config.py (DashboardConfig, DEFAULTS, load_dashboard_config, apply_cli_overrides)
@src/wanctl/dashboard/app.py (DashboardApp, _poll_autorate, parse_args, action_refresh)
@src/wanctl/dashboard/poller.py (EndpointPoller)
@tests/test_dashboard/test_config.py (existing config tests)
@tests/test_dashboard/test_app.py (existing app/polling tests)

<interfaces>
From src/wanctl/autorate_continuous.py (pattern to replicate):
```python
def _load_health_check_config(self) -> None:
    """Load health check settings with defaults."""
    health = self.data.get("health_check", {})
    self.health_check_enabled = health.get("enabled", True)
    self.health_check_host = health.get("host", "127.0.0.1")
    self.health_check_port = health.get("port", 9101)
```

From src/wanctl/steering/daemon.py (current hardcoded call at line 2013):
```python
health_server = start_steering_health_server(
    host="127.0.0.1",
    port=9102,
    daemon=daemon,
)
```

From src/wanctl/dashboard/config.py:
```python
DEFAULTS: dict = {
    "autorate_url": "http://127.0.0.1:9101",
    "steering_url": "http://127.0.0.1:9102",
    "refresh_interval": 2,
}

@dataclass
class DashboardConfig:
    autorate_url: str = DEFAULTS["autorate_url"]
    steering_url: str = DEFAULTS["steering_url"]
    refresh_interval: int | float = DEFAULTS["refresh_interval"]
    wan_rate_limits: dict[str, dict[str, float]] = field(default_factory=dict)
```

From src/wanctl/dashboard/app.py:
```python
class DashboardApp(App):
    def __init__(self, config: DashboardConfig) -> None:
        self._autorate_poller = EndpointPoller("autorate", config.autorate_url, ...)
        self._steering_poller = EndpointPoller("steering", config.steering_url, ...)

    async def _poll_autorate(self) -> None:
        # Currently routes wans[:2] from single autorate endpoint to wan-1/wan-2
```
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Steering health config + dashboard config/CLI for secondary autorate URL</name>
  <files>src/wanctl/steering/daemon.py, src/wanctl/dashboard/config.py, src/wanctl/dashboard/app.py, tests/test_dashboard/test_config.py</files>
  <action>
**Steering daemon (src/wanctl/steering/daemon.py):**

1. Add `_load_health_check_config()` method to `SteeringConfig` class (after `_load_metrics_config` at ~line 494). Follow exact pattern from autorate_continuous.py:482-487 but with port default `9102`:
```python
def _load_health_check_config(self) -> None:
    """Load health check settings with defaults."""
    health = self.data.get("health_check", {})
    self.health_check_enabled = health.get("enabled", True)
    self.health_check_host = health.get("host", "127.0.0.1")
    self.health_check_port = health.get("port", 9102)
```

2. Add `self._load_health_check_config()` call in `_load_specific_fields()` — place it after `self._load_metrics_config()` at line 526 (end of the method).

3. Update `run_steering_daemon()` at line ~2010-2017: wrap the health server start in a `config.health_check_enabled` guard (matching autorate pattern) and replace hardcoded values:
```python
if config.health_check_enabled:
    try:
        health_server = start_steering_health_server(
            host=config.health_check_host,
            port=config.health_check_port,
            daemon=daemon,
        )
    except Exception as e:
        logger.warning(f"Failed to start health server: {e}")
```

**Dashboard config (src/wanctl/dashboard/config.py):**

1. Add `"secondary_autorate_url": ""` to `DEFAULTS` dict.
2. Add `secondary_autorate_url: str = DEFAULTS["secondary_autorate_url"]` field to `DashboardConfig` dataclass (after `wan_rate_limits`).
3. In `load_dashboard_config()`, add `secondary_autorate_url=data.get("secondary_autorate_url", DEFAULTS["secondary_autorate_url"])` to the DashboardConfig constructor call.
4. In `apply_cli_overrides()`, add `secondary_autorate_url` handling:
```python
secondary_autorate_url=(
    args.secondary_autorate_url
    if getattr(args, "secondary_autorate_url", None) is not None
    else config.secondary_autorate_url
),
```
And pass `wan_rate_limits=config.wan_rate_limits` (already present, no change needed).

**Dashboard CLI (src/wanctl/dashboard/app.py):**

In `parse_args()`, add `--secondary-autorate-url` argument:
```python
parser.add_argument(
    "--secondary-autorate-url",
    default=None,
    help="Secondary autorate health endpoint URL for WAN 2 (default: disabled)",
)
```

**Tests (tests/test_dashboard/test_config.py):**

Add tests to existing classes:
- `TestDefaults.test_defaults_has_secondary_autorate_url`: assert `DEFAULTS["secondary_autorate_url"] == ""`
- `TestLoadDashboardConfig.test_secondary_autorate_url_defaults_to_empty`: load with no config, assert `config.secondary_autorate_url == ""`
- `TestLoadDashboardConfig.test_secondary_autorate_url_loaded_from_yaml`: write YAML with `secondary_autorate_url: "http://10.0.0.2:9101"`, assert loaded correctly
- `TestCliOverrides.test_cli_secondary_autorate_url_overrides_config`: add `secondary_autorate_url="http://override:9101"` to args Namespace, assert override applied
- `TestCliOverrides.test_cli_none_secondary_autorate_url_does_not_override`: ensure None arg does not override config value (add field to existing test's args)
  </action>
  <verify>
    <automated>.venv/bin/pytest tests/test_dashboard/test_config.py -x -v</automated>
  </verify>
  <done>SteeringConfig reads health_check.host/port from YAML with defaults 127.0.0.1:9102. run_steering_daemon uses config values instead of hardcoded. DashboardConfig has secondary_autorate_url field with CLI override support. All config tests pass.</done>
</task>

<task type="auto">
  <name>Task 2: Dashboard dual-poller mode with conditional secondary autorate polling</name>
  <files>src/wanctl/dashboard/app.py, tests/test_dashboard/test_app.py</files>
  <action>
**Dashboard app (src/wanctl/dashboard/app.py):**

1. In `DashboardApp.__init__()`, after `self._steering_poller` creation, add conditional secondary poller:
```python
self._secondary_autorate_poller: EndpointPoller | None = None
if config.secondary_autorate_url:
    self._secondary_autorate_poller = EndpointPoller(
        "autorate-secondary",
        config.secondary_autorate_url,
        normal_interval=config.refresh_interval,
    )
```

2. In `on_mount()`, add secondary polling timer if poller exists:
```python
if self._secondary_autorate_poller is not None:
    self.set_interval(self.config.refresh_interval, self._poll_secondary_autorate)
```

3. Split `_poll_autorate()` into two modes. When `_secondary_autorate_poller is None` (no secondary URL), keep EXACT current behavior — `wans[:2]` routing to `#wan-1`/`#wan-2`/`#spark-wan-1`/`#spark-wan-2`/`#gauge-wan-1`/`#gauge-wan-2`. When `_secondary_autorate_poller is not None`, route only `wans[0]` (first WAN) to `#wan-1`, `#spark-wan-1`, `#gauge-wan-1`. Status bar updates from primary in both modes.

Implementation approach — modify `_poll_autorate` to limit WAN routing when dual mode:
```python
async def _poll_autorate(self) -> None:
    """Poll primary autorate endpoint and route data to WAN panels."""
    if self._client is None:
        return

    data = await self._autorate_poller.poll(self._client)
    wan1 = self.query_one("#wan-1", WanPanelWidget)
    wan2 = self.query_one("#wan-2", WanPanelWidget)

    if data and "wans" in data:
        wans = data["wans"]
        if self._secondary_autorate_poller is not None:
            # Dual mode: primary handles only WAN 1
            self._route_wan_data(wans[0] if wans else None, 1, data)
        else:
            # Single mode: primary handles both WANs (existing behavior)
            for i, wan_data in enumerate(wans[:2]):
                self._route_wan_data(wan_data, i + 1, data)

        status_bar = self.query_one("#status-bar", StatusBarWidget)
        status_bar.update_status(
            version=data.get("version", "?"),
            uptime_seconds=data.get("uptime_seconds", 0),
            disk_status=data.get("disk_space", {}).get("status", "unknown"),
        )
    else:
        wan1.update_from_data(None, last_seen=self._autorate_poller.last_seen)
        if self._secondary_autorate_poller is None:
            wan2.update_from_data(None, last_seen=self._autorate_poller.last_seen)
```

4. Extract `_route_wan_data` helper method (reduces duplication between primary and secondary poll):
```python
def _route_wan_data(self, wan_data: dict | None, wan_num: int, full_response: dict | None) -> None:
    """Route WAN data to panel, sparkline, and gauge for the given WAN number."""
    wan_widget = self.query_one(f"#wan-{wan_num}", WanPanelWidget)
    if wan_data is None:
        wan_widget.update_from_data(None)
        return

    status = full_response.get("status") if full_response else None
    last_seen = self._autorate_poller.last_seen if wan_num == 1 else (
        self._secondary_autorate_poller.last_seen if self._secondary_autorate_poller else self._autorate_poller.last_seen
    )
    wan_widget.update_from_data(wan_data, status=status, last_seen=last_seen)

    dl_rate = wan_data.get("download", {}).get("current_rate_mbps", 0)
    ul_rate = wan_data.get("upload", {}).get("current_rate_mbps", 0)
    baseline_rtt = wan_data.get("baseline_rtt_ms", 0)
    load_rtt = wan_data.get("load_rtt_ms", 0)
    rtt_delta = max(0, load_rtt - baseline_rtt)

    spark = self.query_one(f"#spark-wan-{wan_num}", SparklinePanelWidget)
    spark.append_data(dl_rate, ul_rate, rtt_delta)

    cycle_budget = wan_data.get("cycle_budget")
    if cycle_budget is not None:
        gauge = self.query_one(f"#gauge-wan-{wan_num}", CycleBudgetGaugeWidget)
        gauge.update_utilization(cycle_budget.get("utilization_pct", 0))
```

5. Add `_poll_secondary_autorate()` method:
```python
async def _poll_secondary_autorate(self) -> None:
    """Poll secondary autorate endpoint and route data to WAN 2 panel."""
    if self._client is None or self._secondary_autorate_poller is None:
        return

    data = await self._secondary_autorate_poller.poll(self._client)
    wan2 = self.query_one("#wan-2", WanPanelWidget)

    if data and "wans" in data:
        wans = data["wans"]
        if wans:
            self._route_wan_data(wans[0], 2, data)
    else:
        wan2.update_from_data(None, last_seen=self._secondary_autorate_poller.last_seen)
```

6. Update `action_refresh()` to also poll secondary:
```python
async def action_refresh(self) -> None:
    """Handle 'r' keybinding: force immediate refresh of all endpoints."""
    await self._poll_autorate()
    if self._secondary_autorate_poller is not None:
        await self._poll_secondary_autorate()
    await self._poll_steering()
```

**Tests (tests/test_dashboard/test_app.py):**

Add new test class `TestDashboardAppDualPollerMode`:

- `test_no_secondary_url_preserves_single_poller_behavior`: Create DashboardApp with default config (empty secondary URL). Mock autorate poller with 2-WAN response. Call `_poll_autorate()`. Assert both wan-1 and wan-2 get data from the single response. This confirms zero regression.

- `test_secondary_url_creates_secondary_poller`: Create DashboardApp with `secondary_autorate_url="http://10.0.0.2:9101"`. Assert `app._secondary_autorate_poller is not None` and its base_url is correct.

- `test_no_secondary_url_has_none_secondary_poller`: Create DashboardApp with default config. Assert `app._secondary_autorate_poller is None`.

- `test_dual_mode_primary_only_routes_wan1`: Create DashboardApp with secondary URL set. Mock primary poller with 2-WAN response. Call `_poll_autorate()`. Assert wan-1 gets data. Assert wan-2 does NOT get updated from primary (its renderer._data stays None before secondary poll).

- `test_dual_mode_secondary_routes_wan2`: Create DashboardApp with secondary URL. Mock secondary poller with 1-WAN response. Call `_poll_secondary_autorate()`. Assert wan-2 gets data from secondary response.

- `test_action_refresh_calls_secondary_poll_when_configured`: Create DashboardApp with secondary URL. Mock all three pollers. Call `action_refresh()`. Assert secondary poller's poll was called.

- `test_action_refresh_skips_secondary_when_not_configured`: Create DashboardApp without secondary URL. Mock autorate+steering pollers. Call `action_refresh()`. Assert no error (secondary is None, skipped).

Update existing `TestDashboardAppPolling.test_cli_none_values_do_not_override` test's args Namespace to include `secondary_autorate_url=None` to avoid AttributeError from the new `apply_cli_overrides` code.
  </action>
  <verify>
    <automated>.venv/bin/pytest tests/test_dashboard/test_app.py tests/test_dashboard/test_config.py -x -v</automated>
  </verify>
  <done>Dashboard creates secondary EndpointPoller when secondary_autorate_url is non-empty. In dual mode, primary polls WAN 1 only, secondary polls WAN 2. In single mode (empty URL), exact current behavior preserved (wans[:2] from single endpoint). action_refresh polls all configured endpoints. All tests pass.</done>
</task>

</tasks>

<verification>
Run full dashboard test suite and ruff check:

```bash
.venv/bin/pytest tests/test_dashboard/ -x -v
.venv/bin/ruff check src/wanctl/steering/daemon.py src/wanctl/dashboard/config.py src/wanctl/dashboard/app.py
.venv/bin/ruff check tests/test_dashboard/
```
</verification>

<success_criteria>
- Steering daemon reads health_check.host and health_check.port from YAML config with defaults 127.0.0.1/9102
- Steering daemon health server start uses config values (no hardcoded host/port)
- Dashboard DEFAULTS includes secondary_autorate_url: ""
- DashboardConfig has secondary_autorate_url field
- --secondary-autorate-url CLI arg works with apply_cli_overrides
- Empty secondary URL preserves exact current single-poller behavior
- Non-empty secondary URL activates dual-poller mode (primary -> WAN 1, secondary -> WAN 2)
- All existing dashboard tests pass unchanged (except Namespace additions for new field)
- New tests cover config defaults, YAML loading, CLI override, dual-poller routing
</success_criteria>

<output>
After completion, create `.planning/quick/6-lan-accessible-health-endpoints-and-dual/6-SUMMARY.md`
</output>
