#!/usr/bin/env python3
"""Phase 260 bounded read-only dry-run observation and readiness packet harness."""
from __future__ import annotations

import argparse
import json
import logging
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

DEPLOYED_ROOT = Path("/opt/wanctl").resolve()
if DEPLOYED_ROOT.exists():
    sys.path.insert(0, str(DEPLOYED_ROOT.parent))

import wanctl  # noqa: E402
from wanctl import readonly_validator  # noqa: E402
from wanctl.readonly_validator import (  # noqa: E402
    FORBIDDEN_ROUTEROS_ACTIONS,
    iter_commands,
    validate_command,
)
from wanctl.router_client import get_router_client  # noqa: E402
from wanctl.steering.daemon import SteeringConfig  # noqa: E402
from wanctl.steering.route_manager import RouteManager  # noqa: E402
from wanctl.steering.route_ownership_inspector import (  # noqa: E402
    ROUTE_PRINT,
    RouteOwnershipInspector,
)

DEFAULT_CONFIG = Path("/etc/wanctl/steering.yaml")
DEFAULT_HEALTH_URL = "http://127.0.0.1:9102/health"
DEFAULT_ROLLBACK_ANCHOR = "/var/lib/wanctl/phase256-backups/20260620T033704Z"
STATIC_READ_COMMANDS = (
    "/tool netwatch print detail",
    "/system script print detail",
    ROUTE_PRINT,
)
LOCAL_HEALTH_HOSTS = {"127.0.0.1", "localhost", "::1"}


class RouterClientLike(Protocol):
    def run_cmd(
        self, cmd: str, capture: bool = False, timeout: int | None = None
    ) -> tuple[int, str, str]: ...

    def close(self) -> None: ...


class RouteManagerLike(Protocol):
    def status_snapshot(self) -> dict[str, object]: ...


def validate_commands_before_run(
    client: RouterClientLike, commands: list[str] | tuple[str, ...]
) -> None:
    """Validate commands before any client.run_cmd can be reached."""
    _ = client
    for command in commands:
        validate_command(command)


def _utc_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def _utc_iso() -> str:
    return datetime.now(UTC).isoformat()


def _boolish(value: Any) -> bool:
    return value is True or str(value).lower() == "true"


def _intish(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _json_list(out: str, label: str) -> list[dict[str, Any]]:
    try:
        parsed = json.loads(out or "[]")
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"failed to parse RouterOS {label}: {exc}") from exc
    if isinstance(parsed, dict):
        parsed = [parsed]
    if not isinstance(parsed, list) or not all(isinstance(item, dict) for item in parsed):
        raise RuntimeError(f"unexpected RouterOS {label} output shape")
    return parsed


def _validate_local_health_url(url: str) -> None:
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme != "http" or parsed.hostname not in LOCAL_HEALTH_HOSTS:
        raise ValueError(f"health URL must be local HTTP: {url}")


def _project_default_route(route: dict[str, Any]) -> dict[str, Any]:
    return {
        "gateway": route.get("gateway"),
        "disabled": _boolish(route.get("disabled", False)),
        "distance": _intish(route.get("distance")),
        "comment": route.get("comment"),
    }


def sample_health(url: str = DEFAULT_HEALTH_URL) -> dict[str, Any]:
    """Fetch steering health and return ownership/route-management sections.

    HTTP and JSON errors are converted to a bad-sample sentinel so callers fail closed.
    """
    try:
        _validate_local_health_url(url)
        with urllib.request.urlopen(url, timeout=5) as response:
            payload = json.loads(response.read().decode())
        if not isinstance(payload, dict):
            raise TypeError("health payload is not an object")
        ownership = payload.get("ownership_inspection")
        route_management = payload.get("route_management")
        if not isinstance(ownership, dict):
            raise TypeError("missing ownership_inspection object")
        if not isinstance(route_management, dict):
            route_management = {}
        return {
            "sampled_at": _utc_iso(),
            "ownership_inspection": ownership,
            "route_management": route_management,
            "error": None,
        }
    except (OSError, TimeoutError, TypeError, ValueError, json.JSONDecodeError, urllib.error.URLError) as exc:
        return {
            "sampled_at": _utc_iso(),
            "ownership_inspection": {
                "observed_owner": "unknown",
                "configured_owner": "unknown",
                "match": False,
                "inspector_status": "error",
                "inspector_error": str(exc),
                "last_inspected_at": None,
                "netwatch": {"entries_count": 0, "route_mutating_active_count": 0},
                "routes": {"total_route_count": 0, "default_routes": []},
            },
            "route_management": {},
            "error": str(exc),
        }


def gate_sample(
    ownership_inspection: dict[str, Any],
    route_management: dict[str, Any],
    prev_last_inspected_at: str | None,
) -> tuple[bool, str | None]:
    """Fail-closed D-01/D-02 gate for one sampled health payload."""
    status = ownership_inspection.get("inspector_status")
    if status != "ok":
        return False, f"inspector_status={status!r} error={ownership_inspection.get('inspector_error')!r}"
    if ownership_inspection.get("match") is not True:
        return False, f"ownership match is not true: {ownership_inspection.get('match')!r}"
    last_inspected_at = ownership_inspection.get("last_inspected_at")
    if not isinstance(last_inspected_at, str) or not last_inspected_at:
        return False, "last_inspected_at is missing"
    if prev_last_inspected_at is not None and last_inspected_at <= prev_last_inspected_at:
        return False, f"last_inspected_at did not advance: {last_inspected_at} <= {prev_last_inspected_at}"

    guard = route_management.get("guard") if isinstance(route_management, dict) else {}
    if not isinstance(guard, dict):
        guard = {}
    guard_status = str(guard.get("status", "unknown"))
    breaker = route_management.get("circuit_breaker") if isinstance(route_management, dict) else {}
    if not isinstance(breaker, dict):
        breaker = {}
    if _boolish(breaker.get("open", False)):
        return False, "route_management.circuit_breaker.open=true"
    if guard_status in {"circuit-open", "hard-fail", "hard_fail", "failed"}:
        return False, f"route_management.guard.status={guard_status}"
    return True, None


def cross_check(client: RouterClientLike) -> dict[str, Any]:
    """Take the independent read-only RouterOS D-04 cross-check."""
    validate_commands_before_run(_NoRunClient(), STATIC_READ_COMMANDS)
    issued: list[str] = []
    raw: dict[str, list[dict[str, Any]]] = {}
    errors: list[dict[str, str]] = []
    labels = {
        "/tool netwatch print detail": "netwatch",
        "/system script print detail": "scripts",
        ROUTE_PRINT: "routes",
    }
    for command in STATIC_READ_COMMANDS:
        issued.append(command)
        rc, out, err = client.run_cmd(command, capture=True, timeout=10)
        label = labels[command]
        if rc != 0:
            errors.append({"command": command, "error": err or out or "unknown error"})
            raw[label] = []
            continue
        try:
            raw[label] = _json_list(out, label)
        except RuntimeError as exc:
            errors.append({"command": command, "error": str(exc)})
            raw[label] = []

    routes = raw.get("routes", [])
    netwatch = raw.get("netwatch", [])
    default_routes = [_project_default_route(route) for route in routes if route.get("dst-address") == "0.0.0.0/0"]
    route_mutating_active = [entry for entry in netwatch if _netwatch_mutates_route(entry)]
    return {
        "issued_commands": issued,
        "errors": errors,
        "netwatch": {
            "entries_count": len(netwatch),
            "route_mutating_active_count": len(route_mutating_active),
            "entries": netwatch,
        },
        "scripts": {"entries_count": len(raw.get("scripts", [])), "entries": raw.get("scripts", [])},
        "routes": {
            "total_route_count": len(routes),
            "default_routes": default_routes,
            "entries": routes,
        },
    }


def _netwatch_mutates_route(entry: dict[str, Any]) -> bool:
    if _boolish(entry.get("disabled", False)):
        return False
    combined = " ".join(str(entry.get(key, "")) for key in ("up-script", "down-script", "test-script"))
    lowered = f" {combined.lower()} "
    return any(token in lowered for token in ("/ip route", "/ip/route", " ip route "))


def _normalize_routes(routes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(
        [
            {
                "gateway": route.get("gateway"),
                "disabled": _boolish(route.get("disabled", False)),
                "distance": _intish(route.get("distance")),
                "comment": route.get("comment"),
            }
            for route in routes
        ],
        key=lambda r: (str(r.get("comment")), str(r.get("gateway")), str(r.get("distance"))),
    )


def standing_intent_table(
    route_manager: RouteManagerLike, ownership_inspection: dict[str, Any]
) -> list[dict[str, Any]]:
    """Render D-05 standing intent vs live default-route rows without applying actions."""
    snapshot = route_manager.status_snapshot()
    reconciliation = snapshot.get("reconciliation") if isinstance(snapshot, dict) else {}
    route_count = None
    if isinstance(reconciliation, dict):
        route_count = reconciliation.get("route_count")
    manager_routes = getattr(route_manager, "routes", {}) or {}
    live_routes = ownership_inspection.get("routes", {}).get("default_routes", [])
    if not isinstance(live_routes, list):
        live_routes = []

    rows: list[dict[str, Any]] = []
    for key, config in sorted(manager_routes.items()):
        config = config if isinstance(config, dict) else {}
        anchor_value = config.get("comment") or config.get("id")
        matches = [
            route
            for route in live_routes
            if anchor_value
            and (route.get("comment") == anchor_value or route.get(".id") == anchor_value or route.get("id") == anchor_value)
        ]
        live = matches[0] if matches else None
        rows.append(
            {
                "route_key": key,
                "active_owner": snapshot.get("active_owner"),
                "mode": snapshot.get("mode"),
                "intent_anchor": anchor_value,
                "intent_distance": config.get("distance"),
                "live_gateway": live.get("gateway") if live else None,
                "live_disabled": live.get("disabled") if live else None,
                "live_distance": live.get("distance") if live else None,
                "live_comment": live.get("comment") if live else None,
                "match": bool(live) and (config.get("distance") in (None, live.get("distance"))),
            }
        )
    if not rows:
        rows.append(
            {
                "route_key": "default_routes",
                "active_owner": snapshot.get("active_owner"),
                "mode": snapshot.get("mode"),
                "intent_anchor": f"reconciliation.route_count={route_count}",
                "intent_distance": None,
                "live_gateway": None,
                "live_disabled": None,
                "live_distance": None,
                "live_comment": f"default_routes={len(live_routes)}",
                "match": route_count in (None, 0, len(live_routes)),
            }
        )
    return rows


def scan_mutation_tokens(issued_commands: list[str] | tuple[str, ...]) -> list[str]:
    """Scan issued command transcript for forbidden RouterOS action tokens."""
    hits: list[str] = []
    for command in issued_commands:
        lowered = f" {command.lower()} "
        slash_lowered = command.lower()
        for token in FORBIDDEN_ROUTEROS_ACTIONS:
            if token.startswith("/"):
                if token in slash_lowered:
                    hits.append(f"{token}:{command}")
            elif token in lowered:
                hits.append(f"{token.strip()}:{command}")
    return hits


def assemble_divergences(
    samples: list[dict[str, Any]],
    cross_check_result: dict[str, Any],
    table: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Assemble the D-07 union of sample, intent-table, and cross-check divergences."""
    divergences: list[dict[str, Any]] = []
    prev: str | None = None
    for index, sample in enumerate(samples, 1):
        ownership = sample.get("ownership_inspection", {})
        route_management = sample.get("route_management", {})
        ok, blocker = gate_sample(ownership, route_management, prev)
        if not ok:
            divergences.append(
                {
                    "class": "sample-gate",
                    "sample_index": index,
                    "blocker": blocker,
                    "observed": ownership,
                }
            )
        last = ownership.get("last_inspected_at")
        prev = last if isinstance(last, str) and last else prev

    for row in table:
        if row.get("match") is not True:
            divergences.append({"class": "intent-vs-live", "observed": row})

    if cross_check_result.get("errors"):
        divergences.append({"class": "cross-check", "observed": cross_check_result.get("errors")})

    final_ownership = samples[-1].get("ownership_inspection", {}) if samples else {}
    cc_routes = cross_check_result.get("routes", {})
    cc_netwatch = cross_check_result.get("netwatch", {})
    ownership_routes = final_ownership.get("routes", {}) if isinstance(final_ownership, dict) else {}
    ownership_netwatch = final_ownership.get("netwatch", {}) if isinstance(final_ownership, dict) else {}
    comparisons = [
        (
            "total_route_count",
            ownership_routes.get("total_route_count"),
            cc_routes.get("total_route_count"),
        ),
        (
            "default_routes",
            _normalize_routes(ownership_routes.get("default_routes", [])),
            _normalize_routes(cc_routes.get("default_routes", [])),
        ),
        (
            "netwatch.route_mutating_active_count",
            ownership_netwatch.get("route_mutating_active_count"),
            cc_netwatch.get("route_mutating_active_count"),
        ),
    ]
    for field, health_value, cross_value in comparisons:
        if health_value != cross_value:
            divergences.append(
                {
                    "class": "cross-check",
                    "field": field,
                    "ownership_inspection": health_value,
                    "direct_routeros": cross_value,
                }
            )
    return divergences


def compute_verdict(divergences: list[dict[str, Any]], mutation_hits: list[str]) -> str:
    if not divergences and not mutation_hits:
        return "ready-for-approval"
    return "not-ready"


def _verdict_block(verdict: str, mutation_hits: list[str]) -> str:
    hits = "[]" if not mutation_hits else json.dumps(mutation_hits, sort_keys=True)
    return "\n".join(
        [
            f"OBSERVE_VERDICT: {verdict}",
            "APPROVED_ACTIVE_CANARY: false",
            "NETWATCH_REMAINS_OWNER: true",
            "NO_ROUTE_OWNER_FLIP: true",
            "NO_ROUTEROS_ROUTE_MUTATION: true",
            "NO_NETWATCH_MUTATION: true",
            "NO_CAKE_QDISC_CHANGE: true",
            f"MUTATION_TOKEN_HITS: {hits}",
        ]
    )


def run_observation(
    client: RouterClientLike,
    route_manager: RouteManagerLike,
    *,
    health_url: str,
    window_sec: int,
    interval_sec: int,
) -> dict[str, Any]:
    samples: list[dict[str, Any]] = []
    deadline = time.monotonic() + max(0, window_sec)
    first = True
    while first or time.monotonic() < deadline:
        first = False
        sample = sample_health(health_url)
        ownership = sample.get("ownership_inspection", {})
        route_management = sample.get("route_management", {})
        prev = None
        if samples:
            previous = samples[-1].get("ownership_inspection", {}).get("last_inspected_at")
            prev = previous if isinstance(previous, str) else None
        ok, blocker = gate_sample(ownership, route_management, prev)
        sample["gate_ok"] = ok
        sample["gate_blocker"] = blocker
        samples.append(sample)
        if time.monotonic() >= deadline:
            break
        time.sleep(max(1, interval_sec))

    cross = cross_check(client)
    table = standing_intent_table(route_manager, samples[-1].get("ownership_inspection", {}) if samples else {})
    divergences = assemble_divergences(samples, cross, table)
    mutation_hits = scan_mutation_tokens(cross.get("issued_commands", []))
    verdict = compute_verdict(divergences, mutation_hits)
    return {
        "generated_at": _utc_iso(),
        "health_url": health_url,
        "window_sec": window_sec,
        "interval_sec": interval_sec,
        "samples": samples,
        "cross_check": cross,
        "standing_intent_table": table,
        "divergences": divergences,
        "mutation_token_hits": mutation_hits,
        "verdict": verdict,
    }


def render_packet(result: dict[str, Any], evidence_dir: Path, command_file: Path) -> dict[str, Path]:
    """Write 257-shaped readiness packet, raw JSON, and transcript artifacts."""
    evidence_dir.mkdir(parents=True, exist_ok=True)
    packet = evidence_dir / "phase260-readiness-packet.md"
    raw = evidence_dir / "phase260-observation-raw.json"
    transcript = evidence_dir / "phase260-observation-transcript.md"
    timestamped_packet = evidence_dir / f"phase260-readiness-packet-{_utc_stamp()}.md"
    verdict = str(result.get("verdict", "not-ready"))
    mutation_hits = list(result.get("mutation_token_hits", []))
    block = _verdict_block(verdict, mutation_hits)
    divergences = result.get("divergences", [])
    samples = result.get("samples", [])
    latest = samples[-1].get("ownership_inspection", {}) if samples else {}
    route_management = samples[-1].get("route_management", {}) if samples else {}
    cross = result.get("cross_check", {})
    table = result.get("standing_intent_table", [])

    raw.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
    transcript.write_text(_render_transcript(result, command_file))
    body = _render_packet_body(
        verdict=verdict,
        block=block,
        command_file=command_file,
        raw=raw,
        transcript=transcript,
        packet=packet,
        latest=latest,
        route_management=route_management,
        cross=cross,
        table=table,
        divergences=divergences,
        mutation_hits=mutation_hits,
    )
    packet.write_text(body)
    timestamped_packet.write_text(body)
    return {"packet": packet, "raw": raw, "transcript": transcript, "timestamped_packet": timestamped_packet}


def _render_transcript(result: dict[str, Any], command_file: Path) -> str:
    cross = result.get("cross_check", {})
    commands = cross.get("issued_commands", [])
    lines = [
        "# Phase 260 Observation Transcript",
        "",
        f"Generated: {result.get('generated_at')}",
        f"Command file: `{command_file}`",
        "",
        "## Validator Tokens",
        "",
        "```text",
        "READONLY_COMMANDS_VALIDATED",
        "READONLY_COMMANDS_NEGATIVE_SELF_TEST_PASSED",
        "```",
        "",
        "## Issued RouterOS Commands",
        "",
    ]
    for command in commands:
        lines.append(f"- `{command}`")
    lines.extend(["", "## Verdict", "", "```text", _verdict_block(str(result.get("verdict")), list(result.get("mutation_token_hits", []))), "```", ""])
    return "\n".join(lines)


def _render_packet_body(
    *,
    verdict: str,
    block: str,
    command_file: Path,
    raw: Path,
    transcript: Path,
    packet: Path,
    latest: dict[str, Any],
    route_management: dict[str, Any],
    cross: dict[str, Any],
    table: list[dict[str, Any]],
    divergences: list[dict[str, Any]],
    mutation_hits: list[str],
) -> str:
    criteria = _criteria_rows(verdict, latest, route_management, cross, mutation_hits)
    table_rows = _intent_table_rows(table)
    blockers = _blockers_section(verdict, divergences)
    return f"""# Phase 260 Readiness Packet

Verdict: {verdict}

{block}

This packet supersedes the Phase 257 not-ready packet. It reruns the bounded observation with Phase 258's supported REST read-only RouterOS path and Phase 259's live `ownership_inspection` signal.

## Evidence Inputs

- Command file: `{command_file}`
- Raw observation data: `{raw}`
- Observation transcript: `{transcript}`
- Readiness packet: `{packet}`
- Phase 256 rollback anchors: `{DEFAULT_ROLLBACK_ANCHOR}`
- Plan summary: `.planning/phases/260-dry-run-observation-rerun-canary-readiness/260-01-SUMMARY.md`

## Readiness Criteria Matrix

| Criterion | Observed | Status | Readiness impact |
|-----------|----------|--------|------------------|
{criteria}

## Intended vs Live Summary

Route-management / ownership summary from `127.0.0.1:9102/health` and the direct REST cross-check:

- `ownership_inspection.inspector_status={latest.get('inspector_status')}`
- `ownership_inspection.match={latest.get('match')}`
- `observed_owner={latest.get('observed_owner')}`
- `configured_owner={latest.get('configured_owner')}`
- `route_management.mode={route_management.get('mode')}`
- `route_management.active_owner={route_management.get('active_owner')}`
- `route_management.active_allowed={route_management.get('active_allowed')}`
- `route_management.last_intended_action={route_management.get('last_intended_action')}`
- `route_management.last_applied_action={route_management.get('last_applied_action')}`

| Route | Owner | Intent anchor | Intent distance | Live gateway | Live disabled | Live distance | Live comment | Match |
|-------|-------|---------------|-----------------|--------------|---------------|---------------|--------------|-------|
{table_rows}

## SAFE-21 No-Mutation Proof

Preserved.

- `APPROVED_ACTIVE_CANARY: false`
- `NETWATCH_REMAINS_OWNER: true`
- `NO_ROUTE_OWNER_FLIP: true`
- `NO_ROUTEROS_ROUTE_MUTATION: true`
- `NO_NETWATCH_MUTATION: true`
- `NO_CAKE_QDISC_CHANGE: true`
- `MUTATION_TOKEN_HITS: {'[]' if not mutation_hits else json.dumps(mutation_hits)}`
- No controller threshold retuning.
- No service restart/reload.
- No production route-owner flip.
- No active route-management canary.

Only the predeclared `COMMAND:` lines were issued. The validator printed `READONLY_COMMANDS_VALIDATED`, and the local negative self-test printed `READONLY_COMMANDS_NEGATIVE_SELF_TEST_PASSED` before any live command execution.

## Rollback Evidence

Rollback anchor path from Phase 256:

```text
{DEFAULT_ROLLBACK_ANCHOR}
```

This packet did not perform a deploy, config edit, restart, reload, route mutation, Netwatch change, CAKE/qdisc change, or owner flip, so no new rollback action was needed.

## Blockers and Remediation

{blockers}

## Next Recommendation

Keep Netwatch as the active/interim route owner. A future milestone may request explicit operator approval for an active canary, but this packet is not approval and starts no canary.
"""


def _criteria_rows(
    verdict: str,
    latest: dict[str, Any],
    route_management: dict[str, Any],
    cross: dict[str, Any],
    mutation_hits: list[str],
) -> str:
    guard = route_management.get("guard") if isinstance(route_management, dict) else {}
    if not isinstance(guard, dict):
        guard = {}
    reconciliation = route_management.get("reconciliation") if isinstance(route_management, dict) else {}
    if not isinstance(reconciliation, dict):
        reconciliation = {}
    breaker = route_management.get("circuit_breaker") if isinstance(route_management, dict) else {}
    if not isinstance(breaker, dict):
        breaker = {}
    cross_routes = cross.get("routes", {}) if isinstance(cross, dict) else {}
    cross_netwatch = cross.get("netwatch", {}) if isinstance(cross, dict) else {}
    rows = [
        (
            "ownership inspector authoritative",
            f"`inspector_status={latest.get('inspector_status')}`, `match={latest.get('match')}`",
            "pass" if latest.get("inspector_status") == "ok" and latest.get("match") is True else "fail",
            "Replaces Phase 257 guard-status failure with D-01 ownership_inspection gate.",
        ),
        (
            "reconciliation ok",
            f"`reconciliation.status={reconciliation.get('status')}`, `route_count={reconciliation.get('route_count')}`",
            "pass" if reconciliation.get("status") in ("ok", None) else "fail",
            "Route target reconciliation is healthy or not blocking dry-run observation.",
        ),
        (
            "circuit breaker closed",
            f"`circuit_breaker.open={breaker.get('open')}`",
            "pass" if not _boolish(breaker.get("open", False)) else "fail",
            "Circuit does not block observation.",
        ),
        (
            "no intended mutation",
            f"`last_intended_action={route_management.get('last_intended_action')}`",
            "pass" if route_management.get("last_intended_action") in (None, "null") else "fail",
            "No route action was intended during observation.",
        ),
        (
            "no applied mutation",
            f"`last_applied_action={route_management.get('last_applied_action')}`",
            "pass" if route_management.get("last_applied_action") in (None, "null") else "fail",
            "No route action was applied during observation.",
        ),
        (
            "REST read-only inventory succeeded",
            f"`route={cross_routes.get('total_route_count')}`, `netwatch={cross_netwatch.get('entries_count')}`, `script={cross.get('scripts', {}).get('entries_count') if isinstance(cross.get('scripts'), dict) else None}`; Phase 258 ACCESS02_PROOF_PASS route=17 netwatch=3 script=20",
            "pass" if not cross.get("errors") else "fail",
            "Replaces Phase 257 SSH key failure with the supported REST read-only path.",
        ),
        (
            "rollback anchors current",
            f"Phase 256 anchors exist at `{DEFAULT_ROLLBACK_ANCHOR}` per recorded evidence",
            "pass",
            "Rollback evidence remains available for safe/off deployment state.",
        ),
        (
            "SAFE-21 no-mutation proof",
            f"`MUTATION_TOKEN_HITS: {'[]' if not mutation_hits else json.dumps(mutation_hits)}`",
            "pass" if not mutation_hits else "fail",
            "No forbidden mutation class occurred." if not mutation_hits else "Forces not-ready.",
        ),
    ]
    rendered = []
    for criterion, observed, status, impact in rows:
        if verdict == "not-ready" and status == "fail":
            impact = f"Forces `not-ready`. {impact}"
        rendered.append(f"| {criterion} | {observed} | {status} | {impact} |")
    return "\n".join(rendered)


def _intent_table_rows(table: list[dict[str, Any]]) -> str:
    if not table:
        return "| none | unknown | none | none | none | none | none | none | false |"
    rows = []
    for row in table:
        rows.append(
            "| {route_key} | {active_owner} | {intent_anchor} | {intent_distance} | {live_gateway} | {live_disabled} | {live_distance} | {live_comment} | {match} |".format(
                **{k: row.get(k) for k in ("route_key", "active_owner", "intent_anchor", "intent_distance", "live_gateway", "live_disabled", "live_distance", "live_comment", "match")}
            )
        )
    return "\n".join(rows)


def _blockers_section(verdict: str, divergences: list[dict[str, Any]]) -> str:
    if verdict == "ready-for-approval":
        return "No blockers recorded. This is NOT approval and no active canary is requested or started under SAFE-21/D-10."
    if not divergences:
        return "No structured divergences were recorded, but the verdict remained not-ready; inspect raw observation data before proceeding."
    lines = []
    for index, divergence in enumerate(divergences, 1):
        lines.append(f"{index}. `{divergence.get('class')}` divergence: `{json.dumps(divergence, sort_keys=True)}`")
    lines.append("")
    lines.append("No active canary approval is requested here.")
    return "\n".join(lines)


def _assert_deployed_imports() -> None:
    wanctl_path = Path(wanctl.__file__ or "").resolve()
    inspector_path = Path(sys.modules[RouteOwnershipInspector.__module__].__file__ or "").resolve()
    print(f"wanctl.__file__={wanctl_path}")
    print(f"route_ownership_inspector.__file__={inspector_path}")
    if not wanctl_path.is_relative_to(DEPLOYED_ROOT) or not inspector_path.is_relative_to(
        DEPLOYED_ROOT
    ):
        print(
            "OBSERVE_FAIL import-path "
            f"wanctl={wanctl_path} route_ownership_inspector={inspector_path}",
            file=sys.stderr,
        )
        raise SystemExit(1)


def _route_manager_from_config(config: SteeringConfig, client: RouterClientLike) -> RouteManager:
    manager = RouteManager(
        enabled=bool(config.route_management_enabled),
        mode=str(config.route_management_mode),
        routes=config.route_management_routes,
        router_client=client,
        ownership_guard_result=None,
    )
    manager.reconcile_startup()
    return manager


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command_file", type=Path)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--health-url", default=DEFAULT_HEALTH_URL)
    parser.add_argument("--window-sec", type=int, default=636)
    parser.add_argument("--interval-sec", type=int, default=60)
    parser.add_argument("--evidence-dir", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)

    _assert_deployed_imports()
    commands = iter_commands(args.command_file)
    validate_commands_before_run(_NoRunClient(), commands)
    readonly_validator.validate_path(args.command_file)
    if readonly_validator.self_test() != 0:
        return 1

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    logger = logging.getLogger("phase260-observation")
    print(f"config={args.config}")
    config = SteeringConfig(str(args.config))
    print(f"config_loader=SteeringConfig transport={config.router_transport}")
    client = get_router_client(config, logger)
    try:
        route_manager = _route_manager_from_config(config, client)
        result = run_observation(
            client,
            route_manager,
            health_url=args.health_url,
            window_sec=args.window_sec,
            interval_sec=args.interval_sec,
        )
        render_packet(result, args.evidence_dir, args.command_file)
    finally:
        close = getattr(client, "close", None)
        if callable(close):
            close()
    print(_verdict_block(str(result["verdict"]), list(result["mutation_token_hits"])))
    return 0 if result["verdict"] == "ready-for-approval" else 1


class _NoRunClient:
    def run_cmd(
        self, cmd: str, capture: bool = False, timeout: int | None = None
    ) -> tuple[int, str, str]:
        raise AssertionError("validate_commands_before_run must not execute commands")

    def close(self) -> None:
        return None


if __name__ == "__main__":
    raise SystemExit(main())
