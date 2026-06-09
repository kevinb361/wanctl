# Phase 229: ATT Deploy Path + Artifact Tests - Pattern Map

**Mapped:** 2026-06-09
**Files analyzed:** 3 (1 modified, 2 new)
**Analogs found:** 3 / 3 (all exact in-repo precedents)

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `scripts/deploy.sh` (modified — add `deploy_att_cake_autorate()` + flag wiring) | deploy tooling (bash) | file-I/O (scp+ssh sudo mv) | `deploy_spectrum_cake_autorate()` same file, L397-445 | exact (sibling function) |
| `tests/test_att_cake_autorate_artifacts.py` (new) | test (pytest) | file-I/O reads + subprocess + transform | `tests/test_spectrum_cake_autorate_artifacts.py` | exact (5-test template) |
| DEPLOY-02 read-only live-vs-repo audit step/script (new) | utility (bash, read-only remote) | request-response (ssh sudo -n cat → sha256sum) | `scripts/phase226-snapshot-a.sh` L188/L118-120/L241-247 | exact (read-only contract) |

**Match note:** Every file has a verified in-repo precedent. This phase is mechanical mirroring + two new tests + one read-only audit. No file is without an analog (no "No Analog Found" section needed).

## Pattern Assignments

### `scripts/deploy.sh` — add `deploy_att_cake_autorate()` (deploy tooling, file-I/O)

**Analog:** `deploy_spectrum_cake_autorate()` in the same file, lines 397-445. Mirror as a **sibling function**, NOT a `$wan`-generic refactor (anti-pattern, out of scope per RESEARCH §Anti-Patterns).

**Module-level systemd array** — mirror `SPECTRUM_CAKE_AUTORATE_SYSTEMD` (L62-65). Add a parallel `ATT_CAKE_AUTORATE_SYSTEMD` array. ATT carries a **third unit** the Spectrum array does not — the silicom watchdog (see Pitfall 1):
```bash
# Source: scripts/deploy.sh L62-65 [VERIFIED]
SPECTRUM_CAKE_AUTORATE_SYSTEMD=(
    "deploy/systemd/cake-autorate-spectrum.service"
    "deploy/systemd/cake-autorate-spectrum-state-bridge.service"
)
# ATT mirror adds the silicom watchdog unit (no Spectrum sibling exists):
# ATT_CAKE_AUTORATE_SYSTEMD=(
#   "deploy/systemd/cake-autorate-att.service"
#   "deploy/systemd/cake-autorate-att-state-bridge.service"
#   "deploy/systemd/silicom-bypass-watchdog-cake-autorate-att.service"
# )
```

**Function body — core deploy sequence** (L397-445). Mirror each numbered step, substituting ATT values. WAN-name guard → preflight cake-autorate.sh → mkdir → scp config → scp qdisc-init → scp state-bridge → loop systemd array → daemon-reload:
```bash
# Source: scripts/deploy.sh L397-444 [VERIFIED]
deploy_spectrum_cake_autorate() {
    print_step "Deploying Spectrum cake-autorate external-controller artifacts..."

    if [[ "$WAN_NAME" != "spectrum" ]]; then                     # → ATT: != "att"
        print_error "--with-spectrum-cake-autorate is only valid when wan_name is spectrum"
        exit 1
    fi

    if ! ssh "$TARGET_HOST" "test -x /opt/cake-autorate/cake-autorate.sh"; then   # identical preflight
        print_error "cake-autorate is not installed at /opt/cake-autorate/cake-autorate.sh on $TARGET_HOST"
        ...
        exit 1
    fi

    ssh "$TARGET_HOST" "sudo mkdir -p /etc/cake-autorate /var/log/cake-autorate"  # identical

    # scp → /tmp → sudo mv + chown root:root + chmod 644 (config) / 755 (scripts)
    scp "$PROJECT_ROOT/configs/cake-autorate/config.spectrum.sh" "$TARGET_HOST:/tmp/config.spectrum.sh"
    ssh "$TARGET_HOST" "sudo mv /tmp/config.spectrum.sh /etc/cake-autorate/config.spectrum.sh && sudo chown root:root /etc/cake-autorate/config.spectrum.sh && sudo chmod 644 /etc/cake-autorate/config.spectrum.sh"
    echo "  -> /etc/cake-autorate/config.spectrum.sh"
    # → ATT: config.att.sh

    scp "$PROJECT_ROOT/deploy/scripts/cake-autorate-spectrum-qdisc-init" "$TARGET_HOST:/tmp/cake-autorate-spectrum-qdisc-init"
    ssh "$TARGET_HOST" "sudo mv /tmp/cake-autorate-spectrum-qdisc-init /usr/local/sbin/... && sudo chown root:root ... && sudo chmod 755 ..."
    # → ATT: cake-autorate-att-qdisc-init

    scp "$PROJECT_ROOT/deploy/scripts/cake-autorate-spectrum-state-bridge" "$TARGET_HOST:/tmp/..."
    ssh "$TARGET_HOST" "sudo mv ... /usr/local/sbin/... && sudo chown root:root ... && sudo chmod 755 ..."
    # → ATT: cake-autorate-att-state-bridge  (NOTE: byte-identical script — confirmed diff -q IDENTICAL)

    for file in "${SPECTRUM_CAKE_AUTORATE_SYSTEMD[@]}"; do        # → ATT_CAKE_AUTORATE_SYSTEMD[@]
        if [[ -f "$file" ]]; then
            local basename=$(basename "$file")
            scp "$file" "$TARGET_HOST:/tmp/$basename"
            ssh "$TARGET_HOST" "sudo mv /tmp/$basename $TARGET_SYSTEMD_DIR/$basename && sudo chown root:root $TARGET_SYSTEMD_DIR/$basename"
            echo "  -> $basename"
        else
            print_error "Missing Spectrum cake-autorate systemd unit: $file"   # → "ATT"
            exit 1
        fi
    done

    # L437-440: Spectrum-only trial drop-in cleanup — DO NOT copy verbatim (Pitfall 3).
    ssh "$TARGET_HOST" "sudo rm -f $TARGET_SYSTEMD_DIR/cake-autorate-spectrum.service.d/qdisc-init.conf && sudo rmdir ... || true"

    ssh "$TARGET_HOST" "sudo systemctl daemon-reload"            # identical
    print_success "Spectrum cake-autorate artifacts deployed"
}
```

**Flag wiring — 6 mirror sites** (all verified line numbers):
- Var init L617: add `WITH_ATT_CAKE_AUTORATE=false` after `WITH_SPECTRUM_CAKE_AUTORATE=false`.
- Parse L627-630: add `--with-att-cake-autorate) WITH_ATT_CAKE_AUTORATE=true; shift ;;`.
  ```bash
  # Source: scripts/deploy.sh L627-630 [VERIFIED]
  --with-spectrum-cake-autorate)
      WITH_SPECTRUM_CAKE_AUTORATE=true
      shift
      ;;
  ```
- WAN-name gate L694-697: mirror — `--with-att-cake-autorate` valid only with `WAN_NAME=att`.
  ```bash
  # Source: scripts/deploy.sh L694-697 [VERIFIED]
  if [[ "$WITH_SPECTRUM_CAKE_AUTORATE" == "true" && "$WAN_NAME" != "spectrum" ]]; then
      print_error "--with-spectrum-cake-autorate is only valid with WAN name 'spectrum'"
      exit 1
  fi
  ```
- Dispatch L741-743: add `if [[ "$WITH_ATT_CAKE_AUTORATE" == "true" ]]; then deploy_att_cake_autorate; fi`.
  ```bash
  # Source: scripts/deploy.sh L741-743 [VERIFIED]
  if [[ "$WITH_SPECTRUM_CAKE_AUTORATE" == "true" ]]; then
      deploy_spectrum_cake_autorate
  fi
  ```
- `usage()` L99-101: add a `--with-att-cake-autorate` help block (mirror).
- Dry-run block L710-713 + status echo L691: mirror the planned-actions print and the `echo "ATT cake-autorate: ..."` summary line.
- `print_next_steps()` L553-582: mirror an ATT branch keyed on `WITH_ATT_CAKE_AUTORATE` — enable `cake-autorate-att.service cake-autorate-att-state-bridge.service`, disable `wanctl@att.service`, log `/var/log/cake-autorate/cake-autorate.att.log`, state `/var/lib/wanctl/att_state.json` (vs Spectrum's `.spectrum`/`spectrum_state.json`).

**ATT-specific substitution table** (build from real ATT files, NOT by analogy — Pitfall 2):

| Element | Spectrum (template) | ATT (correct) | Source |
|---------|--------------------|----------------|--------|
| config file | `config.spectrum.sh` | `config.att.sh` | configs/cake-autorate/config.att.sh |
| qdisc-init script | `cake-autorate-spectrum-qdisc-init` | `cake-autorate-att-qdisc-init` | deploy/scripts/ |
| state-bridge script | `cake-autorate-spectrum-state-bridge` | `cake-autorate-att-state-bridge` (byte-identical) | confirmed `diff -q` |
| trial drop-in cleanup | removes `cake-autorate-spectrum.service.d/qdisc-init.conf` | **omit** for ATT (ATT unit carries ExecStartPre inline; no known ATT drop-in — Pitfall 3, [ASSUMED] verify read-only in DEPLOY-02) | deploy.sh L437-440 |

---

### `tests/test_att_cake_autorate_artifacts.py` (test, file-I/O + subprocess)

**Analog:** `tests/test_spectrum_cake_autorate_artifacts.py` (full file, 5 tests). Mirror the 5 test shapes; substitute ATT values; add the silicom-watchdog assertions and the TEST-02 drift gate.

**Path constants block** (L13-19) — mirror with ATT names + add watchdog path:
```python
# Source: tests/test_spectrum_cake_autorate_artifacts.py L13-19 [VERIFIED]
REPO_ROOT = Path(__file__).resolve().parents[1]
DEPLOY = REPO_ROOT / "scripts" / "deploy.sh"
STATE_BRIDGE = REPO_ROOT / "deploy" / "scripts" / "cake-autorate-spectrum-state-bridge"  # → -att-
QDISC_INIT = REPO_ROOT / "deploy" / "scripts" / "cake-autorate-spectrum-qdisc-init"      # → -att-
CAKE_SERVICE = REPO_ROOT / "deploy" / "systemd" / "cake-autorate-spectrum.service"        # → -att.service
BRIDGE_SERVICE = REPO_ROOT / "deploy" / "systemd" / "cake-autorate-spectrum-state-bridge.service"  # → -att-
CAKE_CONFIG = REPO_ROOT / "configs" / "cake-autorate" / "config.spectrum.sh"               # → config.att.sh
# ADD (no Spectrum sibling): WATCHDOG_SERVICE = .../silicom-bypass-watchdog-cake-autorate-att.service
```

**Test 1 — deploy.sh text contract** (L28-34):
```python
# Source: L28-34 [VERIFIED]
def test_deploy_script_has_external_spectrum_mode() -> None:   # → ..._att_mode
    text = DEPLOY.read_text(encoding="utf-8")
    assert "--with-spectrum-cake-autorate" in text             # → --with-att-cake-autorate
    assert "deploy_spectrum_cake_autorate" in text             # → deploy_att_cake_autorate
    assert "cake-autorate-spectrum.service" in text            # → cake-autorate-att.service
    assert "cake-autorate-spectrum-state-bridge.service" in text  # → -att-state-bridge.service
```

**Test 2 — artifacts repo-owned + content** (L37-66). Mirror existence checks (add watchdog) + substitute the **ATT content assertions** (built from real files):
```python
# Source: L37-67 [VERIFIED], ATT values from deploy/systemd/cake-autorate-att*.service,
#         deploy/scripts/cake-autorate-att-qdisc-init, configs/cake-autorate/config.att.sh
service = ATT_CAKE_SERVICE.read_text(...)
assert "Conflicts=wanctl@att.service" in service                                          # [VERIFIED att .service L6]
assert "ExecStart=/opt/cake-autorate/cake-autorate.sh /etc/cake-autorate/config.att.sh" in service  # [L11]
assert "ExecStartPre=/usr/local/sbin/cake-autorate-att-qdisc-init" in service             # [L10]

bridge = ATT_BRIDGE_SERVICE.read_text(...)   # ATT bridge has a FULL env block (Pitfall 4 asymmetry)
assert "Wants=cake-autorate-att.service" in bridge
assert "Environment=WANCTL_EXTERNAL_WAN_NAME=att" in bridge                                # [bridge L8]
assert "Environment=WANCTL_EXTERNAL_DL_IF=att-router" in bridge                            # [L9]
assert "Environment=WANCTL_EXTERNAL_UL_IF=att-modem" in bridge                             # [L10]
assert "Environment=WANCTL_EXTERNAL_BASELINE_RTT=28.42043789020452" in bridge             # [L14]
assert "Environment=CAKE_AUTORATE_BRIDGE_HEALTH_HOST=10.10.110.227" in bridge             # [L15]
assert "ExecStart=/usr/local/sbin/cake-autorate-att-state-bridge" in bridge               # [L17]

qdisc = ATT_QDISC_INIT.read_text(...)
assert "dev att-router root cake bandwidth 95000Kbit" in qdisc                             # [qdisc-init L5]
assert "dev att-modem root cake bandwidth 19000Kbit" in qdisc                             # [L6]
assert "ingress" in qdisc      # ATT DL=ingress (Spectrum DL=egress) — assert explicitly (Pitfall 2)
assert "ptm" in qdisc and "overhead 22 mpu 64" in qdisc and "rtt 35ms" in qdisc and "nowash" in qdisc

config = ATT_CAKE_CONFIG.read_text(...)
assert "dl_if=att-router" in config and "ul_if=att-modem" in config                        # [config L5-6]
assert "adjust_dl_shaper_rate=1" in config and "adjust_ul_shaper_rate=0" in config          # [L19-20]
assert "base_dl_shaper_rate_kbps=95000" in config and "base_ul_shaper_rate_kbps=19000" in config  # [L22,L25]
assert 'ping_extra_args="-S 10.10.110.227"' in config                                       # [L10]

watchdog = WATCHDOG_SERVICE.read_text(...)   # NO Spectrum sibling — new assertions (Pitfall 1)
assert "Requires=bpctl-silicom.service" in watchdog                                         # [watchdog L3]
assert "IFACE=att-modem" in watchdog                                                        # [L12]
assert "WANCTL_UNIT=cake-autorate-att.service" in watchdog                                 # [L13]
assert "ExecStart=/usr/local/sbin/wanctl-bpctl-watchdog-petter" in watchdog               # [L14]
```

**Tests 3-5 — state-bridge subprocess** (L69-222). The bridge script is **byte-identical** to Spectrum's, so mirror the subprocess harness exactly; drive ATT via env (`WANCTL_EXTERNAL_WAN_NAME=att`, ATT ifaces) and assert `att` in outputs. Key reuse points:
- Subprocess invocation pattern (L92-99 / L184-191): `subprocess.run([sys.executable, str(STATE_BRIDGE)], env=env, ...)` with `CAKE_AUTORATE_BRIDGE_ONESHOT=1`, explicit `WANCTL_EXTERNAL_STATE_PATH` (sidesteps the hardcoded `spectrum_state.` tmpfile prefix — Pitfall 4, do NOT "fix" the shared script).
- Test 3 (L69-107): assert state JSON `current_rate`/`congestion`/`last_applied`.
- Test 4 (L110-161): set `WANCTL_EXTERNAL_METRICS_DB`; assert metrics rows have `wan_name == "att"` (Spectrum asserts `"spectrum"`).
- Test 5 (L164-222): `free_tcp_port()` helper (L22-25) + 5s poll deadline (well under `--timeout=30`); assert `wan["name"] == "att"` and ATT `qdisc_bandwidth` (`"95Mbit"`/`"19Mbit"` vs Spectrum `"550Mbit"`/`"18Mbit"`).

**Test 6 (NEW) — TEST-02 deploy-list drift gate.** No analog in the Spectrum test (this is a net-new gate). No manifest exists — `deploy.sh` arrays only systemd units; config/qdisc/bridge are inline `scp` paths (Pitfall 5). Approach: read `deploy.sh`, extract the ATT function's `$PROJECT_ROOT/...` source paths + `ATT_CAKE_AUTORATE_SYSTEMD`/`deploy/systemd/...` entries, assert each resolves to an existing repo file; assert set-equality (or subset+nonempty) against the known **6 ATT artifacts** so deploy-references-missing-file and repo-artifact-unreferenced both fail.

---

### DEPLOY-02 read-only live-vs-repo audit (utility, read-only remote request-response)

**Analog:** `scripts/phase226-snapshot-a.sh`. Reuse its read-only contract verbatim — `ssh -o BatchMode=yes "$SSH_HOST" "sudo -n cat <path>"` piped to `sha256sum`, compared against `sha256sum <repo_file>`. **Never** any non-`cat`/`sha256sum` op (no writes) — operator-gated per CLAUDE.md WAN-mutation policy.

**SSH host default + read-only ssh pattern** (L12, L188):
```bash
# Source: scripts/phase226-snapshot-a.sh L12, L188 [VERIFIED]
SSH_HOST="cake-shaper"
ssh -o BatchMode=yes "$SSH_HOST" "sudo -n cat /etc/wanctl/spectrum.yaml" >"$raw_config"
```

**sha256sum helper + equality compare** (L118-120, L241-247):
```bash
# Source: scripts/phase226-snapshot-a.sh L118-120, L241-247 [VERIFIED]
artifact_sha256() { sha256sum "$1" | cut -d' ' -f1; }
...
deployed_sha="$(artifact_sha256 "$deployed_redacted")"
repo_sha="$(artifact_sha256 "$repo_redacted")"
config_equality="diff"
[[ "$deployed_sha" == "$repo_sha" ]] && config_equality="equal"
```

**Apply to the 6 ATT live paths** (all read-only `sudo -n cat | sha256sum` vs repo `sha256sum`):

| Repo file | Live path on cake-shaper |
|-----------|--------------------------|
| `configs/cake-autorate/config.att.sh` | `/etc/cake-autorate/config.att.sh` |
| `deploy/scripts/cake-autorate-att-qdisc-init` | `/usr/local/sbin/cake-autorate-att-qdisc-init` |
| `deploy/scripts/cake-autorate-att-state-bridge` | `/usr/local/sbin/cake-autorate-att-state-bridge` |
| `deploy/systemd/cake-autorate-att.service` | `/etc/systemd/system/cake-autorate-att.service` |
| `deploy/systemd/cake-autorate-att-state-bridge.service` | `/etc/systemd/system/cake-autorate-att-state-bridge.service` |
| `deploy/systemd/silicom-bypass-watchdog-cake-autorate-att.service` | `/etc/systemd/system/silicom-bypass-watchdog-cake-autorate-att.service` |

**Verdict semantics:** repo is declared source of truth; on hash mismatch, report "drift found — reconcile repo to live OR document intentional divergence." Expect a possible state-bridge mismatch (live hand-deployed 2026-06-08; repo may be newer) — surface honestly, do not assume zero-diff ([ASSUMED] A3). If `sudo -n cat` is denied, hand operator a `! <command>` rather than escalating creds (per MEMORY credential-read rule); not a blocker for the offline DEPLOY-01/TEST-01/TEST-02 work.

---

## Shared Patterns

### Mirror-as-sibling, never `$wan`-generic (cross-cutting discipline)
**Source:** `deploy_spectrum_cake_autorate()` (deploy.sh L397-445) + Spectrum test.
**Apply to:** deploy.sh function + test file.
Generic `$wan` symmetry refactor is OUT OF SCOPE (RESEARCH §Anti-Patterns). Mirror as a sibling function/test; substitute ATT values from real files. Premature abstraction explicitly excluded.

### Read-only remote contract
**Source:** `scripts/phase226-snapshot-a.sh` L188 (`ssh -o BatchMode=yes ... sudo -n cat`) + L118-120 (`sha256sum | cut`).
**Apply to:** DEPLOY-02 only. Zero mutation. SSH key auth, BatchMode (no password prompt). Any write = out of scope, operator approval required.

### SAFE-14 controller-path zero-diff (boundary gate, not a new file)
**Source pattern:** `scripts/check-safe07-source-diff.sh` (git protected-path diff). Per Decision 227-04, `wan_controller_state.py` is in the protected set.
**Apply to:** phase boundary verification (not authored as a deliverable file here, but the gate the phase must pass):
```bash
git diff --stat <baseline-ref> -- \
  src/wanctl/wan_controller.py src/wanctl/queue_controller.py \
  src/wanctl/cake_signal.py src/wanctl/wan_controller_state.py \
  src/wanctl/backends/ src/wanctl/alert_engine.py src/wanctl/fusion_healer.py
# MUST be empty at the phase boundary. HEAD at research: 58ef4ff8 (planner pins exact baseline).
```

## No Analog Found

None. All three deliverables have exact in-repo precedents.

## Critical Pitfalls (carry into plans)

1. **Silicom watchdog is an orphan with no Spectrum sibling** — ATT deploy MUST scp `silicom-bypass-watchdog-cake-autorate-att.service`. It `Requires=bpctl-silicom.service` and ExecStarts `/usr/local/sbin/wanctl-bpctl-watchdog-petter` (repo: `scripts/wanctl-bpctl-watchdog-{petter,bypass}`), deployed by no current path. [ASSUMED A1] Conservative scope = ship the unit + preflight bpctl runtime, do NOT own the bpctl tooling install (mirrors Spectrum's "ship units, preflight cake-autorate.sh"). Confirm with operator.
2. **ATT values differ from Spectrum** — `ingress`/`ptm`/`overhead 22 mpu 64`/`rtt 35ms`/`nowash` (DL on att-router), `95000Kbit` DL / `19000Kbit` UL, health host `10.10.110.227`, full bridge env block. Build assertions from real files, not by Spectrum analogy.
3. **Do NOT copy the Spectrum trial drop-in cleanup line** (deploy.sh L437-440) — wrong path for ATT; ATT unit carries ExecStartPre inline. Omit and note why.
4. **Bridge env asymmetry** — ATT bridge unit sets a full `WANCTL_EXTERNAL_*` env block (L8-16); Spectrum sets only health host/port. Assert ATT's explicit env. Shared script's hardcoded `spectrum_state.` tmpfile prefix is harmless (final path = `WANCTL_EXTERNAL_STATE_PATH`); do NOT "fix" it (shared-script diff risk).
5. **TEST-02 must parse, not array-read** — no central manifest; 3 of 6 ATT artifacts are inline `scp` paths, not in the systemd array.

## Metadata

**Analog search scope:** `scripts/deploy.sh`, `tests/`, `deploy/systemd/`, `deploy/scripts/`, `configs/cake-autorate/`, `scripts/phase226-snapshot-a.sh`, `scripts/check-safe07-source-diff.sh`
**Files scanned:** 9 (verified by direct read; bridge byte-identity confirmed via `diff -q`)
**Pattern extraction date:** 2026-06-09
