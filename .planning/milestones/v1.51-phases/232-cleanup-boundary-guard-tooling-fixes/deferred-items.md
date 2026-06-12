# Phase 232 Deferred Items

## 232-02 — pre-existing ShellCheck info findings

- **Found during:** Plan-level `shellcheck scripts/phase231-rollback.sh scripts/phase231-migration-held.sh`
- **Finding:** `scripts/phase231-migration-held.sh` still emits pre-existing SC2317 info-level unreachable-code findings at `json_string()` / `json_string_compact()` helper locations.
- **Disposition:** Out of scope for 232-02. This plan was scoped to CR-01, WR-02, and WR-01/SC2318; SC2318 is gone and no rollback/controller behavior changes were introduced.
- **Suggested follow-up:** Decide in a future tooling-cleanup task whether to remove unused helper functions or add explicit ShellCheck annotations.
