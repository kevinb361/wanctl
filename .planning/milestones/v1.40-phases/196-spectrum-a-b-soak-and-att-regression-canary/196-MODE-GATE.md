# Phase 196 Spectrum Mode Gate

## Spectrum Mode Gate

gate_name: spectrum-cake-signal-enabled-toggle
active_config_path: /etc/wanctl/spectrum.yaml
repo_reference_config: configs/spectrum.yaml
service: wanctl@spectrum.service
rtt-blend: cake_signal.enabled=false
cake-primary: cake_signal.enabled=true
reload_method: systemctl restart wanctl@spectrum.service
sigusr1_only: rejected-for-phase-196-mode-proof

This gate is the only accepted Phase 196 Spectrum mode switch. It uses the
deployment YAML and service lifecycle only; it does not change Python controller
source and does not mutate RouterOS or backend transport settings.

`cake_signal.enabled=false` is the `rtt-blend` gate because
`WANController._run_cake_stats` returns before producing CAKE snapshots when
both CAKE signal processors are disabled. With no valid fresh CAKE snapshot,
`WANController._select_dl_primary_scalar_ms` uses the RTT fallback path and
`signal_arbitration.active_primary_signal` must report `rtt`.

`cake_signal.enabled=true` restores `cake-primary` because a valid non-cold-start
CAKE snapshot lets `_select_dl_primary_scalar_ms` use queue delay as the primary
DL scalar and `signal_arbitration.active_primary_signal` must report `queue`.

`systemctl restart wanctl@spectrum.service` is required for the proof. A
SIGUSR1-only reload can update config but leave an already-populated
`_dl_cake_snapshot` in memory, which can make the selector continue seeing an
old queue snapshot. Restarting the service clears process memory and proves the
mode from a clean runtime.

This gate must forbid backend transport swaps, router API mutation, Python
source edits, tuning changes, and state-machine, threshold, EWMA, dwell, deadband, burst-detection changes.

## Operator Procedure

Run these commands only during an operator-approved Spectrum restart window and
only when no other Spectrum experiment is running. Do not read
`/etc/wanctl/secrets`, do not change router API state, and do not change any
config key except `cake_signal.enabled`.

Set common paths:

```bash
active_config=/etc/wanctl/spectrum.yaml
backup="/etc/wanctl/spectrum.yaml.phase196-$(date -u +%Y%m%dT%H%M%SZ).bak"
sudo cp -a "$active_config" "$backup"
printf 'backup_path=%s\n' "$backup"
```

### Switch to rtt-blend

Set `cake_signal.enabled` to `false` with a YAML-aware editor, or use this
YAML-loading Python command on the Spectrum host:

```bash
sudo python3 - "$active_config" <<'PY'
import sys
import yaml

path = sys.argv[1]
with open(path, "r", encoding="utf-8") as fh:
    data = yaml.safe_load(fh)
data.setdefault("cake_signal", {})["enabled"] = False
with open(path, "w", encoding="utf-8") as fh:
    yaml.safe_dump(data, fh, sort_keys=False)
PY
sudo systemctl restart wanctl@spectrum.service
```

After `/health` is available, capture preflight evidence:

```bash
export PHASE196_OUT_DIR=.planning/phases/196-spectrum-a-b-soak-and-att-regression-canary/soak
test -n "${PHASE196_SPECTRUM_HEALTH_URL:-}"
test -n "${PHASE196_SPECTRUM_SSH_HOST:-}"
test -n "${PHASE196_SPECTRUM_METRICS_DB:-}"
./scripts/phase196-soak-capture.sh preflight
```

Verify the runtime state before proceeding:

```bash
curl --fail --silent --show-error "$PHASE196_SPECTRUM_HEALTH_URL" \
  | jq -e '(.wans[0] // .).cake_signal.enabled == false and (.wans[0] // .).signal_arbitration.active_primary_signal == "rtt"'
ssh -o BatchMode=yes "$PHASE196_SPECTRUM_SSH_HOST" \
  "sudo -n sqlite3 -readonly '$PHASE196_SPECTRUM_METRICS_DB' \"SELECT value FROM metrics WHERE wan_name='spectrum' AND metric_name='wanctl_arbitration_active_primary' ORDER BY timestamp DESC LIMIT 1;\"" \
  | grep -qx '2'
```

### Switch back to cake-primary

Restore `cake_signal.enabled` to `true` with a YAML-aware editor, or use this
YAML-loading Python command on the Spectrum host:

```bash
sudo python3 - "$active_config" <<'PY'
import sys
import yaml

path = sys.argv[1]
with open(path, "r", encoding="utf-8") as fh:
    data = yaml.safe_load(fh)
data.setdefault("cake_signal", {})["enabled"] = True
with open(path, "w", encoding="utf-8") as fh:
    yaml.safe_dump(data, fh, sort_keys=False)
PY
sudo systemctl restart wanctl@spectrum.service
```

After `/health` is available and a valid non-cold-start CAKE sample has landed,
capture preflight evidence again:

```bash
./scripts/phase196-soak-capture.sh preflight
```

Verify the restored runtime state:

```bash
curl --fail --silent --show-error "$PHASE196_SPECTRUM_HEALTH_URL" \
  | jq -e '(.wans[0] // .).cake_signal.enabled == true and (.wans[0] // .).signal_arbitration.active_primary_signal == "queue"'
ssh -o BatchMode=yes "$PHASE196_SPECTRUM_SSH_HOST" \
  "sudo -n sqlite3 -readonly '$PHASE196_SPECTRUM_METRICS_DB' \"SELECT value FROM metrics WHERE wan_name='spectrum' AND metric_name='wanctl_arbitration_active_primary' ORDER BY timestamp DESC LIMIT 1;\"" \
  | grep -qx '1'
```

If either mode check fails, restore from the timestamped backup or set
`cake_signal.enabled=true`, restart `wanctl@spectrum.service`, write
`mode_gate_verdict: "fail"` in the proof artifact, and keep
`196-PREFLIGHT.md` at `decision: blocked-do-not-start-soak`.

## Proof Artifact

The operator proof belongs at:

```text
.planning/phases/196-spectrum-a-b-soak-and-att-regression-canary/soak/preflight/mode-gate-proof.json
```

The proof must include the `gate_name`, the backup path, both observed modes,
the restored mode, `mode_gate_verdict`, and the operator confirmation that no
concurrent Spectrum experiment was running. `mode_gate_verdict` may be `pass`
only when `rtt-blend` reports active primary `rtt` with metric encoding `2`,
`cake-primary` reports active primary `queue` with metric encoding `1`, and the
restored mode is `cake-primary`.
