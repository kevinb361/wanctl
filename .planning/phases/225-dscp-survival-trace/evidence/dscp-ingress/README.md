# DSCP-02 Evidence: CAKE-Ingress DSCP Distribution

This directory is the operator-facing index for Plan 225-02 evidence. It records the DSCP byte that reaches the Spectrum CAKE enqueue observation points under representative traffic and optional deliberately EF-marked probe traffic.

## Artifact Layout

`scripts/phase225-dscp-ingress-capture.sh --output-dir <dir>` writes:

- `capture-point-proof.txt` — machine-readable proof fields for the pre-wash observation point. `CAPTURE_POINT` defaults to `unknown` until `WASH_PROOF_PASS=true` is backed by a falsifiable check.
- `dscp-histogram-spec-router-dl.txt` — direction-split organic download histogram at the Spectrum download enqueue observation point, including `NONBE_PKT_PCT` and `NONBE_BYTE_PCT`.
- `dscp-histogram-spec-modem-ul.txt` — direction-split organic upload histogram at the Spectrum upload enqueue observation point, including `NONBE_PKT_PCT` and `NONBE_BYTE_PCT`.
- `sample-quality.txt` — packet counts, byte counts, active seconds, non-BestEffort packet/byte fractions, and `WINDOW_VALID_DL` / `WINDOW_VALID_UL` sample-floor booleans.
- `dl-ef-probe-result.txt` — download-direction EF probe result, decided only on the probe 5-tuple and carrying source-side DL proof fields.
- `ul-ef-probe-result.txt` — upload-direction EF probe result, decided only on the probe 5-tuple.
- `raw/organic-dl-spec-router.pcap` — raw organic download capture.
- `raw/organic-ul-spec-modem.pcap` — raw organic upload capture.
- `raw/dl-ef-probe.pcap` — enqueue-side probe-only download capture.
- `raw/dl-ef-probe-source.pcap` — source-side download probe capture used to prove whether the return-leg DL packets were actually EF before the path under test.
- `raw/ul-ef-probe.pcap` — enqueue-side probe-only upload capture.
- `topology/` — read-only topology context (`ip -d link show`, bridge membership, bridge QoS ruleset, and CAKE qdisc state).
- `MANIFEST.md` — run metadata, read-only posture, artifact list, and checksums.

## DSCP to CAKE Tin Mapping

The bridge QoS mapping in `deploy/nftables/bridge-qos.nft` is the reference:

| DSCP | Name | CAKE diffserv4 tin |
| ---- | ---- | ------------------ |
| 46 | EF | Voice |
| 34 | AF41 | Video |
| 8 | CS1 | Bulk |
| 0 | CS0 | BestEffort |

Other AF/CS values follow CAKE diffserv4 semantics, but Phase 225’s pre-registered checks focus on EF survival and aggregate non-BestEffort volume.

## Capture Point Rationale

Production Spectrum uses `allow_wash: true` in `configs/spectrum.yaml`. CAKE wash clears DSCP after tin selection. A post-wash transmit-side capture can therefore falsely show a mark as stripped even when it reached CAKE classification intact.

For that reason, DSCP-02 evidence must observe the DSCP byte pre-wash at the enqueue ingress point. `CAPTURE_POINT` is not accepted as an operator assertion and is not satisfied by topology prose or a hardcoded `-Q in` recipe. It must be backed by `capture-point-proof.txt`, using a falsifiable check such as:

- paired pre/post-wash observation of the same probe 5-tuple where pre-wash DSCP is set and post-wash DSCP is cleared; or
- a concrete qdisc-ordering predicate showing the capture hook is upstream of the CAKE egress wash qdisc.

Until that proof passes, `CAPTURE_POINT=unknown` and `WASH_ORDERING_PROVEN=false`; the affected channel cannot drive a negative DSCP-03 verdict.

## Probe Methodology

EF probe traffic is opt-in with `--probe {ul|dl|both}` and always requires `--probe-target`. The script records `PROBE_5TUPLE`, `PROBE_PROTO`, `PROBE_PORT`, `PROBE_PKTS_CAPTURED`, `EF_PKTS_AT_ENQUEUE`, `EF_SURVIVAL_PCT`, and `EF_SURVIVED`.

- `ul_ef_probe` proves only that a local upload mark reaches `spec-modem`; it is corroborating for this milestone and never closes the DL negative branch or unblocks a DL A/B by itself.
- `dl_ef_probe` is the channel that exercises the CRS/Ruckus/bridge download classification path under test.

Download `STRIPPED` is admissible only when the return-leg DL packets were provably EF before the path under test. A LAN client setting `--tos 0xb8` marks its outbound packets, not automatically the return-path DL packets. The DL result therefore includes independently re-derivable fields:

- `SRC_PROBE_PKTS_TOTAL`
- `SRC_EF_PKTS` / `EF_PKTS_AT_SOURCE`
- `SRC_EF_PCT`
- `SRC_CAPTURE_POINT`
- `SRC_ENQUEUE_5TUPLE_MATCH`
- `DL_SOURCE_EF_PROVEN`

`DL_SOURCE_EF_PROVEN=true` requires at least 100 source-side probe packets, at least 90% source-side EF, matching source/enqueue 5-tuple linkage, and the source-side pcap artifact. If that proof is absent, the DL probe is `unknown` / `degraded`; it is never counted as `STRIPPED`.

## Representative-Load Floor and NEGLIGIBLE Rule

A representative organic window is valid only when the sample floor passes:

- total captured IP packets >= 2000; and
- active seconds >= 30.

Invalid windows are recorded as invalid and cannot drive a negative verdict.

The pre-registered NEGLIGIBLE criterion is two-part: non-BestEffort packets < 1.0% and non-BestEffort bytes < 1.0% where measurable. Both `NONBE_PKT_PCT` and `NONBE_BYTE_PCT` are emitted so Plan 225-03 can apply the full criterion rather than packet share alone.

## Read-Only Posture

The script uses bounded `tcpdump` captures and optional low-rate diagnostic probe traffic to an operator-supplied `--probe-target`. It does not change external gear configuration, CAKE mode, bridge QoS runtime state, or persistent classifier state.

Current production CAKE runs `besteffort`, so per-tin CAKE counters are not used to decide survival. The pre-wash DSCP histogram is the evidence source for whether marks reach the shaper.

## Direction-Split Semantics

The verdict consumes direction-aware evidence. The DL channels (`organic_dl_histogram` and `dl_ef_probe`) are the gating channels for the Spectrum download diffserv question. The UL probe is useful context, but UL alone cannot decide the DL branch.
