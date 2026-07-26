#!/bin/bash
# Install wanctl and its exact frozen runtime from pyproject.toml + uv.lock.
set -euo pipefail

REPO_ROOT="${1:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
UV_VERSION="${WANCTL_UV_VERSION:-0.11.29}"
UV_BIN="${WANCTL_UV_BIN:-}"
PIP_BIN="${WANCTL_PIP_BIN:-pip3}"
PYTHON_BIN="${WANCTL_PYTHON_BIN:-python3}"

fail() {
    printf 'wanctl runtime install failed: %s\n' "$1" >&2
    exit 1
}

[[ -f "$REPO_ROOT/pyproject.toml" ]] || fail "missing pyproject.toml"
[[ -f "$REPO_ROOT/uv.lock" ]] || fail "missing uv.lock"
command -v "$PIP_BIN" >/dev/null 2>&1 || fail "pip3 is required"
command -v "$PYTHON_BIN" >/dev/null 2>&1 || fail "python3 is required"

if [[ -z "$UV_BIN" ]]; then
    if command -v uv >/dev/null 2>&1; then
        UV_BIN=$(command -v uv)
    else
        "$PIP_BIN" install --break-system-packages "uv==$UV_VERSION"
        UV_BIN=$(command -v uv) || fail "uv bootstrap did not install an executable"
    fi
fi
command -v "$UV_BIN" >/dev/null 2>&1 || fail "uv executable not found"

runtime_requirements=$(mktemp)
trap 'rm -f "$runtime_requirements"' EXIT

"$UV_BIN" export \
    --project "$REPO_ROOT" \
    --frozen \
    --no-dev \
    --all-extras \
    --no-emit-project \
    --no-hashes \
    --output-file "$runtime_requirements"

"$PIP_BIN" install --break-system-packages --requirement "$runtime_requirements"
"$PIP_BIN" install --break-system-packages --no-deps "$REPO_ROOT"

"$PYTHON_BIN" -c 'import wanctl, paramiko, requests, yaml'
printf 'wanctl frozen runtime installed successfully\n'
