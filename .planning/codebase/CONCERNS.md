# Codebase Concerns

**Analysis Date:** 2026-03-10

## Tech Debt

**pyproject.toml version out of sync with actual release:**
- Issue: `pyproject.toml` declares `version = "1.7.0"` but the codebase is at v1.11.0
- Files: `pyproject.toml:3`
- Impact: Any tooling that reads package version (pip show, pip-audit identifiers, etc.) reports stale version. Not a runtime issue.
- Fix approach: Update `version = "1.11.0"` in `pyproject.toml`

**`pexpect` dependency declared but unused in application code:**
- Issue: `pexpect>=4.9.0` is a declared production dependency in `pyproject.toml:11`, but no source file under `src/wanctl/` imports it. Only `fetch_logs_pexpect.py` (a developer utility at project root) imports pexpect.
- Files: `pyproject.toml:11`, `fetch_logs_pexpect.py`
- Impact: Unnecessary install-time dependency for all deployments. Adds ~1MB to Docker images and pip installs.
- Fix approach: Remove from `[project.dependencies]`; optionally add to a dev extras group or remove the root-level utility.

**`subprocess` import retained in `rtt_measurement.py` purely for test patching:**
- Issue: `src/wanctl/rtt_measurement.py:13` imports `subprocess` only so tests can patch `wanctl.rtt_measurement.subprocess`. The module itself never calls subprocess after the icmplib migration (v1.9). The `# noqa: F401` suppression acknowledges this.
- Files: `src/wanctl/rtt_measurement.py:13`
- Impact: Confusing to readers; test patching of a module that doesn't use its patched symbol is fragile.
- Fix approach: Refactor the affected tests to mock `icmplib.ping` directly, then remove the dead import.

**`timeout_total` parameter retained as dead API in `RTTMeasurement`:**
- Issue: `src/wanctl/rtt_measurement.py:105` accepts `timeout_total` but explicitly notes it is "Retained for API compatibility. Not used by icmplib path". The field `self.timeout_total` is stored but never read.
- Files: `src/wanctl/rtt_measurement.py:105,129-130`, `src/wanctl/steering/daemon.py:1946`
- Impact: API surface is misleading; callers pass a value that has no effect.
- Fix approach: Deprecate the parameter with a warning log on use, then remove it in the next major cleanup pass.

**Legacy config loading pattern repeated without abstraction:**
- Issue: Both daemon `Config` classes implement 13-16 `_load_*()` methods with near-identical structure (extract section, get key with default, assign to `self.*`).
- Files: `src/wanctl/autorate_continuous.py:117-486` (13 loaders), `src/wanctl/steering/daemon.py:133-500` (16 loaders)
- Impact: ~100 lines of boilerplate per daemon. Adding a third daemon would require copy-pasting the same pattern again.
- Fix approach: Extract a `BaseConfig` field-declaration DSL (already partially present in `config_validation_utils.py`) so loaders become data rather than code.

**Dockerfile installs outdated and incomplete dependencies:**
- Issue: `docker/Dockerfile:47` installs only `pexpect==4.9.0 PyYAML==6.0.1` via pip. It omits `requests`, `paramiko`, `tabulate`, `icmplib`, and `cryptography` — all required at runtime. The Dockerfile also carries label `version="1.0"` and does not use `pyproject.toml` for dependency resolution.
- Files: `docker/Dockerfile:47`
- Impact: Docker image built from this file will fail at startup when the autorate daemon tries to `import requests`, `import icmplib`, etc. The image is not production-ready without manual dependency installation.
- Fix approach: Replace the bare pip install with `COPY pyproject.toml .` followed by `pip install .` (or `uv sync --no-dev`).

**`deploy_refactored.sh` installs only `pexpect PyYAML` (missing deps):**
- Issue: `scripts/deploy_refactored.sh:63,109` runs `pip3 install --user pexpect PyYAML`. `icmplib`, `requests`, `paramiko`, and `tabulate` are not installed.
- Files: `scripts/deploy_refactored.sh:62-65,106-111`
- Impact: Deployments using this script will be missing critical dependencies. Production containers were patched manually (`sudo pip3 install --break-system-packages icmplib`).
- Fix approach: Align script with `pyproject.toml` dependencies or install via `pip install -e .`.

**`install.sh` VERSION string does not match codebase version:**
- Issue: `scripts/install.sh:20` sets `VERSION="1.4.0"` while the codebase is at v1.11.0.
- Files: `scripts/install.sh:20`
- Impact: Install script reports wrong version to users. Low runtime risk.
- Fix approach: Update to match `pyproject.toml` version (after first fixing pyproject.toml).

## Known Bugs

No confirmed runtime bugs at time of analysis. All known issues from previous milestones are resolved. The previously deferred test `test_wan_zone_in_stored_metrics` (noted in `.planning/milestones/v1.11-phases/61-observability-metrics/deferred-items.md`) now passes.

## Security Considerations

**REST API password stored in `Config` object as plaintext string:**
- Risk: `autorate_continuous.Config._load_router_transport_config()` stores `self.router_password = router.get("password", "")` directly. Env var expansion from `${VAR}` syntax happens later in `RouterOSREST.from_config()`. The raw credential (or the unexpanded `${VAR}` token if not yet expanded) sits in the long-lived config object.
- Files: `src/wanctl/autorate_continuous.py:460`, `src/wanctl/steering/daemon.py:172`, `src/wanctl/routeros_rest.py:141-144`
- Current mitigation: Passwords are not logged. SSH transport uses key authentication. Env var expansion is handled correctly in `routeros_rest.py`.
- Recommendations: Delete `self.router_password` from Config after router client construction so the credential does not persist in memory for the daemon lifetime.

**`urllib3.disable_warnings(InsecureRequestWarning)` is process-wide:**
- Risk: `src/wanctl/routeros_rest.py:107-110` calls `urllib3.disable_warnings(InsecureRequestWarning)` when `verify_ssl=False`. This suppresses the warning process-wide for the daemon lifetime, not just for the one session.
- Files: `src/wanctl/routeros_rest.py:107-110`
- Current mitigation: Default is `verify_ssl=True`. Self-signed certs are common in home router deployments; operators intentionally set `verify_ssl: false`.
- Recommendations: Use `warnings.filterwarnings("ignore", category=InsecureRequestWarning)` scoped to the session rather than the global disable.

**Hardcoded fallback gateway IP `10.10.110.1` in default config:**
- Risk: `src/wanctl/autorate_continuous.py:438` uses `"10.10.110.1"` as the default `fallback_gateway_ip` when the YAML key is absent. This is environment-specific, not a generic safe default.
- Files: `src/wanctl/autorate_continuous.py:438`
- Current mitigation: Production YAML should always override this. The value is only used when ICMP fails as a connectivity fallback.
- Recommendations: Change default to `""` (empty string) and treat absence as "gateway check disabled", forcing operators to provide an explicit value.

**Integration tests contain hardcoded external IP `104.200.21.31`:**
- Risk: Tests in `tests/integration/` target a hardcoded Dallas netperf server. If the server is unreachable or the IP changes, tests fail with no clear error message.
- Files: `tests/integration/test_latency_control.py:41`, `tests/integration/framework/load_generator.py:27`, `tests/integration/framework/latency_collector.py:67`
- Current mitigation: Integration tests skip when `flent`/`netperf`/`fping` are missing; they do not run in CI.
- Recommendations: Parameterize via `WANCTL_TEST_HOST` env var; document that integration tests require local infra.

## Performance Bottlenecks

**Large `run_cycle()` methods are difficult to profile in isolation:**
- Problem: `WANController.run_cycle()` in `src/wanctl/autorate_continuous.py:1381` is 195 lines. `SteeringDaemon.run_cycle()` in `src/wanctl/steering/daemon.py:1515` is 247 lines. These are the hot-path methods called 20 times/second.
- Files: `src/wanctl/autorate_continuous.py:1381`, `src/wanctl/steering/daemon.py:1515`
- Cause: Algorithm complexity is inherent (multi-stage pipelines with early-return paths, PerfTimer wrapping). Protected from refactoring per CLAUDE.md policy.
- Improvement path: Per-subsystem profiling is already instrumented via `PerfTimer`. Use `--profile` flag and `analyze_profiling.py --budget 50` to identify the next bottleneck before any changes.

**OPTM-04 deferred: overall cycle utilization target (~40%) not achieved:**
- Problem: Current production utilization is 60-80% (30-40ms per 50ms cycle). The target of ~40% utilization was set in v1.9 Phase 48 but not achieved after the icmplib optimization.
- Files: `docs/PROFILING.md:335`
- Cause: Deferred pending RRUL router CPU measurement post-icmplib (per `MEMORY.md`).
- Improvement path: Profile under RRUL load, measure router CPU, identify next bottleneck (likely router communication batching per OPTM-02).

## Fragile Areas

**MetricsWriter singleton is test-hostile without explicit reset:**
- Files: `src/wanctl/storage/writer.py:40-56`
- Why fragile: Module-level singleton persists between test functions. Any test that instantiates `MetricsWriter` without calling `MetricsWriter._reset_instance()` in teardown will corrupt singleton state for subsequent tests (wrong `db_path`, stale connection).
- Safe modification: Always use `MetricsWriter._reset_instance()` in test teardown or the `mock_storage` autouse fixture. Never call `MetricsWriter()` in tests without resetting.
- Test coverage: Covered via `_reset_instance()` in test fixtures, but easy to miss when writing new tests targeting the `storage/` subsystem.

**`signal_utils.py` module-level `_shutdown_event` must not be replaced:**
- Files: `src/wanctl/signal_utils.py:40`
- Why fragile: The module-level `threading.Event` is shared across signal handlers and the daemon main loop. Replacing it (e.g., by assigning a new Event in tests) without updating all references causes the main loop to spin or hang.
- Safe modification: Only access via `signal_utils.get_shutdown_event()`. In test teardown, call `signal_utils._shutdown_event.clear()` to reset state.
- Test coverage: `tests/test_autorate_entry_points.py` covers signal handling.

**WAN-aware steering (v1.11) silently disables on misconfiguration:**
- Files: `src/wanctl/steering/daemon.py:293-348`
- Why fragile: The entire `wan_state:` YAML section is optional. Misconfiguring it (invalid types, missing required fields) triggers warn+disable at INFO level rather than an error. An operator adding `wan_state:` with a typo silently runs without WAN awareness.
- Safe modification: Before enabling `wan_state.enabled: true`, run `wanctl-steering --validate-config`. After startup, verify `health.wan_awareness.enabled == true` on the health endpoint (`http://127.0.0.1:9102/health`).
- Test coverage: `tests/test_steering_daemon.py` has comprehensive config validation tests for `wan_state`.

**`flap_detector.check_flapping()` return value is discarded:**
- Files: `src/wanctl/steering/steering_confidence.py:610-611`
- Why fragile: `_ = self.flap_detector.check_flapping(...)` is called only for its side effect on `timer_state`. If a future refactor moves the state mutation out of `check_flapping()`, flap detection breaks silently.
- Safe modification: Do not change the call-site unless auditing exactly what `check_flapping()` mutates.
- Test coverage: `tests/test_steering_confidence.py` covers flap detection behavior.

**State file JSON is an unversioned inter-daemon interface:**
- Files: `src/wanctl/wan_controller_state.py`, `src/wanctl/steering/daemon.py:700-754`
- Why fragile: The steering daemon reads `state["ewma"]["baseline_rtt"]` and `state["congestion"]["dl_state"]` by hardcoded key path. Any rename in `WANControllerState` silently returns `None` to the steering daemon, which falls back to config defaults with a warning.
- Safe modification: Any change to `WANControllerState` field paths requires auditing `BaselineLoader._load_state()` at `steering/daemon.py:700`. The behavioral integration tests in `tests/test_daemon_interaction.py` must also be updated.
- Test coverage: `tests/test_daemon_interaction.py` covers the contract with real file I/O (not mocked).

## Scaling Limits

**SQLite metrics DB may not compact promptly on high-write systems:**
- Current capacity: Downsampled to 4 granularities (raw, 1m, 5m, 1h). 30-day retention. Hourly VACUUM.
- Limit: VACUUM is skipped at startup (watchdog safety). If writes outpace downsampling deletion for extended periods, the DB file may stay large until the hourly maintenance window. At 50ms cycles with 2 daemons + steering, raw write rate is ~60 rows/second.
- Scaling path: Monitor DB file size via health endpoint `disk_space`. Reduce `storage.retention_days` or increase downsampling aggressiveness in YAML if approaching storage limits.

**Log files grow unbounded without logrotate on non-install.sh deployments:**
- Current capacity: `setup_logging()` uses plain `FileHandler` — no built-in rotation.
- Limit: Docker and manual deployments that do not run `install.sh` have no logrotate config. On a 50ms cycle with verbose logging, main log can grow several MB/day.
- Scaling path: Add `RotatingFileHandler` with configurable `maxBytes` and `backupCount` to `src/wanctl/logging_utils.py:setup_logging()`, or document logrotate as a mandatory deployment step.

## Dependencies at Risk

**`pip` CVE-2026-1703 (dev env only):**
- Risk: `pip 25.3` in `.venv` has a known vulnerability. Fixed in pip 26.0.
- Impact: Dev environment only. pip is not a runtime dependency.
- Migration plan: `pip install --upgrade pip` inside the venv.

**`cryptography` CVE-2026-26007 (transitive via paramiko):**
- Risk: `cryptography < 46.0.5` has a known vulnerability. `pyproject.toml:14` now pins `cryptography>=46.0.5`, so new venvs install the fixed version. Production containers running older installs may still have the vulnerable version.
- Impact: SSH transport to RouterOS uses paramiko/cryptography. MITM risk if running old install.
- Migration plan: Run `pip3 show cryptography` on `cake-spectrum` and `cake-att` containers. Upgrade to `>=46.0.5` if not already current.

## Missing Critical Features

**No contract tests for the autorate↔steering state file schema:**
- Problem: Phase 46 (Contract Tests) was deferred in v1.8. There are no tests in the autorate test suite that fail when a key path read by the steering daemon is renamed. The only cross-daemon coverage is `tests/test_daemon_interaction.py` (behavioral, not schema-enforcing).
- Blocks: Silent schema drift — a rename in `WANControllerState` would pass all autorate tests but break steering silently.
- Files: `.planning/ROADMAP.md:97`

**WAN-aware steering has no end-to-end activation validation path:**
- Problem: The `wan_state:` feature (v1.11) ships disabled by default with no automated path to validate it on real hardware before production enablement. Integration tests do not cover WAN zone injection scenarios.
- Blocks: Safe production enablement of `wan_state.enabled: true`. Operators must validate manually via health endpoint and log monitoring.

## Test Coverage Gaps

**Integration tests excluded from CI — live-traffic validation not automated:**
- What's not tested: End-to-end latency control under RRUL load, actual CAKE queue manipulation, real RTT measurement behavior under congestion.
- Files: `tests/integration/test_latency_control.py`, `tests/integration/framework/`
- Risk: An algorithm change that degrades latency control under load passes all unit tests but fails in production.
- Priority: Low (by design — these tests require dedicated hardware/network)

**Docker deployment path is not exercised by any test:**
- What's not tested: `docker build` validity, runtime behavior of the container image, dependency completeness.
- Files: `docker/Dockerfile`, `docker/docker-compose.yml`
- Risk: Dockerfile silently ships with missing dependencies (`icmplib`, `requests`, `paramiko`, `tabulate`) and would fail at import time.
- Priority: Medium — a `docker build` CI step would catch the dependency gap without requiring live infra.

---

*Concerns audit: 2026-03-10*
