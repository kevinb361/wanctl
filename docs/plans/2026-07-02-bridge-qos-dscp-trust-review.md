# Bridge QoS DSCP Trust Review

Date: 2026-07-02
Status: applied and verified
Scope: `cake-shaper` `/etc/wanctl/bridge-qos.nft`, repo `deploy/nftables/bridge-qos.nft`

## Question

Should cake-shaper continue to trust any non-zero DSCP on download traffic now that main-router has explicit DSCP wash-before-trust?

## Live findings

Live bridge QoS currently has this at the top of both download chains:

```nft
ip dscp != cs0 accept
```

Repo source has the equivalent:

```nft
ether type ip ip dscp != 0 accept
```

Those rules run before wanctl's conntrack/classification rules, so any non-zero DSCP arriving from the modem side bypasses local bridge classification.

Live chain shape:

```text
modem -> cake-shaper bridge QoS -> CAKE qdisc -> router-facing NIC -> main-router WAN ingress wash
```

That means main-router's wash happens after cake-shaper has already used the packet's DSCP for CAKE tin selection. Router-side wash is still needed, but it does not protect the cake-shaper download CAKE tin from remote/ISP-supplied DSCP.

Short tcpdump samples on cake-shaper saw non-zero DSCP on modem-facing interfaces:

```text
spec-modem: DSCP CS6 observed on ICMP during sample
att-modem: DSCP AF11 and EF observed during sample
```

These samples prove non-zero DSCP can arrive from the WAN side. They do not prove harm by themselves, but they invalidate the assumption that modem-side DSCP is always CS0.

CAKE qdisc state:

```text
spec-router/spec-modem: diffserv4 wash
att-router/att-modem:  diffserv4 nowash
```

CAKE `wash` clears DSCP after classification; it is not a replacement for washing before tin selection.

## Assessment

The existing bridge QoS trust rule is too broad for download traffic.

The comment says "endpoint-set DSCP", but on the download chains the packet source is the modem/WAN side, not a trusted LAN endpoint. This should be treated as remote/ISP-supplied DSCP unless a narrower trust model is documented.

## Recommended next slice

Change both download chains from blanket trust:

```nft
ether type ip ip dscp != 0 accept
```

to wash-first then local restore/classification:

```nft
ether type ip ip dscp set cs0
ether type ip ct mark 0x00000004 ip dscp set ef accept
ether type ip ct mark 0x00000002 ip dscp set af41 accept
ether type ip ct mark 0x00000001 ip dscp set cs1 accept
...
```

This preserves wanctl's own per-flow classification via conntrack marks and explicit rules, but prevents arbitrary WAN-side DSCP from bypassing classification.

## Candidate syntax check

Generated candidate file:

```text
/tmp/bridge-qos-wash-first.nft
```

Validated on cake-shaper with:

```bash
sudo nft -c -f /tmp/bridge-qos-wash-first.nft
```

Result:

```text
syntax-ok
```

## Applied change

Applied on 2026-07-02.

Live backup on cake-shaper:

```text
/etc/wanctl/bridge-qos.nft.pre-wash-first-20260702-205956
```

Live deployed file:

```text
/etc/wanctl/bridge-qos.nft
sha256: 35a773abe3d0f08f1473316c75ada465b220420e45065a486c9f2acfdb4114d5
```

Repo source patched:

```text
/home/kevin/projects/wanctl/deploy/nftables/bridge-qos.nft
```

Post-reload live nft starts both download chains with:

```nft
ip dscp set cs0
ct mark 0x00000004 ip dscp set ef accept
ct mark 0x00000002 ip dscp set af41 accept
ct mark 0x00000001 ip dscp set cs1 accept
ct mark 0x00000000 udp sport 53 ip dscp set ef ct mark set 0x00000004 accept
ct mark 0x00000000 udp sport 443 ip dscp set af41 ct mark set 0x00000002 accept
```

Follow-up active traffic test found an important correction: the original `ct state new ... sport ...` classifier rules do not classify normal client-initiated download replies, because those packets are already `ESTABLISHED` from conntrack's perspective. The deployed follow-up fix changed service classifiers to match unmarked packets (`ct mark 0x00000000`) instead.

Second live backup before that correction:

```text
/etc/wanctl/bridge-qos.nft.pre-reply-classify-20260702-210640
```

Verification after apply:

```text
wanctl-bridge-qos.service: active (exited), last ExecStart success
Spectrum health: healthy, GREEN/GREEN, 550M down / 28M up
ATT health: healthy, GREEN/GREEN, 95M down / 19M up
DNS: getent hosts example.com succeeded
HTTPS: curl https://example.com succeeded
CAKE qdisc counters: moving on spec-router/spec-modem/att-router/att-modem
git diff --check: clean
```

Download-path tcpdump spot check after apply:

```text
att-modem inbound still showed remote AF11 samples
att-router outbound showed locally classified AF41 samples
```

That is the intended behavior: modem-side DSCP can exist, but bridge QoS now clears it before local restore/classification.

Active DNS test after reply-classifier correction:

```text
Ran direct DNS queries from 10.10.110.226 to 1.1.1.1 while watching spec-router CAKE tin counters.

spec-router CAKE packet delta, Bulk / BestEffort / Video / Voice:
  0 / 1964 / 134 / 10844
```

The Voice tin increase confirms DNS-response classification is active after the `ct mark 0` correction. Tcpdump on `spec-router` still showed `tos 0x0` for captured DNS replies, so tcpdump on that egress path is not a reliable proof of the DSCP value CAKE used; CAKE tin counters are the better verification surface here.

## Apply shape

1. Patch repo `deploy/nftables/bridge-qos.nft`.
2. Back up live `/etc/wanctl/bridge-qos.nft` on cake-shaper.
3. Copy patched file to `/etc/wanctl/bridge-qos.nft`.
4. Reload `wanctl-bridge-qos.service`.
5. Verify:
   - `sudo nft list table bridge qos`
   - Spectrum/ATT health endpoints remain healthy
   - CAKE qdisc counters move
   - DNS and HTTPS from LAN still work
   - short tcpdump on router-facing interfaces shows only locally classified DSCP, not arbitrary modem-side DSCP passthrough

## Rollback

Restore the backed-up `/etc/wanctl/bridge-qos.nft` and restart `wanctl-bridge-qos.service`:

```bash
ssh cake-shaper 'sudo cp -p /etc/wanctl/bridge-qos.nft.pre-reply-classify-20260702-210640 /etc/wanctl/bridge-qos.nft && sudo systemctl restart wanctl-bridge-qos.service && sudo systemctl is-active wanctl-bridge-qos.service'
```

## Recommendation

Keep main-router wash in place.

Cake-shaper bridge QoS now also washes modem-side DSCP before bridge classification, then restores/classifies wanctl-owned DSCP from conntrack marks and explicit service rules.
