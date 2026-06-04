# DSCP-03 Gated Verdict

VERDICT: MARKS_SURVIVE_QUALIFIED

This verdict was computed from the pre-registered `225-RESEARCH.md` DSCP-03 decision logic, evaluated top-to-bottom, and not reverse-fitted to a desired outcome. The branch logic consumes only re-derived raw-evidence predicates; asserted summary flags are recorded for audit but do not decide the branch.

## Branch Result

`MARKS_SURVIVE_QUALIFIED` fired because both DL gating channels are unavailable/unknown in the committed evidence set:

- `organic_dl_histogram` is a GATING channel, but `.planning/phases/225-dscp-survival-trace/evidence/dscp-ingress/dscp-histogram-spec-router-dl.txt`, `sample-quality.txt`, and `capture-point-proof.txt` are not present in the committed evidence directory. Therefore `WINDOW_VALID_DL=false`, `CAPTURE_POINT=unknown`, and `WASH_ORDERING_PROVEN=false` are re-derived for branch purposes.
- `dl_ef_probe` is a GATING channel, but `.planning/phases/225-dscp-survival-trace/evidence/dscp-ingress/dl-ef-probe-result.txt` and `raw/dl-ef-probe-source.pcap` are not present. Therefore `DL_SOURCE_EF_PROVEN=false` is re-derived, the DL probe is `degraded`, and it cannot count as `STRIPPED` even if any asserted flag elsewhere claimed otherwise.

The negative branch (`MARKS_DO_NOT_SURVIVE`) did not fire because it requires BOTH gating DL channels to be valid: a NEGLIGIBLE organic DL histogram (`NONBE_PKT_PCT < 1.0` AND `NONBE_BYTE_PCT < 1.0`) AND a valid stripped DL EF probe (`EF_SURVIVAL_PCT < 10.0`) with `DL_SOURCE_EF_PROVEN=true`. Those predicates are not satisfied by absent/unknown evidence. The positive branch (`MARKS_SURVIVE`) did not fire because there is no valid DL histogram showing `NONBE_PKT_PCT >= 5.0` and no valid DL EF probe showing `EF_SURVIVAL_PCT >= 90.0`.

## Channel Evidence

### bridge_counter_signal

- **Role:** CORROBORATING-ONLY / non-gating.
- **Validity state:** `unknown`.
- **Driving value:** `.planning/phases/225-dscp-survival-trace/evidence/dscp-trace/bridge-mark-counters.txt` is not present in the committed evidence set. `DSCP-TRACE.md` records the expected production semantics: checked-in `ip dscp set ef|af41|cs1` bridge rules carry no explicit `counter` clause, so absent runtime counters map to `COUNTERS_AVAILABLE=false`, `COUNTER_MODE=unavailable`, and `bridge_counter_signal=unknown` when captured.
- **Branch participation:** none. This channel never gates a branch. `bridge_counter_signal=unknown` is the expected benign case and does not force or block any verdict.

### organic_dl_histogram

- **Role:** GATING.
- **Validity state:** `unknown` / invalid for branch purposes.
- **Driving value:** `.planning/phases/225-dscp-survival-trace/evidence/dscp-ingress/dscp-histogram-spec-router-dl.txt` is absent.
- **Packet fraction:** `NONBE_PKT_PCT=unknown`.
- **Byte fraction:** `NONBE_BYTE_PCT=unknown`.
- **Sample quality:** `WINDOW_VALID_DL=false` re-derived because `sample-quality.txt` is absent and the representative-load floor cannot be proven (`TOTAL_IP_PACKETS >= 2000` and `ACTIVE_SECONDS >= 30` are not demonstrated).
- **Capture point:** `CAPTURE_POINT=unknown`.
- **Wash ordering:** asserted `WASH_ORDERING_PROVEN=missing`; re-derived `WASH_ORDERING_PROVEN=false`; `mismatch=false` because no asserted positive value is present.
- **Branch participation:** cannot contribute to `MARKS_DO_NOT_SURVIVE` or `MARKS_SURVIVE` because the gating channel is not valid.

### dl_ef_probe

- **Role:** GATING.
- **Validity state:** `degraded` / unknown for branch purposes.
- **Driving value:** `.planning/phases/225-dscp-survival-trace/evidence/dscp-ingress/dl-ef-probe-result.txt` is absent.
- **Probe packets:** `PROBE_PKTS_CAPTURED=0` re-derived from absent result file.
- **EF at enqueue:** `EF_PKTS_AT_ENQUEUE=0` re-derived from absent result file.
- **Survival percentage:** `EF_SURVIVAL_PCT=unknown`.
- **Source-side EF packets:** `EF_PKTS_AT_SOURCE=0` re-derived from absent result file and absent `raw/dl-ef-probe-source.pcap`.
- **Source-side proof:** asserted `DL_SOURCE_EF_PROVEN=missing`; re-derived `DL_SOURCE_EF_PROVEN=false` because `SRC_PROBE_PKTS_TOTAL >= 100`, `SRC_EF_PCT >= 90`, `SRC_ENQUEUE_5TUPLE_MATCH=true`, and `raw/dl-ef-probe-source.pcap` presence are not all satisfied; `mismatch=false` because no asserted positive value is present.
- **Capture point:** asserted `WASH_ORDERING_PROVEN=missing`; re-derived `WASH_ORDERING_PROVEN=false` from absent `capture-point-proof.txt`; `CAPTURE_POINT=unknown`; `mismatch=false` because no asserted positive value is present.
- **Branch participation:** cannot count as `STRIPPED` for `MARKS_DO_NOT_SURVIVE`; an unproven source-side DL EF leg is never a valid negative. It also cannot count as survived for `MARKS_SURVIVE`.

### ul_ef_probe

- **Role:** CORROBORATING-ONLY / non-gating.
- **Validity state:** `unknown`.
- **Driving value:** `.planning/phases/225-dscp-survival-trace/evidence/dscp-ingress/ul-ef-probe-result.txt` is absent.
- **Probe packets:** `PROBE_PKTS_CAPTURED=0` re-derived from absent result file.
- **EF at enqueue:** `EF_PKTS_AT_ENQUEUE=0` re-derived from absent result file.
- **Survival percentage:** `EF_SURVIVAL_PCT=unknown`.
- **Sample quality flags:** `WINDOW_VALID_UL=false` re-derived from absent `sample-quality.txt`.
- **Branch participation:** none. A UL-only positive would not close the DL branch or unblock the DL A/B; here even the UL corroborating signal is absent.

## Re-derived Predicate Audit

| Predicate | Asserted | Re-derived | Mismatch | Raw basis |
| --- | --- | --- | --- | --- |
| `organic_dl_histogram.WASH_ORDERING_PROVEN` | missing | false | false | `capture-point-proof.txt` absent; no `WASH_PROOF_PASS=true` with paired set/cleared or qdisc-ordering support. |
| `organic_dl_histogram.WINDOW_VALID_DL` | missing | false | false | `sample-quality.txt` absent; packet and active-second floors cannot be proven. |
| `dl_ef_probe.DL_SOURCE_EF_PROVEN` | missing | false | false | `SRC_PROBE_PKTS_TOTAL`, `SRC_EF_PCT`, `SRC_ENQUEUE_5TUPLE_MATCH`, and `raw/dl-ef-probe-source.pcap` proof are absent. |
| `dl_ef_probe.WASH_ORDERING_PROVEN` | missing | false | false | `capture-point-proof.txt` absent; capture point remains `unknown`. |

## Consequence for Phases 226-228

Phase 226 is **BLOCKED by default**. `MARKS_SURVIVE_QUALIFIED` is a HOLD state, not "marks survive". It neither unblocks Phase 226, which touches production config, nor closes the milestone negative.

REQUIRED operator decision before Phase 226 may proceed:

1. collect better evidence and re-run Phase 225 capture/verdict to reach a clear `MARKS_SURVIVE` or `MARKS_DO_NOT_SURVIVE`; or
2. record an explicit operator override to proceed-with-caveat, deferring the volume question to Phase 226 `GATE-01`.

The verdict does not take that override automatically.

## Read-only Boundary

This verdict did not mutate external network gear, CAKE mode, nftables runtime state, persistent classifier state, controller-path source, or ATT config. SAFE-13 boundary evidence is recorded separately in `.planning/phases/225-dscp-survival-trace/evidence/safe13-boundary-check.json`.
