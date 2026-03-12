# Requirements: wanctl

**Defined:** 2026-03-11
**Core Value:** Sub-second congestion detection with 50ms control loops

## v1.15 Requirements

Requirements for Alerting & Notifications milestone. Each maps to roadmap phases.

### Alert Events

- [ ] **ALRT-01**: Autorate daemon fires alert when WAN stays in RED or SOFT_RED beyond configurable duration
- [ ] **ALRT-02**: Steering daemon fires alert when steering is activated (traffic rerouted to secondary)
- [ ] **ALRT-03**: Steering daemon fires alert when steering is deactivated (traffic returns to primary)
- [ ] **ALRT-04**: Daemon fires alert when health endpoint target becomes unreachable beyond configurable duration
- [ ] **ALRT-05**: Daemon fires alert when previously unreachable endpoint recovers
- [ ] **ALRT-06**: Autorate daemon fires alert when baseline RTT drifts beyond configurable threshold
- [ ] **ALRT-07**: Autorate daemon fires alert when rapid congestion state flapping is detected

### Delivery

- [ ] **DLVR-01**: Alerts delivered via Discord webhook with color-coded embeds (red=critical, yellow=warning, green=recovery)
- [ ] **DLVR-02**: Alert embeds include event type, severity, affected WAN, relevant metrics, and timestamp
- [ ] **DLVR-03**: Webhook delivery retries with backoff on transient HTTP failures
- [ ] **DLVR-04**: Generic webhook interface allows adding new formatters (ntfy.sh, etc.) without engine changes

### Infrastructure

- [x] **INFRA-01**: Per-event-type cooldown suppression with configurable duration per alert type
- [x] **INFRA-02**: YAML `alerting:` configuration section with rules, thresholds, cooldowns, and webhook URL
- [x] **INFRA-03**: Fired alerts persisted to SQLite with timestamp, type, severity, WAN, and details
- [ ] **INFRA-04**: Alert history queryable via `wanctl-history` CLI (e.g., `--alerts` flag)
- [x] **INFRA-05**: Alerting disabled by default, opt-in via `alerting.enabled: true`
- [ ] **INFRA-06**: Health endpoint exposes alerting state (enabled, recent alert count, active cooldowns)

## Future Requirements

### Delivery

- **DLVR-F01**: ntfy.sh push notification delivery
- **DLVR-F02**: Generic HTTP POST with customizable payload template

### Steering Event Log

- **SEVT-01**: Steering decision log showing recent transitions with timestamps and reasons
- **SEVT-02**: Daemon-side ring buffer API endpoint for transition events

## Out of Scope

| Feature | Reason |
|---------|--------|
| ML-based anomaly detection | Simple threshold/heuristic detection sufficient for home network |
| Alert aggregation/grouping | Per-event cooldown handles flood suppression adequately |
| Web UI for alert management | CLI and YAML config sufficient |
| Email delivery | Discord/webhook covers notification needs |
| Alert acknowledgment/silencing | Cooldowns handle suppression; operator intervention not needed |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| ALRT-01 | Phase 78 | Pending |
| ALRT-02 | Phase 78 | Pending |
| ALRT-03 | Phase 78 | Pending |
| ALRT-04 | Phase 79 | Pending |
| ALRT-05 | Phase 79 | Pending |
| ALRT-06 | Phase 79 | Pending |
| ALRT-07 | Phase 79 | Pending |
| DLVR-01 | Phase 77 | Pending |
| DLVR-02 | Phase 77 | Pending |
| DLVR-03 | Phase 77 | Pending |
| DLVR-04 | Phase 77 | Pending |
| INFRA-01 | Phase 76 | Complete |
| INFRA-02 | Phase 76 | Complete |
| INFRA-03 | Phase 76 | Complete |
| INFRA-04 | Phase 80 | Pending |
| INFRA-05 | Phase 76 | Complete |
| INFRA-06 | Phase 80 | Pending |

**Coverage:**
- v1.15 requirements: 17 total
- Mapped to phases: 17
- Unmapped: 0

---
*Requirements defined: 2026-03-11*
*Last updated: 2026-03-11 after roadmap creation*
