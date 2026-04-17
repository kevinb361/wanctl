# Phase 181 Reader Parity Decision

**Date:** 2026-04-14  
**Requirement:** `STOR-06`

## Live Drift Captured In Phase 179

Phase 179 showed a real mismatch between the two supported history-reader surfaces:

- the module-based CLI path (`python3 -m wanctl.history`) could prove merged cross-WAN history
- the deployed `/metrics/history` HTTP endpoint preserved its `{data, metadata}` envelope but did not prove merged cross-WAN history on production

That mismatch was not safe to leave implicit.

## Decision

Phase 181 narrows the HTTP role explicitly instead of pretending it is the same proof surface as the CLI.

### Final operator truth

- `wanctl.history` is the authoritative merged cross-WAN reader
- `/metrics/history` is the endpoint-local reader for the daemon serving that IP

## Repo Changes

The HTTP endpoint now resolves history DB paths this way:

- when running under a live controller, read only the configured local `storage.db_path`
- when running without a controller (tests or standalone ad hoc usage), keep the old discovery fallback

The response contract is preserved:

- top-level `{data, metadata}`
- newest-first ordering
- existing pagination fields

Additive metadata now makes the source explicit:

- `metadata.source.mode`
- `metadata.source.db_paths`

## Why This Is Lower Risk

- It matches the per-service deployment model already used in production.
- It avoids inventing cross-WAN HTTP semantics that the live deployment did not actually provide.
- It preserves the existing response envelope instead of redesigning the endpoint.

## Operator Guidance

Use:

```bash
ssh <host> 'sudo -n env PYTHONPATH=/opt python3 -m wanctl.history --last 1h --metrics wanctl_rtt_ms --json'
```

for authoritative merged cross-WAN reads.

Use:

```bash
ssh <host> 'curl -s "http://<health-ip>:9101/metrics/history?range=1h&limit=5"'
```

for endpoint-local history validation, envelope checks, and local WAN inspection.
