# Phase 225: DSCP Survival Trace — Research

**Researched:** 2026-06-03
**Phase goal:** Operator can read a complete, read-only, evidence-backed picture of whether DSCP marks survive the current end-to-end path to Spectrum CAKE ingress, and gets a gated DSCP-03 verdict that either short-circuits the A/B (marks don't survive → v1.44 confirmed → milestone can close negative) or unblocks it (marks survive → proceed to Phase 226).
**Requirements:** DSCP-01, DSCP-02, DSCP-03, SAFE-13 (cross-phase invariant)

---

## Premise being re-tested

SEED-001's load-bearing claim (fulfilled by v1.44, shipped `920 besteffort wash`):

> ISPs strip DSCP. The shaper sees unmarked ingress in the DL direction. With unmarked
> ingress, `diffserv4` classification collapses to BestEffort for nearly all traffic —
> "classification theater." A single `besteffort` tin is topology-equivalent.

That claim was about **DSCP arriving from the carrier**. The topology has since changed in a way that may invalidate it **at the local pre-CAKE stage**, not at the carrier:

- **`deploy/nftables/bridge-qos.nft`** runs at `hook forward priority -10` on the cake-shaper
  bridge and *sets* DSCP via `ip dscp set ef|af41|cs1` on download flows (`iif spec-modem
  oif spec-router`) **before** the CAKE egress qdisc on `spec-router`. So even if the carrier
  delivers DSCP 0, the bridge re-marks locally just upstream of CAKE.
- **CRS hardware QoS trust** and **Ruckus QoS mirroring** may preserve endpoint-set EF marks
  (e.g. VoIP, WireGuard) end-to-end on the LAN, and the bridge's `ip dscp != 0 accept`
  trust-and-skip rule passes those through untouched.
- **Upload:** router/client-originated DSCP on `spec-modem` egress may matter if Spectrum CAKE
  is allowed to tin upload traffic.

**The re-test question is therefore narrower and more answerable than SEED-001's:**
Do DSCP marks (bridge-set on DL, endpoint/router-set on UL) survive to the **CAKE enqueue
point** on `spec-router` / `spec-modem`, in enough volume to produce useful non-BestEffort tin
separation? If yes → `diffserv4 wash` has real signal to classify on (A/B worth running). If no
→ the bridge marks are being lost/zeroed before CAKE, and v1.44 stands regardless of carrier
behavior.

This is observable **read-only on the cake-shaper host itself** — we do not need to touch CRS,
Ruckus, or the router to answer it. That is the key insight that keeps Phase 225 inside the
read-only constraint.

---

## Where DSCP can be set / preserved / stripped (the trace map)

Ordered DL ingress → CAKE enqueue (the direction that matters most; `diffserv4` DL classification
is the v1.44 theater claim):

| # | Stage | Host / surface | Sets / preserves / strips DSCP? | Read-only observation point |
|---|-------|----------------|----------------------------------|-----------------------------|
| 1 | Carrier (Spectrum CMTS / DOCSIS) | upstream, not ours | Strips/zeros (SEED-001 premise) | Inferred — observe DSCP at modem-side ingress |
| 2 | spec-modem ingress (DL packets arriving from carrier) | cake-shaper `spec-modem` | as-delivered by carrier | `tc filter` byte counters or short `tcpdump` on `spec-modem` ingress |
| 3 | bridge forward chain `spectrum_dl` (priority -10) | cake-shaper `bridge qos` table | **SETS** DSCP (ef/af41/cs1) + trusts non-zero | `nft list table bridge qos` (rule packet/byte counters), `nft monitor` (read-only) |
| 4 | CAKE egress qdisc on spec-router (DL) | cake-shaper `spec-router` | classifies into tin by DSCP (in `diffserv4`); `wash` strips DSCP *after* tin selection | `tc filter show dev spec-router` byte counters by DSCP; `tcpdump`/`tc` at enqueue |
| 5 | spec-router → MikroTik → LAN | downstream | (post-CAKE) | n/a for survival-to-CAKE question |

UL path (CAKE egress on `spec-modem`): endpoint/router DSCP arrives on `spec-router` ingress →
bridge forward (no UL classification chain in `bridge-qos.nft`; only DL chains exist) → CAKE on
`spec-modem`. UL DSCP survival depends entirely on what the router/clients mark, since the bridge
does not re-mark UL.

**Critical nuance — current production mode is `besteffort`, so CAKE has only ONE tin right now.**
`check_cake.py:check_tin_distribution()` reads per-tin counters, but in `besteffort` mode there is
nothing to separate. Therefore the survival trace **cannot** rely on production CAKE tin counters
to answer "do marks survive." It must observe the DSCP field *as it arrives at the CAKE enqueue
interface* — i.e. the DSCP distribution on `spec-router` (DL) / `spec-modem` (UL) egress
**independent of CAKE's tin model**. Two viable read-only techniques:

1. **`tc filter` with `u32`/`flower` match on DSCP, action `pass`, per-DSCP counters** attached
   read-only to the egress qdisc's classification view. Risk: attaching filters is a mutation of
   the qdisc filter list. **Reject for the read-only constraint unless done as an explicitly
   reversible, operator-approved probe** — prefer technique 2.
2. **Short bounded `tcpdump` on the egress interface** (`spec-router` / `spec-modem`), capturing
   only the IP TOS/DSCP byte, histogrammed offline. Read-only, no qdisc mutation, no gear change.
   This is the recommended primary technique. Pair it with the **nftables rule counters** in
   `bridge qos` (stage 3) which are already incrementing in production and are pure reads.

The nftables `bridge qos` rule counters are the single most valuable read-only signal: each
`ip dscp set` rule has packet/byte counters showing how much traffic the bridge is *marking* into
ef/af41/cs1 right now. If those counters are near-zero under representative load, the marks aren't
there to survive regardless of downstream behavior (theater confirmed cheaply). If they're
substantial, stage 4 observation tells us whether those marks reach CAKE intact.

---

## DSCP-02: deliberately marked (EF) flow

To establish whether a *known* mark survives end-to-end (not just inferred from rule counters),
inject a controlled EF-marked flow and observe it at CAKE ingress:

- **Marked flow:** low-rate EF (DSCP 46) UDP from a LAN client toward an external endpoint
  (DL return path) and from the cake-shaper toward the internet (UL). `iperf3 --tos 0xb8`
  (0xb8 = DSCP 46 EF in the TOS byte) or `nping --tos 0xb8` generates cleanly markable traffic.
- **Observation:** `tcpdump -n -v 'ip[1] & 0xfc != 0'` on `spec-router` (DL) / `spec-modem` (UL)
  egress, filtered to the probe 5-tuple, confirming the EF bit is present at the CAKE enqueue
  interface. Degrade-to-best-effort: if the test rig cannot mark cleanly (client TOS stripped by
  WMM/AP), capture whatever DSCP *does* arrive and note the degradation — the check is not dropped
  (AB-04 precedent for graceful degradation).
- This is the deliberately-marked half of Success Criterion 2. The representative-traffic half is
  covered by the bridge rule counters + egress DSCP histogram under organic load.

**Traffic generation caveat:** generating a low-rate probe flow is *not* an external-gear mutation
and is *not* a production CAKE-mode change — it is benign synthetic traffic, consistent with how
prior phases ran flent/RRUL captures (`phase191-flent-capture.sh`). Keep it low-rate to avoid
perturbing the production link. The read-only constraint is about **not mutating CRS/Ruckus/router
config and not changing the Spectrum CAKE mode** — it does not forbid observing traffic or sending
a bounded diagnostic probe.

---

## DSCP-03: the gated verdict (decision logic)

The verdict is a deterministic function of the captured evidence, pre-registered here so it cannot
be reverse-fitted:

**MARKS DO NOT SURVIVE (early-exit → v1.44 confirmed, milestone may close negative)** if ANY:
- Bridge `ip dscp set` rule counters (ef/af41/cs1) are negligible under representative load
  (essentially all DL traffic falls through to BestEffort), AND
- The deliberately-marked EF probe does NOT arrive with its DSCP intact at the `spec-router` /
  `spec-modem` CAKE enqueue interface (mark zeroed/stripped upstream of CAKE).

→ Conclusion: "diffserv4 remains classification theater — v1.44 confirmed." `diffserv4 wash` would
classify near-100% into BestEffort exactly as v1.44 found. Phases 226–228 do not run.

**MARKS DO SURVIVE (proceed → unblock Phase 226)** if:
- Bridge rule counters show meaningful non-BestEffort marking under representative load, AND/OR
- The deliberately-marked EF probe arrives with DSCP intact at the CAKE enqueue interface.

→ Conclusion: "marks reach the shaper — A/B is warranted." Unblock Phase 226 baseline capture.

**Ambiguous / partial** (e.g. EF probe survives but organic non-BestEffort volume is tiny): record
as a *qualified proceed* with the caveat that the A/B must measure whether the surviving volume is
large enough to matter — the GATE-01 "useful non-BestEffort tin separation" threshold in Phase 226
becomes the tie-breaker. Default lean: proceed, because a clean EF-survival result falsifies the
strong form of the theater claim.

The verdict artifact must state which branch fired, cite the specific counter values / capture
evidence, and explicitly name the consequence for Phases 226–228.

---

## Read-only constraint — what is and isn't allowed in this phase

**Allowed (read-only / evidence):**
- SSH to `cake-shaper` with `sudo -n` for **reads only**: `nft list table bridge qos`,
  `nft list ruleset`, `tc -s qdisc show dev spec-router|spec-modem`, `tc filter show`,
  `ip -d link show`, bounded `tcpdump` capture (read), `cat` of config/state files.
- `nft monitor` (read-only event stream), bounded with a timeout.
- Bounded low-rate diagnostic probe traffic (EF-marked iperf3/nping) — benign synthetic traffic,
  not a config mutation.
- Reading wanctl `/health` on `:9101` (bound autorate) — same as phase224 snapshot.

**Forbidden in this phase:**
- Any mutation of CRS / Ruckus / MikroTik router configuration (operator decision; out of milestone).
- Any change to the Spectrum CAKE mode (`diffserv`/`allow_wash`/ceiling) — no candidate deploy here.
- Any change to `bridge-qos.nft` or reload of the `bridge qos` table.
- Attaching persistent `tc filter` probes that survive the capture (prefer tcpdump; if a filter
  probe is unavoidable, it must be explicitly removed and the removal verified).
- Any controller-path source edit (SAFE-13).

---

## SAFE-13 (cross-phase invariant)

Controller-path source must be byte-identical to the v1.48 close. Proven idiom from v1.48 Phase 224
(SAFE-12), reused verbatim with the `v1.48` tag as the anchor:

```bash
git diff --name-only v1.48 HEAD -- \
  src/wanctl/wan_controller.py \
  src/wanctl/queue_controller.py \
  src/wanctl/cake_signal.py \
  src/wanctl/alert_engine.py \
  src/wanctl/fusion_healer.py \
  src/wanctl/backends/
# MUST return zero lines.
```

ATT config byte-identical:
```bash
git diff --name-only v1.48 HEAD -- configs/att.yaml   # MUST return zero lines.
```

Phase 225 is a pure trace/evidence + new-script phase — it adds capture scripts and evidence
artifacts only. There is no reason to touch controller-path source, so SAFE-13 is expected to hold
trivially. The verification is a recorded boundary check, mirroring `safe12-boundary-check.json`.

---

## Reusable assets & conventions (ground the plans in existing patterns)

| Asset | Path | Use |
|-------|------|-----|
| Snapshot/evidence conventions | `scripts/phase224-snapshot-a.sh` | SSH host `cake-shaper`, `sudo -n cat`, redacted committable + operator-private `--raw-dir`, MANIFEST.md, sha256, read-only posture, required-artifact assertion loop |
| Flent/RRUL capture pattern | `scripts/phase191-flent-capture.sh`, `phase213-baseline-capture.sh` | Bounded capture harness, env-driven config, evidence dir layout |
| Bridge QoS ruleset (the thing being traced) | `deploy/nftables/bridge-qos.nft` | `bridge qos` table, `spectrum_dl` chain, `ip dscp set` rules + counters, trust-and-skip rule |
| Per-tin CAKE stats reader | `src/wanctl/check_cake.py:check_tin_distribution()`, `_fetch_tin_stats()` | Read `tc -s qdisc` per-tin; useful for Phase 226+ but NOT sufficient for survival (one tin in besteffort) |
| CAKE interfaces / current mode | `configs/spectrum.yaml:36-45,68,77` | `spec-router` DL egress, `spec-modem` UL egress, host `10.10.110.223`, `diffserv: besteffort`, `allow_wash: true`, 920/18 |
| DSCP→tin mapping reference | `deploy/nftables/bridge-qos.nft:11-15`, Phase 141 CONTEXT canonical_refs | EF=46/Voice, AF4x/Video, CS1=8/Bulk, CS0=0/BestEffort |
| SAFE-12 boundary-check precedent | `.planning/milestones/v1.48-phases/224-production-canary-rollback-discipline/224-05-PLAN.md:108`, `224-03-SUMMARY.md:90` | `git diff --name-only <anchor> HEAD -- <controller files>` == empty |
| BRIDGE_QOS decision doc | `docs/BRIDGE_QOS.md` | `allow_wash` semantics; Spectrum-vs-ATT contrast; the verdict will append to this doc in Phase 228 |

**SSH/host facts:** target host `cake-shaper` (= `10.10.110.223`); autorate `/health` on `:9101`;
DL CAKE egress `spec-router`; UL CAKE egress `spec-modem`; DL bridge classify path
`iif spec-modem oif spec-router` → chain `spectrum_dl`. RouterOS REST at `10.10.99.1` is
**read-only reference only** in this phase (and only if needed to document the trust map; not mutated).

---

## Recommended plan decomposition

Three plans, Wave 1 = the two capture scripts (independent, parallelizable), Wave 2 = the verdict
(depends on both capture datasets) + the SAFE-13 boundary record.

1. **225-01 — Path trace map + bridge/CRS/Ruckus DSCP inventory (DSCP-01).** A read-only
   `scripts/phase225-dscp-trace.sh` capturing the static + live trace: `nft list table bridge qos`
   counters, `tc -s qdisc`/`tc filter` on `spec-router`/`spec-modem`, `ip -d link`, and a
   documented narrative of where DSCP is set/preserved/stripped (CRS trust → Ruckus mirroring →
   bridge → CAKE). Output a redacted evidence dir + `DSCP-TRACE.md` map. No gear mutation.

2. **225-02 — CAKE-ingress DSCP distribution under representative + deliberately-marked traffic
   (DSCP-02).** A read-only `scripts/phase225-dscp-ingress-capture.sh`: bounded `tcpdump` DSCP
   histogram on `spec-router` (DL) and `spec-modem` (UL) under (a) organic representative load and
   (b) a low-rate EF-marked probe (`iperf3 --tos 0xb8` / `nping`), with graceful degradation if the
   rig can't mark cleanly. Output redacted per-DSCP distribution evidence.

3. **225-03 — Gated DSCP-03 verdict + SAFE-13 boundary record.** Compute the pre-registered verdict
   from 225-01 + 225-02 evidence; write `DSCP-03-VERDICT.md` stating marks-survive / marks-don't,
   the consequence for Phases 226–228, and citing the evidence. Record the SAFE-13 boundary check
   (`safe13-boundary-check.json`) proving zero controller-path diff vs `v1.48` and byte-identical ATT.

---

## Open questions for the operator (non-blocking; plans assume safe defaults)

1. **EF probe rig:** is there a LAN client that can mark EF cleanly through the Ruckus AP, or should
   the probe originate on the cake-shaper itself (DL return vs UL)? *Default:* run the probe from
   cake-shaper (UL clean-mark guaranteed) and attempt a LAN-client DL probe best-effort, degrading
   gracefully if WMM strips the mark.
2. **tcpdump vs tc-filter for DSCP histogram:** plans default to `tcpdump` (no qdisc mutation). If
   the operator prefers a reversible `tc filter` counter probe for precision, that's an
   operator-approved variation, not the default.
3. **Capture duration / representative window:** plans default to bounded windows (e.g. 60–120 s)
   matching prior capture harnesses; operator can extend.
