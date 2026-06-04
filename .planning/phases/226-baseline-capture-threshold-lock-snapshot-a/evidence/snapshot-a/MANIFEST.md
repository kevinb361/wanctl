# Snapshot A Manifest

## Captured UTC

- Captured: 2026-06-04T11:05:28Z

## Source Posture

read-only; no deploy, restart, CAKE-mode change, traffic generation, nft mutation, tc mutation, /etc/wanctl write, or production write was performed.

## Health Source URL

- Spectrum health URL: http://10.10.110.223:9101/health

## Deployed Version

- Spectrum /health version: 1.45.0
- Spectrum /health status: healthy
- Health uptime_seconds: 411188.0

## Repo Version

- __version__: 1.47.0
- pyproject.toml version: 1.47.0

## Pre-Deploy Git Ref

- commit_sha: 7e84f43ee2748f8c104ab651c7f0b0b3b44d45c2
- tree_sha_configs: 2efe1e7a8d85a994263de6d9c01bff38aafb77aa
- blob_sha_configs_spectrum_yaml: 1d7ba35c464745bb7679e9f3ec99ffe72e7c1307

## Deployed Config Equality

- deployed_redacted_sha256: 97bd6f0d170601f1196cdaa3d36540715a95c9e85d3af44e3a484627e04b4f9f
- repo_redacted_sha256: 97bd6f0d170601f1196cdaa3d36540715a95c9e85d3af44e3a484627e04b4f9f
- raw_deployed_spectrum_sha256: 9da3ea8e1d7543d93118004b8002ead56b6cf52cccda61d45ecc211469507dfc
- verdict: equal

## Raw Artifact Restore Path

- raw_dir: /tmp/opencode/wanctl-phase226-snapshot-a-raw-20260604T1115Z
- raw_restore_source: /tmp/opencode/wanctl-phase226-snapshot-a-raw-20260604T1115Z/deployed-spectrum.yaml
- restore_destination: /etc/wanctl/spectrum.yaml
- operator_private: true
- committed: false

## Artifacts

- repo-spectrum.redacted.yaml — redacted repo configs/spectrum.yaml.
- deployed-spectrum.redacted.yaml — redacted deployed /etc/wanctl/spectrum.yaml.
- tc-qdisc-spec-router.txt — read-only sudo tc -s qdisc show dev spec-router.
- tc-qdisc-spec-modem.txt — read-only sudo tc -s qdisc show dev spec-modem.
- bridge-qos.live.txt — read-only sudo nft list table bridge qos.
- repo-bridge-qos.nft — repo deploy/nftables/bridge-qos.nft copy.
- pre-deploy-git-ref.txt — commit, configs tree, and configs/spectrum.yaml blob SHA.
- snapshot-a-health.bound.redacted.json — Spectrum /health baseline.
- repo-version.txt — repo version fields.
- artifact-sha256.txt — sha256 inventory for redacted evidence and operator-private raw restore sources.
- /tmp/opencode/wanctl-phase226-snapshot-a-raw-20260604T1115Z/deployed-spectrum.yaml — unredacted raw restore source, operator-private.
- /tmp/opencode/wanctl-phase226-snapshot-a-raw-20260604T1115Z/deployed-spectrum.source-path.txt — restore destination marker, operator-private.

## Artifact SHA256

- 97bd6f0d170601f1196cdaa3d36540715a95c9e85d3af44e3a484627e04b4f9f  /home/kevin/projects/wanctl/.planning/phases/226-baseline-capture-threshold-lock-snapshot-a/evidence/snapshot-a/deployed-spectrum.redacted.yaml
- 97bd6f0d170601f1196cdaa3d36540715a95c9e85d3af44e3a484627e04b4f9f  /home/kevin/projects/wanctl/.planning/phases/226-baseline-capture-threshold-lock-snapshot-a/evidence/snapshot-a/repo-spectrum.redacted.yaml
- cf858eb534db8ecd5f0473b5482e9b6ebdbbf2a6a38c7fa839c7cb1ca8986e4f  /home/kevin/projects/wanctl/.planning/phases/226-baseline-capture-threshold-lock-snapshot-a/evidence/snapshot-a/tc-qdisc-spec-router.txt
- 438a3339aee9007dbb7aaf51a95763f2d7b8a20429f161eec1385b9a426dcd2b  /home/kevin/projects/wanctl/.planning/phases/226-baseline-capture-threshold-lock-snapshot-a/evidence/snapshot-a/tc-qdisc-spec-modem.txt
- e41927a92247676969ddc838c8000e67019141aebdfa0baa46ab0c8a6432422e  /home/kevin/projects/wanctl/.planning/phases/226-baseline-capture-threshold-lock-snapshot-a/evidence/snapshot-a/bridge-qos.live.txt
- 4adcd458ce054d16299dec751cf1ba6c6697afb2f1d5e548dc865adcb1ac54b7  /home/kevin/projects/wanctl/.planning/phases/226-baseline-capture-threshold-lock-snapshot-a/evidence/snapshot-a/repo-bridge-qos.nft
- b8e0905abcb21bcacd03278edf3220d9f660a5c37c5472ea5bf6f617274262de  /home/kevin/projects/wanctl/.planning/phases/226-baseline-capture-threshold-lock-snapshot-a/evidence/snapshot-a/pre-deploy-git-ref.txt
- 368f4c2e5fa115f9803315d812bab4be7531f8b7ede95e0a7496b139c8971e2c  /home/kevin/projects/wanctl/.planning/phases/226-baseline-capture-threshold-lock-snapshot-a/evidence/snapshot-a/snapshot-a-health.bound.redacted.json
- 6df8365456c89c6c24906f4f97806bcdd7b1ca4e638988d2629e61550115339d  /home/kevin/projects/wanctl/.planning/phases/226-baseline-capture-threshold-lock-snapshot-a/evidence/snapshot-a/repo-version.txt
- 9da3ea8e1d7543d93118004b8002ead56b6cf52cccda61d45ecc211469507dfc  /tmp/opencode/wanctl-phase226-snapshot-a-raw-20260604T1115Z/deployed-spectrum.yaml
- cecf787ad5b61f588109cd73368acaa2bf0c0622293a4516960d3b6101637245  /tmp/opencode/wanctl-phase226-snapshot-a-raw-20260604T1115Z/deployed-spectrum.source-path.txt

## Targeted Revert Sequence

Scope note: this manifest proves config-artifact equality and command identity only. It does not claim runtime qdisc restoration, sudo/install permission validity at rollback time, or service-reload behavior; those require a live drill out of scope for Phase 226.

1. Confirm local checkout is at the intended rollback context: `git checkout 7e84f43ee2748f8c104ab651c7f0b0b3b44d45c2`.
2. Restore `<raw-dir>/deployed-spectrum.yaml` to `/etc/wanctl/spectrum.yaml`: `ssh cake-shaper sudo -n install -m 0640 -o root -g wanctl /dev/stdin /etc/wanctl/spectrum.yaml < <raw-dir>/deployed-spectrum.yaml`.
3. Verify restored config bytes during Phase 228 rollback proof with a read-only remote sha256 comparison.
