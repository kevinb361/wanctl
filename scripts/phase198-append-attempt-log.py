#!/usr/bin/env python3
"""Upsert one Plan 198-06 attempt entry in 198-06-ATTEMPT-LOG.md.

Reads <attempt-dir>/attempt-summary.json and either inserts a new
"## Attempt N" section or refreshes an existing one in place. The entry is
keyed on the attempt directory name via a hidden HTML-comment marker
(`<!-- attempt-key: rerun-attempt-N -->`), which makes the helper safe to
call repeatedly: when the JSON has changed since the last call (e.g. after
mark_retry mutated the decision field, or after the operator added notes),
the entry is rewritten in place; when nothing changed, it is a no-op.

Usage:
  scripts/phase198-append-attempt-log.py <attempt-dir> \\
      [--harness-log PATH] [--log-file PATH]

Designed to be safe to call:
  - inline from the cron retry script after each mark_retry, AND
  - manually for backfilling attempts the cron script never logged, AND
  - manually for refreshing entries after operator edits to the JSON.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

DEFAULT_LOG = Path(
    ".planning/phases/198-spectrum-cake-primary-b-leg-rerun/198-06-ATTEMPT-LOG.md"
)

SECTION_BOUNDARY = "\n---\n\n## "
END_PATTERN = "\n---\n\n"

# Harness log filename pattern, e.g. scheduled-attempt-20260430T073139Z-run1.log
_LOG_TS_RE = re.compile(r"(\d{8})T(\d{6})Z")


def _utc_from_log_path(harness_log: Path | None) -> str | None:
    """Extract an ISO-8601 UTC timestamp from a harness log filename.

    Filenames follow `scheduled-attempt-YYYYMMDDTHHMMSSZ-runN.log`. Returns
    `YYYY-MM-DDTHH:MM:SSZ` or None when the pattern is absent.
    """
    if harness_log is None:
        return None
    m = _LOG_TS_RE.search(harness_log.name)
    if m is None:
        return None
    d, t = m.group(1), m.group(2)
    return f"{d[0:4]}-{d[4:6]}-{d[6:8]}T{t[0:2]}:{t[2:4]}:{t[4:6]}Z"


def render_block(
    data: dict,
    attempt_key: str,
    attempt_dir: Path,
    attempt_n: int,
    head_sha_fallback: str,
    harness_log: Path | None,
) -> str:
    per = data.get("per_run_audit_verdicts") or []
    medians = data.get("throughput_medians_mbps") or []
    mom = data.get("throughput_median_of_medians_mbps")
    head_sha = data.get("head_sha") or head_sha_fallback or "unknown"

    # Authoritative field is `attempted_at_utc` (harness writes this on the
    # success path). Tolerate `start_utc` as an alias and fall back to the
    # harness log filename, which embeds the start timestamp even when the
    # harness died before populating the JSON (Plan 198-06 attempts 4-6).
    attempted_at = (
        data.get("attempted_at_utc")
        or data.get("start_utc")
        or _utc_from_log_path(harness_log)
        or "unknown"
    )

    fields: list[str] = [
        f"- **Attempted at (UTC):** {attempted_at}",
        f"- **Local hour at start:** "
        f"{data.get('local_hour_at_start') if data.get('local_hour_at_start') is not None else 'unknown'}",
        f"- **Off-peak window used:** {data.get('off_peak_window_used') or 'unknown'}",
        f"- **HEAD SHA at attempt:** {head_sha}",
        f"- **Failed:** {json.dumps(data.get('failed'))}",
        f"- **Harness exit code:** "
        f"{data.get('harness_exit_code') if data.get('harness_exit_code') is not None else 'unknown'}",
        f"- **Failure stage:** {data.get('failure_stage') or 'none'}",
        f"- **Completed runs:** "
        f"{data.get('completed_runs') if data.get('completed_runs') is not None else 'unknown'}",
        f"- **Throughput verdict:** {data.get('throughput_verdict') or 'n/a'}",
    ]
    for i, m in enumerate(medians, start=1):
        fields.append(f"  - run{i}: {m} Mbps")
    if mom is not None:
        fields.append(f"  - median-of-medians: {mom} Mbps")

    audits = " / ".join(str(v) for v in per) if per else "n/a"
    fields.append(f"- **Per-run loaded-window audit verdicts:** {audits}")
    all_pass = (
        isinstance(per, list)
        and len(per) > 0
        and all(str(v).lower() == "pass" for v in per)
    )
    fields.append(f"- **All per-run audits pass:** {json.dumps(all_pass)}")
    fields.append(f"- **Operator decision:** {data.get('decision') or 'pending'}")
    note = data.get("operator_note")
    if note:
        fields.append(f"- **Operator note:** {note}")
    fields.append(f"- **Evidence dir:** `{attempt_dir.as_posix()}`")
    if harness_log is not None:
        fields.append(f"- **Harness log:** `{harness_log.as_posix()}`")

    head = f"\n---\n\n## Attempt {attempt_n}\n<!-- attempt-key: {attempt_key} -->\n\n"
    body = "\n".join(fields) + "\n"
    return head + body


def find_section_block(text: str, marker: str) -> tuple[int, int] | None:
    """Locate the byte range of the section block containing `marker`.

    A section block runs from its leading `\\n---\\n\\n## ` separator (inclusive)
    up to the next `\\n---\\n\\n` separator (exclusive) or EOF.
    """
    if marker not in text:
        return None
    marker_pos = text.index(marker)
    start = text.rfind(SECTION_BOUNDARY, 0, marker_pos)
    if start == -1:
        return None
    next_sep = text.find(END_PATTERN, marker_pos)
    end = next_sep if next_sep != -1 else len(text)
    return start, end


def find_insert_point_numerical(text: str, attempt_n: int) -> int:
    """Locate the byte position to insert a section numbered `attempt_n`.

    Inserts in numerical order: before the first existing `## Attempt M`
    section where `M > attempt_n`. If every existing `M < attempt_n`, inserts
    after the last attempt section (before whatever follows, typically a
    WARNING block). If no attempt sections exist, appends at end.
    """
    matches = list(re.finditer(r"^## Attempt (\d+)", text, re.MULTILINE))
    if not matches:
        return len(text)

    for m in matches:
        existing_n = int(m.group(1))
        if existing_n > attempt_n:
            heading_pos = m.start()
            sep = text.rfind("\n---\n", 0, heading_pos)
            return sep if sep != -1 else heading_pos

    last_pos = matches[-1].start()
    next_sep = text.find(END_PATTERN, last_pos)
    return next_sep if next_sep != -1 else len(text)


def derive_attempt_number(data: dict, attempt_dir: Path) -> int:
    """Derive the attempt number strictly from the input — never from log state.

    Authoritative sources, in priority order:
      1. `attempt_number` field in attempt-summary.json (harness-assigned)
      2. The directory name `rerun-attempt-N`

    If both are present and disagree, raise — that is a real inconsistency the
    operator must resolve. Inferring N from log state (e.g. `max_existing + 1`)
    would silently misnumber out-of-order backfills and stale-edit refreshes.
    """
    json_n = data.get("attempt_number")
    dir_n: int | None = None
    m = re.match(r"^rerun-attempt-(\d+)$", attempt_dir.name)
    if m:
        dir_n = int(m.group(1))

    if json_n is None and dir_n is None:
        raise ValueError(
            f"cannot derive attempt_number: JSON has no field and dir name "
            f"{attempt_dir.name!r} does not match rerun-attempt-N"
        )
    if json_n is not None and dir_n is not None and int(json_n) != dir_n:
        raise ValueError(
            f"attempt_number mismatch for {attempt_dir}: "
            f"JSON={json_n} dir={dir_n} — refusing to guess"
        )
    return int(json_n) if json_n is not None else dir_n  # type: ignore[return-value]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("attempt_dir", type=Path, help="rerun-attempt-N directory")
    ap.add_argument("--harness-log", type=Path, default=None)
    ap.add_argument("--log-file", type=Path, default=DEFAULT_LOG)
    args = ap.parse_args()

    summary_path = args.attempt_dir / "attempt-summary.json"
    if not summary_path.exists():
        print(f"no attempt-summary.json in {args.attempt_dir}", file=sys.stderr)
        return 1

    attempt_key = args.attempt_dir.name
    text = args.log_file.read_text() if args.log_file.exists() else ""
    marker = f"<!-- attempt-key: {attempt_key} -->"

    data = json.loads(summary_path.read_text())
    head_sha_fallback = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    ).stdout.strip()

    try:
        attempt_n = derive_attempt_number(data, args.attempt_dir)
    except ValueError as exc:
        print(f"refusing to write: {exc}", file=sys.stderr)
        return 1

    block = render_block(
        data,
        attempt_key,
        args.attempt_dir,
        attempt_n,
        head_sha_fallback,
        args.harness_log,
    )

    bounds = find_section_block(text, marker)
    if bounds is None:
        text_without = text
        op = "inserted"
    else:
        start, end = bounds
        text_without = text[:start] + text[end:]
        op = "updated"

    insert_at = find_insert_point_numerical(text_without, attempt_n)
    new_text = text_without[:insert_at] + block + text_without[insert_at:]

    if new_text == text:
        print(f"unchanged: attempt {attempt_n} ({attempt_key})")
        return 0
    args.log_file.write_text(new_text)
    print(f"{op}: attempt {attempt_n} ({attempt_key})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
