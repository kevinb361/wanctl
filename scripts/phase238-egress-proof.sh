#!/usr/bin/env bash
# phase238-egress-proof.sh - Phase 238 read-only fping egress proof.
# Usage: scripts/phase238-egress-proof.sh [--wan spectrum|att|all] [--json] [--print-commands] [--self-test]
#
# Read-only. Proves fping -S <source_ip> egress per WAN via ip route get / ip rule.
# No worktree, prod, CAKE-mode, unit, or controller-source mutation.
#
# Expected per-WAN verdicts are mechanical, not operator-attested:
#   spectrum: src 10.10.110.223 AND dev spec-modem
#   att:      src 10.10.110.227 AND dev att-modem
# The expected dev values are repo-derived from configs/cake-autorate/config.spectrum.sh
# and configs/cake-autorate/config.att.sh ul_if (line 6 in each file). If the live
# host resolves a different egress dev, this script correctly FAILs to surface drift.
#
# Remote command allowlist: only exact full lines shaped as `ip route get <IPv4>`,
# `ip route get <IPv4> from <IPv4>`, or `ip rule` are accepted. Shell metacharacters
# cannot appear inside the digit/dot or literal token classes, and the end anchor
# rejects trailing command tails before any live SSH can run.

set -euo pipefail

TARGETS=(
    "kevin@10.10.110.223|spectrum|<none>|10.10.110.223|spec-modem|spectrum-default|1.1.1.1 9.9.9.9 208.67.222.222"
    "kevin@10.10.110.223|att|10.10.110.227|10.10.110.227|att-modem|att-source-bound|1.1.1.1 8.8.8.8 151.101.1.57"
)

SSH_OPTS=(-o ConnectTimeout=10 -o BatchMode=yes)
WAN_FILTER="all"
JSON_MODE="0"
PRINT_COMMANDS="0"
SELF_TEST="0"

usage() {
    cat <<'EOF'
Usage: scripts/phase238-egress-proof.sh [options]

Read-only Phase 238 proof that fping -S <source_ip> would egress the intended WAN
under the cake-shaper host's current policy routing.

Options:
  --wan spectrum|att|all   WAN to evaluate (default: all)
  --json                   Emit JSON only
  --print-commands         Print exact remote commands without SSH/execution
  --self-test              Run local parser/verdict and injection-rejection fixtures
  --help, -h               Show this help

Expected verdicts:
  spectrum: ip route get <reflector> must resolve src 10.10.110.223 and dev spec-modem
            (Spectrum uses source sentinel <none>, so the proof uses the default route)
  att:      ip route get <reflector> from 10.10.110.227 must resolve src 10.10.110.227
            and dev att-modem

Expected devs are repo-derived from configs/cake-autorate/config.{spectrum,att}.sh
ul_if (line 6), not operator attestation. Live drift from those ul_if values fails.

Posture: read-only SSH queries only. The script does not modify the worktree,
production state, CAKE mode, services, routing policy, or controller source.
EOF
}

require_command() {
    local cmd="$1"
    if ! command -v "$cmd" >/dev/null 2>&1; then
        echo "ERROR: required command missing: $cmd" >&2
        exit 2
    fi
}

validate_wan() {
    case "$WAN_FILTER" in
        spectrum|att|all) ;;
        *) echo "ERROR: --wan must be spectrum, att, or all" >&2; exit 2 ;;
    esac
}

ssh_readonly() {
    local ssh_target="$1" remote_cmd="$2"
    ssh -n "${SSH_OPTS[@]}" "$ssh_target" "$remote_cmd"
}

json_string() {
    python3 -c 'import json, sys; print(json.dumps(sys.argv[1]))' "$1"
}

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

generate_remote_commands() {
    local target ssh_target wan source_ip expected_src expected_dev expected_path reflectors reflector
    for target in "${TARGETS[@]}"; do
        IFS='|' read -r ssh_target wan source_ip expected_src expected_dev expected_path reflectors <<<"$target"
        if [[ "$WAN_FILTER" != "all" && "$WAN_FILTER" != "$wan" ]]; then
            continue
        fi
        for reflector in $reflectors; do
            if [[ "$source_ip" == "<none>" ]]; then
                printf 'ip route get %s\n' "$reflector"
            else
                printf 'ip route get %s from %s\n' "$reflector" "$source_ip"
            fi
        done
    done
    printf 'ip rule\n'
}

is_allowed_remote_command() {
    local remote_cmd="$1"
    [[ "$remote_cmd" =~ ^(ip\ route\ get\ [0-9]+\.[0-9]+\.[0-9]+\.[0-9]+(\ from\ [0-9]+\.[0-9]+\.[0-9]+\.[0-9]+)?|ip\ rule)$ ]]
}

validate_generated_commands_or_exit() {
    local command_file="$1" remote_cmd
    while IFS= read -r remote_cmd; do
        if [[ -z "$remote_cmd" ]]; then
            continue
        fi
        if ! is_allowed_remote_command "$remote_cmd"; then
            echo "ERROR: generated remote command rejected by allowlist: $remote_cmd" >&2
            exit 2
        fi
    done <"$command_file"
}

verdict_for_line() {
    local wan="$1" expected_src="$2" expected_dev="$3" route_line="$4"
    python3 - "$wan" "$expected_src" "$expected_dev" "$route_line" <<'PY'
import json
import sys

wan, expected_src, expected_dev, line = sys.argv[1:]
tokens = line.split()

def after(token):
    try:
        index = tokens.index(token)
    except ValueError:
        return None
    if index + 1 >= len(tokens):
        return None
    return tokens[index + 1]

parsed = {
    "dev": after("dev"),
    # Linux may print source-bound route queries as `<dst> from <source> ...`
    # without a separate `src <source>` token. Treat `from` as the parsed source
    # fallback so fping -S/source-bound evidence is not falsely failed for src.
    "src": after("src") or after("from"),
    "via": after("via"),
}
passed = parsed["src"] == expected_src and parsed["dev"] == expected_dev
print(json.dumps({
    "wan": wan,
    "pass": passed,
    "verdict": "PASS" if passed else "FAIL",
    "expected_src": expected_src,
    "expected_dev": expected_dev,
    "parsed_src": parsed["src"],
    "parsed_dev": parsed["dev"],
    "parsed_via": parsed["via"],
    "route_line": line,
}, separators=(",", ":")))
PY
}

run_self_test() {
    local failures=0 actual allowed

    self_test_verdict_fixture() {
        local name="$1" wan="$2" expected_src="$3" expected_dev="$4" line="$5" expected="$6"
        actual="$(verdict_for_line "$wan" "$expected_src" "$expected_dev" "$line")"
        if python3 - "$actual" "$expected" <<'PY'
import json
import sys
payload = json.loads(sys.argv[1])
expected = sys.argv[2] == "PASS"
raise SystemExit(0 if payload.get("pass") is expected else 1)
PY
        then
            printf 'SELF-TEST verdict %-34s expected=%s actual=%s\n' "$name" "$expected" "$(python3 -c 'import json,sys; print(json.loads(sys.argv[1])["verdict"])' "$actual")"
        else
            printf 'SELF-TEST verdict %-34s expected=%s actual=%s FAILED\n' "$name" "$expected" "$actual" >&2
            failures=$((failures + 1))
        fi
    }

    self_test_reject_fixture() {
        local name="$1" remote_cmd="$2"
        if is_allowed_remote_command "$remote_cmd"; then
            allowed="ACCEPTED"
            failures=$((failures + 1))
            printf 'SELF-TEST injection %-32s expected=REJECTED actual=%s FAILED\n' "$name" "$allowed" >&2
        else
            allowed="REJECTED"
            printf 'SELF-TEST injection %-32s expected=REJECTED actual=%s\n' "$name" "$allowed"
        fi
    }

    self_test_verdict_fixture "spectrum src+dev pass" "spectrum" "10.10.110.223" "spec-modem" \
        "1.1.1.1 via 10.10.110.1 dev spec-modem src 10.10.110.223 uid 1000" "PASS"
    self_test_verdict_fixture "att src+dev pass" "att" "10.10.110.227" "att-modem" \
        "1.1.1.1 from 10.10.110.227 via 10.10.110.2 dev att-modem src 10.10.110.227 uid 1000" "PASS"
    self_test_verdict_fixture "att from-only src pass" "att" "10.10.110.227" "att-modem" \
        "1.1.1.1 from 10.10.110.227 via 10.10.110.2 dev att-modem uid 1000" "PASS"
    self_test_verdict_fixture "att wrong-src fail" "att" "10.10.110.227" "att-modem" \
        "1.1.1.1 from 10.10.110.227 via 10.10.110.1 dev att-modem src 10.10.110.223 uid 1000" "FAIL"
    self_test_verdict_fixture "att wrong-dev fail" "att" "10.10.110.227" "att-modem" \
        "1.1.1.1 from 10.10.110.227 via 10.10.110.1 dev spec-modem src 10.10.110.227 uid 1000" "FAIL"

    self_test_reject_fixture "semicolon chain" 'ip route get 1.1.1.1; reboot'
    self_test_reject_fixture "backtick substitution" 'ip route get `reboot`'
    self_test_reject_fixture "dollar substitution" 'ip route get $(reboot)'

    if [[ "$failures" -ne 0 ]]; then
        echo "SELF-TEST FAILED: $failures fixture(s) failed" >&2
        return 1
    fi
    echo "SELF-TEST PASS"
}

emit_print_commands() {
    local commands_file="$1"
    validate_generated_commands_or_exit "$commands_file"
    echo "--- BEGIN REMOTE COMMANDS ---"
    while IFS= read -r remote_cmd; do
        [[ -z "$remote_cmd" ]] && continue
        printf '%s\n' "$remote_cmd"
    done <"$commands_file"
    echo "--- END REMOTE COMMANDS ---"
}

execute_remote_commands() {
    local ssh_target="$1" commands_file="$2" outputs_dir="$3" idx=0 remote_cmd output
    validate_generated_commands_or_exit "$commands_file"
    while IFS= read -r remote_cmd; do
        [[ -z "$remote_cmd" ]] && continue
        output="$(ssh_readonly "$ssh_target" "$remote_cmd" 2>&1)"
        printf '%s\n' "$output" >"${outputs_dir}/${idx}.out"
        idx=$((idx + 1))
    done <"$commands_file"
}

evaluate_results_from_outputs() {
    local outputs_dir="$1" results_file="$2"
    local target ssh_target wan source_ip expected_src expected_dev expected_path reflectors reflector captured route_line verdict_json idx=0
    local wan_paths_file="${outputs_dir}/wan-paths.ndjson"
    : >"$wan_paths_file"
    for target in "${TARGETS[@]}"; do
        IFS='|' read -r ssh_target wan source_ip expected_src expected_dev expected_path reflectors <<<"$target"
        if [[ "$WAN_FILTER" != "all" && "$WAN_FILTER" != "$wan" ]]; then
            continue
        fi
        captured="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
        local reflector_results_file="${outputs_dir}/${wan}-reflectors.ndjson"
        : >"$reflector_results_file"
        for reflector in $reflectors; do
            route_line="$(<"${outputs_dir}/${idx}.out")"
            verdict_json="$(verdict_for_line "$wan" "$expected_src" "$expected_dev" "$route_line")"
            python3 - "$reflector" "$source_ip" "$expected_path" "$verdict_json" <<'PY' >>"$reflector_results_file"
import json
import sys
reflector, source_ip, expected_path, verdict = sys.argv[1:]
payload = json.loads(verdict)
payload["reflector"] = reflector
payload["source_ip"] = source_ip
payload["expected_path"] = expected_path
payload["egress_key"] = "|".join(str(payload.get(k) or "") for k in ("parsed_src", "parsed_dev", "parsed_via"))
print(json.dumps(payload, separators=(",", ":")))
PY
            python3 - "$wan" "$verdict_json" <<'PY' >>"$wan_paths_file"
import json
import sys
wan, verdict = sys.argv[1:]
payload = json.loads(verdict)
print(json.dumps({"wan": wan, "egress_key": "|".join(str(payload.get(k) or "") for k in ("parsed_src", "parsed_dev", "parsed_via"))}, separators=(",", ":")))
PY
            idx=$((idx + 1))
        done
        python3 - "$wan" "$captured" "$source_ip" "$expected_src" "$expected_dev" "$expected_path" "$reflector_results_file" <<'PY' >>"$results_file"
import json
import sys
from pathlib import Path

wan, captured, source_ip, expected_src, expected_dev, expected_path, path = sys.argv[1:]
reflectors = [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]
print(json.dumps({
    "wan": wan,
    "captured_utc": captured,
    "source_ip": source_ip,
    "expected_src": expected_src,
    "expected_dev": expected_dev,
    "expected_path": expected_path,
    "reflectors": reflectors,
    "verdict": "PASS" if all(item.get("pass") is True for item in reflectors) else "FAIL",
}, separators=(",", ":")))
PY
    done

    local rule_idx="$idx"
    python3 - "$results_file" "$wan_paths_file" "${outputs_dir}/${rule_idx}.out" "$WAN_FILTER" <<'PY'
import json
import sys
from pathlib import Path

results_path, paths_path, rule_path, wan_filter = sys.argv[1:]
rows = [json.loads(line) for line in Path(results_path).read_text().splitlines() if line.strip()]
paths = [json.loads(line) for line in Path(paths_path).read_text().splitlines() if line.strip()]
by_wan = {}
for item in paths:
    by_wan.setdefault(item["wan"], set()).add(item["egress_key"])
distinct = True
if wan_filter == "all" and {"spectrum", "att"}.issubset(by_wan):
    distinct = by_wan["spectrum"].isdisjoint(by_wan["att"])

ip_rule = Path(rule_path).read_text(errors="replace") if Path(rule_path).exists() else ""
for row in rows:
    row["ip_rule"] = ip_rule
    row["distinct_paths_check"] = {"pass": distinct, "paths_by_wan": {k: sorted(v) for k, v in by_wan.items()}}
    if not distinct:
        row["verdict"] = "FAIL"
Path(results_path).write_text("\n".join(json.dumps(row, separators=(",", ":")) for row in rows) + "\n")
PY
}

while [[ $# -gt 0 ]]; do
    case "$1" in
        --wan) WAN_FILTER="${2:-}"; shift 2 ;;
        --json) JSON_MODE="1"; shift ;;
        --print-commands) PRINT_COMMANDS="1"; shift ;;
        --self-test) SELF_TEST="1"; shift ;;
        --help|-h) usage; exit 0 ;;
        *) echo "ERROR: unknown argument: $1" >&2; usage >&2; exit 2 ;;
    esac
done

validate_wan
require_command python3
require_command ssh

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT

commands_file="${tmpdir}/remote-commands.txt"
generate_remote_commands >"$commands_file"

if [[ ! -s "$commands_file" ]]; then
    echo "ERROR: no remote commands generated" >&2
    exit 2
fi

if [[ "$SELF_TEST" == "1" ]]; then
    run_self_test
    exit $?
fi

if [[ "$PRINT_COMMANDS" == "1" ]]; then
    emit_print_commands "$commands_file"
    exit 0
fi

ssh_target=""
for target in "${TARGETS[@]}"; do
    IFS='|' read -r ssh_target _wan _source_ip _expected_src _expected_dev _expected_path _reflectors <<<"$target"
    break
done

outputs_dir="${tmpdir}/outputs"
mkdir -p "$outputs_dir"
execute_remote_commands "$ssh_target" "$commands_file" "$outputs_dir"

results_file="${tmpdir}/results.ndjson"
: >"$results_file"
evaluate_results_from_outputs "$outputs_dir" "$results_file"

if [[ "$JSON_MODE" == "1" ]]; then
    python3 - "$results_file" <<'PY'
import json
import sys
from pathlib import Path
rows = [json.loads(line) for line in Path(sys.argv[1]).read_text().splitlines() if line.strip()]
print(json.dumps(rows, indent=2, sort_keys=True))
PY
else
    python3 - "$results_file" <<'PY'
import json
import sys
from pathlib import Path
rows = [json.loads(line) for line in Path(sys.argv[1]).read_text().splitlines() if line.strip()]
for row in rows:
    print(f"{row['wan']}: {row['verdict']} expected_src={row['expected_src']} expected_dev={row['expected_dev']}")
    for item in row["reflectors"]:
        print(f"  {item['reflector']}: {item['verdict']} parsed_src={item.get('parsed_src')} parsed_dev={item.get('parsed_dev')} via={item.get('parsed_via')}")
    distinct = row.get("distinct_paths_check", {})
    print(f"  distinct_paths: {'PASS' if distinct.get('pass') else 'FAIL'}")
PY
fi

if python3 - "$results_file" <<'PY'
import json
import sys
from pathlib import Path
rows = [json.loads(line) for line in Path(sys.argv[1]).read_text().splitlines() if line.strip()]
raise SystemExit(0 if rows and all(row.get("verdict") == "PASS" for row in rows) else 1)
PY
then
    exit 0
fi

exit 1
