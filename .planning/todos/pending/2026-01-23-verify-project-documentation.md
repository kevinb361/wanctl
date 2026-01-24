---
created: 2026-01-23T21:13
title: Verify project documentation is correct and up to date
area: docs
files:
  - CLAUDE.md
  - README.md
  - CHANGELOG.md
  - docs/*
---

## Problem

Documentation may have drifted from actual implementation over 4 milestones of rapid development (v1.0-v1.3). Need systematic review to ensure:

- Version numbers are current
- Feature descriptions match implementation
- Code examples/commands work
- Architecture docs reflect actual structure
- Configuration docs match current schema
- Dead/outdated sections removed

## Solution

Systematic sweep:

1. Inventory all docs (`docs/`, `CLAUDE.md`, `README.md`, `CHANGELOG.md`)
2. Cross-reference version numbers and feature claims against code
3. Validate commands/examples actually work
4. Check for mentions of removed/renamed features (e.g., "Phase2B" renamed to "confidence-based steering")
5. Update or flag discrepancies
