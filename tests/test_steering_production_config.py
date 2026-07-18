from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]


def test_production_steering_toggles_explicit_work_vpn_eligibility() -> None:
    config = yaml.safe_load((ROOT / "configs/steering.yaml").read_text())

    assert config["mangle_rule"]["comment"] == "ADAPTIVE: Work VPN eligible for ATT"


def test_legacy_broad_rule_installer_fails_closed() -> None:
    script = (ROOT / "scripts/add_steering_rules.sh").read_text()

    assert "is retired" in script
    assert "exit 2" in script
    assert "action=mark-routing" not in script
