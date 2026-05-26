# Phase 211: Production Verification & Milestone Closure - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-26
**Phase:** 211-production-verification-milestone-closure
**Areas discussed:** VERIFY-01 observation gate, Deploy ritual scope, ALERT-03 verification approach, Milestone closure mechanics

---

## VERIFY-01 observation gate

### Q1 — Wait window

| Option | Description | Selected |
|--------|-------------|----------|
| 7 days hard (recommended) | Open observation for 7 days post-deploy. Spectrum fired ul-flapping ~daily during May; 7d gives ATT a chance too without dragging milestone close. If nothing fires, escalate. | ✓ |
| Open-ended, no deadline | Watch until an event lands. Milestone close hangs until then. Risk: indefinite-open phase if DOCSIS plant stabilizes. | |
| 14 days hard | Two-week window. Conservative; matches v1.43/v1.44 archive cadence. Higher chance of catching both Spectrum AND ATT events organically. | |

**User's choice:** 7 days hard

### Q2 — Evidence bar

| Option | Description | Selected |
|--------|-------------|----------|
| One DL or UL event with peak > threshold (recommended) | Single flapping_dl OR flapping_ul row where details.peak_transition_count > details.flap_threshold (>30). Matches REQUIREMENTS.md ALERT-01 literal text and is what Codex round-2 review signed off on. | ✓ |
| Both DL and UL paths observed | Wait for one DL event AND one UL event before closure. Stronger coverage; ATT historically slow on DL events (3 in 30d), could push window past 14d. | |
| Multiple events on same WAN | Two or more events with peak > threshold on either WAN to rule out fluke. Tighter statistical confidence, slower closeout. | |

**User's choice:** One DL or UL event with peak > threshold

### Q3 — Artifact location

| Option | Description | Selected |
|--------|-------------|----------|
| Per-event JSON in phase dir (recommended) | Capture qualifying alert row(s) as JSON under 211-VERIFY-01-evidence/ plus an EVIDENCE.md narrative. Self-contained closeout. | ✓ |
| Inline in VERIFICATION.md | Drop the payload snippets directly into 211-VERIFICATION.md observable-truths table. Simpler, harder to grep later. | |
| External (alerts table only) | Cite alert id + timestamp in VERIFICATION.md; rely on live alerts DB as the durable record. Evidence vanishes if alerts table rotates. | |

**User's choice:** Per-event JSON in phase dir

### Q4 — No-event branch

| Option | Description | Selected |
|--------|-------------|----------|
| Operator review + extend or defer (recommended) | At deadline, operator inspects alert volume + DOCSIS plant state. Options: extend window 7d, or accept synthetic-proof (deferred VERIFY-01 to v1.46 close as a watch-list item). | ✓ |
| Fail and rollback | Treat no-event as VERIFY-01 fail; roll back deploy. Aggressive — doesn't make sense when the change is alerting-only and cannot regress traffic. | |
| Auto-close on deadline if SAFE-10 + ALERT-03 hold | Treat code-level verification as sufficient and close v1.45 at deadline regardless of real-event observation. Risks shipping the milestone without the production gate it was designed around. | |

**User's choice:** Operator review + extend or defer

---

## Deploy ritual scope

### Q1 — Snapshot scope

| Option | Description | Selected |
|--------|-------------|----------|
| Full two-snapshot per host (recommended) | Mirror Phase 209: /opt/wanctl-prephase211-{ISO8601}.tar.gz + /etc/wanctl/{spectrum,att}.yaml.prephase211-{ISO8601} on BOTH hosts. Snapshot A is rollback target; no Snapshot B needed. | ✓ |
| Lightweight snapshot — binary only | Tarball /opt/wanctl on each host, skip config snapshots. Faster ritual; weaker rollback evidence. | |
| Skip snapshots, rely on git tag | v1.44 tag + ability to redeploy from CI. Smallest ritual, no per-host rollback artifact — incompatible with established pattern. | |

**User's choice:** Full two-snapshot per host

### Q2 — A/B soak harness

| Option | Description | Selected |
|--------|-------------|----------|
| No — alerting-only, skip soak (recommended) | v1.45 cannot affect zone/cause-tag distributions — only alert payload field values change. A/B soak vs v1.43 baseline is wrong tool. Saves 24h. | ✓ |
| Yes — 24h soak for regression safety | Run Phase 206 A/B harness against v1.43 20260509T183037Z baseline anyway, as a controller-side regression sanity check. Belt-and-suspenders on SAFE-10. | |
| Soak but no A/B gate — collect for archive only | Capture post-deploy soak NDJSON without running through rollback-gate comparator. Compromise — evidence for future forensic value, no operational decision-gate. | |

**User's choice:** No — alerting-only, skip soak

### Q3 — Deploy ordering

| Option | Description | Selected |
|--------|-------------|----------|
| Spectrum first, ATT next-day (recommended) | Canary-style. Spectrum fires flapping more frequently — ALERT-01/02/03 evidence within ~24h. Then ship ATT once Spectrum is clean. | ✓ |
| Simultaneous on both | Alerting-only change, no traffic-path risk — deploy to both hosts in one ritual. Fastest path; loses canary signal. | |
| Single host only (Spectrum), defer ATT to v1.46 | Ship v1.45 to Spectrum only; ATT stays on v1.44. Smallest blast radius but creates version-skew footgun. | |

**User's choice:** Spectrum first, ATT next-day

### Q4 — Pre-deploy gate

| Option | Description | Selected |
|--------|-------------|----------|
| Phase 210 verified + snapshot captured + /health.version readback (recommended) | Phase 210 already PASSED 11/11 on 2026-05-26. Add: pre-deploy snapshot landed, post-deploy /health.version reports 1.45.0 on both hosts. No predeploy-gate.py rerun. | ✓ |
| Re-run Phase 206 predeploy gate as a smoke test | Even though v1.43 baseline isn't right comparator, running it gives a fresh failure-mode signal. Cheap pulse-check. | |
| Re-run SAFE-10 check against worktree before deploy | Run check-safe07-source-diff.sh one more time at deploy-time to catch drift between Phase 210 PR-merge and deploy. Belt-and-suspenders. | |

**User's choice:** Phase 210 verified + snapshot captured + /health.version readback

---

## ALERT-03 verification approach

### Q1 — Primary signal

| Option | Description | Selected |
|--------|-------------|----------|
| Alerts-table row count vs episode duration (recommended) | For qualifying flapping event, count alerts.rows with rule_id='congestion_flapping' on that WAN+direction over episode. Expect O(1) row per episode. Authoritative operator-visible surface. | ✓ |
| journalctl line count for the congestion_flapping logger | ssh host 'journalctl -u wanctl@<wan>' | grep congestion_flapping over episode — confirm ~1 emission per cooldown_sec window. Closer to 'log-spam' wording but noisier. | |
| alert_engine.fire() invocation count via debug instrumentation | Add temporary instrumentation/log line and count fire() calls. More precise but violates SAFE-10's 'alert_engine semantics unchanged' invariant. | |

**User's choice:** Alerts-table row count vs episode duration

### Q2 — Secondary cross-check

| Option | Description | Selected |
|--------|-------------|----------|
| journalctl scan for log-spam (recommended) | After primary alerts-table row-count check, run journalctl grep over same window as sanity check. Cheap, independent surface. Captures 'log-spam' literal wording. | ✓ |
| Operator narrative only | Operator confirms qualitatively that the event 'felt right' — no log spam observed. Lightweight but unauditable. | |
| None — alerts-table count is sufficient | The alerts-table count IS the end-to-end signal. Skip cross-check. Minimal evidence trail; single signal. | |

**User's choice:** journalctl scan for log-spam

### Q3 — Required margin

| Option | Description | Selected |
|--------|-------------|----------|
| 1 row per episode (recommended) | Strict: cooldown_sec must produce exactly 1 alerts row for the qualifying episode. Matches 'alert-once-per-episode' literal wording in ALERT-03. | ✓ |
| <=3 rows per 10min episode | Allow some retries (e.g., cooldown_sec=300 = 5min cooldown, so 10-15min episode could fire 2-3x). Less strict. | |
| Operator-judgment, no fixed margin | Operator decides on the day whether row count looks reasonable. Flexible but unauditable. | |

**User's choice:** 1 row per episode

### Q4 — Fail-branch

| Option | Description | Selected |
|--------|-------------|----------|
| Block milestone close, open follow-up phase (recommended) | ALERT-03 is a literal v1.45 requirement — if dedup is broken end-to-end, v1.45 isn't shipped even if peak intensity is visible. Open follow-up phase. | ✓ |
| Ship v1.45 anyway, file todo for cooldown investigation | Treat ALERT-03 as soft — headline bug fixed, dedup is separate forensic. Risks shipping incomplete milestone. | |
| Roll back v1.45 entirely | Treat any ALERT-03 fail as hard regression and revert to v1.44. Aggressive — doesn't make sense if v1.44 also had log-spam. | |

**User's choice:** Block milestone close, open follow-up phase

---

## Milestone closure mechanics

### Q1 — Version bump location

| Option | Description | Selected |
|--------|-------------|----------|
| Single closeout commit BEFORE deploy (recommended) | Mirror Phase 209 D-11: one commit flips pyproject.toml + src/wanctl/__init__.py + docker/Dockerfile + CHANGELOG.md v1.45.0 heading. Deploy lands 1.45.0; rollback restores 1.44.0. | ✓ |
| Two commits — version + CHANGELOG separate | Version files in one commit, CHANGELOG entry in another. Cleaner per-concern but splits closeout shape. | |
| Defer version bump to post-VERIFY-01 | Deploy Phase 210 build labeled as 1.44.1-dev; only flip to 1.45.0 after VERIFY-01 passes. Cleaner semver but creates label-drift problem. | |

**User's choice:** Single closeout commit BEFORE deploy

### Q2 — SAFE-10 re-verification

| Option | Description | Selected |
|--------|-------------|----------|
| Run existing script against v1.45 anchor inline (recommended) | Re-run scripts/check-safe07-source-diff.sh with v1.44 close anchor (21ee630). No script edit — pass SHA as positional arg. | ✓ |
| Extend script with --v145-allowlist mode | Add new flag mirroring --att-config-whitelist that whitelists wan_controller.py:4275-4360 + version-bump lines. Repeatable, but adds surface area. | |
| Manual git diff inspection in 211-SAFE-10-CLOSEOUT.md | Skip script extension; capture git diff output in closeout doc, narrate expected hunks. Lightest tooling, no CI hookability. | |

**User's choice:** Run existing script against v1.45 anchor inline

### Q3 — Archive timing

| Option | Description | Selected |
|--------|-------------|----------|
| Same commit/PR as Phase 211 close (recommended) | Archive v1.45 phase dirs to .planning/milestones/v1.45-phases/ in same closeout PR as SAFE-10 verification. Single 'v1.45 closed' moment in git history. | ✓ |
| Separate /gsd:complete-milestone run after close | Phase 211 commits closeout artifacts in-place; archive happens later via dedicated milestone-complete command. Two-step but more reviewable. | |
| Defer archive until v1.46 starts | Leave v1.45 phase dirs at .planning/phases/ until v1.46 kicks off. Lighter-touch; risks drift between roadmap (v1.45 shipped) and on-disk state. | |

**User's choice:** Same commit/PR as Phase 211 close

### Q4 — CHANGELOG content

| Option | Description | Selected |
|--------|-------------|----------|
| Bug fix + ALERT-03 invariant note (recommended) | v1.45.0 heading documents flapping peak-counter bug fix, notes payload field additions/semantics, and explicitly states cooldown_sec dedup is unchanged. Operator-decision-driving. | ✓ |
| Bug fix line only | One-line entry: 'flapping_dl/ul peak_transition_count now reflects 120s-window peak instead of fire-cycle value'. Terse; loses operator context. | |
| Full Codex-review narrative | Include design-option-A rationale, Codex round-2 review citation, and Phase 210 verification status. Useful archive context but bloats CHANGELOG. | |

**User's choice:** Bug fix + ALERT-03 invariant note

---

## Claude's Discretion

- Exact wording of CHANGELOG.md v1.45.0 entry (D-16 constrains content; phrasing open).
- Plan breakdown shape (1 plan vs 3 plans) — planner's call to fold or split.
- Per-event JSON filename convention under `211-VERIFY-01-evidence/` (e.g., `alert-{id}.json` vs `flapping-{wan}-{ISO8601}.json`).
- Whether to add a small `scripts/capture-flapping-evidence.sh` helper for D-03 evidence capture.
- Whether the alerts-table SQL query lives in EVIDENCE.md or as a separate `211-VERIFY-01-evidence/QUERY.sql` file.
- Exact systemd-unit name and journalctl filter pattern for D-10 secondary cross-check.

## Deferred Ideas

- Operator-summary integration for peak-vs-threshold delta — future observability phase.
- Automated rollback trigger on ALERT-03 regression — alerting-only scope doesn't justify automation complexity.
- Phase 206 A/B harness extension for alerting-payload distributions — speculative.
- `scripts/capture-flapping-evidence.sh` operator-callable — small utility, planner's call.
- CHANGELOG.md broader v1.45 cleanup — its own phase if needed.
- Codex round-2 design-review narrative archive — could be promoted to `docs/decisions/` ADR if forensics need to cite it externally.
- SEED-003..007 deferred items — carried to v1.46+ per STATE.md; Phase 211 does not touch them.
