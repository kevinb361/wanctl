# Baseline Manifest

## Captured UTC

- Captured: 2026-06-04T16:31:52Z

## Source Posture

read-only target access; no deploy, restart, mode change, /etc write, nft mutation, or tc mutation. Load generation was client-side RRUL/reference traffic only.

## Baseline State

- 920/18 besteffort wash; mode=diffserv4; wash_gate=true; dl=920; ul=18; docsis_mode=true

## Run Plan

- runs: 3
- duration_seconds: 60
- local_bind: 10.10.110.226
- health_url: http://10.10.110.223:9101/health
- router_iface: spec-router
- modem_iface: spec-modem
- ref_host: vultr-chicago
- iperf_ref_host: dallas
- ref_port: 5201
- tcp_ref_port: 5202
- ref_udp_rate: 1M
- window_used: forced:operator approved live continuation after partial checkpoint
- marked_ef: 1
- ef_ref_port: 5203
- ef_reflector_prerequisite: iperf3 server listening on dallas:5203 when marked_ef=true
- ef_mark_method: per-run ref-ef-marking artifacts
- ef_clean_mark: per-run ref-ef-marking artifacts

## Validity

- validity: valid
- retained: true
- discarded_runs: []
- rerun_policy: rerun only on objective invalid-run failure; do not chase smaller spread after a valid retained set.

## Artifacts

- artifact-sha256.txt
- baseline-summary.json
- BASELINE-SUMMARY.md
- MANIFEST.md
- repo-spectrum.redacted.yaml
- run-01/flent-rrul.01.console.txt
- run-01/flent-rrul.01.flent.gz
- run-01/flent-rrul.01.txt
- run-01/health.after.json
- run-01/health.before.json
- run-01/health.window.ndjson
- run-01/iperf-validity.01.txt
- run-01/ref-dscp-proof.01.txt
- run-01/ref-ef-marking.01.txt
- run-01/ref-tcp-bulk-unmarked.01.txt
- run-01/ref-udp-marked-ef.01.txt
- run-01/ref-udp-unmarked.01.txt
- run-01/rrul-2026-06-04T113153.370729.flent.gz
- run-01/tc-qdisc-spec-modem.after.txt
- run-01/tc-qdisc-spec-modem.before.txt
- run-01/tc-qdisc-spec-modem.during.txt
- run-01/tc-qdisc-spec-router.after.txt
- run-01/tc-qdisc-spec-router.before.txt
- run-01/tc-qdisc-spec-router.during.txt
- run-02/flent-rrul.02.console.txt
- run-02/flent-rrul.02.flent.gz
- run-02/flent-rrul.02.txt
- run-02/health.after.json
- run-02/health.before.json
- run-02/health.window.ndjson
- run-02/iperf-validity.02.txt
- run-02/ref-dscp-proof.02.txt
- run-02/ref-ef-marking.02.txt
- run-02/ref-tcp-bulk-unmarked.02.txt
- run-02/ref-udp-marked-ef.02.txt
- run-02/ref-udp-unmarked.02.txt
- run-02/rrul-2026-06-04T113305.928135.flent.gz
- run-02/tc-qdisc-spec-modem.after.txt
- run-02/tc-qdisc-spec-modem.before.txt
- run-02/tc-qdisc-spec-modem.during.txt
- run-02/tc-qdisc-spec-router.after.txt
- run-02/tc-qdisc-spec-router.before.txt
- run-02/tc-qdisc-spec-router.during.txt
- run-03/flent-rrul.03.console.txt
- run-03/flent-rrul.03.flent.gz
- run-03/flent-rrul.03.txt
- run-03/health.after.json
- run-03/health.before.json
- run-03/health.window.ndjson
- run-03/iperf-validity.03.txt
- run-03/ref-dscp-proof.03.txt
- run-03/ref-ef-marking.03.txt
- run-03/ref-tcp-bulk-unmarked.03.txt
- run-03/ref-udp-marked-ef.03.txt
- run-03/ref-udp-unmarked.03.txt
- run-03/rrul-2026-06-04T113418.315207.flent.gz
- run-03/tc-qdisc-spec-modem.after.txt
- run-03/tc-qdisc-spec-modem.before.txt
- run-03/tc-qdisc-spec-modem.during.txt
- run-03/tc-qdisc-spec-router.after.txt
- run-03/tc-qdisc-spec-router.before.txt
- run-03/tc-qdisc-spec-router.during.txt
