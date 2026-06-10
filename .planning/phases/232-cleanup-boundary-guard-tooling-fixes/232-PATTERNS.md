# Phase 232 — Pattern Map

**Generated:** 2026-06-10
**Scope:** Analog files + concrete excerpts for every file this phase creates or modifies.

---

## File: `scripts/check-cleanup-boundary.sh` (NEW — BOUND-01 guard)

**Role:** Read-only git-evidence gate; fails closed on denylist removal/modification.
**Closest analog:** `scripts/phase225-safe13-boundary-check.sh` (per-file anchor comparison, `--anchor`/`--out` args, JSON evidence, fail-closed) + allowlist concept from `scripts/check-safe07-source-diff.sh`.

Excerpt — arg parse + posture header (`phase225-safe13-boundary-check.sh:9-26,36-43`):

```bash
set -euo pipefail

ANCHOR="v1.48"
OUT=".planning/phases/225-dscp-survival-trace/evidence/safe13-boundary-check.json"
...
while [[ $# -gt 0 ]]; do
    case "$1" in
        --anchor) ANCHOR="${2:-}"; shift 2 ;;
        --out) OUT="${2:-}"; shift 2 ;;
        --help|-h) usage; exit 0 ;;
        *) echo "ERROR: unknown argument: $1" >&2; usage >&2; exit 2 ;;
    esac
done
```

Excerpt — python heredoc comparison core (`phase225-safe13-boundary-check.sh:58-80`):

```bash
python3 - "$ANCHOR" "$OUT" <<'PY'
import json, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path

anchor = sys.argv[1]
out_path = Path(sys.argv[2])

controller_targets = [
    "src/wanctl/wan_controller.py",
    ...
]
def git(*args, check=True):
    result = subprocess.run(...)
PY
```

Excerpt — exit-code contract documentation (`check-safe07-source-diff.sh:23-26`):

```bash
# Exit:
#   0 — clean
#   1 — SAFE-09 VIOLATION or SAFE-08 VIOLATION (...)
#   2 — usage / git error (ref not found)
```

Excerpt — documented allowlist precedent (`check-safe07-source-diff.sh:3-9`): allowlist members enumerated in header comments with the requirement ID that authorized each.

---

## File: `tests/test_cleanup_boundary_guard.py` (NEW — BOUND-01 gate wiring)

**Role:** Default-suite pytest that (a) runs the guard against the real repo and asserts exit 0, (b) proves fail-closed behavior against synthetic violations.
**Closest analog:** `tests/test_check_safe07_source_diff.py` and `tests/test_phase227_safe13_boundary.py` (subprocess-run a guard script, assert exit code + JSON shape).

Excerpt — subprocess harness convention (`tests/test_phase231_rollback.py:9-13,47-55`):

```python
REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "scripts" / "phase231-rollback.sh"
...
    return subprocess.run(
        ["bash", str(SCRIPT), *args],
        cwd=REPO_ROOT, env=env, capture_output=True, text=True, timeout=20, check=False,
    )
```

For synthetic-violation tests: run the guard in a scratch `git init` clone/worktree (or pass a manifest override flag) — never mutate the real worktree.

---

## File: `scripts/phase231-rollback.sh` (MODIFY — FIX-01 / CR-01)

**Role:** Confirm-path hardening only; preflight/dry-run untouched.
**Target state prescribed by `231-REVIEW.md:43-57`:**

```bash
remote_script="${tmpdir}/rollback-remote.sh"
{
    printf '%s\n' 'set -euo pipefail'
    rollback_commands_for_wan "$WAN"
} >"$remote_script"
ssh -n "${SSH_OPTS[@]}" "$SSH_HOST" "bash -s" <"$remote_script"

external_active="$(ssh -n "${SSH_OPTS[@]}" "$SSH_HOST" "systemctl is-active cake-autorate-${WAN}.service || true")"
if [[ "$external_active" == "active" ]]; then
    echo "ROLLBACK VERIFY FAILED: cake-autorate-${WAN}.service is still active" >&2
    exit 1
fi
```

Current code being replaced (`scripts/phase231-rollback.sh:277-284`): bare `rollback_commands_for_wan "$WAN" >"$remote_script"` with no preamble and no external-writer verification.

---

## File: `tests/test_phase231_rollback.py` (MODIFY — FIX-01 proof + WR-02)

**Role:** Extend existing SSH-shim harness with confirm-path payload assertions and read-only negative assertions.
**Shim pattern already in file (lines 13-46):** fake `ssh` on PATH logs `"$*"` to `ssh.log`, returns canned `systemctl` outputs. Note: confirm-path payload arrives on the shim's **stdin** (`bash -s` + redirect), so the shim must be extended to also capture stdin (e.g. `cat >> {payload_log}` when payload is `bash -s`).

WR-02 prescribed assertions (`231-REVIEW.md` WR-02 fix):

```python
log_text = (tmp_path / "ssh.log").read_text(encoding="utf-8")
assert not re.search(r"systemctl\s+(enable|disable|restart|start|stop)", log_text)
assert not re.search(r"tc\s+qdisc\s+(replace|add|del)", log_text)
assert "systemctl is-active" in log_text
```

---

## File: `scripts/phase231-migration-held.sh` (MODIFY — WR-01, optional same-review cleanup)

**Target state prescribed by `231-REVIEW.md` WR-01 fix:**

```bash
metrics_check() {
    local ssh_target="$1" wan="$2"
    local db="/var/lib/wanctl/metrics-${wan}.db"
    ...
}
```

(Split the `local` declaration so `db` derives from the already-assigned local `wan` — fixes SC2318.)

---

## File: `.planning/todos/pending/2026-04-17-operator-summary-digest-permission-handling.md` (MOVE → `closed/` — FIX-02)

**Closest analog:** `.planning/todos/closed/2026-04-08-investigate-tcp-12down-latency-spikes-under-multi-flow-downl.md` frontmatter:

```yaml
resolves_phase: 221
closed_by_phase: 221
verdict: carried_narrower_with_close_with_prejudice_rule
```

Follow: keep original body, add `closed_by_phase: 232` + `verdict:` keys, append `## Resolution` section with evidence pointers, `git mv` pending→closed.

---

## Evidence files (NEW — `.planning/phases/232-cleanup-boundary-guard-tooling-fixes/evidence/`)

**Closest analog:** `.planning/milestones/v1.50-phases/231-.../evidence/rollback-preflight-spectrum.json` and phase225 `safe13-boundary-check.json` — JSON with `proof_type`, `captured_utc`, `overall_pass`, per-check rows.

## PATTERN MAPPING COMPLETE
