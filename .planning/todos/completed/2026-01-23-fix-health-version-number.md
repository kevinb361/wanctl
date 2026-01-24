---
created: 2026-01-23T12:03
title: Fix health endpoint version number
area: observability
files:
  - src/wanctl/__init__.py
  - src/wanctl/health_check.py
---

## Problem

Health endpoint at port 9101 shows version "1.1.0" but project is at v1.3. The `__version__` variable in `__init__.py` needs to be updated.

## Solution

Update `__version__` in `src/wanctl/__init__.py` to "1.3.0" to match the current milestone.
