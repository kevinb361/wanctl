---
created: "2026-03-12T16:49:28.188Z"
title: Audit CAKE qdisc configuration for Spectrum and ATT links
area: networking
files: []
---

## Problem

The CAKE qdisc configuration was set up before wanctl was built and hasn't been formally audited. While it appears to work correctly, the settings may not be optimal for the specific link types:

- **Spectrum (cable/DOCSIS):** Needs `docsis` link-layer compensation keyword. Cable modems have specific per-packet overhead from DOCSIS framing that CAKE can account for. Also needs correct `overhead` value and potentially `mpu` setting.
- **ATT (VDSL2):** Needs `pppoe-ptm` or appropriate ATM/PTM link-layer keyword depending on whether the connection uses PPPoE. VDSL2 typically uses PTM framing with specific overhead bytes. The `overhead` and `atm`/`noatm` settings are critical for accurate bandwidth shaping.

Incorrect link-layer settings mean CAKE miscalculates actual packet sizes on the wire, leading to either under-utilization (shaped too aggressively) or residual bufferbloat (not shaped enough).

## Solution

1. SSH into both containers and dump current CAKE parameters (`tc -s qdisc show`)
2. Research correct CAKE keywords for Spectrum DOCSIS and ATT VDSL2
3. Run bufferbloat tests (Waveform/flent) with current settings as baseline
4. Adjust link-layer compensation keywords and overhead values
5. Re-run bufferbloat tests to compare
6. Document final validated settings
