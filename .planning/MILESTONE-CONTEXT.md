# Milestone Context

**Generated:** 2026-01-14
**Status:** Ready for /gsd:new-milestone

<features>
## Features to Build

- **Phase2B Enablement**: Enable confidence-based steering after dry-run validation period
- **Timer Interval Fix**: Fix Phase2B timer decrement to use actual cycle interval instead of hardcoded 2s
- **Config Documentation**: Document EWMA alphas and baseline_rtt_bounds in CONFIG_SCHEMA.md
- **Baseline Bounds in Autorate**: Add baseline_rtt_bounds validation to autorate_continuous.py for consistency
- **Deprecation Warnings**: Add warnings for legacy params (bad_samples → red_samples_required, good_samples → green_samples_required)
- **Config Edge Case Tests**: Test special characters, long queue names, boundary values in config validation

</features>

<scope>
## Scope

**Suggested name:** v1.2 Configuration & Polish
**Estimated phases:** 5
**Focus:** Complete Phase2B rollout, improve configuration documentation and validation

</scope>

<phase_mapping>
## Phase Mapping

- Phase 16: Timer Interval Fix - Fix Phase2B timer decrement bug (prerequisite for Phase2B)
- Phase 17: Config Documentation - Document EWMA alphas, baseline_rtt_bounds; add bounds to autorate
- Phase 18: Deprecation Warnings - Add warnings for legacy steering params
- Phase 19: Config Edge Case Tests - Boundary conditions, special characters, long names
- Phase 20: Phase2B Enablement - Enable confidence-based steering (set dry_run: false)

</phase_mapping>

<constraints>
## Constraints

- Timer fix must precede Phase2B enablement
- No breaking changes - deprecation warnings only, don't remove legacy params
- Phase2B enablement should wait for adequate dry-run validation data

</constraints>

<notes>
## Additional Context

**Phase2B Safeguards:**
- Sustain timer (2s) prevents transient triggers
- Hold-down timer (30s) prevents rapid recovery
- Flap detection increases threshold on rapid toggles
- Easy rollback: set `dry_run: true` and restart

**Current Dry-Run Status:**
- Phase2B enabled in dry-run mode on cake-spectrum
- Logging WOULD_ENABLE/WOULD_DISABLE decisions
- Validated working during netperf stress test (2026-01-14)

</notes>

---

*This file is temporary. It will be deleted after /gsd:new-milestone creates the milestone.*
