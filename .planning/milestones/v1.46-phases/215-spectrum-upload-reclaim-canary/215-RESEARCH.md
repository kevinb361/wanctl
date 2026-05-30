# Phase 215: Spectrum Upload Reclaim Canary - Research

**Researched:** 2026-05-29
**Domain:** Production network-control parameter canary (single-knob YAML tune + measurement/gate tooling)
**Confidence:** HIGH (all claims grounded in this repo's files + extracted baseline evidence)

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- **D-01:** Canary moves exactly one knob: `ceiling_mbps: 18 → 20`. `setpoint_mbps`, `floor_mbps`, `step_up_mbps`, all other params frozen.
- **D-02:** Setpoint rejected as lever — Spectrum upload pegged near ceiling 18 for 81.46% of `tcp_upload` samples; ceiling is the binding constraint.
- **D-03:** Magnitude +2 (→20), not +4, because `step_up_mbps` is 5 and +2 is the smallest controlled probe.
- **D-04:** WIN = sustained upload throughput under `tcp_upload` improves ≈ median upload up ≥ ~1.5 Mbps vs Phase 213 baseline. Latency is NOT part of WIN.
- **D-05:** Strict latency-first ROLLBACK gate. Roll back if ANY of: loaded upload p95/p99 (`tcp_upload`) > Phase 213 baseline +10%; OR sustained excursion above `warn_bloat_ms` (75 ms); OR floor-hit cycles > 0; OR alert flapping beyond Spectrum cooldown-bounded rate (`cooldown_sec: 600`, ≈ ≤3 firings/event).
- **D-06:** Snapshot A reuses Phase 211 pattern: capture current `configs/spectrum.yaml` (ceiling=18) + state file + `/health` baseline before mutation. Revert = restore config → `scripts/deploy.sh spectrum cake-shaper` → restart `wanctl@spectrum.service` → verify bound endpoint (`http://10.10.110.223:9101/health`) returns reverted config/version.
- **D-07:** Primary instrument is the Phase 213 harness (`scripts/phase213-baseline-capture.sh` → `tcp_upload` + paired `/health` NDJSON).
- **D-08:** Latency percentiles come from the Phase 214 fail-closed extractor (`scripts/phase214-extract.py`, raw `Ping (ms) ICMP`, no zero-fill).
- **D-09:** VOID-on-collapse rule: window with high `signal_outlier_rate` / `measurement_state=collapsed` is VOID and re-run, never scored.
- **D-10:** A/B method: run ceiling 18 → 20 back-to-back in the same session.
- **D-11:** `scripts/libreqos-cli.mjs` is non-gating corroboration only.

### Claude's Discretion
- D-01/D-03 (knob + magnitude) and D-05 (gate strictness) resolved per CONTEXT rationale. Operator approves final mutation at deploy time.
- Baseline-freshness mechanics (reuse `RUN-20260527T222043Z` vs fresh ceiling-18 leg in same A/B session), observation-window duration for floor-hit/alert accumulation, time-of-day window selection — left to research/planning, guided by D-10.

### Deferred Ideas (OUT OF SCOPE)
- `ceiling_mbps → 22` follow-up cycle (only if 20 passes; own canary).
- Baselining `libreqos-cli.mjs`'s own noise floor.
- `setpoint` reclaim.
- ATT cake-primary canary todo (`2026-04-24-resolve-att-cake-primary-canary-after-phase-196.md`).
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| RECLAIM-01 | Spectrum upload operating points evaluated against current production evidence (setpoint 12, ceiling 18, plan 40 Mbps, latency, floor-hit counts, suppression counters, perceived quality) | §2 Baseline Numbers extracts real p95/p99 latency, throughput, floor-hit=0, alert-fire delta=0 from `RUN-20260527T222043Z`. §1 maps the knob's code path. |
| RECLAIM-02 | At most one upload knob changes per canary cycle, with Snapshot A rollback, explicit success + rollback gates | §1 confirms only `configs/spectrum.yaml` upload.ceiling_mbps changes. §4 documents Snapshot A + deploy/revert. §5 gate-script precedents. D-01/D-05/D-06 enforce single-knob + gates. |
| RECLAIM-03 | Successful reclaim improves throughput/perceived quality without increasing floor-hit cycles, alert spam, or p95/p99 beyond approved bounds | §2 grounds the WIN (+1.5 Mbps) and ROLLBACK (p95>58.7ms / p99>75.9ms, floor-hit>0, alert>3/event) numbers. §6 Validation Architecture maps each to evidence. |
</phase_requirements>

## Summary

Phase 215 is a single-value production canary: raise `continuous_monitoring.upload.ceiling_mbps` from 18 to 20 in `configs/spectrum.yaml`, measure an A/B (ceiling-18 leg then ceiling-20 leg, same session) against the Phase 213 baseline, and either keep the win or revert via Snapshot A. No `src/wanctl/` control-logic edits. The knob flows through a short, well-understood path: `autorate_config.py:411` (`upload_ceiling = ul["ceiling_mbps"] * MBPS_TO_BPS`) → `wan_controller.py:414` (QueueController upload `ceiling`) → `queue_controller.py:206/554` (`enforce_rate_bounds(... ceiling=self.ceiling_bps)`). The probe step targets `ceiling_bps * probe_ceiling_pct` (`queue_controller.py:464`), so raising the ceiling lets the controller probe ~2 Mbps higher.

**The single most important finding:** the Phase 213 signal-sheet reports `flent_median: 0.0, flent_p99: 0.0` for the spectrum `tcp_upload` bucket — those are zero-filled (the exact measurement-collapse bug Phase 214 fixed). The *real* baseline must be re-extracted from the raw flent artifact. I did this with the Phase 214 fail-closed extractor and found the actual numbers below. A second, blocking finding: `phase214-extract.py`'s throughput path only knows `TCP download` keys (`THROUGHPUT_KEYS` line 26) and **fails closed on the upload artifact** — the upload throughput series is keyed `"TCP upload"`. The canary's throughput gate (D-04) therefore needs a small extractor change to read upload throughput. Latency extraction works as-is.

**Primary recommendation:** Re-derive the ceiling-18 baseline numbers from the raw flent artifact (or capture a fresh 18-leg in the same A/B session per D-10 — preferred to control for Phase 214 time-of-day sensitivity), extend `phase214-extract.py` (or add a thin sibling) to read the `TCP upload` throughput series, and build a verdict-emitting gate script modeled on `phase200-saturation-canary.sh` that consumes the paired `/health` NDJSON (floor-hit, alert-fire deltas) and the flent extractor output (p95/p99, throughput median). Snapshot A and deploy/revert reuse the proven Phase 211 sequence verbatim.

## Architectural Responsibility Map

| Capability | Primary Tier | Secondary Tier | Rationale |
|------------|-------------|----------------|-----------|
| Hold the upload ceiling knob | Config (`configs/spectrum.yaml`) | Deployed `/etc/wanctl/spectrum.yaml` | Portable-controller invariant: deployment behavior lives in YAML, not Python branching. |
| Apply ceiling to running shaper | Controller (`autorate_config` → `wan_controller` → `queue_controller`) | LinuxCake backend (`linux_cake_adapter.py`) | Config loader converts Mbps→bps; QueueController clamps `current_rate` to `ceiling_bps`. |
| Generate A/B traffic + capture | Dev VM (traffic gen) | `scripts/phase213-baseline-capture.sh` + flent/health pollers | D-07/D-10; dev VM binds Spectrum source IP, never mutates production. |
| Extract latency/throughput percentiles | Offline analysis (`phase214-extract.py`) | — | Fail-closed, stdlib-only, no wanctl imports; VOID-on-collapse source of truth. |
| Evaluate success/rollback gates | Offline gate script (new, modeled on `phase200-saturation-canary.sh`) | `/health` NDJSON + flent extractor JSON | Emits `verdict.json` with pass/fail/abort. |
| Mutate + revert production | Deploy (`scripts/deploy.sh` + manual service restart) | Bound health endpoint verify | Phase 211 proven sequence; deploy copies code/config but does NOT restart the daemon. |

## Question 1 — Code path for the knob

**Source of truth (repo):** `configs/spectrum.yaml` line 77:
```yaml
upload:
  ceiling_mbps: 18  # ← the canaried value (→ 20)
```

**Flow into the running controller (all VERIFIED via grep + file reads):**

1. **Config load:** `src/wanctl/autorate_config.py:397-411` `_load_upload_config()` reads `ul["ceiling_mbps"]` and stores `self.upload_ceiling = ul["ceiling_mbps"] * MBPS_TO_BPS` (line 411). `MBPS_TO_BPS = 1_000_000`, so 18 → 18_000_000 bps, 20 → 20_000_000 bps.
2. **Validation:** `autorate_config.py:526` and `check_config_validators.py:507/565` enforce strict `floor_mbps < setpoint_mbps < ceiling_mbps`. With floor=8, setpoint=12, ceiling 18→20 stays valid (8 < 12 < 20). **No validator blocks the change.** `[VERIFIED: grep]`
3. **Controller wiring:** `src/wanctl/wan_controller.py:408-414` constructs the upload `QueueController(... ceiling=config.upload_ceiling ...)`.
4. **Runtime clamp:** `src/wanctl/queue_controller.py:62` `self.ceiling_bps = ceiling`; line 73 `self.current_rate = ceiling` (starts at ceiling); the rate update clamps via `enforce_rate_bounds(new_rate, floor=..., ceiling=self.ceiling_bps)` at lines **206 and 554**.
5. **Probe headroom:** `queue_controller.py:464` `if self.current_rate >= self.ceiling_bps * self._probe_ceiling_pct:` — the GREEN probe targets `ceiling_bps * probe_ceiling_pct` (Spectrum `probe_ceiling_pct: 0.95`). At ceiling=18 the probe target is ~17.1 Mbps; at ceiling=20 it is ~19 Mbps. **This is the mechanism by which raising the ceiling actually lets throughput climb** — D-02's "pegged at ceiling" observation means the controller was probe-capped at 18.
6. **Backend init:** `src/wanctl/backends/linux_cake_adapter.py:317-321` seeds initial CAKE bandwidth from `cm.upload.ceiling_mbps` (default 40 if absent); logs `"Initializing CAKE on <iface> (upload): ..."` at line 329. `[VERIFIED: file read]`

**Runtime verification that ceiling=20 took effect** (in priority order; `/health` does NOT expose `ceiling_mbps` directly — VERIFIED by grep of `health_check.py`):

| Evidence | Where | What it proves |
|----------|-------|----------------|
| **Config snapshot in metrics DB** | `src/wanctl/storage/config_snapshot.py:39` writes `upload_ceiling_mbps` on trigger `startup`/`reload`/`manual` to `/var/lib/wanctl/metrics-spectrum.db` | Authoritative: the daemon loaded ceiling=20. Query the latest config-snapshot row after restart. |
| **Startup log line** | `linux_cake_adapter.py:329` `"Initializing CAKE on spec-modem (upload): ...bandwidth_kbit=20000"` in `/var/log/wanctl/spectrum.log` (or `journalctl -u wanctl@spectrum`) | Confirms 20_000 kbit initial seed. |
| **`/health.upload_rate_mbps`** climbing to ~20 under load | `health_check.py:1020` `"upload_rate_mbps": upload.get("current_rate_mbps")`; surfaced by `phase213-health-poller.sh:176` as `.wans[0].upload.current_rate_mbps` | Behavioral proof the probe can now exceed 18. At ceiling=18 it caps near 18; at ceiling=20 it can reach ~19-20. |
| **`last_applied_ul_rate`** | `wan_controller.py:530/1671/4699` (in `/health` summary `ul_rate`) | The flash-wear-protected applied rate; confirms the router was sent the higher rate. |

**Caveat — netlink backend, not RouterOS queues:** Spectrum uses `transport: linux-cake-netlink` (config line 20). The ceiling applies to the local CAKE qdisc on `spec-modem`, not a RouterOS queue. Runtime qdisc state can be cross-checked on cake-shaper with `tc -s qdisc show dev spec-modem` (look for the CAKE `bandwidth` parameter). `[VERIFIED: config + adapter read]`

## Question 2 — Baseline numbers (re-extracted from raw evidence)

**Source:** `.planning/phases/213-experience-baseline-harness/evidence/RUN-20260527T222043Z/spectrum/tcp_upload/`
Flent artifact: `~/flent-results/phase213/phase213-20260527T222043Z-tcp_upload/spectrum/20260527-172219/tcp_upload-*.flent.gz`
Health NDJSON: `.../spectrum/tcp_upload/health-spectrum.ndjson` (89 samples)

> **Provenance flag:** the committed `signal-sheet.md` reports `flent_median: 0.0, flent_p99: 0.0` and `signal_outlier_rate_max: 0.933` for this bucket. Those flent fields are **zero-filled artifacts of the Phase 214 measurement-collapse bug** — do NOT use them. The numbers below were re-extracted by me on 2026-05-29 using the Phase 214 fail-closed extractor on the raw `.flent.gz`. `[VERIFIED: phase214-extract.py run + manual flent parse]`

### Loaded upload latency (flent `Ping (ms) ICMP`, fail-closed, n=349)
| Metric | Baseline (ceiling 18) | Rollback trigger (+10%, D-05) |
|--------|----------------------|-------------------------------|
| p50 | 31.0 ms | — |
| **p95** | **53.4 ms** | **roll back if leg-B p95 > 58.7 ms** |
| **p99** | **69.0 ms** | **roll back if leg-B p99 > 75.9 ms** |
| max | 102.0 ms | — |
| mean | 32.9 ms | — |

> ping command in artifact: `ping -n -D -i 0.20 -w 70 -I 10.10.110.226 dallas` (bind = Spectrum dev-VM source IP). `window_start 2026-05-27T22:22:20Z`, 70 s.

### Upload throughput (flent `TCP upload` series, n=293)
| Metric | Baseline (ceiling 18) | Success gate (D-04) |
|--------|----------------------|---------------------|
| **median goodput** | **11.43 Mbps** | **WIN if leg-B median ≥ ~12.9 Mbps** (+1.5) |
| p95 | 18.02 Mbps | — |
| max | 21.44 Mbps | — |

> **Distinction the planner must respect:** flent `TCP upload` median (11.43 Mbps) is *application goodput* (TCP overhead + DOCSIS framing below the 18 Mbps shaper rate). The `/health.upload_rate_mbps` median over the same window is 18.0 Mbps (the *shaper ceiling/probe rate*). D-04 says "sustained upload throughput under `tcp_upload`" — that is the **flent goodput series**, not the health rate. Score the +1.5 gate on flent `TCP upload` median. `[VERIFIED: extracted both]`

### Health-window signals over the same `tcp_upload` window (n=89, from health-spectrum.ndjson)
| Field | Baseline value | Gate relevance |
|-------|---------------|----------------|
| `upload_rate_mbps` | median 18.0, mean 15.9, min 12, pct≥18 = 65.2% | Behavioral: probe-capped at 18. (Signal-sheet's 81.46% is over a different/larger sample set.) |
| `upload_floor_hit_cycles_total` | **0 → 0 (delta 0)** | D-05 rollback if leg-B delta > 0. |
| `signal_outlier_rate` | median 0.20, **max 0.933** | D-09 VOID: high transient outlier spikes present even in the baseline — windows must be screened. |
| `measurement_state` | **all 89 = "healthy"** | The health-side measurement state was healthy (the 0.933 collapse is the flent-side reflector loss, not the controller's reflector set). Important nuance for D-09: VOID screening must look at BOTH the flent extractor (fail-closed) AND `signal_outlier_rate`, since health `measurement_state` stayed healthy. |
| `alerting_fire_count` | **140 → 140 (delta 0)** | D-05 rollback if leg-B alert-fire delta exceeds cooldown-bounded rate (~3/event). Baseline = 0 firings in-window. |
| `cake_ul_peak_delay_us` | median 6198, p95 21564, p99 42946 | Corroborating queue-delay signal (not a gate, but useful evidence). |
| `load_rtt_ms` (health) | median 30.07, p95 54.67, p99 55.78 | Cross-check vs flent ICMP; health p95 54.7 ≈ flent p95 53.4 (consistent). |
| `baseline_rtt_ms` | median 22.84 | Delta = ~7.2 ms loaded bloat at baseline (well under `warn_bloat_ms`=75). |

**`warn_bloat_ms` excursion gate (D-05):** baseline load-RTT delta (~7 ms) and max load_rtt (55.8 ms health / 102 ms flent max) — the 75 ms `warn_bloat_ms` is an *absolute bloat* threshold; baseline did not sustain excursions above it. Roll back if leg-B sustains load_rtt-delta excursions above 75 ms.

## Question 3 — Measurement harness reuse

### `scripts/phase213-baseline-capture.sh` (orchestrator, VERIFIED by full read)
- **Inputs:** `--bind-map spectrum=<ip>,att=<ip>` (required), `--wans`, `--tests` (default `browse,tcp_upload,tcp_download,rrul,tcp_12down`), `--flent-duration` (default 60), `--pre-buf`/`--post-buf` (default 10s), `--evidence-root`.
- **Mutation posture:** dev-VM traffic generation + read-only snapshots only; **forbidden:** service changes, `/etc/wanctl` writes, deploys, controller config changes (lines 6-14). The canary mutation happens OUTSIDE this harness (via deploy.sh), not inside it.
- **Per-test flow** (`run_bracketed_test`, lines 296-325): steering snapshot → start two health pollers (`phase213-health-poller.sh` against `http://10.10.110.223:9101/health` for spectrum, `.227` for att) → `PRE_BUF` sleep → flent capture via `phase191-flent-capture.sh --tests <test> --wan <wan> --local-bind <bind> --host dallas` → `POST_BUF` sleep → stop pollers → post steering snapshot → `phase213-alert-window.sh` → per-test `manifest.json`.
- **Egress guard (lines 244-247, 331-334):** REFUSES if spectrum egress via the bind IP ≠ `70.123.224.169`. The canary A/B must use the same bind contract.
- **Outputs per test:** `RUN-<ts>/<wan>/<test>/{flent (symlink), health-<wan>.ndjson, steering-pre/post, alerts-*.json, manifest.json}` + run-level `signal-sheet.{json,md}` via `phase213-classify.py`.

### Wiring the A/B run (D-10, same session, ceiling 18 → 20)
The harness runs ONE config state per invocation. The A/B is two `tcp_upload` captures bracketing the mutation:
1. **Leg A (ceiling 18):** `phase213-baseline-capture.sh --bind-map spectrum=<ip> --wans spectrum --tests tcp_upload --flent-duration 60` → captures the fresh 18 baseline in-session (preferred over reusing `RUN-20260527T222043Z` per D-10, to control Phase 214 time-of-day sensitivity).
2. **Mutate:** edit `configs/spectrum.yaml` ceiling 18→20 → Snapshot A → `deploy.sh spectrum cake-shaper` → restart `wanctl@spectrum.service` → verify `/health` (see §4).
3. **Leg B (ceiling 20):** rerun the same `--tests tcp_upload` capture, ideally within the same time-of-day window, same bind, same `--flent-duration`.
4. **Score:** extract both legs' flent latency + throughput, compare leg B against leg A (and/or the `RUN-20260527T222043Z` reference).

**Recommend `--flent-duration` ≥ 120s** for the canary legs (vs the 60s baseline) to accumulate more floor-hit/alert-window observation, while keeping legs equal-duration for apples-to-apples. Operator decides per D-05 discretion; document the choice.

### VOID-on-collapse signal source (D-09)
Two independent signals, both must be checked:
- **Flent side (primary, fail-closed):** `phase214-extract.py` raises `FlentExtractionError` if `raw_values['Ping (ms) ICMP']` is missing/empty (lines 73-78) — a hard VOID. It never zero-fills.
- **Controller side:** `signal_outlier_rate` and `measurement_state` in the health NDJSON. Phase 213 spectrum `tcp_upload` showed `signal_outlier_rate` max 0.933 (the value cited in D-09) — but note `measurement_state` was "healthy" for all 89 samples in that window. So the VOID screen should trip on **either** a high `signal_outlier_rate` ceiling **or** any `measurement_state=collapsed` sample **or** a `FlentExtractionError`. The 0.933 figure is a per-sample peak, not a window mean (window mean was 0.20) — set the VOID threshold on a sustained/quantile basis, not a single spike.

## Question 4 — Snapshot A + deploy/revert mechanism

### Phase 211 canary deploy sequence (VERIFIED: STATE.md lines 141-143)
- `[211-01]` Spectrum v1.45 canary verified via **bound** endpoint `http://10.10.110.223:9101/health`; **loopback `127.0.0.1:9101` is NOT listening** in production config.
- `[211-01]` `scripts/deploy.sh spectrum cake-shaper` copied code but **did NOT restart the running daemon**; orchestrator restarted `wanctl@spectrum.service`, after which `/health.version` returned the new version.
- `[211-02]` ATT mirror: Snapshot A `20260527T174231Z` captured, `deploy.sh att cake-shaper`, then `wanctl@att.service` restart required before `.227` endpoint returned the new version.

### What `deploy.sh spectrum cake-shaper` does (VERIFIED: full read)
Args are `<wan_name> <target_host>` → `spectrum cake-shaper`. Sequence:
1. `check_prerequisites` (SSH reachable, rsync present).
2. `deploy_code` → runs the **Phase 201 predeploy gate** (`phase201-predeploy-gate.sh`) because `WAN_NAME == spectrum` (deploy.sh:161-179). The gate reads `/etc/wanctl/spectrum.yaml` on the target and **BLOCKS** if `target_bloat_ms`/`warn_bloat_ms` are present under `continuous_monitoring.upload`, or if `docsis_mode: true` without `setpoint_mbps`. **The ceiling-20 change passes this gate** (it touches none of those keys; setpoint_mbps stays 12). Then rsyncs `src/wanctl/` (no-op for this phase — no code edits).
3. `deploy_config spectrum` → scp `configs/spectrum.yaml` → `/etc/wanctl/spectrum.yaml` (mode 640, owner root:wanctl).
4. Deploys scripts/systemd/QoS assets, `daemon-reload`, `verify_deployment`, `validate-deployment.sh`.
5. **Does NOT restart `wanctl@spectrum.service`** — a manual restart is mandatory for the new ceiling to load (config is read at startup; `config_snapshot.py` trigger `startup`).

**Why the manual restart:** the daemon reads config once at process start (`autorate_config` load → QueueController construction). `deploy.sh` writes the new YAML but the long-running 20Hz process holds the old `upload_ceiling`. A reload/restart re-runs `config_snapshot` and re-seeds the CAKE bandwidth. `[VERIFIED: STATE.md + deploy.sh + config_snapshot.py]`

### Snapshot A capture (D-06) — exact contents
Before mutation, capture (timestamp `<ts>`):
| Artifact | Path / command |
|----------|----------------|
| Repo config (pre) | copy of `configs/spectrum.yaml` (ceiling=18) → evidence dir |
| Deployed config (pre) | `ssh cake-shaper 'sudo cat /etc/wanctl/spectrum.yaml'` → redacted copy |
| State file | `ssh cake-shaper 'sudo cat /var/lib/wanctl/spectrum_state.json'` (config line 149) |
| `/health` baseline | `curl -s http://10.10.110.223:9101/health` → `snapshot-a-health.json` |
| Version + uptime | from `/health.version`, `/health.uptime_seconds` |
| Config-snapshot DB row | latest `upload_ceiling_mbps` from `/var/lib/wanctl/metrics-spectrum.db` (proves 18 was loaded) |

### Exact revert path (D-06)
1. `git checkout configs/spectrum.yaml` (or restore the Snapshot-A copy) → ceiling back to 18.
2. `scripts/deploy.sh spectrum cake-shaper` (predeploy gate passes; config redeployed).
3. `ssh cake-shaper 'sudo systemctl restart wanctl@spectrum.service'`.
4. Verify: `curl -s http://10.10.110.223:9101/health` shows reverted version, `status: healthy`, `upload_rate_mbps` back in the ≤18 regime; confirm latest config-snapshot row `upload_ceiling_mbps == 18`.
5. Run `scripts/canary-check.sh --ssh cake-shaper` (exit 0 = PASS) as the post-revert health gate.

> **Note:** D-06 calls the fallback "restore 18", NOT the config comment's "drop setpoint to 10" (config lines 86-87). The setpoint-10 fallback is a *different* control decision and is explicitly NOT the revert path here.

## Question 5 — Gate-script precedents

| Script | Fit for 215 gate | Reusable pattern |
|--------|------------------|------------------|
| **`scripts/phase200-saturation-canary.sh`** | **CLOSEST MATCH — use as the template.** | Emits `verdict.json` with `verdict ∈ {pass,fail,abort}`, exit 0/1/2. Primary gate is `floor_hit_cycles_total_delta_loaded_window` computed from `/health` field `.wans[0].upload.floor_hit_cycles_total` (lines 268-272), bookended idle baselines, env-var preflight that ABORTs on stale config (`PHASE200_REMOTE_YAML_SSH` compares declared vs deployed `floor_mbps`/`ceiling_mbps`). Also surfaces `ul_hysteresis_suppressions_per_60s`. **This is the floor-hit + suppression surfacing the planner asked about.** |
| `scripts/phase201-predeploy-gate.sh` | Reuse AS-IS (runs automatically inside deploy.sh) | Fail-closed YAML key inspection on the deploy target. The ceiling-20 change passes it; no modification needed. Confirms single-knob discipline at deploy time. |
| `scripts/canary-check.sh` | Reuse AS-IS for post-restart health gate | Polls bound endpoints, checks `status`, `upload_state` (GREEN/YELLOW=pass, RED/SOFT_RED=warn), version, storage. Exit 0/1/2. Run after both the mutation restart and the revert restart. |

**Recommended gate script for 215** (`scripts/phase215-reclaim-gate.sh` or similar): clone the `phase200-saturation-canary.sh` skeleton (env preflight that ABORTs if deployed `ceiling_mbps` ≠ expected, NDJSON `/health` sampling, `verdict.json` emit) but score the D-04/D-05 gates:
- **floor-hit:** `floor_hit_cycles_total` delta over leg-B window (D-05: > 0 → FAIL). Already the proven `phase200` primary gate.
- **alert flapping:** `alerting_fire_count` delta over leg-B window vs cooldown-bounded budget (Spectrum `cooldown_sec: 600` → ≈ ≤3 firings/event; D-05). Health field `.wans[0]...` / NDJSON `alerting_fire_count`. Cross-check against `suppression_alert_threshold: 180` (config line 117) and `phase213-alert-window.sh` SQLite alert counts.
- **p95/p99 latency:** from `phase214-extract.py` on the leg-B flent (D-05: p95 > 58.7 ms or p99 > 75.9 ms → FAIL).
- **warn_bloat excursion:** sustained load_rtt-delta > 75 ms (D-05).
- **throughput WIN:** flent `TCP upload` median ≥ baseline +1.5 Mbps (D-04) — requires the extractor fix below.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Latency percentile extraction | Custom flent parser | `scripts/phase214-extract.py::extract_flent_latency` | Already fail-closed, stdlib-only, canonical Phase 214 percentile contract, VOID-on-collapse. |
| Verdict-emitting canary gate | New from scratch | Clone `scripts/phase200-saturation-canary.sh` | Proven env-preflight + `verdict.json` + floor-hit/suppression surfacing + ABORT-on-stale-config. |
| Predeploy single-knob enforcement | New check | `scripts/phase201-predeploy-gate.sh` (auto-runs in deploy.sh) | Fail-closed; already wired for spectrum. |
| Post-restart health validation | New health poller | `scripts/canary-check.sh` | Knows bound endpoints, upload_state, version, storage; exit 0/1/2. |
| A/B traffic capture | New harness | `scripts/phase213-baseline-capture.sh --tests tcp_upload` | Same instrument as the baseline → apples-to-apples; egress-guarded. |
| Snapshot/deploy/revert | New deploy logic | `scripts/deploy.sh spectrum cake-shaper` + manual restart | Phase 211 proven sequence. |

**Key insight:** every piece of this canary already exists as a hardened script. The phase is ~90% orchestration + one small extractor extension + numeric gates, not new tooling.

## Common Pitfalls

### Pitfall 1: Trusting the signal-sheet's zero-filled flent latency
**What goes wrong:** Using `flent_median: 0.0 / flent_p99: 0.0` from `signal-sheet.md` as the baseline → meaningless +10% gate (10% of 0 = 0).
**Why:** the Phase 213 classifier zero-filled collapsed flent series; Phase 214 fixed this with the fail-closed extractor.
**How to avoid:** always re-extract from the raw `.flent.gz` with `phase214-extract.py`. Real baseline: p95=53.4, p99=69.0 ms.
**Warning signs:** any latency value of exactly 0.0.

### Pitfall 2: `phase214-extract.py` fails closed on the upload artifact (BLOCKER for D-04)
**What goes wrong:** `extract_flent_throughput` only checks `THROUGHPUT_KEYS = ("TCP download sum", "TCP totals", "TCP download avg")` (line 26). The upload artifact's series is keyed **`"TCP upload"`**, so the function raises `FlentExtractionError: no usable TCP download series found` — exactly what happened when I ran it. Latency extraction is unaffected.
**How to avoid:** extend `THROUGHPUT_KEYS` to include upload keys, OR add an `extract_flent_upload_throughput(path)` sibling (recommended — keeps the download contract untouched and respects the "no Phase 213 back-edits" invariant). This is a required, in-scope tooling change (measurement/gate tooling is explicitly in scope; `src/wanctl/` is not — this script is not in `src/wanctl/`).
**Warning signs:** the gate script aborts on throughput extraction for the upload leg.

### Pitfall 3: Forgetting the manual service restart
**What goes wrong:** `deploy.sh` writes ceiling=20 to `/etc/wanctl/spectrum.yaml` but the running 20Hz daemon keeps ceiling=18; leg B silently measures the OLD config → false "no change" result.
**How to avoid:** always `systemctl restart wanctl@spectrum.service` after deploy, then verify via the config-snapshot DB row / startup log / `/health` (§1, §4). Phase 211 documented this exact trap.
**Warning signs:** `/health.version` or config-snapshot `upload_ceiling_mbps` unchanged after deploy.

### Pitfall 4: Querying the loopback health endpoint
**What goes wrong:** `curl http://127.0.0.1:9101/health` returns nothing — loopback is not listening (STATE 211-01).
**How to avoid:** always use the bound IP `http://10.10.110.223:9101/health`.

### Pitfall 5: Phase 214 time-of-day / path sensitivity confounds the A/B
**What goes wrong:** comparing a leg-B run hours later (or against the day-old `RUN-20260527T222043Z`) attributes a diurnal/path shift to the ceiling change.
**How to avoid:** D-10 — run both legs back-to-back, same session, same bind, same `--flent-duration`, same reflector/host (`dallas`). Prefer a fresh in-session 18-leg over the stored reference.

## Runtime State Inventory

> This is a config-value canary, not a rename/refactor. Included for completeness because it mutates a production daemon's effective config.

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | `/var/lib/wanctl/spectrum_state.json` holds EWMA/streak/`current_rate`. On ceiling raise, `current_rate` may carry the old 18 cap until the next probe; QueueController re-clamps to the new ceiling. | Capture in Snapshot A. No migration — state self-heals on probe. On revert, state will re-clamp down to 18 via `enforce_rate_bounds`. |
| Live service config | Deployed `/etc/wanctl/spectrum.yaml` (NOT in git) is the running source; repo `configs/spectrum.yaml` is what `deploy.sh` pushes. Metrics DB `/var/lib/wanctl/metrics-spectrum.db` records config snapshots. | Snapshot A captures deployed config + DB row. Verify post-deploy DB row = 20. |
| OS-registered state | `wanctl@spectrum.service` (systemd). Restart required; no unit-file change. | Manual restart; verify via `systemctl status` + bound `/health`. |
| Secrets/env vars | None touched. `ROUTER_PASSWORD`, `DISCORD_WEBHOOK_URL` unchanged. | None. |
| Build artifacts | None — no code change, no rebuild. `deploy.sh` rsync of `src/wanctl/` is a no-op for this phase. | None. |

## Code Examples

### Re-extract baseline latency (works today)
```bash
GZ="$HOME/flent-results/phase213/phase213-20260527T222043Z-tcp_upload/spectrum/20260527-172219/tcp_upload-*.flent.gz"
.venv/bin/python3 scripts/phase214-extract.py --flent-gz $GZ --output-json /tmp/base.json
# latency block works; throughput block FAILS on upload (see Pitfall 2)
```

### Extract upload throughput (the fix needed — sibling function pattern)
```python
# Add to scripts/phase214-extract.py (does NOT touch download contract):
UPLOAD_THROUGHPUT_KEYS = ("TCP upload sum", "TCP totals", "TCP upload avg", "TCP upload")
def extract_flent_upload_throughput(path: Path) -> dict[str, Any]:
    data = _load_flent(path)
    results = data.get("results")
    if not isinstance(results, dict):
        raise FlentExtractionError(f"{path}: results missing or not an object")
    for key in UPLOAD_THROUGHPUT_KEYS:
        values = _numeric_values(results.get(key))
        if values:
            values.sort(); n = len(values)
            return {"throughput_median_mbps": statistics.median(values),
                    "throughput_p95_mbps": values[min(n-1, int(n*0.95))],
                    "throughput_max_mbps": values[-1],
                    "sample_count": n, "series_key_used": key}
    raise FlentExtractionError(f"{path}: no usable TCP upload series found")
```
> Verified the baseline upload series key is `"TCP upload"`: median 11.43, p95 18.02, max 21.44 Mbps.

### Deploy + restart + verify (Phase 211 sequence)
```bash
# after editing configs/spectrum.yaml ceiling 18->20 and capturing Snapshot A:
scripts/deploy.sh spectrum cake-shaper          # predeploy gate passes; pushes config
ssh cake-shaper 'sudo systemctl restart wanctl@spectrum.service'   # MANDATORY
curl -s http://10.10.110.223:9101/health | python3 -m json.tool    # verify status/version
scripts/canary-check.sh --ssh cake-shaper        # exit 0 = PASS
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Trust flent series in signal-sheet | Fail-closed raw-values extraction (`phase214-extract.py`) | Phase 214 (v1.46) | Baseline latency must be re-extracted; zero-fill is a bug. |
| Casual threshold tuning | One-knob canary + Snapshot A + explicit gates | v1.46 invariant (STATE line 61) | This phase IS the discipline; no second knob. |
| RouterOS REST/SSH queue | linux-cake-netlink local qdisc | pre-215 (config line 20) | Ceiling applies to `spec-modem` CAKE qdisc, not a RouterOS queue. |

## Assumptions Log

| # | Claim | Section | Risk if Wrong |
|---|-------|---------|---------------|
| A1 | `dallas` netperf/flent host + Spectrum bind IP (`10.10.110.226` dev-side egress `70.123.224.169`) remain valid for leg-B capture | §2/§3 | If reflector path changed, leg-B not comparable to baseline → re-baseline in-session (D-10 already mitigates). |
| A2 | A fresh in-session 18-leg is preferable to reusing `RUN-20260527T222043Z` | §3 | Operator discretion (D-05/D-10 explicitly leave this open); reusing the reference is also valid if same-session capture is impractical. |
| A3 | `--flent-duration` ≥120s for canary legs gives enough floor-hit/alert observation | §3 | Too short → under-samples rare RED bursts; operator sets per D-05. |
| A4 | Spectrum `cooldown_sec: 600` → ~≤3 firings/event budget for the alert gate | §5 | Matches config comment (line 239) and STATE line 135; if alert semantics changed, re-derive budget. |

## Open Questions (RESOLVED)

1. **Baseline-freshness choice (D-05 discretion):** reuse `RUN-20260527T222043Z` extracted numbers (p95=53.4, p99=69.0, throughput median 11.43) as the reference, or capture a fresh 18-leg in the same A/B session?
   - What we know: D-10 wants same-session legs to control Phase 214 time-of-day sensitivity.
   - Recommendation: capture a fresh 18-leg in-session AND keep the re-extracted `RUN-20260527T222043Z` numbers as a sanity cross-check.
   - **RESOLVED:** fresh in-session leg-A captured in Plan 03 Task 2 STEP A (moved out of Plan 02 per cross-AI REVIEW-5 so leg-A/leg-B are guaranteed back-to-back); the `RUN-20260527T222043Z` numbers (and derived 58.7/75.9/12.9 bounds) are pinned in Plan 01 as documented static fallback/sanity constants used only when no `--baseline-extract` is supplied.

2. **Observation-window duration for floor-hit/alert accumulation:**
   - What we know: floor-hit and alert events are rare; 60s legs saw 0 of each at baseline.
   - Recommendation: ≥120s loaded legs; document the choice in the plan.
   - **RESOLVED:** `--flent-duration 120` used for both legs in Plans 02/03.

3. **VOID threshold on `signal_outlier_rate`:** the baseline window peaked at 0.933 (single spike) but averaged 0.20 and `measurement_state` stayed healthy.
   - Recommendation: VOID on a sustained/quantile basis (e.g., p90 of `signal_outlier_rate` over the window, or any `measurement_state=collapsed`), not a single-sample peak, OR on `FlentExtractionError`.
   - **RESOLVED:** Plan 01 pins VOID = `signal_outlier_rate_p90 >= 0.30` OR any `measurement_state == collapsed` sample OR `FlentExtractionError`; warn-bloat = load_rtt-minus-baseline excursion > 75 ms sustained over ≥5 consecutive samples.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| `flent` | A/B capture (`phase191-flent-capture.sh`) | assumed ✓ (used in baseline RUN-20260527T222043Z) | — | none — required for measurement |
| `.venv/bin/python3` | `phase214-extract.py`, harness helpers | ✓ | 3.11+ | none |
| `jq`, `curl`, `ssh` | harness, gate, deploy, canary-check | assumed ✓ | — | python fallback in canary-check |
| `node` | `libreqos-cli.mjs` (non-gating, D-11) | unverified | — | skip corroboration (non-gating) |
| SSH `cake-shaper` + sudo | deploy, snapshot, restart | ✓ (Phase 211 used it) | — | none — required for mutation |
| Bound endpoint `10.10.110.223:9101` | verify, NDJSON poll | ✓ (Phase 211) | — | none; loopback NOT listening |

**Missing dependencies with no fallback:** none confirmed missing; verify `flent` + SSH/sudo to `cake-shaper` at plan-execution time (`phase213-baseline-capture.sh --check-prereqs` does exactly this).

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest (`.venv/bin/pytest`) |
| Config file | `pyproject.toml` (project standard; see CLAUDE.md) |
| Quick run command | `.venv/bin/pytest tests/test_phase214_extract.py -x` (extractor unit tests) |
| Full suite command | `.venv/bin/pytest tests/ -q` |

> Existing precedent tests: `tests/test_phase201_predeploy_gate.py` (gate-script tests), `tests/test_phase214_*` (extractor). The upload-throughput extractor addition should get a unit test mirroring the existing latency/download tests, using a fixture flent with a `TCP upload` series.

### Phase Requirements → Test / Evidence Map
| Req ID | Behavior | Validation Type | Command / Evidence | Exists? |
|--------|----------|-----------------|--------------------|---------|
| RECLAIM-01 | Upload operating points evaluated vs production evidence | evidence (re-extracted baseline) | `phase214-extract.py` on baseline `.flent.gz` + health NDJSON aggregates (p95=53.4, p99=69.0, throughput 11.43, floor-hit=0, alert=0) | ✅ done in this research |
| RECLAIM-02 | One knob + Snapshot A + explicit gates | unit + procedure | `tests/test_phase201_predeploy_gate.py` (single-knob gate passes for ceiling-20); Snapshot-A artifact checklist; gate-script `verdict.json` | partial — gate test ✅; new 215 gate script ❌ Wave 0 |
| RECLAIM-02 | Upload throughput extractor reads `TCP upload` | unit | `tests/test_phase214_upload_throughput.py` (new) | ❌ Wave 0 |
| RECLAIM-03 | WIN proven (throughput ≥ +1.5 Mbps) | evidence | leg-B flent `TCP upload` median ≥ ~12.9 Mbps via extractor | needs leg-B run |
| RECLAIM-03 | No regression (p95/p99, floor-hit, alert spam) | evidence (gate) | leg-B: p95 ≤ 58.7, p99 ≤ 75.9, floor-hit delta = 0, alert-fire delta ≤ ~3 → `verdict.json` | needs leg-B run + gate script |
| RECLAIM-03 | Rollback works | procedure | revert sequence (§4) → `canary-check.sh --ssh cake-shaper` exit 0 + config-snapshot row = 18 | ✅ canary-check exists |
| RECLAIM-02 | Snapshot-A discipline held | evidence | Snapshot-A artifacts present + deployed-config DB row matches pre-mutation | ✅ mechanism exists |

### Sampling Rate
- **Per task commit:** `.venv/bin/pytest tests/test_phase214_extract.py tests/test_phase201_predeploy_gate.py -x` (tooling unit tests).
- **Per wave merge:** full focused suite + `bash -n` on new gate script + `--check-manifest`/`--check-prereqs` dry-runs.
- **Phase gate (production):** Snapshot A captured → mutation deployed + restart verified → leg-B captured non-VOID → `verdict.json` PASS (WIN) or rollback executed + `canary-check.sh` exit 0.

### Wave 0 Gaps
- [ ] `scripts/phase214-extract.py` — add `extract_flent_upload_throughput` (reads `TCP upload` series) — covers RECLAIM-02/03 throughput gate (Pitfall 2 BLOCKER).
- [ ] `tests/test_phase214_upload_throughput.py` — unit test for the upload-series fixture.
- [ ] `scripts/phase215-reclaim-gate.sh` (clone of `phase200-saturation-canary.sh`) — emits `verdict.json`; scores floor-hit, alert-fire, p95/p99, warn_bloat excursion, throughput WIN.
- [ ] `tests/test_phase215_reclaim_gate.py` — offline fixture verdict tests (pass/fail/abort), mirroring phase200/phase201 gate-test style.
- [ ] Evidence dir scaffold under `.planning/phases/215-spectrum-upload-reclaim-canary/evidence/` for Snapshot A + leg A/B + verdict.

## Sources

### Primary (HIGH confidence — this repo)
- `configs/spectrum.yaml` (lines 20, 75-108, 117, 149, 239) — knob, transport, thresholds, state file, alerting.
- `src/wanctl/autorate_config.py:397-411,526` — config load + validation.
- `src/wanctl/wan_controller.py:408-414,530,1611,1671,4699` — QueueController wiring, flash-wear, applied rate.
- `src/wanctl/queue_controller.py:62,73,206,464,554` — ceiling clamp + probe target.
- `src/wanctl/backends/linux_cake_adapter.py:317-329` — CAKE bandwidth seed + init log.
- `src/wanctl/health_check.py:454-524,1020` — measurement state, `upload_rate_mbps` exposure (no ceiling field).
- `src/wanctl/storage/config_snapshot.py:38-39` — `upload_ceiling_mbps` recorded to metrics DB.
- `scripts/phase213-baseline-capture.sh` (full) + `phase213-health-poller.sh:176-179` — harness + field map.
- `scripts/phase214-extract.py` (full) — fail-closed extractor; `THROUGHPUT_KEYS` download-only gap.
- `scripts/phase200-saturation-canary.sh` (header + lines 131-272) — verdict/floor-hit/suppression gate template.
- `scripts/phase201-predeploy-gate.sh` (full) — single-knob fail-closed gate (passes for ceiling-20).
- `scripts/canary-check.sh` (full) — post-restart health gate, bound endpoints.
- `scripts/deploy.sh` (full) — deploy sequence, Spectrum predeploy gate hook, no auto-restart.
- `.planning/STATE.md:61,135,141-143` — v1.46 one-knob invariant, alert cooldown semantics, Phase 211 deploy facts.
- `.planning/phases/213-experience-baseline-harness/evidence/RUN-20260527T222043Z/` — baseline run (signal-sheet + health NDJSON + flent symlink).

### Re-extracted evidence (HIGH — computed this session 2026-05-29)
- Flent latency (fail-closed): p50=31.0, p95=53.4, p99=69.0, max=102.0 ms (n=349).
- Flent `TCP upload` throughput: median 11.43, p95 18.02, max 21.44 Mbps (n=293).
- Health NDJSON aggregates: floor-hit delta 0, alert-fire delta 0, measurement_state all healthy, signal_outlier_rate median 0.20/max 0.933 (n=89).

## Metadata

**Confidence breakdown:**
- Code path (Q1): HIGH — every hop verified by file read + grep.
- Baseline numbers (Q2): HIGH — re-extracted from raw artifact; signal-sheet zero-fill flagged.
- Harness reuse (Q3): HIGH — full read of orchestrator + poller field map.
- Snapshot/deploy/revert (Q4): HIGH — deploy.sh + STATE.md Phase 211 facts.
- Gate precedents (Q5): HIGH — full read of all three precedent scripts.
- Tooling gap (Pitfall 2): HIGH — reproduced the `FlentExtractionError` live.

**Research date:** 2026-05-29
**Valid until:** ~2026-06-28 (stable repo; re-verify baseline freshness if a new 213-style run supersedes `RUN-20260527T222043Z`, and re-check bind/reflector IPs at execution).
