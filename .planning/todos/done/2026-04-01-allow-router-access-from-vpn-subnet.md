---
created: 2026-04-01T15:30:00.000Z
title: Allow router access from VPN subnet
area: network
files:
  - router/configs/router_config.rsc
---

## Problem

Cannot connect to MikroTik router (10.10.99.1) via Winbox or SSH when connected over VPN.
The VPN (WireGuard) terminates on the router but the router's management services (Winbox, SSH,
REST API) likely have IP service restrictions or firewall rules that only allow access from
local subnets, not the VPN/WireGuard subnet.

Discovered 2026-04-01 while away from home — could VPN into the network via ATT but couldn't
reach the router to diagnose the Spectrum outage failover issue.

## Solution

On MikroTik router, add the WireGuard subnet to allowed addresses for management services:

- `/ip service` — check `address` restrictions on winbox, ssh, api-ssl (www-ssl for REST)
- `/ip firewall filter` — check input chain rules that may block WireGuard subnet
- Test: VPN in, confirm Winbox + SSH + REST API all reachable on 10.10.99.1

Must be done while physically at home (if misconfigured, could lock out management access).
