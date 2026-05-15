---
created: 2026-04-08T23:35:04.832Z
title: Improve reflector path diversity for ICMP resilience
area: controller
files:
  - /etc/wanctl/spectrum.yaml
  - /etc/wanctl/att.yaml
---

## Problem

On 2026-04-08 at 18:04 CDT, all 3 ICMP reflectors (1.1.1.1, 208.67.222.222, 9.9.9.9) dropped simultaneously on both WANs for ~5 seconds. All are major anycast DNS services likely sharing peering at the same IX. This caused ATT to hit SOFT_RED/RED and Spectrum to hit YELLOW. The graceful_degradation fallback worked but the simultaneous failure exposes a common-path dependency.

## Solution

- Research reflectors routed via different AS paths / transit providers
- Consider a non-DNS target (regional CDN edge, cloud provider health endpoint)
- IRTT server on Dallas (104.200.21.31) already provides alternate measurement path for fusion
- Low urgency — system self-healed in seconds — but would harden against a known failure mode

## Investigation Notes — 2026-04-14

Live production testing from `cake-shaper`, bound to both WAN source IPs, checked current reflectors plus a small candidate set:

- current: `1.1.1.1`, `9.9.9.9`, `8.8.8.8`, `208.67.222.222`
- candidates tested: `104.200.21.31`, `151.101.1.57`, `13.107.42.14`, `23.220.75.232`

Observed behavior:

- `13.107.42.14` responded cleanly on both WANs and showed the strongest evidence of a materially different upstream path on ATT.
- `151.101.1.57` also responded cleanly on both WANs and is a plausible non-DNS CDN-backed candidate.
- `104.200.21.31` responded, but it is the existing IRTT server and had notably higher RTT on ATT (~45ms). Using it as a primary ICMP reflector would couple the ICMP path to the IRTT dependency and is not desirable.
- `23.220.75.232` responded, but RTT was materially higher on both WANs (~47-57ms), making it a poor fit for a low-latency baseline reflector.

Practical recommendation:

- Keep one existing low-latency public DNS reflector for continuity.
- Add `13.107.42.14` as the strongest non-DNS/provider-diverse candidate.
- Consider `151.101.1.57` as the second replacement candidate if we want a CDN-backed path distinct from the public resolver set.
- Do not use `104.200.21.31` as a primary ICMP reflector.
- Do not use `23.220.75.232` unless there is a specific reason to prefer its path over latency quality.

## Resolution — FIXED 2026-04-14

The reflector sets were diversified in production after a bounded-cadence admission pass and live soak validation.

What shipped:

- ATT: `1.1.1.1`, `8.8.8.8`, `151.101.1.57`
- Spectrum: `1.1.1.1`, `208.67.222.222`, `151.101.1.57`

Important implementation detail:

- Before finalizing the reflector trial, autorate background RTT probing was fixed to run on the controller cadence instead of free-running.
- That change was shipped in commit `b633734` (`Bound autorate RTT probing to control cadence`).
- Without that fix, reflector candidates were being judged under an artificially aggressive probe regime.

Trial outcome:

- `13.107.42.14` (Microsoft) initially looked good in short manual tests, but failed the live ATT soak with repeated `Ping to 13.107.42.14 failed (no response)` warnings and was rejected.
- `151.101.1.57` (Fastly) survived the bounded-cadence admission test and short live soak on both WANs without the Microsoft-style no-response pattern.

Live soak result after the final change:

- Both WANs remained `healthy`
- Both new Fastly-based sets stayed fully active and fully successful in `/health`
- No reflector deprioritization occurred during the short soak window
- No new host-specific `Ping to ... failed` warnings were observed in the final watch

Repo / deploy record:

- Final reflector-set change shipped in commit `6c7b113` (`Diversify ICMP reflector sets with Fastly`)

This closes the original common-path dependency todo. Future reflector work, if any, should be incremental tuning of the candidate pool rather than a first-pass diversity fix.
