---
phase: quick
plan: 260503-cfs
type: execute
wave: 1
depends_on: []
files_modified:
  - "/etc/wanctl/spectrum.yaml (production, on cake-shaper)"
  - "/etc/wanctl/att.yaml (production, on cake-shaper) — verify-only"
autonomous: false
requirements: []

must_haves:
  truths:
    - "Spectrum YAML alerting.rules.congestion_flapping carries a valid severity ∈ {info, warning, critical}"
    - "ATT YAML alerting.rules.congestion_flapping carries a valid severity (or document why not)"
    - "Post-restart journal does NOT show 'alerting.rules.congestion_flapping missing required severity; disabling alerting' on either WAN"
  artifacts:
    - path: "/etc/wanctl/spectrum.yaml"
      provides: "alerting.rules.congestion_flapping.severity present"
---

<objective>
Restore congestion_flapping alerting on Spectrum (and verify ATT) by adding the missing `severity` key to the per-WAN YAML rule. Surfaced 2026-05-03 during Phase 200 Plan 06 deploy work: every wanctl restart on Spectrum emits `alerting.rules.congestion_flapping missing required 'severity'; disabling alerting`, which silently turns off ALL alerting (autorate_config.py:707-713 fail-closes the whole alerting subsystem on any rule validation error).

Spectrum has been running with alerting silently disabled since 2026-04-17 when `cooldown_sec: 600` was added to the rule (operator note in YAML: "Raised from default on 2026-04-17: 2026-04-16 DOCSIS event produced 16 alerts (8 DL + 8 UL) for one 30-min oscillation"). The cooldown bump preserved the rule presence but dropped or never had the required severity field.

Purpose: production observability — congestion_flapping alerts are the primary operator surface for DOCSIS oscillation events; without severity the rule is silently rejected.
</objective>

<context>
Validator location: src/wanctl/autorate_config.py:699-721 (`_validate_alerting_rules`).
Current Spectrum YAML excerpt (production):

```yaml
alerting:
  rules:
    congestion_flapping:
      cooldown_sec: 600  # Raised from default on 2026-04-17: 2026-04-16 DOCSIS event produced 16 alerts (8 DL + 8 UL) for one 30-min oscillation. 600s caps firings at ~3 per event while preserving detection.
      # severity: <missing>  ← root cause
```

Default rule shape used elsewhere in codebase: `severity: warning` is the typical choice for congestion_flapping per the alert engine's intended classification (operator notification, non-critical).
</context>

<tasks>

<task type="checkpoint:human-action" gate="blocking">
  <name>Task 1: Operator adds severity to Spectrum YAML on cake-shaper, restarts service, verifies clean journal</name>
  <how-to-verify>
    Operator-driven (production YAML change):

    ```bash
    ssh kevin@10.10.110.223 "sudo cp /etc/wanctl/spectrum.yaml /etc/wanctl/spectrum.yaml.bak.260503"
    ssh kevin@10.10.110.223 "sudo $EDITOR /etc/wanctl/spectrum.yaml"
    # Add 'severity: warning' under alerting.rules.congestion_flapping
    ssh kevin@10.10.110.223 "sudo systemctl restart wanctl@spectrum.service"
    sleep 6
    ssh kevin@10.10.110.223 "sudo journalctl -u wanctl@spectrum.service --since '1 minute ago' \
      | grep -E 'alerting|congestion_flapping' | head -10"
    # Expect: no 'missing required severity' line; expect 'Alerting: enabled (N rules configured)'
    ```

    Then verify ATT does not have the same regression:

    ```bash
    ssh kevin@10.10.110.223 "sudo grep -A3 'congestion_flapping:' /etc/wanctl/att.yaml | head -10"
    ```
  </how-to-verify>
</task>

<task type="auto">
  <name>Task 2: Update repo example/template YAML so future deploys carry severity by default</name>
  <action>
    If `configs/spectrum.yaml.example` (or whatever the repo-side reference is) has the same gap, add `severity: warning` under `alerting.rules.congestion_flapping` and commit the fix. Verify with `grep -A3 'congestion_flapping:' configs/*.yaml*`.
  </action>
</task>

</tasks>

<verification>
- `sudo journalctl -u wanctl@spectrum.service --since '1 minute ago' | grep 'Alerting: enabled'` returns a line.
- No `missing required 'severity'` warning in journal post-restart.
- ATT verified clean (or scheduled for the same fix).
- Repo-side YAML examples carry severity for the rule.
</verification>

<success_criteria>
1. Spectrum production YAML has `alerting.rules.congestion_flapping.severity: warning` (or other valid value).
2. Service restart produces no severity-missing warning.
3. Alerting reports as enabled in startup logs.
4. Repo-side example/template YAML carries severity for the congestion_flapping rule (so future operators don't drop it again).
</success_criteria>
