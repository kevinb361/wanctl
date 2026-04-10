# Phase 37: CLI Tool Tests - Context

**Gathered:** 2026-01-25
**Status:** Ready for planning

<domain>
## Phase Boundary

Write tests for CLI tools — specifically the calibrate and profiler utilities. Goal is achieving 90%+ coverage for these modules to complete the v1.6 milestone. Does not include new CLI functionality or tool enhancements.

</domain>

<decisions>
## Implementation Decisions

### Invocation patterns
- Test via direct function calls (call main() or parse_args() directly)
- Verify entry point wiring (__main__.py or if __name__ == '__main__' blocks)
- Pass args directly to parse functions using argparse's parse_args(['--flag', 'value'])
- Use shared fixtures for common setup (config, mock router, tmp dirs)

### Output assertions
- Assert key values only (specific rates, RTT values present), ignore formatting details
- Do not require exact output string matching

### Coverage scope
- All flags/options must have at least one test exercising them
- Target 90%+ coverage (milestone standard)

### Error scenarios
- Test all three categories: invalid arguments, missing dependencies, runtime failures
- Use mocks for router/network communication (fast, deterministic, no real network)

### Claude's Discretion
- Exit code testing strategy (when to verify, when to skip)
- Profiler output assertions (timing breakdown vs completion message)
- Calibrate rate calculation verification (full math check vs smoke test)
- Flag combination tests (which combos are worth testing)
- Help output testing (based on custom help logic presence)
- Error message content assertions (user-friendly text vs exit code only)
- KeyboardInterrupt handling tests (based on existing signal infrastructure)

</decisions>

<specifics>
## Specific Ideas

- Pattern established in Phase 35-06: test entry point via source inspection rather than runpy.run_module
- Follow existing fixture patterns (controller_with_mocks, valid_config_dict, tmp_path for file I/O)
- Use pytest.raises(SystemExit) for argparse errors (established in Phase 36-02)

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 37-cli-tool-tests*
*Context gathered: 2026-01-25*
