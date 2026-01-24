---
created: 2026-01-23T21:18
title: Integration test for router communication
area: testing
files:
  - src/wanctl/router_client.py
  - src/wanctl/backends/routeros.py
  - tests/
---

## Problem

Unit tests mock RouterOS responses. Real integration issues may go undetected:

- SSH connection handling edge cases
- REST API timeout behavior
- Response parsing with actual router output
- Authentication failure handling

## Solution

Options (TBD based on test environment availability):

1. **Mock router container** - RouterOS CHR in Docker for CI
2. **Recorded responses** - VCR-style replay of real router sessions
3. **Manual integration test** - Script for running against real router (not CI)
4. **Contract tests** - Verify mock matches real router response format
