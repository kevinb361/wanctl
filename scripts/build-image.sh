#!/bin/bash
# Build a revision-identified local wanctl image from a clean Git tree.
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
REPO_ROOT="${WANCTL_REPO_ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"

command -v git >/dev/null 2>&1 || { echo "git is required" >&2; exit 1; }
command -v python3 >/dev/null 2>&1 || { echo "python3 is required" >&2; exit 1; }
command -v docker >/dev/null 2>&1 || { echo "docker is required" >&2; exit 1; }
command -v tar >/dev/null 2>&1 || { echo "tar is required" >&2; exit 1; }

[[ -z $(git -C "$REPO_ROOT" status --porcelain --untracked-files=all) ]] || {
    echo "refusing to build from a dirty Git worktree" >&2
    exit 1
}

revision=$(git -C "$REPO_ROOT" rev-parse HEAD)
[[ "$revision" =~ ^[0-9a-f]{40}$ ]] || {
    echo "Git did not return a full lowercase revision" >&2
    exit 1
}
version=$(python3 -c \
    'import pathlib, sys, tomllib; print(tomllib.loads(pathlib.Path(sys.argv[1]).read_text())["project"]["version"])' \
    "$REPO_ROOT/pyproject.toml" 2>/dev/null)
[[ -n "$version" ]] || { echo "project release version is empty" >&2; exit 1; }

image_tag="${1:-wanctl:${version}-${revision:0:12}}"
build_context=$(mktemp -d)
trap 'rm -rf "$build_context"' EXIT
git -C "$REPO_ROOT" archive HEAD | tar -x -C "$build_context"

docker build --pull \
    --build-arg "WANCTL_RELEASE_VERSION=$version" \
    --build-arg "WANCTL_BUILD_REVISION=$revision" \
    --label "org.opencontainers.image.source-revision=$revision" \
    -f "$build_context/docker/Dockerfile" \
    -t "$image_tag" \
    "$build_context"
