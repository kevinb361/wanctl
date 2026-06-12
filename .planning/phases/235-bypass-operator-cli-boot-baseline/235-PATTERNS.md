# Phase 235: Bypass Operator CLI + Boot Baseline - Pattern Map

**Mapped:** 2026-06-12
**Files analyzed:** 7 (5 new, 2 modified/extended) + 1 SAFE-16 invariant (no edit)
**Analogs found:** 7 / 7

This phase is pure bash + systemd + docs + tests. Every new artifact has a strong in-repo analog — the work is consolidation and guarding, not invention. The planner should copy structure from the cited files rather than design fresh patterns. Two load-bearing corrections carry through every artifact: ship `spec-modem` not `sil-spare1` (Pitfall 1 / Assumption A1), and keep the `BPCTL_UTIL` env seam so the executor never touches the live card.

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `scripts/silicom-bypass` (NEW) | operator CLI (bash) | request-response (per-verb card read/write) | `scripts/phase225-safe13-boundary-check.sh` (heavy bash: arg parse, exit codes) + `scripts/wanctl-bpctl-watchdog-petter` (BPCTL_UTIL seam, util() wrapper, read-then-act) | exact (composite) |
| `deploy/systemd/silicom-bypass-init.service` (NEW) | systemd oneshot unit | event-driven (boot ordering) | `deploy/systemd/bpctl-silicom.service` | exact |
| `deploy/scripts/silicom-bypass.conf.example` (NEW) | config example | config (env-sourced KEY=value) | `deploy/scripts/bpctl-watchdog-spectrum.env.example` | exact |
| `tests/test_silicom_bypass_cli.py` (NEW) | pytest (offline verification) | request-response (subprocess + fake tool) + static asserts | `tests/test_check_safe07_source_diff.py` (subprocess+env runner) + `tests/test_att_cake_autorate_artifacts.py` (static artifact asserts) | exact (composite) |
| `scripts/deploy.sh` (MODIFY) | deploy orchestrator (bash) | batch (scp/ssh install) | self — extend the `deploy_att_cake_autorate()` stanza + `*_SYSTEMD=()` array pattern (lines 67-71, 456-504) | self-extend |
| `deploy/systemd/bpctl-silicom.service` (MODIFY/reconcile) | systemd oneshot unit | event-driven (boot ordering) | self — adjust `Before=` targets, become `Requires=`/`After=` anchor for init unit | self-reconcile |
| `docs/SILICOM-BYPASS.md` (MODIFY) | docs | n/a | self — append CLI usage + operator-gated live procedures | self-extend |
| `src/wanctl/**` (NO EDIT — SAFE-16) | controller path | n/a | invariant proven by `scripts/phase225-safe13-boundary-check.sh --anchor v1.51` | n/a |

---

## Pattern Assignments

### `scripts/silicom-bypass` (operator CLI, request-response)

Composite of two analogs: the **heavy-bash skeleton** (header, arg parse, exit codes, usage) from `scripts/phase225-safe13-boundary-check.sh`, and the **card-tool seam + read-then-act** from `scripts/wanctl-bpctl-watchdog-petter`.

**Header + strict mode + arg dispatch** — copy from `scripts/phase225-safe13-boundary-check.sh:1-48`:
```bash
#!/usr/bin/env bash
set -euo pipefail
# ... defaults ...
usage() { cat <<'EOF' ... EOF }
require_command() { ... }              # lines 28-34
while [[ $# -gt 0 ]]; do               # lines 36-43 — adapt to subcommand dispatch
    case "$1" in
        --anchor) ANCHOR="${2:-}"; shift 2 ;;
        --help|-h) usage; exit 0 ;;
        *) echo "ERROR: unknown argument: $1" >&2; usage >&2; exit 2 ;;
    esac
done
```
Reuse the exit-code grammar verbatim: `0` ok/no-op, `1` runtime/read-back failure, `2` usage/unknown-arg. The watchdog/bpctl scripts use `#!/bin/sh` + `set -eu`; the new CLI needs `#!/usr/bin/env bash` + `set -euo pipefail` for `[[`, arrays, and subcommand `case` dispatch — match the heavier `phase225-*` script, NOT the lightweight bpctl scripts.

**BPCTL_UTIL env seam + util wrapper** — copy from `scripts/wanctl-bpctl-watchdog-petter:6-12`:
```bash
: "${BPCTL_UTIL:=/opt/bpctl-silicom/bpctl_util}"
util() {
  "$BPCTL_UTIL" "$IFACE" "$@"
}
```
This is the testability spine — the fake `bpctl_util` is injected by overriding `BPCTL_UTIL`. The CLI must keep it so pytest and the executor never reach the live card. Add the config + marks-log default seams alongside (research "CLI skeleton"):
```bash
CONF="${SILICOM_BYPASS_CONF:-/etc/silicom-bypass.conf}"
MARKS_LOG="${SILICOM_MARKS_LOG:-/var/log/silicom-bypass-marks.log}"
[ -r "$CONF" ] && . "$CONF"            # provides PAIRS="att-modem spec-modem"
```

**Read-then-act idempotent verb** — adapt the state-check pattern in `scripts/wanctl-bpctl-watchdog-petter:27-43` (`is-active` gate guarding `set_bypass`). For the CLI, the gate is the current `get_bypass`/`get_disc` read-back: no-op + exit 0 if already in target state; otherwise `set_*`, re-read, substring-assert, journal. Destructive verbs (`on`, `disc`) require `--yes`; dual-pair → non-NIC additionally requires `--both-wan-confirm`.

**Capability probe before mutate** — `bpctl_util <iface> get_bypass_slave`; empty slave ⇒ refuse the iface loudly. Validate `<pair>` against the `PAIRS` allowlist first (V5 input validation; no `eval`, quote all expansions). The bare mutators to wrap are exactly those in `scripts/wanctl-bpctl-watchdog-bypass:7-9` (`set_dis_bypass off`, `set_bypass on`).

**Read-back assertion strings** — centralize the documented substrings (`docs/SILICOM-BYPASS.md` lines 540-578). Match the `non-` form first (`*non-Bypass*` before `*Bypass*`). Counterintuitive: `set_dis_bypass off` ⇒ `get_dis_bypass` reads `Bypass mode enabled` (Pitfall 2). Baseline want-strings: `Bypass mode enabled`, `Bypass at power off`, `non-Bypass at power up`, `non-Disconnect at power up`, `not in Standard NIC mode`.

**`mark` / journal** — `logger -t silicom-bypass -- "$*"` for journal; append to `$MARKS_LOG` for grep. Quote the label (`-- "$label"`, no `eval`).

**Single source of truth** — implement a `baseline` subcommand here (the 5-verb apply+assert loop ×pair) so `silicom-bypass-init.service` calls `silicom-bypass baseline` rather than duplicating bpctl logic in a second script (CONTEXT discretion; research recommendation).

---

### `deploy/systemd/silicom-bypass-init.service` (oneshot, event-driven)

**Analog:** `deploy/systemd/bpctl-silicom.service` (full file, 14 lines).

Mirror structure exactly:
```ini
[Service]
Type=oneshot
RemainAfterExit=yes
ExecStart=/usr/local/sbin/silicom-bypass baseline

[Install]
WantedBy=multi-user.target
```
**Ordering reconciliation (the load-bearing difference):** `bpctl-silicom.service:5` orders `Before=wanctl@att.service wanctl@spectrum.service` — those wanctl@ units are **disabled** since 2026-06-08 (cake-autorate mode). The init unit owns *policy baseline* and must `Requires=`/`After=bpctl-silicom.service` (which owns module + `/dev/bpctl0`), then `Before=` the live WAN units. Add cake-autorate units to the `Before=` set; keeping the wanctl@ entries too is harmless (Assumption A3):
```ini
[Unit]
Description=Silicom bypass known-good boot baseline
Requires=bpctl-silicom.service
After=bpctl-silicom.service
Before=cake-autorate-att.service cake-autorate-spectrum.service wanctl@att.service wanctl@spectrum.service
```
**Avoid `systemd-udev-settle.service`** — `bpctl-silicom.service:2-4` still references it (deprecated). Do NOT propagate it to the new unit; order on `bpctl-silicom.service` plus a bounded master-iface poll inside `silicom-bypass baseline` (mirror the 50×0.1s `/proc/devices` poll in `scripts/wanctl-bpctl-init:18-24`). Note the `bpctl-silicom.service` udev-settle reference for cleanup but don't expand it.

---

### `deploy/scripts/silicom-bypass.conf.example` (config)

**Analog:** `deploy/scripts/bpctl-watchdog-spectrum.env.example` (2 lines, `KEY=value` sourced by `.`).

Same flat shell-sourced format. Ship live names (the env example itself confirms `IFACE=spec-modem`):
```sh
PAIRS="att-modem spec-modem"
WD_TIMEOUT_MS=10000     # reserved for Phase 236
HEARTBEAT_MS=3000       # reserved for Phase 236
```
**Do NOT ship `sil-spare1`** (Pitfall 1 / A1). The seed/CONTEXT `PAIRS="att-modem sil-spare1"` is stale; `deploy/scripts/bpctl-watchdog-spectrum.env.example:1` (`IFACE=spec-modem`) and `docs/SILICOM-BYPASS.md` lines 256-271 are authoritative.

---

### `tests/test_silicom_bypass_cli.py` (pytest, offline)

Composite of two analogs.

**Subprocess + env-injection runner** — copy the runner shape from `tests/test_check_safe07_source_diff.py:49-58`:
```python
def _run_script(repo, *args, env=None):
    return subprocess.run(
        ["bash", str(repo / "scripts" / SCRIPT.name), *args],
        cwd=repo, capture_output=True, text=True,
        env={**os.environ, **(env or {})},
    )
```
Plus the `REPO_ROOT = Path(__file__).resolve().parents[1]` / `SCRIPT = REPO_ROOT / "scripts" / ...` anchor pattern (lines 11-12) and the per-test `assert result.returncode == N` + `assert "<msg>" in result.stderr/stdout` assertion style (used throughout, e.g. lines 75-88, 238-242). The exit-code-by-class contract (0/1/2) is directly mirrored from this file.

**Fake `bpctl_util` fixture** — research "pytest with fake bpctl_util" sketch: write a bash stub to `tmp_path/bpctl_util` that echoes canned `get_*` strings and records `set_*` calls to a log, `chmod 0o755`, then run the CLI with `env={"BPCTL_UTIL": str(fake), "PAIRS": "att-modem spec-modem", "SILICOM_BYPASS_CONF": "/dev/null"}`. Assert on recorded calls (idempotency = `set_bypass off` NOT in the log) and exit code. This is the offline seam that keeps the executor off the live card.

**Static artifact assertions** — copy from `tests/test_att_cake_autorate_artifacts.py`. Reuse:
- Module-level path constants (lines 14-23) → point at `silicom-bypass`, `silicom-bypass-init.service`, the conf example.
- `test_*_artifacts_are_repo_owned()` (lines 49-101): `.exists()` + `read_text()` substring asserts on the unit file (`Requires=bpctl-silicom.service`, `ExecStart=/usr/local/sbin/silicom-bypass baseline`, the `Before=`/`After=` lines). Directly models `test_init_service_artifact` from the research test map.
- `test_deploy_*_file_list_matches_repo()` (lines 286-307) + the `_*_systemd_array_entries()` regex helper (lines 280-283): models `test_artifacts_repo_owned` — assert deploy.sh references every new 235 artifact and references no nonexistent file.
- `test_deploy_script_has_external_att_mode()` (lines 40-47): models the static "deploy seam wired" check (assert the new function name + flag string + unit basenames appear in deploy.sh text).

Test map (from RESEARCH §Phase Requirements → Test Map): `test_status_reads_live`, `test_off_idempotent_noop`, `test_on_requires_yes`, `test_refuses_non_pair_iface`, `test_both_wan_confirm_gate`, `test_mark_appends_log`, `test_baseline_applies_and_asserts`, `test_baseline_fails_on_mismatch`, `test_init_service_artifact`, `test_artifacts_repo_owned`.

**No bats.** Repo is pytest-only (`Makefile` has no bats/shellcheck target). Quick run: `.venv/bin/pytest tests/test_silicom_bypass_cli.py -x -q`.

---

### `scripts/deploy.sh` (MODIFY — deploy seam extension)

**Analog:** self — the ATT cake-autorate stanza is the template for a minimal operator-gated install of the new 235 artifacts (Assumption A4; full DEPLOY-03 stays Phase 237).

**`*_SYSTEMD=()` array declaration** — mirror `scripts/deploy.sh:67-71`:
```bash
ATT_CAKE_AUTORATE_SYSTEMD=(
    "deploy/systemd/cake-autorate-att.service"
    ...
)
```
Add a `SILICOM_BYPASS_SYSTEMD=("deploy/systemd/silicom-bypass-init.service")` array (the static test asserts this array matches the repo file set).

**Install function** — mirror `deploy_att_cake_autorate()` (`scripts/deploy.sh:456-504`): `scp $PROJECT_ROOT/<file> $TARGET_HOST:/tmp/...` then `ssh "sudo mv ... && sudo chown root:root ... && sudo chmod 755"`, looping `*_SYSTEMD[@]` into `$TARGET_SYSTEMD_DIR`, ending with `sudo systemctl daemon-reload`. Install `scripts/silicom-bypass` → `/usr/local/sbin/silicom-bypass` (chmod 755), the conf example → `/etc/silicom-bypass.conf` (chmod 644, install-if-absent — don't clobber operator edits). **Do NOT** couple this to the wanctl release/restart path (Assumption 3); gate the whole stanza behind its own `--with-silicom-bypass`-style flag, operator-run only. The bpctl-script presence guard at line 497-499 is the model for a soft "absent ⇒ warn, don't fail enable" check.

---

### `deploy/systemd/bpctl-silicom.service` (MODIFY — reconcile, don't duplicate)

**Analog:** self. Anti-pattern to avoid (research): two competing boot units both owning card policy. Clear split — `bpctl-silicom.service` keeps module + `/dev/bpctl0` (`ExecStart=/usr/local/sbin/wanctl-bpctl-init`); the new init unit owns *policy baseline* and depends on it. Reconcile the `Before=` targets here too (wanctl@ units disabled). Keep edits minimal: do not rebuild, do not touch `wanctl-bpctl-init` logic.

---

## Shared Patterns

### Tool-path env seam (BPCTL_UTIL)
**Source:** `scripts/wanctl-bpctl-watchdog-petter:6,10-12` and `scripts/wanctl-bpctl-watchdog-bypass:5`
**Apply to:** `scripts/silicom-bypass` (the `baseline` subcommand too) AND `tests/test_silicom_bypass_cli.py` (fake injection).
```bash
: "${BPCTL_UTIL:=/opt/bpctl-silicom/bpctl_util}"
util() { "$BPCTL_UTIL" "$IFACE" "$@"; }
```
Single most important cross-cutting pattern: it is what keeps every automated step off the live card.

### Heavy-bash arg-parse + exit-code grammar
**Source:** `scripts/phase225-safe13-boundary-check.sh:1-48`
**Apply to:** `scripts/silicom-bypass`.
`#!/usr/bin/env bash` + `set -euo pipefail`; `usage()` heredoc; `require_command`; `while [[ $# -gt 0 ]]; do case ... esac`; exit `0` ok, `1` runtime, `2` usage.

### Config sourced from flat KEY=value file
**Source:** `deploy/scripts/bpctl-watchdog-spectrum.env.example`
**Apply to:** `/etc/silicom-bypass.conf` (CLI sources it; mapping lives in config, not hardcoded). Live names only.

### Offline shell-artifact verification (subprocess + env, plus static asserts)
**Source:** `tests/test_check_safe07_source_diff.py:11-12,49-58` (runner) + `tests/test_att_cake_autorate_artifacts.py:14-101,280-307` (static + deploy-list)
**Apply to:** `tests/test_silicom_bypass_cli.py`. `REPO_ROOT/parents[1]` anchor; `subprocess.run(["bash", str(SCRIPT), *args], env={**os.environ, ...})`; `returncode`/substring asserts; deploy-array regex cross-check.

### SAFE-16 controller-path zero-diff proof (read-only)
**Source:** `scripts/phase225-safe13-boundary-check.sh` (turnkey; protected target list at lines 67-76)
**Apply to:** phase gate. `scripts/phase225-safe13-boundary-check.sh --anchor v1.51 --out .../evidence/safe16-boundary-235.json`. exit 0 + `passed=true` + zero controller-path diff. No `src/wanctl/**` edit by construction; do not author a bespoke checker (research "Don't Hand-Roll").

---

## No Analog Found

None. Every artifact has a strong in-repo analog. The only "gap" is operational, not pattern-level: the deploy seam for these artifacts does not exist yet (the existing bpctl scripts/units were placed manually; `deploy.sh:497` only *checks* their presence). That is covered by extending the `deploy_att_cake_autorate()` template (Assumption A4) rather than inventing a new pattern.

## Metadata

**Analog search scope:** `scripts/`, `deploy/systemd/`, `deploy/scripts/`, `tests/`
**Files scanned (read):** `scripts/wanctl-bpctl-watchdog-petter`, `scripts/wanctl-bpctl-watchdog-bypass`, `scripts/wanctl-bpctl-init`, `scripts/phase225-safe13-boundary-check.sh`, `scripts/deploy.sh` (3 regions), `deploy/systemd/bpctl-silicom.service`, `deploy/scripts/bpctl-watchdog-spectrum.env.example`, `tests/test_check_safe07_source_diff.py`, `tests/test_att_cake_autorate_artifacts.py`
**Pattern extraction date:** 2026-06-12
**Carry-through corrections:** (1) ship `spec-modem` not `sil-spare1` everywhere; (2) keep `BPCTL_UTIL` seam in CLI + tests; (3) reconcile `Before=` targets to cake-autorate units (wanctl@ disabled); (4) no second boot unit — `Requires=`/`After=bpctl-silicom.service`.
