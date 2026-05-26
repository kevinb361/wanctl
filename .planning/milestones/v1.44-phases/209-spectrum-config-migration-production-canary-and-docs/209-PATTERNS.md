# Phase 209: Spectrum config migration, production canary, and docs - Pattern Map

**Mapped:** 2026-05-18
**Files analyzed:** 12 (8 code/config + 3 docs + 1 changelog)
**Analogs found:** 12 / 12

**Bias note (per CLAUDE.md change policy):** wanctl is production-critical, "stability > safety > clarity > elegance." Mirror existing patterns exactly. Do not generalize, do not refactor adjacent code. Every analog below has a load-bearing structural detail the executor MUST preserve.

---

## File Classification

| New/Modified File | Role | Data Flow | Closest Analog | Match Quality |
|-------------------|------|-----------|----------------|---------------|
| `configs/spectrum.yaml` | config | static | (self — value-only edit; no structural analog) | n/a (edit-in-place) |
| `configs/att.yaml` | config | static | (no-op — SAFE-08 byte-identity invariant) | n/a (byte-identity) |
| `scripts/check-safe07-source-diff.sh` | utility/script | request-response (CLI) | `scripts/check-safe07-source-diff.sh` (self, extend new mode) | exact |
| `src/wanctl/backends/netlink_cake.py` (`_VALIDATE_KEY_TO_TCA` + `validate_cake`) | backend/middleware | request-response (kernel readback) | self (lines 69–78, 509–563) + sibling key entries | exact |
| `src/wanctl/cake_params.py` (`build_expected_readback`) | utility | transform (params -> expected) | self (lines 191–236) | exact |
| `src/wanctl/backends/linux_cake.py` (validate_cake JSON readback) | backend/middleware | request-response (tc -j) | self (lines 396–402 emission + 416–459 validate) | exact |
| `src/wanctl/__init__.py` | config (version) | static | git `311c9a4` and `ad820f6` (prior bump commits) | exact |
| `pyproject.toml` | config (version) | static | git `311c9a4` (prior bump commit) | exact |
| `docker/Dockerfile` | config (version label) | static | git `311c9a4` (prior bump commit) | exact |
| `docs/BRIDGE_QOS.md` | docs (new) | static | `docs/CONFIGURATION.md` + `docs/RUNBOOK.md` tone | tone-match |
| `docs/CONFIGURATION.md` (allow_wash entry) | docs | static | self (existing `cake_params` paragraph at line 387 + per-direction sections) | exact |
| `CHANGELOG.md` (v1.44.0 heading) | docs | static | self (`## Unreleased (v1.44 — in progress)` at line 8) | exact |
| Snapshot artifact names (rollback ritual) | runtime (operator) | file-I/O | Phase 201-15 plan (`prephase201-recanary-<TS>-snapA/B`) | exact |

---

## Pattern Assignments

### `src/wanctl/backends/netlink_cake.py` (backend, kernel readback)

**Analog:** self — extend, don't restructure. Two surfaces touch.

**Surface 1: `_VALIDATE_KEY_TO_TCA` mapping (lines 69–78)**

Current (line 69):

```python
# Map validate_cake expected dict keys to TCA_CAKE option attribute names.
_VALIDATE_KEY_TO_TCA: dict[str, str] = {
    "diffserv": "TCA_CAKE_DIFFSERV_MODE",
    "overhead": "TCA_CAKE_OVERHEAD",
    "bandwidth": "TCA_CAKE_BASE_RATE64",
    "rtt": "TCA_CAKE_RTT",
    "memlimit": "TCA_CAKE_MEMORY",
    "split_gso": "TCA_CAKE_SPLIT_GSO",
    "ack_filter": "TCA_CAKE_ACK_FILTER",
    "ingress": "TCA_CAKE_INGRESS",
}
```

**Pattern to copy:** new entry `"wash": "TCA_CAKE_WASH"` (or whatever the pyroute2 TCA constant name actually is — executor must verify; the existing entries are the schema). Key naming convention is **snake_case for python-side keys** (`split_gso`, `ack_filter`) — wash is already a single token, so the key is just `"wash"`. No new helper, no new normalization function — exactly one new dict line.

**Surface 2: `validate_cake()` consumption (lines 530–542)**

The reader at line 532 uses `_VALIDATE_KEY_TO_TCA.get(key)` — generic lookup. Adding the wash entry to the dict is the entire wiring. The `diffserv` enum normalization at line 538 is the only key-specific branch and it is keyed by string `"diffserv"`; wash needs no analogous branch unless pyroute2 returns the wash readback as an int enum (executor must verify against pyroute2 docs; if it returns bool, the existing equality check at line 542 is sufficient).

**Excerpt of generic lookup path (lines 530–550) — DO NOT MODIFY structure:**

```python
all_match = True
for key, expected_value in expected.items():
    tca_key = _VALIDATE_KEY_TO_TCA.get(key)
    if tca_key is not None:
        actual = options.get_attr(tca_key)
    else:
        actual = options.get_attr(key)
    # Normalize diffserv: netlink returns int enum, config uses string
    if key == "diffserv" and isinstance(expected_value, str):
        expected_value = _DIFFSERV_NAME_TO_INT.get(
            expected_value, expected_value
        )
    if actual != expected_value:
        self.logger.error(
            "CAKE param mismatch on %s: %s expected=%r actual=%r",
            ...
        )
        all_match = False
```

**Initialize-side kwarg emission already exists** (lines 479–486) — wash is emitted as `kwargs["wash"] = bool(params["wash"])`. No edit needed for emission; this is the readback half only.

---

### `src/wanctl/cake_params.py` — `build_expected_readback()` (lines 191–236)

**Analog:** self — extend, don't restructure.

**Current shape (lines 206–235):**

```python
expected: dict[str, Any] = {}

if "overhead_keyword" in params:
    kw = params["overhead_keyword"]
    if kw in OVERHEAD_READBACK:
        expected.update(OVERHEAD_READBACK[kw])

if "diffserv" in params:
    expected["diffserv"] = params["diffserv"]

if "rtt" in params:
    ...
if "memlimit" in params:
    ...

return expected
```

**Pattern to copy:** add `if "wash" in params: expected["wash"] = bool(params["wash"])` (or with the strict-bool normalization that matches Phase 205's `allow_wash` precedent — `expected["wash"] = params["wash"] is True`). The latter mirrors the strict-is-True guard at `cake_params.py:153`:

```python
allow_wash = cake_config.get("allow_wash") is True if cake_config else False
```

**Decision driver:** D-05 says ATT (allow_wash=false) asserts wash bit NOT set; Spectrum (allow_wash=true) asserts it IS set. That means `build_expected_readback` MUST emit `wash` for BOTH sides — true on Spectrum, false on ATT — so the validator catches accidental wash regressions on ATT. This means the condition is `if "wash" in params` (always), not `if params.get("wash")` (truthy only). Executor must double-check: does Phase 205's `build_cake_params` put `wash: False` into the params dict when `allow_wash` is false, or does it omit the key entirely?

Re-reading lines 156–172: when `allow_wash` is false and the YAML does not specify `wash:`, the `wash` key is NOT in `params`. So symmetric ATT-side assertion requires either:
- (a) `build_cake_params` to always emit `wash: False` when allow_wash is false (mirrors the explicit-False precedent at netlink_cake.py:478 "Explicit False matters for operator overrides"), OR
- (b) `build_expected_readback` to default-emit `wash: False` when key is absent.

**Recommendation for planner:** prefer (a) — keep `build_expected_readback` a pure pass-through transform; let `build_cake_params` own the always-emit-wash policy. This mirrors the existing pattern where build_cake_params owns the policy and build_expected_readback owns the transform.

---

### `src/wanctl/backends/linux_cake.py` (tc-CLI readback, lines 416–459)

**Analog:** self — `validate_cake()` already exists; needs no structural change.

**Current validate_cake (lines 444–459) is generic:**

```python
options = cake_entry.get("options", {})
all_match = True
for key, expected_value in expected.items():
    actual_value = options.get(key)
    if actual_value != expected_value:
        self.logger.error(
            "CAKE param mismatch on %s: %s expected=%r actual=%r",
            self.interface,
            key,
            expected_value,
            actual_value,
        )
        all_match = False
return all_match
```

**Pattern observation:** `tc -j qdisc show` emits CAKE options as a JSON object. Generic `options.get(key)` lookup handles new keys automatically once `build_expected_readback` emits them. **No edit required to `linux_cake.py` itself** for the readback, IF the `tc -j` JSON field name matches what `build_expected_readback` emits.

**Critical executor verification step:** the `tc -j qdisc show` JSON for a CAKE qdisc emits wash status as field name **`wash`** (boolean) when wash is enabled — confirm against a live `tc -j` capture. If field name differs (e.g., `washing`, `nowash`), `build_expected_readback` must emit the correct key OR `validate_cake` needs a tiny normalization shim at line 448 similar to the diffserv enum branch in netlink_cake.py.

**Emission side already correct (lines 392–402):**

```python
# Boolean flags -- explicit False must emit the corresponding negation
# where tc supports one, otherwise operator overrides can be ignored.
# Note: "ecn" is excluded -- not supported by iproute2-6.15.0's tc,
# and CAKE enables ECN by default on all tins anyway.
for flag in ("split-gso", "ack-filter", "ingress", "wash"):
    if params.get(flag):
        cmd_args.append(flag)
    elif flag == "ack-filter" and flag in params:
        cmd_args.append("no-ack-filter")
    elif flag == "wash" and flag in params:
        cmd_args.append("nowash")
```

**Pattern echo:** the wash/nowash emission at 401–402 mirrors the ack-filter/no-ack-filter emission at 399–400. The readback parser inherits this asymmetry — if the kernel emits `wash: false` when `nowash` was passed, the generic lookup just works. If the kernel omits the key entirely when wash is off, then `expected["wash"] = False` will compare to `None` and FAIL the validation — that is the explicit-False trap warned about in the comment at netlink_cake.py:478. **Executor must validate against live kernel output before assuming the generic lookup is sufficient.**

---

### `src/wanctl/backends/linux_cake_adapter.py` (integration point, lines 341–348)

**Analog:** self — call site already wired. No edit needed; informational only for the planner.

```python
# Validate readback (BACK-03)
expected = build_expected_readback(params)
if expected and not backend.validate_cake(expected):
    logger.warning(
        "CAKE readback validation failed on %s (%s) -- continuing anyway",
        backend.interface,
        direction,
    )
```

**Pattern observation:** current behavior is `logger.warning("... continuing anyway")` — a SOFT signal. **CONTEXT.md D-06 says "Mismatch is a hard error at controller startup. Controller refuses to start."** This is a behavioral change from the existing soft-signal pattern.

**Executor flag for planner:** D-06 implies upgrading the `logger.warning` at line 344 to a raise (e.g., `raise RuntimeError(...)`) when wash mismatches. This is the smallest behavioral delta. The planner must decide whether D-06 applies ONLY to wash mismatches (most conservative — preserves existing soft-signal for other params) or to all readback mismatches (broader). **Recommendation:** make it wash-specific to honor "stability > clarity" — extend the soft path with a wash-specific hard-fail branch.

**Note:** `linux_cake_adapter.py` is NOT in the SAFE-09 allowlist set (per ROADMAP §"Closeout invariants"). Adding a wash-specific hard-fail branch here would expand the SAFE-09 surface — planner must explicitly call out whether the SAFE-09 allowlist is expanded for Phase 209 or whether the hard-fail moves to a different file (e.g., directly inside the backends' validate_cake methods).

---

### `scripts/check-safe07-source-diff.sh` (utility/script, request-response)

**Analog:** self (entire 100-line file). Extend by adding a new mode flag, NOT a new script.

**Imports/header pattern (lines 1–16):**

```bash
#!/usr/bin/env bash
# SAFE-07 cross-cutting invariant verification.
# ...
# Usage:
#   bash scripts/check-safe07-source-diff.sh                  # uses default ref
#   bash scripts/check-safe07-source-diff.sh <git-ref>        # override ref
#   PHASE_202_CLOSE=<sha> bash scripts/check-safe07-source-diff.sh
#
# Exit:
#   0 — clean
#   1 — SAFE-07 VIOLATION
#   2 — usage / git error (ref not found)
set -euo pipefail
```

**Default-ref + env-override pattern (lines 21–23):**

```bash
DEFAULT_PHASE_202_CLOSE="b72b463"
REF="${1:-${PHASE_202_CLOSE:-$DEFAULT_PHASE_202_CLOSE}}"
```

**Pattern to copy for Phase 209:** add an env var like `DEFAULT_PHASE_209_ATT_REF="6508d68"` and a positional fallback, gated by a new `--att-config-whitelist` mode flag. Per CONTEXT D-02: "Reference SHA baked into the script default is `6508d68` (v1.43 close)" with "operator may override via positional arg or `PHASE_209_ATT_REF` env."

**Ref-resolution check pattern (lines 25–30):**

```bash
if ! git rev-parse --verify "${REF}^{commit}" >/dev/null 2>&1; then
  echo "ERROR: ref '${REF}' not found in this repository." >&2
  ...
  exit 2
fi
```

**Dirty-tree pre-check pattern (lines 32–66) — REUSE VERBATIM, just change path scope:**

```bash
DIRTY_UNSTAGED=0
DIRTY_STAGED=0
DIRTY_UNTRACKED_LIST=""
git diff --quiet -- src/wanctl/ || DIRTY_UNSTAGED=1
git diff --cached --quiet -- src/wanctl/ || DIRTY_STAGED=1
DIRTY_UNTRACKED_LIST=$(git ls-files --others --exclude-standard -- src/wanctl/ || true)
```

For `--att-config-whitelist` mode, the scope is `configs/att.yaml` (single file, not a directory). The untracked check becomes irrelevant (a single-file untracked clone of `att.yaml` would already show as a different filename — D-03 says examples are explicitly out of scope).

**Diff-vs-ref pattern (lines 68–97):**

```bash
DIFF_OUTPUT=$(git diff "${REF}..HEAD" -- src/wanctl/ 2>&1 || true)
if [ -n "${DIFF_OUTPUT}" ]; then
  CHANGED_PATHS=$(git diff --name-only "${REF}..HEAD" -- src/wanctl/)
  DISALLOWED_PATHS=$(printf '%s\n' "${CHANGED_PATHS}" | grep -vx 'src/wanctl/__init__.py' || true)
  ...
  echo "SAFE-07 VIOLATION: src/wanctl/ has changed since ${REF}" >&2
  ...
  exit 1
fi
echo "SAFE-07 OK: no src/wanctl/ diff vs ${REF}"
exit 0
```

**Pattern to copy:** for `--att-config-whitelist`, replace `src/wanctl/` with `configs/att.yaml` and remove the `__init__.py` allowlist branch (no version-bump is allowed inside ATT config — D-03/D-04 explicit). Exit-1 message becomes "SAFE-08 VIOLATION: configs/att.yaml has changed since ${REF}."

**Mode-flag dispatch pattern:** the existing script has no mode-flag dispatch yet — Phase 209 introduces it. Smallest mirror:

```bash
MODE="default"
while [ "$#" -gt 0 ]; do
  case "$1" in
    --att-config-whitelist) MODE="att-whitelist"; shift ;;
    --) shift; break ;;
    -*) echo "Unknown flag: $1" >&2; exit 2 ;;
    *) break ;;  # positional ref left for legacy handling
  esac
done
```

then branch the rest of the script on `${MODE}`. **Bias:** keep both modes' code paths visible side-by-side — do not refactor the existing path into a shared function. This matches HRDN-01 fail-closed precedent which kept inline logic readable.

**Exit-code contract (lines 13–16):** new mode reuses 0/1/2 semantics: 0 clean, 1 SAFE-08 violation, 2 ref-not-found. No new exit codes.

---

### `CHANGELOG.md` v1.44.0 heading

**Analog:** lines 8–43 (current `## Unreleased (v1.44 — in progress)` block).

**Heading pattern to flip at closeout:**

Current line 8:
```markdown
## Unreleased (v1.44 — in progress)
```

Pattern target (mirrors v1.43.0 close at line 45 `## v1.43.0 — 2026-05-13`):
```markdown
## v1.44.0 — <YYYY-MM-DD>
```

**Subsection ordering (preserve existing v1.43.0 convention, lines 47–91):**

```markdown
### Added
### Changed
### Fixed
### Tests        # (only when tests-only items exist; Phase 208 used it)
### Decisions    # (only when explicit YES/NO decisions need preserving; HRDN-04 used it)
### Removed
### Deploy notes
### Notes
```

**Item style (mirror v1.43.0 lines 49–63):**

```markdown
- **<TAG> (<Phase X>):** <one-paragraph description with planning anchor link>
```

**Phase 209-specific anchors required per CONTEXT D-16:**
- `allow_wash` knob (default-false)
- besteffort/wash semantics shift on Spectrum
- `ceiling_mbps: 940 → 920`
- explicit link to `docs/BRIDGE_QOS.md`
- NO inline DSCP-rationale paragraph (D-16 — avoid duplication)

**Single-commit landing pattern (D-11):** the YAML flip + version bump + CHANGELOG heading all land in one closeout commit. Mirrors v1.43.0 close commit `ad820f6` shape.

---

### Version bump trio — `src/wanctl/__init__.py`, `pyproject.toml`, `docker/Dockerfile`

**Analog:** git commit `311c9a4` ("chore(201-15): bump version to 1.42.1 across all surfaces"). Three-file, three-line diff.

**Diff shape (from `git show 311c9a4`):**

```diff
--- a/docker/Dockerfile
@@ -10,7 +10,7 @@ FROM python:3.12-slim
 LABEL maintainer="wanctl project"
 LABEL description="Adaptive CAKE bandwidth controller for Mikrotik RouterOS"
-LABEL version="1.42.0"
+LABEL version="1.42.1"

--- a/pyproject.toml
@@ -1,6 +1,6 @@
 [project]
 name = "wanctl"
-version = "1.42.0"
+version = "1.42.1"

--- a/src/wanctl/__init__.py
@@ -1,3 +1,3 @@
 """wanctl - Adaptive CAKE bandwidth control for RouterOS."""
-__version__ = "1.42.0"
+__version__ = "1.43.0"
```

**Pattern to copy for Phase 209:** identical three-file diff, `1.43.0 → 1.44.0`. Commit message pattern (from `ad820f6`):

```
chore(209-XX): bump deploy version to 1.44.0

- align package, module, and Docker version surfaces
- preserve SAFE-08/SAFE-09 source-diff gate for canary Deploy
```

**Critical:** the v1.43.0 bump commit `ad820f6` did NOT have `src/wanctl/__init__.py` in its 3-file diff alone — it shipped alongside the v1.43 changes. Phase 209 D-11 says the bump lands in the SAME closeout commit as the spectrum.yaml flip — so the final commit will be 6 files (3 version + spectrum.yaml + CHANGELOG.md + possibly check-safe07 script update).

---

### `configs/spectrum.yaml` — three-value migration

**Analog:** self at lines 35–43 (`cake_params:` block) and line 61 (`ceiling_mbps: 940`).

**Existing `cake_params:` block (lines 35–43):**

```yaml
cake_params:
  download_interface: "spec-router" # Spectrum router-side NIC (download egress)
  upload_interface: "spec-modem" # Spectrum modem-side NIC (upload egress)
  overhead: "docsis" # sweep validated 2026-04-04 (=18 bytes, matches MikroTik)
  mpu: 64 # sweep validated 2026-04-04 (matches MikroTik)
  memlimit: "64mb" # Raised from 32mb — DL qdisc was at 86.6% (27.7/32MB)
  rtt: "100ms" # Conservative DOCSIS interval; 1s was diagnostic only, not an operating tune
  ack_filter: false # Silicom validation 2026-04-28; preserve no-ack-filter on upload
  ingress: false # Silicom validation 2026-04-28; ingress on spec-router hurt upload tests
```

**Pattern to copy for the three edits:**

1. **`ceiling_mbps: 940 → 920`** (line 61, under `download:` block) — value-only, preserve trailing comment. Update comment to reference Phase 209 / topology-correct evidence.
2. **Add `diffserv: besteffort`** inside `cake_params:` block — new line. No existing diffserv entry in spectrum.yaml today (defaults to diffserv4 via DIRECTION_DEFAULTS). Comment must reference BRIDGE_QOS.md and the 2026-04-22 flent finding.
3. **Add `allow_wash: true`** inside `cake_params:` block — new line. Comment must cite the per-WAN gate (Phase 205 TOPO-02) and BRIDGE_QOS.md.

**Style mirror:** all existing entries have inline `# comment` providing dated rationale (e.g., "sweep validated 2026-04-04", "Silicom validation 2026-04-28"). Phase 209 entries should follow: e.g., `allow_wash: true # 2026-04-22 flent finding; see docs/BRIDGE_QOS.md`.

---

### `configs/att.yaml` — SAFE-08 byte-identity (NO EDIT)

**Analog:** self at git ref `6508d68`. The pattern is **no diff**. SAFE-08 enforces this via the new `--att-config-whitelist` mode of check-safe07-source-diff.sh. If the executor finds themselves editing att.yaml, the plan is wrong.

---

### `docs/BRIDGE_QOS.md` (NEW)

**Analog:** `docs/CONFIGURATION.md` and `docs/RUNBOOK.md` for tone; `docs/CABLE_TUNING.md` for the "per-WAN concrete tradeoff" narrative shape (cable-vs-other contrast).

**CONFIGURATION.md tone reference (line 387):**

```markdown
- `cake_params`: required for `linux-cake` and `linux-cake-netlink` transports.
```

decision-oriented, terse, cross-links to schema and subsystems docs.

**RUNBOOK.md tone marker** (operator-callable, action-leading) — per D-15 "lead with how to decide, end with why."

**Suggested structure (mirror CABLE_TUNING.md sectioning):**

```markdown
# Bridge QoS: when to enable `allow_wash`

## When to enable allow_wash
<decision tree — flowchart-style prose>

## Spectrum vs ATT: a worked contrast
<concrete: Spectrum allow_wash=true besteffort; ATT allow_wash=false diffserv4>

## Why DSCP does not survive consumer ISP topologies
<topology rationale: DOCSIS CMTS, transparent CPE; brief>

## See also
- docs/CONFIGURATION.md `cake_params` section
- configs/spectrum.yaml / configs/att.yaml worked examples
```

**Scope guard (D-14):** NOT a diffserv4-vs-besteffort tradeoff matrix, NOT a historical migration narrative. Reject either if the executor drifts.

---

### `docs/CONFIGURATION.md` — `allow_wash` entry

**Analog:** self. Existing `cake_params` mention at line 387 is one-line summary; Phase 209 adds a focused `allow_wash` entry, likely under the `## Additional Production Sections` block or inside a new `### cake_params` subsection.

**Tone mirror (lines 242–293, "DOCSIS-Aware UL Control Mode (v1.42+)"):** decision-driven section with explicit per-WAN guidance. Phase 209 `allow_wash` entry should mirror this shape — short paragraph, default value (`false`), per-WAN decision rule, cross-link to `docs/BRIDGE_QOS.md` (NOT duplicate the topology rationale).

**Anti-pattern:** do NOT add a tradeoff matrix or topology explanation here. D-13 explicit: "CONFIGURATION.md gets a focused `allow_wash` entry that cross-links to BRIDGE_QOS.md rather than carrying duplicate topology content."

---

### Two-snapshot rollback artifact naming

**Analog:** Phase 201-15 plan + Phase 198-01 (per CONTEXT).

**Naming convention (from `201-15-recanary-PLAN.md` lines 60, 73, 144–146, 159–160):**

```
/opt/wanctl-prephase201-recanary-<TS>-snapA.tar.gz
/opt/wanctl-prephase201-recanary-<TS>-snapB.tar.gz
/etc/wanctl/spectrum.yaml.prephase201-recanary-<TS>-snapA
/etc/wanctl/spectrum.yaml.prephase201-recanary-<TS>-snapB
```

**Pattern to copy for Phase 209:**

```
/opt/wanctl-prephase209-<ISO8601>-snapA.tar.gz
/opt/wanctl-prephase209-<ISO8601>-snapB.tar.gz
/etc/wanctl/spectrum.yaml.prephase209-<ISO8601>-snapA
/etc/wanctl/spectrum.yaml.prephase209-<ISO8601>-snapB
```

**Ordering invariant (mirror Phase 201-15 lines 30–36):**
1. Snapshot A captured BEFORE predeploy gate, BEFORE any YAML reconcile — rollback-clean evidence (binary == `1.43.0`, spectrum.yaml has `ceiling_mbps: 940`, `diffserv4`, no `allow_wash`).
2. Predeploy gate runs.
3. Reconcile candidate `configs/spectrum.yaml` (the Phase 209 flip) into `/etc/wanctl/spectrum.yaml`.
4. Snapshot B captured AFTER reconcile — deploy evidence ONLY, never a rollback target.
5. Rollback always restores from Snapshot A.

**Verification gate (mirror line 36):** post-rollback grep must show:
- `/health.version == 1.43.0`
- `grep -c '^[[:space:]]*allow_wash:' /etc/wanctl/spectrum.yaml == 0`
- `grep -c '^[[:space:]]*diffserv:.*besteffort' /etc/wanctl/spectrum.yaml == 0`
- `ceiling_mbps: 940` (not 920) under `download:`

---

## Shared Patterns

### Strict-bool guard (allow_wash)

**Source:** `src/wanctl/cake_params.py:153`

```python
allow_wash = cake_config.get("allow_wash") is True if cake_config else False
```

**Apply to:** any new wash-related boolean read across cake_params and build_expected_readback. `bool("false") == True` is the documented operator-typo trap; the `is True` idiom rejects strings outright. Phase 209 readback validation inherits this convention.

### Explicit-False matters for boolean flags

**Source:** `src/wanctl/backends/netlink_cake.py:477–486` + `linux_cake.py:392–402`

```python
# Boolean flags. Explicit False matters for operator overrides such as
# ack_filter=false; omitting the netlink attribute can preserve/default on.
```

**Apply to:** wash readback. If `build_expected_readback` does not emit `wash: False` when allow_wash is false, the symmetric ATT-side assertion (D-05) silently degrades to "we don't check ATT wash at all." Executor must verify the emission policy covers both true and false cases.

### Generic key-lookup readback validation

**Source:** `netlink_cake.py:530–550` and `linux_cake.py:444–459`

Both backends iterate `expected.items()` and compare via a single generic lookup. **No per-key parsing branches** except the diffserv enum normalization. Phase 209 wash readback fits this generic shape — do NOT add a wash-specific parser unless live kernel output forces it. If the generic path breaks, prefer extending `_DIFFSERV_NAME_TO_INT`-style normalization shim, not new branches.

### Fail-closed exit semantics (HRDN-01)

**Source:** `scripts/check-safe07-source-diff.sh:44–66`

Dirty-tree, staged, or untracked edits → exit 1 with explicit per-class messaging. Apply identical pattern to `--att-config-whitelist` mode. **No warn-and-continue path** (D-04 explicit).

### Single-commit closeout

**Source:** Phase 201-15 / Phase 204 closeout commits (`311c9a4`, `ad820f6`).

Three-file version-bump diff + CHANGELOG heading flip + config edits all land in ONE commit. Avoids the temporary "version-mismatched intermediate state" rollback artifact-naming confusion (D-11). For Phase 209: 6-file commit (3 version + `configs/spectrum.yaml` + `CHANGELOG.md` + `check-safe07-source-diff.sh` mode flag).

### SAFE-05 pin block (forward-looking)

**Source:** `tests/test_phase_195_replay.py:642–714`

```python
phase202_expected_counts = {
    "_record_suppression": 4,
    "_window_suppressions_by_cause": 6,
    ...
}
for name, expected_count in phase202_expected_counts.items():
    assert sum(1 for line in phase201_src.splitlines() if name in line) == expected_count
```

**Pattern observation:** every phase that adds named symbols to the control path appends a NEW dict (`phaseNNN_expected_counts`) to this test, never modifies existing dicts. Phase 209 wash readback adds at minimum:
- `TCA_CAKE_WASH` (constant name in netlink_cake.py)
- `"wash"` key in `_VALIDATE_KEY_TO_TCA`
- `"wash"` key emission in `build_expected_readback`

**Whether a new `phase209_expected_counts` dict is needed depends on whether wash adds line-counts that drift detection should pin.** Planner discretion — the bias from CLAUDE.md "stability > clarity" says **add a Phase 209 pin block** to lock the wash readback line counts, mirroring how Phase 202-03 / 204-02 pinned their additive surfaces. Pin candidates:
- `TCA_CAKE_WASH` count == 1 (single dict entry)
- `_VALIDATE_KEY_TO_TCA` key count gained: 1 line vs `6508d68`

---

## No Analog Found

None. Every Phase 209 file has a clear analog in the codebase or in prior phase closeout commits.

---

## Metadata

**Analog search scope:**
- `src/wanctl/backends/` (netlink_cake.py, linux_cake.py, linux_cake_adapter.py)
- `src/wanctl/cake_params.py`, `src/wanctl/__init__.py`, `src/wanctl/check_config_validators.py`
- `scripts/check-safe07-source-diff.sh`
- `configs/spectrum.yaml`, `configs/att.yaml`
- `tests/backends/test_netlink_cake.py`, `tests/backends/test_linux_cake.py`, `tests/test_cake_params.py`, `tests/test_phase_195_replay.py`
- `docs/CONFIGURATION.md`, `docs/RUNBOOK.md`, `docs/CABLE_TUNING.md`
- `CHANGELOG.md`
- Git history: `311c9a4`, `ad820f6` (prior version-bump commits)
- `.planning/milestones/v1.42-phases/201-docsis-aware-ul-congestion-control/201-15-recanary-PLAN.md`
- `pyproject.toml`, `docker/Dockerfile`

**Files scanned:** ~20
**Pattern extraction date:** 2026-05-18
