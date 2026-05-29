import gzip
import importlib.util
import json
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
EXTRACTOR = REPO_ROOT / "scripts/phase214-extract.py"


def _load_extractor():
    spec = importlib.util.spec_from_file_location("phase214_extract", EXTRACTOR)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _write_flent(tmp_path: Path, results: dict[str, list[float]]) -> Path:
    flent_gz = tmp_path / "sample.flent.gz"
    payload = {
        "metadata": {
            "T0": "2026-05-29T00:00:00+00:00",
            "TOTAL_LENGTH": 10,
        },
        "raw_values": {"Ping (ms) ICMP": [{"val": 10.0}, {"val": 12.0}]},
        "results": results,
    }
    with gzip.open(flent_gz, "wt") as fh:
        json.dump(payload, fh)
    return flent_gz


def test_extract_upload_throughput_reads_tcp_upload_series(tmp_path: Path) -> None:
    extractor = _load_extractor()
    flent_gz = _write_flent(tmp_path, {"TCP upload": [1.0, 7.0, 3.0, 5.0, 9.0]})

    result = extractor.extract_flent_upload_throughput(flent_gz)

    assert result == {
        "throughput_median_mbps": 5.0,
        "throughput_p95_mbps": 9.0,
        "throughput_max_mbps": 9.0,
        "sample_count": 5,
        "series_key_used": "TCP upload",
    }


def test_extract_upload_throughput_fails_closed_on_download_only(tmp_path: Path) -> None:
    extractor = _load_extractor()
    flent_gz = _write_flent(tmp_path, {"TCP download sum": [10.0, 11.0, 12.0]})

    with pytest.raises(extractor.FlentExtractionError, match="no usable TCP upload series found"):
        extractor.extract_flent_upload_throughput(flent_gz)


def test_extract_upload_throughput_fails_closed_on_tcp_totals_only(tmp_path: Path) -> None:
    extractor = _load_extractor()
    flent_gz = _write_flent(tmp_path, {"TCP totals": [10.0, 11.0, 12.0]})

    with pytest.raises(extractor.FlentExtractionError, match="no usable TCP upload series found"):
        extractor.extract_flent_upload_throughput(flent_gz)
