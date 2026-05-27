# Phase 212 Evidence Command Index

Phase 212 is read-only/default-no-mutation. Evidence in this directory is captured from repo files or production host `cake-shaper` using inspection-only commands. Secret-like values are redacted with the D-08 key pattern: `password|secret|token|credential|auth|key|private`.

## Evidence Index

| Timestamp (UTC) | Source host | Command purpose | Redaction method | Output file | Mutation posture |
|---|---|---|---|---|---|
| 2026-05-27T18:42:41Z | dev repo checkout | Summarize repo expected version, service units, config paths, and non-secret health endpoints from committed files | Omit raw secret-bearing values; record only proof-relevant non-secret fields | `repo-expected-summary.json` | Read-only local file reads; no production access |

## Redaction Policy

- Redact any key whose lowercase name contains `password`, `secret`, `token`, `credential`, `auth`, `key`, or `private`.
- Do not save `/etc/wanctl/secrets` content, raw RouterOS passwords, webhook URLs, private key material, tokens, credentials, or raw secret-bearing environment dumps.
- Preserve proof-relevant non-secret operating points needed for drift interpretation: WAN name, transport, router host identity, queue names, floors, ceilings, setpoints, DOCSIS mode, health/metrics ports, steering thresholds, state paths, and cooldowns.
- `/health` artifacts are daemon-state evidence for version, state, rates, measurement quality, and active status; they are not user-experience proof.

## Production Boundary

- Production evidence must come from `ssh cake-shaper ...` or an already-local shell on that production host.
- The development VM is not production evidence.
- Do not deploy, restart services, write production config, write RouterOS state, or stage a steering degraded restart in Phase 212.
