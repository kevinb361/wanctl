# Phase 62: Deployment Alignment - Context

**Gathered:** 2026-03-10
**Status:** Ready for planning

<domain>
## Phase Boundary

Deployment artifacts accurately reflect the codebase's actual runtime dependencies and version. No source code changes. Touches: Dockerfile, deploy scripts, install.sh, pyproject.toml version.

Requirements: DPLY-01, DPLY-02, DPLY-03, DPLY-04

</domain>

<decisions>
## Implementation Decisions

### deploy_refactored.sh disposition
- Move `scripts/deploy_refactored.sh` to `scripts/.obsolete/` — it is thoroughly obsolete (references `adaptive_cake.py`, non-FHS paths, hardcoded IPs, sshpass)
- DPLY-02 satisfied by `deploy.sh` + `install.sh` instead — install.sh gains a `pip3 install` step for runtime dependencies
- Same pattern as the old deploy.sh already in `scripts/.obsolete/`

### install.sh dependency installation
- install.sh gains a `pip3 install --break-system-packages` step that installs all runtime deps from a list matching pyproject.toml
- Codifies the manual pattern already used in production (noted in MEMORY.md)
- Dependency list: requests, pyyaml, paramiko, pexpect, tabulate, icmplib, cryptography (pexpect will be removed in Phase 63)

### Dockerfile dependency pinning
- Use `>=` ranges matching pyproject.toml (e.g., `requests>=2.31.0`), not exact pins
- pyproject.toml is the single source of truth for dependency versions
- When Phase 63 removes pexpect, the Dockerfile update mirrors pyproject.toml

### Dockerfile version label
- Manual bump from `"1.0"` to `"1.12.0"` — no build-arg automation
- Dockerfile hasn't been built yet; automation is over-engineering at this stage

### Claude's Discretion
- install.sh pip3 install implementation details (error handling, idempotency)
- Dockerfile `>=` range formatting and ordering
- Whether to add a comment in Dockerfile referencing pyproject.toml as source of truth

</decisions>

<specifics>
## Specific Ideas

- Production containers use system Python (`/usr/bin/python3`), no venv — deps installed with `sudo pip3 install --break-system-packages`
- deploy.sh uses rsync for code deployment and delegates initial setup to install.sh via `run_remote_install`
- Current deploy.sh has no pip dependency installation step — install.sh is the right place for it

</specifics>

<code_context>
## Existing Code Insights

### Reusable Assets
- `scripts/.obsolete/` directory already exists with precedent for archiving superseded scripts
- `deploy.sh` line 129-138: `run_remote_install()` copies and runs install.sh on target — this is the dependency installation hook point
- `install.sh` has environment detection (docker, lxc, systemd, minimal) that may affect pip3 invocation

### Established Patterns
- FHS paths: `/opt/wanctl`, `/etc/wanctl`, `/var/lib/wanctl`, `/var/log/wanctl`
- deploy.sh uses rsync with `--delete` for code sync — no file lists to maintain
- pyproject.toml dependencies section (lines 7-15) is the canonical dependency list

### Integration Points
- `pyproject.toml` version field → install.sh VERSION variable → Dockerfile LABEL version (all must read "1.12.0")
- install.sh pip3 install list must match pyproject.toml `[project.dependencies]`
- Dockerfile pip install line must match pyproject.toml `[project.dependencies]`
- Phase 63 will remove pexpect from pyproject.toml — all three artifacts will need the same removal

</code_context>

<deferred>
## Deferred Ideas

- Dockerfile `pip install .` from pyproject.toml directly (eliminates drift but changes deployment model) — revisit when Docker becomes an active workflow
- Build-arg automation for Dockerfile version label — revisit if Docker builds become routine
- deploy.sh adding its own pip install step (beyond install.sh) — not needed since install.sh handles it

</deferred>

---

*Phase: 62-deployment-alignment*
*Context gathered: 2026-03-10*
