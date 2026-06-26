# Phase 258 Context: Read-Only RouterOS Access Repair

**Phase:** 258 — Read-Only RouterOS Access Repair
**Milestone:** v1.57 Supported read-only RouterOS ownership inspection
**Date:** 2026-06-20
**Requirements:** ACCESS-01, ACCESS-02, ACCESS-03 (SAFE-21 cross-cutting)

## Domain

Establish and prove **one** supported, least-privilege, read-only path from `cake-shaper` to RouterOS so live Netwatch and default-route state can actually be read. This is the unblocking gate for the milestone — Phases 259 (inspection) and 260 (dry-run rerun) cannot produce evidence until a read-only RouterOS command returns real state from this host.

The v1.56 dry-run (Phase 257) ended `not-ready` because its RouterOS inventory used the **SSH transport** (`/etc/wanctl/ssh/router.key`) and the key was inaccessible on `cake-shaper`. The working hypothesis: v1.56 used the *wrong* transport — production steering already reaches RouterOS from `cake-shaper` by another path.

## Decisions (locked)

### D1 — Transport: match steering's live transport
Use whatever transport **production steering already uses** to reach RouterOS from `cake-shaper` (expected to be REST/password per `INTEGRATIONS.md`, which names REST the steering default). If steering uses REST, the v1.56 SSH-key repair is **dropped entirely** — `router.key` is not the path. Rationale: reuse a path already proven to work from this exact host; lowest risk; avoids re-incurring the key-provisioning failure surface.
- **Research must confirm first:** what transport + endpoint the live steering daemon actually uses on `cake-shaper`, and that REST (443) is reachable to the RouterOS host. Do not assume — verify against the deployed steering config/service.

### D2 — Read-only enforcement: allowlist layer, not RouterOS user policy
Reuse the existing steering credential rather than minting a dedicated read-only RouterOS user. Consequence (explicitly accepted): read-only-ness is **not** mechanically enforced at the RouterOS permission layer — steering creds can write mangle rules. Instead, read-only is enforced by the **deterministic command-file allowlist validator** established in v1.56 Phase 257 (`phase257-readonly-validator`). ACCESS-03 and SAFE-21 are satisfied at the allowlist/validator layer.
- **Implication for planning:** the allowlist/validator from Phase 257 is the keeper mechanism — carry it forward / generalize it, do not rebuild a parallel guard. Any inspection command must pass the read-only allowlist before execution.

### D3 — Provisioning: operator step + existing /etc/wanctl/secrets pattern
If any credential setup is needed on `cake-shaper`, it is a documented, repeatable step (repo script) that the **operator runs at the keyboard** (`! <command>`), with the credential stored via the existing `/etc/wanctl/secrets` pattern (same as `ROUTER_PASSWORD`). Not folded into `deploy.sh` (avoids pushing a privileged secret through the deploy path). Likely minimal/no provisioning if reusing steering creds already present on the host — provisioning then reduces to *verifying* the steering credential is readable by the inspection code path.
- **Operator-at-keyboard constraint:** privileged credential reads on `cake-shaper` are handed to Kevin as `! <command>`, not done via credential escalation.

### D4 — Proof of ACCESS-02: both reads, parseable
Proof = live `/ip/route/print` **and** `/tool/netwatch/print` (or transport-equivalent) each return exit 0 with non-empty, parseable output. Proving both now de-risks Phase 259, which needs exactly these two reads. Single-command proof rejected.

## Canonical refs (read before planning)

- `.planning/REQUIREMENTS.md` — v1.57 requirements (ACCESS-01/02/03, SAFE-21).
- `.planning/ROADMAP.md` — Phase 258 goal + dependency chain (258→259→260).
- `.planning/codebase/INTEGRATIONS.md` — RouterOS transports (REST default for steering; SSH key path; config keys `router.host/user/ssh_key/password/transport`; secret `ROUTER_PASSWORD` → `/etc/wanctl/secrets`).
- `src/wanctl/router_client.py` — transport factory (`get_router_client`, `get_router_client_with_failover`), REST↔SSH selection.
- `src/wanctl/routeros_rest.py` — `RouterOSREST` (password auth, REST default).
- `src/wanctl/routeros_ssh.py` — `RouterOSSSH` (key at `router.ssh_key`).
- `src/wanctl/check_config_validators.py` — `_check_ssh_key_path` and `router.ssh_key` validation (lines ~797–817).
- `.planning/milestones/v1.56-phases/257-dry-run-observation-canary-readiness-decision/evidence/phase257-readonly-validator-20260620T120700Z.py` — the read-only command-file allowlist validator (D2 keeper mechanism).
- `.planning/milestones/v1.56-phases/257-dry-run-observation-canary-readiness-decision/257-01-SUMMARY.md` — the not-ready blocker record (SSH inventory failure, guard.status=error).
- Live steering deployment on `cake-shaper` — the actual deployed steering config/service is the source of truth for D1's transport question (verify live, not from repo assumptions).

## Code context (reusable assets)

- **Transport is already abstracted** — `router_client.get_router_client(config)` returns REST or SSH by `router.transport`. Inspection should go through this factory, not a new bespoke client.
- **REST↔SSH failover exists** — `get_router_client_with_failover()` already retries REST→SSH; relevant if D1 lands on REST-primary.
- **Read-only allowlist validator exists** (Phase 257) — D2's enforcement mechanism; carry forward rather than rebuild.
- **Config validation exists** — `check_config_validators.py` already validates `router.ssh_key`/transport; extend rather than duplicate.

## Open questions for research (gsd-phase-researcher)

1. **What transport + endpoint does the live steering daemon on `cake-shaper` actually use to reach RouterOS?** (Confirms or refutes D1's REST hypothesis. Source of truth = deployed config/service on the host, not repo defaults.) Operator may need to run the inspection (`! <command>`).
2. Is the RouterOS REST endpoint (443) reachable from `cake-shaper`, and is `ROUTER_PASSWORD`/steering credential present and readable by the inspection code path's user?
3. Can the Phase 257 read-only allowlist validator be reused/generalized to cover `/ip/route/print` + `/tool/netwatch/print` over the chosen transport?
4. What exact read-only command syntax do route + netwatch reads take over the chosen transport (REST path form vs SSH CLI form)?

## Deferred ideas (not this phase)

- Dedicated least-privilege read-only RouterOS user (mechanical enforcement) — rejected for 258 in favor of allowlist-layer enforcement (D2); could revisit if a future milestone wants RouterOS-side read-only guarantees.
- `deploy.sh` credential automation — deferred (D3 keeps provisioning operator-driven).

## Safety boundary

SAFE-21: read-only / dry-run only. No RouterOS route mutation, no Netwatch disablement, no CAKE/qdisc change, no threshold retuning, no route-owner flip. The allowlist validator (D2) is the enforcement mechanism; any command outside the read-only allowlist is rejected before execution. Active canary remains a separate, explicit operator gate (out of scope here).
