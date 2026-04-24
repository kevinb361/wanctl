---
id: SEED-001
status: dormant
planted: 2026-04-24
planted_during: v1.40 Queue-Primary Signal Arbitration (Phase 195 planning)
trigger_when: before v1.40 milestone planning OR when cake_signal.py / EXCLUDED_PARAMS / CAKE mode is touched
scope: Medium
---

# SEED-001: Spectrum topology-correct CAKE mode — migrate to 920Mbit besteffort wash

## Why This Matters

An out-of-band flent test ~2026-04-22 found `920Mbit besteffort wash` outperforms the current-accepted `940Mbit diffserv4 nowash` on Spectrum. The result wasn't captured in `.planning/` at the time — it surfaced on 2026-04-24 during Phase 195 planning when Kevin recalled the finding.

The result is **topology-correct, not just a tuning win**:

- Physical layout: Both ISPs (Spectrum, ATT) → cake-shaper VM 206 (transparent bridge, linux-cake) → MikroTik router → LAN. The shaper sits between the ISPs and the MikroTik.
- ISPs do not preserve DSCP across their networks. Packets arrive at the shaper unmarked in the DL direction.
- With unmarked ingress, `diffserv4` classification at the shaper collapses to BestEffort tin for nearly all traffic — it's *classification theater*. A single `besteffort` tin is topology-equivalent and removes the ceremony.
- `wash` at the shaper (DL) strips DSCP before the router sees it. Since the router no longer consumes DSCP (post-simplification) and LAN-side WMM is not in scope for this deployment, `wash` is benign in DL and beneficial on UL (ISPs ignore DSCP anyway).

Why it matters now: v1.21 locked `diffserv4` + `no nat, no wash` as the transparent-bridge default back when the shaper was doing the DSCP classification. The topology has since shifted (router simplified, shaper moved), and the v1.21 default is now a legacy contract that Phase 195 (RTT confidence demotion + healer containment) will further encrust.

## When to Surface

**Trigger:** Before v1.40 milestone planning, OR any time work touches `src/wanctl/cake_signal.py`, `src/wanctl/cake_params.py:EXCLUDED_PARAMS`, or CAKE qdisc mode selection.

This seed should be presented during `/gsd-new-milestone` when the milestone scope matches:
- Signal-path refactor or simplification
- CAKE parameter changes on the shaper
- Any phase planning to build more on top of multi-tin diffserv4 assumptions (re-confound risk)
- Before the next "linux-cake optimization" style milestone

## Scope Estimate

**Medium** — A phase or two, needs planning. Likely a dedicated Phase 196 with:

1. **`cake_signal.py` tin-agnostic refactor** — currently aggregates over `tins[1:]` (Bulk/BestEffort/Video/Voice) at `cake_signal.py:13, :173, :306`. Surgical change: iterate over whatever tins exist (`len()`-aware), handle single-tin besteffort cleanly, preserve multi-tin diffserv4 behavior for ATT.
2. **Remove `wash` from `EXCLUDED_PARAMS`** behind a config gate — don't flip the D-08 transparent-bridge rule globally. Add a per-WAN config flag `cake_params.allow_wash: bool = false` that, when true, permits `wash` in the qdisc args. Default stays false so ATT and any future bridge deployments remain protected.
3. **Spectrum-only deployment** with A/B soak and rollback criteria. ATT stays `diffserv4 nowash` until separately validated (different carrier, different DSCP behavior).
4. **Replay harness** — a Phase 196 replay that captures before/after latency, throughput, jitter against the out-of-band finding. Use the existing replay pattern from Phase 193/194.

**Blocking dependencies:** Phase 195 must ship first (RTT confidence + healer containment). Changing CAKE mode under Phase 195 would create a three-way confound (RTT logic × signal simplification × CAKE mode) — impossible to bisect. Codex recommendation 2026-04-24 confirmed this ordering.

## Breadcrumbs

### Code that must change in Phase 196

- `src/wanctl/cake_signal.py:13, :173, :306` — aggregates `tins[1:]`, assumes Bulk/BestEffort/Video/Voice
- `src/wanctl/cake_params.py:60` — `EXCLUDED_PARAMS = {"nat", "wash", "autorate-ingress"}`
- `src/wanctl/cake_params.py:26-38` — `UPLOAD_DEFAULTS` / `DOWNLOAD_DEFAULTS` set `diffserv: "diffserv4"`
- `configs/spectrum.yaml:59` — `ceiling_mbps: 940` (becomes 920)
- `src/wanctl/backends/netlink_cake.py:63-65` — `diffserv` enum includes `besteffort: 2`

### Historical context

- `v1.21-ROADMAP.md:5` — original D-08 transparent-bridge rule: no nat, no wash, diffserv4
- `.planning/milestones/v1.22-phases/106-cake-optimization-parameters/106-CONTEXT.md:21` — reinforced the rule during CAKE optimization
- `.planning/milestones/v1.27-phases/133-diffserv-bridge-audit/133-ANALYSIS.md:16` — Phase 133 captured live as `940Mbit diffserv4 nowash`, option to "accept download BestEffort" mentioned but superseded
- `.planning/milestones/v1.28-phases/141-bridge-download-dscp-classification/141-CONTEXT.md:9` — Phase 141 reinforced diffserv4 bridge classification
- `docs/BRIDGE_QOS.md:24` — documents diffserv4 tins for bridge DSCP classification

### Related decisions

- Codex rescue session 2026-04-24 recommended Path A (ship Phase 195 on current contract, Phase 196 handles migration) — see memory `project_spectrum_besteffort_wash_finding.md`
- Memory `feedback_capture_out_of_band_tests.md` — this seed exists because the out-of-band test slipped project capture

## Notes

- ATT is a separate question. Different carrier (DSL, not DOCSIS), different DSCP behavior, different ISP tendencies. Do not assume the Spectrum finding generalizes. Phase 196 should explicitly scope to Spectrum only and leave ATT validation as its own follow-up.
- The `2026-04-23 Spectrum event replay` in Plan 195-03 remains valid for Phase 195 — it replays against the current controller mode. When Phase 196 lands, add a new replay fixture against the post-migration controller; do not retrofit the 195 replay.
- Rollback criteria for Phase 196 must include: any regression >5% on RRUL p99 latency, any increase in spectrum daemon restart rate, any increase in pressure-state transitions per hour.
- Out-of-band test details (date, flent profile, measured deltas) should be recovered from Kevin's test logs and added to the Phase 196 CONTEXT.md. If lost, Phase 196 must re-run the validation before landing.
