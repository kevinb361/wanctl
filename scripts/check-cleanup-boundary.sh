#!/usr/bin/env bash
#
# BOUND-01 cleanup boundary guard.
#
# Encodes the WANCTL_CAKE_AUTORATE_FUTURE.md no-delete list as a concrete
# manifest for v1.51 sweep work. Posture is read-only: git plumbing and
# worktree hashing only; no worktree, index, ref, service, qdisc, SSH, sudo, or
# external-gear mutation. Run on demand and before/after every Phase 233 sweep
# commit.
#
# Exit contract:
#   0 — clean
#   1 — BOUND-01 VIOLATION (denylisted surface missing or immutable drift)
#   2 — usage or git/anchor error

set -euo pipefail

ANCHOR="v1.50"
OUT=".planning/phases/232-cleanup-boundary-guard-tooling-fixes/evidence/cleanup-boundary-check.json"
PRINT_MANIFEST=0

usage() {
    cat <<'EOF'
Usage:
  scripts/check-cleanup-boundary.sh [--anchor REF] [--out PATH]
  scripts/check-cleanup-boundary.sh --print-manifest

Options:
  --anchor REF       Git anchor for immutable-file comparison (default: v1.50)
  --out PATH         JSON evidence output path
  --print-manifest   Print manifest rows as class<TAB>path<TAB>policy and exit 0
  --help, -h         Show this help

Posture: read-only git/worktree inspection only. The script does not modify the
worktree, index, refs, services, qdiscs, RouterOS, or production state.
EOF
}

require_command() {
    local cmd="$1"
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo "ERROR: required command not found: $cmd" >&2
        exit 2
    fi
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --anchor)
            ANCHOR="${2:-}"
            shift 2
            ;;
        --out)
            OUT="${2:-}"
            shift 2
            ;;
        --print-manifest)
            PRINT_MANIFEST=1
            shift
            ;;
        --help|-h)
            usage
            exit 0
            ;;
        *)
            echo "ERROR: unknown argument: $1" >&2
            usage >&2
            exit 2
            ;;
    esac
done

if [[ -z "$ANCHOR" || -z "$OUT" ]]; then
    usage >&2
    exit 2
fi

require_command git
require_command mkdir
require_command python3

if [[ "$PRINT_MANIFEST" -ne 1 ]] && ! git rev-parse --verify "${ANCHOR}^{commit}" >/dev/null 2>&1; then
    echo "ERROR: anchor '${ANCHOR}' not found in this repository." >&2
    exit 2
fi

if [[ "$PRINT_MANIFEST" -ne 1 ]]; then
    mkdir -p "$(dirname "$OUT")"
fi

python3 - "$ANCHOR" "$OUT" "$PRINT_MANIFEST" <<'PY'
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

anchor = sys.argv[1]
out_path = Path(sys.argv[2])
print_manifest = sys.argv[3] == "1"

# Policy meanings:
# - must-match-anchor: file must exist and, when present in the anchor tree,
#   worktree blob must equal the anchor blob.
# - must-exist: file must exist; content drift is allowed because another v1.51
#   task or living-doc policy authorizes annotation/change, but deletion remains
#   forbidden.
manifest = [
    ("native-controller", "src/wanctl/autorate_continuous.py", "must-match-anchor"),
    ("native-deploy-path", "deploy/systemd/wanctl@.service", "must-match-anchor"),
    ("native-deploy-path", "scripts/install.sh", "must-match-anchor"),
    ("native-deploy-path", "scripts/install-systemd.sh", "must-match-anchor"),
    ("native-deploy-path", "scripts/deploy.sh", "must-match-anchor"),
    ("native-tests", "tests/test_autorate_continuous.py", "must-match-anchor"),
    ("native-tests", "tests/test_autorate_config.py", "must-match-anchor"),
    ("native-tests", "tests/test_autorate_baseline_bounds.py", "must-match-anchor"),
    ("native-tests", "tests/test_autorate_entry_points.py", "must-match-anchor"),
    ("native-tests", "tests/test_autorate_error_recovery.py", "must-match-anchor"),
    ("native-tests", "tests/test_autorate_metrics_recording.py", "must-match-anchor"),
    ("native-tests", "tests/test_autorate_telemetry.py", "must-match-anchor"),
    ("native-config-validation", "src/wanctl/autorate_config.py", "must-match-anchor"),
    ("native-config-validation", "src/wanctl/config_base.py", "must-match-anchor"),
    ("native-config-validation", "src/wanctl/config_validation_utils.py", "must-match-anchor"),
    ("native-config-validation", "src/wanctl/check_config.py", "must-match-anchor"),
    ("native-config-validation", "src/wanctl/check_config_validators.py", "must-match-anchor"),
    ("native-config-validation", "tests/test_check_config.py", "must-match-anchor"),
    ("native-config-validation", "tests/test_config_base.py", "must-match-anchor"),
    ("native-config-validation", "tests/test_config_validation_utils.py", "must-match-anchor"),
    # FIX-01 / Phase 231 review CR-01 authorizes content drift; removal remains forbidden.
    ("rollback-commands-docs", "scripts/phase231-rollback.sh", "must-exist"),
    ("rollback-commands-docs", "scripts/phase227-rollback.sh", "must-match-anchor"),
    # FIX-01 proof + WR-02 authorizes content drift; removal remains forbidden.
    ("rollback-commands-docs", "tests/test_phase231_rollback.py", "must-exist"),
    # SWEEP-02 residual doc verification may annotate mode notes; deletion remains forbidden.
    ("rollback-commands-docs", "docs/UPGRADING.md", "must-exist"),
    # SWEEP-02 residual doc verification may annotate mode notes; deletion remains forbidden.
    ("rollback-commands-docs", "docs/DEPLOYMENT.md", "must-exist"),
    # Living planning doc; appended trial logs are normal. Absence is still a violation.
    ("rollback-commands-docs", ".planning/cake-autorate-trials/WANCTL_CAKE_AUTORATE_FUTURE.md", "must-exist"),
]


def git(*args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        ["git", *args],
        check=False,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if check and result.returncode != 0:
        raise SystemExit(
            f"git {' '.join(args)} failed with {result.returncode}: {result.stderr.strip()}"
        )
    return result


def anchor_blob(path: str) -> str | None:
    result = git("rev-parse", f"{anchor}:{path}", check=False)
    return result.stdout.strip() if result.returncode == 0 else None


def worktree_blob(path: str) -> str | None:
    if not Path(path).is_file():
        return None
    result = git("hash-object", path, check=False)
    return result.stdout.strip() if result.returncode == 0 else None


def is_tracked(path: str) -> bool:
    return git("ls-files", "--error-unmatch", "--", path, check=False).returncode == 0


if print_manifest:
    for row in manifest:
        print("\t".join(row))
    raise SystemExit(0)

checks = []
violations = []

for item_class, path, policy in manifest:
    path_obj = Path(path)
    exists = path_obj.exists()
    anchor_oid = anchor_blob(path)
    worktree_oid = worktree_blob(path)
    anchor_present = anchor_oid is not None
    tracked = is_tracked(path)

    if not exists:
        status = "MISSING"
    elif policy == "must-match-anchor" and anchor_present and worktree_oid != anchor_oid:
        status = "MODIFIED"
    elif policy == "must-exist" and anchor_present and worktree_oid != anchor_oid:
        status = "allowlisted-modified"
    else:
        status = "ok"

    row = {
        "class": item_class,
        "path": path,
        "policy": policy,
        "anchor_present": anchor_present,
        "exists": exists,
        "tracked": tracked,
        "status": status,
    }
    checks.append(row)

    if status in {"MISSING", "MODIFIED"}:
        violations.append(row)

record = {
    "proof_type": "bound01-cleanup-boundary-check",
    "captured_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
    "anchor": anchor,
    "overall_pass": not violations,
    "checks": checks,
}

out_path.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")

for row in violations:
    print(f"BOUND-01 VIOLATION: {row['path']} {row['status']} ({row['policy']})", file=sys.stderr)

if violations:
    raise SystemExit(1)
PY

echo "cleanup boundary check passed: $OUT"
