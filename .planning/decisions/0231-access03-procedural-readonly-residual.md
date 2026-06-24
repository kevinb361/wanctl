# ACCESS-03 read-only RouterOS inspection is enforced procedurally, not by RouterOS RBAC

## Symptom

v1.57 Phase 258 repaired a supported read-only RouterOS inspection path from `cake-shaper` so the steering
guard can read `/ip route`, `/tool netwatch`, and `/system script` over the REST transport. ACCESS-03 requires
that the credential/method used for inspection *cannot* perform route mutation, Netwatch changes, or config
writes. The path that was built reuses the existing steering REST credential, which retains write capability at
the RouterOS permission (RBAC) layer. Read-only is therefore guaranteed by *convention in wanctl code* — GET-only
transport handlers plus `readonly_validator` command-file validation — not by a least-privilege RouterOS account.

A future operator reading `src/wanctl/readonly_validator.py` could reasonably assume the inspection credential is
itself least-privilege. It is not: nothing at the RouterOS layer stops that credential from writing. The protection
is that wanctl only ever issues GET-shaped reads through `_handle_netwatch_print` / `_handle_script_print`, and that
every proof command is validated (mutating verbs, shell metacharacters, unknown objects, embedded-substring and
prefix-boundary bypasses all rejected) before execution.

References: `.planning/phases/258-read-only-routeros-access-repair/evidence/258-03-access02-proof.md`
(section "ACCESS-03 residual"); `.planning/phases/258-read-only-routeros-access-repair/258-VERIFICATION.md`
(ACCESS-03 row: "Passed with explicit residual").

## Blast Radius

- Time window / scope: standing residual for the life of v1.57's read-only inspection path, on `cake-shaper`'s
  RouterOS REST access. Applies every steering cycle that runs the ownership guard.
- Recovery / reversal mechanism: provision a dedicated read-only RouterOS user and repoint the inspection
  transport credential at it, making read-only RBAC-enforced rather than convention-enforced (see Override Path).
- Frequency: steady state — the reused credential is in effect continuously, not just at restart.
- Not affected: this changes no live routing, Netwatch state, CAKE/qdisc config, or controller thresholds; it is
  an access-layer risk acceptance only. SAFE-21 (no mutation during v1.57) is independently held and proven.

## Evidence Links

- `.planning/phases/258-read-only-routeros-access-repair/evidence/258-03-access02-proof.md` — "ACCESS-03 residual"
  section; live proof `ACCESS02_PROOF_PASS route=17 netwatch=3 script=20`.
- `.planning/phases/258-read-only-routeros-access-repair/258-VERIFICATION.md` — frontmatter `ACCESS-03: passed`;
  row "Passed with explicit residual".
- `src/wanctl/readonly_validator.py` — the procedural guard; `--self-test` →
  `READONLY_COMMANDS_NEGATIVE_SELF_TEST_PASSED`.
- `tests/test_readonly_validator.py` — validator rejection coverage.
- `.planning/TRACEABILITY.md` (commit `ccbd502b`) — ACCESS-03 caveat section recording the missing signed waiver
  that this record now closes.

## Default Disposition

Accept procedural read-only enforcement for v1.57. The dedicated read-only RouterOS user (true RBAC-enforced
least-privilege) was the rejected fork (decision D2): it adds RouterOS user provisioning and credential-rotation
surface for an inspection-only milestone whose scope is explicitly read-only and whose mutation invariant
(SAFE-21) is independently proven. The reused-credential-plus-procedural-guard path satisfies ACCESS-03 as a
behavior guarantee. This residual is expected and does not constitute a regression when next observed — it is a
known, documented acceptance, not a defect.

## Override Path

If the operator instead requires RBAC-enforced least-privilege (the rejected fork), before relying on this path:
1. Provision a dedicated read-only RouterOS user (read policy only; no write/policy/ftp).
2. Repoint the inspection transport credential at that user in `/etc/wanctl/steering.yaml` / `/etc/wanctl/secrets`.
3. Re-run the Phase 258 live proof (`scripts/phase258-readonly-proof.py`) to confirm the three reads still pass.
4. Strike the Sign-Off below and supersede this record.

Rollback note: the change is config-only (credential repoint) — revert by restoring the prior `steering.yaml` /
`secrets` credential and restarting `steering.service`. No live routing, Netwatch, or CAKE state is touched by
either direction of this change, so there is no route-ownership rollback to stage.

## Sign-Off

Accepted: YES — read-only RouterOS inspection for v1.57 is enforced by GET-only handlers + `readonly_validator`,
not by RouterOS RBAC; the reused steering credential retains write capability at the RBAC layer.   Date: 2026-06-24   Operator: Kevin Blalock

> Authorized via `/saga-decision` session on 2026-06-24. Default Disposition accepted; Override Path NOT invoked.
> Recorded by Claude Code on operator instruction.
