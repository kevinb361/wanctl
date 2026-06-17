import json
import stat
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "phase243-hygiene-sampler.sh"


def load_rows(path: Path) -> list[dict[str, int]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def cpu_nsec_is_monotonic(rows: list[dict[str, int]]) -> bool:
    values = [row["cpu_nsec"] for row in rows]
    return all(current >= previous for previous, current in zip(values, values[1:], strict=False))


def fd_is_strictly_increasing(rows: list[dict[str, int]]) -> bool:
    values = [row["fd"] for row in rows]
    return all(current > previous for previous, current in zip(values, values[1:], strict=False))


def test_sampler_is_executable() -> None:
    assert SCRIPT.exists()
    assert SCRIPT.stat().st_mode & stat.S_IXUSR


def test_sampler_contains_required_read_only_sampling_contracts() -> None:
    source = SCRIPT.read_text(encoding="utf-8")

    assert "set -euo pipefail" in source
    assert "MainPID" in source
    assert "/proc/" in source
    assert "TasksCurrent" in source
    assert "CPUUsageNSec" in source
    assert "CPUAccounting" in source
    assert 'state" = "Z"' in source
    assert "exit 2" in source
    assert "tc " not in source
    assert "qdisc" not in source
    assert "RouterOS" not in source


def test_hygiene_ndjson_shape_and_cpu_delta(tmp_path: Path) -> None:
    fixture = tmp_path / "hygiene.ndjson"
    fixture.write_text(
        "\n".join(
            [
                json.dumps({"t": 1000, "fd": 12, "tasks": 4, "zombies": 0, "cpu_nsec": 100}),
                json.dumps({"t": 1001, "fd": 12, "tasks": 4, "zombies": 0, "cpu_nsec": 250}),
                json.dumps({"t": 1002, "fd": 13, "tasks": 5, "zombies": 0, "cpu_nsec": 400}),
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    rows = load_rows(fixture)

    assert set(rows[0]) == {"t", "fd", "tasks", "zombies", "cpu_nsec"}
    assert all(isinstance(row["cpu_nsec"], int) for row in rows)
    assert cpu_nsec_is_monotonic(rows)
    assert rows[-1]["cpu_nsec"] - rows[0]["cpu_nsec"] == 300
    assert max(row["zombies"] for row in rows) == 0


def test_fixture_checks_detect_bad_trends() -> None:
    increasing_fd = [
        {"t": 1, "fd": 10, "tasks": 3, "zombies": 0, "cpu_nsec": 100},
        {"t": 2, "fd": 11, "tasks": 3, "zombies": 0, "cpu_nsec": 200},
        {"t": 3, "fd": 12, "tasks": 3, "zombies": 0, "cpu_nsec": 300},
    ]
    zombie_rows = [{"t": 1, "fd": 10, "tasks": 3, "zombies": 1, "cpu_nsec": 100}]
    decreasing_cpu = [
        {"t": 1, "fd": 10, "tasks": 3, "zombies": 0, "cpu_nsec": 200},
        {"t": 2, "fd": 10, "tasks": 3, "zombies": 0, "cpu_nsec": 100},
    ]

    assert fd_is_strictly_increasing(increasing_fd)
    assert max(row["zombies"] for row in zombie_rows) > 0
    assert not cpu_nsec_is_monotonic(decreasing_cpu)
