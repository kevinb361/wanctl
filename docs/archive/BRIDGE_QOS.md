# Bridge QoS

`wanctl` can classify **download** traffic into CAKE `diffserv4` tins before the
packet reaches the Linux CAKE egress qdisc.

This is done with the nftables bridge rules in
[deploy/nftables/bridge-qos.nft](/home/kevin/projects/wanctl/deploy/nftables/bridge-qos.nft),
loaded by `wanctl-bridge-qos.service`.

## Why This Exists

Inbound ISP traffic often arrives as `CS0`, so pure endpoint DSCP trust is not
enough to create useful CAKE tin separation on download.

The bridge classifier fixes that by:

- trusting existing non-zero DSCP when endpoints already mark traffic
- restoring DSCP from conntrack marks for established flows
- classifying selected latency-sensitive reply traffic into `EF`
- classifying selected media / QUIC reply traffic into `AF41`
- demoting large unclassified transfers to `AF41` after `10 MB`
- demoting very large unclassified transfers to `CS1` after `100 MB`

## Current Production Baseline

Observed on Spectrum during a controlled RRUL on `2026-04-14`:

- download `Video` tin carried the backlog and drops
- download `Bulk` tin stayed at zero backlog/drops during the same window
- upload still showed the expected stronger non-BE tin usage

That means download tin classification is **active and materially used** in the
current bridge-QoS deployment. The older assumption that inbound traffic is
effectively all `Bulk` is no longer accurate for this production path.

## Operational Check

Useful checks on a live host:

```bash
sudo nft list table bridge qos
curl -s http://10.10.110.223:9101/health | python3 -m json.tool
PYTHONPATH=/opt python3 -m wanctl.history --db /var/lib/wanctl/metrics-spectrum.db --last 1h --tins --json
```

During load, inspect `wans[0].cake_signal.download.tins` in `/health`.
If download classification is working, `Video` and/or `Voice` should show
backlog or drop activity instead of all pressure accumulating in `Bulk`.
