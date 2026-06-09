# Phase 230: soak-monitor ATT Coverage - Research

**Researched:** 2026-06-09
**Domain:** Bash operational tooling (`soak-monitor.sh`) — mode detection + journal error-scan for cake-autorate external-controller WANs. No external libraries.
**Confidence:** HIGH (entire surface is one in-repo bash script + the ATT unit files; verified by direct reads, not training data)

## Summary

This phase fixes a **monitoring blind spot**, not a deploy or controller change. After the 2026-06-08 migration, both WANs run cake-autorate external-controller mode and the native `wanctl@{wan}.service` units are disabled. `scripts/soak-monitor.sh` was retrofitted for the **Spectrum** cake-autorate trial only — it has a Spectrum-specific bridge-state fallback, a Spectrum-named mode detector (`is_spectrum_cake_trial_active`), and a Spectrum-only error-scan branch. For ATT it still scans the **disabled** `wanctl@att.service`, so any error in the live ATT units (`cake-autorate-att.service`, `cake-autorate-att-state-bridge.service`, the silicom watchdog) is **invisible** to the 1h error scan. That is exactly MON-01.

The good news, verified directly: the ATT state-bridge **already serves a real `/health` endpoint on `10.10.110.227:9101`** (the shared bridge script runs a `ThreadingHTTPServer`; the ATT unit sets `CAKE_AUTORATE_BRIDGE_HEALTH_HOST=10.10.110.227`). The existing `check_target` curl path already hits that IP for the `att` TARGETS row — so ATT's health *display* already works via the live bridge endpoint, with no Spectrum-style `sudo -n python3` fallback needed. The actual gap is narrower than "rebuild ATT monitoring": it is (a) the **error-scan unit set** for ATT, and (b) **de-hardcoding mode detection** so ATT is treated as external-controller mode at parity with Spectrum. This keeps the change small and observability-only — no controller path, satisfying SAFE-14.

**Primary recommendation:** Generalize the Spectrum-only `is_spectrum_cake_trial_active` + error-scan branches into a per-WAN, parameterized "external-controller mode" detection that maps each WAN to its live unit set (`cake-autorate-<wan>.service`, `cake-autorate-<wan>-state-bridge.service`, plus the silicom watchdog for ATT). Drive the unit names from a small per-WAN table instead of the literal `spectrum`/`att` strings. Add a focused test that asserts the script references the live ATT units and does **not** scan `wanctl@att.service` in external mode, and demonstrate a real run surfacing a representative ATT-unit error (success criterion 3). Mirror Spectrum's existing transition handling — do not invent a new monitoring model.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| WAN deployment-mode detection (native vs external cake-autorate) | `soak-monitor.sh` (ops tooling) | Target host (`systemctl is-active` over ssh) | The script decides which units are authoritative for each WAN by probing live `systemctl` state |
| ATT error-scan over live units | `soak-monitor.sh` `check_errors()` | Target host (read-only `journalctl -p err`) | Pure read-only journal scan; owns the unit-arg list per WAN |
| ATT health display | Already working — ATT bridge `/health` on `:9101` | `check_target()` curl path | Bridge serves a real endpoint; no Spectrum-style state fallback required for ATT |
| Regression proof (references live units, not `wanctl@att`) | Repo test (`tests/`) | — | Static text assertions over `soak-monitor.sh`; no host contact |
| SAFE-14 controller-path zero-diff | Boundary verification (git diff) | — | Phase touches only `scripts/soak-monitor.sh` + a test; controller `.py` untouched |

**Key insight:** This is observability-only. The only production interaction is **read-only** (`systemctl is-active`, `journalctl -p err`, `curl /health`) — all already used by the script today. No mutation, no controller edits.

## Standard Stack

No external libraries. Stack is the existing repo toolchain.

### Core
| Tool | Version | Purpose | Why Standard |
|------|---------|---------|--------------|
| bash | system | `soak-monitor.sh` itself | The script is the unit of work; mirror its existing patterns [VERIFIED: scripts/soak-monitor.sh] |
| shellcheck | 0.9.0 | lint gate for the bash change | Already installed; current script passes `shellcheck -S error` clean (exit 0) [VERIFIED: ran locally 2026-06-09] |
| pytest | repo-pinned | static regression test over the script text | Existing framework; `test_spectrum_cake_autorate_artifacts.py` shows the "read a repo file, assert substrings" pattern [VERIFIED: pyproject.toml L163-165] |
| ssh / systemctl / journalctl / curl | system | read-only live observation | All already used by `soak-monitor.sh` today [VERIFIED: scripts/soak-monitor.sh] |

**Installation:** None. **Package Legitimacy Audit is N/A** — this phase installs zero external packages.

### Pytest config note
`addopts = "--cov-config=pyproject.toml --timeout=30 -m 'not integration'"` [VERIFIED: 229-RESEARCH L42, pyproject.toml L164]. A new soak-monitor regression test is a pure on-disk text-assertion test (read `scripts/soak-monitor.sh`, assert/deny substrings) — stays in the default non-integration suite, no host contact, well under the 30s timeout. `bats` is **not** installed (`command -v bats` empty) — do not introduce a new bash-test framework; use pytest + `subprocess`/text reads like the existing repo tests, or shellcheck.

## Package Legitimacy Audit

**N/A — this phase installs no external packages.** All work uses bash, shellcheck (already installed), pytest, and read-only ssh tooling already present. slopcheck gate not applicable.

## Architecture Patterns

### System Architecture Diagram

```
                       soak-monitor.sh (ops tooling, dev box)
                                  │
        ┌─────────────────────────┴──────────────────────────┐
        │  per-WAN loop over TARGETS[]                         │
        │  ssh kevin@10.10.110.223 (cake-shaper)              │
        └─────────────────────────┬──────────────────────────┘
                                  │
        ┌──────────── mode detection (per WAN) ───────────────┐
        │  systemctl is-active cake-autorate-<wan>.service ?  │
        │  systemctl is-active wanctl@<wan>.service ?         │
        │     external mode  ◄── cake-autorate active &       │
        │                        wanctl@<wan> inactive        │
        └─────────────────────────┬──────────────────────────┘
                 ┌────────────────┴───────────────────┐
        HEALTH DISPLAY                          ERROR SCAN (the gap)
        curl http://<health_ip>:9101/health     journalctl -p err --since 1h
          spectrum: bridge endpoint OR             external mode units:
                    sudo -n python3 fallback         cake-autorate-<wan>.service
          att:      bridge endpoint (works today)    cake-autorate-<wan>-state-bridge.service
                                                     + silicom watchdog (att only)
                                                   native mode unit (legacy):
                                                     wanctl@<wan>.service   ◄── ATT WRONGLY USES THIS TODAY
                 └────────────────┬───────────────────┘
                                  ▼
                   formatted table / --json output
                   + summary "Service error scan (1h)"
```

### Pattern 1: Generalize Spectrum-only mode detection into a per-WAN external-mode predicate
**What:** Replace/extend `is_spectrum_cake_trial_active()` (L275-280) with a WAN-parameterized predicate.
**Current (Spectrum-hardcoded) [VERIFIED: scripts/soak-monitor.sh L275-280]:**
```bash
is_spectrum_cake_trial_active() {
    local ssh_target=$1
    ssh ... 'test "$(systemctl is-active cake-autorate-spectrum.service 2>/dev/null)" = active \
             && test "$(systemctl is-active wanctl@spectrum.service 2>/dev/null)" != active'
}
```
**Target shape:**
```bash
# external cake-autorate mode = cake-autorate-<wan> active AND wanctl@<wan> not active
is_external_cake_mode() {
    local ssh_target=$1 wan=$2
    ssh ... "test \"\$(systemctl is-active cake-autorate-${wan}.service 2>/dev/null)\" = active \
             && test \"\$(systemctl is-active wanctl@${wan}.service 2>/dev/null)\" != active"
}
```
**When to use:** Always — this is MON-02 ("no Spectrum-only hardcoding in mode detection"). Keep a thin `is_spectrum_cake_trial_active` wrapper only if other call sites depend on the name; otherwise update all 3 call sites (L327, L340, L400/L418).

### Pattern 2: Per-WAN live-unit map drives the error scan
**What:** A WAN→units mapping so `check_errors` scans the live units when in external mode. ATT in external mode must scan its three live units, never `wanctl@att.service`.
**The live ATT unit set [VERIFIED: deploy/systemd/*.service]:**
- `cake-autorate-att.service`
- `cake-autorate-att-state-bridge.service`
- `silicom-bypass-watchdog-cake-autorate-att.service` *(ATT-only; no Spectrum sibling — see Pitfall 2)*

Spectrum external-mode set (already coded, for reference):
- `cake-autorate-spectrum.service`, `cake-autorate-spectrum-state-bridge.service` *(no silicom watchdog)*

**Recommended approach:** a small bash helper returning the unit list for a WAN+mode:
```bash
external_units_for() {
    local wan=$1
    case "$wan" in
        att) echo "cake-autorate-att.service cake-autorate-att-state-bridge.service silicom-bypass-watchdog-cake-autorate-att.service" ;;
        *)   echo "cake-autorate-${wan}.service cake-autorate-${wan}-state-bridge.service" ;;
    esac
}
```
Then per-WAN error scan (replaces the Spectrum-only branch at L327-331 / L340-344):
```bash
if is_external_cake_mode "$ssh_target" "$wan_name"; then
    errors=$(check_errors "$ssh_target" $(external_units_for "$wan_name"))
else
    errors=$(check_errors "$ssh_target" "wanctl@${wan_name}.service")
fi
```
This is the MON-01 fix.

### Pattern 3: Summary / `--json` service-group scan must include ATT live units
**What:** The bottom-of-run aggregate scan (L398-432 non-json, L398-413 json) currently builds a Spectrum-trial-only branch and otherwise falls back to `SERVICE_UNITS` (which hardcodes `wanctl@att.service`, L14-18).
**Fix:** Build the aggregate unit set by iterating WANs through `is_external_cake_mode` + `external_units_for`, plus `steering.service`. Drop the `SERVICE_UNITS` literal `wanctl@att.service` entry for the external-mode case (keep a native-mode fallback for completeness). Keep `steering.service` always (it runs in both modes per CLAUDE.md service model).

### Pattern 4: Regression test asserts live-unit coverage (success criterion 3 evidence)
**What:** `tests/test_soak_monitor_att_coverage.py` — static text assertions over `scripts/soak-monitor.sh`:
1. Script references `cake-autorate-att.service` and `cake-autorate-att-state-bridge.service`.
2. Script references the silicom watchdog unit OR derives it via the att branch of `external_units_for`.
3. Mode detection is **not** Spectrum-hardcoded — assert a generalized predicate exists (e.g., `is_external_cake_mode` present) OR that `att` appears in an external-mode code path (negative: ATT error scan is not unconditionally `wanctl@att.service`).
4. (Optional) `shellcheck -S error scripts/soak-monitor.sh` passes via `subprocess` — current script passes clean, so this guards the edit. Gate on `shutil.which("shellcheck")` so CI without shellcheck skips, not fails.
**Source template:** `tests/test_spectrum_cake_autorate_artifacts.py::test_deploy_script_has_external_spectrum_mode` (read file → assert substrings) [VERIFIED: L29-35].

### Anti-Patterns to Avoid
- **Rebuilding ATT health acquisition:** Not needed. ATT bridge already serves `/health` on `:9101`; `check_target` already curls it. Do **not** add a Spectrum-style `sudo -n python3` ATT state fallback unless the ATT bridge endpoint is found unreachable in practice (it shouldn't be — bridge is the live health source).
- **Generic `$wan` symmetry refactor across the whole script:** Out of scope per REQUIREMENTS.md Out-of-Scope table. Parameterize only as far as MON-01/02 require — the error-scan unit set + mode predicate. Do not collapse the entire script into a generic engine.
- **Touching the controller path:** SAFE-14. This phase edits `scripts/soak-monitor.sh` + a test only. No `.py` controller edits.
- **Mutating anything on live hosts:** All probes stay read-only (`is-active`, `journalctl -p err`, `curl /health`). No `systemctl start/stop`, no writes.
- **Dropping the Spectrum bridge-state fallback:** Keep `check_spectrum_cake_autorate_state` (L56-182) — it is Spectrum-specific by design (its `/health` may be down during certain trials). Generalizing it to ATT is unnecessary scope; ATT's bridge endpoint is live.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Bash unit testing | Introduce `bats` | pytest reading the script text + `subprocess` for shellcheck | `bats` not installed; repo convention is pytest static assertions (`test_spectrum_cake_autorate_artifacts.py`) |
| Mode detection | New systemd-introspection daemon | `systemctl is-active` over ssh (already in the script) | Existing, read-only, proven pattern (L275-280) |
| ATT health acquisition | New ATT state-fetch python over ssh | Existing `curl http://10.10.110.227:9101/health` (ATT bridge endpoint) | Bridge already serves it; `check_target` already calls it |
| Error scan | New journal parser | Existing `check_errors()` (L283-297) with the corrected unit list | Already filters `-- No entries --`, handles `-p err`, 1h window |
| Controller-path boundary proof | New invariant checker | `check-safe07-source-diff.sh`-style git protected-path diff vs baseline | SAFE-07..13 precedent; baseline `87980bdf` from Phase 229 [VERIFIED: STATE 229-03] |

**Key insight:** The only thing being *built* is a per-WAN unit mapping + a generalized mode predicate, plus one static test. Everything else is reusing functions already in the script.

## Runtime State Inventory

> This is an ops-tooling edit, not a rename/migration. But the script embeds runtime assumptions about which units are authoritative — those are the "state" to correct.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None. soak-monitor reads, never writes. No DB/state files mutated. | None. |
| Live service config | The **disabled** `wanctl@att.service` is hardcoded as ATT's scan target (L14-18 `SERVICE_UNITS`, L330/343/404/422 fallback). Live ATT runs `cake-autorate-att*` + silicom watchdog. | Code edit: map ATT external mode → live units. This IS the MON-01 fix. |
| OS-registered state | systemd units on cake-shaper: `cake-autorate-att.service`, `-state-bridge.service`, `silicom-bypass-watchdog-cake-autorate-att.service` enabled & active; `wanctl@att.service` disabled. | None to change on host (read-only). The script must *observe* the right ones. |
| Secrets/env vars | None referenced by soak-monitor. Health IPs (`10.10.110.223/.227`) and SSH target are inline literals — already committed, public-exposure unchanged. | None. |
| Build artifacts | None. Bash script, no build. | None. |

**The canonical question — what runtime state still has stale assumptions after the edit?** Only the hardcoded `wanctl@att.service` references inside `soak-monitor.sh`. Replacing them with the per-WAN live-unit map closes the loop. No data migration; pure code edit.

## Common Pitfalls

### Pitfall 1: ATT health already works — don't mistake the gap for "ATT monitoring is broken"
**What goes wrong:** Assuming ATT needs the full Spectrum treatment (bridge-state `sudo -n python3` fallback + new health acquisition). It does not. The `att` TARGETS row (L12, `health_ip=10.10.110.227`) already curls the live ATT bridge `/health` endpoint, which the shared bridge serves (`ThreadingHTTPServer`, `CAKE_AUTORATE_BRIDGE_HEALTH_HOST=10.10.110.227`) [VERIFIED: bridge script L13/29-30/298-320, att bridge unit L15].
**Why it happens:** The Spectrum path has a big visible `sudo -n python3` fallback block (L56-182); pattern-matching suggests ATT needs the same.
**How to avoid:** Scope the fix to **error-scan unit set + mode detection**. Health display for ATT is already correct. Verify by running `soak-monitor.sh --json` and confirming the `att` row returns a real bridge payload (`"source":"cake-autorate-state-bridge"`).
**Warning sign:** A plan that adds a `check_att_cake_autorate_state()` mirror of the 130-line Spectrum block is over-scoped.

### Pitfall 2: The silicom watchdog is ATT-only — Spectrum has no sibling
**What goes wrong:** Building a symmetric WAN→units map that assumes both WANs have the same unit shape. ATT's live set includes `silicom-bypass-watchdog-cake-autorate-att.service`; Spectrum has no equivalent [VERIFIED: 229-RESEARCH Pitfall 1; only ATT watchdog exists in `deploy/systemd/`].
**Why it happens:** ATT runs on a Silicom bypass NIC (VDSL2 path); Spectrum (DOCSIS) does not.
**How to avoid:** The `external_units_for` helper must special-case ATT to append the watchdog (see Pattern 2). An ATT error in the watchdog unit is exactly the kind of failure MON-01 wants visible — include it in the scan.
**Warning sign:** A generic `cake-autorate-${wan}*` glob that silently omits the watchdog.

### Pitfall 3: `is_spectrum_cake_trial_active` is called in 3+ places — change all of them
**What goes wrong:** Renaming/generalizing the predicate but leaving stale Spectrum-only call sites, so ATT still falls through to the `wanctl@att.service` branch.
**Call sites [VERIFIED: scripts/soak-monitor.sh]:** L327 (json per-WAN error branch), L340 (table per-WAN error branch), L400 & L418 (aggregate summary scan, both hardcoded `kevin@10.10.110.223` + Spectrum units).
**How to avoid:** Audit every `is_spectrum_cake_trial_active` and every literal `wanctl@att.service` / `cake-autorate-spectrum` occurrence. The aggregate scan (L398-432) currently builds a Spectrum-trial-vs-`SERVICE_UNITS` binary that does not consider ATT external mode at all — it must iterate WANs.
**Warning sign:** `grep -n 'wanctl@att' scripts/soak-monitor.sh` returns matches after the edit (other than an intentional native-mode fallback).

### Pitfall 4: SAFE-14 boundary diff must stay empty — phase is bash + test only
**What goes wrong:** Scope creep into controller `.py` (e.g., "while I'm here, tweak the bridge health payload").
**How to avoid:** Confine edits to `scripts/soak-monitor.sh` and `tests/test_soak_monitor_att_coverage.py`. Run the SAFE-14 git-diff gate at the boundary against baseline `87980bdf` (Phase 229's pinned last docs/planning-only commit) [VERIFIED: STATE 229-03; `git rev-parse 87980bdf` resolves]. Protected set per Decision 227-04 includes `wan_controller_state.py`.
**Warning sign:** `git diff --stat 87980bdf -- src/wanctl/...` is non-empty.

### Pitfall 5: Success criterion 3 wants a *real run* surfacing a representative ATT error
**What goes wrong:** Proving the fix only via the static test, never demonstrating a live run that would have missed an ATT error pre-fix.
**How to avoid:** Plan an evidence step: with the fix, run `soak-monitor.sh --json` (or non-json) and show the ATT error count now reflects the `cake-autorate-att*`/watchdog journal. To make it representative without mutating production, either (a) capture a window where a benign ATT-unit journal `err` already exists, or (b) demonstrate the *unit set* the scan now targets via `--json` units list, contrasted with the pre-fix `wanctl@att.service`-only scan. Per MEMORY/USER.md, any live probe is read-only; if `sudo -n`/journal read is denied, hand Kevin a `! <command>`. Do **not** inject a fault into a live ATT unit.
**Warning sign:** No evidence artifact showing the before/after scan target difference.

## Code Examples

### Generalized external-mode predicate (replaces L275-280)
```bash
# Source: generalize scripts/soak-monitor.sh L275-280 [VERIFIED]
# external cake-autorate mode = cake-autorate-<wan> active AND wanctl@<wan> inactive
is_external_cake_mode() {
    local ssh_target=$1 wan=$2
    ssh -o ConnectTimeout=5 -o BatchMode=yes "$ssh_target" \
        "test \"\$(systemctl is-active cake-autorate-${wan}.service 2>/dev/null)\" = active \
         && test \"\$(systemctl is-active wanctl@${wan}.service 2>/dev/null)\" != active" \
        >/dev/null 2>&1
}
```

### Per-WAN error scan (replaces the Spectrum-only branches at L327/L340)
```bash
# Source: generalize scripts/soak-monitor.sh L283-297 + L327-331 [VERIFIED]
external_units_for() {
    case "$1" in
        att) echo "cake-autorate-att.service cake-autorate-att-state-bridge.service silicom-bypass-watchdog-cake-autorate-att.service" ;;
        *)   echo "cake-autorate-$1.service cake-autorate-$1-state-bridge.service" ;;
    esac
}

if is_external_cake_mode "$ssh_target" "$wan_name"; then
    errors=$(check_errors "$ssh_target" $(external_units_for "$wan_name"))
else
    errors=$(check_errors "$ssh_target" "wanctl@${wan_name}.service")
fi
```

### Regression test (mirror of the Spectrum artifact test pattern)
```python
# Source: tests/test_spectrum_cake_autorate_artifacts.py L29-35 pattern [VERIFIED]
import shutil, subprocess
from pathlib import Path

SOAK = Path(__file__).resolve().parents[1] / "scripts" / "soak-monitor.sh"

def test_soak_monitor_scans_live_att_units() -> None:
    text = SOAK.read_text(encoding="utf-8")
    assert "cake-autorate-att.service" in text
    assert "cake-autorate-att-state-bridge.service" in text
    assert "silicom-bypass-watchdog-cake-autorate-att.service" in text

def test_soak_monitor_mode_detection_not_spectrum_hardcoded() -> None:
    text = SOAK.read_text(encoding="utf-8")
    # generalized predicate exists (MON-02)
    assert "is_external_cake_mode" in text

def test_soak_monitor_shellcheck_clean() -> None:
    if not shutil.which("shellcheck"):
        import pytest; pytest.skip("shellcheck not installed")
    r = subprocess.run(["shellcheck", "-S", "error", str(SOAK)], capture_output=True)
    assert r.returncode == 0, r.stdout.decode() + r.stderr.decode()
```

### SAFE-14 controller-path zero-diff boundary check
```bash
# Source pattern: scripts/check-safe07-source-diff.sh [VERIFIED via 229-RESEARCH]
# Baseline: 87980bdf (Phase 229 pinned last docs/planning-only commit) [VERIFIED: git rev-parse resolves]
git diff --stat 87980bdf -- \
  src/wanctl/wan_controller.py src/wanctl/wan_controller_state.py \
  src/wanctl/queue_controller.py src/wanctl/cake_signal.py \
  src/wanctl/backends/ src/wanctl/alert_engine.py src/wanctl/fusion_healer.py
# MUST be empty at the phase boundary. (Planner may re-pin baseline to the 230-start commit.)
```

## State of the Art

Project-internal only — no external ecosystem.

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| soak-monitor scans `wanctl@{spectrum,att}.service` (native controllers) | Spectrum retrofitted to detect cake-autorate trial + scan `cake-autorate-spectrum*`; ATT left on disabled `wanctl@att.service` | Spectrum trial era (`aaa576bb`, then `fc47a0c`) | ATT error-scan blind spot — this phase closes it |
| Spectrum-only `is_spectrum_cake_trial_active` mode gate | Per-WAN `is_external_cake_mode` predicate | This phase | ATT handled at parity (MON-02) |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | ATT `/health` endpoint on `10.10.110.227:9101` is reachable in the running deployment, so no ATT state-fallback block is needed | Pitfall 1 | If the ATT bridge endpoint is actually down in practice, the `att` health row reads UNREACHABLE and a (smaller) bridge-state fallback may be wanted — verify with a live read-only `--json` run before finalizing scope |
| A2 | The silicom watchdog unit should be **included** in the ATT error scan (an err there is operationally meaningful) | Pattern 2 / Pitfall 2 | If operator considers the watchdog out of soak scope, exclude it — trivial one-line change |
| A3 | SAFE-14 baseline for this phase = `87980bdf` (or the 230-start commit); planner pins exact ref per SAFE-07..13 precedent | Pitfall 4 / Code Examples | Wrong baseline gives a misleading diff |
| A4 | `steering.service` runs in both modes and should remain in the aggregate scan | Pattern 3 | If steering is mode-gated differently, the aggregate set needs adjusting (low risk — CLAUDE.md says steering daemon runs in both modes) |

## Open Questions

1. **Should mode detection be probed once per WAN or cached?** The script probes `systemctl is-active` per call site; generalizing may add ssh round-trips. Recommendation: probe once per WAN per run, reuse the result across health + error + summary (minor refactor, fewer ssh calls). Not required for correctness.
2. **Native-mode fallback retention.** Keep a `wanctl@<wan>.service` scan branch for when a WAN is *not* in external mode (e.g., post-rollback)? Recommendation: yes — keep the `else` branch so soak-monitor still works if a WAN is rolled back to native (supports Phase 231 SOAK-02 rollback verification). Cheap and forward-useful.
3. **Representative ATT error evidence (criterion 3).** Capture an existing benign journal `err`, or demonstrate via the `--json` `units` list contrast? Recommendation: the `--json` before/after unit-set contrast is the cleanest no-mutation proof; supplement with any naturally-occurring ATT `err` if present in the window.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| shellcheck | lint gate + test | ✓ | 0.9.0 | test skips if absent (`shutil.which`) |
| pytest (repo venv) | regression test | ✓ | repo-pinned | — |
| bash | the script | ✓ | system | — |
| cake-shaper ssh + read-only `systemctl is-active`/`journalctl -p err` | live run / criterion-3 evidence | ✗ verify at runtime | — | If `sudo -n`/journal read denied: per MEMORY hand Kevin a `! <command>`; static test still proves the fix |
| bats | — | ✗ (not installed) | — | Don't use it — pytest is the repo convention |

**Missing dependencies with no fallback:** none for the code+test work (fully offline). Live evidence (criterion 3) is runtime-gated on read-only cake-shaper access.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (repo-pinned) [VERIFIED: pyproject.toml L163] |
| Config file | `pyproject.toml` `[tool.pytest.ini_options]` (L163-165) |
| Quick run command | `.venv/bin/pytest tests/test_soak_monitor_att_coverage.py -v` |
| Full suite command | `.venv/bin/pytest tests/ -v` |
| Lint gate | `shellcheck -S error scripts/soak-monitor.sh` (currently exit 0) |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| MON-01 | error-scan covers live ATT units, not disabled `wanctl@att.service` | unit (script text) | `.venv/bin/pytest tests/test_soak_monitor_att_coverage.py::test_soak_monitor_scans_live_att_units -x` | ❌ Wave 0 (new test) |
| MON-01 | live demonstration error scan reads ATT units | manual/evidence (read-only run) | `./scripts/soak-monitor.sh --json` then inspect ATT `units`/`errors_1h` | ❌ Wave 0 (evidence step) |
| MON-02 | mode detection not Spectrum-hardcoded; ATT external mode at parity | unit (script text) | `.venv/bin/pytest tests/test_soak_monitor_att_coverage.py::test_soak_monitor_mode_detection_not_spectrum_hardcoded -x` | ❌ Wave 0 (new test) |
| (guard) | script stays shellcheck-clean after edit | unit (subprocess) | `.venv/bin/pytest tests/test_soak_monitor_att_coverage.py::test_soak_monitor_shellcheck_clean -x` | ❌ Wave 0 |
| SAFE-14 | controller-path zero-diff at boundary | git diff gate | `git diff --stat 87980bdf -- src/wanctl/{wan_controller,wan_controller_state,queue_controller,cake_signal,alert_engine,fusion_healer}.py src/wanctl/backends/` (empty) | ✓ pattern exists (`check-safe07-source-diff.sh`) |

### Sampling Rate
- **Per task commit:** `.venv/bin/pytest tests/test_soak_monitor_att_coverage.py -q` + `shellcheck -S error scripts/soak-monitor.sh`
- **Per wave merge:** focused slice + full `shellcheck`; optional read-only `soak-monitor.sh --json` smoke
- **Phase gate:** full `.venv/bin/pytest tests/` green + SAFE-14 git-diff empty + criterion-3 evidence (read-only live run showing ATT live-unit scan) recorded before `/gsd:verify-work`.

### Wave 0 Gaps
- [ ] `tests/test_soak_monitor_att_coverage.py` — covers MON-01, MON-02, shellcheck guard. Mirror the `test_spectrum_cake_autorate_artifacts.py` read-and-assert pattern.
- [ ] `is_external_cake_mode` + `external_units_for` (or equivalent) in `scripts/soak-monitor.sh` — the implementation the test asserts against.
- [ ] Criterion-3 evidence artifact (read-only `--json` before/after unit-set contrast). Document in a phase evidence note.
- Framework install: none — pytest + shellcheck already present.

## Security Domain

> `security_enforcement` not explicitly `false`, so included. Surface is host observation, not app input.

### Applicable ASVS Categories
| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | yes (host access) | SSH key auth only (CLAUDE.md); `ssh -o BatchMode=yes` already used |
| V4 Access Control | yes | All soak-monitor probes read-only (`is-active`, `journalctl -p err`, `curl /health`); no mutation. Any write = out of scope, operator-gated (WAN mutation policy) |
| V5 Input Validation | low | WAN names come from the in-repo `TARGETS[]` literals, not untrusted input. Keep them literal; do not eval external strings into ssh commands. |
| V6 Cryptography | no | None introduced. |

### Known Threat Patterns for this stack
| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Accidental production mutation via monitor edit | Tampering | Read-only probe contract preserved; no `systemctl start/stop`, no fault injection on live units |
| Shell injection via WAN name into ssh command | Tampering/Elevation | WAN names are in-repo literals (`spectrum`/`att`); do not interpolate untrusted input into the `systemctl is-active cake-autorate-${wan}` string |
| Privileged read denial mid-evidence | DoS (self) | Per MEMORY: hand operator a `! <command>` rather than escalating creds; static test still proves the fix without host access |
| Secret/IP leak into public docs | Information Disclosure | Health IPs already committed in the script/units; keep new evidence notes consistent, don't expand exposure |

## Sources

### Primary (HIGH confidence — direct repo reads, 2026-06-09)
- `scripts/soak-monitor.sh` — full read: TARGETS (L10-13), SERVICE_UNITS (L14-18), `check_spectrum_cake_autorate_state` (L56-182), `check_target` curl + Spectrum fallback (L185-271), `is_spectrum_cake_trial_active` (L275-280), `check_errors` (L283-297), per-WAN error branches (L327-344), aggregate summary scan (L398-432)
- `deploy/systemd/cake-autorate-att.service`, `cake-autorate-att-state-bridge.service`, `silicom-bypass-watchdog-cake-autorate-att.service` — live ATT unit names + `CAKE_AUTORATE_BRIDGE_HEALTH_HOST=10.10.110.227`
- `deploy/systemd/cake-autorate-spectrum-state-bridge.service` — Spectrum health host `10.10.110.223` (contrast)
- `deploy/scripts/cake-autorate-att-state-bridge` (shared bridge) — confirmed it serves a real `/health` endpoint (`ThreadingHTTPServer`, `do_GET /health`, `source:"cake-autorate-state-bridge"`)
- `deploy/scripts/cake-autorate-att-qdisc-init` — ATT device names `att-router`/`att-modem`
- `tests/test_spectrum_cake_autorate_artifacts.py` — read-and-assert test pattern template
- `.planning/REQUIREMENTS.md` (MON-01/02, SAFE-14, Out-of-Scope), `.planning/ROADMAP.md` (Phase 230), `.planning/STATE.md` (229-03 baseline 87980bdf, 229 decisions), `.planning/phases/229-att-deploy-path-artifact-tests/229-RESEARCH.md` (ATT unit/artifact inventory, silicom-orphan pitfall, SAFE-14 protected set incl. `wan_controller_state.py`)
- Live tool checks: `shellcheck 0.9.0` present + current script passes `-S error` (exit 0); `bats` absent; `git rev-parse 87980bdf` resolves; HEAD `4ad2986e` (`v1.49-19`)

### Secondary / Tertiary
- None — entire surface is in-repo; no external sources needed.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no external deps; shellcheck/pytest verified present, bats verified absent.
- Architecture (per-WAN mode predicate + unit map, error-scan fix): HIGH — every call site located by direct read with line numbers; ATT health endpoint confirmed live in the bridge script.
- Pitfalls: HIGH — derived from direct reads (silicom-only-on-ATT, 4 Spectrum-hardcoded call sites, ATT health already working).
- Open questions (probe caching, native-mode fallback retention, criterion-3 evidence form): MEDIUM — implementation/scope choices, flagged in Assumptions Log.

**Research date:** 2026-06-09
**Valid until:** ~30 days (stable, in-repo; invalidated only if `soak-monitor.sh` or the ATT units change before planning)
