# Milestone Audit — v1.61 QoS Classification Contract

**Audit date:** 2026-07-18
**Auditor:** independent frontier close-out (different model from the executor)
**Method:** full-tree evidence sweep (/saga-verify) + milestone audit (/saga-audit --milestone v1.61)
**Access constraint:** auditor had NO live production access. Repo-side and test-side evidence was independently re-executed. Live-production evidence was verified by artifact inspection only (per SAFE-24 the auditor must not touch production).

---

## Verdict

**CONDITIONAL**

Requirements are met and evidenced (6/6 PROVEN, 0 ASSERTED, 0 OPEN; SAFE-24 gate PROVEN). No unevidenced `[x]`, no broken claim, and every mechanical/repo claim the auditor could re-run passed. The verdict is CONDITIONAL rather than clean PASS because of finalization and evidentiary-asymmetry conditions listed below — none of which contradict a requirement.

### REQ counts (REQ-001..006)

| Status | Count |
|--------|-------|
| PROVEN | 6 |
| ASSERTED | 0 |
| OPEN | 0 |

SAFE-24 production-mutation gate: **PROVEN**.

---

## What the auditor independently reproduced (green)

| Check | Result |
|-------|--------|
| `tests/test_bridge_qos_nft.py` (full nft contract suite, incl. new retirement guard) | **6 passed** |
| REQ-002 propagation test + full steering/bridge suite | **283 passed** |
| infra-ansible REQ-005 audit suite (`test_routeros_qos_contract_audit` + `test_routeros_qos_composite_policy`) | **24 passed** |
| AF31 upload import present in repo `bridge-qos.nft` `spectrum_ul` (L46) + `att_ul` (L52) | confirmed |
| `spectrum_dl`/`att_dl` retirement matches claim (16384-32767, TCP/22, 3478-3480→3478-3479, NNTP/119, WG/51820 gone) | confirmed via diff + grep |
| All 9 REQ-003 live-evidence artifacts exist under `../infra-ansible/.../20260717_routeros-qos-composite-policy/` | confirmed |

`nft -c -f deploy/nftables/bridge-qos.nft` was inconclusive locally (netlink cache init requires privilege on this non-router host, not a syntax error); the parse itself did not report a syntax error and the structural test suite covers ruleset shape.

## What the auditor verified by artifact inspection (not re-executable)

- Live RouterOS contract-audit PASS captures, `wanctl 25/25` preflights, live nft hashes, and natural CAKE counter deltas — all live-only, read from the executor's evidence files.
- **Hash lineage is continuous and gap-free across the four live canaries:**
  `649bd585` (Spectrum baseline) → `12300940` (Spectrum retired / ATT baseline) → `e1063434` (ATT retired / AF31 baseline) → `a6b85d55` (AF31 converged, final live).
  Each canary's authorized baseline exactly equals the prior canary's target. This rules out silent out-of-band mutation between steps and is the strongest integrity signal in the milestone.
- **Correct causal order for REQ-003:** per-selector equivalence was audit-proven (contract audit overall PASS, coverage #15/#35/#36/#37/#38 before default #39) BEFORE any bridge duplicate was retired. The requirement's "removed only after equivalence proven" clause is satisfied in sequence, not just in outcome.
- **Fail-closed behavior demonstrated live, not just claimed:** slice 23 aborted before mutation when the approval anchor had drifted; AF31 v1 rolled back cleanly on a postcheck disagreement (unrelated Spectrum Bulk saturation vs an over-strict zero-drop acceptance). v2 added a load-aware precondition and succeeded. The safety contract was exercised under real disagreement and held.

---

## Conditions attached to this CONDITIONAL verdict

1. **Working tree is uncommitted.** `bridge-qos.nft`, `test_bridge_qos_nft.py`, `QOS_CLASSIFICATION_CONTRACT.md`, and the four `.planning` spine files are modified-not-committed. The milestone is functionally drained but not durably recorded. Close-out is not complete until these are committed and the phase dirs are archived into `milestones/v1.61-phases/` (recurring archival gap noted in project memory — archive before any new-milestone `phases.clear`).

2. **Natural-traffic confirmation deferred for 2 of 5 selectors.** Generic RTP, WireGuard, and SSH have observed natural-hit counter proof. UDP/3480 and NNTP immediate counters are `0/0`; natural confirmation is deferred (no synthetic probes, by design). This does NOT block REQ-003 — equivalence for those selectors is proven structurally (exact enabled terminal rule before the true catch-all) and by contract-audit PASS — but the practical hit-confirmation is weaker than the other three selectors. Recommend a follow-up read-only counter check once natural traffic occurs.

3. **Live evidence is auditor-document-verified, not auditor-re-executed.** By SAFE-24 scope the auditor cannot touch production, so the live hashes/audits/counters rest on the executor's artifacts. Confidence is high (continuous hash lineage, internal consistency, independent Claude reviews recorded per slice, all reproducible repo-side claims green) but this is a structural limit of an out-of-band close-out, stated plainly.

---

## Defects found and their disposition

- **Stale TRACEABILITY summary (FIXED in this pass).** The prior `TRACEABILITY.md` v1.61 table marked REQ-003 PROVEN while its own summary line still read "REQ-003 OPEN" — an internal contradiction left by the executor. The freshly written `TRACEABILITY.md` corrects the summary to match the table and adds explicit counts + an auditor-scope note.
- No requirement-level defects. No unevidenced `[x]`. No claim contradicted by a reproduced check.

---

## Product-code note

Per instructions, no product code was implemented or repaired. The auditor read `deploy/nftables/bridge-qos.nft` and the test/doc changes to verify claims only. The single functional change under audit (download-chain classifier retirement + symmetric AF31 upload import) is consistent with REQ-002/REQ-003 and passes its own test suite.

---

## Recommendation

Proceed to finalization: run the project-finalizer/commit gate, commit the drained v1.61 work (note the `.planning` gitignore quirk — `git add -f` + `SKIP_DOC_CHECK=1` per project memory), archive `v1.61-phases`, then schedule the deferred UDP/3480 + NNTP natural-counter read-only follow-up. No requirement rework is needed.
