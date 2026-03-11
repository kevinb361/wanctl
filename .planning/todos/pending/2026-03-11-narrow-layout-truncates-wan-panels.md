# Narrow layout truncates WAN panel content

**Category:** dashboard/ui
**Priority:** low
**Source:** v1.14 milestone completion review

## Description

In narrow/stacked layout (<120 cols), WAN panels get height-squeezed and UL rate, RTT, and Router OK lines are not visible. The data is present (health endpoint returns all fields) — the widget just doesn't have enough vertical space in stacked mode.

## Possible Approaches

- Enforce min-height on WanPanelWidget in narrow mode
- Add scroll container around wan-col in narrow layout
- Compact rendering mode that uses fewer lines (e.g., single-line rate display)

## Notes

Wide layout (>=120 cols) displays all content correctly. This is cosmetic — no data loss, just visibility.
