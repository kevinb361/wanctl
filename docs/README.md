# Documentation Index

This directory keeps current operator and developer references at the top level.
Historical investigations, closed incidents, old deployment paths, and one-off
validation reports live in [`docs/archive/`](archive/).

## Start Here

- [`GETTING-STARTED.md`](GETTING-STARTED.md): first installation and smoke-test path.
- [`CONFIGURATION.md`](CONFIGURATION.md): practical YAML guidance and tuning model.
- [`CONFIG_SCHEMA.md`](CONFIG_SCHEMA.md): exhaustive config key reference.
- [`DEPLOYMENT.md`](DEPLOYMENT.md): active service-based install/deploy flow.
- [`RUNBOOK.md`](RUNBOOK.md): post-deploy checks and incident response.

## Architecture And Operations

- [`ARCHITECTURE.md`](ARCHITECTURE.md): portable controller invariants and configuration-driven design.
- [`SUBSYSTEMS.md`](SUBSYSTEMS.md): storage, dashboard, transports, health, alerting, measurement quality, and bridge QoS internals.
- [`STEERING.md`](STEERING.md): optional dual-WAN steering behavior and operations.
- [`PERFORMANCE.md`](PERFORMANCE.md): 50ms production interval, profiling, and historical interval-test pointers.
- [`SECURITY.md`](SECURITY.md): SSH host-key validation and credential handling notes.

## Specialized References

- [`CALIBRATION.md`](CALIBRATION.md): shaped-rate discovery workflow.
- [`CABLE_TUNING.md`](CABLE_TUNING.md): DOCSIS tuning rationale and validation data.
- [`SILICOM-BYPASS.md`](SILICOM-BYPASS.md): Silicom bypass NIC LED meanings and recovery notes.
- [`TESTING.md`](TESTING.md): local test, lint, type-check, and integration-test commands.
- [`UPGRADING.md`](UPGRADING.md): upgrade and rollback notes.

## Archive Policy

The tracked archive is intentionally retained. It contains historical evidence
that can be useful for forensics, but those files are not the source of truth for
current deployment or tuning instructions. Prefer the top-level docs above unless
an archived file is explicitly referenced as historical context.
