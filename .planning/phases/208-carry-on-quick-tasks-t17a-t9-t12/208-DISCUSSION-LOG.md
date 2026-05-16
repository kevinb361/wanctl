# Phase 208: Carry-on quick-tasks (T17a / T9 / T12) - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-15
**Phase:** 208-carry-on-quick-tasks-t17a-t9-t12
**Areas discussed:** Aggregator contract, Ingestion-rate output, Digest permission guard

---

## Todo Folding

| Option | Description | Selected |
|--------|-------------|----------|
| T9 + T12 only | Fold ingestion-rate and operator-summary permission todos; leave unrelated/future items deferred. | yes |
| T9 only | Fold only ingestion-rate todo. | |
| T12 only | Fold only operator-summary permission todo. | |
| None | Do not fold pending todos. | |

**User's choice:** T9 + T12 only.
**Notes:** Storage/tuning/Silicom/ATT matches were reviewed as false positives or future work and left deferred.

---

## Gray Area Selection

| Option | Description | Selected |
|--------|-------------|----------|
| All three areas | Cover aggregator schema/fail-closed behavior, ingestion-rate output contract, and digest permission handling. | yes |
| Aggregator contract | TOOL-01 schema contract and Phase 207 advisory warning. | |
| Ingestion-rate output | TOOL-02 human/JSON output and rate semantics. | |
| Digest permission guard | TOOL-03 skip-message and no-raise behavior. | |

**User's choice:** All three areas.

---

## Aggregator Contract

| Question | Option | Description | Selected |
|----------|--------|-------------|----------|
| Should TOOL-01 fix the advisory false-pass? | Fix it now | Treat as part of stabilizing the aggregator schema contract. | yes |
| Should TOOL-01 fix the advisory false-pass? | Schema only | Only confirm v1.43/v1.44 schema round-trip. | |
| Should TOOL-01 fix the advisory false-pass? | Document only | Record risk but do not plan code changes. | |
| What should schema proof look like? | Golden round-trip | Use fixture/golden JSON checks for v1.43 reference and v1.44 fresh-style summaries. | yes |
| What should schema proof look like? | Key-set only | Assert exact keys without full golden comparison. | |
| What should schema proof look like? | Loose compatibility | Only assert consumers do not crash. | |
| How strict should invalid config handling be? | Fail verdict with reason | Keep output shape stable, set verdict fail, value 0.0, and reason. | yes |
| How strict should invalid config handling be? | Raise exception | Abort aggregation immediately. | |
| How strict should invalid config handling be? | Warn and continue | Warn but keep defaults. | |

**User's choice:** Fix it now; Golden round-trip; Fail verdict with reason.
**Notes:** This closes Phase 207 review WR-01 inside TOOL-01.

---

## Ingestion-Rate Output

| Question | Option | Description | Selected |
|----------|--------|-------------|----------|
| Human output shape | Compact table | One row per WAN with database/window/rows/rates. | yes |
| Human output shape | Plain lines | One readable line per WAN. | |
| Human output shape | Summary only | One merged total. | |
| JSON shape | Object with wans | Top-level metadata plus `wans` array. | yes |
| JSON shape | Array only | Only an array of per-WAN rows. | |
| JSON shape | Match table fields | JSON rows mirror table columns only. | |
| Windowed mean definition | Selected time range | Count divided by requested time window duration. | yes |
| Windowed mean definition | Observed span | First-to-last row timestamp span. | |
| Windowed mean definition | Both values | Emit both requested and observed rates. | |
| Filter behavior | Respect all filters | Reuse `--db`, `--wan`, and time range. | yes |
| Filter behavior | Time range only | Ignore WAN filter. | |
| Filter behavior | No filters | Always default recent window. | |

**User's choice:** Compact table; Object with wans; Selected time range; Respect all filters.
**Notes:** Per-WAN rows/sec is the locked requirement; per-metric breakdown from the folded todo is optional only if it does not expand scope.

---

## Digest Permission Guard

| Question | Option | Description | Selected |
|----------|--------|-------------|----------|
| Write failure behavior | Skip line continue | Catch output/write OSError, log stable skip, continue remaining WAN DBs. | yes |
| Write failure behavior | Fail command | Return non-zero. | |
| Write failure behavior | Skip all digest | Stop emitting digest lines but return success. | |
| Skip message | stderr stable prefix | Stable stderr line with WAN/db context. | yes |
| Skip message | logger only | Use Python logging. | |
| Skip message | stdout note | Put skip note in normal output. | |
| Catch scope | OSError only | Catch output/digest-write OS failures only. | yes |
| Catch scope | PermissionError only | Catch only PermissionError. | |
| Catch scope | Broad exceptions | Catch everything in digest mode. | |
| Test injection | Mock write failure | Deterministic monkeypatch of write/emission boundary. | yes |
| Test injection | Filesystem perms | chmod-based permission scenario. | |
| Test injection | Both | Unit plus filesystem scenario. | |
| DB/read vs output conflict | Both, narrowly | Handle unreadable DBs and output-write OSError narrowly. | yes |
| DB/read vs output conflict | Unreadable DBs only | Follow folded todo literally. | |
| DB/read vs output conflict | Output write only | Follow ROADMAP wording literally. | |

**User's choice:** Skip line continue; stderr stable prefix; OSError only; Mock write failure; Both, narrowly.
**Notes:** The extra clarification resolved a conflict between ROADMAP wording and the folded T12 todo.

---

## the agent's Discretion

- Exact helper names and table widths.
- Whether per-metric ingestion breakdown can fit without expanding TOOL-02 scope.

## Deferred Ideas

- T6/T7 storage-hygiene optimization and related storage audit todos.
- SEED-005 conservative UL tuning sweep.
- T17(b) CALIB-02 YAML knob-shape evaluation.
- Unrelated tuning, steering, Silicom, archive cleanup, and ATT canary todos surfaced by keyword matching.
