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


def _rule_lines(chain_body: str) -> list[str]:
    return [
        line.strip()
        for line in chain_body.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


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


def test_router_dscp_classification_is_propagated_to_download_replies() -> None:
    ruleset = BRIDGE_QOS.read_text()

    expected_import = [
        "ether type ip ip dscp ef ct mark set 0x00000004 accept",
        "ether type ip ip dscp af31 ct mark set 0x00000002 accept",
        "ether type ip ip dscp cs1 ct mark set 0x00000001 accept",
    ]
    expected_paths = {
        "spectrum_ul": 'iif spec-router oif spec-modem jump spectrum_ul',
        "att_ul": 'iif att-router oif att-modem jump att_ul',
    }
    for chain_name, dispatch in expected_paths.items():
        body = _chain_body(ruleset, chain_name)
        assert _rule_lines(body) == expected_import
        assert dispatch in ruleset


def test_download_restore_contract_is_symmetric_with_best_effort_fallback() -> None:
    ruleset = BRIDGE_QOS.read_text()

    expected_prefix = [
        "ether type ip ip dscp set cs0",
        "ether type ip ct mark 0x00000004 ip dscp set ef accept",
        "ether type ip ct mark 0x00000002 ip dscp set af41 accept",
        "ether type ip ct mark 0x00000001 ip dscp set cs1 accept",
    ]
    for chain_name in ("spectrum_dl", "att_dl"):
        rules = _rule_lines(_chain_body(ruleset, chain_name))
        assert rules[:4] == expected_prefix

        # Every post-restore class change is a narrow fallback for an
        # unclassified connection. With no match, the initial CS0 wash remains
        # in force and CAKE receives Best Effort.
        for rule in rules[4:]:
            if "ip dscp set" in rule:
                assert "ct mark 0x00000000" in rule
                assert any(token in rule for token in ("sport", "dport", "ct bytes"))


def test_generic_large_downloads_go_directly_to_bulk() -> None:
    ruleset = BRIDGE_QOS.read_text()

    for chain_name in ("spectrum_dl", "att_dl"):
        body = _chain_body(ruleset, chain_name)
        assert (
            "ct bytes > 10000000 ct mark 0x00000000 "
            "ip dscp set cs1 ct mark set 0x00000001 accept"
        ) in body
        assert "ct bytes > 10000000 ct mark 0 ip dscp set af41" not in body
        assert "ct bytes > 100000000" not in body
