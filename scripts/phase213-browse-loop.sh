#!/usr/bin/env bash
# Phase 213 curl-browse loop. D-02 normal-browsing surface; D-09/D-10
# evidence-only traffic generation from the dev VM. Records TTFB, total time,
# payload size, and curl exit code for each source-bound request.

set -euo pipefail

usage() {
  cat <<'EOF'
Usage:
  scripts/phase213-browse-loop.sh --output <csv-path> [--duration <sec>] [--local-bind <ip>] [--sites <csv>]

Options:
  --output <path>        CSV output path (required)
  --duration <seconds>   Run duration in seconds (default: 60)
  --local-bind <ip>      Source IP for curl --interface (default: 10.10.110.233)
  --sites <csv>          Comma-separated URL rotation override
  --help, -h             Show this help
EOF
}

OUTPUT=""
DURATION="60"
LOCAL_BIND="10.10.110.233"
SITES_CSV=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --output)
      OUTPUT="${2:-}"
      shift 2
      ;;
    --duration)
      DURATION="${2:-}"
      shift 2
      ;;
    --local-bind)
      LOCAL_BIND="${2:-}"
      shift 2
      ;;
    --sites)
      SITES_CSV="${2:-}"
      shift 2
      ;;
    --help|-h)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [[ -z "$OUTPUT" ]]; then
  echo "phase213-browse-loop: --output is required" >&2
  usage >&2
  exit 2
fi

if ! [[ "$DURATION" =~ ^[0-9]+$ ]]; then
  echo "phase213-browse-loop: --duration must be a non-negative integer; got '${DURATION}'" >&2
  exit 2
fi

if ! command -v curl >/dev/null 2>&1; then
  echo "phase213-browse-loop: curl is required" >&2
  exit 2
fi

if [[ -n "$SITES_CSV" ]]; then
  IFS=',' read -r -a SITES <<< "$SITES_CSV"
else
  SITES=(
    "https://www.google.com/"
    "https://www.cloudflare.com/"
    "https://github.com/"
    "https://www.wikipedia.org/"
    "https://news.ycombinator.com/"
    "https://www.bbc.com/news"
    "https://i.imgur.com/aB6Z9zN.jpg"
  )
fi

if [[ "${#SITES[@]}" -eq 0 ]]; then
  echo "phase213-browse-loop: at least one site is required" >&2
  exit 2
fi

mkdir -p "$(dirname "$OUTPUT")"
printf 'ts_utc,site,http_code,time_starttransfer,time_total,size_download,exit_code\n' > "$OUTPUT"

cache_bust_url() {
  local site="$1"
  local bust="cache_bust=$(date +%s%N)"
  if [[ "$site" == *\?* ]]; then
    printf '%s&%s' "$site" "$bust"
  else
    printf '%s?%s' "$site" "$bust"
  fi
}

T_END=$(($(date +%s) + DURATION))
i=0

while [[ "$(date +%s)" -lt "$T_END" ]]; do
  SITE="${SITES[$((i % ${#SITES[@]}))]}"
  URL="$(cache_bust_url "$SITE")"
  TS="$(date -u -Iseconds)"
  OUT=""
  EC=0

  OUT=$(curl --interface "$LOCAL_BIND" --silent --max-time 10 \
    --write-out '%{http_code},%{time_starttransfer},%{time_total},%{size_download}' \
    --output /dev/null "$URL" 2>/dev/null) || EC=$?

  printf '%s,%s,%s,%s\n' "$TS" "$SITE" "$OUT" "$EC" >> "$OUTPUT"
  i=$((i + 1))
  sleep 2
done
