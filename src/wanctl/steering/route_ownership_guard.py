"""Route ownership guard for future active route management.

The guard is read-only: it inspects RouterOS Netwatch and script state through the
existing router client command boundary and reports whether wanctl may safely take
active route ownership. Any read/parse failure fails closed.
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
    """One route-mutating Netwatch/script conflict."""

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
            return f"{len(self.conflicts)} route-mutating Netwatch/script conflict(s)"
        return self.error


class RouteOwnershipGuard:
    """Inspect RouterOS route-owner conflicts without mutating RouterOS."""

    NETWATCH_PRINT = "/tool netwatch print detail"
    SCRIPT_PRINT = "/system script print detail"

    def __init__(self, router_client: RouteOwnershipClient) -> None:
        self.router_client = router_client

    def inspect(self) -> RouteOwnershipGuardResult:
        """Return current route ownership status, failing closed on uncertainty."""
        netwatch_result = self._read_json_list(self.NETWATCH_PRINT, "netwatch")
        if isinstance(netwatch_result, RouteOwnershipGuardResult):
            return netwatch_result
        script_result = self._read_json_list(self.SCRIPT_PRINT, "script")
        if isinstance(script_result, RouteOwnershipGuardResult):
            return script_result

        scripts = self._script_lookup(script_result)
        conflicts: list[RouteOwnershipConflict] = []
        for entry in netwatch_result:
            if not isinstance(entry, dict) or self._is_disabled(entry):
                continue
            name = self._entry_name(entry)
            referenced_scripts = self._referenced_scripts(entry)
            for script_name in referenced_scripts:
                source = scripts.get(script_name, "")
                if _contains_route_mutation(source):
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

        if conflicts:
            return RouteOwnershipGuardResult(
                status="conflict",
                active_allowed=False,
                owner="netwatch",
                conflicts=tuple(conflicts),
            )
        return RouteOwnershipGuardResult(status="ok", active_allowed=True, owner="wanctl")

    def _read_json_list(
        self, cmd: str, label: str
    ) -> list[dict[str, Any]] | RouteOwnershipGuardResult:
        rc, out, err = self.router_client.run_cmd(cmd, capture=True, timeout=5)
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
        if not isinstance(parsed, list) or not all(isinstance(item, dict) for item in parsed):
            return RouteOwnershipGuardResult(
                status="error",
                active_allowed=False,
                owner="unknown",
                error=f"unexpected RouterOS {label} output shape",
            )
        return parsed

    def _script_lookup(self, scripts: list[dict[str, Any]]) -> dict[str, str]:
        lookup: dict[str, str] = {}
        for script in scripts:
            name = script.get("name") or script.get(".id")
            if isinstance(name, str) and name:
                lookup[name] = str(script.get("source", ""))
        return lookup

    def _is_disabled(self, entry: dict[str, Any]) -> bool:
        disabled = entry.get("disabled", False)
        return disabled is True or str(disabled).lower() == "true"

    def _entry_name(self, entry: dict[str, Any]) -> str:
        for key in ("name", "comment", "host", ".id"):
            value = entry.get(key)
            if isinstance(value, str) and value:
                return value
        return "unknown"

    def _referenced_scripts(self, entry: dict[str, Any]) -> tuple[str, ...]:
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
        names.extend(match.group(1).strip('"') for match in re.finditer(pattern, source, re.I))
    if source and not source.startswith("/") and "\n" not in source and ";" not in source:
        names.append(source.strip('"'))
    return [name for name in names if name]


def _contains_route_mutation(source: str) -> bool:
    return bool(_ROUTE_MUTATION_RE.search(source))
