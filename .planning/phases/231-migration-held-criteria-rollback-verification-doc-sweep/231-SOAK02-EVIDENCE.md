# Phase 231 SOAK-02 Evidence: Rollback Verification Provable Path

**Captured:** 2026-06-10T13:43:33Z  
**Scope:** read-only rollback preflight + documented rollback/return procedure; no production mutation  
**Verdict:** SOAK-02 PROVABLE-PATH PASS — rollback to native `wanctl@{wan}` is trivially provable for both WANs by a double-gated script, live read-only preflight, committed command renders, and historical ATT exercise citation.

## Safety Boundary

- Live host contact was read-only: `systemctl cat`, `systemctl is-enabled`, `systemctl is-active`, and `sudo -n test -f`/`test -x` precondition checks over SSH.
- No `systemctl start/stop/enable/disable`, no `tc qdisc replace`, no bpctl command, and no target-host writes were executed.
- `scripts/phase231-rollback.sh --dry-run` renders mutation commands locally only; dry-run did not invoke SSH.
- Confirm mode remains gated behind BOTH `--confirm` and `--i-have-operator-approval` and is not executed by this evidence capture.

## Documented Procedure

The executable source of truth is `scripts/phase231-rollback.sh`. The rendered procedures below were captured from dry-run mode and committed under `evidence/`.

### ATT rollback and return-to-cake procedure

Command:

```bash
bash scripts/phase231-rollback.sh --wan att --dry-run
```

Captured output (`evidence/rollback-dry-run-att.txt`):

```text
Phase 231 SOAK-02 rollback plan for att (mutation only with --confirm --i-have-operator-approval)

Expected watchdog states:
  - spectrum: silicom-bypass-watchdog@spectrum.service active in external mode and native rollback mode; rollback leaves it untouched.
  - att: silicom-bypass-watchdog-cake-autorate-att.service active in external mode; silicom-bypass-watchdog@att.service inactive until native rollback.

Rollback sequence:
  sudo systemctl disable --now cake-autorate-att.service cake-autorate-att-state-bridge.service silicom-bypass-watchdog-cake-autorate-att.service
  sudo systemctl enable --now wanctl@att.service silicom-bypass-watchdog@att.service
  sleep 8
  cd /opt/bpctl-silicom
  sudo ./bpctl_util att-modem set_disc off
  sudo ./bpctl_util att-modem set_bypass off
  sudo ./bpctl_util att-modem reset_bypass_wd >/dev/null || true
  sudo tc qdisc replace dev att-router root cake bandwidth 95Mbit diffserv4 triple-isolate ingress nonat nowash no-ack-filter split-gso rtt 35ms ptm overhead 22 mpu 64 memlimit 32Mb
  sudo tc qdisc replace dev att-modem root cake bandwidth 18Mbit diffserv4 triple-isolate egress nonat nowash ack-filter split-gso rtt 35ms ptm overhead 22 mpu 64 memlimit 32Mb

Return-to-cake sequence (production steady state after any live exercise):
  sudo systemctl disable --now wanctl@att.service silicom-bypass-watchdog@att.service
  sudo systemctl enable --now cake-autorate-att.service cake-autorate-att-state-bridge.service silicom-bypass-watchdog-cake-autorate-att.service
  # qdisc re-init is handled by /usr/local/sbin/cake-autorate-att-qdisc-init via ExecStartPre
```

### Spectrum rollback and return-to-cake procedure

Command:

```bash
bash scripts/phase231-rollback.sh --wan spectrum --dry-run
```

Captured output (`evidence/rollback-dry-run-spectrum.txt`):

```text
Phase 231 SOAK-02 rollback plan for spectrum (mutation only with --confirm --i-have-operator-approval)

Expected watchdog states:
  - spectrum: silicom-bypass-watchdog@spectrum.service active in external mode and native rollback mode; rollback leaves it untouched.
  - att: silicom-bypass-watchdog-cake-autorate-att.service active in external mode; silicom-bypass-watchdog@att.service inactive until native rollback.

Rollback sequence:
  sudo systemctl disable --now cake-autorate-spectrum.service cake-autorate-spectrum-state-bridge.service
  sudo systemctl enable --now wanctl@spectrum.service
  sleep 8
  sudo tc qdisc replace dev spec-router root cake bandwidth 550Mbit diffserv4 triple-isolate nonat wash no-ack-filter split-gso rtt 25ms noatm overhead 18 mpu 64 memlimit 64Mb
  sudo tc qdisc replace dev spec-modem root cake bandwidth 18Mbit diffserv4 triple-isolate nonat wash ack-filter split-gso rtt 25ms noatm overhead 18 mpu 64 memlimit 64Mb

Return-to-cake sequence (production steady state after any live exercise):
  sudo systemctl disable --now wanctl@spectrum.service
  sudo systemctl enable --now cake-autorate-spectrum.service cake-autorate-spectrum-state-bridge.service
  # silicom-bypass-watchdog@spectrum.service stays active in both modes; do not stop/disable it here.
  # qdisc re-init is handled by /usr/local/sbin/cake-autorate-spectrum-qdisc-init via ExecStartPre
```

## Preflight Proof

Commands:

```bash
bash scripts/phase231-rollback.sh --wan att --preflight --out .planning/phases/231-migration-held-criteria-rollback-verification-doc-sweep/evidence/rollback-preflight-att.json
bash scripts/phase231-rollback.sh --wan spectrum --preflight --out .planning/phases/231-migration-held-criteria-rollback-verification-doc-sweep/evidence/rollback-preflight-spectrum.json
```

Proof JSON files:

- `evidence/rollback-preflight-att.json` — `overall_pass: true`, captured `2026-06-10T13:43:26Z`.
- `evidence/rollback-preflight-spectrum.json` — `overall_pass: true`, captured `2026-06-10T13:43:33Z`.

### Per-check preflight summary

| WAN | Check | Raw output | Verdict |
|-----|-------|------------|---------|
| att | `systemctl cat wanctl@.service` | `# /etc/systemd/system/wanctl@.service ... ExecStart=/usr/bin/python3 /opt/wanctl/autorate_continuous.py --config /etc/wanctl/%i.yaml` | PASS |
| att | `systemctl is-enabled wanctl@att.service` | `disabled` | PASS |
| att | `systemctl is-active wanctl@att.service` | `inactive` | PASS |
| att | `sudo -n test -f /etc/wanctl/att.yaml` | empty stdout, exit 0 | PASS |
| att | `test -f /opt/wanctl/autorate_continuous.py` | empty stdout, exit 0 | PASS |
| att | `systemctl cat cake-autorate-att.service` | contains `Conflicts=wanctl@att.service` | PASS |
| att | `systemctl is-active cake-autorate-att.service` | `active` | PASS |
| att | `systemctl is-active cake-autorate-att-state-bridge.service` | `active` | PASS |
| att | `systemctl is-active silicom-bypass-watchdog-cake-autorate-att.service` | `active` | PASS |
| att | `systemctl is-active silicom-bypass-watchdog@att.service` | `inactive` | PASS |
| att | `test -x /opt/bpctl-silicom/bpctl_util` | empty stdout, exit 0 | PASS |
| att | `systemctl cat silicom-bypass-watchdog@.service` | contains `EnvironmentFile=/etc/wanctl/bpctl-watchdog/%i.env` | PASS |
| att | `sudo -n test -f /etc/wanctl/bpctl-watchdog/att.env` | empty stdout, exit 0 | PASS |
| spectrum | `systemctl cat wanctl@.service` | `# /etc/systemd/system/wanctl@.service ... ExecStart=/usr/bin/python3 /opt/wanctl/autorate_continuous.py --config /etc/wanctl/%i.yaml` | PASS |
| spectrum | `systemctl is-enabled wanctl@spectrum.service` | `disabled` | PASS |
| spectrum | `systemctl is-active wanctl@spectrum.service` | `inactive` | PASS |
| spectrum | `sudo -n test -f /etc/wanctl/spectrum.yaml` | empty stdout, exit 0 | PASS |
| spectrum | `test -f /opt/wanctl/autorate_continuous.py` | empty stdout, exit 0 | PASS |
| spectrum | `systemctl cat cake-autorate-spectrum.service` | contains `Conflicts=wanctl@spectrum.service` | PASS |
| spectrum | `systemctl is-active cake-autorate-spectrum.service` | `active` | PASS |
| spectrum | `systemctl is-active cake-autorate-spectrum-state-bridge.service` | `active` | PASS |
| spectrum | `systemctl is-active silicom-bypass-watchdog@spectrum.service` | `active` | PASS |

The committed JSON files preserve the full raw stdout/stderr for each check plus the rendered rollback and return-to-cake sequences.

## Historical Exercise

The same ATT rollback shape was previously exercised on 2026-06-05 and recorded in `.planning/cake-autorate-trials/WANCTL_CAKE_AUTORATE_FUTURE.md`:

- disabled/stopped `cake-autorate-att.service`
- disabled/stopped `cake-autorate-att-state-bridge.service`
- enabled/started `wanctl@att.service`
- restored ATT qdiscs to native baseline:
  - `att-router`: `95Mbit diffserv4 triple-isolate ingress nonat nowash no-ack-filter split-gso rtt 35ms ptm overhead 22 mpu 64 memlimit 32Mb`
  - `att-modem`: `18Mbit diffserv4 triple-isolate egress nonat nowash ack-filter split-gso rtt 35ms ptm overhead 22 mpu 64 memlimit 32Mb`

That historical exercise is supporting evidence for the provable path; the current SOAK-02 proof is the fresh read-only preflight plus documented double-gated procedure above.

## Operator Decision

PENDING CHECKPOINT — Task 3 must record one explicit operator choice:

1. **Default/recommended:** Provable path accepted — no production mutation.
2. **Opt-in only:** Live rollback exercise on one named WAN, only after explicit approval and followed by return-to-cake verification.

The SOAK-01 ordering gate is satisfied before this checkpoint: `.planning/phases/231-migration-held-criteria-rollback-verification-doc-sweep/231-SOAK01-EVIDENCE.md` exists and contains `SOAK-01 PASS` with operator-approved evidence.

## One-Line Verdict

SOAK-02 PROVABLE-PATH PASS: both WAN rollback procedures are documented by a double-gated script, both WANs passed live read-only preflight (native units disabled/inactive, configs/code present, Conflicts guards present, external units active, watchdog states correct), dry-run renders the exact rollback and return-to-cake sequences, and no production mutation occurred.
