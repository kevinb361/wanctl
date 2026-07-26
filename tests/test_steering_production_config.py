from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_public_steering_example_names_an_explicit_mangle_rule() -> None:
    config = yaml.safe_load((ROOT / "configs/examples/steering.yaml.example").read_text())

    assert config["mangle_rule"]["comment"] == "ADAPTIVE: Steer latency-sensitive to WAN2"


def test_legacy_broad_rule_installer_fails_closed() -> None:
    script = (ROOT / "scripts/add_steering_rules.sh").read_text()

    assert "is retired" in script
    assert "exit 2" in script
    assert "action=mark-routing" not in script
