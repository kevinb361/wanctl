# DSCP Ingress Capture Manifest

## Captured

- Captured: 2026-06-04T04:59:06Z
- SSH host: cake-shaper
- Duration: 90 seconds
- Packet cap: 250000 packets per capture
- Probe mode: none
- Probe target: not_requested
- Probe proto/port: udp/5201
- DL source proof: unsupported (no --dl-source-ssh-host/--dl-source-iface; DL channel degrades, never STRIPPED)

## Source Posture

Read-only: bounded tcpdump over SSH plus optional bounded low-rate EF probe. No external gear configuration, queue mode, ruleset, or persistent classifier state was changed.

## Capture Point

See capture-point-proof.txt. CAPTURE_POINT defaults to unknown unless WASH_PROOF_PASS is true.

## Artifacts

- capture-point-proof.txt
- sample-quality.txt
- dscp-histogram-spec-router-dl.txt
- dscp-histogram-spec-modem-ul.txt
- dl-ef-probe-result.txt
- ul-ef-probe-result.txt
- raw/organic-dl-spec-router.pcap
- raw/organic-ul-spec-modem.pcap
- raw/dl-ef-probe.pcap
- raw/dl-ef-probe-source.pcap: NOT PRODUCED (DL source proof unsupported; no empty pcap written)
- raw/ul-ef-probe.pcap
- topology/ip-d-link-show.txt
- topology/bridge-link-show.txt
- topology/nft-bridge-qos.txt
- topology/tc-qdisc-spec-router.txt
- topology/tc-qdisc-spec-modem.txt

## SHA256

115d30ae0eea52b75645a05e02f01c16ebb5a88c6f4f329cf08db4b5d120a4cc  capture-point-proof.txt
af8e13f3c2e7751102871ee410a605171e5ddd3096b3229c75470e2e2dee186f  dl-ef-probe-result.txt
5eef3809b939340b4b7b681456a31d4ce6f2424a8cf1e689e0a0148b03bf514a  dscp-histogram-spec-modem-ul.txt
9a9eaae5a71dc105bfcfa37f6b360b9305e527583c0e8990d9c349b3df9ae8b5  dscp-histogram-spec-router-dl.txt
0bbe207252c339342144bae33bdaec3d91ad6b2e08943bc24f097cb84e4a5d74  dscp_pcap_analyzer.py
e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855  raw/dl-ef-probe.pcap
d761b5e3fc705a854b3208093cbaee58716fa6ffdada1804c86a945089863923  raw/organic-dl-spec-router.pcap
67c8f1e87d00e685d40f7ee5b9b4eecc4779adaff455be1043815c801e0efd5e  raw/organic-ul-spec-modem.pcap
e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855  raw/ul-ef-probe.pcap
bb2b796967e3af8ee721ed4b7b6dfb72613e9af1c370c325321d9af75363036e  sample-quality.txt
e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855  topology/bridge-link-show.txt
a0dfec12bbc6e69bd8dae6fa49e8778c9561922885b1c4ffaa8a0ec60655a759  topology/ip-d-link-show.txt
e41927a92247676969ddc838c8000e67019141aebdfa0baa46ab0c8a6432422e  topology/nft-bridge-qos.txt
990b4a1b4a3895d7b8c90cf7ec956f6d99f7c242c75e016946ee2e9412195f64  topology/tc-qdisc-spec-modem.txt
cbf42ecb44b83ac91b61f275d3d12c38db1c8dee894e0ec077f90c4887eb1b1d  topology/tc-qdisc-spec-router.txt
71b54c7915a329a3d53095821b46b8e21951ceea63a1b36dd9fdaf31d7e87cbe  ul-ef-probe-result.txt
