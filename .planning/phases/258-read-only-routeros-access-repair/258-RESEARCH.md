# Phase 258: Read-Only RouterOS Access Repair - Research

**Researched:** 2026-06-20
**Domain:** RouterOS read-only access from `cake-shaper` (transport selection, credential repair, read-only allowlist enforcement)
**Confidence:** HIGH (all findings sourced from this repo's deployed code/config and v1.56 Phase 257 evidence; live-host facts flagged for operator verification)

> NOTE: No external packages are installed by this phase. The Package Legitimacy Audit, Standard Stack version-verification, and Security/ASVS web-research steps are N/A — this is a credential/transport-repair phase against an existing internal RouterOS integration. Sections that don't apply are marked N/A rather than padded.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**D1 — Transport: match steering's live transport.** Use whatever transport production steering already uses to reach RouterOS from `cake-shaper` (expected REST/password per INTEGRATIONS.md). If steering uses REST, the v1.56 SSH-key repair is dropped entirely — `router.key` is not the path. Research must confirm first what transport + endpoint the live steering daemon actually uses, and that the chosen path can read both required objects.

**D2 — Read-only enforcement: allowlist layer, not RouterOS user policy.** Reuse the existing steering credential rather than minting a dedicated read-only RouterOS user. Read-only-ness is enforced by the deterministic command-file allowlist validator from v1.56 Phase 257, not at the RouterOS permission layer. ACCESS-03 and SAFE-21 are satisfied at the allowlist/validator layer. Carry the validator forward / generalize it — do not rebuild a parallel guard.

**D3 — Provisioning: operator step + existing `/etc/wanctl/secrets` pattern.** Any credential setup on `cake-shaper` is a documented repeatable repo script the operator runs at the keyboard (`! <command>`), credential stored via the existing `/etc/wanctl/secrets` pattern. Not folded into `deploy.sh`. Likely minimal/no provisioning if reusing steering creds already present — provisioning then reduces to verifying the steering credential is readable by the inspection code path.

**D4 — Proof of ACCESS-02: both reads, parseable.** Proof = live `/ip/route/print` AND `/tool/netwatch/print` (or transport-equivalent) each return exit 0 with non-empty, parseable output. Single-command proof rejected.

### Claude's Discretion

(CONTEXT.md did not enumerate a discrete discretion list; the open questions below are the research-owned areas. The transport fork — REST-for-routes vs SSH-for-netwatch vs add-REST-netwatch-handler — is the central decision this research informs.)

### Deferred Ideas (OUT OF SCOPE)

- Dedicated least-privilege read-only RouterOS user (mechanical RouterOS-side enforcement) — rejected for 258 in favor of allowlist-layer enforcement (D2). Could revisit in a future milestone.
- `deploy.sh` credential automation — deferred (D3 keeps provisioning operator-driven).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| ACCESS-01 | Diagnose root cause of inaccessible `/etc/wanctl/ssh/router.key` on `cake-shaper` — presence, path, ownership, perms, service user — and document it. | Root cause is two-layered (see Summary + Pitfall 1). v1.56 used a nested `sudo -n ssh -i /etc/wanctl/ssh/router.key admin@10.10.99.1` path that failed `returncode=255`. The diagnosis must distinguish *that* shell-level SSH-key failure from the *daemon's* REST-client netwatch failure. Operator commands provided in "Open Questions / operator-run inspection." |
| ACCESS-02 | Repair or establish a *supported* read-only RouterOS access path, proven by a live read-only command. | Route read already works over REST (reconciliation returned `route_count=3` in 257). Netwatch read does NOT work over REST (no handler). The supported-path decision and proof commands are in "Architecture Patterns" + "Code Examples." |
| ACCESS-03 | Access path is least-privilege and read-only; cannot mutate. | Enforced at the Phase 257 allowlist-validator layer (D2). Validator already rejects mutating RouterOS verbs + shell metacharacters. Generalization plan in "Don't Hand-Roll" + "Code Examples." |
| SAFE-21 | No RouterOS route mutation, Netwatch disablement, CAKE/qdisc change, threshold retuning, or route-owner flip during diagnosis/repair. | All proof commands are `print`-only. Validator's `FORBIDDEN_ROUTEROS_ACTIONS` blocks `set/add/remove/enable/disable/run/import/reset`. Inspection-only throughout. |
</phase_requirements>

## Summary

The working hypothesis in D1 — "production steering uses REST, so reuse REST and drop the SSH-key repair" — is **half right and half wrong, and the wrong half is exactly the part Phase 259 needs.** Two independent facts decide this phase:

1. **The live steering daemon uses REST.** `configs/steering.yaml` deployed on `cake-shaper` sets `router.transport: "rest"`, `host: 10.10.99.1`, `port: 443`, `verify_ssl: false`, `password: ${ROUTER_PASSWORD}`. The daemon constructs `get_router_client_with_failover(config)` (REST primary, SSH fallback). This is confirmed in repo config and corroborated by the Phase 257 transcript (steering service healthy, route reconciliation succeeded with `route_count=3`). [VERIFIED: repo config + 257 transcript]

2. **REST cannot read Netwatch.** `routeros_rest.py::_execute_single_command` routes only `/queue tree`, `/ip firewall mangle`, and `/ip route` commands. There is **no `/tool netwatch` handler** — a `/tool netwatch print detail` falls through to `Unsupported command for REST API`, returns `None` → `run_cmd` returns `rc=1`, and `RouteOwnershipGuard` fails closed with `status="error"`. This is the **exact** failure recorded in the Phase 257 readiness packet: `guard.status=error`, `blocked_reason: "failed to read RouterOS netwatch: Command failed"`. [VERIFIED: src/wanctl/routeros_rest.py lines 260–296 + 257 transcript line 184]

So the v1.56 "not-ready" had **two distinct broken paths**, not one:
- **(a) Daemon path:** the steering daemon's own REST client could read routes but not netwatch → guard error. (This is the real blocker for inspection.)
- **(b) Manual evidence path:** the Phase 257 operator used a *nested SSH* command `sudo -n ssh -i /etc/wanctl/ssh/router.key admin@10.10.99.1 "..."` that failed `returncode=255` because `router.key` was inaccessible on `cake-shaper`. This SSH-key path is a *separate, parallel* access method the operator scripted for evidence — it is NOT how the daemon talks to RouterOS.

**Primary recommendation:** Resolve the transport fork explicitly. The cleanest supported path that satisfies D1's "reuse a proven path" intent AND reads *both* objects is to **keep REST as the transport and add a read-only `/tool netwatch print` handler to `RouterOSREST`** (the REST endpoint is `GET /rest/tool/netwatch`). Routes already work over REST. This avoids re-incurring the `router.key` provisioning failure entirely (honoring D1's risk rationale), keeps a single transport, and the new code is read-only (GET) by construction. The Phase 257 allowlist validator is carried forward as the D2/ACCESS-03/SAFE-21 enforcement layer. If the operator instead prefers the nested-SSH path, that requires fixing `router.key` ownership/perms on `cake-shaper` and is a second, redundant credential surface — research recommends against it.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Reach RouterOS from `cake-shaper` | RouterOS REST API (443) via `RouterOSREST` | SSH fallback via `RouterOSSSH` (`router.key`) | Live steering daemon is REST-primary with auto-failover; this is the proven host→router path. |
| Read `/ip route` state | `RouterOSREST._handle_route_print` (`GET /rest/ip/route`) | SSH `/ip route print` | Already works over REST — reconciliation read 3 routes in 257. |
| Read `/tool netwatch` state | **MISSING** — needs new `RouterOSREST` handler (`GET /rest/tool/netwatch`) | SSH `/tool netwatch print detail` (paramiko) | REST has no handler today; this is the v1.56 blocker. |
| Read-only enforcement | Phase 257 command-file allowlist validator (process/operator layer) | n/a (RouterOS-side user policy explicitly deferred per D2) | D2 locks enforcement at the allowlist layer, not RouterOS permissions. |
| Credential storage | `/etc/wanctl/secrets` (`ROUTER_PASSWORD`), read by the service user's env | n/a | D3 reuses the existing REST-password secret pattern; no new key needed if REST. |
| Proof / evidence rendering | Operator-run `! <command>` against the chosen transport | wanctl in-process call through `get_router_client(config)` | D3 + operator-at-keyboard constraint for any privileged read. |

## Standard Stack

N/A — no new external dependencies. The phase operates entirely on existing, already-vendored components:

| Component | Location | Role in this phase |
|-----------|----------|--------------------|
| `RouterOSREST` | `src/wanctl/routeros_rest.py` | REST transport; needs a read-only `/tool netwatch print` GET handler added. |
| `RouterOSSSH` | `src/wanctl/routeros_ssh.py` | SSH fallback transport (paramiko); keyed on `router.ssh_key`. Relevant only if SSH path chosen. |
| `get_router_client` / `get_router_client_with_failover` | `src/wanctl/router_client.py` | Transport factory; inspection must go through this, not a bespoke client. |
| `RouteOwnershipGuard` | `src/wanctl/steering/route_ownership_guard.py` | Existing read-only Netwatch+script inspector; consumes whatever the transport returns. The downstream consumer of the netwatch read. |
| Phase 257 allowlist validator | `.planning/milestones/v1.56-phases/257-.../evidence/phase257-readonly-validator-20260620T120700Z.py` | D2 keeper enforcement mechanism — generalize, don't rebuild. |
| `requests` | already a project dep (used by `RouterOSREST`) | HTTP client for REST. |
| `paramiko` | already a project dep (used by `RouterOSSSH`) | SSH client (only if SSH path chosen). |

**Installation:** None.

## Package Legitimacy Audit

N/A — no packages installed. (slopcheck not run because there is nothing to check.)

## Architecture Patterns

### System Data Flow (current vs. required)

```
                         cake-shaper (host running steering.service)
                         ┌────────────────────────────────────────────┐
 operator `! <cmd>` ───▶ │  in-proc inspection / proof call             │
                         │     │                                        │
                         │     ▼  get_router_client(config)             │
                         │  ┌──────────────────────────────────────┐    │
                         │  │ FailoverRouterClient (REST primary)   │    │
                         │  │   ROUTER_PASSWORD ◀── /etc/wanctl/secrets│  │
                         │  └───────┬───────────────────┬──────────┘    │
                         └──────────│                   │───────────────┘
                                    │ REST GET 443      │ SSH fallback (router.key)
                                    ▼                   ▼
                  ┌─────────────────────────┐   ┌──────────────────────┐
                  │ RouterOS 10.10.99.1 :443│   │ RouterOS 10.10.99.1:22│
                  │  /rest/ip/route   ✅ WORKS│   │ /ip route print  ✅   │
                  │  /rest/tool/netwatch ❌  │   │ /tool netwatch print ✅│
                  │   (NO HANDLER — blocker) │   │ (but router.key 255 ❌)│
                  └─────────────────────────┘   └──────────────────────┘
```

Trace of the v1.56 failure: route reconciliation took the REST `GET /rest/ip/route` path and returned 3 routes (`reconciliation.status=ok`, `route_count=3`); the ownership guard took the REST `/tool netwatch print detail` path, hit `Unsupported command for REST API`, and returned `guard.status=error`. Separately, the operator's manual evidence script took the nested-SSH `router.key` path and got `returncode=255`. Both the route read (REST) and the netwatch read (SSH) individually have a working method on the router — they were just never available *through one supported path on `cake-shaper`*.

### Pattern 1: Add a read-only REST handler (RECOMMENDED)

**What:** Extend `RouterOSREST._execute_single_command` to recognize `/tool netwatch print` (and `/tool/netwatch/print`) and dispatch to a new `_handle_netwatch_print` that issues `GET {base_url}/tool/netwatch`, mirroring the existing `_handle_route_print` (lines 609–641).

**When to use:** Chosen transport stays REST (D1 intent: single proven path from this host). This is the lowest-risk supported way to make *both* required reads succeed over the path the daemon already uses.

**Why this is read-only by construction:** the handler only issues HTTP `GET`. There is no write verb. It cannot mutate. ACCESS-03/SAFE-21 hold at the code level *and* at the allowlist-validator level.

**Example (mirror of existing route-print handler):**
```python
# Source: pattern lifted from src/wanctl/routeros_rest.py::_handle_route_print (lines 609-641)
def _handle_netwatch_print(
    self, cmd: str, timeout: int | None = None
) -> list[dict[str, Any]] | None:
    """Handle /tool netwatch print commands via REST (read-only GET)."""
    timeout_val = timeout if timeout is not None else self.timeout
    url = f"{self.base_url}/tool/netwatch"
    try:
        resp = self._request("GET", url, timeout=timeout_val)
        if not resp.ok:
            self.logger.error(f"Failed to get netwatch: {resp.status_code}")
            return None
        return resp.json()  # list[dict]
    except requests.RequestException as e:
        self.logger.error(f"REST API error getting netwatch: {e}")
        return None
```
And the dispatch line in `_execute_single_command` (near line 286):
```python
if cmd.startswith("/tool netwatch print") or cmd.startswith("/tool/netwatch/print"):
    return self._handle_netwatch_print(cmd, timeout=timeout_val)
```

### Pattern 2: Fix the SSH-key path instead (ALTERNATIVE — research recommends against)

**What:** Provision `/etc/wanctl/ssh/router.key` on `cake-shaper` with correct owner/perms for the steering service user, and use SSH transport (or the nested `sudo -n ssh` evidence form) for netwatch.

**When this makes sense:** Only if RouterOS REST does not actually expose `/rest/tool/netwatch` on the deployed RouterOS version (verify — see Open Questions), or if the operator has a standing reason to prefer SSH. Routes still read fine over REST, so this would create a *split-transport* inspection (routes REST, netwatch SSH) unless the daemon transport is flipped to SSH wholesale — which would regress the proven REST steering path.

**Tradeoff:** Reintroduces the exact `router.key` provisioning/permission surface that caused the v1.56 failure (D1 explicitly wants to avoid this). Two credential surfaces instead of one.

### Anti-Patterns to Avoid

- **Building a bespoke RouterOS client for inspection.** The factory (`get_router_client`) and `RouteOwnershipGuard` already exist and are the consumers Phase 259 will use. A parallel client diverges from the daemon's real behavior and would not actually prove the daemon can inspect.
- **Proving access with only one read.** D4 explicitly rejects single-command proof; route-read-only would mask the netwatch gap (that's precisely how v1.56 slipped to "not-ready").
- **Flipping the daemon transport to SSH to get netwatch.** Regresses the proven REST steering path for mangle/route ops; high blast radius on a production control host.
- **Minting a RouterOS read-only user in this phase.** Explicitly deferred by D2.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Read-only command enforcement | A new guard/validator | Generalize the Phase 257 `phase257-readonly-validator` (allowlist + `FORBIDDEN_ROUTEROS_ACTIONS` + shell-metachar rejection) | D2 locks it as the keeper; it already has a negative self-test and blocks `set/add/remove/enable/disable/run/import/reset` and `; && | \` $( > <`. |
| RouterOS transport selection | New connection code | `get_router_client(config)` / `get_router_client_with_failover(config)` | Already abstracts REST↔SSH with failover; matches how the live daemon connects. |
| Netwatch/script conflict parsing | New parser | `RouteOwnershipGuard.inspect()` | Already parses netwatch JSON, resolves referenced scripts, detects inline route mutation, fails closed. It just needs the transport to actually return netwatch JSON. |
| Route owner attribution | New logic | `RouteManager` reconciliation + `_active_owner()` | Already reads `/ip route print detail where comment=...` over REST and attributes `netwatch`/`wanctl`/`unknown`. (This is Phase 259's surface, but confirms route-read works today.) |

**Key insight:** Nearly everything needed already exists and is wired into the steering daemon. The single missing primitive is a **REST `/tool netwatch print` GET handler**. The phase is small and surgical, not a build-out.

## Runtime State Inventory

> This is a credential/transport-repair phase, not a rename. Included because there is host-side runtime state (a credential file + a deployed config) that a repo grep will not surface.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | None. No datastore keys involved. | None — verified: inspection reads RouterOS live state, writes no records. |
| Live service config | `steering.yaml` deployed at `/etc/wanctl/steering.yaml` on `cake-shaper` sets `router.transport: "rest"` (repo `configs/steering.yaml` is the source-of-truth template; **verify deployed copy matches** — see operator commands). `route_management.enabled=true, mode=dry_run` is live per 257 transcript. | Operator verification only (read `/etc/wanctl/steering.yaml` transport key). No mutation. |
| OS-registered state | `steering.service` registered + active on `cake-shaper` (`ExecStart=python3 -m wanctl.steering.daemon --config /etc/wanctl/steering.yaml`, NRestarts=0 per 257). | None — do not restart in this phase (inspection-only). |
| Secrets/env vars | `ROUTER_PASSWORD` in `/etc/wanctl/secrets`, read by the steering service env → consumed by `RouterOSREST`. If REST path chosen, **this is the only credential needed** and it is already present (route reads succeeded → password works). `/etc/wanctl/ssh/router.key` exists in config but was **inaccessible** to the nested-SSH evidence path on `cake-shaper`. | If REST: verify `ROUTER_PASSWORD` is readable by the inspection code path's user (D3). If SSH chosen: diagnose+fix key owner/perms (operator at keyboard). |
| Build artifacts | None relevant. | None. |

**Canonical question answered:** After repo changes, the runtime state that matters is (1) the deployed `steering.yaml` transport value on `cake-shaper`, and (2) which credential the inspection code path's user can actually read. Both must be confirmed live before declaring ACCESS-02 proven.

## Common Pitfalls

### Pitfall 1: Treating "router.key inaccessible" as THE root cause (ACCESS-01 trap)
**What goes wrong:** ACCESS-01 is phrased around `/etc/wanctl/ssh/router.key`. Diagnosing only the key misses that the *daemon* never used the key — it used REST and failed on netwatch specifically. Fixing the key alone would still leave the daemon's netwatch read broken.
**Why it happens:** v1.56's manual evidence script used nested SSH (`sudo -n ssh -i router.key`), so the visible error was `returncode=255` / key inaccessible. That's the *evidence-path* failure, not the *daemon-path* failure.
**How to avoid:** Document BOTH failure modes in the ACCESS-01 root-cause writeup: (a) REST has no `/tool netwatch` handler → `guard.status=error` (the real inspection blocker); (b) the nested-SSH evidence path's `router.key` was inaccessible (a parallel, now-avoidable surface). State which one the chosen path resolves.
**Warning signs:** A plan task that only `chmod`/`chown`s `router.key` and re-runs an SSH command, with no netwatch-over-REST work.

### Pitfall 2: REST `verify_ssl: false` masking a real connectivity failure
**What goes wrong:** `steering.yaml` sets `verify_ssl: false` (self-signed router cert). A proof that "succeeds" might be hitting the wrong endpoint or silently degraded.
**How to avoid:** Use `RouterOSREST.test_connection()` (issues `GET /rest/system/resource`) as a connectivity precondition before the route/netwatch proof, and assert non-empty parseable JSON (D4), not just HTTP 200.
**Warning signs:** Empty `[]` netwatch result treated as success — distinguish "no netwatch entries configured" from "endpoint returned nothing." (RouterOS Netwatch is the interim route owner, so a non-empty result is expected.)

### Pitfall 3: Allowlist validator anchored to exact literal strings
**What goes wrong:** The Phase 257 validator's `ALLOWED_COMMANDS` is an exact-match set of full nested-SSH command strings. Generalizing it naively (just adding new literals) keeps it brittle.
**How to avoid:** When carrying it forward (D2), generalize the *predicate* (read-only verb + no shell metachars + RouterOS object in a read allowlist like `{/ip route print, /tool netwatch print, /system script print}`) rather than pinning full command literals. Keep the negative self-test.
**Warning signs:** A new evidence command rejected by the validator solely because its literal wasn't pre-listed, even though it is a `print`.

### Pitfall 4: Restarting steering.service to "apply" inspection changes
**What goes wrong:** SAFE-21 + production-control-host caution. A daemon restart during this phase is an unnecessary mutation of a live steering service.
**How to avoid:** Prove the path with an out-of-process operator `! <command>` (in-proc `get_router_client(config)` call or direct REST GET), not by bouncing the service. Code changes to `RouterOSREST` land in repo; deploying/restarting is a separate, later, operator-gated step (likely Phase 259).

## Code Examples

### Proof command — both reads via the chosen REST transport (D4)

Operator-run, read-only, in-process through the real factory (recommended proof shape):
```python
# Source: composed from src/wanctl/router_client.py + routeros_rest.py (this repo)
# Run on cake-shaper with ROUTER_PASSWORD in env (same as steering.service).
import logging, json
from wanctl.router_client import get_router_client
# config object must carry router_transport="rest", router_host="10.10.99.1",
# router_user="admin", router_password="${ROUTER_PASSWORD}", router_port=443,
# router_verify_ssl=False  (mirrors /etc/wanctl/steering.yaml)

log = logging.getLogger("phase258")
client = get_router_client(cfg, log)
assert client.test_connection(), "REST /system/resource unreachable"   # precondition

rc_r, out_r, err_r = client.run_cmd("/ip route print", capture=True, timeout=5)
rc_n, out_n, err_n = client.run_cmd("/tool netwatch print", capture=True, timeout=5)
assert rc_r == 0 and json.loads(out_r), f"route read failed: {err_r}"
assert rc_n == 0 and json.loads(out_n), f"netwatch read failed: {err_n}"   # needs new handler
print("ACCESS-02 PROVED: both reads exit 0, non-empty, parseable")
client.close()
```
Note: the netwatch assertion **fails today** until Pattern 1's handler is added — that failure *is* the demonstration of the v1.56 blocker.

### Transport equivalence — REST path vs SSH CLI form (answers Open Question 4)

| Read | SSH CLI form (paramiko / nested ssh) | REST form (requests) |
|------|--------------------------------------|----------------------|
| Routes | `/ip route print detail` (or `... where comment="X"`) | `GET https://10.10.99.1:443/rest/ip/route` → JSON list. Handled by `_handle_route_print`. ✅ exists |
| Netwatch | `/tool netwatch print detail` | `GET https://10.10.99.1:443/rest/tool/netwatch` → JSON list. **No handler — must add** `_handle_netwatch_print`. ❌ missing |
| System scripts (guard dep) | `/system script print detail` | `GET .../rest/system/script` → JSON list. **Also no handler** — guard reads scripts too (`SCRIPT_PRINT`); add alongside netwatch if guard is to run fully over REST. |

> IMPORTANT for planning: `RouteOwnershipGuard.inspect()` reads BOTH `/tool netwatch print detail` AND `/system script print detail`. If the goal is the guard working end-to-end over REST (Phase 259), **two** handlers may be needed (`/tool/netwatch` and `/system/script`), not one. For Phase 258's narrower D4 proof, netwatch + route is sufficient, but flag the script-read gap so 259 isn't surprised. [VERIFIED: route_ownership_guard.py lines 63-64]

### Generalized read-only validator predicate (carry-forward of Phase 257, D2)
```python
# Generalize phase257-readonly-validator: predicate over verbs + objects,
# instead of exact-literal ALLOWED_COMMANDS.
READ_ONLY_ROUTEROS_OBJECTS = (
    "/ip route print", "/ip/route/print",
    "/tool netwatch print", "/tool/netwatch/print",
    "/system script print", "/system/script/print",
)
# Keep existing FORBIDDEN_SUBSTRINGS (shell metachars) and
# FORBIDDEN_ROUTEROS_ACTIONS (set/add/remove/enable/disable/run/import/reset).
# A command passes only if: no forbidden substring, no forbidden action,
# AND it starts with one of READ_ONLY_ROUTEROS_OBJECTS. Retain the negative self-test.
```

## State of the Art

| Old Approach (v1.56) | Current/Required Approach (v1.57 P258) | When Changed | Impact |
|----------------------|----------------------------------------|--------------|--------|
| Netwatch read attempted via nested `sudo -n ssh -i router.key` evidence script | Netwatch read via REST `GET /rest/tool/netwatch` (new handler) over the daemon's actual transport | This phase | Removes the `router.key` provisioning surface; single transport. |
| Route read via REST (already working) | Unchanged — keep REST route read | — | No change; already proven. |
| Read-only enforced by exact-literal allowlist (257) | Generalized read-only predicate (verb + object allowlist) | This phase (D2 carry-forward) | Less brittle, reusable for 259/260 evidence. |

**Deprecated/outdated for this phase:**
- The v1.56 SSH-key repair line of work — D1 drops it *if* REST is confirmed as the path AND the netwatch handler is added. `router.key` remains a configured SSH-fallback credential but is not the inspection path.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | RouterOS (deployed firmware on 10.10.99.1) exposes `/rest/tool/netwatch` as a readable GET endpoint. | Summary, Pattern 1 | If the firmware/REST build doesn't expose it, the REST-handler approach fails and the phase must fall back to the SSH path (Pattern 2). MUST verify on the live router before locking the plan. RouterOS 7.x REST generally mirrors CLI menus, so this is likely — but unverified against this device. [ASSUMED] |
| A2 | The deployed `/etc/wanctl/steering.yaml` on `cake-shaper` matches the repo template's `router.transport: "rest"`. | Runtime State Inventory | If the deployed copy differs (e.g., someone set `ssh`), the failover/primary reasoning changes. Operator should read the live file. [ASSUMED — repo is described as drift-proof source of truth, but confirm] |
| A3 | `ROUTER_PASSWORD` in `/etc/wanctl/secrets` is readable by whatever user runs the inspection proof. Route reads succeeding in 257 implies the *daemon* user can read it; an operator-run `! <cmd>` may run as a different user/env. | D3, Pitfall | If the proof runs as a user without the secret in env, it fails spuriously and gets misdiagnosed as a router problem. Run proof with the same env as `steering.service` (e.g., via the unit's EnvironmentFile or `sudo -u <svc-user>`). [ASSUMED] |
| A4 | A non-empty netwatch result is expected (Netwatch is the interim route owner). | Pitfall 2, Code Examples | If netwatch is actually empty, an `[]` could be wrongly treated as failure or success. Confirm at least one enabled netwatch entry exists. [ASSUMED — consistent with milestone narrative] |

## Open Questions (RESOLVED-IN-EXECUTION)

> **Disposition (added during plan verification, Phase 258):** All three questions are structurally handled by the plans rather than answered at plan-time.
> - **Q1 (A1):** RESOLVED at Plan 258-03 Checkpoint A — a blocking `! <command>` operator gate verifies `/rest/tool/netwatch` live before the proof; on 404 the plan forks to Pattern 2 (SSH `router.key` repair) and records the fork.
> - **Q2 (system/script scope):** RESOLVED — Plan 258-02 treats the `system/script` handler as optional forward-compat for Phase 259; 258's scope stays "prove route+netwatch."
> - **Q3 (proof user/env):** RESOLVED — Plan 258-03 Checkpoint B runs the proof under `steering.service`'s environment so `ROUTER_PASSWORD` resolves identically.

1. **Does RouterOS at 10.10.99.1 expose `/rest/tool/netwatch` (and `/rest/system/script`)?** (Resolves A1; decides Pattern 1 vs Pattern 2.)
   - What we know: REST mirrors CLI menus on RouterOS 7.x; `/rest/ip/route` works here.
   - What's unclear: whether the deployed firmware exposes the `tool/netwatch` and `system/script` REST sub-paths.
   - Recommendation: operator runs the inspection commands below before plan lock.

2. **Does the daemon need the `/system script` read too, or just netwatch+route?** (Scopes the handler work.)
   - The guard reads both netwatch and scripts. Phase 258's D4 proof needs route+netwatch. Recommend adding the `system/script` handler in the same change so Phase 259's guard runs fully over REST, but flag it so 258's scope stays "prove route+netwatch."

3. **Which user/env will run the ACCESS-02 proof?** (Resolves A3.) Recommend running with `steering.service`'s environment so `ROUTER_PASSWORD` resolves identically.

### Operator-run inspection commands (`! <command>` — privileged reads on cake-shaper)

> Per D3 + operator-at-keyboard constraint, hand these to Kevin rather than escalating. All are read-only.

```bash
# (1) Confirm deployed steering transport + endpoint (A2)
! ssh cake-shaper 'grep -E "transport|host|port|verify_ssl" /etc/wanctl/steering.yaml'

# (2) Confirm ROUTER_PASSWORD presence + readability (A3) — show only that it is set, not the value
! ssh cake-shaper 'sudo test -r /etc/wanctl/secrets && echo SECRETS_READABLE; sudo grep -c ROUTER_PASSWORD /etc/wanctl/secrets'

# (3) Diagnose router.key for the ACCESS-01 writeup (presence/owner/perms) — even if dropping SSH path
! ssh cake-shaper 'sudo ls -l /etc/wanctl/ssh/router.key 2>&1; sudo stat -c "%U %G %a" /etc/wanctl/ssh/router.key 2>&1'

# (4) Does RouterOS REST expose netwatch + script? (A1) — read-only GET, verify_ssl off matches steering.yaml
! ssh cake-shaper 'source /etc/wanctl/secrets; curl -fsS -k -u "admin:$ROUTER_PASSWORD" https://10.10.99.1/rest/tool/netwatch | head -c 400; echo; curl -fsS -k -u "admin:$ROUTER_PASSWORD" https://10.10.99.1/rest/system/script | head -c 200'

# (5) Confirm REST route read still works (baseline parity with 257 reconciliation)
! ssh cake-shaper 'source /etc/wanctl/secrets; curl -fsS -k -u "admin:$ROUTER_PASSWORD" https://10.10.99.1/rest/ip/route | head -c 400'
```
If (4) returns parseable JSON for netwatch, **Pattern 1 is confirmed viable** and the SSH-key repair is dropped (D1). If (4) 404s/errors on netwatch, fall back to Pattern 2 and the ACCESS-01 `router.key` diagnosis from (3) becomes load-bearing.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| RouterOS REST API (443) on 10.10.99.1 | REST transport / route reads | ✓ (route reads succeeded in 257) | — (verify firmware) | SSH transport (22) |
| `/rest/tool/netwatch` endpoint | netwatch read over REST | ✗ unverified (A1) | — | SSH `/tool netwatch print detail` (needs `router.key` repair) |
| `ROUTER_PASSWORD` (`/etc/wanctl/secrets`) | REST auth | ✓ (route reads worked → password valid) | — | — |
| `/etc/wanctl/ssh/router.key` on cake-shaper | SSH fallback / nested-ssh evidence | ✗ inaccessible in 257 (returncode 255) | — | REST (preferred) |
| `requests`, `paramiko` (Python) | REST / SSH clients | ✓ existing project deps | — | — |

**Missing dependencies with no fallback:** None — both reads have at least one viable method on the router; the phase decides which supported path to wire on `cake-shaper`.
**Missing dependencies with fallback:** `/rest/tool/netwatch` (fallback: SSH netwatch read, contingent on `router.key` repair).

## Validation Architecture

> `nyquist_validation: true` in config — section included.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (per `pyproject.toml` / CLAUDE.md) |
| Config file | `pyproject.toml` (`.venv/bin/pytest`) |
| Quick run command | `.venv/bin/pytest -o addopts='' tests/test_route_ownership_guard.py tests/test_route_manager.py -q` |
| Full suite command | `.venv/bin/pytest tests/ -v` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| ACCESS-02 | `RouterOSREST` parses/dispatches `/tool netwatch print` to a GET handler returning JSON | unit | `.venv/bin/pytest tests/test_routeros_rest.py -k netwatch -q` | ❌ Wave 0 (add netwatch-handler test; mirror existing route-print tests if present) |
| ACCESS-02 | route read still dispatches correctly (no regression) | unit | `.venv/bin/pytest tests/test_routeros_rest.py -k route -q` | ⚠️ verify `tests/test_routeros_rest.py` exists; add if missing |
| ACCESS-03 / SAFE-21 | generalized read-only validator accepts `print` objects, rejects mutating verbs + shell metachars | unit | `.venv/bin/pytest tests/test_readonly_validator.py -q` + validator `--self-test` | ❌ Wave 0 (port Phase 257 validator + its negative self-test into `tests/`) |
| ACCESS-01 (guard wiring) | guard returns `ok`/`conflict` (not `error`) when netwatch JSON is returned | unit | `.venv/bin/pytest tests/test_route_ownership_guard.py -q` | ✅ exists (FakeRouter already returns netwatch JSON) |

### Sampling Rate
- **Per task commit:** `.venv/bin/pytest -o addopts='' tests/test_route_ownership_guard.py tests/test_route_manager.py -q`
- **Per wave merge:** add `tests/test_routeros_rest.py` + `tests/test_readonly_validator.py`
- **Phase gate:** full suite green before `/gsd:verify-work`; PLUS the operator-run live ACCESS-02 proof (both reads exit 0, parseable) — the live proof is the D4 acceptance gate and cannot be satisfied by unit tests alone.

### Wave 0 Gaps
- [ ] `tests/test_routeros_rest.py` — netwatch-handler dispatch + GET-only assertion (covers ACCESS-02). Verify whether this file already exists; if so, extend it.
- [ ] `tests/test_readonly_validator.py` — generalized read-only predicate + negative self-test (covers ACCESS-03/SAFE-21).
- [ ] Live proof harness/script (operator-run) producing the D4 two-read evidence artifact — not a pytest, an evidence command file validated by the carried-forward allowlist validator.

## Security Domain

> `security_enforcement` not set false in config; included but scoped — this is an internal RouterOS credential/transport phase, not a web-facing surface.

### Applicable controls (scoped to this phase)

| Concern | Applies | Standard Control (already present) |
|---------|---------|-----------------------------------|
| Read-only enforcement (no mutation) | yes | Phase 257 allowlist validator: rejects RouterOS mutating verbs + shell metacharacters; guard/manager fail closed on parse/read error. |
| Command injection (nested-ssh / CLI) | yes | Validator `FORBIDDEN_SUBSTRINGS` blocks `; && || | \` $( > <`. REST path avoids shell entirely (HTTP GET via `requests`, no `shell=True`). |
| Credential exposure | yes | `ROUTER_PASSWORD` stays in `/etc/wanctl/secrets`; daemon clears in-memory password post-construction (`clear_router_password`). Operator proof commands print only presence, never the value. |
| Transport confidentiality | partial | REST uses HTTPS but `verify_ssl: false` (self-signed router cert) — pre-existing, in-scope of LAN-trusted router link; do NOT change cert posture in this phase (out of scope). |
| Least privilege (RouterOS-side) | deferred | D2 explicitly defers RouterOS read-only user; steering creds retain write capability, mitigated at allowlist layer. Document this accepted residual. |

### Threat note
The accepted residual (D2): the reused steering credential *can* write mangle/route rules at the RouterOS permission layer. SAFE-21 + ACCESS-03 are therefore enforced procedurally (allowlist validator + `print`-only commands + GET-only REST handler), not by RouterOS RBAC. This is a deliberate, documented tradeoff — surface it in the ACCESS-03 evidence so the residual is explicit, not silent.

## Sources

### Primary (HIGH confidence — this repo, deployed code/config + 257 evidence)
- `src/wanctl/routeros_rest.py` (lines 260–296 dispatch; 609–641 route handler) — confirms REST handles `/ip route`, lacks `/tool netwatch`.
- `src/wanctl/router_client.py` — transport factory + failover (REST primary, SSH fallback).
- `src/wanctl/routeros_ssh.py` — SSH transport, keyed on `router.ssh_key`.
- `src/wanctl/steering/route_ownership_guard.py` (lines 63–64) — guard reads `/tool netwatch print detail` + `/system script print detail`.
- `src/wanctl/steering/route_manager.py` (lines 136–184, 398–415) — reconciliation reads `/ip route print detail where comment=...`; owner attribution.
- `src/wanctl/steering/daemon.py` (lines 834, 1185–1218) — daemon builds failover client; guard instantiated on `self.router.client`.
- `configs/steering.yaml` — deployed-template transport (`rest`), host/port/secret.
- `.planning/codebase/INTEGRATIONS.md` — RouterOS transport overview.
- `.planning/milestones/v1.56-phases/257-.../evidence/phase257-readonly-validator-20260620T120700Z.py` — D2 keeper validator.
- `.planning/milestones/v1.56-phases/257-.../evidence/phase257-observation-transcript-*.md` — live failure: `guard.status=error`, `route_count=3`, nested-ssh `returncode=255`.
- `.planning/milestones/v1.56-phases/257-.../257-01-SUMMARY.md` — not-ready blocker record.
- `.planning/STATE.md` — explicitly records "REST Netwatch inspection (`/tool netwatch print detail` unsupported over REST)".

### Secondary (MEDIUM)
- `tests/test_route_ownership_guard.py` — confirms guard's expected netwatch JSON shape (FakeRouter).

### Tertiary (LOW / to verify live)
- RouterOS 7.x REST exposing `/rest/tool/netwatch` and `/rest/system/script` — general RouterOS-7 behavior, unverified on this specific device (A1; operator command (4) verifies).

## Metadata

**Confidence breakdown:**
- Transport reality (steering=REST, REST reads routes not netwatch): HIGH — deployed code + 257 transcript agree exactly.
- Root-cause two-layer diagnosis (ACCESS-01): HIGH — both failures present in 257 evidence.
- REST netwatch endpoint existence (A1): MEDIUM-LOW — RouterOS-7 generally exposes it, unverified on this router; operator command (4) resolves before plan lock.
- Allowlist carry-forward (D2): HIGH — validator file read directly; generalization is mechanical.

**Research date:** 2026-06-20
**Valid until:** 2026-07-20 (stable internal integration; re-verify if the deployed `steering.yaml` transport or RouterOS firmware changes)
