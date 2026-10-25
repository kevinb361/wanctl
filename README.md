# wanctl (archived)

[![License: GPL v2](https://img.shields.io/badge/License-GPL_v2-blue.svg)](https://www.gnu.org/licenses/old-licenses/gpl-2.0.en.html)

**This repository is archived and read-only. It is no longer developed or deployed.**

## What it was

wanctl was an adaptive CAKE bandwidth controller. It measured RTT to a set of reflectors and changed CAKE's bandwidth
limit in real time, 20 times a second, to keep latency low under load. It started out driving CAKE queues on a
MikroTik RouterOS router over the REST API, with SSH as a fallback, and later also drove Linux CAKE qdiscs on an
inline bridge. It also had optional latency-based WAN steering, health and Prometheus endpoints, and a set of
measurement tools.

## How it ended

- **2026-01:** REST beat SSH for router writes: about 50 ms per command against 150-200 ms, and 194 ms against 404 ms
  peak RTT under a heavy upload test. REST became the RouterOS transport.
- **2026-04:** Shaping moved from the router to a Linux inline bridge, where rate changes are local `tc` calls. Cable
  tuning from many RRUL A/B runs is in `docs/CABLE_TUNING.md`. Two findings matter most: evening latency on the cable
  link was dominated by ISP-side congestion, not by CAKE settings, and no static ceiling fixed it.
- **2026-06:** The Linux shaper moved to upstream [cake-autorate](https://github.com/lynxthecat/cake-autorate). On the
  VDSL2 link it measured equal to wanctl's controller within noise (about 84 Mbit, p99 about 60 ms). On the cable link
  it was judged materially better. wanctl was kept only as a state bridge and metrics layer.
- **2026-10:** No live system used wanctl's controller any more, and the planned v1.67 release was cancelled. The
  planning record's baseline for the seven days ending 2026-10-25, over all samples, is p50 0.2 ms, p95 9.1 ms and
  p99 20 ms, with 91 % of samples at or under 5 ms and a worst evening hour p95 of 28-35 ms. Those figures are
  cake-autorate's added latency (RTT rise over its baseline, `cake_rtt_delta_ms`), not absolute RTT.

## Where things went

- The pieces still in use are in **cake-autorate-tools** (`<cake-autorate-tools-url>`): the cake-autorate state
  bridge, the metrics exporter, the Silicom bypass watchdog and the RRUL and capacity measurement tools.
- What was learned about CAKE on RouterOS is written up in that repository's `docs/cake-on-mikrotik.md`.

## Reading this code

The last commit is the reference point for the controller, the RouterOS REST/SSH transports and the tuning history
(`docs/CABLE_TUNING.md`, `docs/CALIBRATION.md`, `docs/ARCHITECTURE.md`, `CHANGELOG.md`). Nothing here is maintained.
Configs, thresholds and deployment scripts describe one past setup and are not recommendations.

## License

GPL-2.0. See [LICENSE](LICENSE).
