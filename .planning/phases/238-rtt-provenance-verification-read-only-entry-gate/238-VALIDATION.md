---
phase: 238
slug: rtt-provenance-verification-read-only-entry-gate
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-06-14
---

# Phase 238 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.
> **Read-only entry gate:** NO production source code is introduced. Validation is
> **artifact + behavioral + git-assertion**, not pytest-on-controller.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | pytest (repo standard) — NOT the validation surface for this phase |
| **Config file** | `pyproject.toml` (repo) |
| **Quick run command** | `scripts/phase238-safe17-boundary-check.sh` (controller-path git-diff assertion; exit 0 = clean) |
| **Full suite command** | `scripts/phase238-egress-proof.sh --json` (operator on live cake-shaper host, both WANs) + artifact review of `238-*/PROVENANCE-MAP.md` |
| **Estimated runtime** | ~5–15 seconds (scripts); artifact review manual |

---

## Sampling Rate

- **After every task commit:** Run `scripts/phase238-safe17-boundary-check.sh` — controller-path git diff vs `v1.52` anchor MUST stay empty.
- **After every plan wave:** Re-run the SAFE-17 assertion; for the egress/provenance waves, confirm the proof script exits 0 for both WANs and the map embeds all D-06 evidence.
- **Before phase verification:** SAFE-17 assertion passes; egress-proof exits 0 for both WANs; `git status` shows only phase-dir artifacts + the two new read-only `scripts/phase238-*.sh` changed.
- **Max feedback latency:** ~15 seconds (script runs).

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Threat Ref | Secure Behavior | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|------------|-----------------|-----------|-------------------|-------------|--------|
| 238-01-* | 01 | 1 | SAFE-17 | T-238-01 (accidental prod mutation) | Controller-path byte-unchanged vs `v1.52`; script is read-only (`set -euo pipefail`, no writes) | automated git assertion | `scripts/phase238-safe17-boundary-check.sh` | ❌ W0 | ⬜ pending |
| 238-02-* | 02 | 1 | PROV-03 | T-238-02 (shell injection via arg) | Read-only `ip route get` / `ip rule` / `curl`; `--wan` arg validated against fixed allowlist | smoke (script self-test) | `scripts/phase238-egress-proof.sh --json` | ❌ W0 | ⬜ pending |
| 238-03-* | 03 | 2 | PROV-01, PROV-02 | T-238-03 (infra detail leakage) | Internal IPs stay in phase-dir evidence; not promoted to public CLAUDE.md/README | artifact review (manual) | inspect `238-*/PROVENANCE-MAP.md` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `scripts/phase238-safe17-boundary-check.sh` — covers SAFE-17 (lightweight clone of `scripts/phase237-safe16-boundary-check.sh`; controller-path target list, anchor `v1.52`)
- [ ] `scripts/phase238-egress-proof.sh` — covers PROV-03 (model on `scripts/phase231-migration-held.sh`; `validate_wan` arg pattern; both WANs)
- [ ] `238-*/PROVENANCE-MAP.md` — covers PROV-01 / PROV-02 (no test framework; artifact-review gate)
- Framework install: none (no production code under test).

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Provenance map embeds verified code-path trace + live `/health` capture | PROV-01 | Evidence artifact authored in-phase; live capture requires operator on cake-shaper host | Inspect `238-*/PROVENANCE-MAP.md`: confirm code-path trace with file:line, embedded live `/health` `measurement` block, deployed-bridge identity (sha vs repo). |
| A/B recommendation with evidence + operator ratification | PROV-02 | Per D-01, operator makes the binding A/B selection at execution/verification | Inspect map A/B section: both interpretations present honestly, fidelity-rubric (D-03) recommendation stated, operator selection recorded. |
| Egress proof on live host, both WANs | PROV-03 | Requires SSH to live cake-shaper host; not reproducible in CI | Operator runs `scripts/phase238-egress-proof.sh --json` on host; stdout captured into the map; confirm each WAN's `ip route get <reflector> from <source_ip>` egresses the intended interface. |

---

## Security Domain

> `security_enforcement` default-enabled. Phase 238 is read-only with no new attack surface;
> controls below are about **not mutating prod** and not leaking infra details.

| Pattern | STRIDE | Mitigation |
|---------|--------|-----------|
| Accidental prod mutation via "read-only" script | Tampering | `set -euo pipefail`; only `ip route get` / `ip rule` / `curl` / git-read; read-only posture banner; no sudo-write, no unit control. |
| Shell injection via WAN/arg | Tampering | Validate args against fixed allowlist (phase231/237 pattern); quote all expansions. |
| Infra detail leakage | Info Disclosure | Internal IPs stay in phase-dir evidence; never written to public-safe CLAUDE.md/README. |

---

## Validation Sign-Off

- [ ] All tasks have automated assertion/script verify or Wave 0 dependencies
- [ ] Sampling continuity: SAFE-17 assertion runs after every task commit
- [ ] Wave 0 covers all MISSING references (2 scripts + 1 artifact)
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
