# Phase 238: RTT-Provenance Verification (Read-Only Entry Gate) - Pattern Map

**Mapped:** 2026-06-14
**Files analyzed:** 3 (2 scripts + 1 evidence artifact)
**Analogs found:** 2 / 2 code files (PROVENANCE-MAP.md is artifact-only, no code analog)

This is a read-only entry-gate phase. No source files are created or modified. The only
new files are two committed bash proof scripts under `scripts/` and one phase-dir markdown
evidence artifact. Neither script is a controller-path file, so SAFE-17 holds.

## File Classification

| New File | Role | Data Flow | Closest Analog | Match Quality |
|----------|------|-----------|----------------|---------------|
| `scripts/phase238-egress-proof.sh` | utility (read-only proof script) | request-response (SSH read → kernel query → JSON) | `scripts/phase231-migration-held.sh` | exact (same SSH-to-cake-shaper, per-WAN TARGETS, python3-JSON, mktemp+trap, exit-code verdict) |
| `scripts/phase238-safe17-boundary-check.sh` | utility (read-only git assertion) | transform (git read → JSON record → exit code) | `scripts/phase237-safe16-boundary-check.sh` | exact (same controller-path target list, anchor-diff pattern) — clone **lightly**, drop fail-closed machinery |
| `.planning/phases/238-.../PROVENANCE-MAP.md` | evidence artifact (markdown) | n/a | none (artifact-only) | n/a — prior read-only phase evidence (212/222/225) is the shape reference |

## Pattern Assignments

### `scripts/phase238-egress-proof.sh` (utility, read-only proof script)

**Primary analog:** `scripts/phase231-migration-held.sh` (read in full)
**Secondary analog:** `scripts/phase225-dscp-ingress-capture.sh` (header/banner only)

Clone the *structure* of phase231, not its checks. phase231 runs health/metrics/journal/qdisc
checks; phase238 runs `ip route get` + `ip rule` egress proofs. The harness skeleton is identical;
swap the per-WAN check functions.

**Header + read-only posture banner + `set -euo pipefail`** — combine phase231's usage line
(`phase231:1-5`) with phase225's prose read-only banner (`phase225:1-9`). phase231 header:
```bash
#!/usr/bin/env bash
# phase231-migration-held.sh - Read-only migration-held evaluator for SOAK-01.
# Usage: scripts/phase231-migration-held.sh [--wan spectrum|att|all] [--window-hours N] [--json]

set -euo pipefail
```
phase225 banner prose to adapt (`phase225:2-8`): a 3-line block stating the script is read-only,
uses bounded SSH reads, and mutates nothing. For 238 the banner must state: "Read-only. Proves
`fping -S <source_ip>` egress per WAN via `ip route get`/`ip rule`. No worktree, prod, CAKE-mode,
unit, or controller-source mutation." (Mirrors phase237's posture sentence at `phase237:23-25`.)

**Per-WAN TARGETS array** (`phase231:7-10`) — the load-bearing pattern. phase231 packs pipe-delimited
fields and unpacks with `IFS='|' read`:
```bash
TARGETS=(
    "kevin@10.10.110.223|spectrum|10.10.110.223|spec-router|spec-modem"
    "kevin@10.10.110.223|att|10.10.110.227|att-router|att-modem"
)
```
For 238, repack to carry `source_ip` (or `<none>` for Spectrum) + the reflector list per the
RESEARCH skeleton. **Pitfall (RESEARCH Pitfall 3):** Spectrum has no `ping_source_ip` — its proof is
`ip route get <reflector>` (default route), only ATT uses `from 10.10.110.227`. Encode `<none>` as
a sentinel and branch the `ip route get` invocation on it.

**Read-only SSH helper** (`phase231:22, :85-88`):
```bash
SSH_OPTS=(-o ConnectTimeout=10 -o BatchMode=yes)

ssh_readonly() {
    local ssh_target="$1" remote_cmd="$2"
    ssh -n "${SSH_OPTS[@]}" "$ssh_target" "$remote_cmd"
}
```
The `ssh -n` (no stdin) + `BatchMode=yes` (no password prompt) combo is the read-only posture.
Per CONTEXT D-08 + credential memory: if any read trips a guardrail, the script may instead emit
the exact `! ssh cake-shaper '…'` commands for the operator to paste rather than escalating creds.

**Arg parsing + `--wan`/`--json` flags** (`phase231:401-409`):
```bash
while [[ $# -gt 0 ]]; do
    case "$1" in
        --wan) WAN_FILTER="${2:-}"; shift 2 ;;
        --window-hours) WINDOW_HOURS="${2:-}"; shift 2 ;;
        --json) JSON_MODE="1"; shift ;;
        --help|-h) usage; exit 0 ;;
        *) echo "ERROR: unknown argument: $1" >&2; usage >&2; exit 2 ;;
    esac
done
```
Drop `--window-hours`; keep `--wan spectrum|att|all` and `--json`. Add `--help`.

**Arg validation against fixed allowlist** (`phase231:59-64`) — ASVS V5 control (RESEARCH Security):
```bash
validate_wan() {
    case "$WAN_FILTER" in
        spectrum|att|all) ;;
        *) echo "ERROR: --wan must be spectrum, att, or all" >&2; exit 2 ;;
    esac
}
```

**Command preflight** (`phase231:44-50, :413-415`):
```bash
require_command() {
    local cmd="$1"
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo "ERROR: required command missing: $cmd" >&2
        exit 2
    fi
}
# ... then: require_command python3; require_command ssh
```
For 238 also `require_command ip` is run on the *remote* host (inside the SSH command), so the
local preflight checks `python3` + `ssh` only.

**JSON assembly via inline `python3 - "$arg" <<'PY'`** (`phase231:94-106`, `status_json`) — the house
pattern for shell→JSON. Reuse verbatim for per-WAN/per-reflector egress records:
```bash
status_json() {
    local pass="$1" evidence="$2" error="$3"
    python3 - "$pass" "$evidence" "$error" <<'PY'
import json
import sys
passed, evidence, error = sys.argv[1:]
payload = {"pass": passed == "true", "evidence": evidence}
if error:
    payload["error"] = error
print(json.dumps(payload, separators=(",", ":")))
PY
}
```
Also `json_string` (`phase231:90-92`) for safe string escaping.

**mktemp + trap cleanup** (`phase231:418-419`):
```bash
tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT
```

**Main loop: TARGETS unpack + WAN filter + NDJSON accumulate** (`phase231:423-429`):
```bash
for target in "${TARGETS[@]}"; do
    IFS='|' read -r ssh_target wan health_ip dl_if ul_if <<<"$target"
    if [[ "$WAN_FILTER" != "all" && "$WAN_FILTER" != "$wan" ]]; then
        continue
    fi
    evaluate_wan "$ssh_target" "$wan" ... >>"$results_file"
done
```

**Dual output mode + exit-code verdict** (`phase231:436-473`) — `--json` emits the full array;
default prints a human summary; final `python3` block sets exit 0 iff every WAN's verdict is PASS.
For 238: PASS iff every resolved egress `dev`/path matches the intended WAN interface. The
`ip rule` table is captured once per host as context (CONTEXT D-07), not pass/fail-scored.

**Core 238-specific operation (no analog — new kernel queries, RESEARCH Code Examples):**
```bash
# ATT (source-bound): expect egress path toward ATT (FORCE_OUT_ATT)
ip route get 1.1.1.1 from 10.10.110.227
# Spectrum (default route, no source IP):
ip route get 1.1.1.1
# Policy table context, once per host (D-07):
ip rule
```
These are pure read-only kernel queries — no `ip ... add/del`, no sudo-write, no unit control
(RESEARCH Pitfall 5).

---

### `scripts/phase238-safe17-boundary-check.sh` (utility, read-only git assertion)

**Analog:** `scripts/phase237-safe16-boundary-check.sh` (read in full)

Clone **lightly** (CONTEXT D-09 / RESEARCH "SAFE-17 Lightweight Boundary Assertion"). Reuse the
controller-path target list and the anchor-diff/`status --porcelain` pattern. **Do NOT** clone the
fail-closed machinery: per-file sha256 hashing of `backends/`, the `att.yaml` special-case, the
union-expansion of directory targets, or the narrowed v1.53 allowlist — all of which arrive in
Phase 239's full verifier.

**Header + read-only posture + `set -euo pipefail`** (`phase237:1-9`):
```bash
#!/usr/bin/env bash
#
# Phase 238 SAFE-17 lightweight boundary check.
# Read-only git evidence: controller-path is byte-unchanged vs the v1.52 anchor.

set -euo pipefail
```

**Anchor default + out path** (`phase237:11-12`) — change anchor to `v1.52` (RESEARCH: latest
milestone tag; v1.53 has no tag yet) and point `OUT` at the 238 evidence dir:
```bash
ANCHOR="v1.52"
OUT=".planning/phases/238-rtt-provenance-verification-read-only-entry-gate/evidence/safe17-boundary-238.json"
```

**Posture banner in usage()** (`phase237:23-25`) — copy verbatim:
```
Posture: read-only git inspection only. The script does not modify the worktree,
index, refs, external gear, CAKE mode, or controller source.
```

**Arg parsing + validation** (`phase237:36-48`):
```bash
while [[ $# -gt 0 ]]; do
    case "$1" in
        --anchor) ANCHOR="${2:-}"; shift 2 ;;
        --out) OUT="${2:-}"; shift 2 ;;
        --help|-h) usage; exit 0 ;;
        *) echo "ERROR: unknown argument: $1" >&2; usage >&2; exit 2 ;;
    esac
done

if [[ -z "$ANCHOR" || -z "$OUT" ]]; then
    usage >&2
    exit 2
fi
```

**Command preflight + mkdir** (`phase237:50-55`):
```bash
require_command date; require_command git; require_command mkdir; require_command python3
mkdir -p "$(dirname "$OUT")"
```

**Controller-path target list** (`phase237:67-75`) — this is the load-bearing reusable asset; it
defines what "controller-path" means and must stay consistent across SAFE phases:
```python
controller_targets = [
    "src/wanctl/wan_controller.py",
    "src/wanctl/wan_controller_state.py",
    "src/wanctl/queue_controller.py",
    "src/wanctl/cake_signal.py",
    "src/wanctl/alert_engine.py",
    "src/wanctl/fusion_healer.py",
    "src/wanctl/backends/",
]
```
**Drop** `att_config = "configs/att.yaml"` (`phase237:76`) and all att-special-case handling — not
needed for the lightweight 238 assertion.

**git helper + numstat/dirty pattern** (`phase237:79-91, :118-153`) — the diff machinery to keep:
```python
def git(*args, check=True):
    result = subprocess.run(["git", *args], check=False, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if check and result.returncode != 0:
        raise SystemExit(f"git {' '.join(args)} failed with {result.returncode}: {result.stderr.strip()}")
    return result.stdout
```
Reuse `parse_numstat` (`:118-128`), `diff_for_path` (`:131-146`), `dirty_for_path` (`:149-153`).
**Drop** `object_id_at_anchor`/`object_id_at_worktree` (`:156-180`) and `expand_protected_files`
(`:108-115`) — per-file sha256 hashing is Phase 239 machinery.

**Pass condition (simplified)** — phase237 ANDs five clauses (`:233-238`); 238 keeps only the
diff/dirty clauses, drops hash + att clauses:
```python
committed_clean = not any(row["committed"]["lines"] for row in per_path_diff.values())
staged_clean    = not any(row["staged"]["lines"] for row in per_path_diff.values())
dirty_tree_clean = not dirty_tree["status_porcelain"] and not dirty_tree["untracked"]
passed = committed_clean and staged_clean and dirty_tree_clean
```

**JSON record + fail-on-stderr + success echo** (`phase237:240-277`) — keep the record-write,
`raise SystemExit(1)` on failure, and the final `echo "...passed: $OUT"`. Trim the record fields to
match the simplified pass set (`anchor`, `baseline_commit`, `head_commit`, `protected_paths`,
`per_path_diff`, `dirty_tree`, `committed_clean`, `staged_clean`, `dirty_tree_clean`, `passed`,
`checked_at`, `notes`). Update `notes` to "SAFE-17 lightweight read-only boundary check vs v1.52;
full fail-closed verifier + narrowed allowlist deferred to Phase 239."

**Core 238 operation (RESEARCH Code Examples — what the script proves):**
```bash
git diff --numstat v1.52 HEAD -- <controller_targets>   # expect EMPTY
git status --porcelain -- <controller_targets>          # expect EMPTY
```

---

### `.planning/phases/238-.../PROVENANCE-MAP.md` (evidence artifact)

**No code analog.** This is a markdown evidence artifact, not code. The shape reference is prior
read-only milestone evidence (Phases 212 inventory, 222 steering drift audit, 225 DSCP ingress
trace) — same pattern: capture live read-only evidence into a phase-dir artifact and prove zero
mutation.

Required embedded content (CONTEXT D-05/D-06, RESEARCH PROV-01/PROV-02):
- **(a)** Live `/health` `measurement` block capture from the prod cake-shaper (both WANs), obtained
  read-only — operator runs `! ssh cake-shaper 'curl -fsS --max-time 5 http://...:9101/health'`
  (RESEARCH Code Examples / CONTEXT D-06a). Capture the prod (bridge) shape; note `health_check.py`
  shape for contrast.
- **(b)** Verified code-path trace proving steering's live RTT source (`run_cycle → _measure_current_rtt_with_retry → measure_current_rtt → load_live_rtt`, reading `/health measurement.raw_rtt_ms`) and that the constructed `RTTMeasurement` is dead (`daemon.py:2554`/`:1137`, never invoked). Cite file:line per RESEARCH Code-Path Trace.
- **(c)** Deployed bridge identity + repo-vs-prod reconciliation: confirm `/usr/local/sbin/cake-autorate-{spectrum,att}-state-bridge` is the live `raw_rtt_ms` producer; operator sha-compares deployed binary vs repo `deploy/scripts/...` (RESEARCH Pitfall 2 / Open Question 1).
- **A/B recommendation with evidence** (PROV-02): present BOTH interpretations honestly (D-02),
  recommend on the fidelity rubric (D-03) — lean A, document the `source_ip`-wiring tradeoff —
  and leave the binding selection to the operator (D-01). Surface the crux: bridge `raw_rtt_ms` is
  carried-forward `ewma.load_rtt` / static `DEFAULT_BASELINE_RTT` (~22.5ms), not a fresh sample
  (RESEARCH Pitfall 1).

## Shared Patterns

### Read-only posture banner
**Source:** `scripts/phase237-safe16-boundary-check.sh:23-25` (prose) + `scripts/phase225-dscp-ingress-capture.sh:2-8` (header block)
**Apply to:** both new scripts
Every read-only proof script in this lineage carries an explicit "does not modify worktree, index,
refs, external gear, CAKE mode, or controller source" statement plus `set -euo pipefail`. Combined
with `ssh -n -o BatchMode=yes` and only-read commands (`ip route get`/`ip rule`/`curl`/`git` reads),
this is the no-mutation contract (RESEARCH Pitfall 5, Security: Tampering mitigation).

### `set -euo pipefail` harness header
**Source:** `phase231:5`, `phase237:9`, `phase225:9`
**Apply to:** both new scripts
Mandatory first executable line after the header comment block.

### Arg-allowlist validation (no shell injection)
**Source:** `scripts/phase231-migration-held.sh:59-64` (`validate_wan`)
**Apply to:** `phase238-egress-proof.sh` (`--wan`), and the unknown-arg `*)` case in both scripts
ASVS V5 control. Validate every flag against a fixed `case` allowlist; quote all expansions; never
interpolate untrusted input into the SSH command string.

### Inline python3 JSON assembly
**Source:** `scripts/phase231-migration-held.sh:90-106` (`json_string`, `status_json`)
**Apply to:** `phase238-egress-proof.sh` (egress records); the boundary-check uses the heavier
single-block `python3 - "$ANCHOR" "$OUT" <<'PY'` form from `phase237:57`
House pattern for shell→JSON. Pass shell values as `sys.argv`, never via string interpolation.

### `require_command` preflight
**Source:** `phase231:44-50`, `phase237:28-34`
**Apply to:** both new scripts
Fail fast (exit 1/2) if a required local tool is missing.

### Per-WAN TARGETS array + `IFS='|' read` unpack
**Source:** `scripts/phase231-migration-held.sh:7-10, :423-429`
**Apply to:** `phase238-egress-proof.sh`
Both WANs SSH to the same cake-shaper host; the per-WAN differentiator (`source_ip`, reflectors) is
packed pipe-delimited and unpacked in the main loop, with a `--wan` filter skip.

## No Analog Found

| File | Role | Reason |
|------|------|--------|
| `.planning/phases/238-.../PROVENANCE-MAP.md` | evidence artifact | Markdown evidence, not code. Shape reference is prior read-only phase evidence (212/222/225), not a code analog. No excerpts to copy. |

(Both new *scripts* have exact analogs; only the artifact lacks one.)

## Metadata

**Analog search scope:** `scripts/` (proof-script lineage), confirmed against RESEARCH Sources
**Files read this session:** `scripts/phase231-migration-held.sh` (full, 474 lines),
`scripts/phase237-safe16-boundary-check.sh` (full, 277 lines),
`scripts/phase225-dscp-ingress-capture.sh` (header, :1-45)
**Pattern extraction date:** 2026-06-14
