from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
BRIDGE_QOS = REPO_ROOT / "deploy" / "nftables" / "bridge-qos.nft"


def _chain_body(ruleset: str, chain_name: str) -> str:
    match = re.search(
        rf"chain {chain_name} \{{(?P<body>.*?)^    \}}", ruleset, re.MULTILINE | re.DOTALL
    )
    assert match is not None, f"missing {chain_name} chain"
    return match.group("body")


def test_download_chains_wash_wan_dscp_before_classification() -> None:
    ruleset = BRIDGE_QOS.read_text()

    for chain_name in ("spectrum_dl", "att_dl"):
        body = _chain_body(ruleset, chain_name)
        assert "ip dscp != 0 accept" not in body
        assert "ip dscp != cs0 accept" not in body

        wash = body.index("ip dscp set cs0")
        restore = body.index("ct mark 0x00000004 ip dscp set ef accept")
        classify = body.index("ct mark 0x00000000 udp sport 53")

        assert wash < restore < classify


def test_reply_classification_uses_unmarked_conntrack_not_new_state() -> None:
    ruleset = BRIDGE_QOS.read_text()

    assert "ct state new" not in ruleset

    expected_rules = [
        "ct mark 0x00000000 udp sport 53 ip dscp set ef ct mark set 0x00000004 accept",
        "ct mark 0x00000000 tcp sport 53 ip dscp set ef ct mark set 0x00000004 accept",
        "ct mark 0x00000000 udp sport 443 ip dscp set af41 ct mark set 0x00000002 accept",
        "ct mark 0x00000000 tcp sport 6881-6889 ip dscp set cs1 ct mark set 0x00000001 accept",
    ]
    for expected in expected_rules:
        assert expected in ruleset
