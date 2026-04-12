#!/usr/bin/env python3
"""Wrapper for wanctl-analyze-baseline.

Works from both a repo checkout (src/ layout) and production (/opt/wanctl/).
"""
import sys
from pathlib import Path

_script_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(_script_dir.parent / "src"))  # dev layout
sys.path.insert(0, str(_script_dir.parent.parent))    # prod layout (/opt)

from wanctl.analyze_baseline import main

if __name__ == "__main__":
    main()
