---
phase: 244-health-payload-attribution-metadata
plan: 04
type: execute
wave: 1
depends_on: ["244-01"]
files_modified:
  - deploy/scripts/cake-autorate-spectrum-state-bridge
  - deploy/scripts/cake-autorate-att-state-bridge
autonomous: true
requirements: [HEALTH-01, SAFE-17]
user_setup: []

must_haves:
  truths:
    - "Both state-bridge /health measurement blocks (healthy AND degraded paths) additively emit producer='cake-autorate-bridge', backend=null, source_ip=null."
    - "Existing bridge measurement keys (available, raw_rtt_ms, staleness_sec) are byte-preserved."
    - "The two bridge scripts remain byte-identical in their health_payload region (Pitfall 4)."
    - "No bridge env wiring is added to fake a source IP (R1: null is the only honest value)."
  artifacts:
    - path: "deploy/scripts/cake-autorate-spectrum-state-bridge"
      provides: "health_payload() emits the D-02 honest triple on both paths"
      contains: "cake-autorate-bridge"
    - path: "deploy/scripts/cake-autorate-att-state-bridge"
      provides: "identical D-02 honest triple (lockstep with spectrum)"
      contains: "cake-autorate-bridge"
  key_links:
    - from: "deploy/scripts/cake-autorate-spectrum-state-bridge"
      to: "deploy/scripts/cake-autorate-att-state-bridge"
      via: "byte-identical health_payload region (kept in lockstep)"
      pattern: "producer.*cake-autorate-bridge"
---

<objective>
Surface the attribution triple on the LIVE production `/health` endpoint (D-01 surface 3): the
cake-autorate state bridges. Both WANs run on cake-autorate today, so these two deploy scripts
are the real production `/health`. Per D-02 honesty: the bridge parses RTT from upstream bash
cake-autorate's EWMA log and NEVER ran the wanctl seam (238 D-04), and its env carries no
`ping_source_ip` (R1 verified) — so it MUST emit `producer="cake-autorate-bridge"`,
`backend=null`, `source_ip=null`. This guarantees `backend` never lies and a Phase 245 A/B
scraper structurally cannot mix bridge EWMA RTT into the icmplib-vs-fping comparison.

Purpose: HEALTH-01 requires the triple uniform across all three producers; the bridge is the live
endpoint. The null values are honest, not a per-deployment Python branch (satisfies the Portable
Controller Architecture constraint).

Output: identical additive edits to `deploy/scripts/cake-autorate-spectrum-state-bridge` and
`deploy/scripts/cake-autorate-att-state-bridge`, validated by both Wave 0 artifact tests.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/244-health-payload-attribution-metadata/244-CONTEXT.md
@.planning/phases/244-health-payload-attribution-metadata/244-PATTERNS.md
@.planning/phases/244-health-payload-attribution-metadata/244-RESEARCH.md

<interfaces>
<!-- Verified facts the executor needs — no codebase exploration required. -->

cake-autorate-spectrum-state-bridge :: health_payload() (verified, ~234-296):
- Healthy-path measurement block (~267-271):
    "measurement": {
        "available": available,                                              # BYTE-PRESERVED
        "raw_rtt_ms": float(raw_rtt) if isinstance(raw_rtt, (int, float)) else None,  # PRESERVED
        "staleness_sec": age,                                                # BYTE-PRESERVED
    }
  ADD (D-02 honesty): "producer": "cake-autorate-bridge", "backend": None, "source_ip": None
- Degraded-path measurement block (~243):
    "measurement": {"available": False, "raw_rtt_ms": None, "staleness_sec": None}
  ADD the IDENTICAL triple so the shape is uniform across BOTH code paths.
- Top level already labels `source: "cake-autorate-state-bridge"` (~239/263) — LEAVE IT.

cake-autorate-att-state-bridge: the health_payload region is BYTE-IDENTICAL to spectrum
(verified via diff). Apply the identical edit; keep them in lockstep (Pitfall 4 — tests cover
both via test_spectrum/att_cake_autorate_artifacts.py).

R1 (verified, RESEARCH): bridge env reads only WANCTL_EXTERNAL_WAN_NAME / DL_IF / UL_IF /
log/state/metrics paths / baseline RTT / UID/GID / poll/health host:port / max-state-age. NO
ping_source_ip, NO source-IP env of any kind. Do NOT add bridge env wiring to learn/fake a
source IP — out of 244's additive scope and explicitly deferred. `null` is the only honest value.

These are deploy scripts, not src/wanctl — they are OUTSIDE the SAFE-17 controller-path
allowlist scope entirely (the verifier only diffs src/wanctl/). No allowlist change needed for
them. The bridge artifact tests are the gate.
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Add the D-02 honest triple to both bridge scripts' healthy and degraded measurement blocks</name>
  <files>deploy/scripts/cake-autorate-spectrum-state-bridge, deploy/scripts/cake-autorate-att-state-bridge</files>
  <read_first>
    - deploy/scripts/cake-autorate-spectrum-state-bridge (health_payload() ~234-296; healthy block ~267-271; degraded block ~243; top-level source label ~239/263; confirm env section ~16-31 carries NO ping_source_ip)
    - deploy/scripts/cake-autorate-att-state-bridge (confirm the health_payload region is byte-identical to spectrum before editing)
    - .planning/phases/244-health-payload-attribution-metadata/244-PATTERNS.md (§cake-autorate-*-state-bridge health_payload — both blocks)
    - .planning/phases/244-health-payload-attribution-metadata/244-RESEARCH.md (R1 — bridge source_ip resolved to null; Pitfall 4 — keep both in lockstep)
  </read_first>
  <action>
    In `deploy/scripts/cake-autorate-spectrum-state-bridge` `health_payload()`, add three keys to
    BOTH measurement blocks — the healthy-path block (~267-271) and the degraded-path block (~243):
    `"producer": "cake-autorate-bridge"`, `"backend": None`, `"source_ip": None`. Append them after
    the existing `staleness_sec` key; do NOT reorder or mutate `available`/`raw_rtt_ms`/
    `staleness_sec`. Leave the top-level `source: "cake-autorate-state-bridge"` label unchanged.
    Apply the IDENTICAL edit to `deploy/scripts/cake-autorate-att-state-bridge` so the two scripts
    stay byte-identical in the health_payload region (Pitfall 4). Do NOT add any new env var,
    `ip route` lookup, or source-IP derivation — `null` is the only honest value (R1).
  </action>
  <verify>
    <automated>diff <(sed -n '/def health_payload/,/^def /p' deploy/scripts/cake-autorate-spectrum-state-bridge) <(sed -n '/def health_payload/,/^def /p' deploy/scripts/cake-autorate-att-state-bridge) && grep -c 'cake-autorate-bridge' deploy/scripts/cake-autorate-spectrum-state-bridge | grep -qx 2 && grep -c 'cake-autorate-bridge' deploy/scripts/cake-autorate-att-state-bridge | grep -qx 2</automated>
  </verify>
  <acceptance_criteria>
    - Both scripts' healthy AND degraded measurement blocks contain
      `"producer": "cake-autorate-bridge"`, `"backend": None`, `"source_ip": None` after
      `staleness_sec` (grep counts `cake-autorate-bridge` literal == 2 per script: one per block).
    - The `health_payload` regions of the two scripts are byte-identical (diff is empty).
    - `available`/`raw_rtt_ms`/`staleness_sec` keys+types unchanged.
    - No new env var or source-IP lookup added (grep for `ping_source_ip` / `ip route` shows no
      new additions).
  </acceptance_criteria>
  <done>
    Both bridge scripts emit the D-02 honest triple on both health paths, byte-identical to each
    other, with no env wiring added.
  </done>
</task>

<task type="auto">
  <name>Task 2: Turn both bridge artifact endpoint tests GREEN on the triple</name>
  <files>deploy/scripts/cake-autorate-spectrum-state-bridge, deploy/scripts/cake-autorate-att-state-bridge</files>
  <read_first>
    - tests/test_spectrum_cake_autorate_artifacts.py (test_state_bridge_serves_wanctl_compatible_health_endpoint ~164-213 — the Wave-0-extended endpoint poll asserting the triple)
    - tests/test_att_cake_autorate_artifacts.py (the spectrum mirror)
    - deploy/scripts/cake-autorate-spectrum-state-bridge (the edited health_payload from Task 1)
  </read_first>
  <action>
    This task validates Task 1 against the Wave 0 endpoint tests. Run both bridge artifact tests;
    they spawn the bridge subprocess, poll `/health`, and now assert
    `wan["measurement"]["producer"] == "cake-autorate-bridge"`, `wan["measurement"]["backend"] is
    None`, `wan["measurement"]["source_ip"] is None`, plus the byte-preserved existing fields. If a
    test fails because the live `/health` does not emit the triple, the fault is in the Task 1
    edit (a missed block or a typo) — fix the deploy script, NOT the test. The test surface was
    fixed in Wave 0 (Plan 01); do not modify the test assertions here. No source/test file other
    than the two deploy scripts should change in this plan.
  </action>
  <verify>
    <automated>.venv/bin/pytest -o addopts='' tests/test_spectrum_cake_autorate_artifacts.py tests/test_att_cake_autorate_artifacts.py -q</automated>
  </verify>
  <acceptance_criteria>
    - `.venv/bin/pytest -o addopts='' tests/test_spectrum_cake_autorate_artifacts.py
      tests/test_att_cake_autorate_artifacts.py -q` passes, including the Wave 0 triple assertions
      on the live-served `/health` measurement block for BOTH WANs.
    - The byte-preserved existing assertions (`raw_rtt_ms`, `available`, `staleness_sec`) still pass.
    - `git status` shows only the two deploy scripts changed in this plan (no test edits).
  </acceptance_criteria>
  <done>
    Both bridge artifact endpoint tests are GREEN on the D-02 honest triple; the live production
    `/health` now carries uniform attribution keys.
  </done>
</task>

</tasks>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| operator/monitoring → bridge `/health` (127.0.0.1:9101) | localhost-bound production observability endpoint; no untrusted network input crosses here. |
| cake-autorate EWMA log → bridge health_payload | the bridge parses RTT from upstream bash; it never ran the wanctl seam, so backend/source_ip are honestly null. |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-244-06 | Spoofing | bridge RTT mistaken for a wanctl-backend A/B contender | mitigate | `producer="cake-autorate-bridge"` + `backend=null` make the bridge structurally non-attributable to icmplib/fping; a Phase 245 scraper filters on `producer == "wanctl-backend"` and cannot mix bridge EWMA RTT into the A/B (D-02 honesty). |
| T-244-01 | Information Disclosure | attribution exposed on production `/health` | accept | `source_ip` is `null` on the bridge (no source-IP env); the only added strings are the literal producer label + nulls. No sensitive data added. Endpoint localhost-bound. |
| T-244-07 | Tampering | the two bridge scripts drifting apart | mitigate | Task 1 keeps the health_payload regions byte-identical (diff gate); both artifact tests cover both WANs (Pitfall 4). |
| T-244-SC | Tampering | npm/pip/cargo installs | mitigate | N/A — bash deploy-script edits only; no external package installs. |
</threat_model>

<verification>
- `.venv/bin/pytest -o addopts='' tests/test_spectrum_cake_autorate_artifacts.py tests/test_att_cake_autorate_artifacts.py -q` passes.
- `diff` of the two scripts' `health_payload` regions is empty (lockstep).
- These are deploy scripts (outside src/wanctl) — they do NOT affect the SAFE-17 controller-path
  verifier, but the wave-gate `bash scripts/phase244-safe17-boundary-check.sh` must still pass
  (proving the parallel src edits in Plans 02/03 introduced no drift).
- Live confirmation is post-merge/deploy-time (operator: `ssh <host> 'curl -s
  http://127.0.0.1:9101/health | python3 -m json.tool'`), NOT a planning gate.
</verification>

<success_criteria>
- Both bridge scripts emit the D-02 honest triple (`producer="cake-autorate-bridge"`, `backend=null`,
  `source_ip=null`) on both health paths, byte-identical to each other.
- Existing bridge contract fields byte-preserved; both artifact tests GREEN; no env wiring added.
</success_criteria>

<output>
Create `.planning/phases/244-health-payload-attribution-metadata/244-04-SUMMARY.md` when done.
</output>
