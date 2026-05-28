import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
MATRIX_SUMMARY = REPO_ROOT / "scripts/phase214-matrix-summary.py"


def _load_module():
    if not MATRIX_SUMMARY.exists():
        pytest.skip("scripts/phase214-matrix-summary.py not built yet")
    spec = importlib.util.spec_from_file_location("phase214_matrix_summary", MATRIX_SUMMARY)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sheet(
    window: str,
    run_dir: str,
    *,
    verdict: str = "pass",
    primary_driver: str | None = None,
    ranked: list[str] | None = None,
    signal_disposition: str = "none",
    p50_ms: float = 10.0,
    p95_ms: float = 20.0,
    p99_ms: float = 30.0,
    wan: str = "spectrum",
) -> dict:
    ranked = ranked or []
    return {
        "phase": 214,
        "run_dir": run_dir,
        "started_utc": "2026-06-01T00:00:00+00:00",
        "ended_utc": "2026-06-01T00:01:00+00:00",
        "window": window,
        "wan": wan,
        "latency": {"p50_ms": p50_ms, "p95_ms": p95_ms, "p99_ms": p99_ms},
        "verdict": verdict,
        "primary_driver": primary_driver,
        "ranked": ranked,
        "signal_disposition": signal_disposition,
    }


def _write_signal_sheet(evidence_root: Path, sheet: dict) -> Path:
    out = evidence_root / sheet["run_dir"] / sheet["wan"] / "tcp_12down" / "signal-sheet.json"
    out.parent.mkdir(parents=True)
    out.write_text(json.dumps(sheet, indent=2) + "\n", encoding="utf-8")
    return out


def _run_cli(evidence_root: Path, output_json: Path, *extra_args: str) -> subprocess.CompletedProcess[str]:
    if not MATRIX_SUMMARY.exists():
        pytest.skip("scripts/phase214-matrix-summary.py not built yet")
    return subprocess.run(
        [
            sys.executable,
            str(MATRIX_SUMMARY),
            "--evidence-root",
            str(evidence_root),
            "--output-json",
            str(output_json),
            *extra_args,
        ],
        capture_output=True,
        text=True,
        timeout=20,
    )


def test_matrix_summary_script_exists() -> None:
    assert MATRIX_SUMMARY.exists(), "scripts/phase214-matrix-summary.py must exist"


def test_matrix_verdict_all_pass() -> None:
    module = _load_module()
    assert module.matrix_verdict(["pass", "pass", "pass"]) == "pass"


def test_matrix_verdict_any_fail() -> None:
    module = _load_module()
    assert module.matrix_verdict(["pass", "fail", "ambiguous"]) == "fail"


def test_matrix_verdict_any_ambiguous() -> None:
    module = _load_module()
    assert module.matrix_verdict(["pass", "pass", "ambiguous"]) == "ambiguous"


def test_matrix_verdict_empty() -> None:
    module = _load_module()
    with pytest.raises(ValueError, match="at least one"):
        module.matrix_verdict([])


def test_matrix_verdict_partial_flag() -> None:
    module = _load_module()
    assert module.matrix_verdict(["pass", "pass"], full_window_set=False) == "partial"
    assert module.matrix_verdict(["pass", "pass", "pass"], full_window_set=True) == "pass"
    assert module.matrix_verdict(["pass", "fail"], full_window_set=False) == "fail"


def test_build_summary_lex_ordering() -> None:
    module = _load_module()
    sheets = [
        _sheet("prime-time", "RUN-20260602T2000Z"),
        _sheet("off-peak", "RUN-20260601T0300Z"),
        _sheet("daytime", "RUN-20260601T1400Z"),
    ]
    summary = module.build_matrix_summary(sheets)
    assert [row["run_dir"] for row in summary["windows"]] == [
        "RUN-20260601T0300Z",
        "RUN-20260601T1400Z",
        "RUN-20260602T2000Z",
    ]


def test_build_summary_primary_driver_aggregation() -> None:
    module = _load_module()
    sheets = [
        _sheet("off-peak", "RUN-a", verdict="fail", primary_driver="reflector_loss", ranked=["reflector_loss"]),
        _sheet("daytime", "RUN-b", verdict="ambiguous", primary_driver="cake_queue_mismatch", ranked=["cake_queue_mismatch"]),
        _sheet("prime-time", "RUN-c", verdict="fail", primary_driver="reflector_loss", ranked=["reflector_loss"]),
    ]
    summary = module.build_matrix_summary(sheets)
    assert summary["primary_driver"] == "reflector_loss"


def test_build_summary_signal_disposition_aggregation() -> None:
    module = _load_module()
    sheets = [
        _sheet("off-peak", "RUN-a", verdict="fail", signal_disposition="form_b"),
        _sheet("daytime", "RUN-b", verdict="fail", signal_disposition="form_c"),
        _sheet("prime-time", "RUN-c", verdict="fail", signal_disposition="form_b"),
    ]
    summary = module.build_matrix_summary(sheets)
    assert summary["signal_disposition"] == "form_b"


def test_matrix_summary_missing_window_fails_closed(tmp_path: Path) -> None:
    evidence_root = tmp_path / "evidence"
    _write_signal_sheet(evidence_root, _sheet("daytime", "RUN-20260601T1400Z"))
    _write_signal_sheet(evidence_root, _sheet("prime-time", "RUN-20260602T2000Z"))

    result = _run_cli(evidence_root, tmp_path / "matrix-summary.json")

    assert result.returncode == 1
    assert "missing required Spectrum window" in result.stderr
    assert "off-peak" in result.stderr


def test_matrix_summary_partial_requires_reason(tmp_path: Path) -> None:
    evidence_root = tmp_path / "evidence"
    _write_signal_sheet(evidence_root, _sheet("daytime", "RUN-20260601T1400Z"))
    _write_signal_sheet(evidence_root, _sheet("prime-time", "RUN-20260602T2000Z"))

    missing_reason = _run_cli(evidence_root, tmp_path / "out-1.json", "--allow-partial")
    missing_flag = _run_cli(evidence_root, tmp_path / "out-2.json", "--partial-reason", "operator accepted missing off-peak")

    assert missing_reason.returncode != 0
    assert missing_flag.returncode != 0
    assert "--allow-partial and --partial-reason must be passed together" in (missing_reason.stderr + missing_flag.stderr)


def test_matrix_summary_partial_is_never_pass(tmp_path: Path) -> None:
    evidence_root = tmp_path / "evidence"
    _write_signal_sheet(evidence_root, _sheet("daytime", "RUN-20260601T1400Z", verdict="pass"))
    _write_signal_sheet(evidence_root, _sheet("prime-time", "RUN-20260602T2000Z", verdict="pass"))
    output_json = tmp_path / "matrix-summary.json"

    result = _run_cli(evidence_root, output_json, "--allow-partial", "--partial-reason", "off-peak window unavailable for 5 days")

    assert result.returncode == 0, result.stderr
    summary = json.loads(output_json.read_text(encoding="utf-8"))
    assert summary["verdict"] == "partial"
    assert summary["partial_reason"] == "off-peak window unavailable for 5 days"
    assert summary["missing_windows"] == ["off-peak"]


def test_cli_emits_matrix_summary_against_synthesized_evidence(tmp_path: Path) -> None:
    evidence_root = tmp_path / "evidence"
    _write_signal_sheet(evidence_root, _sheet("off-peak", "RUN-20260601T0300Z"))
    _write_signal_sheet(evidence_root, _sheet("daytime", "RUN-20260601T1400Z"))
    _write_signal_sheet(evidence_root, _sheet("prime-time", "RUN-20260602T2000Z"))
    output_json = tmp_path / "matrix-summary.json"

    result = _run_cli(evidence_root, output_json)

    assert result.returncode == 0, result.stderr
    summary = json.loads(output_json.read_text(encoding="utf-8"))
    assert {
        "phase",
        "started_utc",
        "ended_utc",
        "git_head_sha",
        "verdict",
        "primary_driver",
        "ranked_drivers",
        "windows",
        "signal_disposition",
        "mutation_posture",
        "partial_reason",
        "missing_windows",
    } <= set(summary)
