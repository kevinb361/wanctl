#!/usr/bin/env bash

set -euo pipefail

THRESHOLDS_PATH="scripts/phase245-thresholds.json"

usage() {
    cat <<'EOF'
Usage:
  scripts/phase245-prereg-provenance.sh record
  scripts/phase245-prereg-provenance.sh assert-descends <prereg_commit> <evidence_commit>
  scripts/phase245-prereg-provenance.sh assert-blob-unchanged <expected_blob_sha>
EOF
}

record() {
    local thresholds_blob_sha prereg_commit_sha
    thresholds_blob_sha="$(git rev-parse "HEAD:${THRESHOLDS_PATH}")"
    prereg_commit_sha="$(git rev-parse HEAD)"
    python3 - "$thresholds_blob_sha" "$prereg_commit_sha" "$THRESHOLDS_PATH" <<'PY'
import json
import sys

thresholds_blob_sha, prereg_commit_sha, thresholds_path = sys.argv[1:]
print(json.dumps({
    "thresholds_blob_sha": thresholds_blob_sha,
    "prereg_commit_sha": prereg_commit_sha,
    "thresholds_path": thresholds_path,
}, indent=2, sort_keys=True))
PY
}

assert_descends() {
    local prereg_commit="${1:-}"
    local evidence_commit="${2:-}"
    if [[ -z "$prereg_commit" || -z "$evidence_commit" ]]; then
        usage >&2
        exit 2
    fi
    if ! git merge-base --is-ancestor "$prereg_commit" "$evidence_commit"; then
        echo "ERROR: evidence commit $evidence_commit does not descend from prereg commit $prereg_commit" >&2
        exit 1
    fi
}

assert_blob_unchanged() {
    local expected_blob_sha="${1:-}"
    if [[ -z "$expected_blob_sha" ]]; then
        usage >&2
        exit 2
    fi
    local actual_blob_sha
    actual_blob_sha="$(git rev-parse "HEAD:${THRESHOLDS_PATH}")"
    if [[ "$actual_blob_sha" != "$expected_blob_sha" ]]; then
        echo "ERROR: thresholds blob changed: expected $expected_blob_sha, got $actual_blob_sha" >&2
        exit 1
    fi
}

case "${1:-}" in
    record) record ;;
    assert-descends) shift; assert_descends "$@" ;;
    assert-blob-unchanged) shift; assert_blob_unchanged "$@" ;;
    --help|-h|"") usage; [[ "${1:-}" ]] || exit 2 ;;
    *) echo "ERROR: unknown subcommand: $1" >&2; usage >&2; exit 2 ;;
esac
