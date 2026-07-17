# QoS Specification

## Purpose
Define the observable class handoff and queue treatment across the split RouterOS and cake-shaper edge.

## Scope
- In scope: trusted RouterOS DSCP import, carrier wash, reply restoration, CAKE tin selection, and safe fallback.
- Not in scope: NAT/routing ownership, CAKE rate tuning, or per-LAN-host fairness across a separate NAT host.

## Requirements

### REQ: wash-untrusted-download-dscp
The system SHALL clear modem-facing IPv4 DSCP before applying locally trusted connection classification.

#### Scenario: carrier-marked-download
- GIVEN a download packet enters from a modem-facing interface with nonzero DSCP
- WHEN bridge QoS processes the packet
- THEN carrier DSCP is cleared before local restoration or fallback classification

### REQ: restore-known-reply-class
The system SHALL restore a known bridge connection class before CAKE schedules a download reply.

#### Scenario: classified-reply
- GIVEN bridge conntrack contains Voice, Video, or Bulk intent
- WHEN a reply crosses either WAN download path
- THEN the packet enters the corresponding CAKE diffserv4 tin

### REQ: best-effort-fallback
The system SHALL leave traffic without trusted or fallback classification in Best Effort.

#### Scenario: unclassified-flow
- GIVEN no trusted class was imported and no explicit fallback matches
- WHEN the packet reaches CAKE
- THEN it is scheduled as Best Effort

## Delta: v1.61-req-002-af31-import — 2026-07-17

Source: `/saga-next` v1.61 REQ-002 and REQ-003 repo slices. Status: repo-verified by exact symmetric import/restore and Best Effort fallback tests; pending live deployment.

### ADDED to qos

### REQ: import-router-video-class
The system SHALL import RouterOS AF31 from either router-facing WAN interface into the bridge Video connection class.

#### Scenario: af31-request-and-reply
- GIVEN RouterOS emits AF31 on an outbound flow
- WHEN that flow crosses either WAN upload path and later receives a reply
- THEN bridge conntrack records Video intent
- AND download CAKE schedules the restored reply in the Video tin
