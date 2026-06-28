# Phase 261 — Rollback Anchor Evidence (RECON-02)

**Timestamp:** 2026-06-28T22:59 UTC
**Host:** cake-shaper (referenced by name only)

## Code Anchor (D-02)

- **ANCHOR_DIR:** /var/lib/wanctl/phase261-backups/20260628T225946Z/
- **Tarball:** opt-wanctl.tgz
- **Tarball SHA256:** 28c25d406531a6a30042e4674abd8c176fdda5ea772e807aa335e6ed372f376d
- **Tarball readable:** yes (tar -tzf succeeded)
- **Free disk:** 12G of 29G (59%) — sufficient for anchor + extract

## Scratch Restore Drill

Extracted tarball into mktemp scratch dir, per-file sha256-diff against live /opt/wanctl (excluding *.pyc/__pycache__). Diff empty.

**Verdict: PHASE261_RESTORE_DRILL_PASS**

Scratch dir cleaned up. No service bounced, no /opt/wanctl touched.

## One-Command Code Revert

```
ssh cake-shaper 'sudo systemctl stop steering.service; sudo tar -C /opt -xzf /var/lib/wanctl/phase261-backups/20260628T225946Z/opt-wanctl.tgz; sudo systemctl start steering.service'
```

## Host Config Backups (non-/opt write-set coverage)

Location: <ANCHOR_DIR>/host-config-pre-deploy/ (mirroring absolute paths)

Backed up files (sudo cp -a, preserving owner/mode):
- etc/wanctl/steering.yaml (sha: b8cc6244d5e617ef11a081cf654e30a6d5ae5708d9da965b5d2f48403ab01bcd)
- etc/wanctl/spectrum.yaml (sha: 7d64982361eabb4d7041d187f92b20d4e947aa18adefe5d0d8b844a35fa29ba1)
- etc/wanctl/att.yaml (sha: 6daa1a0f971284569fad19cc10cd58de8660f279ccdf7040f6e5b028247a7479)
- etc/cake-autorate/config.spectrum.sh (sha: bc44a9edd4dad0b6e36f0aeaff0c7f5a5c13efa5565c11cb0908586777b920d3)
- etc/cake-autorate/config.att.sh (sha: 52808576f512628dac0a7acce762b051760e1441adf3e096c93e26c28cecb4b5)
- etc/systemd/system/steering.service (sha: 1ea0c07cbebace6fb4ebcffa0f57485af5733cfcd6b34b9b05891afaa3f27ece)
- etc/systemd/system/cake-autorate-spectrum.service (sha: 1348925c06eaf9ff8e59b7e7f57b984673decdd0f6d1df97874000263e2002b1)
- etc/systemd/system/cake-autorate-att.service (sha: a63aff9764c4e30daa5316989732151755f6984579843511b168d66e0515dd0a)
- etc/systemd/system/cake-autorate-spectrum-state-bridge.service (sha: 53afd7ba8313a654f81c53b8da0e1510299f977020e968712417b1f86dd5521c)
- etc/systemd/system/cake-autorate-att-state-bridge.service (sha: 2152b147e7c0733cc7cd28e7510465a90841c5a4a0322a786e8031a7901cd427)
- etc/sysctl.d/99-wanctl-network.conf (sha: cabe4c1b5b11e851c61f2cce3e95f8525398628c1dc5124dc205058b82f3347b)

## Helper Script SHA Baseline (non-controller, reproducible from repo)

Pre-deploy sha256 of helper scripts deploy.sh installs:
- /usr/local/sbin/cake-autorate-spectrum-qdisc-init: 28ca62236f4e64501f048152a6a95eebdade9ebac58ae83a1903f93efaede881
- /usr/local/sbin/cake-autorate-spectrum-state-bridge: cde33afc0a889c8a431dcccf1c1b51e4dc10db4611a0ce454ac3dc4aaf495bee
- /usr/local/sbin/cake-autorate-att-qdisc-init: 13cf091de0849e3913229921ec4939d6f29bcb3865cb363265a2fe7884de41ee
- /usr/local/sbin/cake-autorate-att-state-bridge: cde33afc0a889c8a431dcccf1c1b51e4dc10db4611a0ce454ac3dc4aaf495bee
- /usr/local/sbin/wanctl-bpctl-watchdog-petter: f0423eb77b93ddbedd3c91794c94f117fdfa10def99d03924fe53fdfca54a6fc
- /usr/local/sbin/wanctl-bpctl-watchdog-bypass: cd9001ce2c6c6aa8c3c9e0d13c16c596c67c3167ca19c26f53db1abfd7fb4b87
- /usr/local/bin/wanctl-nic-tuning.sh: 8364d09f75b24c0c53a2e8c4166b78ff0c820f796bcec1b4efe5a53aa395221d
- /usr/local/bin/wanctl-bridge-qos.sh: 9231b3fdda5f0a1b720c86b95776448322c8df29432527e340360cc594a1e21e
- /opt/scripts/profiling_collector.py: e1900d8f5ffb57ba9cd22d41a69af29ee06e2e40a99b718517df2920ed9e24ec
- /opt/scripts/analyze_profiling.py: 67f44b7d41a4059503dc8e985cebfe8f54cf123a7a858dbc85b3ac9493e66cc2
- /opt/docs/PROFILING.md: aa5b3c051ee8bb775cc83667c8e49ee313c01a4caf9144d2dcf90945ac10a80f

## Full Deploy.sh Write-Set Classification Table

Every path deploy.sh writes is classified into exactly one bucket:

| Path | Bucket | Evidence |
|------|--------|----------|
| /opt/wanctl/* | backed-up | opt-wanctl.tgz tarball anchor |
| /etc/wanctl/steering.yaml | backed-up | host-config-pre-deploy + sha |
| /etc/wanctl/spectrum.yaml | backed-up | host-config-pre-deploy + sha |
| /etc/wanctl/att.yaml | backed-up | host-config-pre-deploy + sha |
| /etc/cake-autorate/config.spectrum.sh | backed-up | host-config-pre-deploy + sha |
| /etc/cake-autorate/config.att.sh | backed-up | host-config-pre-deploy + sha |
| /etc/systemd/system/steering.service | backed-up | host-config-pre-deploy + sha |
| /etc/systemd/system/cake-autorate-spectrum.service | backed-up | host-config-pre-deploy + sha |
| /etc/systemd/system/cake-autorate-att.service | backed-up | host-config-pre-deploy + sha |
| /etc/systemd/system/cake-autorate-*-state-bridge.service | backed-up | host-config-pre-deploy + sha |
| /etc/sysctl.d/99-wanctl-network.conf | backed-up | host-config-pre-deploy + sha |
| /etc/systemd/system/wanctl@.service | reproducible-from-repo | tracked in deploy/systemd/ |
| /etc/systemd/system/nic-tuning.service | reproducible-from-repo | tracked in deploy/systemd/ |
| /etc/systemd/system/bridge-qos.service | reproducible-from-repo | tracked in deploy/systemd/ |
| /etc/systemd/system/silicom-bypass-watchdog@.service | reproducible-from-repo | tracked in deploy/systemd/ |
| /usr/local/sbin/cake-autorate-*-qdisc-init | sha-baselined | pre-deploy sha recorded above |
| /usr/local/sbin/cake-autorate-*-state-bridge | sha-baselined | pre-deploy sha recorded above |
| /usr/local/sbin/wanctl-bpctl-watchdog-* | sha-baselined | pre-deploy sha recorded above |
| /usr/local/bin/wanctl-nic-tuning.sh | sha-baselined | pre-deploy sha recorded above |
| /usr/local/bin/wanctl-bridge-qos.sh | sha-baselined | pre-deploy sha recorded above |
| /opt/scripts/profiling_collector.py | sha-baselined | pre-deploy sha recorded above |
| /opt/scripts/analyze_profiling.py | sha-baselined | pre-deploy sha recorded above |
| /opt/docs/PROFILING.md | sha-baselined | pre-deploy sha recorded above |
| /opt/wanctl/scripts/{analyze_baseline,validate-deployment,wanctl-history,...} | reproducible-from-repo | tracked in scripts/, deploy.sh installs |
| /etc/wanctl/bpctl-watchdog/{att,spectrum}.env | install-if-absent | deploy.sh writes only if missing |
| systemctl daemon-reload | documented-non-issue | reversible by another daemon-reload |
| venv/pip state | documented-non-issue | deploy.sh rsyncs source only, no pip |

## Documented Non-Issues

(a) deploy.sh performs NO venv/pip install — rsyncs source only, no dependency-state mutation.
(b) deploy.sh performs NO unit enable/start/disable in main path — only daemon-reload (reversible).
(c) /etc/wanctl/steering.yaml additionally handled by Plan 02 preserve/restore safeguard.
(d) /etc/wanctl/bpctl-watchdog/*.env: install-if-absent only — never overwrites existing.

## One-Command Host-Config Revert

```
ssh cake-shaper 'sudo cp -a /var/lib/wanctl/phase261-backups/20260628T225946Z/host-config-pre-deploy/etc/* /etc/; sudo systemctl daemon-reload'
```

## Verdict

Every enumerated path classified into exactly one bucket. No unclassified paths.

**PHASE261_FULL_WRITESET_ROLLBACK_COVERED**
