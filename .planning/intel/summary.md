# Codebase Intelligence Summary

Last updated: 2026-01-21T14:30:00Z
Indexed files: 72

## Naming Conventions

- Export naming: snake_case (85% of 1206 exports)
- Classes: PascalCase (standard Python)

## Key Directories

- `src/wanctl/`: Core autorate controller and utilities (35 files)
- `src/wanctl/backends/`: Router transport backends - SSH, REST (3 files)
- `src/wanctl/steering/`: WAN steering and congestion assessment (5 files)
- `tests/`: Unit and integration tests (35 files)
- `tests/integration/framework/`: Test harness for latency validation (6 files)

## File Patterns

- `test_*.py`: Test files (25 files)
- `*_utils.py`: Utility modules (18 files)
- `*_state.py`: State management (4 files)

## Architecture

- Entry point: `autorate_continuous.py` (daemon main loop)
- Config: `config_base.py` (YAML parsing, validation)
- Router: `router_client.py` factory -> `routeros_ssh.py` | `routeros_rest.py`
- Health: `health_check.py` (HTTP endpoint on :9101)

Total exports: 1298
