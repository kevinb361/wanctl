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

The nftables `bridge qos` rule counters are a useful CORROBORATING read-only signal (NOT a gating
one — see the gating-vs-corroborating taxonomy under ## DSCP-03): if present, each `ip dscp set` rule
would show how much traffic the bridge is *marking* into ef/af41/cs1. **However, the checked-in rules
carry no explicit `counter` statement (verified), so in production these counters are expected to be
ABSENT.** Counter absence maps to `bridge_counter_signal=unknown` and, because this channel is
corroborating-only, it NEVER gates the verdict — it neither confirms theater nor forces a negative
close. The AUTHORITATIVE DL marking signal is the pre-wash `organic_dl_histogram` at the enqueue
interface (stage 4 observation), which is what actually decides whether marks reach CAKE intact. Treat
any bridge counter that does happen to be present as supporting context only.

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
- **Source-side DL DSCP proof (NEW HIGH — required for any negative DL reading).** A LAN client's
  `--tos 0xb8` marks its OUTBOUND (UL) packets, NOT the RETURN-path DL packets. So a `STRIPPED` reading
  on `dl_ef_probe` is only meaningful if the DL return leg was PROVEN to carry DSCP 46 at the source
  (before the path under test). The probe MUST observe the DL return leg at a source-side point (the
  same 5-tuple at/near the external/return endpoint, or the first hop where the DL leg is observable as
  marked) and record `EF_PKTS_AT_SOURCE` + `DL_SOURCE_EF_PROVEN` (true only when `EF_PKTS_AT_SOURCE` ≥
  100 AND ≥90% of source-side DL probe packets carry DSCP 46). When `DL_SOURCE_EF_PROVEN=false`,
  `dl_ef_probe` is `unknown`/`degraded`, NEVER `STRIPPED` — a never-EF DL packet cannot be miscounted
  as a stripped mark and feed the negative-close AND.
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
be reverse-fitted. This section was hardened after the cycle-1 Codex review (225-REVIEWS.md): the
original draft said "if ANY" over AND-joined bullets (self-contradictory), left "meaningful" and
"negligible" unquantified, had no minimum-sample floor, and had no defined branch for the case where
the bridge nft counters do not exist. All of those are resolved below **before any capture runs**.

### Evidence channels (each tagged with a validity state)

The verdict consumes four direction-split evidence channels. Each channel resolves to one of
`valid` / `invalid` / `unknown`. A channel that is `invalid` or `unknown` is NEVER silently read as
a negative signal.

**Channel roles — gating vs corroborating (resolves cycle-2 HIGH-A).** The four channels are NOT
all equal in the verdict. Exactly two channels are **gating** for the DL diffserv question that the
milestone re-evaluates: `organic_dl_histogram` and `dl_ef_probe`. The other two —
`bridge_counter_signal` and `ul_ef_probe` — are **corroborating-only / non-gating**: they may add
context and may corroborate a positive, but their state (including `unknown`) is NEVER counted among
the channels that decide the branch. Consequently:

- `bridge_counter_signal=unknown` (the VERIFIED production reality — the `ip dscp set` rules carry no
  `counter` clause, so counters are absent) is **expected and benign**. Because the bridge-counter
  channel is corroborating-only, its `unknown` state neither blocks nor forces any branch — it is
  simply not a gating input. The authoritative DL marking signal is `organic_dl_histogram` (the
  pre-wash DSCP histogram at the enqueue interface), exactly as established in the prior revision.
- `ul_ef_probe` is likewise non-gating for the DL verdict (a UL mark reaching spec-modem does not
  exercise the DL CRS/Ruckus/bridge path); it can corroborate but never decide.

This makes the verdict function **deterministic for the counters-absent case**: an absent/`unknown`
bridge counter alone can never force a negative verdict, and the "unknown maps to QUALIFIED" rule
below applies to the two GATING DL channels, not to the corroborating bridge-counter channel.

1. **`bridge_counter_signal`** (DL marking corroboration — **corroborating-only, non-gating**; from
   225-01 `bridge-mark-counters.txt`).
   - **CRITICAL — counters may not exist.** The checked-in `deploy/nftables/bridge-qos.nft` rules
     (`ip dscp set ef|af41|cs1` at L42, L47-49, L53-85, L96, L99-122) carry **no explicit `counter`
     statement** (verified by Codex and re-verified against the repo). `nft list table bridge qos`
     may therefore emit no per-rule counters. **Counter ABSENCE maps to
     `bridge_counter_signal=unknown`, NEVER `negligible`.** 225-01 must emit
     `COUNTERS_AVAILABLE=true|false` and `COUNTER_MODE=delta|snapshot|unavailable`.
   - If counters ARE present, the signal must be a **before/after delta over a bounded window**
     (`COUNTER_MODE=delta`), not a single cumulative snapshot (a snapshot is stale state, not a load
     measurement). A snapshot-only read is `COUNTER_MODE=snapshot` and is treated as `unknown` for
     verdict purposes (insufficient to prove a load level).
2. **`dl_ef_probe`** (DL survival, from 225-02). EF (DSCP 46) survival to the **`spec-router` CAKE
   enqueue point** on a DL-direction probe that exercises the CRS/Ruckus/bridge classification path.
   **Source-side proof required for a negative reading:** a `STRIPPED` (negative) result is admissible
   ONLY when `DL_SOURCE_EF_PROVEN=true` (the DL return leg carried DSCP 46 at source — see DSCP-02). If
   `DL_SOURCE_EF_PROVEN=false`, this channel is `unknown`/`degraded`, never `STRIPPED`, so it cannot
   contribute to the negative-close AND.
3. **`ul_ef_probe`** (UL survival, from 225-02). EF survival to the **`spec-modem` CAKE enqueue
   point** on a UL probe sourced from cake-shaper. NOTE: a UL probe only proves a local mark reaches
   spec-modem — it does **not** exercise the DL CRS/Ruckus/bridge path the milestone re-evaluates,
   so `ul_ef_probe` alone can NEVER drive the negative branch and can NEVER, by itself, unblock a DL
   diffserv A/B.
4. **`organic_dl_histogram`** (DL organic marking, from 225-02 `dscp-histogram-spec-router.txt`).
   Fraction of DL IP packets at the `spec-router` enqueue interface carrying non-zero DSCP.

### Pre-registered numeric thresholds (quantifies "meaningful" / "negligible")

- **NEGLIGIBLE marking** (DL): non-BestEffort (DSCP != 0) packets are **< 1.0%** of total DL IP
  packets at the enqueue interface, AND non-BestEffort bytes (where measurable) are **< 1.0%** of
  DL bytes, over a valid representative window.
- **MEANINGFUL marking** (DL): non-BestEffort packets are **≥ 5.0%** of total DL IP packets at the
  enqueue interface. The 1.0%–5.0% band is the **ambiguous** zone (qualified proceed).
- **EF probe SURVIVED**: **≥ 90%** of the probe's own 5-tuple-filtered packets arrive at the
  enqueue interface still carrying DSCP 46. **STRIPPED**: **< 10%** carry DSCP 46. The 10%–90% band
  is `degraded` (qualified). Survival is decided on the **probe 5-tuple by count**, never on
  unfiltered histogram presence (background EF or one stray packet must not flip the result).
- **Representative-load floor (minimum-sample gate)** — a DL histogram window is only `valid` if
  BOTH: **total captured IP packets ≥ 2000** AND **active seconds (seconds with ≥ 1 captured
  packet) ≥ 30** within the capture duration. A window below either floor is
  `organic_dl_histogram=invalid` (quiet window) and CANNOT drive `MARKS_DO_NOT_SURVIVE`.
- **EF probe sample gate** — an EF-probe result is only `valid` if the probe emitted and the capture
  recorded **≥ 100 probe-5-tuple packets** at the source side; below that the probe is
  `unknown`/`degraded`, not a clean negative. For the DL probe, a negative (`STRIPPED`) reading
  additionally requires `DL_SOURCE_EF_PROVEN=true` (`EF_PKTS_AT_SOURCE` ≥ 100 AND ≥90% of source-side
  DL probe packets carry DSCP 46); if source-side DL marking is unproven the DL probe is
  `unknown`/`degraded`, never `STRIPPED`.

### Capture-ordering rule (resolves the CAKE-wash false-negative)

Production Spectrum runs `diffserv: besteffort` + **`allow_wash: true`** (verified at
`configs/spectrum.yaml:44-45`). CAKE wash strips DSCP **after** tin selection at enqueue. A capture
taken on the **post-wash egress/transmit side** can falsely show EF stripped even though the mark
reached CAKE intact — a false negative that would wrongly close the milestone.

**Rule:** the EF-survival and organic-DL evidence MUST be captured at the **pre-wash / ingress-to-CAKE
observation point** (the DSCP byte as it *arrives* at the enqueue interface, BEFORE the CAKE egress
qdisc applies wash), NOT on the post-wash transmit side.

**Capture direction is NOT self-evident and MUST be proven, not asserted (resolves cycle-2 HIGH-C).**
The naive `tcpdump -Q in` recipe is directionally wrong for DL: download packets *egress*
`spec-router` toward the LAN, so host-inbound (`-Q in`) on `spec-router` is not the pre-CAKE enqueue
point. The correct DL pre-wash observation point is where DL packets **arrive at the CAKE-bearing
interface from the marking stage** — i.e. inbound on the `spec-router` bridge member that faces
`spec-modem`/the `spectrum_dl` marking chain (the DSCP byte after the bridge sets it but before the
`spec-router` egress qdisc washes it). The exact interface + direction must be **derived from the
live topology** (`ip -d link show`, bridge member roles, and the `iif spec-modem oif spec-router`
classification path), not assumed.

**`CAPTURE_POINT` is a FALSIFIABLY-PROVEN property, not an operator-asserted flag or topology citation
(resolves cycle-3 HIGH-C).** 225-02 MUST run a FALSIFIABLE proof step that establishes, from live
evidence, that the chosen capture interface+direction sits (a) downstream of the DSCP-setting stage
and (b) upstream of the CAKE egress qdisc that applies wash. The proof must be able to FAIL if the hook
were actually post-wash. Acceptable falsifiable checks: (i) **paired pre/post-wash observation of the
same probe 5-tuple** — the candidate pre-wash hook shows the DSCP bit (EF/AF41/CS1) SET while a
post-wash egress/transmit-side observation of the same 5-tuple shows it CLEARED (because `allow_wash:
true` strips it after tin selection); the hook is proven upstream of wash. This FAILS (point stays
`unknown`) if both sides agree, so it is genuinely falsifiable. (ii) An equivalent positive
demonstration via `tc -d qdisc/filter show` ordering that the capture hook fires before the
`spec-router` CAKE-egress wash qdisc. **Topology text alone (interface, direction, bridge member role)
is NOT a proof — it is supporting context only.** The script records
`CAPTURE_POINT=pre_wash_ingress|post_wash_egress|unknown`, `WASH_ORDERING_PROVEN=true|false`, AND a
`capture-point-proof.txt` artifact recording the falsifiable check result plus supporting topology
context. **Default until the falsifiable check passes is `CAPTURE_POINT=unknown` /
`WASH_ORDERING_PROVEN=false`.** `pre_wash_ingress` may be recorded ONLY when the falsifiable check
passes.

If capture ordering relative to wash cannot be proven (`WASH_ORDERING_PROVEN=false` or
`CAPTURE_POINT=unknown`), the affected survival channel is `unknown` — it CANNOT drive
`MARKS_DO_NOT_SURVIVE` (an ambiguous/unproven capture point must not early-exit the milestone), and
per the gating rule it also cannot satisfy the negative branch's requirement that both gating DL
channels be `valid`.

### The pre-registered branches (mutually exclusive, evaluated top to bottom)

Fire exactly one. Evaluate in order; the first matching branch wins.

**MARKS_DO_NOT_SURVIVE** (early-exit → v1.44 confirmed, milestone may close negative) — fires ONLY
when BOTH required negative signals are `valid`, observed, and above the sample-quality floors
(this is a logical AND of two valid negatives, matching the original intent of the two bullets):
- `organic_dl_histogram` is `valid` AND shows **NEGLIGIBLE** DL marking (< 1.0% packets AND, where
  measurable, < 1.0% bytes — see the byte-fraction rule under "Pre-registered numeric thresholds"),
  **AND**
- `dl_ef_probe` is `valid` AND **STRIPPED** (< 10% of probe packets carry DSCP 46 at the pre-wash
  enqueue point) AND `DL_SOURCE_EF_PROVEN=true` (the DL return leg was provably EF at source — a
  never-EF DL packet can never be counted STRIPPED; if source-side marking is unproven the channel is
  `unknown`/`degraded`, not a valid negative).
- This branch is gated EXCLUSIVELY by the two GATING DL channels above (`organic_dl_histogram` and
  `dl_ef_probe`); both MUST be `valid`. The corroborating-only channels do NOT gate it:
  `bridge_counter_signal=unknown` (counters absent — the verified production case) neither blocks nor
  enables this branch, and `ul_ef_probe` is irrelevant to it. If EITHER gating DL channel is
  `invalid` or `unknown` (quiet window below the sample floor, or capture point not proven pre-wash),
  this branch CANNOT fire → fall through to QUALIFIED. There is no path by which an absent bridge
  counter forces a negative close.

→ Conclusion: "diffserv4 remains classification theater — v1.44 confirmed." Phases 226–228 do not run.

**MARKS_SURVIVE** (proceed → unblock Phase 226) — fires when DL marking clearly reaches the shaper:
- `organic_dl_histogram` is `valid` AND shows **MEANINGFUL** DL marking (≥ 5.0%), **OR**
- `dl_ef_probe` is `valid` AND **SURVIVED** (≥ 90% of probe packets carry DSCP 46 at the pre-wash
  enqueue point).

→ Conclusion: "marks reach the shaper on the DL path under test — A/B is warranted." Unblock Phase 226.

**MARKS_SURVIVE_QUALIFIED** (the catch-all / fail-safe default) — fires in every remaining case,
including:
- ambiguous-band DL marking (1.0%–5.0%) or `degraded` DL EF probe (10%–90%); OR
- a GATING DL channel is `invalid` (quiet window below the sample floor) or `unknown` (wash ordering
  unproven / `CAPTURE_POINT=unknown`) so the negative branch could not fire and the positive branch
  was not met; OR
- the only surviving signal is `ul_ef_probe` (UL mark reaches spec-modem) without a `valid` GATING DL
  channel — a UL-only positive cannot unblock a DL diffserv A/B, nor can it close negative.

(Note: an absent/`unknown` `bridge_counter_signal` is NOT itself a reason to land here — it is
corroborating-only and non-gating; this branch is reached via the gating DL channels or a UL-only
positive, not via the bridge counter.)

→ Conclusion: "evidence is insufficient to early-exit negative and insufficient to clearly unblock."
**`unknown` ALWAYS maps here, never to MARKS_DO_NOT_SURVIVE** — the milestone is never closed negative
on absent/ambiguous evidence.

**Relationship to the Phase 226 gate (resolves cycle-2 HIGH-B — conservative default).** ROADMAP.md
gates Phase 226 on a **"marks survive"** verdict from Phase 225. `MARKS_SURVIVE_QUALIFIED` is NOT
"marks survive" — it is the explicit absence of a clear positive. Phase 226 is the phase that builds
Snapshot A, locks GATE-01 thresholds, and begins **touching production config**, so the
safety-preserving default is unambiguous:

> **QUALIFIED BLOCKS Phase 226 by default.** Only a `MARKS_SURVIVE` verdict satisfies the ROADMAP.md
> Phase 226 gate and unblocks it. `MARKS_SURVIVE_QUALIFIED` does NOT auto-unblock Phase 226 and does
> NOT auto-close the milestone negative. It is a hold state.

A QUALIFIED verdict therefore terminates the autonomous flow and requires an explicit, recorded
operator decision before Phase 226 may proceed — one of: (a) collect better evidence and re-run the
Phase 225 capture/verdict (e.g. a longer/representative window, a clean DL EF probe) to reach a clear
`MARKS_SURVIVE` or `MARKS_DO_NOT_SURVIVE`; or (b) the operator explicitly accepts the documented
caveat and authorizes Phase 226 to proceed-with-caveat, deferring the volume question to Phase 226's
GATE-01 "useful non-BestEffort tin separation" tie-breaker. Option (b) is an operator override that
the verdict artifact must surface as a required decision — it is never taken automatically by the
verdict logic. This keeps an ambiguous verdict from silently leaking into the production-touching
phase while preserving a path forward that the roadmap's GATE-01 tie-breaker can adjudicate once a
human has signed off.

### Verdict artifact requirements

The verdict artifact must:
- emit a single machine-readable `VERDICT:` line with exactly one of `MARKS_DO_NOT_SURVIVE` /
  `MARKS_SURVIVE` / `MARKS_SURVIVE_QUALIFIED`;
- record each of the four channels with its validity state and the concrete value that drove it
  (counter deltas or `COUNTERS_AVAILABLE=false`; DL/UL probe survival percentages with packet
  counts; for the DL probe `EF_PKTS_AT_SOURCE` / `DL_SOURCE_EF_PROVEN`; DL non-BestEffort packet AND
  byte fractions; sample-floor pass/fail; `CAPTURE_POINT` / `WASH_ORDERING_PROVEN`);
- name the explicit consequence for Phases 226–228 (do-not-run + negative close, OR unblock 226 with
  the proceed condition);
- restate that it was computed from this pre-registered logic, not reverse-fitted.

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

Controller-path source must be byte-identical to the v1.48 close. The cycle-1 review found the draft
SAFE-13 check (`git diff --name-only v1.48 HEAD`) was **weaker** than the SAFE-12 precedent it
claims to mirror: a name-only committed-diff misses unstaged edits, staged-but-uncommitted edits,
and untracked files under the protected paths. The v1.48 `safe12-boundary-check.json` recorded a
strictly stronger artifact. SAFE-13 must match that standard.

**SAFE-13 must run all three git state channels over each protected path, plus per-file sha equality
against the `v1.48` anchor:**

```bash
# Channel 1 — committed diff vs anchor (per path):
git diff --name-only v1.48 HEAD -- <path>        # committed changes
# Channel 2 — staged (index) changes (per path):
git diff --name-only --staged -- <path>          # equivalently --cached
# Channel 3 — working-tree dirty state (per path):
git status --porcelain -- <path>                 # unstaged + untracked + staged summary
git ls-files --others --exclude-standard -- <path>   # untracked files explicitly
# Per-file integrity — sha equality vs the anchor blob:
git rev-parse v1.48:<path>  vs  sha of HEAD/worktree <path>
```

Protected controller paths (the six SAFE-12 controller-path entries; Phase 225 does not touch
steering but the script accepts the same protected set):
`src/wanctl/wan_controller.py`, `src/wanctl/queue_controller.py`, `src/wanctl/cake_signal.py`,
`src/wanctl/alert_engine.py`, `src/wanctl/fusion_healer.py`, `src/wanctl/backends/`. Plus ATT config
byte-identical: `configs/att.yaml`.

The emitted JSON MUST match the v1.48 `safe12-boundary-check.json` shape (strictly stronger than a
name-only count): `baseline_tag`/`anchor`, `baseline_commit`, `head_commit`, `protected_paths`,
`per_path_diff` (per-file added/removed/lines), `per_file_sha256_equal` (per-file bool vs anchor),
`dirty_tree` (`unstaged`/`staged`/`untracked`/`status_porcelain`), `dirty_tree_clean` (bool),
`committed_clean` (bool), `att_config_diff_count`, `passed` (bool), `checked_at`.

**Fail-closed semantics:** `passed` is true ONLY when committed diff == 0 across all protected paths
AND `dirty_tree_clean` is true (no staged/unstaged/untracked changes) AND every
`per_file_sha256_equal` is true AND `att_config_diff_count` == 0. Any dirty or diverged state fails
the boundary and the verdict gate (225-03) fails closed.

Phase 225 is a pure trace/evidence + new-script phase — it adds capture scripts and evidence
artifacts only (all outside the protected paths). There is no reason to touch controller-path
source, so SAFE-13 is expected to hold trivially. The value is the recorded proof at the SAFE-12
standard. Reference artifact:
`.planning/milestones/v1.48-phases/224-production-canary-rollback-discipline/.../safe12-boundary-check.json`.

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
