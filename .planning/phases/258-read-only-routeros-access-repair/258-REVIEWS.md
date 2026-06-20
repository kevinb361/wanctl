---
phase: 258
reviewers: [codex]
review_cycles: 2
reviewed_at: 2026-06-20T14:30:00Z
plans_reviewed: [258-01-PLAN.md, 258-02-PLAN.md, 258-03-PLAN.md]
cycle_1_high: 4
cycle_2_high_open: 1
---

# Cross-AI Plan Review — Phase 258

> Executed inside Claude Code, so the Claude self-review is skipped for independence.
> External reviewer: Codex (`codex-cli 0.141.0`, default model).
> Two cycles recorded below. Cycle 1 raised 4 HIGH concerns; the plans were revised in
> commit `d0c0af90`; cycle 2 re-reviewed the revised plans. Cycle-2's load-bearing
> residual HIGH (Plan 03 proof harness runtime/config provenance) was independently
> verified against `deploy/systemd/steering.service:18` (`PYTHONPATH=/opt`) and
> `258-03-PLAN.md:246,173` before publishing — confirmed accurate.

# Cycle 2 (Re-Review of Revised Plans — current)

> Reviewed against revised plans at commit `d0c0af90`. Disposition of the 4 cycle-1
> HIGHs and any new HIGHs. **This is the authoritative current-state section.**

## Codex Cycle-2 Review

### Plan 258-01

**Summary** — Now documents the two-layer root cause and moves A1 into a blocking preflight before Plan 02. No longer treats the SSH-key failure as the only blocker; explicitly stops/replans if REST netwatch is absent.

**Strengths**
- Names both daemon-path gaps: `/tool netwatch print` and `/system script print`.
- Explains why netwatch-only leaves `RouteOwnershipGuard.inspect()` failing.
- Separates manual `router.key` evidence failure from daemon REST failure.
- A1 is a hard gate (`A1-failed = STOP`), not an inline SSH improvisation.
- Credential facts split into known-evidence vs operator-pending.

**Concerns**
- **MEDIUM:** A1 only probes `/rest/tool/netwatch`; Plan 02 and the guard also require `/rest/system/script`. D4 catches script failure later, but the preflight could fail earlier and cheaper.
- **LOW:** A1 records only an OK/fail marker; capturing HTTP status + parse result would reduce later ambiguity.

**Risk Assessment: LOW** — Read-only doc + GET preflight with fail-closed sequencing.

### Plan 258-02

**Summary** — Directly addresses the daemon REST gap: requires BOTH netwatch and script GET handlers, adds tests, proves the guard clears over mocked REST, and carries the validator forward with a safer anchored-prefix predicate.

**Strengths**
- `_handle_script_print` is REQUIRED, not optional.
- GET-only success/fail-closed tests specified for both new handlers.
- Guard-over-mocked-REST integration test proves both reads are load-bearing.
- Validator rejects mutation, shell metacharacters, unknown objects, and substring bypasses.
- Existing route dispatch explicitly protected from regression.

**Concerns**
- **LOW:** Tests should explicitly cover slash-form dispatch (`/tool/netwatch/print`, `/system/script/print`), not only space-form.
- **LOW:** `/system script print detail` can expose script source; downstream redaction should stay mandatory.

**Risk Assessment: LOW** — Narrow, test-backed, read-only by construction.

### Plan 258-03

**Summary** — Materially improved: validator-gated command file, a Python proof harness using `get_router_client`, deployed-code confirmation, and a three-read live proof. One HIGH remains: the plan does not quite prove the same deployed runtime/config path as `steering.service`.

**Strengths**
- Raw curl demoted to A1 only; D4 uses a Python harness through `get_router_client` + `run_cmd`.
- Full JSON parse required; no truncation.
- Proof includes route + netwatch + script; deployed-handler grep gates the live proof.
- ACCESS-03 residual accurately scoped as procedural, not RouterOS RBAC.

**Concerns**
- **HIGH:** The live proof command runs `cd /opt/wanctl && python3 /tmp/phase258-readonly-proof.py ...`, but `steering.service` runs with `Environment=PYTHONPATH=/opt` (`deploy/systemd/steering.service:18`). A `/tmp` harness without `PYTHONPATH=/opt` may import `wanctl` from a different path than the deployed daemon, or fail to import. The harness also "builds a minimal config object" mirroring `/etc/wanctl/steering.yaml` instead of loading it, so "same config/env as steering" is only partially proven.
- **MEDIUM:** The deploy command is full `./scripts/deploy.sh spectrum cake-shaper --with-steering`, which pushes config + steering config + systemd units + daemon-reload, not just code rsync as the plan implies.
- **LOW:** Proof runs as an operator shell, not clearly as the `wanctl` service user; fine for transport proof but does not prove service-user runtime equivalence unless recorded.

**Suggestions**
- Run proof with `PYTHONPATH=/opt`; have the harness assert `wanctl.__file__` / `routeros_rest.__file__` resolve under `/opt/wanctl`.
- Load the actual deployed `/etc/wanctl/steering.yaml`, or record field-by-field parsed values before building the config object.
- Replace full deploy with code-only rsync, or add before/after checksums for `/etc/wanctl/*.yaml` + systemd units.

**Risk Assessment: HIGH** — Proof is close, but the runtime/config provenance gap can still produce evidence that doesn't prove the supported steering path end-to-end.

## Prior HIGH Disposition (Cycle 1 → Cycle 2)

- **HIGH-1 (Plan 02, `/system script print` required): FULLY RESOLVED** — Plan 02 makes `/system script print` required, adds handler/tests, and includes a guard-over-REST integration proof.
- **HIGH-2 (Plan 03, proof through `get_router_client` not curl): PARTIALLY RESOLVED** — Raw curl is fixed and the harness goes through `get_router_client`, but Plan 03 still does not fully prove the *same deployed runtime/config path*: the harness uses a synthetic config object and the shown proof command omits `PYTHONPATH=/opt`. Verified against `steering.service:18` and `258-03-PLAN.md:173,246`.
- **HIGH-3 (Plan 03, deploy patched code to cake-shaper): FULLY RESOLVED** — Operator deploy step + deployed-code grep + proof sequencing added. The residual import-path issue is folded into HIGH-2, not counted separately.
- **HIGH-4 (Plan 03, SSH fallback under-specified): FULLY RESOLVED** — A1 is now a blocking Plan 01 gate; A1 failure stops and replans SSH as a separate phase, with no inline SSH fork.

## Cycle-2 Overall

- **Open HIGH count: 1** (HIGH-2 partially resolved — counts as open).
- **New separate HIGHs: 0.**
- **Overall risk: HIGH** until Plan 03 pins the proof harness to the deployed `/opt/wanctl` runtime (`PYTHONPATH=/opt`, assert `__file__` under `/opt/wanctl`) and loads the actual deployed steering config instead of a synthetic one.

**Recommended remediation (single, surgical):** In Plan 03, change the proof command to set `PYTHONPATH=/opt` and have the harness (a) assert `wanctl.__file__`/`routeros_rest.__file__` resolve under `/opt/wanctl`, and (b) load (or field-by-field record) the real `/etc/wanctl/steering.yaml` rather than building a synthetic config. This closes the last open HIGH without changing the phase's safety posture.

---

# Cycle 1 (Original Review of Initial Plans — historical)

> Retained for audit. All 4 cycle-1 HIGHs are dispositioned in the Cycle-2 section above.

## Codex Review

**Summary**

The plans are mostly well shaped and conservative, but they have two material gaps: Plan 02 makes `/system script print` optional even though `RouteOwnershipGuard.inspect()` requires it after Netwatch, and Plan 03's live proof says "go through `get_router_client`" while the actual operator proof uses raw `curl`. As written, the phase may prove that RouterOS REST exposes routes/netwatch, but not that wanctl's supported inspection path actually works end to end.

### PLAN 258-01

**Strengths**

- Correctly separates the daemon REST failure from the manual `router.key` SSH failure.
- Avoids mutating RouterOS or restarting services.
- Good explicit handling of D1: SSH-key repair is dropped if REST is the live steering path.
- Calls out sensitive credential facts without exposing secrets.

**Concerns**

- **MEDIUM:** `autonomous: true` conflicts with ACCESS-01 credential facts if owner/perms/service-user require privileged live reads. A doc full of `[OPERATOR-VERIFY]` placeholders may not actually satisfy ACCESS-01.
- **LOW:** Verification is grep-based and can pass with shallow wording rather than a real root-cause record.
- **LOW:** It should cite live deployed steering evidence, not just repo config, when saying steering uses REST.

**Suggestions**

- Make the credential-fact section explicitly "known from evidence" vs "operator-pending," and do not mark ACCESS-01 complete until required live-only fields are filled or formally scoped as non-blocking.
- Add a negative check that the evidence doc contains no secrets and no mutating RouterOS verbs.

**Risk Assessment: MEDIUM** — Documentation-only and safe, but there is a completeness risk around ACCESS-01 if operator-only credential facts remain unresolved.

### PLAN 258-02

**Strengths**

- The `_handle_netwatch_print` design matches the existing route handler and is read-only by HTTP method.
- Good unit-test shape: success, fail-closed, GET-only, route regression.
- Carrying forward the Phase 257 validator is the right direction for SAFE-21 procedural enforcement.
- Scope is mostly surgical and avoids control-loop logic.

**Concerns**

- **HIGH:** `/system script print detail` is optional, but `RouteOwnershipGuard.inspect()` reads Netwatch and then scripts. If only Netwatch is added, the guard will likely move from "failed to read netwatch" to "failed to read script," so the v1.56 blocker is not truly cleared for the guard path.
- **HIGH:** The validator is not wired into `RouterOSREST.run_cmd`; it only exists as a separate module unless the proof harness uses it. That is okay for evidence-command gating, but the plan overstates ACCESS-03 if it implies all live read-only access is mechanically enforced.
- **MEDIUM:** `READ_ONLY_ROUTEROS_OBJECTS` using "contains" is too loose. It should be anchored/parsed as the command object prefix after normalization.
- **MEDIUM:** A1 is unresolved before implementation. Adding the handler is low-risk, but if `/rest/tool/netwatch` is absent, the primary path fails and the fallback is not ready.
- **LOW:** The handler should fail closed on bad JSON shape too, or tests should document that downstream parsing owns shape validation.

**Suggestions**

- Make `_handle_script_print` required in Plan 02, with GET-only tests for `/system/script`.
- Add an integration-style test: `RouteOwnershipGuard(RouterOSREST)` with mocked REST route/netwatch/script responses returns a non-error result.
- Tighten validator parsing: normalize whitespace/slashes and require command to start with an allowed read object, not merely contain it.
- Reword ACCESS-03 as "procedural read-only enforcement for proof commands," unless the validator is actually integrated into the execution harness.

**Risk Assessment: HIGH** — The code change itself is low-risk, but the plan can fail the real milestone goal because the guard needs `/system script` too.

### PLAN 258-03

**Strengths**

- Correctly makes live proof operator-driven and blocks on human verification.
- Explicitly handles A1 instead of assuming REST Netwatch support.
- Records the D2 residual: reused steering credentials can write at RouterOS RBAC.
- Keeps SAFE-21 language clear: GET/print only, no service restart, no Netwatch change.

**Concerns**

- **HIGH:** The proof claims it goes through `get_router_client`, but the actual checkpoint commands use raw `curl`. Raw REST success does not prove wanctl's REST dispatch handler, config loading, password resolution, or `run_cmd` contract.
- **HIGH:** There is no deployment/execution plan for running the patched Plan 02 code from `cake-shaper`. If `/opt/wanctl` is unchanged, the new handler is not being proven.
- **HIGH:** The SSH fallback is under-specified. "Fork to Pattern 2" is not enough for ACCESS-02: it needs concrete repair steps, validator coverage, proof commands, and a decision override because D1 dropped SSH if REST is steering's path.
- **MEDIUM:** `head -c 400` can truncate JSON, so it cannot reliably produce parseable proof evidence. It is fine for a quick A1 sniff, not D4 proof.
- **MEDIUM:** The command file validates RouterOS verbs, but the live commands executed are curl URLs. That means the validator does not actually gate the commands being run.
- **MEDIUM:** `curl -u "admin:$ROUTER_PASSWORD"` can expose the password to local process listings while running.

**Suggestions**

- Move the A1 probe before Plan 02, or add a blocking preflight between Plan 01 and Plan 02.
- Replace the final curl proof with a small Python harness on `cake-shaper` that: loads the same config/env as steering, calls `get_router_client`, validates the command file, runs `/ip route print`, `/tool netwatch print`, and preferably `/system script print`, parses full JSON and prints counts/redacted sample fields.
- Keep curl only as the A1 endpoint-existence probe.
- If A1 fails, require a separate SSH fallback plan instead of an inline fork.

**Risk Assessment: HIGH** — This is the highest-risk plan. It has the right safety posture, but as written it may prove the RouterOS REST API manually, not the supported wanctl inspection path.

### Overall

Overall risk: **HIGH until Plan 02 requires `/system script print` and Plan 03 proves through `get_router_client` using deployed/patched code on `cake-shaper`.**

Recommended default: keep the REST approach, but tighten the phase gate to "route + netwatch + script via wanctl client factory, command-file validated, full JSON parsed." If A1 fails, stop and write a real SSH fallback plan rather than trying to improvise it inside Plan 03.

---

## Consensus Summary

Single external reviewer (Codex). No cross-reviewer consensus is available, but the
findings were spot-checked against the codebase. The most actionable items:

### Verified Findings (checked against source)

- **Guard needs `/system script print` too (HIGH).** Confirmed: `RouteOwnershipGuard.inspect()`
  (`src/wanctl/steering/route_ownership_guard.py:69-76`) reads `NETWATCH_PRINT` then
  `SCRIPT_PRINT = "/system script print detail"`, each fail-closed via `_read_json_list`.
  Plan 02 leaves the `/system script` REST handler **optional**, so the daemon guard path would
  move from "failed to read netwatch" to "failed to read script" — the v1.56 blocker is not
  cleared for the guard. This should be promoted from optional to required in Plan 02.

### Key Concerns (highest priority)

1. **Proof transport mismatch (HIGH, Plan 03).** D4 proof and the README/CONTEXT say the proof
   goes through `get_router_client` (the wanctl factory), but the operator checkpoint commands are
   raw `curl` against `/rest/...`. Raw curl success proves the RouterOS REST API is reachable; it
   does **not** prove wanctl's dispatch handler, config/env loading, password resolution, or the
   `run_cmd` contract — i.e. the actual supported inspection path the milestone needs.
2. **No deployment of patched code to `cake-shaper` (HIGH, Plan 03).** Plan 02 adds the handler in
   the repo, but there is no step that gets that code onto `/opt/wanctl` on `cake-shaper` before the
   live proof. Without it, the proof exercises stock code, not the fix.
3. **SSH fallback under-specified (HIGH, Plan 03).** The A1-fail fork to "Pattern 2 (SSH router.key)"
   has no concrete repair steps, validator coverage, or proof commands, and it contradicts D1's
   "drop SSH if REST is steering's path." If A1 fails it should trigger a real replan, not an inline
   improvisation.
4. **`/system script print` REST handler missing (HIGH, Plan 02).** See verified finding above.

### Divergent Views

None — single reviewer.

### Note on validator/ACCESS-03 framing (MEDIUM)

Codex flags that the validator gates *evidence command files*, not the live `run_cmd` execution
path, and that the proof actually runs curl URLs rather than validator-gated RouterOS verbs. This is
consistent with D2's design intent (procedural allowlist on the command file, GET-only handler on the
transport), but the ACCESS-03 wording in the plans should say "procedural read-only enforcement for
proof commands" rather than implying mechanical enforcement on all live access. Worth tightening but
lower priority than the four HIGHs.
