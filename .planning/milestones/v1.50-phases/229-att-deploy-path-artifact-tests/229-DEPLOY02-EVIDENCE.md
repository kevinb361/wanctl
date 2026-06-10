# Phase 229 DEPLOY-02 Evidence: ATT Artifact Live-vs-Repo Diff

**Captured:** 2026-06-09
**Host:** `cake-shaper`
**Command:** `bash scripts/phase229-att-artifact-diff.sh cake-shaper`
**Boundary:** read-only; remote access crossed SSH only through `sudo -n cat <live_path> | sha256sum`.
**Source of truth:** repo artifacts.

## DEPLOY-02 Verdict

**DEPLOY-02: PASS** — all six repo-owned ATT cake-autorate artifacts are byte-equal to the live hand-deployed copies on `cake-shaper`.

| artifact | repo_sha | live_sha | verdict | disposition |
|---|---|---|---|---|
| `configs/cake-autorate/config.att.sh` | `52808576f512628dac0a7acce762b051760e1441adf3e096c93e26c28cecb4b5` | `52808576f512628dac0a7acce762b051760e1441adf3e096c93e26c28cecb4b5` | equal | no drift; no reconciliation needed |
| `deploy/scripts/cake-autorate-att-qdisc-init` | `13cf091de0849e3913229921ec4939d6f29bcb3865cb363265a2fe7884de41ee` | `13cf091de0849e3913229921ec4939d6f29bcb3865cb363265a2fe7884de41ee` | equal | no drift; no reconciliation needed |
| `deploy/scripts/cake-autorate-att-state-bridge` | `cde33afc0a889c8a431dcccf1c1b51e4dc10db4611a0ce454ac3dc4aaf495bee` | `cde33afc0a889c8a431dcccf1c1b51e4dc10db4611a0ce454ac3dc4aaf495bee` | equal | no drift; no reconciliation needed |
| `deploy/systemd/cake-autorate-att.service` | `a63aff9764c4e30daa5316989732151755f6984579843511b168d66e0515dd0a` | `a63aff9764c4e30daa5316989732151755f6984579843511b168d66e0515dd0a` | equal | no drift; no reconciliation needed |
| `deploy/systemd/cake-autorate-att-state-bridge.service` | `2152b147e7c0733cc7cd28e7510465a90841c5a4a0322a786e8031a7901cd427` | `2152b147e7c0733cc7cd28e7510465a90841c5a4a0322a786e8031a7901cd427` | equal | no drift; no reconciliation needed |
| `deploy/systemd/silicom-bypass-watchdog-cake-autorate-att.service` | `3d2cdf5a69d20cd9ab7e0b29d04bc88998b48b7d3c8b473bfcddfc965f8fdb7c` | `3d2cdf5a69d20cd9ab7e0b29d04bc88998b48b7d3c8b473bfcddfc965f8fdb7c` | equal | no drift; no reconciliation needed |

Overall verdict line from the read-only audit:

```text
ALL EQUAL
```

## Raw DEPLOY-02 Output

```text
artifact	repo_sha	live_sha	verdict
configs/cake-autorate/config.att.sh	52808576f512628dac0a7acce762b051760e1441adf3e096c93e26c28cecb4b5	52808576f512628dac0a7acce762b051760e1441adf3e096c93e26c28cecb4b5	equal
deploy/scripts/cake-autorate-att-qdisc-init	13cf091de0849e3913229921ec4939d6f29bcb3865cb363265a2fe7884de41ee	13cf091de0849e3913229921ec4939d6f29bcb3865cb363265a2fe7884de41ee	equal
deploy/scripts/cake-autorate-att-state-bridge	cde33afc0a889c8a431dcccf1c1b51e4dc10db4611a0ce454ac3dc4aaf495bee	cde33afc0a889c8a431dcccf1c1b51e4dc10db4611a0ce454ac3dc4aaf495bee	equal
deploy/systemd/cake-autorate-att.service	a63aff9764c4e30daa5316989732151755f6984579843511b168d66e0515dd0a	a63aff9764c4e30daa5316989732151755f6984579843511b168d66e0515dd0a	equal
deploy/systemd/cake-autorate-att-state-bridge.service	2152b147e7c0733cc7cd28e7510465a90841c5a4a0322a786e8031a7901cd427	2152b147e7c0733cc7cd28e7510465a90841c5a4a0322a786e8031a7901cd427	equal
deploy/systemd/silicom-bypass-watchdog-cake-autorate-att.service	3d2cdf5a69d20cd9ab7e0b29d04bc88998b48b7d3c8b473bfcddfc965f8fdb7c	3d2cdf5a69d20cd9ab7e0b29d04bc88998b48b7d3c8b473bfcddfc965f8fdb7c	equal
ALL EQUAL
```

## SAFE-14 Controller-Path Boundary Proof

**SAFE-14 baseline:** `87980bdf8ea52e5537110cd9bbc7a368f523d2e2` (`87980bdf`), the last docs/planning-only commit before Phase 229 Plan 01/02/03 implementation commits.

**Protected set:**

- `src/wanctl/wan_controller.py`
- `src/wanctl/wan_controller_state.py`
- `src/wanctl/queue_controller.py`
- `src/wanctl/cake_signal.py`
- `src/wanctl/alert_engine.py`
- `src/wanctl/fusion_healer.py`
- `src/wanctl/backends/`

The protected set intentionally uses the `src/wanctl/backends/` directory entry for backend implementations; it does not list non-existent top-level `src/wanctl/linux_cake.py` or `src/wanctl/netlink_cake.py` paths.

### Committed Diff Check

Command:

```bash
git diff --stat 87980bdf -- src/wanctl/wan_controller.py src/wanctl/wan_controller_state.py src/wanctl/queue_controller.py src/wanctl/cake_signal.py src/wanctl/alert_engine.py src/wanctl/fusion_healer.py src/wanctl/backends/
```

Output:

```text

```

### Dirty-Tree Check

Command:

```bash
git status --porcelain -- src/wanctl/wan_controller.py src/wanctl/wan_controller_state.py src/wanctl/queue_controller.py src/wanctl/cake_signal.py src/wanctl/alert_engine.py src/wanctl/fusion_healer.py src/wanctl/backends/
```

Output:

```text

```

## SAFE-14 Verdict

**SAFE-14: PASS** — the controller path has zero committed diff from the pinned Phase 229 baseline and no staged, unstaged, or untracked protected-path changes at the phase boundary.
