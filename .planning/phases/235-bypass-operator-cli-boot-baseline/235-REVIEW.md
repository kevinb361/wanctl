---
phase: 235-bypass-operator-cli-boot-baseline
reviewed: 2026-06-12T16:16:37Z
depth: standard
files_reviewed: 7
files_reviewed_list:
  - scripts/silicom-bypass
  - scripts/deploy.sh
  - tests/test_silicom_bypass_cli.py
  - deploy/scripts/silicom-bypass.conf.example
  - deploy/systemd/silicom-bypass-init.service
  - deploy/systemd/bpctl-silicom.service
  - docs/SILICOM-BYPASS.md
findings:
  critical: 1
  warning: 2
  info: 0
  total: 3
status: issues_found
---

# Phase 235: Code Review Report

**Reviewed:** 2026-06-12T16:16:37Z
**Depth:** standard
**Files Reviewed:** 7
**Status:** issues_found

## Summary

Reviewed the Silicom bypass operator CLI, standalone deploy path, systemd boot baseline units, tests, example config, and runbook. The CLI itself is conservative about destructive card mutations (`--yes`, read-back assertions, and dual-WAN non-NIC guard), but the deploy and boot/operator surfaces have a few production-safety issues to fix before treating this as hardened.

## Critical Issues

### CR-01: Predictable `/tmp` staging before privileged install can be raced on the target

**File:** `scripts/deploy.sh:528-544`

**Issue:** `deploy_silicom_bypass()` copies root-installed executables and systemd units to predictable paths under `/tmp` (`/tmp/silicom-bypass`, `/tmp/wanctl-bpctl-init`, `/tmp/$basename`) and then runs `sudo mv` into privileged locations. On any target with another local user/process, the window between `scp` and `sudo mv` allows replacement/race of those predictable paths, potentially installing attacker-controlled content as root. This is especially risky because the installed files become root-run WAN/bypass control surface.

**Fix:** Stage into a per-deploy remote directory created by `mktemp -d`, restrict it to the SSH user, copy into that directory, then move from there and remove it. Example pattern:

```bash
remote_tmp=$(ssh "$TARGET_HOST" "mktemp -d /tmp/wanctl-silicom.XXXXXX")
ssh "$TARGET_HOST" "chmod 700 '$remote_tmp'"
scp "$PROJECT_ROOT/scripts/silicom-bypass" "$TARGET_HOST:$remote_tmp/silicom-bypass"
ssh "$TARGET_HOST" "sudo install -o root -g root -m 0755 '$remote_tmp/silicom-bypass' /usr/local/sbin/silicom-bypass"
# repeat for the other artifacts, then:
ssh "$TARGET_HOST" "rm -rf '$remote_tmp'"
```

Prefer `install -o root -g root -m ...` over separate `mv/chown/chmod` so mode and ownership are applied atomically at the destination.

## Warnings

### WR-01: `RemainAfterExit=yes` makes documented manual baseline starts a no-op after boot

**File:** `deploy/systemd/silicom-bypass-init.service:11` and `docs/SILICOM-BYPASS.md:153-157`

**Issue:** `silicom-bypass-init.service` is a oneshot with `RemainAfterExit=yes`. After it has run once, systemd considers it active, so the documented manual exercise command (`systemctl start silicom-bypass-init.service`) will not rerun `ExecStart`. For a production bypass baseline, that can give an operator false confidence that the baseline was re-applied when no bpctl commands actually ran.

**Fix:** Either remove `RemainAfterExit=yes` from the baseline unit, or update the runbook to use `systemctl restart silicom-bypass-init.service` for manual re-application. For this unit, the safer default is likely:

```ini
[Service]
Type=oneshot
ExecStart=/usr/local/sbin/silicom-bypass baseline
```

### WR-02: Standalone deploy ignores extra positional arguments in Silicom-only mode

**File:** `scripts/deploy.sh:811-818`

**Issue:** In `--silicom-bypass-only` mode, the parser stores the first positional argument in `WAN_NAME` and the second in `TARGET_HOST`, but the handler unconditionally resets `TARGET_HOST="$WAN_NAME"`. If an operator accidentally supplies an extra positional argument, the script silently deploys to the first host and ignores the second. For a live bypass control install, ambiguous target selection should fail closed.

**Fix:** Reject extra positional arguments and conflicting deployment mode flags before mutating anything:

```bash
if [[ "$SILICOM_BYPASS_ONLY" == "true" ]]; then
    if [[ -z "$WAN_NAME" || -n "$TARGET_HOST" ]]; then
        print_error "Usage: $0 --silicom-bypass-only <target_host> [--dry-run]"
        usage
        exit 1
    fi
    if [[ "$WITH_STEERING" == "true" || "$WITH_SPECTRUM_CAKE_AUTORATE" == "true" || "$WITH_ATT_CAKE_AUTORATE" == "true" ]]; then
        print_error "--silicom-bypass-only cannot be combined with WAN deployment options"
        exit 1
    fi
    TARGET_HOST="$WAN_NAME"
    ...
fi
```

---

_Reviewed: 2026-06-12T16:16:37Z_  
_Reviewer: the agent (gsd-code-reviewer)_  
_Depth: standard_
