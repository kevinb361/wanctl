# Pitfalls Research

**Domain:** Pluggable subprocess (`fping`) RTT measurement backend for a 50ms adaptive CAKE/steering control loop (wanctl v1.53)
**Researched:** 2026-06-13
**Confidence:** HIGH (grounded in in-repo code + live production config + fping/cake-autorate upstream docs)

## Scope Note (read first)

This milestone is the **first controller-path-touching milestone in 10** — it deliberately ends the SAFE-07..16 zero-diff streak. The in-scope surface is `src/wanctl/rtt_measurement.py`, `src/wanctl/autorate_continuous.py`, `src/wanctl/steering/daemon.py`, plus configs. Every pitfall below is specific to *adding an `fping`/subprocess RTT backend behind a config seam and A/B-ing it against the live consumer* — not generic subprocess advice.

**Three load-bearing facts that anchor the whole risk picture:**

1. **The existing hot path uses `icmplib` raw sockets — no fork/exec.** `RTTMeasurement.ping_host()` calls `icmplib.ping(..., source=self.source_ip, privileged=True)`. Switching to `fping` *introduces a subprocess into a path that currently has none.* That is the entire new risk surface.
2. **There is already an in-repo subprocess-backend precedent: `irtt_measurement.py`.** It encodes most lifecycle lessons correctly (`shutil.which` availability gate, `subprocess.run(capture_output, timeout)`, parse-output-even-on-nonzero-exit, flock serialization, failure-log-level management, return-`None`-on-all-failures, always-instantiated/no-op-when-disabled). **The fping backend should be modeled on this wrapper, and the pitfalls below are mostly the places fping *diverges* from it** (line-oriented text not one JSON blob; loop/`-l` mode tempts long-lived processes; `-S` source binding).
3. **`fping -S 10.10.110.223` already runs in production today** via upstream cake-autorate on the Spectrum shaper (`configs/cake-autorate/config.spectrum.sh`: `pinger_method=fping`, `ping_extra_args="-S 10.10.110.223"`). The observed STALL was a *systemd-lifecycle / buffering* problem under the first setup, **not** evidence fping is unfit. fping+source-binding is proven viable on this exact host.

---

## Critical Pitfalls

### Pitfall 1: Pipe-buffer stall — the observed systemd STALL, root-caused

**What goes wrong:**
An `fping` subprocess (especially in loop/`-l` or count/`-c` continuous mode) produces no readable lines for seconds-to-minutes while the controller starves, then dumps a burst — or never flushes at all. This is the exact STALL observed during the Spectrum cake-autorate trial: fping "entered STALL under the first systemd setup while classic `ping` produced live samples."

**Why it happens:**
By default, writes to stdout pass through a ~4096-byte block buffer **unless stdout is a TTY**, in which case it is line-buffered. Under systemd, the child's stdout is a pipe, not a TTY, so fping block-buffers its output. The controller's `readline()` blocks until 4 KB accumulates. `ping` happened to flush differently (or was line-buffered by glibc heuristics for its output cadence), so it "worked" — masking the real cause. fping only gained native line-buffered stdout in **v4.3 (2020-07-11)** (`#179`); any older fping, or any build/path where that behavior regresses, block-buffers into pipes. This is a buffering bug masquerading as an fping-is-bad result.

**How to avoid:**
- **Prefer one-shot invocation per measurement (the IRTT pattern), not a long-lived loop process.** `subprocess.run(["fping","-q","-C","<count>", ...], capture_output=True, text=True, timeout=...)` collects all output after process exit — no streaming, no buffer to stall. This sidesteps the entire buffering class and matches `irtt_measurement.py`. A 50ms cycle does **not** require a persistent pinger; the existing `BackgroundRTTThread` already decouples probe cadence from the control loop.
- If a streaming/loop design is ever chosen anyway: force line buffering on the child with `stdbuf --output=L --error=L fping ...` (or fping ≥ 4.3 which line-buffers natively), and pin a minimum fping version with `shutil.which` + `fping -v` parse + hard-warn-below-4.3.
- Never rely on the inherited systemd stdout being a TTY.

**Warning signs:**
A/B candidate shows long gaps with zero samples followed by bursts; `steering_rtt_measurement` PerfTimer shows bimodal latency (near-zero then multi-second); cycle `successful_count=0` runs clustered then a flood; behavior differs between interactive shell (works) and under systemd (stalls). The TTY-vs-pipe divergence *is* the fingerprint.

**Phase to address:**
Backend-implementation phase (the fping wrapper itself). One-shot design decision must be locked here. Re-verify under an actual systemd unit, not an interactive shell, in the benchmarking phase.

---

### Pitfall 2: Subprocess lifecycle fragility — zombies, orphan accumulation, hang-on-timeout

**What goes wrong:**
A subprocess RTT backend that forks every cycle (20 Hz) but doesn't reliably reap children leaks zombies; a child that hangs (DNS, dead reflector, kernel socket exhaustion) blocks the cycle past the 50ms budget or pegs the watchdog; on `subprocess.run` timeout the child may be left running because Python kills the immediate child but not its process group.

**Why it happens:**
Naive `Popen` without `.wait()`/`.communicate()` leaks zombies. `subprocess.run(timeout=...)` raises `TimeoutExpired` and *does* kill the child, but if the backend ever moves to `Popen` + manual loop (or a wrapper shell), the grandchildren survive. At 20 Hz any per-cycle leak compounds fast. The IRTT wrapper avoids this by being one-shot per *burst* on a 10 s cadence, not per 50 ms cycle.

**How to avoid:**
- **Do not fork per 50ms cycle.** Run the fping probe on the `BackgroundRTTThread` cadence (decoupled from the control loop), exactly like icmplib runs there today and like IRTT runs on `IRTTThread`. The control loop reads the cached `RTTSnapshot` lock-free; it never waits on a subprocess.
- Use `subprocess.run(..., timeout=...)` (auto-reaps, raises on timeout) rather than hand-rolled `Popen`. Mirror `IRTTMeasurement._run_serialized()`.
- Set `timeout = probe_window + grace` (IRTT uses `duration + 5s`); on `TimeoutExpired` return `None` and let the existing stale-prefer-`None` / history-fallback path carry the cycle.
- If `Popen` is unavoidable, use `start_new_session=True` and kill the process *group* on timeout.

**Warning signs:**
`ps --ppid <pid>` shows growing defunct/`<zombie>` children; RSS or fd count climbs over a soak; `steering_rtt_measurement` occasionally spikes to the timeout value; systemd `Tasks:` count for the unit trends upward.

**Phase to address:**
Backend-implementation phase. Verify zombie/fd/task counts explicitly in the benchmarking/soak phase (add to the "looks done but isn't" checklist).

---

### Pitfall 3: Source-IP / policy-routing breakage (`-S` mismatch → silently wrong WAN)

**What goes wrong:**
The fping backend probes egress the **wrong WAN** (or the host default route) because the source binding is missing, wrong, or silently ignored. The controller then measures the *other* link's latency and shapes/steers on garbage — and nothing errors, because pings still succeed.

**Why it happens:**
The icmplib path binds via `icmplib.ping(source=self.source_ip)`, and `ping_source_ip` is the policy-routing key (`configs/att.yaml: ping_source_ip: "10.10.110.227"`, Spectrum `.226`/`.223`). fping's equivalent is `-S <source_addr>`. If the seam doesn't *translate* `source_ip → -S`, or passes a hostname instead of the bound address, or the address isn't actually assigned/route-mapped, fping falls back to the default source and the policy route sends it out the default WAN. Success masks the error. This is a *correctness* failure, not a crash — the most dangerous kind in a control loop.

**How to avoid:**
- The backend seam contract must carry `source_ip` and the fping backend must emit `-S <source_ip>` for every invocation. Production already proves this works (`fping -S 10.10.110.223` live on the Spectrum shaper).
- Add a **binding-assertion test**: probe a known-asymmetric reflector and assert the measured path matches the intended WAN (e.g., compare against the icmplib baseline for the same `source_ip` — they must agree within tolerance). A divergence means the bind didn't take.
- Validate at config-load that `source_ip` is a locally-assigned address before handing it to fping; fail closed.
- Preserve the per-WAN distinction: ATT `.227`, Spectrum `.226`/`.223`. A single hardcoded `-S` is a foot-gun for the multi-WAN deployment.

**Warning signs:**
Candidate RTT for one WAN suddenly resembles the other WAN's baseline; loss/RTT no longer correlates with that link's known congestion events; `fping -S` silently accepted but `ip route get <reflector> from <source>` shows the wrong table. A/B "win" that's actually measuring the healthier WAN.

**Phase to address:**
Backend-implementation phase (seam must carry & emit `-S`). Binding-assertion verification in the benchmarking phase **before** any live A/B — a source-bind bug invalidates the entire A/B.

---

### Pitfall 4: Output-parsing edge cases (partial lines, loss markers, locale/timestamp/units)

**What goes wrong:**
The parser mis-reads fping output: treats a `-` / `timed out` / unreachable line as `0ms` (catastrophic — fakes a perfect link), drops a partial final line, mis-parses locale-formatted decimals (`12,3` vs `12.3`), confuses ICMP-error lines (`ICMP Host Unreachable`) with RTT lines, or mishandles fping's `: xmt/rcv/loss` summary vs per-probe `[seq], ... time=X ms` lines.

**Why it happens:**
fping output is line-oriented and *mode-dependent*: `-C` emits per-target arrays, `-c`/`-l` emit summary stats, quiet `-q` suppresses per-probe lines and sends summary to **stderr**, loss shows as `-` in `-C` mode. The existing `parse_ping_output()` regex (`time=([0-9.]+)`) is tuned for classic `ping` and explicitly *not* used in the hot path — reusing it for fping will silently miss fping's distinct formats. Locale (`LC_NUMERIC`) can change the decimal separator. Loss markers parsed as numbers become `0.0`, which the controller reads as a perfect link → it *raises* shaping rate into congestion. This is the inverse-of-safe failure.

**How to avoid:**
- **Build the parser from captured real fping output samples** (the milestone already calls for this) covering: success, partial loss, total loss (`-`), unreachable/ICMP-error lines, the quiet-mode stderr summary, and a truncated trailing line. Unit-test each.
- **Loss must map to "no sample," never to `0ms`.** Distinguish "host responded with RTT" from "host did not respond." Return per-host `None` for non-responses (matches `RTTSnapshot.per_host_results: dict[str, float | None]`).
- Pin `-C <n>` (per-probe RTT arrays, machine-friendly) and force `LC_ALL=C` in the subprocess env so the decimal separator and field labels are stable regardless of host locale.
- Mirror IRTT's discipline: parse even on non-zero exit (fping returns non-zero when *any* host is unreachable — see Pitfall 5), and return `None` only when *nothing* parseable was produced.
- Only count the trailing line if complete; with one-shot `subprocess.run` (Pitfall 1) the output is whole at exit, eliminating partial-line risk entirely — another reason to prefer one-shot.

**Warning signs:**
Candidate reports implausibly low/zero RTT during a known-bad window; loss events show as RTT dips instead of gaps; parser test corpus lacks a total-loss / unreachable fixture; RTT distribution has a spike at exactly `0.0`.

**Phase to address:**
Backend-implementation phase (parser + fixtures). The captured-sample unit tests are a hard gate before benchmarking.

---

### Pitfall 5: Exit-code / loss semantics treated as failure (or success) incorrectly

**What goes wrong:**
The backend treats fping's non-zero exit as "measurement failed" and discards valid RTT data for the reflectors that *did* respond — or conversely treats exit 0 as "all good" and never notices a reflector is dark.

**Why it happens:**
fping exits non-zero if *any* target is unreachable (exit 1) or on bad arguments (exit 3+). In a multi-reflector fanout, one dead reflector makes the whole invocation exit non-zero even though 3 of 4 succeeded. A wrapper that keys off return code alone throws away good data. The IRTT wrapper already learned this exact lesson ("IRTT returns non-zero on 100% packet loss but stdout may still be valid" → parse output even on non-zero exit).

**How to avoid:**
- **Decouple exit code from data validity: always parse stdout, then decide.** Exit code is advisory, not authoritative.
- Aggregate over responding reflectors only (the existing path already does median-of-3 / mean-of-2 / single over `successful_rtts`). One dark reflector should degrade quorum, not the whole cycle.
- Reserve hard-fail for exit codes meaning *bad invocation* (3/4 — syntax/permission), which indicate a config/seam bug, not network loss.

**Warning signs:**
`successful_count` collapses to 0 whenever a single reflector flaps; logs show "fping failed (exit 1)" while other reflectors were clearly reachable; A/B candidate has systematically fewer valid cycles than baseline for no network reason.

**Phase to address:**
Backend-implementation phase. Cross-check against baseline cycle-success rate in the benchmarking phase.

---

### Pitfall 6: 50ms cycle-budget regression from fork/exec in the wrong place

**What goes wrong:**
The fping backend adds fork/exec/parse cost to the hot path, pushing cycle p99 past the 50ms budget. Production baseline is `cycle_total.avg_ms≈2.86, p99≈6.9` over tens of thousands of samples — there is headroom, but fork/exec of a subprocess is ~ms-scale and *variable*, and doing it inline at 20 Hz would be reckless.

**Why it happens:**
Replacing an in-process raw-socket call (icmplib, sub-ms, no syscall fork) with a subprocess fork/exec/wait/parse is orders of magnitude more expensive and far more jittery (scheduler, page faults, ELF load). If the measurement is left **inline in `run_cycle()`** (as steering's `_measure_current_rtt_with_retry()` currently is for the synchronous path) instead of on the background thread, every cycle eats the subprocess cost.

**How to avoid:**
- **Keep fping off the synchronous control-loop path.** Run it on `BackgroundRTTThread` at the existing decoupled cadence; the control loop reads the cached snapshot lock-free. This is the architecture that already makes icmplib cheap from the loop's perspective.
- Benchmark idle **and** under load, comparing `cycle_total` and `steering_rtt_measurement`/`rtt_background_cycle` p50/p99 against the icmplib baseline. Pre-register a "no cycle p99 regression beyond X%" gate (the milestone calls for this).
- Account for CPU: 20 Hz × N reflectors × fork/exec is real CPU on the shaper host; measure CPU% delta, not just latency.
- Use `OperationProfiler`/`PerfTimer` already wired into both threads — no new instrumentation needed.

**Warning signs:**
`cycle_total.p99` climbs above ~7ms baseline; overrun_count rises; CPU% on the shaper increases noticeably; `rtt_background_cycle` profiler shows fork/exec jitter; watchdog margin shrinks.

**Phase to address:**
Benchmarking/cycle-budget phase. The "no regression" gate is a hard accept/reject criterion before the live A/B.

---

### Pitfall 7: Fallback that silently masks failure (fail-open into wrong shaping)

**What goes wrong:**
When fping is missing, stalls, or returns garbage, an over-eager fallback quietly substitutes another source (icmplib, stale cache, history average, autorate health) **without surfacing that the selected backend isn't actually running** — so the operator believes they're A/B-ing fping while production silently runs icmplib (or stale data), and the "no regression" result is meaningless.

**Why it happens:**
The milestone *requires* automatic fallback when fping is missing (no hard dependency) — correct for resilience, dangerous for evidence. The steering daemon already has a layered fallback chain (`autorate_health` → `autorate_irtt` → `history_fallback` → `unavailable`) with source-attribution counters (`_rtt_source_counts`, `rtt_source` health block). A new backend fallback that doesn't *attribute* which backend produced the sample makes silent masking invisible. Worse: stale-prefer-`None` + history fallback can keep steering "working" on data that no longer reflects reality.

**How to avoid:**
- **Make backend selection observable and attributed.** Extend the existing `rtt_source` health surface to record *which RTT backend* (icmplib vs fping) produced each sample, and a count of fallback activations. The A/B must read this to confirm the candidate backend actually ran.
- **Fallback must log loudly the first time and stay counted** (mirror `IRTTMeasurement._log_failure`: WARN-once then DEBUG, INFO on recovery, monotonic failure counter). Silent fallback is forbidden in the A/B window.
- Distinguish *configured backend unavailable* (fping not installed → loud, expected during dev) from *configured backend failing at runtime* (stall/parse error → alarming).
- A/B acceptance must require a minimum fraction of cycles served by the *intended* backend; otherwise the comparison is confounded (see Pitfall 8).

**Warning signs:**
`rtt_source` shows `history_fallback`/`autorate_health` dominating during a supposed fping A/B; fallback counter non-zero but no WARN logged; identical RTT distributions for "icmplib leg" and "fping leg" (smell: both legs actually ran icmplib).

**Phase to address:**
Backend-implementation phase (attribution + loud fallback). A/B-methodology phase (minimum-intended-backend-fraction gate).

---

### Pitfall 8: A/B methodology traps — confounded comparison, weak-evidence flip, no rollback anchor

**What goes wrong:**
The A/B "proves" fping wins (or loses) for reasons unrelated to the backend: the two legs ran at different times of day / different congestion, on different reflector sets, with different counts/intervals, or one leg silently fell back (Pitfall 7). Or the default is flipped to fping on a handful of cycles or one quiet evening. Or there's no clean rollback anchor, so reverting after a regression is improvised.

**Why it happens:**
Network latency is non-stationary (diurnal load, DOCSIS contention, BGP path drift — the v1.47 `tcp_12down` matrix was literally contaminated by mid-run BGP drift). Sequential A/B (icmplib for a while, then fping) confounds backend with time. Different probe parameters (count, interval, reflector list) between legs confound backend with measurement config. The pull to "ship it, looked better" is strong on a control loop you're tired of babysitting.

**How to avoid:**
- **Hold everything constant except the backend:** same reflectors, same count/interval, same `source_ip`/`-S`, same aggregation, same host. The *only* variable is icmplib-vs-fping.
- **Prefer concurrent / interleaved comparison over long sequential legs** where feasible: run both backends against the same reflectors in the same window and compare per-cycle, so diurnal load is shared. If that's impractical in the live consumer, use multiple matched windows and treat single-window deltas as suspect (v1.47/v1.49 precedent: matched windows, pre-registered thresholds, BGP-overlay exclusion).
- **Pre-register accept/reject thresholds *before* looking at data** (the milestone requires this): RTT agreement vs icmplib within tolerance, no loss-detection regression, no cycle-budget regression (Pitfall 6), minimum intended-backend cycle fraction (Pitfall 7), stability (no new restarts/stalls over a soak).
- **Rollback anchor first, always.** Capture a Snapshot-A-style anchor (config + version + the icmplib default), prove the revert path *before* flipping, and keep `icmplib` the default unless fping *clearly* wins. The milestone's stance — "stay on icmplib unless A/B clearly wins" — is the correct bias; honor it.
- **A negative/inconclusive result is a valid close.** "Keep icmplib, document the finding" ships the milestone (v1.46/v1.47/v1.49 evidence-milestone precedent). Do not manufacture a flip.

**Warning signs:**
Single-window evidence driving a default flip; legs run on different days with no overlap; reflector list or probe count differs between legs; "win" margin within measurement noise / CI overlaps; rollback never rehearsed; pressure to flip "because we built it."

**Phase to address:**
A/B-methodology + verdict phase. Threshold pre-registration and rollback-anchor capture are entry gates to the live A/B, not afterthoughts.

---

### Pitfall 9: A/B-ing a code path the live consumer doesn't exercise

**What goes wrong:**
You swap the backend in `RTTMeasurement.ping_host()` and benchmark it, but **production steering in cake-autorate mode doesn't take its live RTT from that call** — it reads RTT from the bridge-written autorate state (`measure_current_rtt()`: `autorate_health` → `autorate_irtt` → `history_fallback`). So the "live steering consumer A/B" measures a path steering isn't actually using right now, and the result doesn't transfer.

**Why it happens:**
The deployment moved to cake-autorate on both WANs (2026-06-08); `wanctl@` is the dormant rollback path. Steering still constructs an `RTTMeasurement` object, but in the live external-controller topology its authoritative RTT comes through the state bridge from cake-autorate's *own* fping pinger — which is a separate (shell) measurement, not wanctl's Python `RTTMeasurement`. wanctl's native `RTTMeasurement`/`BackgroundRTTThread` is fully exercised only by **native autorate** (dormant) and the steering *synchronous-ping* fallback path. It's easy to refactor the backend seam, pass all unit tests, benchmark green — and never touch the bytes that produce the steering signal in production.

**How to avoid:**
- **Pin down, before scoping the A/B, exactly where the live steering RTT originates in cake-autorate mode**, and target the A/B at *that* producer. If the live signal is cake-autorate's own fping, the wanctl-side fping backend A/B validates the *capability and parser*, not the production signal — say so explicitly and don't overclaim.
- If the intent is to validate wanctl's fping backend as a *steering RTT source*, the A/B must route steering to consume wanctl's `RTTMeasurement` (the synchronous/`BackgroundRTTThread` path) for the comparison window, with a clean revert to the bridge source. That is itself a controller-path change and must be gated/anchored.
- Be explicit in the verdict about which consumer was actually exercised. The milestone says "native autorate inherits the capability via the shared path but is not stood up for validation" — so the A/B's reach is the *steering* path; confirm that path is the one carrying the live signal, or scope the claim down.

**Warning signs:**
Backend swap merged, tests green, but `rtt_source` in steering health still shows `autorate_health` (not the new backend) throughout the A/B; the A/B numbers come from a benchmark harness, not from the live steering daemon's own measurements; verdict claims "validated on live consumer" while production RTT provenance is the bridge.

**Phase to address:**
Requirements / A/B-design phase (provenance mapping is an entry gate). Verdict phase (scope the claim to what was actually exercised).

---

### Pitfall 10: Breaking the SAFE zero-diff discipline carelessly now that it's intentionally lifted

**What goes wrong:**
Because the streak is being broken "by design," the team relaxes the *whole* discipline and lets the diff sprawl beyond the RTT-measurement seam into unrelated controller logic (state machine, thresholds, EWMA, fusion, CAKE signal), introducing latent regressions that the 9-milestone zero-diff streak was specifically protecting against.

**Why it happens:**
"We're touching the controller path anyway" is a slippery permission. The SAFE invariant historically used an explicit allowlist + a fail-closed source-diff verifier (SAFE-07 verifier "fails closed on dirty/staged/untracked `src/wanctl/` surfaces"). Lifting the invariant entirely instead of *narrowing the allowlist* removes the guardrail at the exact moment risk is highest.

**How to avoid:**
- **Narrow, don't abolish.** Define a v1.53 allowlist scoped to the RTT-measurement seam: `rtt_measurement.py` (backend abstraction + fping backend), the explicit per-WAN config keys, and the *minimal* wiring in `autorate_continuous.py` / `steering/daemon.py` needed to select the backend. Everything else — state machine, thresholds, EWMA/dwell/deadband, fusion, `cake_signal.py`, `wan_controller.py` control logic — stays zero-diff and is verified at every phase boundary, same mechanics as SAFE-07..16.
- Keep the seam *additive*: `icmplib` refactored *behind* the abstraction with byte-equivalent behavior as the default, so the no-fping-selected path is provably unchanged. Add a test that the icmplib-default path produces identical results to pre-refactor.
- Run the source-diff verifier against the narrowed allowlist at each boundary and at milestone close. A control-logic diff outside the seam is a fail-closed stop.

**Warning signs:**
Diff touches `wan_controller.py`/`cake_signal.py`/fusion/threshold files "while we're in here"; the icmplib-default path's outputs changed vs the pre-refactor baseline; no narrowed allowlist defined; verifier disabled "because the invariant is lifted."

**Phase to address:**
Every phase boundary (allowlist verifier). The narrowed-allowlist definition is an entry gate to the first implementation phase; the icmplib-default-unchanged proof is a gate on the refactor phase.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Long-lived `fping -l` loop process instead of one-shot per burst | Slightly lower fork overhead; "feels" like real-time | Reintroduces the entire pipe-buffer STALL class (Pitfall 1), zombie/orphan risk on restart, partial-line parsing | Never for v1.53 — one-shot is strictly safer and the cadence doesn't need streaming |
| Reuse `parse_ping_output()` regex for fping | No new parser | Silently misses fping loss markers / `-C` arrays / quiet-mode stderr → loss read as `0ms` (Pitfall 4) | Never — build an fping-specific parser from captured samples |
| Hardcode a single `-S` source address | Quick to wire | Breaks multi-WAN (ATT vs Spectrum) source binding (Pitfall 3) | Never — seam must carry per-WAN `source_ip` |
| Inline subprocess call in `run_cycle()` | Simplest wiring | Per-cycle fork/exec blows the 50ms budget (Pitfall 6) | Never — use `BackgroundRTTThread` |
| Flip default to fping after one good window | Ships the milestone faster | Confounded/weak-evidence flip; possible silent fallback masking (Pitfalls 7,8) | Never — pre-registered thresholds + matched windows + rollback anchor required |
| Lift SAFE invariant entirely instead of narrowing | Less ceremony | Latent controller regressions the 9-milestone streak prevented (Pitfall 10) | Never — narrow the allowlist, keep the verifier |

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| `fping` binary | Assume it's present; hard-crash if missing | `shutil.which("fping")` gate + automatic icmplib fallback with loud first-time WARN (IRTT pattern) |
| `fping` version | Assume native line buffering | Require ≥ 4.3 for line-buffered stdout, *or* (better) use one-shot `subprocess.run` so buffering is moot; parse `fping -v` and warn below 4.3 |
| systemd unit stdout | Assume TTY line-buffering | stdout is a pipe → block-buffered; one-shot invocation or `stdbuf --output=L` (Pitfall 1) |
| Source binding (`-S`) | Pass hostname / omit / hardcode | Emit `-S <per-WAN source_ip>`; assert egress WAN via binding test (Pitfall 3) |
| Locale (`LC_NUMERIC`) | Inherit host locale → `12,3` decimals | Force `LC_ALL=C` in subprocess env |
| Exit code | `returncode != 0` ⇒ discard data | Always parse stdout; exit code advisory; one dead reflector ≠ failed cycle (Pitfall 5) |
| cake-autorate's own fping | Assume swapping wanctl's backend changes the live steering signal | Map RTT provenance first — live signal may come via the bridge, not wanctl `RTTMeasurement` (Pitfall 9) |

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Per-cycle fork/exec at 20 Hz | `cycle_total.p99` > 7ms, CPU% climb, overruns | Probe on `BackgroundRTTThread`; loop reads cached snapshot | Immediately at 50ms cycle under any load |
| fork/exec jitter under memory pressure | Bimodal `rtt_background_cycle`; occasional multi-ms spikes | One-shot run with bounded timeout; soak-measure p99 not just avg | Under shaper-host load / page-fault pressure |
| Reflector fanout × subprocess | Linear CPU growth with reflector count | Single fping invocation with multiple targets (fping's strength) rather than N subprocesses | As reflector count grows (currently 3-4 → 8) |
| Stale-prefer-`None` hiding a dead backend | Steering "works" on frozen RTT | Cycle-status (`successful_count=0`) + fallback attribution surfaced in health | When the backend silently stops producing |

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| `shell=True` / string-interpolated reflectors into fping cmd | Command injection via config-controlled reflector/source values | Build `cmd` as a list (IRTT pattern, `# noqa: S603` on the hardcoded invocation); never `shell=True` |
| Running fping setuid/elevated unnecessarily | Privilege surface | fping needs raw-socket cap like icmplib (`CAP_NET_RAW`); grant the cap, don't run as root broadly |
| Trusting reflector list / source_ip from unvalidated config | Probes to attacker-chosen targets / spoofed source | Validate `source_ip` is locally assigned; validate reflectors at config load |

## UX / Operability Pitfalls

| Pitfall | Operator Impact | Better Approach |
|---------|-----------------|-----------------|
| Backend selection invisible in `/health` | Can't tell which backend is live during A/B | Extend `rtt_source` health block to attribute backend (icmplib/fping) + fallback count |
| Silent fallback | Operator thinks fping is running; it's icmplib/stale | Loud WARN-once + counter + health surface (Pitfall 7) |
| No rollback verb / anchor | Improvised revert under pressure during a regression | Snapshot-A anchor + rehearsed revert before flip (Pitfall 8) |
| Verdict overclaims "validated on live consumer" | False confidence | Scope claim to the path actually exercised (Pitfall 9) |

## "Looks Done But Isn't" Checklist

- [ ] **fping backend:** Often missing — verify it runs **under a real systemd unit** (pipe stdout), not just an interactive shell; confirm no STALL over a soak.
- [ ] **One-shot vs loop:** Verify the design uses one-shot `subprocess.run` (or proven line-buffering) — check there's no long-lived `-l` process that can buffer-stall.
- [ ] **Source binding:** Verify `-S <source_ip>` is emitted per WAN and a binding-assertion test proves probes egress the intended WAN (ATT `.227` vs Spectrum `.226/.223`).
- [ ] **Loss semantics:** Verify total-loss / unreachable / `-` markers map to "no sample," never `0ms`; corpus includes a total-loss fixture.
- [ ] **Exit code:** Verify non-zero exit with partial reflector success still yields valid aggregated RTT.
- [ ] **Cycle budget:** Verify `cycle_total` p99 and CPU% measured idle **and** under load vs icmplib baseline (`p99≈6.9` anchor); gate pre-registered.
- [ ] **Zombies/fds/tasks:** Verify no defunct children, fd leak, or systemd `Tasks:` growth over a soak.
- [ ] **Fallback attribution:** Verify `/health` shows which backend produced samples + fallback count; silent fallback impossible.
- [ ] **A/B provenance:** Verify the A/B actually exercised the live steering RTT producer (not a dead path) — `rtt_source` reflects the intended backend during the window.
- [ ] **icmplib default unchanged:** Verify the no-fping path is byte-/behavior-equivalent to pre-refactor (regression test).
- [ ] **SAFE narrowed allowlist:** Verify the source-diff verifier runs against the narrowed allowlist at every boundary; no control-logic diff outside the seam.
- [ ] **Rollback anchor:** Verify Snapshot-A captured and revert rehearsed before any default flip.

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| fping STALL in production A/B | LOW | Existing fallback/stale-prefer-`None` carries; flip backend config back to icmplib (anchor); root-cause buffering offline |
| `-S` mismatch → wrong-WAN data | MEDIUM | Invalidate the A/B window (data is garbage); fix seam to emit correct `-S`; re-run binding test; restart A/B |
| Loss parsed as `0ms` (raised into congestion) | HIGH | Controller may have shaped/steered wrong during window; revert to icmplib, audit shaping decisions in window, fix parser + add total-loss fixture, re-A/B |
| Weak-evidence flip already shipped | MEDIUM | Revert default to icmplib via anchor; re-run matched-window A/B with pre-registered thresholds before re-flipping |
| Control-logic diff leaked outside seam | MEDIUM-HIGH | Source-diff verifier should have caught it at boundary; revert the out-of-seam diff; re-prove icmplib-default unchanged |
| A/B-d a dead path | LOW (process) | Re-scope: map live RTT provenance, route steering to the intended producer for the window or downscope the verdict claim |

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| 1. Pipe-buffer STALL | Backend-implementation (one-shot design) | Soak under real systemd unit; no STALL; bimodal-latency check |
| 2. Subprocess lifecycle/zombies | Backend-implementation | Soak: zombie/fd/Tasks counts flat |
| 3. Source-binding `-S` | Backend-implementation (seam carries `source_ip`) | Binding-assertion test before live A/B |
| 4. Output parsing edge cases | Backend-implementation (parser + captured-sample fixtures) | Unit tests incl. total-loss/unreachable/partial-line/locale |
| 5. Exit-code/loss semantics | Backend-implementation | Partial-reflector-success yields valid RTT test |
| 6. 50ms cycle-budget regression | Benchmarking phase | `cycle_total` p99 + CPU idle/load vs baseline; pre-registered gate |
| 7. Silent fallback masking | Backend-implementation (attribution) + A/B phase | `/health` backend attribution; min-intended-backend-fraction gate |
| 8. A/B methodology / weak flip / no anchor | A/B-design + verdict phase | Pre-registered thresholds; matched windows; rehearsed rollback |
| 9. A/B-ing a dead path | Requirements/A/B-design phase | RTT-provenance map; `rtt_source` shows intended backend in window |
| 10. SAFE discipline sprawl | Every phase boundary | Narrowed-allowlist source-diff verifier; icmplib-default-unchanged proof |

## Sources

- In-repo: `src/wanctl/rtt_measurement.py` (icmplib hot path, `source=`, `BackgroundRTTThread`, stale-prefer-`None`), `src/wanctl/irtt_measurement.py` + `irtt_thread.py` (existing subprocess-backend precedent: `shutil.which`, `subprocess.run` timeout, parse-on-nonzero-exit, flock, failure-log-level, return-`None`), `src/wanctl/steering/daemon.py` (`measure_current_rtt` fallback chain, `rtt_source` health attribution, inline retry path), `src/wanctl/autorate_continuous.py` (`source_ip=config.ping_source_ip`) — HIGH
- Live production config: `configs/cake-autorate/config.spectrum.sh` (`pinger_method=fping`, `ping_extra_args="-S 10.10.110.223"` — fping+source-binding proven viable on this host); `configs/att.yaml` / `configs/spectrum.yaml` (`ping_source_ip`, reflector lists) — HIGH
- Project: `.planning/PROJECT.md` v1.53 milestone (SAFE streak break, A/B target, cycle baseline `p99≈6.9`); v1.47/v1.49 evidence-milestone precedent (matched windows, BGP-drift contamination, negative-result-is-valid-close) — HIGH
- fping changelog: line-buffered stdout added v4.3 (2020-07-11, #179); SIGQUIT summary; per-lost-packet output v5.0 — https://fping.org/dist/CHANGELOG.md — HIGH
- Unix stdout buffering (4096-byte block buffer on pipes, line-buffer only on TTY; `stdbuf --output=L`) — https://www.turnkeylinux.org/blog/unix-buffering — HIGH
- cake-autorate pinger architecture (fping default round-robin; iputils-ping alternate; per-instance bash+fping processes; `$pinger_binary`/`pinger_method`) — https://github.com/lynxthecat/cake-autorate (README/CHANGELOG/INSTALLATION) — MEDIUM
- fping options reference (`-l`, `-c`, `-C`, `-p`, `-S`, `-t`, `-q`, scriptable output) — https://linux.die.net/man/8/fping, https://netbeez.net/blog/linux-how-to-use-fping/ — MEDIUM

---
*Pitfalls research for: pluggable fping/subprocess RTT backend in a 50ms adaptive CAKE/steering control loop (wanctl v1.53)*
*Researched: 2026-06-13*
