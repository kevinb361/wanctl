# Phase 238: RTT-Provenance Verification (Read-Only Entry Gate) - Research

**Researched:** 2026-06-14
**Domain:** Live RTT provenance tracing, policy-routing egress proof, read-only evidence capture (no source/prod mutation)
**Confidence:** HIGH (all code-path claims verified against source with file:line citations; live host values to be confirmed by operator at execution)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions (HONOR verbatim — do not re-litigate)
- **D-01:** Evidence-first. Phase produces provenance map **+ an A-vs-B recommendation with evidence**; the operator (Kevin) makes the binding A/B selection at execution/verification. CONTEXT captures decision *criteria*, not a verdict.
- **D-02:** A/B leaning is genuinely undecided. Present **both** interpretations honestly, including why each is or isn't viable.
- **D-03:** Decision rubric = **maximize A/B evidence fidelity** — favor whichever target yields the most trustworthy icmplib-vs-fping comparison on real traffic for Phase 245. Blast-radius / SAFE-17 cost is documented as a tradeoff, not the primary selector.
- **D-04:** Verified live steering RTT chain = `run_cycle → _measure_current_rtt_with_retry → measure_current_rtt → load_live_rtt`, reading autorate `/health` `measurement.raw_rtt_ms`. Steering's own `RTTMeasurement` (icmplib) is constructed but never called. Prod `raw_rtt_ms` produced by deployed `cake-autorate-{wan}-state-bridge` binary. **(Confirmed — see Code-Path Trace; one refinement noted below.)**
- **D-05:** Single phase-dir evidence artifact: `238-*/PROVENANCE-MAP.md` (NOT a `docs/` runbook).
- **D-06:** Artifact embeds (a) live `/health` capture, (b) verified code-path trace, (c) deployed bridge identity + repo-vs-prod reconciliation.
- **D-07:** fping egress proof covers **BOTH WANs** (Spectrum + ATT): `ip route get <reflector> from <source_ip>` per WAN + host `ip rule` table.
- **D-08:** Capture via committed read-only proof script `scripts/phase238-egress-proof.sh`; stdout → evidence artifact. Reproducible, re-runnable, not ad-hoc paste.
- **D-09:** SAFE-17 satisfied via a **LIGHTWEIGHT controller-path git-diff assertion** (empty controller-path diff + explicit no-mutation statement). The FULL fail-closed SAFE-17 verifier + narrowed allowlist are authored in **Phase 239**, NOT here.

### Claude's Discretion
- Exact filenames, section structure of `PROVENANCE-MAP.md`, and shape of egress-proof script output — planner/executor's discretion, as long as D-05..D-08 evidence is captured.
- How "live capture" is obtained read-only: operator runs `! curl …` / `! ssh …` at the keyboard, OR the committed script fetches `/health` itself. Privileged/credentialed reads should be handed to the operator as `! <command>` rather than escalated (consistent with the credential-reads memory).

### Deferred Ideas (OUT OF SCOPE for Phase 238)
- **NATIVE-AB-01** — stand up native autorate (makes interpretation B fully wanctl-owned). Deferred out of v1.53 entirely.
- **docs/RTT-PROVENANCE.md** durable runbook — deferred; evidence stays in phase dir.
- **Full SAFE-17 fail-closed verifier + narrowed allowlist** — Phase 239 scope.
- Any backend code: `RttBackend` Protocol (239), config/validator (240), fping backend (241), factory/fallback (242), benchmark (243), health wiring (244), live A/B (245), flip (246).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| PROV-01 | Documented map of which producer feeds live steering RTT (state bridge / autorate `/health` `measurement.raw_rtt_ms` vs wanctl `RTTMeasurement`), captured read-only, zero mutation. | Full code-path trace below (daemon.py:1000-1024, :1755-1767, :2080-2089, :2554) + bridge producer identity (deploy/scripts/cake-autorate-{wan}-state-bridge:234-271). **Key refinement: prod `raw_rtt_ms` is carried-forward `ewma.load_rtt`, NOT a live ICMP sample.** |
| PROV-02 | A/B target interpretation (A = revive steering's own pinger; B = evaluate at autorate/bridge producer) selected + recorded with evidence before any backend code. | A/B viability analysis below grounds the recommendation in the fidelity rubric (D-03) + the bridge `load_rtt` finding. |
| PROV-03 | Confirm `fping -S <source_ip>` egresses intended WAN under current `ip rule` policy routing via `ip route get <reflector> from <source_ip>`. | Resolved source IPs + reflectors per WAN (config keys below); reusable egress-proof script skeleton from phase231/phase225. |
| SAFE-17 | Controller-path changes within narrowed v1.53 allowlist; no out-of-allowlist drift. Phase 238: lightweight controller-path git-diff assertion (no source changes). | Existing SAFE boundary-check skeleton (phase237-safe16-boundary-check.sh) provides the exact controller-path target list + anchor-diff pattern to clone lightly. |
</phase_requirements>

## Summary

Phase 238 is a **read-only entry gate**. It produces three artifacts with zero source changes and zero production mutation: a provenance map (PROV-01), an evidence-backed A/B recommendation that the operator ratifies (PROV-02), and a both-WANs fping-egress proof (PROV-03), plus a lightweight SAFE-17 boundary assertion (no controller-path diff).

The core technical work is **verification**, not construction. The D-04 code-path claim is **confirmed**: steering's live RTT flows `run_cycle → _measure_current_rtt_with_retry → measure_current_rtt → baseline_loader.load_live_rtt()`, which reads the autorate `/health` `measurement.raw_rtt_ms`. The `RTTMeasurement` (icmplib pinger) constructed in `_create_steering_components` (`daemon.py:2554`) is stored as `self.rtt_measurement` (`:1137`) and **never invoked anywhere** — verified by exhaustive grep. In production both WANs run cake-autorate external mode, so `raw_rtt_ms` is emitted by the deployed `cake-autorate-{wan}-state-bridge` binary.

**One refinement to D-04 that is load-bearing for the A/B fidelity rubric (D-03):** the bridge does NOT parse a live ICMP/RTT value out of the cake-autorate log. `rates_from_row` extracts only DL/UL rate + status; the bridge's `health_payload()` sets `raw_rtt_ms = ewma.load_rtt` (`bridge:250`), and `load_rtt` is carried forward from the previous state file via `old_rtt()` (`bridge:96-104`), defaulting to a **static constant** `DEFAULT_BASELINE_RTT` (~22.5ms). So in the current external cake-autorate topology, the value steering treats as "live RTT" is effectively a near-static carried-forward baseline, not a fresh path measurement. This is the crux PROV-02 must surface: interpretation B (evaluate at the bridge producer) cannot produce a trustworthy icmplib-vs-fping comparison on real traffic because the bridge has no real per-cycle RTT to compare against, and the true upstream RTT lives in **bash** cake-autorate that the wanctl `RttBackend` seam cannot reach.

**Primary recommendation:** Plan three tasks — (1) author `PROVENANCE-MAP.md` embedding the verified trace + a live `/health` capture; (2) author + run `scripts/phase238-egress-proof.sh` (both WANs, modeled on `phase231-migration-held.sh`); (3) author a lightweight controller-path git-diff assertion (clone the target list from `phase237-safe16-boundary-check.sh`, no fail-closed machinery). The A/B recommendation that the map should present to the operator: **lean interpretation A** (revive steering's own pinger as the live RTT source) on fidelity grounds, because it is the only v1.53-reachable path that produces a genuine icmplib-vs-fping comparison — with the caveat that A requires wiring `source_ip` into the currently-source-less steering `RTTMeasurement` construction (`daemon.py:2554`).

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Provenance evidence (PROV-01) | Phase-dir artifact (`238-*/PROVENANCE-MAP.md`) | — | Versioned phase evidence; consistent with 212/222/225 read-only milestones (D-05). |
| Live RTT production (prod reality) | Deployed bridge binary (`/usr/local/sbin/cake-autorate-{wan}-state-bridge`) | upstream **bash** cake-autorate (out of wanctl reach) | External cake-autorate mode is the active deployment; bridge is the `/health` producer. |
| Live RTT consumption | wanctl steering daemon (`src/wanctl/steering/daemon.py`) | — | `load_live_rtt()` reads `/health measurement.raw_rtt_ms`. |
| Egress proof (PROV-03) | Read-only script run on live cake-shaper host (`10.10.110.223`) | operator `! ssh`/`! curl` for any privileged read | `ip route get … from …` + `ip rule` are host-local routing-policy facts. |
| SAFE-17 boundary (SC-4) | Local git inspection (no worktree mutation) | — | Lightweight diff assertion; full verifier deferred to 239 (D-09). |

## Standard Stack

No new libraries. This phase only **reads** existing code, config, and live host state. Tools used by the evidence/proof scripts (all already present in the repo's proof-script lineage):

| Tool | Purpose | Already used by |
|------|---------|-----------------|
| `bash` (`set -euo pipefail`) | Proof-script harness | phase225, phase231, phase237 |
| `ssh -n -o BatchMode=yes -o ConnectTimeout=N` | Read-only remote capture | phase231 (`ssh_readonly`) |
| `python3` (stdlib `json`) | JSON assembly / parse from shell | phase231, phase237 |
| `ip route get`, `ip rule` | Policy-routing egress proof (read-only) | NEW for 238 (read-only kernel queries) |
| `curl -fsS --max-time N` | `/health` capture | phase231 (`health_check`) |
| `git ls-tree / diff --numstat / hash-object / status --porcelain` | Controller-path boundary assertion | phase237-safe16, check-safe07 |

**No package installs. No `npm`/`pip`/`cargo`. Package Legitimacy Audit: N/A (zero external packages introduced).**

## Code-Path Trace (PROV-01) — VERIFIED

All citations are `src/wanctl/...` unless noted. Verified by direct read on 2026-06-14.

### Live steering RTT consumption chain (confirms D-04)
1. `steering/daemon.py:2080-2089` — `run_cycle()` RTT subsystem: `current_rtt = self._measure_current_rtt_with_retry()` inside `PerfTimer("steering_rtt_measurement")`. If `None`, cycle is skipped. `[VERIFIED: source read]`
2. `steering/daemon.py:1769-1815` — `_measure_current_rtt_with_retry()` wraps `self.measure_current_rtt` via `measure_with_retry(...)` with a `fallback_to_history()` (source label `history_fallback`). `[VERIFIED]`
3. `steering/daemon.py:1755-1767` — `measure_current_rtt()`: tries `self.baseline_loader.load_live_rtt()` (label `autorate_health`), then `load_live_irtt_rtt()` (label `autorate_irtt`), else `_current_rtt_source = "unavailable"`. `[VERIFIED]`
4. `steering/daemon.py:1000-1024` — `load_live_rtt()` (on `BaselineLoader`): reads `target_wan["measurement"]`, requires `available is True`, reads `raw_rtt_ms` + `staleness_sec`, rejects if `staleness > STALE_AUTORATE_MEASUREMENT_THRESHOLD_SECONDS`. `[VERIFIED]`
5. `steering/daemon.py:1052-1076` — `_load_target_wan_health()`: `urllib.request.urlopen(self.config.primary_health_url, timeout=0.2)`, selects the WAN entry whose `name == self.config.primary_wan`. `[VERIFIED]`

### Dead `RTTMeasurement` (confirms "constructed but never called")
- `steering/daemon.py:2554-2559` — `_create_steering_components()` constructs `RTTMeasurement(logger, timeout_ping=config.timeout_ping, aggregation_strategy=MEDIAN, log_sample_stats=False)`. **Note: no `source_ip=` argument is passed.** `[VERIFIED]`
- `steering/daemon.py:1137` — stored as `self.rtt_measurement = rtt_measurement`. `[VERIFIED]`
- **Grep confirms `self.rtt_measurement` appears exactly once (the assignment at :1137) and is never invoked** (no `.ping_host`/`.measure*` call anywhere in `daemon.py`). The only other `rtt_measurement` mentions are the import (:63), constructor plumbing (:1130, :2561, :2642, :2671), a comment (:923), and the unrelated PerfTimer label string `"steering_rtt_measurement"` (:2051, :2081). `[VERIFIED: grep -n "rtt_measurement" + grep for invocation]`
- `rtt_measurement.py:139-172` — `RTTMeasurement.__init__` accepts `source_ip: str | None = None`. `rtt_measurement.py:199-207` — `ping_host()` passes `source=self.source_ip` to `icmplib.ping(...)`. This `source=` is the **`-S`-equivalent**; the dead constructor leaves it `None`, so even if revived as-is it would NOT bind a WAN source IP. `[VERIFIED]`

### Production producer of `raw_rtt_ms` (confirms D-06c, with a load-bearing refinement)
Both WANs run **external cake-autorate mode** (MEMORY: "Both WANs on cake-autorate", wanctl@ disabled since 2026-06-08). The `/health` `raw_rtt_ms` is produced by the deployed bridge:
- `deploy/systemd/cake-autorate-spectrum-state-bridge.service` → `ExecStart=/usr/local/sbin/cake-autorate-spectrum-state-bridge`. Same for ATT. `[VERIFIED: source read]`
- Repo source of that binary: `deploy/scripts/cake-autorate-{spectrum,att}-state-bridge` (Python, 338 lines, shebang `#!/usr/bin/env python3`). **Repo-vs-prod note:** the repo file is the source-of-truth, but the *running* artifact is the copy under `/usr/local/sbin/` — verify the deployed copy matches (sha/byte compare) during capture; do not assume repo == prod. `[VERIFIED: repo read; live compare is an operator step]`
- `bridge:234-247` — degraded path emits `measurement: {available: False, raw_rtt_ms: None, staleness_sec: None}`. `[VERIFIED]`
- `bridge:249-271` — healthy path: `raw_rtt = ewma.get("load_rtt")`; `available = isinstance(raw_rtt, (int,float)) and age <= MAX_STATE_AGE_SECONDS`; `measurement: {available, raw_rtt_ms: float(raw_rtt)|None, staleness_sec: age}`. `[VERIFIED]`

**LOAD-BEARING REFINEMENT (crux of PROV-02):** the bridge's `raw_rtt_ms` is **not a fresh path RTT**.
- `bridge:33` — `LINE_RE = ^(SUMMARY|LOAD); ` and `bridge:65` — `rates_from_row()` returns `(dl_rate, ul_rate, dl_status, ul_status)` only. **No RTT is parsed from the cake-autorate log.** `[VERIFIED]`
- `bridge:191-218` — `build_state()` sets `ewma: {baseline_rtt: baseline, load_rtt: load}` where `baseline, load = old_rtt()` (i.e. carried forward from the *previous* state file). `[VERIFIED]`
- `bridge:96-104` — `old_rtt()` reads `ewma.load_rtt`/`baseline_rtt` from the existing state JSON, defaulting both to `DEFAULT_BASELINE_RTT` (`bridge:23`, env `WANCTL_EXTERNAL_BASELINE_RTT`, default `22.535852814520855`). `[VERIFIED]`

Therefore in the current topology, steering's "live RTT" is a near-static carried-forward baseline constant, and the **real** RTT signal lives in upstream **bash** cake-autorate (its own pinger), which the wanctl `RttBackend` Python seam cannot touch. The provenance map MUST state this prominently.

### Native autorate producer (interpretation B's wanctl-owned variant — NOT running)
- `autorate_continuous.py` constructs `RTTMeasurement` in `_create_wan_components` (CONTEXT cites :120-167) — this is the wanctl-owned producer that would emit a real `raw_rtt_ms`, but native autorate is **dormant** in prod (NATIVE-AB-01 deferred). So interpretation B's only genuinely-wanctl-owned form is out of v1.53 scope. `[CITED: CONTEXT D-04; not independently re-read this session — flag LOW for exact line numbers]`

## `/health` `measurement` Block Shape (PROV-01 capture target)

Two producers emit a `measurement` block; the provenance map should capture the **prod (bridge)** shape and note the wanctl health_check.py shape for contrast.

### Prod (deployed bridge) — what steering actually reads today
From `deploy/scripts/cake-autorate-{wan}-state-bridge:267-271`:
```json
{
  "wans": [{
    "name": "spectrum",
    "measurement": { "available": true, "raw_rtt_ms": 22.54, "staleness_sec": 0.7 },
    "irtt": { "available": false },
    "download": { "state": "GREEN", "current_rate_mbps": …, "qdisc_bandwidth": "…Mbit" },
    "upload":   { "state": "GREEN", "current_rate_mbps": …, "qdisc_bandwidth": "…Mbit" }
  }]
}
```
`load_live_rtt()` consumes exactly `measurement.{available, raw_rtt_ms, staleness_sec}` — the only three fields that matter for steering. `[VERIFIED: daemon.py:1006-1024 + bridge:267-271]`

### wanctl `health_check.py` (native/wanctl@ producer — for contrast, NOT live in prod)
`health_check.py:493-524` `_build_measurement_section` emits a richer block: `available, raw_rtt_ms, staleness_sec, active_reflector_hosts, successful_reflector_hosts, state, successful_count, stale`. Phase 244 (HEALTH-01) must byte-preserve `raw_rtt_ms/available/staleness_sec`. `[VERIFIED: source read]`

## Config Keys — Source IPs & Reflectors (PROV-03 inputs)

Resolved per WAN. The egress proof must use these exact values. `[VERIFIED: config read]`

| WAN | `ping_source_ip` | `ping_hosts` (reflectors) | `/health` endpoint | Config file |
|-----|------------------|--------------------------|--------------------|-------------|
| Spectrum (primary) | **absent** → `None` → egresses via default route (host primary IP `10.10.110.223`) | `["1.1.1.1", "9.9.9.9", "208.67.222.222"]` | `10.10.110.223:9101` | `configs/spectrum.yaml:8-10, :133` |
| ATT (alternate) | `10.10.110.227` (routes via MikroTik `FORCE_OUT_ATT`) | `["1.1.1.1", "8.8.8.8", "151.101.1.57"]` | `10.10.110.227:9101` | `configs/att.yaml:9, :13-14, :88` |

Key provenance facts:
- `ping_source_ip` is loaded at `autorate_config.py:643` from top-level YAML key `ping_source_ip` (default `None`). `[VERIFIED]`
- `ping_hosts` is loaded at `autorate_config.py:617` from `continuous_monitoring.ping_hosts` (required list, `autorate_config.py:349`). `[VERIFIED]`
- Steering's own (dead) RTT block: `configs/steering.yaml:37-40` `measurement.ping_host: 1.1.1.1`, `ping_count: 3` — feeds only the unused `RTTMeasurement`; document as dead config. `[VERIFIED]`
- **Spectrum has no source IP**: its egress proof is `ip route get <reflector>` (default-route path); for completeness also `ip route get <reflector> from 10.10.110.223`. ATT's is `ip route get <reflector> from 10.10.110.227` and must show the ATT egress path. `[VERIFIED config; live routing result is the operator-run proof]`
- ATT IRTT reflector (`104.200.21.31:2112`, `configs/att.yaml`) is the Dallas Linode netperf host (MEMORY) — not an fping reflector; note but don't proof it here.

## Egress-Proof Script Skeleton (PROV-03, D-07/D-08)

Model `scripts/phase238-egress-proof.sh` on `scripts/phase231-migration-held.sh` (closest fit — same SSH-to-cake-shaper, per-WAN TARGETS array, python3-JSON, mktemp+trap, exit-code verdict). Reusable structure extracted:

```bash
#!/usr/bin/env bash
set -euo pipefail
# Read-only. Proves fping -S <source_ip> egress per WAN under live ip rule policy.

# Both WANs SSH to the SAME host (cake-shaper). source_ip differs per WAN.
TARGETS=(
  "kevin@10.10.110.223|spectrum|<none>|1.1.1.1 9.9.9.9 208.67.222.222"
  "kevin@10.10.110.223|att|10.10.110.227|1.1.1.1 8.8.8.8 151.101.1.57"
)
SSH_OPTS=(-o ConnectTimeout=10 -o BatchMode=yes)
ssh_readonly() { ssh -n "${SSH_OPTS[@]}" "$1" "$2"; }   # phase231 pattern

# Per WAN, per reflector: ip route get <reflector> [from <source_ip>]
#   spectrum: `ip route get 1.1.1.1`            (default route; also `... from 10.10.110.223`)
#   att:      `ip route get 1.1.1.1 from 10.10.110.227`
# Once per host: `ip rule`  (policy table context, D-07)
# Assemble JSON via `python3 - <<'PY'`; write stdout to evidence; exit 0 iff every
# resolved egress dev matches the intended WAN interface.
```

Conventions to carry over from phase231: `usage()` heredoc, `require_command python3/ssh/ip`, `--wan spectrum|att|all` + `--json` flags, JSON-only mode + human summary mode, `status_json`/`json_string` helpers, `mktemp -d` + `trap 'rm -rf' EXIT`. **Read-only posture banner** in the header comment (copy phase237's "does not modify worktree, index, refs, external gear, CAKE mode, or controller source"). `ip route get` and `ip rule` are pure kernel queries — no mutation. `[VERIFIED: phase231/phase225/phase237 read]`

**Discretion note (D-08 + credential memory):** `ip route get`/`ip rule` on the cake-shaper may not need sudo; `/health` curl does not. If any read trips a guardrail, hand Kevin a `! ssh cake-shaper '…'` rather than escalating. The script can EITHER run via SSH itself OR emit the exact `! ssh …` commands for the operator to paste — planner's discretion.

## SAFE-17 Lightweight Boundary Assertion (SC-4, D-09)

Phase 238 has **no source changes by definition**. Prove it with an empty controller-path git diff + explicit no-mutation statement. **Clone the controller-path target list and anchor-diff pattern from `scripts/phase237-safe16-boundary-check.sh`; do NOT build the fail-closed verifier or narrowed allowlist (Phase 239).**

Controller-path target set (from `phase237-safe16-boundary-check.sh:67-75`) — these are the "controller-path" files SAFE counts: `[VERIFIED: source read]`
```
src/wanctl/wan_controller.py
src/wanctl/wan_controller_state.py
src/wanctl/queue_controller.py
src/wanctl/cake_signal.py
src/wanctl/alert_engine.py
src/wanctl/fusion_healer.py
src/wanctl/backends/
```
Pattern to reuse (lightly): `git rev-parse <anchor>`, `git diff --numstat <anchor> HEAD -- <path>`, `git diff --numstat --staged -- <path>`, `git status --porcelain -- <path>`, write a JSON record, pass iff committed+staged+dirty are all clean for the controller paths.

**Anchor:** latest milestone tag is `v1.52` (`git tag` sorted by creatordate). Use `--anchor v1.52` as the default (v1.53 has no tag yet). `[VERIFIED: git tag]`

**Scope boundary for 238:** the assertion only needs to prove the controller-path set is byte-unchanged vs anchor (lightweight). It does NOT need: per-file sha256 hashing of `backends/`, fail-closed exit on add/delete, the att.yaml special-case, or the narrowed v1.53 allowlist — all of which arrive in Phase 239's full verifier. Keep it minimal.

## A/B Interpretation Analysis (PROV-02) — Evidence for the operator's decision

Present BOTH honestly (D-02), recommend on the fidelity rubric (D-03). Operator ratifies (D-01).

### Interpretation A — revive steering's own pinger as the live RTT source
- **Reachability:** In v1.53 scope. The `RttBackend` seam (Phase 239) sits behind `RTTMeasurement` (`rtt_measurement.py`), which steering already constructs (`daemon.py:2554`). Reviving it means actually *calling* it in the cycle and feeding its output where `load_live_rtt()` output goes today.
- **Fidelity (rubric-positive):** Produces a genuine per-cycle ICMP RTT against real reflectors → a real icmplib-vs-fping comparison on live traffic for Phase 245. **This is the only v1.53-reachable target that yields a trustworthy A/B.**
- **Cost / blast radius (documented tradeoff, not selector):** Higher SAFE-17 touch — steering's RTT consumption path changes from "read `/health`" to "call backend." Also requires wiring `source_ip` into the currently source-less construction (`daemon.py:2554` passes no `source_ip`; `rtt_measurement.py:206` needs it for `-S`-equivalent egress binding). Steering's `primary_wan = spectrum` has no `ping_source_ip` (default route OK); ATT would need `10.10.110.227`.
- **Risk:** Touches the live steering control path (CLAUDE.md: stability > safety). Mitigated by the byte-identical icmplib-default requirement (SEAM-02) and the A/B rollback anchor (AB-01).

### Interpretation B — evaluate at the autorate/bridge producer
- **Reachability:** Largely OUT of v1.53. The live producer is the **bash** cake-autorate pinger (unreachable by the Python seam). The wanctl-owned producer (`autorate_continuous.py` `RTTMeasurement`) is dormant (NATIVE-AB-01 deferred).
- **Fidelity (rubric-negative):** The bridge's `raw_rtt_ms` is carried-forward `ewma.load_rtt` / a static `DEFAULT_BASELINE_RTT` constant (`bridge:96-104, :250`), NOT a fresh measurement. There is no real per-cycle RTT at the bridge to compare backends against → an icmplib-vs-fping A/B here would compare nothing meaningful. Standing up native autorate to fix this is explicitly deferred.
- **Cost:** Lower steering-path blast radius, but only because it doesn't actually exercise a real RTT path.

### Recommended lean (for operator ratification): **Interpretation A**
On the fidelity rubric (D-03), A is the only target that produces a trustworthy real-traffic icmplib-vs-fping verdict within v1.53 scope, since B's live value is a static baseline and B's real signal lives in unreachable bash. Document A's higher SAFE-17 cost + the `source_ip` wiring requirement as the accepted tradeoff. **This is a recommendation with evidence, NOT a verdict — Kevin selects at execution (D-01).**

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Read-only proof harness | A bespoke script from scratch | Clone `phase231-migration-held.sh` structure | Proven SSH/JSON/exit-code pattern, matches prior-phase evidence shape. |
| Controller-path diff assertion | A new SAFE verifier | Lightweight clone of `phase237-safe16-boundary-check.sh` target list + diff pattern | The full verifier is Phase 239's job (D-09); reusing the target list keeps the "controller-path" definition consistent. |
| `/health` parse | Custom JSON walker | `curl -fsS \| python3 -c 'json.load…'` (phase231 `health_check`) | Already the house pattern. |

**Key insight:** every deliverable here has a direct prior-phase template. Phase 238 is assembly + verification, not invention.

## Common Pitfalls

### Pitfall 1: Treating bridge `raw_rtt_ms` as a live measurement
**What goes wrong:** Concluding interpretation B is viable because `/health` shows a plausible `raw_rtt_ms`.
**Root cause:** The value is carried-forward `ewma.load_rtt` / static `DEFAULT_BASELINE_RTT` (`bridge:96-104,:250`), not a fresh sample.
**Avoid:** State this explicitly in the map; it is the decisive PROV-02 evidence.
**Warning sign:** `raw_rtt_ms` barely changes across captures and sits near ~22.5ms.

### Pitfall 2: Assuming repo == prod for the bridge
**What goes wrong:** Documenting the repo `deploy/scripts/...` file as "the live producer" without confirming the deployed `/usr/local/sbin/...` copy matches.
**Avoid:** Capture/compare the deployed copy (operator `! ssh cake-shaper 'sha256sum /usr/local/sbin/cake-autorate-spectrum-state-bridge'` vs repo). Both-WANs-on-cake-autorate memory warns repo may lag prod.

### Pitfall 3: Forgetting Spectrum has no `ping_source_ip`
**What goes wrong:** Egress proof tries `ip route get <reflector> from <spectrum_source_ip>` with a nonexistent IP.
**Avoid:** Spectrum proof is default-route (`ip route get <reflector>`); only ATT uses `from 10.10.110.227`.

### Pitfall 4: Accidentally scoping in Phase 239 machinery
**What goes wrong:** Building the fail-closed SAFE-17 verifier / narrowed allowlist here.
**Avoid:** D-09 is explicit — lightweight assertion only. Resist gold-plating.

### Pitfall 5: Mutating prod during "read-only" capture
**What goes wrong:** Using a command that writes (e.g. running cake-autorate, restarting a unit, an `ip rule add`).
**Avoid:** Only `ip route get`, `ip rule` (list), `curl /health`, `sha256sum`, `git` read ops. Header banner + `set -euo pipefail`. No sudo-write, no unit control.

## Runtime State Inventory

> Phase 238 is read-only/evidence — it changes no stored data, config, OS state, secrets, or build artifacts. Inventory is of what the map must *read*, not mutate.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | `/var/lib/wanctl/{spectrum,att}_state.json` (bridge-written; source of `load_rtt`) | Read-only capture for provenance; no migration. |
| Live service config | Deployed `/usr/local/sbin/cake-autorate-{wan}-state-bridge`; `cake-autorate-{wan}-state-bridge.service`; `steering.service`; bash cake-autorate at `configs/cake-autorate/config.{wan}.sh` | Confirm deployed bridge matches repo (read-only sha compare). |
| OS-registered state | systemd units (read-only `systemctl status` / `journalctl` only) | None — no re-registration. |
| Secrets/env vars | `WANCTL_EXTERNAL_BASELINE_RTT` (bridge default baseline); `${ROUTER_PASSWORD}` (unrelated) | None — note baseline env exists; do not change. |
| Build artifacts | `deploy/scripts/__pycache__/...state-bridge*.pyc` (stale; cosmetic) | None — not in controller path. |

**Verified explicitly:** Phase 238 writes **no** source files, **no** prod state, **no** config. The only files created are phase-dir evidence + the two committed scripts (`scripts/phase238-egress-proof.sh` + the SAFE-17 assertion script) — neither is a controller-path file, so SAFE-17 holds.

## Code Examples

### Provenance code-path one-liner verification (read-only, local)
```bash
# Confirm RTTMeasurement is constructed but never invoked:
grep -n "rtt_measurement" src/wanctl/steering/daemon.py        # assignment at :1137, construction at :2554; no .ping_host/.measure call
# Confirm load_live_rtt reads the bridge measurement block:
sed -n '1000,1024p' src/wanctl/steering/daemon.py
```

### Egress proof (read-only kernel query) — the core PROV-03 operation
```bash
# ATT (source-bound):  expect egress dev/path toward ATT (FORCE_OUT_ATT)
ssh -n cake-shaper "ip route get 1.1.1.1 from 10.10.110.227"
# Spectrum (default route):
ssh -n cake-shaper "ip route get 1.1.1.1"
# Policy table context (D-07):
ssh -n cake-shaper "ip rule"
```

### Live `/health` capture (read-only) — the PROV-01 measurement-block evidence
```bash
ssh -n cake-shaper "curl -fsS --max-time 5 http://10.10.110.223:9101/health" | python3 -m json.tool   # Spectrum
ssh -n cake-shaper "curl -fsS --max-time 5 http://10.10.110.227:9101/health" | python3 -m json.tool   # ATT
```

### SAFE-17 lightweight assertion core (read-only git)
```bash
git diff --numstat v1.52 HEAD -- src/wanctl/wan_controller.py src/wanctl/queue_controller.py \
  src/wanctl/cake_signal.py src/wanctl/wan_controller_state.py src/wanctl/alert_engine.py \
  src/wanctl/fusion_healer.py src/wanctl/backends/   # expect EMPTY
git status --porcelain -- <same paths>                # expect EMPTY
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| wanctl@ mode: native autorate emits live ICMP `raw_rtt_ms` | External cake-autorate mode: bash autorate shapes; bridge surfaces carried-forward `load_rtt` as `raw_rtt_ms` | wanctl@ disabled 2026-06-08 (MEMORY) | The "live RTT" steering reads is no longer a fresh wanctl ICMP sample — central to PROV-02. |
| SAFE-07..16 zero-diff streak | SAFE-17 narrowed allowlist (controller path opens by design) | v1.53 (this milestone) | Phase 238 is still zero-diff; the streak ends in 239+. |

**Deprecated/dead in this topology:**
- Steering `RTTMeasurement` (icmplib) — constructed, never called (`daemon.py:2554`/`:1137`).
- `configs/steering.yaml:37-40` `measurement.ping_host`/`ping_count` — feed only the dead pinger.

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | Deployed `/usr/local/sbin/cake-autorate-{wan}-state-bridge` is byte-identical to repo `deploy/scripts/...` | Code-Path Trace / Pitfall 2 | If prod differs, the documented `raw_rtt_ms` derivation may be wrong. **Mitigation: operator sha-compare during capture (already a planned step).** |
| A2 | `autorate_continuous.py` `RTTMeasurement` construction is at :120-167 | A/B Interpretation B | Line numbers cited from CONTEXT, not re-read this session. Low risk (existence is the point, not exact lines). |
| A3 | cake-shaper SSH alias / `kevin@10.10.110.223` reachable and `ip`/`curl` available read-only | Egress proof | If sudo needed, hand operator `! ssh …` (credential memory). |
| A4 | Live `raw_rtt_ms` will read ~22.5ms (static baseline) at capture time | Pitfall 1 | If autorate writes a real load_rtt that drifts, the "static" framing softens — but the code path (no log RTT parse) still proves B's non-fidelity. |

## Open Questions

1. **Does the deployed bridge match the repo copy?**
   - Known: repo source exists; ExecStart points at `/usr/local/sbin/`.
   - Unclear: whether prod was redeployed after the last repo edit.
   - Recommendation: operator `! ssh cake-shaper 'sha256sum /usr/local/sbin/cake-autorate-{spectrum,att}-state-bridge'`; diff vs `sha256sum deploy/scripts/...`. Record in map.

2. **For interpretation A, does reviving the pinger require a `source_ip` config addition for steering?**
   - Known: `daemon.py:2554` constructs `RTTMeasurement` with no `source_ip`; ATT needs `10.10.110.227`.
   - Recommendation: flag as a Phase 239/241 design input in the map; not solved here.

## Environment Availability

> Read-only proof depends on standard tooling on the live cake-shaper host.

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `ip` (iproute2) | PROV-03 egress proof | expected ✓ (live host) | — | Operator runs `! ssh` manually |
| `curl` | `/health` capture | expected ✓ | — | `python3 -c urllib` |
| `python3` | JSON assembly | ✓ (repo proof-script lineage) | 3.11+ | — |
| `git` | SAFE-17 assertion | ✓ | — | — |
| `ssh` to cake-shaper (`10.10.110.223`) | All live captures | operator-confirmed | — | Operator pastes `! <cmd>` output |
| `slopcheck` | Package audit | N/A | — | No external packages introduced |

**Missing dependencies with no fallback:** none identified (all live-host reads have an operator `! <cmd>` fallback per the credential memory).

## Validation Architecture

> nyquist_validation default-enabled (no explicit `false` found). Phase 238 introduces NO production source code, so validation is **artifact/behavioral**, not pytest-on-controller.

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (repo standard) — but NOT the validation surface for this phase |
| Config file | `pyproject.toml` (repo) |
| Quick run command | `.venv/bin/pytest -o addopts='' tests/test_health_check.py -q` (only if touching nothing — sanity) |
| Full suite command | `.venv/bin/pytest tests/ -q` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| PROV-01 | Provenance map embeds verified trace + live `/health` capture | artifact review (manual) | inspect `238-*/PROVENANCE-MAP.md` | ❌ artifact authored in phase |
| PROV-02 | A/B recommendation present with evidence; operator ratification recorded | artifact review (manual) | inspect map A/B section | ❌ authored in phase |
| PROV-03 | `scripts/phase238-egress-proof.sh` runs read-only, both WANs, correct egress | smoke (script self-test) | `scripts/phase238-egress-proof.sh --json` (operator on live host) | ❌ script authored in phase |
| SAFE-17 | Controller-path byte-unchanged vs `v1.52` | automated git assertion | new lightweight assertion script (exit 0 = clean) | ❌ script authored in phase |

### Sampling Rate
- **Per task commit:** controller-path git-diff assertion (must stay empty).
- **Per phase gate:** egress-proof script exits 0 for both WANs; provenance map embeds all D-06 evidence; SAFE-17 assertion passes; `git status` shows only phase-dir + the two new scripts changed.

### Wave 0 Gaps
- [ ] `scripts/phase238-egress-proof.sh` — covers PROV-03 (model on `phase231-migration-held.sh`)
- [ ] SAFE-17 lightweight assertion script (e.g. `scripts/phase238-safe17-boundary-check.sh`) — covers SAFE-17 (lightweight clone of `phase237-safe16-boundary-check.sh`)
- [ ] `238-*/PROVENANCE-MAP.md` — covers PROV-01/PROV-02 (no test framework; artifact-review gate)
- Framework install: none (no production code under test).

## Security Domain

> `security_enforcement` default-enabled. Phase 238 is read-only with no new attack surface; controls below are about **not mutating prod** and not leaking infra details.

### Applicable ASVS Categories
| ASVS Category | Applies | Standard Control |
|---------------|---------|-----------------|
| V2 Authentication | no | Reuses existing SSH-key auth to cake-shaper; no new auth. |
| V5 Input Validation | yes (light) | Proof scripts: validate `--wan` arg (phase231 `validate_wan` pattern); never interpolate untrusted input into shell. |
| V6 Cryptography | no | No crypto introduced. |
| V7 Logging | yes | Evidence artifacts may contain internal IPs — keep in phase dir; CLAUDE.md says project CLAUDE.md is public-safe but phase evidence is internal. Don't promote IPs to public docs. |

### Known Threat Patterns
| Pattern | STRIDE | Standard Mitigation |
|---------|--------|---------------------|
| Accidental prod mutation via "read-only" script | Tampering | `set -euo pipefail`, only `ip route get`/`ip rule`/`curl`/`git read`; read-only posture banner; no sudo-write/unit control. |
| Shell injection via WAN/arg | Tampering | Validate args against a fixed allowlist; quote all expansions (phase231/237 do this). |
| Infra detail leakage | Info Disclosure | Internal IPs (`10.10.110.x`) stay in phase-dir evidence; do not write to public-safe CLAUDE.md/README. |

## Sources

### Primary (HIGH confidence — direct source reads, this session)
- `src/wanctl/steering/daemon.py` — :1000-1024, :1052-1076, :1130-1137, :1755-1815, :2080-2089, :2544-2561 (code-path trace, dead RTTMeasurement)
- `src/wanctl/rtt_measurement.py` — :139-172, :199-207 (`source_ip` / icmplib `source=` binding)
- `src/wanctl/health_check.py` — :493-524 (`measurement` block shape, native producer)
- `deploy/scripts/cake-autorate-spectrum-state-bridge` — :23, :33, :65, :76-104, :191-271 (prod producer; `raw_rtt_ms = load_rtt` carried-forward finding)
- `deploy/systemd/cake-autorate-{spectrum,att}-state-bridge.service` — ExecStart → `/usr/local/sbin/...`
- `configs/spectrum.yaml`, `configs/att.yaml`, `configs/steering.yaml` — source IPs, reflectors, dead steering measurement block
- `src/wanctl/autorate_config.py` — :617, :643 (`ping_hosts` / `ping_source_ip` loaders)
- `scripts/phase231-migration-held.sh` (full), `scripts/phase225-dscp-ingress-capture.sh` (:1-50), `scripts/phase237-safe16-boundary-check.sh` (full) — reusable skeletons + controller-path target list
- `git tag` — anchor `v1.52`

### Secondary (CONTEXT/MEMORY, MEDIUM)
- `238-CONTEXT.md` (D-01..D-09), `REQUIREMENTS.md` (PROV/SAFE-17), project MEMORY (both WANs on cake-autorate; credential-reads → operator `! cmd`)

### Tertiary (LOW — to confirm at execution)
- `autorate_continuous.py:120-167` line numbers (cited from CONTEXT, not re-read)
- Live `/health` values and deployed-bridge sha (operator captures)

## Metadata

**Confidence breakdown:**
- Code-path trace (PROV-01): HIGH — every claim has a verified file:line; "constructed but never called" confirmed by exhaustive grep.
- Bridge `raw_rtt_ms` = carried-forward `load_rtt` finding: HIGH — read `rates_from_row`, `old_rtt`, `health_payload` directly.
- Config keys / source IPs / reflectors (PROV-03): HIGH — read from configs.
- A/B recommendation (PROV-02): MEDIUM-HIGH — grounded in verified code, but it's a recommendation for operator ratification (D-01), not a verdict.
- Script skeletons / SAFE-17 target list: HIGH — cloned from existing scripts read in full.
- Live host values (deployed sha, live `/health`, `ip route get` results): MEDIUM — operator-confirmed at execution.

**Research date:** 2026-06-14
**Valid until:** 2026-07-14 (stable; re-confirm if cake-autorate topology or bridge source changes, or if wanctl@ mode is re-enabled)
