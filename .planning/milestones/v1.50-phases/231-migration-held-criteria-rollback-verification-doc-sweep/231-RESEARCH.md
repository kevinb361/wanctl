# Phase 231 Research: Migration-Held Criteria, Rollback Verification & Doc Sweep

**Researched:** 2026-06-10
**Phase requirements:** SOAK-01, SOAK-02, DOCS-04, SAFE-14
**Question answered:** What do we need to know to PLAN formal migration-held evaluation, rollback verification, the stale-doc sweep, and the SAFE-14 milestone-close proof?

---

## 1. Live Deployment Reality (as of migration 2026-06-08, commit `fc47a0c`)

Both WANs run external cake-autorate mode on the cake-shaper VM (`ssh kevin@10.10.110.223`):

| Unit | Spectrum | ATT |
|------|----------|-----|
| Shaper | `cake-autorate-spectrum.service` | `cake-autorate-att.service` |
| State bridge | `cake-autorate-spectrum-state-bridge.service` | `cake-autorate-att-state-bridge.service` |
| Silicom watchdog | `silicom-bypass-watchdog@spectrum.service` | `silicom-bypass-watchdog-cake-autorate-att.service` |
| Native controller | `wanctl@spectrum.service` — disabled, rollback only | `wanctl@att.service` — disabled, rollback only |
| Health endpoint | `http://10.10.110.223:9101/health` | `http://10.10.110.227:9101/health` |
| State JSON | `/var/lib/wanctl/spectrum_state.json` | `/var/lib/wanctl/att_state.json` |
| Metrics DB | `/var/lib/wanctl/metrics-spectrum.db` | `/var/lib/wanctl/metrics-att.db` |
| cake-autorate log | `/var/log/cake-autorate/cake-autorate.spectrum.log` | `/var/log/cake-autorate/cake-autorate.att.log` |
| DL interface | `spec-router` | `att-router` |
| UL interface | `spec-modem` | `att-modem` |

`steering.service` consumes both state files. Source of truth for the live post-migration unit
inventory: `.planning/cake-autorate-trials/WANCTL_CAKE_AUTORATE_FUTURE.md` ("Live post-migration
state", lines ~1122–1134). The bridge defaults derive paths from `WANCTL_EXTERNAL_WAN_NAME`
(`deploy/scripts/cake-autorate-spectrum-state-bridge` lines 19–21); ATT overrides via unit env in
`deploy/systemd/cake-autorate-att-state-bridge.service`.

### Configured envelopes (qdisc criterion source of truth)

From `configs/cake-autorate/config.spectrum.sh` and `config.att.sh` (repo copies match deployed
per Phase 229 DEPLOY-02 byte-equality evidence):

| WAN | DL autorate | DL min/base/max kbps | UL autorate | UL fixed |
|-----|-------------|----------------------|-------------|----------|
| Spectrum | enabled (`adjust_dl_shaper_rate=1`) | 500000 / 550000 / 600000 | disabled (`adjust_ul_shaper_rate=0`) | 18 Mbit (base) |
| ATT | enabled | 60000 / 95000 / 100000 | disabled | 19 Mbit (base) |

Qdisc-within-envelope criterion: DL CAKE `bandwidth` on `{spec,att}-router` within [min_dl, max_dl];
UL CAKE `bandwidth` on `{spec,att}-modem` equals the fixed base rate. Parse from
`tc qdisc show dev <iface>` over SSH (read-only).

## 2. SOAK-01 — Formal "migration held" criteria

The roadmap names four criterion families; all have existing read-only evidence channels:

1. **Bridge health** — `curl http://<ip>:9101/health` per WAN; healthy payload includes
   `status: healthy` and GREEN/GREEN state. `scripts/soak-monitor.sh --json` (generalized for
   external mode in Phase 230) already aggregates this per WAN.
2. **Metrics-DB ingestion** — bridge writes compact metrics into `/var/lib/wanctl/metrics-{wan}.db`.
   Channels: `wanctl-history --ingestion-rate` CLI (Phase 219, `src/wanctl/history.py`, envelope
   JSON), or direct read-only `sqlite3` row-count-in-window over SSH with `sudo -n` (Phase 212
   precedent for read-only sudo). Criterion: recent rows present within the evaluation window for
   both DBs (non-zero ingestion rate).
3. **No sustained service errors** — `journalctl -u <unit> --since <window> -p err` per live unit;
   `soak-monitor.sh --json` exposes `errors_1h` per WAN using the Phase 230 live-unit array
   (covers cake-autorate, state-bridge, and ATT watchdog units in external mode).
4. **Qdisc within configured envelope** — see table above.

**Migration date anchor:** 2026-06-08. The criteria definition must pick an explicit soak window
(e.g., "since 2026-06-08T00:00Z" or trailing 24/48h) and record it in the criteria doc — the
formality is the point of SOAK-01: criteria first, then evaluation against live evidence, both WANs.

**Recommended shape:** a committed criteria definition + a read-only evaluator script
(`scripts/phase231-migration-held.sh`) that emits per-WAN PASS/FAIL JSON with raw evidence
captured, plus a committed evidence artifact `231-SOAK01-EVIDENCE.md` (Phase 230's
`230-MON01-EVIDENCE.md` is the formatting precedent). Everything read-only: SSH + curl + journalctl
+ tc + sqlite3 SELECT. No `systemctl start/stop`, no writes on the target.

## 3. SOAK-02 — Rollback verification

Requirement allows two paths:
- **(a) Exercised** on one WAN under operator approval (production mutation — requires explicit gate);
- **(b) Trivially provable** via documented, preflighted procedure with evidence captured.

Existing assets:

- **A documented ATT rollback block already exists** in `WANCTL_CAKE_AUTORATE_FUTURE.md`
  (lines ~1136–1150): disable cake-autorate trio → enable `wanctl@att.service` +
  `silicom-bypass-watchdog@att.service` → bpctl non-bypass + WDT reset → `tc qdisc replace` both
  ATT NICs to native baseline. Note it restores `att-modem` to 18 Mbit (native-era baseline),
  not the current cake-autorate 19 Mbit point — correct for native rollback since native
  `wanctl@att` config owns rates after start.
- **Rollback was actually exercised once** on ATT (2026-06-05, pre-migration trial rollback,
  documented in the same file with restore verification). This is historical-exercise evidence
  supporting the "trivially provable" claim, not a substitute for a current preflight.
- **Script precedent:** `scripts/phase227-rollback.sh` — `--dry-run` default-safe, `--confirm`
  required for mutation, ordered plan printout, health-check verify, proof JSON output.
  Project memory: do NOT wire abort paths to `phase226-restore.sh` (dry-run-only); 227 is the
  mutation-capable precedent.
- Native units, configs, and code still exist by policy ("What not to delete yet"):
  `deploy/systemd/wanctl@.service` (ExecStart `/usr/bin/python3 /opt/wanctl/autorate_continuous.py
  --config /etc/wanctl/%i.yaml`), `/etc/wanctl/{wan}.yaml` on target, `/opt/wanctl` deployment.

**Preflight checks that make rollback "trivially provable" (all read-only):**
1. `wanctl@{wan}.service` unit file present on target; unit `disabled`/`inactive` (rollback-ready,
   no dual-writer).
2. `/etc/wanctl/{wan}.yaml` present and parseable on target; `/opt/wanctl/autorate_continuous.py`
   present.
3. For ATT: `silicom-bypass-watchdog@.service` template present; bpctl utility present at
   `/opt/bpctl-silicom`.
4. Rollback command sequence rendered per WAN (units to stop/disable, units to enable/start,
   qdisc restore commands) and recorded in evidence.
5. `Conflicts=wanctl@{wan}.service` present in the cake-autorate unit (prevents dual-writer on
   rollback — verify via `systemctl cat`).

**Recommended shape:** parameterized `scripts/phase231-rollback.sh --wan {spectrum|att}` modeled
on phase227-rollback.sh (`--dry-run` default, `--confirm` gated, preflight subcommand emits proof
JSON), plus `231-SOAK02-EVIDENCE.md` documenting the procedure + preflight evidence + historical
exercise citation. An operator checkpoint offers the optional live exercise on one WAN; the
provable path completes SOAK-02 without production mutation if the operator declines.

**Spectrum rollback specifics:** native-era Spectrum baseline qdiscs (pre-migration):
`spec-router` CAKE 550Mbit / `spec-modem` 18Mbit with production flags (see restore blocks in
WANCTL_CAKE_AUTORATE_FUTURE.md trial sections). Native `wanctl@spectrum` re-applies rates after
start, so qdisc restore is a bootstrap step, not the steady state.

## 4. DOCS-04 — Stale-doc sweep surface

Verified by grep on 2026-06-10: **zero** mentions of cake-autorate in `README.md`,
`docs/README.md`, `docs/DEPLOYMENT.md`, `docs/ARCHITECTURE.md`, `docs/CONFIGURATION.md`.
The external mode is documented only in `CLAUDE.md` (Service Model section — the correct prose
source) and planning artifacts.

Specific stale claims found:

| File | Lines | Claim |
|------|-------|-------|
| `docs/DEPLOYMENT.md` | ~47–56, 141–211 | wanctl@<wan> enable/restart presented as THE deployment flow; lines ~187, ~201 explicitly journalctl `wanctl@spectrum.service -u wanctl@att.service` as the live soak-evidence path |
| `docs/CONFIGURATION.md` | ~235, ~290 | "apply config by `systemctl restart wanctl@<wan>.service`" with no external-mode caveat |
| `README.md` | ~75, ~259–262 | quickstart + monitoring via `wanctl@wan1.service` only (generic `wan1` examples are acceptable as wanctl@-mode docs, but the doc must state both modes exist) |
| `docs/ARCHITECTURE.md` | n/a | no wanctl@ claims, but describes only the native controller architecture; needs an external-mode/state-bridge section "as applicable" |

**Sweep policy (from requirement + CLAUDE.md):** docs must (1) describe both deployment modes
correctly (wanctl@ template mode AND external cake-autorate + state-bridge mode), (2) stop
claiming native-wanctl ownership of Spectrum/ATT rate control, (3) not reintroduce timer-era
guidance, (4) stay public-safe (no new private IPs in docs/ — generic host placeholders; note
`deploy/systemd/` units already contain LAN IPs, which the project accepts for deploy artifacts,
but docs prose should stay generic). The generic/portable wanctl@ documentation remains valid for
non-Spectrum/ATT deployments — do not delete it; reframe it as one of two modes.

## 5. SAFE-14 — Boundary + milestone-close proof

Precedent: `230-SAFE14-BOUNDARY.md` (two-baseline pattern, PASS verdict format).

- **Protected set (exact):** `src/wanctl/wan_controller.py`, `src/wanctl/wan_controller_state.py`,
  `src/wanctl/queue_controller.py`, `src/wanctl/cake_signal.py`, `src/wanctl/alert_engine.py`,
  `src/wanctl/fusion_healer.py`, `src/wanctl/backends/`. (`wan_controller_state.py` explicitly
  listed per decision [227-04].)
- **SAFE_BASE:** `87980bdf8ea52e5537110cd9bbc7a368f523d2e2` (pinned at Phase 229; reused at 230).
- **Scope baseline:** capture `PHASE231_START` = repo HEAD at phase execution start, used ONLY for
  Phase 231 file-scope accounting (decision [230-02]: keep the two baselines separate).
- **Milestone close:** Phase 231 is the v1.50 closeout phase, so the final SAFE-14 boundary proof
  doubles as the milestone-close proof — it MUST run as the LAST task after all other Phase 231
  commits (decision [225-05] precedent: boundary re-run LAST so head_commit stamps true final HEAD).
- **Dirty-tree checks:** `git status --porcelain -- src/wanctl/` + staged/unstaged `--quiet` checks,
  all clean.
- **Known pre-existing noise:** full `pytest tests/ -q` shows 21 pre-existing Phase 220/221
  boundary-test failures (they refuse committed `src/wanctl/` drift since
  `PHASE214_BASE_SHA=50f3d513`); classify as pre-existing, unrelated to SAFE-14 protected-path proof.

## 6. Production-safety constraints binding this phase

- Production network control system; **read-only evidence gathering is allowed without asking;
  any mutation (rollback exercise) requires explicit operator approval** (roadmap text + USER.md
  safety boundaries + CLAUDE.md change policy).
- No controller threshold/algorithm changes — milestone surface is deploy/test/ops/doc only.
- Flash-wear/steering/health contracts untouched; this phase ships scripts, docs, and evidence only.
- `sudo -n` read-only pattern for permission-blocked target reads (Phase 212 precedent).
- Pause/resume of the Spectrum hourly validation cron is only relevant if a live rollback exercise
  is approved; the provable path needs no cron interaction.

## 7. Existing patterns to follow

| Need | Analog |
|------|--------|
| Evidence artifact format | `.planning/phases/230-soak-monitor-att-coverage/230-MON01-EVIDENCE.md` |
| SAFE-14 boundary format | `.planning/phases/230-soak-monitor-att-coverage/230-SAFE14-BOUNDARY.md` |
| Gated mutation script | `scripts/phase227-rollback.sh` (`--dry-run`/`--confirm`, proof JSON) |
| Read-only multi-check evaluator | `scripts/soak-monitor.sh` (TARGETS array, external-mode detection, `--json`) |
| Artifact regression tests | `tests/test_att_cake_autorate_artifacts.py`, `tests/test_spectrum_cake_autorate_artifacts.py`, `tests/test_soak_monitor_att_coverage.py` |
| Script lint gate | `shellcheck -S error scripts/<new>.sh` (Phase 230 verification precedent) |
| Test runner | `.venv/bin/pytest tests/<focused>.py -q`; full-suite failures classified per §5 |

## 8. Risks / planning notes

- **Don't conflate the two SOAK-02 paths:** plan must complete autonomously on the provable path;
  the live exercise is an optional operator-gated checkpoint, never a default.
- **Evidence freshness:** SOAK-01 evidence must be captured at execution time (live curl/ssh), not
  copied from Phase 230 artifacts; cite the capture timestamp and window in the evidence file.
- **soak-monitor TARGETS/SERVICE_UNITS header still lists `wanctl@{spectrum,att}.service`** in its
  static array (fallback path, kept intentionally per decision [230-01]) — the evaluator should
  rely on the Phase 230 external-mode detection output, not the static array.
- **Doc sweep scope creep:** DOCS-04 names README, DEPLOYMENT, ARCHITECTURE, CONFIGURATION "as
  applicable". Keep the sweep to these + docs/README.md index links if needed. Do not rewrite
  STEERING/PERFORMANCE/etc. unless they contain native-ownership claims (grep first).
- **SAFE-14 ordering hazard:** any commit after the boundary proof invalidates "milestone close"
  semantics. The boundary task must be the final task of the final plan, and the SUMMARY/metadata
  commit pattern used in 225-05 should be acknowledged (committed JSON/MD references the commit
  immediately prior to its own tracking commit — expected parent-reference semantics).

## Validation Architecture

**Test infrastructure:** pytest (`.venv/bin/pytest`), shellcheck, ruff/mypy (unchanged code paths).

| Deliverable | Validation |
|-------------|------------|
| `scripts/phase231-migration-held.sh` | `shellcheck -S error`; focused pytest artifact test asserting criteria thresholds/flags parse and read-only command construction (no `systemctl start/stop/restart`, no `tc qdisc replace` outside dry-run rendering); live run output committed as evidence |
| `scripts/phase231-rollback.sh` | `shellcheck -S error`; focused pytest asserting `--confirm` gating (no mutation commands executed without flag), per-WAN unit/qdisc rendering correctness; `--dry-run`/preflight live run (read-only) committed as evidence |
| `231-SOAK01-EVIDENCE.md` / `231-SOAK02-EVIDENCE.md` | grep-checkable assertions: per-WAN PASS verdicts, capture timestamps, criteria table present |
| Doc sweep | grep assertions: zero stale exclusive-ownership claims (`journalctl -u wanctl@spectrum` etc. as live-path), both modes described (`cake-autorate` appears in each swept doc); no new private IPs in docs/ prose |
| SAFE-14 | `git diff --stat 87980bdf -- <protected set>` empty; dirty-tree clean; committed `231-SAFE14-BOUNDARY.md` |

**Quick run command:** `.venv/bin/pytest tests/test_phase231_*.py -q` (new focused tests)
**Full suite command:** `.venv/bin/pytest tests/ -q` (21 pre-existing failures classified, see §5)
**Hot-path regression slice (unchanged code, cheap reassurance):**
`.venv/bin/pytest -o addopts='' tests/test_cake_signal.py tests/test_queue_controller.py tests/test_wan_controller.py tests/test_health_check.py -q`

---
*Research complete: 2026-06-10. Sources: live repo at d7e57a98, WANCTL_CAKE_AUTORATE_FUTURE.md,
Phase 229/230 artifacts, deploy/systemd units, configs/cake-autorate, docs grep survey.*
