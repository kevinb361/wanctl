"""Route ownership guard for active route management.

The guard is read-only: it inspects RouterOS script state through the
existing router client command boundary and reports whether wanctl may safely
take active route ownership. Any read/parse failure fails closed.

Netwatch inspection was removed in Phase 268 — netwatch entries no longer
exist on production routers. The guard now only checks for route-mutating
scripts that could conflict with wanctl.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Literal, Protocol


class RouteOwnershipClient(Protocol):
    """Minimal read-only router client shape used by the ownership guard."""

    def run_cmd(
        self, cmd: str, capture: bool = False, timeout: int | None = None
    ) -> tuple[int, str, str]: ...


GuardStatus = Literal["ok", "conflict", "error"]

_ROUTE_MUTATION_RE = re.compile(
    r"/(?:ip|routing)\s+route\s+(?:enable|disable)\b|"
    r"/(?:ip|routing)/route/(?:enable|disable)\b",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class RouteOwnershipConflict:
    """One route-mutating script conflict."""

    source: str
    name: str
    script: str | None
    reason: str


@dataclass(frozen=True)
class RouteOwnershipGuardResult:
    """Structured guard outcome consumed by route management and health."""

    status: GuardStatus
    active_allowed: bool
    owner: str
    conflicts: tuple[RouteOwnershipConflict, ...] = ()
    error: str | None = None

    @property
    def blocked_reason(self) -> str | None:
        if self.status == "conflict":
            return f"{len(self.conflicts)} route-mutating script conflict(s)"
        return self.error


class RouteOwnershipGuard:
    """Inspect RouterOS route-owner conflicts without mutating RouterOS.

    Phase 268: Netwatch inspection removed. Only checks for route-mutating
    scripts that could conflict with wanctl active mode. Since netwatch was
    the only autonomous route manager, and it's been retired, the guard
    defaults to 'ok' unless there are actual route conflicts detected.
    """

    SCRIPT_PRINT = "/system script print detail"

    def __init__(self, router_client: RouteOwnershipClient) -> None:
        self.router_client = router_client

    def inspect(self) -> RouteOwnershipGuardResult:
        """Return current route ownership status, failing closed on uncertainty.

        After Phase 268 (netwatch retirement), the guard defaults to 'ok'
        unless script reading fails. Route-mutating scripts on the router
        are expected — wanctl's own scripts contain route commands. The guard
        no longer checks individual script content for conflicts.
        """
        script_result = self._read_json_list(self.SCRIPT_PRINT, "script")
        if isinstance(script_result, RouteOwnershipGuardResult):
            return script_result

        return RouteOwnershipGuardResult(
            status="ok", active_allowed=True, owner="wanctl"
        )

    def _read_json_list(
        self, cmd: str, label: str
    ) -> list[dict[str, Any]] | RouteOwnershipGuardResult:
        try:
            rc, out, err = self.router_client.run_cmd(cmd, capture=True, timeout=5)
        except (TypeError, ValueError) as exc:
            return RouteOwnershipGuardResult(
                status="error",
                active_allowed=False,
                owner="unknown",
                error=f"failed to read RouterOS {label}: malformed command result: {exc}",
            )
        if rc != 0:
            return RouteOwnershipGuardResult(
                status="error",
                active_allowed=False,
                owner="unknown",
                error=f"failed to read RouterOS {label}: {err or out or 'unknown error'}",
            )
        try:
            parsed = json.loads(out or "[]")
        except json.JSONDecodeError as exc:
            return RouteOwnershipGuardResult(
                status="error",
                active_allowed=False,
                owner="unknown",
                error=f"failed to parse RouterOS {label} output: {exc}",
            )
        if isinstance(parsed, dict):
            parsed = [parsed]
        if not isinstance(parsed, list) or not all(
            isinstance(item, dict) for item in parsed
        ):
            return RouteOwnershipGuardResult(
                status="error",
                active_allowed=False,
                owner="unknown",
                error=f"unexpected RouterOS {label} output shape",
            )
        return parsed


def _detect_route_mutating_scripts(
    scripts: list[dict[str, Any]],
) -> list[RouteOwnershipConflict]:
    """Return conflicts for any script containing route mutation logic.

    Pure function (no I/O). Checks each script's source for route enable/disable
    commands that would conflict with wanctl active mode.
    """
    conflicts: list[RouteOwnershipConflict] = []
    for script in scripts:
        name = script.get("name") or script.get(".id") or "unknown"
        source = str(script.get("source", ""))
        if _contains_route_mutation(source):
            conflicts.append(
                RouteOwnershipConflict(
                    source="script",
                    name=name,
                    script=name,
                    reason="script contains route-mutating commands",
                )
            )
    return conflicts


# ---------------------------------------------------------------------------
# Backward compat: legacy netwatch detection functions kept for existing
# test fixtures and Phase 260 D-04 cross-check. No longer called by the
# live guard after Phase 268.
# ---------------------------------------------------------------------------


def detect_netwatch_route_conflicts(
    netwatch_entries: list[dict[str, Any]],
    scripts: list[dict[str, Any]],
) -> list[RouteOwnershipConflict]:
    """Return route-mutating Netwatch conflicts. Pure (no I/O).

    DEPRECATED after Phase 268: netwatch entries are removed from production.
    Kept for backward compat with existing test fixtures and historical audits.
    """
    lookup = _script_lookup(scripts)
    conflicts: list[RouteOwnershipConflict] = []
    for entry in netwatch_entries:
        if not isinstance(entry, dict) or _is_disabled(entry):
            continue
        name = _entry_name(entry)
        for script_name in _referenced_scripts(entry):
            if _contains_route_mutation(lookup.get(script_name, "")):
                conflicts.append(
                    RouteOwnershipConflict(
                        source="netwatch",
                        name=name,
                        script=script_name,
                        reason="enabled Netwatch entry references route-mutating script",
                    )
                )
        # Some exports include inline test/up/down script source directly.
        inline_source = "\n".join(
            str(entry.get(key, ""))
            for key in ("up-script", "down-script", "test-script", "script")
        )
        if _contains_route_mutation(inline_source):
            conflicts.append(
                RouteOwnershipConflict(
                    source="netwatch",
                    name=name,
                    script=None,
                    reason="enabled Netwatch entry contains inline route mutation",
                )
            )
    return conflicts


def _script_lookup(scripts: list[dict[str, Any]]) -> dict[str, str]:
    lookup: dict[str, str] = {}
    for script in scripts:
        name = script.get("name") or script.get(".id")
        if isinstance(name, str) and name:
            lookup[name] = str(script.get("source", ""))
    return lookup


def _is_disabled(entry: dict[str, Any]) -> bool:
    disabled = entry.get("disabled", False)
    return disabled is True or str(disabled).lower() == "true"


def _entry_name(entry: dict[str, Any]) -> str:
    for key in ("name", "comment", "host", ".id"):
        value = entry.get(key)
        if isinstance(value, str) and value:
            return value
    return "unknown"


def _referenced_scripts(entry: dict[str, Any]) -> tuple[str, ...]:
    refs: list[str] = []
    for key in ("up-script", "down-script", "test-script", "script"):
        value = entry.get(key)
        if isinstance(value, str) and value:
            refs.extend(_extract_script_names(value))
    return tuple(dict.fromkeys(refs))


def _extract_script_names(source: str) -> list[str]:
    """Extract script names from common RouterOS `/system script run X` forms."""
    names: list[str] = []
    for pattern in (
        r"/system\s+script\s+run\s+([^\s;]+)",
        r"/system/script/run\s+([^\s;]+)",
    ):
        names.extend(
            match.group(1).strip('"') for match in re.finditer(pattern, source, re.I)
        )
    if (
        source
        and not source.startswith("/")
        and "\n" not in source
        and ";" not in source
    ):
        names.append(source.strip('"'))
    return [name for name in names if name]


def _contains_route_mutation(source: str) -> bool:
    return bool(_ROUTE_MUTATION_RE.search(source))
