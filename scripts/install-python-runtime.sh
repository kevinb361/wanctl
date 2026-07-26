#!/bin/bash
# Install wanctl and its exact frozen runtime from pyproject.toml + uv.lock.
set -euo pipefail

REPO_ROOT="${1:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"
UV_VERSION="${WANCTL_UV_VERSION:-0.11.29}"
UV_BIN="${WANCTL_UV_BIN:-}"
PIP_BIN="${WANCTL_PIP_BIN:-pip3}"
PYTHON_BIN="${WANCTL_PYTHON_BIN:-python3}"
REQUESTED_REVISION="${WANCTL_BUILD_REVISION:-}"

fail() {
    printf 'wanctl runtime install failed: %s\n' "$1" >&2
    exit 1
}

resolve_build_revision() {
    local git_revision=""
    if command -v git >/dev/null 2>&1 \
        && git -C "$REPO_ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
        [[ -z $(git -C "$REPO_ROOT" status --porcelain --untracked-files=all) ]] \
            || fail "Git worktree must be clean before installation"
        git_revision=$(git -C "$REPO_ROOT" rev-parse HEAD)
        if [[ -n "$REQUESTED_REVISION" && "$REQUESTED_REVISION" != "$git_revision" ]]; then
            fail "requested revision does not match Git HEAD"
        fi
        printf '%s\n' "$git_revision"
        return
    fi
    [[ -n "$REQUESTED_REVISION" ]] \
        || fail "WANCTL_BUILD_REVISION is required outside a Git worktree"
    printf '%s\n' "$REQUESTED_REVISION"
}

[[ -f "$REPO_ROOT/pyproject.toml" ]] || fail "missing pyproject.toml"
[[ -f "$REPO_ROOT/uv.lock" ]] || fail "missing uv.lock"
[[ -f "$REPO_ROOT/src/wanctl/_build_identity.py" ]] || fail "missing build identity module"
command -v "$PIP_BIN" >/dev/null 2>&1 || fail "pip3 is required"
command -v "$PYTHON_BIN" >/dev/null 2>&1 || fail "python3 is required"

BUILD_REVISION=$(resolve_build_revision)
[[ "$BUILD_REVISION" =~ ^[0-9a-f]{40}$ ]] || fail "build revision must be a full lowercase Git SHA"
RELEASE_VERSION=$("$PYTHON_BIN" -c \
    'import pathlib, sys, tomllib; print(tomllib.loads(pathlib.Path(sys.argv[1]).read_text())["project"]["version"])' \
    "$REPO_ROOT/pyproject.toml")
[[ -n "$RELEASE_VERSION" ]] || fail "project release version is empty"

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
staging_root=$(mktemp -d)
cleanup() {
    rm -f "$runtime_requirements"
    rm -rf "$staging_root"
}
trap cleanup EXIT

"$UV_BIN" export \
    --project "$REPO_ROOT" \
    --frozen \
    --no-dev \
    --all-extras \
    --no-emit-project \
    --no-hashes \
    --output-file "$runtime_requirements"

cp "$REPO_ROOT/pyproject.toml" "$staging_root/pyproject.toml"
cp -a "$REPO_ROOT/src" "$staging_root/src"
printf '"""Generated immutable source revision."""\n\nBUILD_REVISION = "%s"\n' \
    "$BUILD_REVISION" > "$staging_root/src/wanctl/_build_identity.py"

"$PIP_BIN" install --break-system-packages --requirement "$runtime_requirements"
"$PIP_BIN" install --break-system-packages --no-deps "$staging_root"

WANCTL_EXPECTED_VERSION="$RELEASE_VERSION" WANCTL_EXPECTED_REVISION="$BUILD_REVISION" \
    "$PYTHON_BIN" -c \
    'import os, wanctl, paramiko, requests, yaml; assert wanctl.__version__ == os.environ["WANCTL_EXPECTED_VERSION"]; assert wanctl.__revision__ == os.environ["WANCTL_EXPECTED_REVISION"]'
printf 'wanctl frozen runtime installed successfully: %s (%s)\n' \
    "$RELEASE_VERSION" "$BUILD_REVISION"
