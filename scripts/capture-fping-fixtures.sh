#!/usr/bin/env bash
# Operator wrapper for real fping fixture capture.
#
# Non-mutating posture: this script does not alter routing, CAKE, qdisc, tc,
# RouterOS, services, or shaping state.  If partial-loss needs external loss
# induction, the operator is responsible for applying and reverting it outside
# this helper.

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd -- "${SCRIPT_DIR}/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-${REPO_ROOT}/.venv/bin/python}"

usage() {
    cat <<'EOF'
Usage:
  scripts/capture-fping-fixtures.sh [options]

Options:
  --source-ip IP              WAN source IP to pass as fping -S
  --reflectors "H1 H2 ..."    Normal reflector list (default: "1.1.1.1 8.8.8.8")
  --lossy-reflector HOST      Operator-selected lossy/distant target for partial_loss
  --scenario NAME             reply|total_loss|partial_loss|partial_line|banner_noise|process_death|all
  --out-dir DIR               Fixture output directory (default: tests/fixtures/fping)
  --print-command             Print byte-identical runtime fping argv and exit; does not require fping
  --redact-source             Redact source IP / final reflector in metadata command
  --fping-bin PATH            Override fping binary path for command parity/capture
  --help, -h                  Show this help

Safety:
  This helper performs NO routing, CAKE, shaping, tc/qdisc, RouterOS, service,
  or firewall mutation. total_loss uses TEST-NET 192.0.2.1. Any tc/netem or
  other loss induction for partial_loss is manual operator responsibility and
  must be reverted by the operator outside this script.
EOF
}

require_command() {
    local cmd="$1"
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo "ERROR: required command not found: $cmd" >&2
        exit 2
    fi
}

for arg in "$@"; do
    case "$arg" in
        --help|-h)
            usage
            exit 0
            ;;
    esac
done

if [[ ! -x "$PYTHON_BIN" ]]; then
    PYTHON_BIN="python3"
fi

require_command "$PYTHON_BIN"

cat >&2 <<'EOF'
wanctl fping fixture capture preflight:
  - NON-MUTATING: no routing, CAKE, shaping, tc/qdisc, RouterOS, service, or firewall changes.
  - total_loss uses TEST-NET 192.0.2.1; no route change is performed.
  - partial_loss external loss induction, if needed, is manual operator responsibility and must be reverted outside this helper.
EOF

exec "$PYTHON_BIN" "${SCRIPT_DIR}/capture_fping_fixtures.py" "$@"
