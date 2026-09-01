"""TUNE-003: Recommendation output framework tests.

Proof: deterministic historical/synthetic replays cover keep, no-change,
revert, stale-data, and conflicting-dimension outcomes; changed-path
and command-surface review proves read-only behavior.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from wanctl.tuning.recommendation import (
    FORBIDDEN_MODULES,
    MIN_CONFIDENCE_TO_RECOMMEND,
    Recommendation,
    RecommendationAction,
    ScoringDimension,
    TelemetryHealth,
    check_telemetry_health,
    make_no_change_recommendation,
    score_and_recommend,
    verify_read_only,
)

RECOMMENDATION_MODULE = (
    Path(__file__).resolve().parent.parent.parent
    / "src"
    / "wanctl"
    / "tuning"
    / "recommendation.py"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _healthy_telemetry(
    data_points: int = 1000, expected: int = 1000, staleness: float = 10.0
) -> TelemetryHealth:
    return check_telemetry_health(data_points, expected, staleness)


def _positive_dimensions() -> list[ScoringDimension]:
    return [
        ScoringDimension("congestion_reduction", 0.8, 0.5, 0.1, "RED fraction decreased"),
        ScoringDimension("latency_improvement", 0.6, 0.3, 0.2, "p95 RTT decreased"),
        ScoringDimension("throughput_stability", 0.4, 0.2, 0.3, "throughput variance unchanged"),
    ]


def _negative_dimensions() -> list[ScoringDimension]:
    return [
        ScoringDimension("congestion_increase", -0.7, 0.5, 0.1, "RED fraction increased"),
        ScoringDimension("latency_degradation", -0.5, 0.3, 0.2, "p95 RTT increased"),
    ]


def _conflicting_dimensions() -> list[ScoringDimension]:
    return [
        ScoringDimension("congestion_reduction", 0.3, 0.5, 0.4, "slight RED decrease"),
        ScoringDimension("latency_degradation", -0.29, 0.5, 0.4, "slight RTT increase"),
    ]


# ---------------------------------------------------------------------------
# Telemetry health
# ---------------------------------------------------------------------------


class TestTelemetryHealth:
    def test_accepts_fresh_complete_data(self) -> None:
        health = _healthy_telemetry()
        assert health.is_stale is False
        assert health.is_incomplete is False
        assert health.rejection_reasons == []

    def test_rejects_stale_data(self) -> None:
        health = _healthy_telemetry(staleness=600)
        assert health.is_stale is True
        assert "stale" in health.rejection_reasons[0]

    def test_rejects_incomplete_data(self) -> None:
        health = _healthy_telemetry(data_points=800, expected=1000)
        assert health.is_incomplete is True
        assert "coverage" in health.rejection_reasons[0]

    def test_rejects_both_stale_and_incomplete(self) -> None:
        health = _healthy_telemetry(data_points=500, expected=1000, staleness=600)
        assert health.is_stale is True
        assert health.is_incomplete is True
        assert len(health.rejection_reasons) == 2

    def test_zero_expected_points(self) -> None:
        health = check_telemetry_health(0, 0, 10.0)
        assert health.is_incomplete is True


# ---------------------------------------------------------------------------
# Scoring dimension validation
# ---------------------------------------------------------------------------


class TestScoringDimension:
    def test_rejects_empty_name(self) -> None:
        with pytest.raises(ValueError, match="dimension name must not be empty"):
            ScoringDimension("", 0.5, 0.5, 0.1, "desc")

    def test_rejects_weight_out_of_range(self) -> None:
        with pytest.raises(ValueError, match="weight must be in"):
            ScoringDimension("test", 0.5, 1.5, 0.1, "desc")

    def test_rejects_uncertainty_out_of_range(self) -> None:
        with pytest.raises(ValueError, match="uncertainty must be in"):
            ScoringDimension("test", 0.5, 0.5, -0.1, "desc")


# ---------------------------------------------------------------------------
# Recommendation: stale data rejection
# ---------------------------------------------------------------------------


class TestStaleDataRejection:
    def test_stale_telemetry_produces_no_change(self) -> None:
        health = _healthy_telemetry(staleness=600)
        rec = score_and_recommend(
            "target_bloat_ms",
            "spectrum",
            15.0,
            20.0,
            _positive_dimensions(),
            health,
        )
        assert rec.action == RecommendationAction.NO_CHANGE
        assert "stale" in rec.rationale

    def test_incomplete_telemetry_produces_no_change(self) -> None:
        health = _healthy_telemetry(data_points=500, expected=1000)
        rec = score_and_recommend(
            "target_bloat_ms",
            "spectrum",
            15.0,
            20.0,
            _positive_dimensions(),
            health,
        )
        assert rec.action == RecommendationAction.NO_CHANGE
        assert "coverage" in rec.rationale

    def test_stale_data_cannot_produce_keep(self) -> None:
        """Even with strongly positive dimensions, stale data must reject."""
        health = _healthy_telemetry(staleness=9999)
        rec = score_and_recommend(
            "target_bloat_ms",
            "spectrum",
            15.0,
            20.0,
            _positive_dimensions(),
            health,
        )
        assert rec.action != RecommendationAction.KEEP

    def test_stale_data_cannot_produce_revert(self) -> None:
        health = _healthy_telemetry(staleness=9999)
        rec = score_and_recommend(
            "target_bloat_ms",
            "spectrum",
            15.0,
            20.0,
            _negative_dimensions(),
            health,
        )
        assert rec.action != RecommendationAction.REVERT


# ---------------------------------------------------------------------------
# Recommendation: keep
# ---------------------------------------------------------------------------


class TestKeepRecommendation:
    def test_positive_dimensions_produce_keep(self) -> None:
        rec = score_and_recommend(
            "target_bloat_ms",
            "spectrum",
            15.0,
            20.0,
            _positive_dimensions(),
            _healthy_telemetry(),
        )
        assert rec.action == RecommendationAction.KEEP
        assert rec.proposed_value == 20.0
        assert rec.confidence >= MIN_CONFIDENCE_TO_RECOMMEND

    def test_keep_exposes_weighted_score(self) -> None:
        rec = score_and_recommend(
            "target_bloat_ms",
            "spectrum",
            15.0,
            20.0,
            _positive_dimensions(),
            _healthy_telemetry(),
        )
        assert rec.weighted_score > 0

    def test_keep_exposes_all_dimensions(self) -> None:
        rec = score_and_recommend(
            "target_bloat_ms",
            "spectrum",
            15.0,
            20.0,
            _positive_dimensions(),
            _healthy_telemetry(),
        )
        assert len(rec.dimensions) == 3
        d = rec.to_dict()
        assert len(d["dimensions"]) == 3
        assert d["weighted_score"] > 0


# ---------------------------------------------------------------------------
# Recommendation: revert
# ---------------------------------------------------------------------------


class TestRevertRecommendation:
    def test_negative_dimensions_produce_revert(self) -> None:
        rec = score_and_recommend(
            "target_bloat_ms",
            "spectrum",
            20.0,
            15.0,
            _negative_dimensions(),
            _healthy_telemetry(),
        )
        assert rec.action == RecommendationAction.REVERT
        assert rec.weighted_score < 0


# ---------------------------------------------------------------------------
# Recommendation: conflicting dimensions
# ---------------------------------------------------------------------------


class TestConflictingDimensions:
    def test_near_zero_weighted_score_produces_no_change(self) -> None:
        rec = score_and_recommend(
            "target_bloat_ms",
            "spectrum",
            15.0,
            20.0,
            _conflicting_dimensions(),
            _healthy_telemetry(),
        )
        assert rec.action == RecommendationAction.NO_CHANGE
        assert "conflicting" in rec.rationale

    def test_no_dimensions_produces_no_change(self) -> None:
        rec = score_and_recommend(
            "target_bloat_ms",
            "spectrum",
            15.0,
            20.0,
            [],
            _healthy_telemetry(),
        )
        assert rec.action == RecommendationAction.NO_CHANGE


# ---------------------------------------------------------------------------
# Recommendation: low confidence
# ---------------------------------------------------------------------------


class TestLowConfidence:
    def test_high_uncertainty_produces_no_change(self) -> None:
        dims = [
            ScoringDimension("dim1", 0.8, 0.5, 0.9, "very uncertain"),
            ScoringDimension("dim2", 0.7, 0.5, 0.95, "extremely uncertain"),
        ]
        rec = score_and_recommend(
            "target_bloat_ms",
            "spectrum",
            15.0,
            20.0,
            dims,
            _healthy_telemetry(),
        )
        assert rec.action == RecommendationAction.NO_CHANGE
        assert rec.is_low_confidence is True


# ---------------------------------------------------------------------------
# Recommendation: serialization
# ---------------------------------------------------------------------------


class TestSerialization:
    def test_round_trip_through_json(self) -> None:
        rec = score_and_recommend(
            "target_bloat_ms",
            "spectrum",
            15.0,
            20.0,
            _positive_dimensions(),
            _healthy_telemetry(),
        )
        json_str = rec.to_json()
        restored = Recommendation.from_dict(__import__("json").loads(json_str))
        assert restored.action == rec.action
        assert restored.parameter == rec.parameter
        assert restored.wan == rec.wan

    def test_to_dict_contains_derived_fields(self) -> None:
        rec = score_and_recommend(
            "target_bloat_ms",
            "spectrum",
            15.0,
            20.0,
            _positive_dimensions(),
            _healthy_telemetry(),
        )
        d = rec.to_dict()
        assert "weighted_score" in d
        assert "max_uncertainty" in d
        assert "is_low_confidence" in d


# ---------------------------------------------------------------------------
# Recommendation: constructor validation
# ---------------------------------------------------------------------------


class TestConstructorValidation:
    def test_stale_telemetry_must_be_no_change(self) -> None:
        health = TelemetryHealth(
            coverage_ratio=1.0,
            staleness_seconds=600,
            data_points=100,
            expected_data_points=100,
            is_stale=True,
            is_incomplete=False,
        )
        with pytest.raises(ValueError, match="must produce NO_CHANGE"):
            Recommendation(
                action=RecommendationAction.KEEP,
                parameter="x",
                wan="spectrum",
                current_value=1,
                proposed_value=2,
                confidence=0.8,
                dimensions=[],
                telemetry_health=health,
                rationale="test",
                generated_at="2026-01-01T00:00:00+00:00",
            )

    def test_conflicting_dimensions_must_be_no_change(self) -> None:
        dims = [
            ScoringDimension("a", 0.02, 0.5, 0.1, "slight positive"),
            ScoringDimension("b", -0.02, 0.5, 0.1, "slight negative"),
        ]
        with pytest.raises(ValueError, match="conflicting dimensions"):
            Recommendation(
                action=RecommendationAction.KEEP,
                parameter="x",
                wan="spectrum",
                current_value=1,
                proposed_value=2,
                confidence=0.8,
                dimensions=dims,
                telemetry_health=_healthy_telemetry(),
                rationale="test",
                generated_at="2026-01-01T00:00:00+00:00",
            )


# ---------------------------------------------------------------------------
# Read-only proof
# ---------------------------------------------------------------------------


class TestReadOnlyProof:
    def test_no_forbidden_imports(self) -> None:
        violations = verify_read_only(str(RECOMMENDATION_MODULE))
        import_violations = [v for v in violations if "import" in v]
        assert import_violations == [], f"forbidden imports found: {import_violations}"

    def test_no_control_patterns(self) -> None:
        violations = verify_read_only(str(RECOMMENDATION_MODULE))
        control_violations = [v for v in violations if "control pattern" in v]
        assert control_violations == [], f"control patterns found: {control_violations}"

    def test_module_has_no_file_write_surface(self) -> None:
        """The recommendation module never opens files for writing.

        Asserted against the code *before* verify_read_only, so the checker's own
        literals cannot satisfy the test. The original used an ``or`` disjunction
        that passed whenever its first operand held, making it vacuous.
        """
        source = RECOMMENDATION_MODULE.read_text()
        before_checker = source.split("def _scan_import_surface")[0]
        # Comments are not surface. The checker's own control_patterns scan skips
        # them for the same reason; without this, a comment mentioning open() reads
        # as a write path.
        code_only = "\n".join(
            line for line in before_checker.splitlines() if not line.strip().startswith("#")
        )
        for surface in ("open(", "write_text(", "write_bytes(", "writelines("):
            assert surface not in code_only, f"write surface {surface!r} present"

    def test_module_has_no_subprocess_surface(self) -> None:
        violations = verify_read_only(str(RECOMMENDATION_MODULE))
        subprocess_violations = [
            v for v in violations if "subprocess" in v or "os.system" in v or "os.popen" in v
        ]
        assert subprocess_violations == [], f"subprocess violations: {subprocess_violations}"


# ---------------------------------------------------------------------------
# make_no_change_recommendation
# ---------------------------------------------------------------------------


class TestMakeNoChange:
    def test_produces_no_change_with_none_proposed_value(self) -> None:
        rec = make_no_change_recommendation(
            "target_bloat_ms",
            "spectrum",
            15.0,
            _healthy_telemetry(),
            "current config is optimal",
        )
        assert rec.action == RecommendationAction.NO_CHANGE
        assert rec.proposed_value is None
        assert rec.confidence == 1.0


class TestReadOnlyProofDiscriminates:
    """AUD-v1.67-001: the checker must be able to FAIL, not just return clean.

    Every pre-existing test asserted an empty result against the real module, so
    a checker that could never detect anything passed all of them. The original
    forbidden list held "os.system"/"os.popen" -- attribute paths, not importable
    module names -- so they could never match an import node, and bare ``os`` plus
    every network module went undetected. Dynamic imports bypassed it entirely.
    """

    @staticmethod
    def _write(tmp_path, body: str):
        bad = tmp_path / "candidate_module.py"
        bad.write_text(body)
        return str(bad)

    def test_detects_dynamic_import_of_subprocess(self, tmp_path):
        path = self._write(tmp_path, 'def f(c):\n    __import__("subprocess").run(c)\n')
        violations = verify_read_only(path)
        assert violations, "dynamic __import__ escaped the checker"
        assert any("dynamic import call" in v for v in violations)

    def test_detects_importlib_indirection(self, tmp_path):
        path = self._write(
            tmp_path,
            'import importlib\n\n\ndef f(c):\n    importlib.import_module("subprocess").run(c)\n',
        )
        assert any("dynamic import call" in v for v in verify_read_only(path))

    def test_detects_bare_os_import(self, tmp_path):
        path = self._write(tmp_path, "import os\n\n\ndef f(c):\n    os.system(c)\n")
        violations = verify_read_only(path)
        assert any("forbidden import: os" in v for v in violations), violations

    @pytest.mark.parametrize(
        "module", ["subprocess", "socket", "urllib", "requests", "httpx", "shutil", "sqlite3"]
    )
    def test_detects_process_and_network_imports(self, tmp_path, module):
        path = self._write(tmp_path, f"import {module}\n")
        assert any(f"forbidden import: {module}" in v for v in verify_read_only(path))

    def test_detects_from_import_form(self, tmp_path):
        path = self._write(tmp_path, "from os import system\n")
        assert any("forbidden import from: os" in v for v in verify_read_only(path))

    def test_auditor_reproduction_no_longer_returns_clean(self, tmp_path):
        """The exact synthetic module the audit fed it, which returned []."""
        path = self._write(
            tmp_path,
            "import os\n\n\ndef sneaky(cmd):\n"
            '    __import__("subprocess").run(cmd)\n'
            "    os.system(cmd)\n",
        )
        violations = verify_read_only(path)
        assert len(violations) >= 2, violations

    def test_clean_module_still_returns_empty(self, tmp_path):
        """Discrimination must not come from flagging everything."""
        path = self._write(
            tmp_path,
            "import json\nfrom dataclasses import dataclass\n\n\n"
            "def f(d):\n    return json.dumps(d)\n",
        )
        assert verify_read_only(path) == []

    def test_forbidden_modules_are_importable_names(self):
        """Guards the original defect class: attribute paths can never match."""
        for name in FORBIDDEN_MODULES:
            assert "." not in name, f"{name!r} is not a top-level module name"


class TestReadOnlyProofClosesKnownBypasses:
    """AUD-v1.67-011: the nine bypass forms the second re-audit executed.

    Every one of these previously returned an empty violation list. They are kept
    verbatim so a future weakening of the checker fails here rather than being
    rediscovered by the next audit.
    """

    @staticmethod
    def _write(tmp_path, body: str) -> str:
        f = tmp_path / "candidate.py"
        f.write_text(body)
        return str(f)

    @pytest.mark.parametrize(
        ("label", "body", "expected"),
        [
            (
                "aliased-import-module",
                'from importlib import import_module as _load\n\n\ndef f(c):\n    _load("subprocess").run(c)\n',
                "importlib",
            ),
            (
                "getattr-importlib",
                'import importlib\n\n\ndef f(c):\n    getattr(importlib, "import_module")("subprocess").run(c)\n',
                "importlib",
            ),
            (
                "getattr-builtins-split-name",
                'import builtins\n\n\ndef f(c):\n    getattr(builtins, "__imp" + "ort__")("os").system(c)\n',
                "builtins",
            ),
            ("exec", 'def f(c):\n    exec("import subprocess; subprocess.run(c)")\n', "exec"),
            ("eval", "def f(c):\n    eval('__imp' + 'ort__(\"os\").system(c)')\n", "eval"),
            (
                "pathlib-write-text",
                'import pathlib\n\n\ndef f(cfg):\n    pathlib.Path("/etc/wanctl/x.yaml").write_text(cfg)\n',
                "write_text",
            ),
            (
                "pathlib-open-writelines",
                'import pathlib\n\n\ndef f(x):\n    pathlib.Path("/tmp/a").open("w").writelines(x)\n',
                "writelines",
            ),
            ("ctypes", "import ctypes\n", "ctypes"),
            (
                "asyncio-subprocess",
                "import asyncio\n\n\nasync def f(c):\n    await asyncio.create_subprocess_shell(c)\n",
                "asyncio",
            ),
        ],
    )
    def test_known_bypass_is_detected(self, tmp_path, label, body, expected):
        violations = verify_read_only(self._write(tmp_path, body))
        assert violations, f"{label} still returns no violations"
        assert any(expected in v for v in violations), (label, violations)

    def test_open_in_write_mode_is_detected(self, tmp_path):
        path = self._write(tmp_path, 'def f(x):\n    open("/etc/wanctl/x.yaml", "w").write(x)\n')
        assert any("write" in v for v in verify_read_only(path))

    @pytest.mark.parametrize("mode", ["w", "a", "x", "r+"])
    def test_every_write_mode_counts(self, tmp_path, mode):
        path = self._write(tmp_path, f'def f():\n    open("/tmp/a", "{mode}")\n')
        assert any("open()" in v for v in verify_read_only(path))

    def test_reading_stays_legal(self, tmp_path):
        """pathlib is not banned outright -- reading is this module's own use."""
        path = self._write(
            tmp_path, "import pathlib\n\n\ndef f(p):\n    return pathlib.Path(p).read_text()\n"
        )
        assert verify_read_only(path) == []

    def test_open_for_reading_stays_legal(self, tmp_path):
        path = self._write(tmp_path, 'def f(p):\n    return open(p, "r").read()\n')
        assert not any("open()" in v for v in verify_read_only(path))

    def test_checker_self_verifies_without_an_exemption(self):
        """The checker must pass its own check with no special-casing.

        It uses pathlib for read_text() only. If a future edit reaches for getattr
        or a write method here, this fails rather than being silently exempted.
        """
        assert verify_read_only(str(RECOMMENDATION_MODULE)) == []

    @pytest.mark.parametrize("method", ["unlink", "mkdir", "rmdir", "rename", "touch", "chmod"])
    def test_ast_only_write_methods_are_detected(self, tmp_path, method):
        """Write methods with no `control_patterns` entry.

        The string scan independently catches write_text/write_bytes/writelines, so
        a probe using those cannot prove the AST check does anything -- deleting it
        leaves them passing. These methods are caught by the AST check alone.
        """
        path = self._write(
            tmp_path,
            f'import pathlib\n\n\ndef f():\n    pathlib.Path("/etc/wanctl/x.yaml").{method}()\n',
        )
        violations = verify_read_only(path)
        assert any(f"filesystem write call: {method}()" in v for v in violations), violations
