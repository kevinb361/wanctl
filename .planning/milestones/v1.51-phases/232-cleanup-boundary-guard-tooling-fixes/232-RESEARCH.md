# Phase 232: Cleanup Boundary Guard + Tooling Fixes - Research

**Researched:** 2026-06-10
**Domain:** Internal repo tooling — bash guard scripts, pytest harnesses, planning-artifact hygiene (no external packages, no controller-path code)
**Confidence:** HIGH (all claims verified against the live repo at HEAD `b65ac8d9` and git anchor `v1.50`)

## User Constraints

No CONTEXT.md exists for this phase (orchestrated run; operator pre-approved scope at roadmap approval). Binding constraints come from REQUIREMENTS.md, ROADMAP.md, and project CLAUDE.md:

- **Locked:** Milestone surface is scripts/docs/planning/tests ONLY — zero `src/wanctl/` controller-path mutation (SAFE-15). Controller path = `wan_controller.py`, `queue_controller.py`, `cake_signal.py`, `backends/`, `alert_engine.py`, fusion.
- **Locked:** NO live rollback exercise and no production mutation anywhere in this phase (REQUIREMENTS.md Out of Scope: "Live rollback exercise").
- **Locked:** The future-doc denylist is binding: native controller, native deploy path, native tests, native config validation, rollback commands/docs must not be removed (ROLE-01 event gate not met).
- **Locked:** FIX-02 closes the digest todo by *validating* against the v1.44 Phase 208 T12/TOOL-03 tolerance; reimplementation only if validation shows the criterion unmet.
- **Claude's Discretion:** Guard script naming, manifest format, evidence JSON layout, which closed-todo directory convention to use, whether to also fix the two WARNINGs (WR-01, WR-02) from the same Phase 231 review.
- **Deferred (do NOT plan):** SWEEP-01..03 (Phase 233), META-01..03 (Phase 234), SEED-006/007, ROLE-01, TAIL-01, any new `$wan` abstraction.

## Summary

This phase has three independent work surfaces plus a cross-phase boundary proof, all on the scripts/tests/planning surface:

1. **BOUND-01 guard.** The repo already has two mature precedents for machine-checkable git-anchored boundary checks: `scripts/check-safe07-source-diff.sh` (allowlist-bounded diff vs a pinned anchor, exit 0/1/2 contract) and `scripts/phase225-safe13-boundary-check.sh` (per-file hash check vs `--anchor` ref with JSON evidence via `--out`, fails closed on deleted *or added* files). The new guard should follow the phase225 shape: enumerate the future-doc denylist as concrete paths verified at the `v1.50` anchor, fail non-zero on any removal or modification, emit JSON evidence, and carry an explicit, machine-readable allowlist for the two files FIX-01 legitimately modifies in this same phase (`scripts/phase231-rollback.sh`, `tests/test_phase231_rollback.py`) — mirroring the documented-allowlist precedent in check-safe07. Wiring: a pytest file in the default suite invokes the guard so any sweep commit that violates the denylist turns the suite red, plus on-demand operator invocation.

2. **FIX-01 confirm-path fix.** The v1.50 Phase 231 review CR-01 (231-REVIEW.md:37-57) is precise: `run_confirm()` pipes a generated remote script into `ssh ... "bash -s"` *without* `set -euo pipefail`, so a failed intermediate rollback command (disable cake-autorate, enable wanctl@, bpctl bypass step, first `tc qdisc replace`) is masked if the last command succeeds — partial-rollback/dual-writer risk. The review supplies the exact fix: prepend `set -euo pipefail` to the generated remote script and add a post-rollback verification that `cake-autorate-${WAN}.service` is NOT active. The existing test harness (`tests/test_phase231_rollback.py`) already has an SSH-shim pattern (PATH-injected fake `ssh` logging to `ssh.log`) that can prove the fix without any live rollback. The same review's WR-02 (preflight test does not assert the remote command set is read-only) directly strengthens the no-live-mutation proof and is cheap; WR-01 (SC2318 dynamic-scoping in `phase231-migration-held.sh:136`) is a two-line same-review cleanup on the same tooling surface.

3. **FIX-02 digest validation.** The 2026-04-17 todo (`.planning/todos/pending/2026-04-17-operator-summary-digest-permission-handling.md`, already tagged `resolves_phase: 232`) was functionally superseded by v1.44 Phase 208 plan 208-03 (T12/TOOL-03): `print_digest()` in `src/wanctl/operator_summary.py` (verified at HEAD, lines 190-250+) already catches `(sqlite3.OperationalError, OSError)` at the DB-open boundary, emits the stable `_DIGEST_SKIP_PREFIX` skip line per unreadable DB, continues to the next DB, and exits 0 with a "no readable WAN DBs" hint when nothing is readable. `tests/test_operator_digest.py` pins all of this (9 tests, all passing at HEAD: skip-one-bad-DB, all-unreadable-exit-0, write-OSError, query-errors-bubble, discovery-OSError). FIX-02 is therefore an evidence-and-closure task: re-run the pinned tests, optionally capture a read-only live `--digest` run as an unprivileged user, record evidence, and move the todo to `closed/` with `closed_by_phase: 232` + `verdict` frontmatter (matching the existing closed-todo convention). No reimplementation is indicated by current evidence.

4. **SAFE-15 boundary proof.** `scripts/phase225-safe13-boundary-check.sh` already takes `--anchor` and `--out` and checks exactly the SAFE-15 controller-target list (`wan_controller.py`, `wan_controller_state.py`, `queue_controller.py`, `cake_signal.py`, `alert_engine.py`, `fusion_healer.py`, `backends/`). Reuse it with `--anchor v1.50` and a phase-232 evidence path — no new abstraction.

**Primary recommendation:** Three plans — (1) guard script + gating test, (2) CR-01 fix + WR-01/WR-02 + shim-based proof tests, (3) FIX-02 evidence/closure + SAFE-15 boundary run at phase end (wave 2, after all mutations).

## Project Constraints (from CLAUDE.md)

- Production network control system — change conservatively; stability > safety > clarity > elegance.
- Dev commands: `.venv/bin/pytest tests/ -v`, `.venv/bin/ruff check src/ tests/`, `.venv/bin/mypy src/wanctl/`, `.venv/bin/ruff format src/ tests/`.
- Hot-path regression slice: `.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q`.
- Do not reintroduce timer-era guidance; active deployment is service-based.
- Health/observability payload shapes are contractual.
- Project memory: `.planning/` is gitignored but tracked — commit planning files with `git add -f`; if the interactive pre-commit doc hook blocks, use `SKIP_DOC_CHECK=1`.
- RouterOS mutations need approval; both WANs run cake-autorate (wanctl@ disabled since 2026-06-08) — repo vs prod state must not be assumed.

## The Denylist Manifest (verified against `git ls-tree -r v1.50`)

All paths below exist at the `v1.50` tag and at HEAD `b65ac8d9` [VERIFIED-LOCAL]:

| Denylist class (future doc §"Not safe to remove") | Concrete paths |
|---|---|
| Native controller | `src/wanctl/autorate_continuous.py` |
| Native `wanctl@$wan.service` deploy path | `deploy/systemd/wanctl@.service`, `scripts/install.sh`, `scripts/install-systemd.sh`, `scripts/deploy.sh` |
| Native controller tests | `tests/test_autorate_continuous.py`, `tests/test_autorate_config.py`, `tests/test_autorate_baseline_bounds.py`, `tests/test_autorate_entry_points.py`, `tests/test_autorate_error_recovery.py`, `tests/test_autorate_metrics_recording.py`, `tests/test_autorate_telemetry.py` |
| Native config validation | `src/wanctl/autorate_config.py`, `src/wanctl/config_base.py`, `src/wanctl/config_validation_utils.py`, `src/wanctl/check_config.py`, `src/wanctl/check_config_validators.py`, `tests/test_check_config.py`, `tests/test_config_base.py`, `tests/test_config_validation_utils.py` |
| Rollback commands/docs | `scripts/phase231-rollback.sh`, `scripts/phase227-rollback.sh`, `tests/test_phase231_rollback.py`, `docs/UPGRADING.md`, `docs/DEPLOYMENT.md`, `.planning/cake-autorate-trials/WANCTL_CAKE_AUTORATE_FUTURE.md` |

Notes:
- The future doc itself is the canonical denylist source and lives under gitignored-but-tracked `.planning/` — guard must use `git ls-files`-aware existence checks, not just worktree stat, OR plain `test -f` (file is present in worktree). Plain existence + hash-vs-anchor both work since the file is tracked. [VERIFIED-LOCAL: `git ls-tree v1.50` does NOT list `.planning/` paths — the trials doc is tracked at HEAD but the v1.50 tag tree must be checked at plan time; if absent at the anchor, existence-only check applies to it.]
- **Phase-232 allowlist (modified-this-phase, must still exist):** `scripts/phase231-rollback.sh`, `tests/test_phase231_rollback.py` (FIX-01), `scripts/phase231-migration-held.sh` + `tests/test_phase231_migration_held.py` if WR-01 is fixed. The guard must allow *modification* of these vs the v1.50 anchor while still failing on *removal*.

## Architecture Patterns

### Pattern 1: Git-anchored per-file boundary check with JSON evidence (REUSE)
**What:** `scripts/phase225-safe13-boundary-check.sh` — bash arg parse (`--anchor`, `--out`), embedded `python3 - <<'PY'` heredoc comparing `git rev-parse`/per-file blob hashes between anchor and HEAD/worktree, JSON evidence written to `--out`, exit non-zero on any drift, deleted *and added* files fail closed.
**When to use:** Both the new BOUND-01 guard (same shape, denylist targets, allowlist support) and the SAFE-15 boundary proof (reuse the phase225 script directly — its `controller_targets` list IS the SAFE-15 list).

### Pattern 2: Allowlist-bounded source diff (REUSE concept)
**What:** `scripts/check-safe07-source-diff.sh` — diff vs pinned anchor must be empty OR bounded to a documented allowlist; header comments document why each allowlisted file is allowed.
**When to use:** The BOUND-01 guard's handling of FIX-01-modified files: removal always fails; modification allowed only for the documented phase-232 allowlist.

### Pattern 3: PATH-injected SSH shim for mutation-script tests (REUSE)
**What:** `tests/test_phase231_rollback.py::run_script` writes a fake `ssh` into `tmp_path/bin`, prepends to PATH, logs every invocation to `ssh.log`, returns canned `systemctl` outputs. Tests assert (a) behavior and (b) that no SSH calls happened in read-only modes.
**When to use:** Proving the CR-01 fix without live rollback: assert the generated remote payload begins with `set -euo pipefail`, assert the post-rollback external-writer verification command appears in `ssh.log`, and assert confirm-path failure propagation — all against the shim.

### Pattern 4: Closed-todo frontmatter convention (FOLLOW)
**What:** `.planning/todos/closed/2026-04-08-*.md` carries `resolves_phase`, `closed_by_phase: <N>`, `verdict: <slug>` frontmatter on the original body, file moved from `pending/` to `closed/`.
**When to use:** FIX-02 closure: add `closed_by_phase: 232`, `verdict: validated_already_implemented_v144_phase208` (or similar), append a Resolution section with evidence pointers, `git mv` to `closed/`.

### Anti-Patterns to Avoid
- **New `$wan` abstraction or generalized "guard framework"** — explicitly out of scope (REQUIREMENTS.md); one phase-specific guard script following existing precedent.
- **Unfiltered `grep -c` gates** — header prose self-invalidates the gate; use `grep -v '^#' | grep -c` (planner rule, also bitten before in this repo).
- **chmod-based permission tests** — Phase 208 D-15 pinned monkeypatch-based failure injection (root runs chmod tests green; CI breaks). Keep that convention for any new digest evidence test.
- **Anchoring the guard to a floating ref (HEAD~N)** — anchor must be the immutable `v1.50` tag, with `--anchor` override for future milestones.
- **Wiring the guard only into docs** — "wired so sweep work cannot proceed" needs an executable gate: a pytest in the default suite + the script's non-zero exit as a pre-commit/manual gate for Phase 233.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| SAFE-15 controller zero-diff proof | New checker | `scripts/phase225-safe13-boundary-check.sh --anchor v1.50 --out <evidence>` | Target list already matches SAFE-15; takes anchor/out args; JSON evidence format already accepted in prior audits |
| Remote-command capture in tests | Mock SSH library | Existing PATH shim in `tests/test_phase231_rollback.py` | Proven pattern, zero deps |
| JSON evidence emission from bash | jq string assembly | `python3 - <<'PY'` heredoc (repo-wide convention) | Used by phase225/phase231 scripts; safe quoting |

## Common Pitfalls

### Pitfall 1: Guard self-conflict with FIX-01
**What goes wrong:** A naive "zero diff vs v1.50 on all denylisted paths" guard fails the moment FIX-01 lands, because `scripts/phase231-rollback.sh` and its test ARE denylisted rollback surfaces and ARE modified this phase.
**How to avoid:** Explicit modification-allowlist (Pattern 2) inside the guard, documented with the CR-01 rationale. Removal of allowlisted files still fails.

### Pitfall 2: `ssh -n` + stdin heredoc interplay in run_confirm
**What goes wrong:** `run_confirm` uses `ssh -n ... "bash -s" <"$remote_script"`. `-n` redirects stdin from /dev/null and can starve `bash -s` of the script on some OpenSSH configurations. The Phase 231 review's fix snippet retains `-n`; preserve current transport behavior (it demonstrably worked for preflight) but do not "clean it up" beyond CR-01's scope — the shim tests assert payload content, not transport flags. If the fix drops `-n` for the `bash -s` line, that is a deliberate, test-pinned decision; either way the test must assert the `set -euo pipefail` preamble reaches the remote payload.
**Warning signs:** confirm-path shim test passes but logged payload is empty.

### Pitfall 3: Boundary check ordering
**What goes wrong:** Running the SAFE-15 boundary proof in wave 1 produces evidence that predates FIX-01/guard commits — "verified, not assumed" fails on audit.
**How to avoid:** SAFE-15 run is the LAST task of the LAST wave; evidence JSON committed with the phase close.

### Pitfall 4: Todo directory sprawl
**What goes wrong:** `.planning/todos/` has `pending/`, `closed/`, `completed/`, `done/` — picking a novel destination breaks META-01's Phase 234 reconciliation sweep.
**How to avoid:** Use `closed/` with `closed_by_phase`/`verdict` frontmatter (most recent convention, Phase 221 precedent).

### Pitfall 5: Live digest validation environment drift
**What goes wrong:** Treating a live unprivileged `--digest` run as REQUIRED blocks the phase if the host/group membership changed (live state ≠ repo assumptions; both WANs now run cake-autorate with bridge-owned DB writers).
**How to avoid:** Tests are the primary FIX-02 evidence (they pin the T12/TOOL-03 contract deterministically). Live read-only run is best-effort supplementary evidence with a recorded fallback note.

## Runtime State Inventory

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | `/var/lib/wanctl/metrics-{spectrum,att}.db` (0640 wanctl:wanctl on live host) | Read-only optional live digest check only; no mutation |
| Live service config | cake-autorate + state-bridge units live on both WANs; `wanctl@` disabled since 2026-06-08 | None — phase touches repo only |
| Git anchors | `v1.50` tag exists [VERIFIED-LOCAL] | Guard + SAFE-15 anchor |
| Planning state | todo already tagged `resolves_phase: 232` (commit `b65ac8d9`) | Move to `closed/` at FIX-02 completion |

## Validation Architecture

> workflow.nyquist_validation is enabled.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (repo venv, Python 3.11+) |
| Config file | `pyproject.toml` |
| Quick run command | `.venv/bin/pytest -o addopts='' tests/test_cleanup_boundary_guard.py tests/test_phase231_rollback.py tests/test_operator_digest.py -q` |
| Full suite command | `.venv/bin/pytest tests/ -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| BOUND-01 | Guard exits non-zero when a denylisted file is removed/modified; 0 when clean | integration (subprocess) | `.venv/bin/pytest -o addopts='' tests/test_cleanup_boundary_guard.py -q` | ❌ Wave 0 (new file, created in plan 01) |
| FIX-01 | Remote confirm payload starts with `set -euo pipefail`; post-rollback external-writer check present; preflight remains read-only | integration (SSH shim) | `.venv/bin/pytest -o addopts='' tests/test_phase231_rollback.py -q` | ✅ (extended in plan 02) |
| FIX-02 | Digest tolerates unreadable DBs per T12/TOOL-03 (skip+continue, exit-0 hint, query errors bubble) | unit/integration | `.venv/bin/pytest -o addopts='' tests/test_operator_digest.py -q` | ✅ (existing, re-run as evidence) |
| SAFE-15 | Controller-path zero diff vs v1.50 at phase boundary | script + evidence JSON | `bash scripts/phase225-safe13-boundary-check.sh --anchor v1.50 --out .planning/phases/232-cleanup-boundary-guard-tooling-fixes/evidence/safe15-boundary-232.json` | ✅ (script exists) |

### Sampling Rate
- **Per task commit:** `.venv/bin/pytest -o addopts='' tests/test_phase231_rollback.py tests/test_operator_digest.py -q` (+ `tests/test_cleanup_boundary_guard.py` once created)
- **Per wave merge:** hot-path slice `.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q`
- **Phase gate:** full suite green + SAFE-15 evidence JSON `overall pass` before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `tests/test_cleanup_boundary_guard.py` — covers BOUND-01 (created alongside the guard in plan 01; the guard script and its test land in the same plan, so no separate Wave 0 plan is needed)

## Security Domain

### Applicable ASVS Categories
| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no (SSH key auth pre-existing) | — |
| V4 Access Control | yes | `--confirm` + `--i-have-operator-approval` double gate preserved; guard refuses by exit code |
| V5 Input Validation | yes | bash `case` validation of `--wan`/flags (existing pattern); guard validates anchor ref via `git rev-parse --verify` |
| V6 Cryptography | no | — |

### Known Threat Patterns for bash ops tooling
| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Partial remote mutation masked by last-command status | Tampering/DoS | `set -euo pipefail` preamble in generated remote script + post-state verification (CR-01 fix) |
| Read-only mode silently gaining mutation verbs | Tampering | WR-02 negative assertions on shim command log (`systemctl (enable|disable|...)`, `tc qdisc (replace|add|del)` absent) |
| Guard bypass via untracked/renamed denylist file | Repudiation | Guard resolves manifest against git anchor AND worktree; unknown predicate/ref → exit 2 fail-closed |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `v1.50` tag tree is the correct guard/SAFE-15 anchor (vs a close SHA) | Manifest | Low — tag verified present; check-safe07 used SHAs, phase225 used tags; `--anchor` override exists |
| A2 | WR-01/WR-02 inclusion is acceptable scope under "Tooling Fixes" (same review, same surface) | Summary | Low — they are warnings from the SAME review FIX-01 cites; if operator objects, they are isolated tasks easily dropped |
| A3 | Live unprivileged digest run is optional evidence, not required for FIX-02 closure | Pitfall 5 | Low — requirement says "tests or recorded evidence"; tests exist and pass |

## Open Questions

1. **Should the guard also protect `configs/*.yaml` native-controller config examples?**
   - What we know: future doc names code/deploy/tests/validation/rollback surfaces, not configs.
   - Recommendation: No — keep the manifest exactly at the future-doc list; SWEEP-03 (Phase 233) handles config hardcoding separately. Guard is trivially extensible via its manifest.

## Sources

### Primary (HIGH confidence — read directly this session)
- `.planning/cake-autorate-trials/WANCTL_CAKE_AUTORATE_FUTURE.md` §"What not to delete yet" + §"Cleanup policy" (denylist source)
- `.planning/milestones/v1.50-phases/231-.../231-REVIEW.md` CR-01, WR-01, WR-02 (exact findings + prescribed fixes)
- `scripts/phase231-rollback.sh` (full read — current confirm path at lines 269-306)
- `tests/test_phase231_rollback.py` (full read — SSH shim harness)
- `.planning/milestones/v1.44-phases/208-carry-on-quick-tasks-t17a-t9-t12/208-03-PLAN.md` (T12/TOOL-03 contract: must_haves truths)
- `src/wanctl/operator_summary.py::print_digest` (HEAD implementation of the tolerance)
- `tests/test_operator_digest.py` (9 tests; verified passing at HEAD: `16 passed` with rollback tests)
- `scripts/check-safe07-source-diff.sh`, `scripts/phase225-safe13-boundary-check.sh` (guard precedents)
- `git ls-tree -r v1.50` (manifest existence verification)
- `.planning/REQUIREMENTS.md`, `.planning/ROADMAP.md` Phase 232 section, `CLAUDE.md`

## Metadata

**Confidence breakdown:**
- Denylist manifest: HIGH — every path verified at v1.50 and HEAD
- CR-01 fix shape: HIGH — review prescribes exact code
- FIX-02 already-implemented finding: HIGH — code read + tests executed green this session
- Guard wiring approach: MEDIUM-HIGH — pytest-gate pattern is repo-consistent; exact Phase 233 invocation discipline is that phase's planning concern

**Research date:** 2026-06-10
**Valid until:** v1.51 close (internal-repo research; invalidated only by repo changes)
