# Production Ops

Current operational guidance based on live production observation.

## 2026-04-16

### Current Read

Production is usable and materially better than it was before the recent investigation.

The multi-WAN cross-coupling issue appears fixed:
- ATT no longer gets dragged down materially when Spectrum is under synthetic stress.
- Distinct IRTT targets plus fusion protection were the key stabilizers.

The remaining production risk is localized to Spectrum:
- Spectrum is the higher-capacity path.
- Spectrum is also the noisier path under stress.
- Short ICMP blackout / measurement-collapse windows can still happen on Spectrum and recover automatically.

ATT is the calmer but smaller path:
- Lower throughput ceiling under heavy RRUL-style load.
- Better behaved operationally.
- Suitable as the quality / protection path rather than the bulk path.

### Practical WAN Roles

Treat the WANs differently on purpose:
- Spectrum: bulk/default path
- ATT: stability-sensitive / protection / failover path

Do not expect one tuning profile to make the two WANs behave the same. The current controller now exposes their different path characteristics more honestly instead of masking them.

### Recent Stress Findings

#### Spectrum

Observed pattern:
- Higher throughput ceiling under RRUL and downstream bulk load
- Can hit aggressive rate cuts under stress
- Can still show brief all-reflector collapse windows and cached-RTT reuse
- Usually recovers back to GREEN without operator action

Operational interpretation:
- Spectrum remains production-usable
- Spectrum is still the "problem child"
- Remaining issues look more like path/ISP behavior under stress than a major controller defect

#### ATT

Observed pattern:
- Lower throughput ceiling under the same 12-stream RRUL hammer
- Cleaner behavior under load
- Much less pathological churn

Representative result from dev-bound ATT hammer:
- RRUL 12 TCP streams, source bound to the ATT-routed dev IP
- TCP download sum about 65.9 Mbps
- TCP upload sum about 14.5 Mbps
- ATT degraded during the run, Spectrum stayed clean

Operational interpretation:
- ATT is not the fast path
- ATT is the steady path

### Current Production Posture

Recommended posture right now:
- Leave production logic and timing alone
- Keep Spectrum as primary bulk path
- Keep ATT as the calmer secondary/protection path
- Avoid live micro-tuning unless there is a specific, repeatable production symptom to target

### Known Remaining Risk

Bounded Spectrum reflector and measurement blackouts still occur occasionally.

Current judgment:
- Recoverable
- Not a broad controller failure
- Worth watching, but not worth more live tuning right now

If this reopens later, the next investigation should focus on:
- Spectrum path instability during blackout windows
- Whether those windows correlate with real ISP or load events
- Avoiding further live tuning experiments that change polling or timing without a very tight hypothesis
