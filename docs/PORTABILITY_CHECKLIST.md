# Portability Checklist

**Status:** ✅ Production (Phase 2A Validated)
**Last Updated:** 2025-12-17

---

## Purpose

This checklist **verifies** that the CAKE controller remains link-agnostic across all deployments.

Use this before:
- Deploying a new phase (e.g., Phase 2B)
- Adding new features
- Modifying control logic
- Creating new configs

---

## Code Portability Verification

### ✅ Core Controller (`autorate_continuous_v2.py`)

- [ ] **No ISP-specific logic**
  - No `if wan_name == "Spectrum": ...`
  - No `if wan_name == "ATT": ...`
  - No hardcoded ISP names in control flow

- [ ] **No medium-specific logic**
  - No `if link_type == "cable": ...`
  - No `if link_type == "dsl": ...`
  - No DOCSIS-specific heuristics
  - No DSL-specific state machines

- [ ] **All parameters from config**
  - Floors loaded from YAML
  - Thresholds loaded from YAML
  - EWMA alphas loaded from YAML
  - No hardcoded magic numbers in control logic

- [ ] **State machine is universal**
  - Same transition logic for all deployments
  - Transitions driven by thresholds, not link type
  - N-state support via config (3-state, 4-state, future N-state)

- [ ] **Upload/download independence**
  - Upload state doesn't influence download adjustments
  - Download state doesn't influence upload adjustments
  - Configs can use different state counts (e.g., DL=4-state, UL=3-state)

### ✅ Configuration Loading (`Config` class)

- [ ] **Backward compatibility**
  - Legacy `floor_mbps` (single floor) supported
  - Missing `floor_soft_red_mbps` defaults to `floor_yellow_mbps`
  - Missing `hard_red_bloat_ms` defaults to sensible value (80ms)

- [ ] **No assumptions about deployment**
  - Config doesn't infer link type from `wan_name`
  - No special-case loading based on deployment context

### ✅ State Adjustment (`QueueController` class)

- [ ] **`adjust()` method (3-state) is link-agnostic**
  - Takes config parameters (floor, ceiling, thresholds)
  - No link-specific branching

- [ ] **`adjust_4state()` method (4-state) is link-agnostic**
  - Takes config parameters (floor_green, floor_yellow, floor_soft_red, floor_red)
  - No link-specific branching
  - Works on any deployment with 4-state config

- [ ] **Download uses correct method**
  - 4-state if `floor_soft_red_mbps` differs from `floor_yellow_mbps`
  - 3-state otherwise

- [ ] **Upload uses correct method**
  - Typically 3-state (Phase 2A design)
  - Can be 4-state if config specifies

---

## Configuration Portability Verification

### ✅ Reference Configs Exist

- [ ] **Cable (DOCSIS):** `configs/spectrum_config.yaml`
- [ ] **DSL (VDSL2):** `configs/att_config.yaml`
- [ ] **Fiber (GPON):** `configs/dad_fiber_config.yaml` (template)

### ✅ Configs Use Universal Schema

- [ ] All configs use same YAML structure
- [ ] All configs have same required fields
- [ ] No cable-specific or DSL-specific config fields
- [ ] Behavioral differences expressed via parameter values only

### ✅ Config Invariants Hold

For each config, verify:

- [ ] **Threshold ordering:**
  ```
  0 < target_bloat_ms < warn_bloat_ms < hard_red_bloat_ms
  ```

- [ ] **Floor ordering (download):**
  ```
  floor_red_mbps ≤ floor_soft_red_mbps ≤ floor_yellow_mbps ≤ floor_green_mbps ≤ ceiling_mbps
  ```

- [ ] **Floor ordering (upload):**
  ```
  floor_red_mbps ≤ floor_yellow_mbps ≤ floor_green_mbps ≤ ceiling_mbps
  ```

- [ ] **EWMA alpha range:**
  ```
  0 < alpha_baseline < 1
  0 < alpha_load < 1
  alpha_load > alpha_baseline
  ```

- [ ] **Backoff factor range:**
  ```
  0 < factor_down < 1
  ```

### ✅ Config Comments Document Intent

- [ ] Comments explain **why** values are chosen (not what they do)
  - Example: `# DOCSIS scheduler variance` (good)
  - Example: `# Sets target bloat threshold` (bad - states the obvious)

- [ ] Comments reference link characteristics, not link types
  - Example: `# Stable latency, tight tolerance` (good)
  - Example: `# DSL needs this` (bad - not portable)

---

## Deployment Portability Verification

### ✅ Same Binary, Different Configs

- [ ] All deployments run `python -m cake.autorate_continuous_v2`
- [ ] Only difference is `--config <path>`
- [ ] No deployment-specific forks or patches

### ✅ Systemd Timers Are Generic

- [ ] Timer configs reference config file via path only
- [ ] No ISP names in systemd units (except for naming/logging)
- [ ] Timer frequency is config-driven (not hardcoded per deployment)

### ✅ Logging Is Deployment-Agnostic

- [ ] Log format is identical across deployments
- [ ] State names (GREEN/YELLOW/SOFT_RED/RED) are universal
- [ ] No deployment-specific log messages

---

## Testing Portability Verification

### ✅ Unit Tests Are Link-Agnostic

- [ ] Tests use synthetic configs (not real deployment configs)
- [ ] Tests cover 3-state and 4-state modes
- [ ] Tests verify invariants (threshold ordering, floor ordering)
- [ ] No tests assume specific link types

### ✅ Integration Tests Use Reference Configs

- [ ] Tests run against all reference configs (cable, DSL, fiber)
- [ ] Same test suite, different config parameters
- [ ] Results validated against expected behavior (not link type)

---

## Documentation Portability Verification

### ✅ Architecture Docs Are Universal

- [ ] `PORTABLE_CONTROLLER_ARCHITECTURE.md` exists
- [ ] Explains link-agnostic design
- [ ] No cable-specific or DSL-specific sections

### ✅ Config Schema Is Universal

- [ ] `CONFIG_SCHEMA.md` exists
- [ ] Defines canonical configuration model
- [ ] Documents invariants for all deployments

### ✅ Phase Docs Don't Introduce Link-Specific Logic

- [ ] Phase 2A (`PHASE_2A_SOFT_RED.md`): Config-only changes ✅
- [ ] Phase 2B (future): Time-of-day bias via config only (planned)
- [ ] No phase introduces `if wan_type: ...` logic

### ✅ Operational Docs Use Generic Examples

- [ ] Deployment guides use `<wan_name>` placeholders
- [ ] Commands are parameterized (not hardcoded for Spectrum/AT&T)
- [ ] Troubleshooting is symptom-based (not link-based)

---

## Future Phase Readiness

### ✅ Phase 2B: Time-of-Day Bias (Config-Only)

**Proposed config addition:**
```yaml
tod_bias:
  enabled: true
  evening_hours: [18, 19, 20, 21]  # 6pm-9pm
  evening_floor_multiplier: 0.85   # Lower floors during peak
  offpeak_floor_multiplier: 1.0    # Normal floors otherwise
```

**Verification:**
- [ ] No link-specific time-of-day logic
- [ ] Same bias algorithm for all deployments
- [ ] Cable (has evening congestion) and DSL (doesn't) both use same code
- [ ] Config drives when bias is applied

### ✅ Phase 2C: CAKE Stats Corroboration (Config-Only)

**Proposed config addition:**
```yaml
cake_corroboration:
  enabled: true
  drop_threshold: 10       # Drops/sec to confirm RED
  queue_threshold: 0.8     # Queue utilization to confirm YELLOW
```

**Verification:**
- [ ] No link-specific CAKE stats interpretation
- [ ] Same corroboration logic for all deployments
- [ ] Thresholds configurable per deployment

### ✅ Phase 2D: Adaptive Thresholds (Config-Only)

**Proposed config addition:**
```yaml
adaptive_thresholds:
  enabled: true
  variance_window: 300     # 5min history
  threshold_headroom: 1.5  # Multiplier above observed baseline
```

**Verification:**
- [ ] No link-specific threshold adaptation
- [ ] Same adaptation algorithm for all deployments

---

## Red Flags (Violations of Portability)

### 🚫 Code Red Flags

- **Immediate failure:** Code contains:
  - `if wan_name == "Spectrum": ...`
  - `if wan_name == "ATT": ...`
  - `if link_type == "cable": ...`
  - `if link_type == "dsl": ...`

- **Failure:** Control logic has:
  - Hardcoded thresholds (not from config)
  - ISP-specific state machines
  - Medium-specific heuristics

### 🚫 Config Red Flags

- **Immediate failure:** Config has:
  - `link_type: "cable"` (controller shouldn't care)
  - `isp: "spectrum"` (controller shouldn't care)
  - Cable-specific fields (e.g., `docsis_version: 3.1`)

- **Failure:** Config violates invariants:
  - `floor_green_mbps > ceiling_mbps`
  - `target_bloat_ms > warn_bloat_ms`
  - `alpha_baseline > 1.0`

### 🚫 Documentation Red Flags

- **Failure:** Docs say:
  - "This feature only works on cable"
  - "DSL deployments need different logic"
  - "Fiber uses a separate state machine"

---

## Validation Commands

### Verify Code Has No Link-Specific Logic

```bash
cd src/cake
grep -n "wan_name.*==" autorate_continuous_v2.py
# Should return nothing

grep -n "link_type" autorate_continuous_v2.py
# Should return nothing

grep -n "cable\|dsl\|fiber\|docsis\|vdsl" autorate_continuous_v2.py
# Should only appear in comments, not control flow
```

### Verify Configs Use Same Schema

```bash
cd configs

# Check all configs have same top-level keys
diff <(yq 'keys' spectrum_config.yaml) <(yq 'keys' att_config.yaml)
# Should show no differences (or only expected differences)

# Check threshold ordering
for cfg in spectrum_config.yaml att_config.yaml dad_fiber_config.yaml; do
  echo "Checking $cfg..."
  python3 -c "
import yaml
with open('$cfg') as f:
    cfg = yaml.safe_load(f)
thresh = cfg['continuous_monitoring']['thresholds']
assert thresh['target_bloat_ms'] < thresh['warn_bloat_ms']
assert thresh['warn_bloat_ms'] < thresh.get('hard_red_bloat_ms', 1000)
print('✅ $cfg: Thresholds valid')
"
done
```

### Verify Same Binary Runs on All Deployments

```bash
# On Spectrum container
ssh kevin@10.10.110.246 "python3 -m cake.autorate_continuous_v2 --help"

# On AT&T container
ssh kevin@10.10.110.247 "python3 -m cake.autorate_continuous_v2 --help"

# Should be identical output (same code)
```

---

## Sign-Off Template

When validating a new phase or deployment:

```
Portability Checklist - Phase 2A Validation

Date: 2025-12-17
Phase: 2A (SOFT_RED state)
Validator: Kevin

Code Portability:
- [✅] No ISP-specific logic
- [✅] No medium-specific logic
- [✅] All parameters from config
- [✅] State machine universal
- [✅] Upload/download independent

Config Portability:
- [✅] Reference configs exist
- [✅] Universal schema used
- [✅] Invariants hold
- [✅] Comments document intent

Deployment Portability:
- [✅] Same binary across deployments
- [✅] Systemd timers generic
- [✅] Logging deployment-agnostic

Testing Portability:
- [✅] Unit tests link-agnostic
- [✅] Integration tests use reference configs

Documentation Portability:
- [✅] Architecture docs universal
- [✅] Config schema universal
- [✅] Phase docs config-only

Red Flags Found: None

Result: ✅ PASS - Phase 2A maintains portability

Notes:
- Spectrum uses 4-state download (GREEN/YELLOW/SOFT_RED/RED)
- AT&T uses 3-state (GREEN/YELLOW/RED)
- Same controller code for both (4-state degrades to 3-state via config)
- Upload remains 3-state for both deployments
```

---

## Summary

This checklist ensures the CAKE controller remains **portable and link-agnostic**.

**Key verification points:**
1. Code has no ISP/medium-specific logic
2. Configs use universal schema
3. Same binary runs on all deployments
4. State machine driven by thresholds (not link type)
5. Future phases remain config-only

**Use this checklist:**
- Before every deployment
- Before merging new features
- When adding new configs
- During code review

**Phase 2A validation:** ✅ PASS (see sign-off template above)

**Ready for Phase 2B:** ✅ YES (time-of-day bias can be config-only)

---

**Next:** Deploy Phase 2B when ready (see `PHASE_2B_TOD_BIAS.md` proposal).
