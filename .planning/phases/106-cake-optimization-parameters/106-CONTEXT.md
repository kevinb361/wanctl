# Phase 106: CAKE Optimization Parameters - Context

**Gathered:** 2026-03-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Define and apply the full CAKE parameter sets for each WAN link and direction. Upload gets ack-filter, download gets ingress+ecn, each link gets its overhead keyword. Parameters stored as YAML config with ecosystem-validated defaults. `initialize_cake()` from Phase 105 applies them at startup. No factory wiring (Phase 107), no steering integration (Phase 108).

</domain>

<decisions>
## Implementation Decisions

### Parameter Storage
- **D-01:** Dual-layer storage — hardcoded ecosystem-validated defaults for boolean flags (split-gso always on, ack-filter on upload, ingress+ecn on download) PLUS YAML config for operator-tunable values (overhead keyword, memlimit, rtt, bandwidth limits).
- **D-02:** Config can override defaults. If YAML specifies `ack-filter: false`, it overrides the upload default. This allows operators to disable features if they cause problems.
- **D-03:** Default parameter construction builds a complete params dict by merging defaults + config, then passes to `initialize_cake()`.

### Per-Link Parameters (Locked by Ecosystem Research)
- **D-04:** Upload CAKE (modem-side NIC egress): `diffserv4 split-gso ack-filter <overhead-keyword> memlimit 32mb rtt <rtt-value>`
- **D-05:** Download CAKE (router-side NIC egress): `diffserv4 split-gso ingress ecn <overhead-keyword> memlimit 32mb rtt <rtt-value>`
- **D-06:** Spectrum overhead: `docsis` keyword (= overhead 18, mpu 64, noatm)
- **D-07:** ATT overhead: `bridged-ptm` keyword (= overhead 22, noatm)
- **D-08:** Explicitly excluded: `nat` (no conntrack on bridge), `wash` (DSCP marks must survive), `autorate-ingress` (wanctl IS the autorate system)

### Overhead Keywords
- **D-09:** Use tc overhead keywords (`docsis`, `bridged-ptm`) in YAML config, not raw numeric values. Keywords are self-documenting and canonical per tc-cake(8). The keyword is a string in YAML: `overhead: "docsis"`.

### RTT Parameter
- **D-10:** `rtt` is configurable in YAML with default `100ms`. Not hardcoded to 50ms.
- **D-11:** `rtt` is a candidate for adaptive tuning (v1.20 infrastructure). The tuning system can adjust it per-link based on observed latency. Not implemented in this phase — just declared as tunable.

### Memlimit
- **D-12:** Default `memlimit: "32mb"` for ~1Gbps links. Configurable per-link in YAML.

### Claude's Discretion
- YAML config schema structure (how cake_params section is organized)
- Builder function/class design for constructing params dict from config + defaults
- Test fixtures and assertion patterns
- Whether to add a helper for per-direction param construction

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Backend Implementation (Phase 105 output)
- `src/wanctl/backends/linux_cake.py` — `initialize_cake(params)` and `validate_cake(expected)` methods that consume the params dict this phase constructs
- `tests/test_linux_cake_backend.py` — Existing tests for initialize_cake param handling

### Ecosystem Research
- `.planning/research/OPENSOURCE-CAKE.md` — Exact tc command patterns per link type (§Recommended CAKE Setup Commands), parameter rationale table, overhead keywords
- `.planning/research/FEATURES.md` — Feature categorization (table stakes vs differentiators)
- `.planning/research/STACK.md` — tc-cake(8) parameter reference

### Config Patterns
- `src/wanctl/autorate_config.py` — Existing Config class with YAML loading patterns
- `src/wanctl/config_validation_utils.py` — Existing validation patterns (deprecate_param, schema checks)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `LinuxCakeBackend.initialize_cake(params: dict)` — already handles all params as generic dict (Phase 105)
- `LinuxCakeBackend.validate_cake(expected: dict)` — already validates params via readback (Phase 105)
- `autorate_config.py` Config class — YAML loading, nested section parsing
- `config_validation_utils.py` — deprecate_param(), schema validation helpers

### Established Patterns
- Config sections are YAML dicts loaded into Python dicts or dataclass attributes
- Boolean flags stored as `key: true/false` in YAML
- Overhead/encap values stored as strings (e.g., `overhead: "docsis"`)
- Config validation at startup, not per-cycle

### Integration Points
- Phase 106 output (param builder) feeds into Phase 107 (factory wiring) and Phase 109 (VM startup)
- `initialize_cake()` is called during daemon startup, before the 50ms control loop begins
- `validate_cake()` is called immediately after `initialize_cake()` to verify

</code_context>

<specifics>
## Specific Ideas

- Exact tc commands from OPENSOURCE-CAKE.md research:
  - Spectrum upload: `tc qdisc replace dev $NIC root cake bandwidth ${RATE}kbit diffserv4 split-gso ack-filter docsis memlimit 32mb`
  - Spectrum download: `tc qdisc replace dev $NIC root cake bandwidth ${RATE}kbit diffserv4 split-gso ingress ecn docsis memlimit 32mb`
  - ATT upload: same as Spectrum but `bridged-ptm` instead of `docsis`
  - ATT download: same pattern with `bridged-ptm`
- Per-tin order in diffserv4: index 0=Bulk, 1=BestEffort, 2=Video, 3=Voice
- DSCP marks from RB5009 mangle rules are preserved through the L2 bridge

</specifics>

<deferred>
## Deferred Ideas

- Adaptive tuning of `rtt` parameter — infrastructure exists in v1.20, integration deferred
- `diffserv8` mode for finer classification — would require mangle rule expansion
- Per-tin bandwidth allocation tuning — custom tin ratios

</deferred>

---

*Phase: 106-cake-optimization-parameters*
*Context gathered: 2026-03-24*
