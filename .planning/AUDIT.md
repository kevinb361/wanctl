# Milestone Audit — v1.62 QoS Validation & Trust Hardening

**Audit date:** 2026-07-20
**Auditor:** independent frontier close-out (different model/context from the executor)
**Method:** full-tree evidence sweep against `.planning/evidence` + referenced read-only artifacts in `../infra-ansible`; repo-side checks independently re-executed (parallel where pytest); saga-verify classification applied.
**Access constraint:** auditor had **NO** live production access — no SSH, no network services, no Ansible against hosts, no traffic generation, no mutation outside this repo. Live-production evidence was verified by **artifact inspection only**; all live claims below are document-verified, not auditor-re-executed.

---

## Verdict

**CONDITIONAL PASS**

All seven in-scope requirements are met and concretely evidenced: **QVT-001..006 = 6 PROVEN / 0 ASSERTED / 0 OPEN; SAFE-25 gate = PROVEN.** No unevidenced `[x]`, no claim contradicted by a reproduced check, and every mechanical/repo claim the auditor could re-run passed. Failed and blocked attempts are preserved as failures and were not reinterpreted. The verdict is CONDITIONAL rather than clean PASS solely because of the finalization and evidentiary-asymmetry conditions listed below — none of which contradicts a requirement.

### Counts (QVT-001..006)

| Status | Count |
|--------|-------|
| PROVEN | 6 |
| ASSERTED | 0 |
| OPEN | 0 |

SAFE-25 bounded-production/hardening gate: **PROVEN.**

---

## What the auditor independently reproduced (green)

| Check | Result |
|-------|--------|
| `saga-lint .` (bundled validator, read-only) | exit **0** — clean structure |
| wanctl `tests/test_bridge_qos_nft.py` + `test_qos_spectrum_packet_proof.py` + `test_qos_iot_wash_proof.py` (`-n auto`) | **17 passed** |
| infra-ansible `test_routeros_dscp_trust_attribution` + `test_routeros_ephemeral_torch_identity` + `test_routeros_qos_contract_audit` + `test_routeros_qos_composite_policy` (`-n auto`) | **37 passed** |
| All referenced evidence directories exist and are populated (`qvt002-spectrum-…`, `qvt003-iot-wash-…`, `qvt005-bridge-drift-…`, `live-preflight/*.json`, infra `network-{audits,changes,readonly}/…`) | confirmed |
| QVT-002 `class-analysis.json` — machine record matches prose | EF `[46]`/AF31 `[26]`/CS1 `[8]`/CS0 `[0]`, 5 each, `overall_pass=true` |
| QVT-003 failed one-packet `wash-analysis.json` — failure genuinely preserved | `overall_pass=false`, `source_ef_proven=true`, `wash_packet_delta=0`, `trust_excludes_iot=true` |
| QVT-005 `parity-report.json` — executable/loaded parity | executable lines 55/55 equal; repo+live `nft --check` PASS; loaded 5 chains / 41 semantic rules == repo; `raw_equal=false` |
| QVT-004 operator LOW-risk acceptance is durably recorded (not just asserted in planning prose) | `docs/QOS_CLASSIFICATION_CONTRACT.md` §"RouterOS client-marker risk acceptance (v1.62)", dated 2026-07-20 |

## What the auditor verified by artifact inspection only (not re-executable — live-evidence boundary)

- Strict RouterOS contract-audit PASS captures, `wanctl 25/25` live preflights, live mangle/nft hashes, source packet captures, and natural CAKE/counter deltas are **live-only** and were read from the executor's retained artifacts. Per SAFE-25 the auditor must not touch production, so these are trusted on the artifact, not independently re-run.
- **Mangle-hash lineage is continuous and gap-free across the v1.62 live mutations:**
  `4ad83ba7…921e` (v1.62 baseline = final v1.61 NNTP canary target) → `43f7b575…ae7c3` (QVT-003 additive source-wash canary applied) → held stable through the QVT-003 natural-canary proof → `634d177a…e6e5` (QVT-004 v5 controller-owned Work-VPN adaptive toggle).
  Each authorized baseline exactly equals the prior action's resulting hash. This is the strongest integrity signal available to an out-of-band auditor: it mechanically rules out silent out-of-band mutation between approved steps and links v1.62 continuously to the audited v1.61 lineage.
- **Correct causal order and honest failure handling:** the QVT-003 zero-hit explanation rests on a *failed* live packet (source EF proven, legacy wash `0/0`), a bridge/trunk root-cause diagnosis (unreachable `in-interface=vlan120-IOT` selector at prerouting), and a working source-subnet canary observed moving under natural traffic — satisfying the requirement's read-only-explanation branch without weakening the `+1` acceptance to "at least one."
- **Failed/blocked attempts preserved, not reinterpreted:** QVT-002 first attempt (multiline-parser/established-flow contamination), QVT-003 legacy packet (mismatch), and the QVT-004 ephemeral identity chain v1→v5 (vault-flag omission → API/SSH hash mismatch → Torch permission failure → parser/scope disagreement → source-only persistence with policy-hash disagreement) each retain their own evidence file and appear in the SAFE-25 ledger as failures with no-retry and non-replayable token rotation.

---

## Requirement-by-requirement disposition

| Req | Status | Basis (artifact-anchored) |
|-----|--------|---------------------------|
| QVT-001 | PROVEN | Baseline strict audit exit `0`/PASS, live preflight `25/25`, four-class map exact, drift characterized as comment-only (later mechanically confirmed by QVT-005 parity). |
| QVT-002 | PROVEN | Separately approved repaired second attempt; `class-analysis.json` machine-confirms all four classes 5/5; CAKE `8004:`/`diffserv4` healthy before/after; strict audits PASS and `25/25` immediate + postflight; first failed attempt retained as negative evidence. |
| QVT-003 | PROVEN (read-only-explanation branch) | Failed legacy packet + unreachable-selector root cause + additive source-subnet canary moving `1429/377172 → 1458/385374` under natural traffic while legacy stayed `0/0`. Packet re-proof declined rather than weakened. **Residual: the approved source-wash canary remains a live active mangle rule (see Condition 3).** |
| QVT-004 | PROVEN (evidence-backed risk-acceptance branch) | Explicit operator LOW-risk acceptance recorded 2026-07-20 in the living contract; bounded ephemeral attribution found legitimate EF sources, AF4x inconclusive; no trust-rule mutation. v5 policy-hash disagreement preserved, not hidden (see Condition 4). |
| QVT-005 | PROVEN | `parity-report.json`: executable 55/55 and loaded 5-chain/41-rule semantics equal repo; both `nft --check` PASS; comment-only drift formally retained; no reload. |
| QVT-006 | PROVEN | Fresh 66-row scan: `*308` sole consumer, zero producers, `0/0`, no script/scheduler ref; 2026-07-03 disable-not-remove intent reproduced; keep-disabled disposition, no deletion. |
| SAFE-25 | PROVEN | Complete action ledger: fresh baselines, action-specific approvals, deterministic outcomes, retained failures, non-replayable tokens, exact mangle/identity cleanup, declined unjustified nft/rule actions; no CAKE/rate/controller/routing/NAT/firewall/VLAN/topology/saturation change. Fresh close-out strict audit PASS + `25/25`. |

---

## Conditions attached to this CONDITIONAL verdict

1. **Repository finalization was pending at audit time (RESOLVED during close-out).** The v1.62 spine/docs and six new QoS proof tooling files were uncommitted when the independent verdict was written. The normal project finalizer equivalent, complete CI, staged diff/doc/security review, and milestone commit subsequently completed. No v1.62 phase directories exist: this milestone used Saga bounded slices in `STATE.md`; the sole existing `.planning/phases/223-*` directory predates v1.62 and is intentionally untouched.

2. **Live evidence is auditor-document-verified, not auditor-re-executed.** By SAFE-25 scope the auditor cannot touch production, so every live hash/audit/preflight/counter rests on the executor's artifacts. Confidence is high — continuous gap-free mangle-hash lineage, machine artifacts internally consistent with prose, repo-side checks all green — but this is a structural limit of an out-of-band close-out, stated plainly.

3. **Residual approved live state carried out of v1.62.** The QVT-003 additive source-subnet IoT DSCP-wash canary (`src-address=10.10.120.0/24`, `change-dscp 0`) remains **active** in production mangle at hash `43f7b575…ae7c3` (as of the QVT-003 natural-canary proof; note QVT-004 v5 subsequently advanced the hash to `634d177a…e6e5` via an unrelated controller-owned toggle). The unreachable legacy `in-interface=vlan120-IOT` rule is intentionally retained. Both are approved and documented — not defects — but the milestone leaves a live additive rule in place; legacy-rule promotion/deletion remains a separate mutation gate.

4. **QVT-004 v5 policy-hash acceptance disagreement (evidentiary asymmetry).** During the approved v5 ephemeral observation the mangle hash changed `43f7b575…ae7c3 → 634d177a…e6e5`; the executor's normalized diff attributes the sole change to the controller-owned Work-VPN adaptive selector toggling disabled→enabled, with trust and all other rows unchanged and strict/health checks green. This is honestly preserved as a *packet-acceptance disagreement* and explicitly excluded from any PASS claim — the correct handling. An out-of-band auditor cannot causally disambiguate a controller-owned toggle from a diagnostic side-effect on artifacts alone; the disposition rests on the executor's normalization and the unchanged-trust evidence, which are internally consistent.

---

## Defects found and their disposition

- **Stale v1.62 TRACEABILITY header (FIXED in this pass).** The prior `TRACEABILITY.md` v1.62 section header still read `**Date:** 2026-07-19` / `**Verifier:** local read-only baseline slice` (written at the baseline slice) even though the table had been updated through 2026-07-20 close-out. Corrected to reflect the independent frontier close-out audit and add reproduced-checks + auditor-scope notes. Requirement rows were already accurate and were left substantively unchanged.
- **No requirement-level defects.** No unevidenced `[x]`, no ASSERTED, no OPEN, no claim contradicted by a reproduced check.

---

## Product-code note

Per instructions, no product code, requirement, roadmap, state, or evidence was changed. The auditor read source/tests/docs and ran read-only checks to verify claims only. This audit wrote exactly two artifacts: this `AUDIT.md` (freshly replacing the prior v1.61 audit) and the v1.62 section of `TRACEABILITY.md`.

---

## Recommendation

Repository finalization is complete. There is **no requirement rework and no ASSERTED/OPEN blocker.** `ROADMAP.md` is shipped and no v1.62 phase directory exists to archive. Track as living items (not blockers): the still-active QVT-003 source-wash canary and the deferred AF4x source-attribution follow-up, both reopenable per their documented triggers.
