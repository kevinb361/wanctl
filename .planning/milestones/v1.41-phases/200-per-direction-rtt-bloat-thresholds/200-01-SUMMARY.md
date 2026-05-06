---
phase: 200-per-direction-rtt-bloat-thresholds
plan: 01
status: complete
date: 2026-05-03
requirements-completed: [ARB-05]
decisions-applied: [D-03, D-06]
key-files:
  modified:
    - src/wanctl/autorate_config.py
    - src/wanctl/wan_controller.py
    - src/wanctl/check_config_validators.py
    - tests/conftest.py
    - tests/test_autorate_config.py
    - tests/test_wan_controller.py
next-plan: 200-02 (SAFE-05 expected count update)
one_liner: Replaced value-derived `_upload_thresholds_explicit` flag with two per-key presence flags so live-tuning can no longer silently overwrite operator-explicit UL thresholds when the operator's value happens to equal the DL global; added one-shot INFO log for Plan 06 deploy verification.
---

# Plan 01 Summary — D-03 Codex bug fix

## What changed

**`src/wanctl/autorate_config.py`** — Added two per-key presence flags inside `_load_upload_config`:
```python
self._upload_target_bloat_ms_explicit = "target_bloat_ms" in ul
self._upload_warn_bloat_ms_explicit = "warn_bloat_ms" in ul
```
Driven by `in` membership against the upload dict, so presence (not value) determines the flag.

**`src/wanctl/wan_controller.py`** — Removed the old value-derived `_upload_thresholds_explicit` flag (`grep` confirms zero matches). Replaced with two per-key flags resolved via `getattr(config, ...)` and a one-shot INFO log emission at controller construction when either explicit flag is True. The log line format `phase200 explicit UL thresholds active: upload_target_bloat_ms=42 upload_warn_bloat_ms=105` is the surface Plan 06 Task 2 Step 4 will read via `journalctl` to verify the new thresholds are live (D-06 — no new `/health` field added).

**`_apply_threshold_param`** — Each field now gates on its own per-key flag independently. Live-tuning of `target_bloat_ms` writes UL `target_delta` only if `_upload_target_bloat_ms_explicit` is False; same for `warn_bloat_ms` and `warn_delta`.

**`src/wanctl/check_config_validators.py`** — Verified (no change needed — already on working tree from initial diff): both `continuous_monitoring.upload.target_bloat_ms` and `continuous_monitoring.upload.warn_bloat_ms` are members of `KNOWN_AUTORATE_PATHS`. Plan 03's silent-pass invariant is unblocked.

**`tests/conftest.py`** — Mock fixture `mock_autorate_config` now defaults both new explicit flags to False so unrelated existing tests continue to work without modification.

**`tests/test_autorate_config.py`** — 3 pre-existing schema tests in `TestLoadUploadThresholdConfig` (defaults, override, ordering) verified passing after flag rewrite.

**`tests/test_wan_controller.py`** — Added 2 new tests verifying D-03 invariants:
- `test_upload_thresholds_explicit_when_value_equal_to_global` — operator sets UL key to value equal to DL global; presence flag is True; live-tuning cannot overwrite.
- `test_upload_thresholds_explicit_per_key_independence` — only `target_bloat_ms` set in YAML; `target_delta` is protected, `warn_delta` remains live-tunable.

## Why it matters

Codex pre-review of the original draft caught that `_upload_thresholds_explicit = (target_delta != config.target_bloat_ms or warn_delta != config.warn_bloat_ms)` collapses two failure modes into "no protection":

1. Operator coincidentally sets `continuous_monitoring.upload.target_bloat_ms` equal to the DL global default → flag is False → live-tuning silently overwrites the operator's intent.
2. Operator sets only one of the two UL keys → single combined flag cannot represent "target explicit, warn implicit" or vice versa.

The per-key presence-based form (`"key" in ul`) handles both correctly. The 2 new tests pin both invariants.

## Verification

Hot-path test slice: 614 tests passed in 44.27s
- `tests/test_cake_signal.py`
- `tests/test_queue_controller.py`
- `tests/test_wan_controller.py`
- `tests/test_health_check.py`
- `tests/test_autorate_config.py`

Old flag removal: `grep -n "_upload_thresholds_explicit" src/wanctl/wan_controller.py src/wanctl/autorate_config.py` returns zero matches.

KNOWN_AUTORATE_PATHS membership: both leaf paths registered (verified via `grep -v '^#' src/wanctl/check_config_validators.py | grep -F '"continuous_monitoring.upload.target_bloat_ms"'` and same for `warn_bloat_ms`).

## Production state

Working tree no longer carries the value-derived `_upload_thresholds_explicit` flag. The Codex stop-hook gate that fired on this issue is now resolved.

The remaining Phase 200 working-tree content (`configs/spectrum.yaml` adoption of new keys, version bump 1.41.0, CHANGELOG entry, validator hardening for unknown keys, canary script, deploy + soak) is queued for Plans 02–08.
