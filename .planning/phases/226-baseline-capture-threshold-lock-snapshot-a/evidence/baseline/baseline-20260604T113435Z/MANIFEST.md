# Baseline Manifest

## Captured UTC

- Captured: 2026-06-04T11:34:35Z

## Source Posture

read-only target access; no deploy, restart, mode change, /etc write, nft mutation, or tc mutation. Load generation was client-side RRUL/reference traffic only.

## Baseline State

- 920/18 besteffort wash; mode=besteffort; wash_gate=true; dl=920; ul=18; docsis_mode=true

## Run Plan

- runs: 3
- duration_seconds: 60
- local_bind: 10.10.110.226
- health_url: http://10.10.110.223:9101/health
- router_iface: spec-router
- modem_iface: spec-modem
- ref_host: vultr-chicago
- ref_port: 5201
- ref_udp_rate: 1M
- window_used: forced:operator approved forced run now at checkpoint

## Validity

- validity: valid
- retained: true
- discarded_runs: ["discarded-baseline-20260604T112413Z-netperf-errors", "discarded-baseline-20260604T112930Z-netperf-reset"]
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
- run-01/ref-dscp-proof.01.txt
- run-01/ref-tcp-bulk-unmarked.01.txt
- run-01/ref-udp-unmarked.01.txt
- run-01/rrul-2026-06-04T063436.426718.flent.gz
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
- run-02/ref-dscp-proof.02.txt
- run-02/ref-tcp-bulk-unmarked.02.txt
- run-02/ref-udp-unmarked.02.txt
- run-02/rrul-2026-06-04T063548.720507.flent.gz
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
- run-03/ref-dscp-proof.03.txt
- run-03/ref-tcp-bulk-unmarked.03.txt
- run-03/ref-udp-unmarked.03.txt
- run-03/rrul-2026-06-04T063701.058966.flent.gz
- run-03/tc-qdisc-spec-modem.after.txt
- run-03/tc-qdisc-spec-modem.before.txt
- run-03/tc-qdisc-spec-modem.during.txt
- run-03/tc-qdisc-spec-router.after.txt
- run-03/tc-qdisc-spec-router.before.txt
- run-03/tc-qdisc-spec-router.during.txt
