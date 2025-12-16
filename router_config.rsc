# 2025-12-11 22:44:52 by RouterOS 7.20.5
# software id = PBDT-QIWT
#
# model = RB5009UG+S+
# serial number = EC1A0EE7388F
/interface bridge
add ageing-time=5m arp=enabled arp-timeout=auto auto-mac=yes dhcp-snooping=no \
    disabled=no ether-type=0x8100 fast-forward=no forward-delay=15s \
    frame-types=admit-all igmp-snooping=yes igmp-version=3 ingress-filtering=\
    yes last-member-interval=1s last-member-query-count=2 \
    max-learned-entries=auto max-message-age=20s membership-interval=4m20s \
    mld-version=2 mtu=auto multicast-querier=yes multicast-router=\
    temporary-query mvrp=yes name=bridge1 port-cost-mode=short priority=\
    0x1000 protocol-mode=rstp pvid=1 querier-interval=4m15s query-interval=\
    2m5s query-response-interval=10s startup-query-count=2 \
    startup-query-interval=31s250ms transmit-hold-count=6 vlan-filtering=yes
/interface ethernet
set [ find default-name=ether1 ] advertise="10M-baseT-half,10M-baseT-full,100M\
    -baseT-half,100M-baseT-full,1G-baseT-half,1G-baseT-full,2.5G-baseT" arp=\
    enabled arp-timeout=auto auto-negotiation=yes bandwidth=\
    unlimited/unlimited disabled=no l2mtu=1514 loop-protect=default \
    loop-protect-disable-time=5m loop-protect-send-interval=5s mac-address=\
    2C:C8:1B:FF:5F:45 mtu=1500 name=ether1-WAN-Spectrum orig-mac-address=\
    2C:C8:1B:FF:5F:45 rx-flow-control=off tx-flow-control=off
set [ find default-name=ether2 ] advertise="10M-baseT-half,10M-baseT-full,100M\
    -baseT-half,100M-baseT-full,1G-baseT-half,1G-baseT-full" arp=enabled \
    arp-timeout=auto auto-negotiation=yes bandwidth=unlimited/unlimited \
    disabled=no l2mtu=1514 loop-protect=default loop-protect-disable-time=5m \
    loop-protect-send-interval=5s mac-address=2C:C8:1B:FF:5F:46 mtu=1500 \
    name=ether2-WAN-ATT orig-mac-address=2C:C8:1B:FF:5F:46 rx-flow-control=\
    off tx-flow-control=off
set [ find default-name=ether3 ] advertise="10M-baseT-half,10M-baseT-full,100M\
    -baseT-half,100M-baseT-full,1G-baseT-half,1G-baseT-full" arp=enabled \
    arp-timeout=auto auto-negotiation=yes bandwidth=unlimited/unlimited \
    disabled=no l2mtu=1514 loop-protect=default loop-protect-disable-time=5m \
    loop-protect-send-interval=5s mac-address=2C:C8:1B:FF:5F:47 mtu=1500 \
    name=ether3 orig-mac-address=2C:C8:1B:FF:5F:47 rx-flow-control=off \
    tx-flow-control=off
set [ find default-name=ether4 ] advertise="10M-baseT-half,10M-baseT-full,100M\
    -baseT-half,100M-baseT-full,1G-baseT-half,1G-baseT-full" arp=enabled \
    arp-timeout=auto auto-negotiation=yes bandwidth=unlimited/unlimited \
    disabled=no l2mtu=1514 loop-protect=default loop-protect-disable-time=5m \
    loop-protect-send-interval=5s mac-address=2C:C8:1B:FF:5F:48 mtu=1500 \
    name=ether4 orig-mac-address=2C:C8:1B:FF:5F:48 rx-flow-control=off \
    tx-flow-control=off
set [ find default-name=ether5 ] advertise="10M-baseT-half,10M-baseT-full,100M\
    -baseT-half,100M-baseT-full,1G-baseT-half,1G-baseT-full" arp=enabled \
    arp-timeout=auto auto-negotiation=yes bandwidth=unlimited/unlimited \
    disabled=no l2mtu=1514 loop-protect=default loop-protect-disable-time=5m \
    loop-protect-send-interval=5s mac-address=2C:C8:1B:FF:5F:49 mtu=1500 \
    name=ether5 orig-mac-address=2C:C8:1B:FF:5F:49 rx-flow-control=off \
    tx-flow-control=off
set [ find default-name=ether6 ] advertise="10M-baseT-half,10M-baseT-full,100M\
    -baseT-half,100M-baseT-full,1G-baseT-half,1G-baseT-full" arp=enabled \
    arp-timeout=auto auto-negotiation=yes bandwidth=unlimited/unlimited \
    disabled=no l2mtu=1514 loop-protect=default loop-protect-disable-time=5m \
    loop-protect-send-interval=5s mac-address=2C:C8:1B:FF:5F:4A mtu=1500 \
    name=ether6 orig-mac-address=2C:C8:1B:FF:5F:4A rx-flow-control=off \
    tx-flow-control=off
set [ find default-name=ether7 ] advertise="10M-baseT-half,10M-baseT-full,100M\
    -baseT-half,100M-baseT-full,1G-baseT-half,1G-baseT-full" arp=enabled \
    arp-timeout=auto auto-negotiation=yes bandwidth=unlimited/unlimited \
    disabled=no l2mtu=1514 loop-protect=default loop-protect-disable-time=5m \
    loop-protect-send-interval=5s mac-address=2C:C8:1B:FF:5F:4B mtu=1500 \
    name=ether7 orig-mac-address=2C:C8:1B:FF:5F:4B rx-flow-control=off \
    tx-flow-control=off
set [ find default-name=ether8 ] advertise="10M-baseT-half,10M-baseT-full,100M\
    -baseT-half,100M-baseT-full,1G-baseT-half,1G-baseT-full" arp=enabled \
    arp-timeout=auto auto-negotiation=yes bandwidth=unlimited/unlimited \
    disabled=no l2mtu=1514 loop-protect=default loop-protect-disable-time=5m \
    loop-protect-send-interval=5s mac-address=2C:C8:1B:FF:5F:4C mtu=1500 \
    name="ether8-MGMT Port" orig-mac-address=2C:C8:1B:FF:5F:4C \
    rx-flow-control=off tx-flow-control=off
set [ find default-name=sfp-sfpplus1 ] advertise=10G-baseCR arp=enabled \
    arp-timeout=auto auto-negotiation=yes bandwidth=unlimited/unlimited \
    comment="Link to 10g Switch" disabled=no l2mtu=1514 loop-protect=default \
    loop-protect-disable-time=5m loop-protect-send-interval=5s mac-address=\
    2C:C8:1B:FF:5F:4D mtu=1500 name=sfp-10gSwitch orig-mac-address=\
    2C:C8:1B:FF:5F:4D rx-flow-control=on sfp-ignore-rx-los=yes \
    sfp-rate-select=low sfp-shutdown-temperature=95C tx-flow-control=on
/interface veth
add address=172.17.0.2/24 comment=containers dhcp=no disabled=no gateway=\
    172.17.0.1 gateway6="" mac-address=00:00:00:00:00:00 name=veth1
/interface wireguard
add disabled=no listen-port=51820 mtu=1420 name=wireguard1
/queue interface
set bridge1 queue=no-queue
set veth1 queue=no-queue
set wireguard1 queue=no-queue
/interface vlan
add arp=enabled arp-timeout=auto comment=MGMT disabled=no interface=bridge1 \
    loop-protect=default loop-protect-disable-time=5m \
    loop-protect-send-interval=5s mtu=1500 mvrp=yes name=vlan99-mgmt \
    use-service-tag=no vlan-id=99
add arp=enabled arp-timeout=auto comment=Trusted disabled=no interface=\
    bridge1 loop-protect=default loop-protect-disable-time=5m \
    loop-protect-send-interval=5s mtu=1500 mvrp=yes name=vlan110-trusted \
    use-service-tag=no vlan-id=110
add arp=enabled arp-timeout=auto comment=IOT disabled=no interface=bridge1 \
    loop-protect=default loop-protect-disable-time=5m \
    loop-protect-send-interval=5s mtu=1500 mvrp=yes name=vlan120-IOT \
    use-service-tag=no vlan-id=120
add arp=enabled arp-timeout=auto comment=Camera disabled=no interface=bridge1 \
    loop-protect=default loop-protect-disable-time=5m \
    loop-protect-send-interval=5s mtu=1500 mvrp=yes name=vlan130-camera \
    use-service-tag=no vlan-id=130
/queue interface
set vlan99-mgmt queue=no-queue
set vlan110-trusted queue=no-queue
set vlan120-IOT queue=no-queue
set vlan130-camera queue=no-queue
/disk
set usb1 compress=no disabled=no media-interface=none media-sharing=no \
    mount-filesystem=yes !mount-point-template mount-read-only=no parent="" \
    slot=usb1 smb-sharing=no swap=no type=hardware
/interface ethernet switch
set 0 cpu-flow-control=yes mirror-egress-target=none name=switch1
/interface ethernet switch port
set 0 !egress-rate !ingress-rate mirror-egress=no mirror-ingress=no \
    mirror-ingress-target=none
set 1 !egress-rate !ingress-rate mirror-egress=no mirror-ingress=no \
    mirror-ingress-target=none
set 2 !egress-rate !ingress-rate mirror-egress=no mirror-ingress=no \
    mirror-ingress-target=none
set 3 !egress-rate !ingress-rate mirror-egress=no mirror-ingress=no \
    mirror-ingress-target=none
set 4 !egress-rate !ingress-rate mirror-egress=no mirror-ingress=no \
    mirror-ingress-target=none
set 5 !egress-rate !ingress-rate mirror-egress=no mirror-ingress=no \
    mirror-ingress-target=none
set 6 !egress-rate !ingress-rate mirror-egress=no mirror-ingress=no \
    mirror-ingress-target=none
set 7 !egress-rate !ingress-rate mirror-egress=no mirror-ingress=no \
    mirror-ingress-target=none
set 8 !egress-rate !ingress-rate mirror-egress=no mirror-ingress=no \
    mirror-ingress-target=none
set 9 !egress-rate !ingress-rate mirror-egress=no mirror-ingress=no \
    mirror-ingress-target=none
/interface ethernet switch port-isolation
set 0 !forwarding-override
set 1 !forwarding-override
set 2 !forwarding-override
set 3 !forwarding-override
set 4 !forwarding-override
set 5 !forwarding-override
set 6 !forwarding-override
set 7 !forwarding-override
set 8 !forwarding-override
set 9 !forwarding-override
/interface list
set [ find name=all ] comment="contains all interfaces" exclude="" include="" \
    name=all
set [ find name=none ] comment="contains no interfaces" exclude="" include="" \
    name=none
set [ find name=dynamic ] comment="contains dynamic interfaces" exclude="" \
    include="" name=dynamic
set [ find name=static ] comment="contains static interfaces" exclude="" \
    include="" name=static
add exclude="" include="" name=WAN
add exclude="" include="" name=LAN
add exclude="" include="" name=VLAN
add exclude="" include="" name=WIRELESS
add comment="VPN interfaces (WireGuard, etc.)" exclude="" include="" name=VPN
/interface lte apn
set [ find default=yes ] add-default-route=yes apn=internet authentication=\
    none default-route-distance=2 ip-type=ipv4 name=default use-network-apn=\
    no use-peer-dns=yes
/interface macsec profile
set [ find default-name=default ] name=default server-priority=10
/interface wireless security-profiles
set [ find default=yes ] authentication-types="" disable-pmkid=no \
    eap-methods=passthrough group-ciphers=aes-ccm group-key-update=5m \
    interim-update=0s management-protection=disabled mode=none \
    mschapv2-username="" name=default radius-called-format=mac:ssid \
    radius-eap-accounting=no radius-mac-accounting=no \
    radius-mac-authentication=no radius-mac-caching=disabled \
    radius-mac-format=XX:XX:XX:XX:XX:XX radius-mac-mode=as-username \
    static-algo-0=none static-algo-1=none static-algo-2=none static-algo-3=\
    none static-sta-private-algo=none static-transmit-key=key-0 \
    supplicant-identity=MikroTik tls-certificate=none tls-mode=\
    no-certificates unicast-ciphers=aes-ccm
/ip dhcp-client option
set clientid_duid code=61 name=clientid_duid value="0xff\$(CLIENT_DUID)"
set clientid code=61 name=clientid value="0x01\$(CLIENT_MAC)"
set hostname code=12 name=hostname value="\$(HOSTNAME)"
/ip dhcp-server option
add code=66 comment=ruckus-tftp name=ruckus-tftp value="'10.10.110.1'"
/ip hotspot profile
set [ find default=yes ] dns-name="" hotspot-address=0.0.0.0 html-directory=\
    hotspot html-directory-override="" http-cookie-lifetime=3d http-proxy=\
    0.0.0.0:0 install-hotspot-queue=yes login-by=cookie,http-chap name=\
    default rate-limit="" smtp-server=0.0.0.0 split-user-domain=no \
    use-radius=no
/ip hotspot user profile
set [ find default=yes ] add-mac-cookie=yes address-list="" idle-timeout=none \
    !insert-queue-before keepalive-timeout=2m mac-cookie-timeout=3d name=\
    default !parent-queue !queue-type shared-users=1 status-autorefresh=1m \
    transparent-proxy=no
/ip ipsec mode-config
set [ find default=yes ] name=request-only responder=no use-responder-dns=\
    exclusively
/ip ipsec policy group
set [ find default=yes ] name=default
/ip ipsec profile
set [ find default=yes ] dh-group=modp2048,modp1024 dpd-interval=2m \
    dpd-maximum-failures=5 enc-algorithm=aes-128,3des hash-algorithm=sha1 \
    lifetime=1d name=default nat-traversal=yes proposal-check=obey
add dh-group=modp2048 dpd-interval=2m dpd-maximum-failures=5 enc-algorithm=\
    aes-256 hash-algorithm=sha256 lifetime=1d name=icsolutions nat-traversal=\
    no proposal-check=obey
/ip ipsec peer
add address=174.47.171.10/32 disabled=yes exchange-mode=main name=icsolutions \
    profile=icsolutions send-initial-contact=yes
/ip ipsec proposal
set [ find default=yes ] auth-algorithms=sha1 disabled=yes enc-algorithms=\
    aes-256-cbc,aes-192-cbc,aes-128-cbc lifetime=30m name=default pfs-group=\
    modp1024
add auth-algorithms=sha256 disabled=no enc-algorithms=aes-256-cbc lifetime=\
    12h name=icsolutions pfs-group=none
/ip pool
add name=vlan110 ranges=10.10.110.200-10.10.110.250
add name=vlan120 ranges=10.10.120.200-10.10.120.250
add name=vlan130 ranges=10.10.130.250-10.10.130.254
add name=dhcp_pool8 ranges=10.10.140.2-10.10.140.254
add name=ap_pool ranges=10.10.250.100-10.10.250.200
/ip dhcp-server
add add-arp=yes address-lists="" address-pool=vlan110 disabled=no interface=\
    vlan110-trusted lease-script="# When \"1\" all DNS entries with IP address\
    \_of DHCP lease are removed\
    \n:local dnsRemoveAllByIp \"1\"\
    \n# When \"1\" all DNS entries with hostname of DHCP lease are removed\
    \n:local dnsRemoveAllByName \"1\"\
    \n# When \"1\" addition and removal of DNS entries is always done also for\
    \_non-FQDN hostname\
    \n:local dnsAlwaysNonfqdn \"1\"\
    \n# DNS domain to add after DHCP client hostname\
    \n:local dnsDomain \"home.arpa\"\
    \n# DNS TTL to set for DNS entries\
    \n:local dnsTtl \"00:15:00\"\
    \n# Source of DHCP client hostname, can be \"lease-hostname\" or any other\
    \_lease attribute, like \"host-name\" or \"comment\"\
    \n:local leaseClientHostnameSource \"lease-hostname\"\
    \n\
    \n:local leaseComment \"dhcp-lease-script_\$leaseServerName_\$leaseClientH\
    ostnameSource\"\
    \n:local leaseClientHostname\
    \n:if (\$leaseClientHostnameSource = \"lease-hostname\") do={\
    \n  :set leaseClientHostname \$\"lease-hostname\"\
    \n} else={\
    \n  :set leaseClientHostname ([:pick \\\
    \n    [/ip dhcp-server lease print as-value where server=\"\$leaseServerNa\
    me\" address=\"\$leaseActIP\" mac-address=\"\$leaseActMAC\"] \\\
    \n    0]->\"\$leaseClientHostnameSource\")\
    \n}\
    \n:local leaseClientHostnames \"\$leaseClientHostname\"\
    \n:if ([:len [\$dnsDomain]] > 0) do={\
    \n  :if (\$dnsAlwaysNonfqdn = \"1\") do={\
    \n    :set leaseClientHostnames \"\$leaseClientHostname.\$dnsDomain,\$leas\
    eClientHostname\"\
    \n  } else={\
    \n    :set leaseClientHostnames \"\$leaseClientHostname.\$dnsDomain\"\
    \n  }\
    \n}\
    \n:if (\$dnsRemoveAllByIp = \"1\") do={\
    \n  /ip dns static remove [/ip dns static find comment=\"\$leaseComment\" \
    and address=\"\$leaseActIP\"]\
    \n}\
    \n:foreach h in=[:toarray value=\"\$leaseClientHostnames\"] do={\
    \n  :if (\$dnsRemoveAllByName = \"1\") do={\
    \n    /ip dns static remove [/ip dns static find comment=\"\$leaseComment\
    \" and name=\"\$h\"]\
    \n  }\
    \n  /ip dns static remove [/ip dns static find comment=\"\$leaseComment\" \
    and address=\"\$leaseActIP\" and name=\"\$h\"]\
    \n  :if (\$leaseBound = \"1\") do={\
    \n    :delay 1\
    \n    /ip dns static add comment=\"\$leaseComment\" address=\"\$leaseActIP\
    \" name=\"\$h\" ttl=\"\$dnsTtl\"\
    \n  }\
    \n}" lease-time=1d name=vlan110 use-radius=no use-reconfigure=no
add add-arp=yes address-lists="" address-pool=vlan120 disabled=no interface=\
    vlan120-IOT lease-script="" lease-time=1d name=vlan120 use-radius=no \
    use-reconfigure=no
add add-arp=yes address-lists="" address-pool=vlan130 disabled=no interface=\
    vlan130-camera lease-script="" lease-time=1d10m name=vlan130 use-radius=\
    no use-reconfigure=no
/ip smb users
set [ find default=yes ] disabled=yes name=guest read-only=yes
/port
set 0 baud-rate=auto data-bits=8 flow-control=none name=serial0 parity=none \
    stop-bits=1
set 1 baud-rate=auto data-bits=8 flow-control=none name=serial1 parity=none \
    stop-bits=1
set 2 baud-rate=115200 data-bits=8 flow-control=none name=usb3 parity=none \
    stop-bits=1
/ppp profile
set *0 address-list="" !bridge !bridge-horizon bridge-learning=default \
    !bridge-path-cost !bridge-port-priority !bridge-port-trusted \
    !bridge-port-vid change-tcp-mss=yes !dhcpv6-lease-time !dhcpv6-use-radius \
    !dns-server !idle-timeout !incoming-filter !insert-queue-before \
    !interface-list !local-address name=default on-down="" on-up="" only-one=\
    default !outgoing-filter !parent-queue !queue-type !rate-limit \
    !remote-address !remote-ipv6-prefix-reuse !session-timeout \
    use-compression=default use-encryption=default use-ipv6=yes use-mpls=\
    default use-upnp=default !wins-server
set *FFFFFFFE address-list="" !bridge !bridge-horizon bridge-learning=default \
    !bridge-path-cost !bridge-port-priority !bridge-port-trusted \
    !bridge-port-vid change-tcp-mss=yes !dhcpv6-lease-time !dhcpv6-use-radius \
    !dns-server !idle-timeout !incoming-filter !insert-queue-before \
    !interface-list !local-address name=default-encryption on-down="" on-up=\
    "" only-one=default !outgoing-filter !parent-queue !queue-type \
    !rate-limit !remote-address !remote-ipv6-prefix-reuse !session-timeout \
    use-compression=default use-encryption=yes use-ipv6=yes use-mpls=default \
    use-upnp=default !wins-server
/queue type
set 0 kind=sfq name=default sfq-allot=1514 sfq-perturb=5
set 1 kind=pfifo name=ethernet-default pfifo-limit=50
set 2 cake-ack-filter=none cake-bandwidth=0bps cake-diffserv=diffserv4 \
    cake-flowmode=dual-dsthost cake-nat=yes cake-overhead=0 \
    cake-overhead-scheme="" cake-rtt=100ms cake-wash=no kind=cake name=\
    wireless-default
set 3 kind=red name=synchronous-default red-avg-packet=1000 red-burst=20 \
    red-limit=60 red-max-threshold=50 red-min-threshold=10
set 4 kind=sfq name=hotspot-default sfq-allot=1514 sfq-perturb=5
add cake-ack-filter=aggressive cake-atm=ptm cake-bandwidth=0bps \
    cake-diffserv=diffserv4 cake-flowmode=triple-isolate cake-nat=yes \
    cake-overhead=30 cake-overhead-scheme=pppoe-ptm cake-rtt=30ms \
    cake-rtt-scheme=regional cake-wash=no kind=cake name=cake-up-att
add cake-ack-filter=none cake-atm=ptm cake-bandwidth=0bps cake-diffserv=\
    diffserv4 cake-flowmode=triple-isolate cake-nat=yes cake-overhead=30 \
    cake-overhead-scheme=pppoe-ptm cake-rtt=50ms cake-wash=no kind=cake name=\
    cake-down-att
add cake-ack-filter=none cake-bandwidth=0bps cake-diffserv=diffserv4 \
    cake-flowmode=triple-isolate cake-mpu=64 cake-nat=yes cake-overhead=18 \
    cake-overhead-scheme=docsis cake-rtt=25ms cake-wash=no kind=cake name=\
    cake-down-spectrum
add cake-ack-filter=aggressive cake-bandwidth=0bps cake-diffserv=diffserv4 \
    cake-flowmode=triple-isolate cake-mpu=64 cake-nat=yes cake-overhead=18 \
    cake-overhead-scheme=docsis cake-rtt=25ms cake-wash=no kind=cake name=\
    cake-up-spectrum
set 9 kind=pcq name=pcq-upload-default pcq-burst-rate=0 pcq-burst-threshold=0 \
    pcq-burst-time=10s pcq-classifier=src-address pcq-dst-address-mask=32 \
    pcq-dst-address6-mask=128 pcq-limit=50KiB pcq-rate=0 \
    pcq-src-address-mask=32 pcq-src-address6-mask=128 pcq-total-limit=2000KiB
set 10 kind=pcq name=pcq-download-default pcq-burst-rate=0 \
    pcq-burst-threshold=0 pcq-burst-time=10s pcq-classifier=dst-address \
    pcq-dst-address-mask=32 pcq-dst-address6-mask=128 pcq-limit=50KiB \
    pcq-rate=0 pcq-src-address-mask=32 pcq-src-address6-mask=128 \
    pcq-total-limit=2000KiB
set 11 kind=none name=only-hardware-queue
set 12 kind=mq-pfifo mq-pfifo-limit=2000 name=multi-queue-ethernet-default
set 13 kind=pfifo name=default-small pfifo-limit=10
/queue interface
set ether1-WAN-Spectrum queue=only-hardware-queue
set ether2-WAN-ATT queue=only-hardware-queue
/queue tree
add bucket-size=0 burst-limit=0 burst-threshold=0 burst-time=0s comment=\
    "ATT upload shaping" disabled=no limit-at=0 max-limit=17M name=\
    WAN-Upload-ATT packet-mark=wan-out-att parent=global priority=8 queue=\
    cake-up-att
add bucket-size=0.1 burst-limit=0 burst-threshold=0 burst-time=0s comment=\
    "ATT download shaping" disabled=no limit-at=0 max-limit=87M name=\
    WAN-Download-ATT packet-mark=wan-in-att parent=bridge1 priority=8 queue=\
    cake-down-att
add bucket-size=0.1 burst-limit=0 burst-threshold=0 burst-time=0s comment=\
    "Spectrum download shaping (VLAN egress)" disabled=no limit-at=0 \
    max-limit=870M name=WAN-Download-Spectrum packet-mark=wan-in-spectrum \
    parent=bridge1 priority=8 queue=cake-down-spectrum
add bucket-size=0 burst-limit=0 burst-threshold=0 burst-time=0s comment=\
    "Spectrum upload shaping" disabled=no limit-at=0 max-limit=35M name=\
    WAN-Upload-Spectrum packet-mark=wan-out-spectrum parent=global priority=8 \
    queue=cake-up-spectrum
/routing bgp template
set default disabled=no name=default output.network=bgp-networks
/routing ospf instance
add disabled=no name=default-v2 router-id=main version=2 vrf=main
add disabled=no name=default-v3 router-id=main version=3 vrf=main
/routing ospf area
add area-id=0.0.0.0 disabled=yes instance=default-v2 name=backbone-v2 type=\
    default
add area-id=0.0.0.0 disabled=yes instance=default-v3 name=backbone-v3 type=\
    default
/routing table
add disabled=no fib name=to_ATT
add disabled=no fib name=to_Spectrum
/snmp community
set [ find default=yes ] addresses=10.10.110.0/24 authentication-protocol=MD5 \
    disabled=no encryption-protocol=DES name=public read-access=yes security=\
    none write-access=no
/system logging action
set 0 memory-lines=1000 memory-stop-on-full=no name=memory target=memory
set 1 disk-file-count=2 disk-file-name=log disk-lines-per-file=1000 \
    disk-stop-on-full=no name=disk target=disk
set 2 name=echo remember=yes target=echo
set 3 name=remote remote=0.0.0.0 remote-log-format=default remote-port=514 \
    remote-protocol=udp src-address=0.0.0.0 syslog-facility=daemon \
    syslog-severity=auto syslog-time-format=bsd-syslog target=remote vrf=main
add name=remotesyslog remote=10.10.99.50 remote-log-format=default \
    remote-port=514 remote-protocol=udp src-address=10.10.99.1 \
    syslog-facility=daemon syslog-severity=auto syslog-time-format=bsd-syslog \
    target=remote vrf=main
/user group
set read name=read policy="local,telnet,ssh,reboot,read,test,winbox,password,w\
    eb,sniff,sensitive,api,romon,rest-api,!ftp,!write,!policy" skin=default
set write name=write policy="local,telnet,ssh,reboot,read,write,test,winbox,pa\
    ssword,web,sniff,sensitive,api,romon,rest-api,!ftp,!policy" skin=default
set full name=full policy="local,telnet,ssh,ftp,reboot,read,write,policy,test,\
    winbox,password,web,sniff,sensitive,api,romon,rest-api" skin=default
add name=prometheus policy="read,test,winbox,api,!local,!telnet,!ssh,!ftp,!reb\
    oot,!write,!policy,!password,!web,!sniff,!sensitive,!romon,!rest-api" \
    skin=default
/user-manager attribute
set [ find default-name=Framed-IP-Address ] name=Framed-IP-Address \
    packet-types=access-accept type-id=8 value-type=ip-address vendor-id=\
    standard
set [ find default-name=Framed-IP-Netmask ] name=Framed-IP-Netmask \
    packet-types=access-accept type-id=9 value-type=ip-address vendor-id=\
    standard
set [ find default-name=Session-Timeout ] name=Session-Timeout packet-types=\
    access-accept type-id=27 value-type=uint32 vendor-id=standard
set [ find default-name=Idle-Timeout ] name=Idle-Timeout packet-types=\
    access-accept type-id=28 value-type=uint32 vendor-id=standard
set [ find default-name=Framed-Pool ] name=Framed-Pool packet-types=\
    access-accept type-id=88 value-type=string vendor-id=standard
set [ find default-name=Framed-IPv6-Address ] name=Framed-IPv6-Address \
    packet-types=access-accept type-id=168 value-type=ip-address vendor-id=\
    standard
set [ find default-name=Framed-IPv6-Pool ] name=Framed-IPv6-Pool \
    packet-types=access-accept type-id=100 value-type=string vendor-id=\
    standard
set [ find default-name=Framed-IPv6-Prefix ] name=Framed-IPv6-Prefix \
    packet-types=access-accept type-id=97 value-type=ip6-prefix vendor-id=\
    standard
set [ find default-name=Delegated-IPv6-Prefix ] name=Delegated-IPv6-Prefix \
    packet-types=access-accept type-id=123 value-type=ip6-prefix vendor-id=\
    standard
set [ find default-name=Tunnel-Type ] name=Tunnel-Type packet-types=\
    access-accept type-id=64 value-type=uint32 vendor-id=standard
set [ find default-name=Tunnel-Medium-Type ] name=Tunnel-Medium-Type \
    packet-types=access-accept type-id=65 value-type=uint32 vendor-id=\
    standard
set [ find default-name=Tunnel-Private-Group-ID ] name=\
    Tunnel-Private-Group-ID packet-types=access-accept type-id=81 value-type=\
    string vendor-id=standard
set [ find default-name=Acct-Interim-Interval ] name=Acct-Interim-Interval \
    packet-types=access-accept type-id=85 value-type=uint32 vendor-id=\
    standard
set [ find default-name=Mikrotik-Recv-Limit ] name=Mikrotik-Recv-Limit \
    packet-types=access-accept type-id=1 value-type=uint32 vendor-id=Mikrotik
set [ find default-name=Mikrotik-Xmit-Limit ] name=Mikrotik-Xmit-Limit \
    packet-types=access-accept type-id=2 value-type=uint32 vendor-id=Mikrotik
set [ find default-name=Mikrotik-Group ] name=Mikrotik-Group packet-types=\
    access-accept type-id=3 value-type=string vendor-id=Mikrotik
set [ find default-name=Mikrotik-Wireless-Forward ] name=\
    Mikrotik-Wireless-Forward packet-types=access-accept type-id=4 \
    value-type=uint32 vendor-id=Mikrotik
set [ find default-name="Mikrotik-Wireless-Skip-Dot1x " ] name=\
    "Mikrotik-Wireless-Skip-Dot1x " packet-types=access-accept type-id=5 \
    value-type=uint32 vendor-id=Mikrotik
set [ find default-name=Mikrotik-Wireless-Enc-Algo ] name=\
    Mikrotik-Wireless-Enc-Algo packet-types=access-accept type-id=6 \
    value-type=uint32 vendor-id=Mikrotik
set [ find default-name=Mikrotik-Wireless-Enc-Key ] name=\
    Mikrotik-Wireless-Enc-Key packet-types=access-accept type-id=7 \
    value-type=string vendor-id=Mikrotik
set [ find default-name=Mikrotik-Rate-Limit ] name=Mikrotik-Rate-Limit \
    packet-types=access-accept type-id=8 value-type=string vendor-id=Mikrotik
set [ find default-name=Mikrotik-Realm ] name=Mikrotik-Realm packet-types=\
    access-accept type-id=9 value-type=string vendor-id=Mikrotik
set [ find default-name=Mikrotik-Host-IP ] name=Mikrotik-Host-IP \
    packet-types=access-accept type-id=10 value-type=ip-address vendor-id=\
    Mikrotik
set [ find default-name=Mikrotik-Mark-Id ] name=Mikrotik-Mark-Id \
    packet-types=access-accept type-id=11 value-type=string vendor-id=\
    Mikrotik
set [ find default-name=Mikrotik-Advertise-URL ] name=Mikrotik-Advertise-URL \
    packet-types=access-accept type-id=12 value-type=string vendor-id=\
    Mikrotik
set [ find default-name=Mikrotik-Advertise-Interval ] name=\
    Mikrotik-Advertise-Interval packet-types=access-accept type-id=13 \
    value-type=uint32 vendor-id=Mikrotik
set [ find default-name=Mikrotik-Recv-Limit-Gigawords ] name=\
    Mikrotik-Recv-Limit-Gigawords packet-types=access-accept type-id=14 \
    value-type=uint32 vendor-id=Mikrotik
set [ find default-name=Mikrotik-Xmit-Limit-Gigawords ] name=\
    Mikrotik-Xmit-Limit-Gigawords packet-types=access-accept type-id=15 \
    value-type=uint32 vendor-id=Mikrotik
set [ find default-name=Mikrotik-Wireless-PSK ] name=Mikrotik-Wireless-PSK \
    packet-types=access-accept type-id=16 value-type=string vendor-id=\
    Mikrotik
set [ find default-name=Mikrotik-Total-Limit ] name=Mikrotik-Total-Limit \
    packet-types=access-accept type-id=17 value-type=uint32 vendor-id=\
    Mikrotik
set [ find default-name=Mikrotik-Total-Limit-Gigawords ] name=\
    Mikrotik-Total-Limit-Gigawords packet-types=access-accept type-id=18 \
    value-type=uint32 vendor-id=Mikrotik
set [ find default-name=Mikrotik-Address-List ] name=Mikrotik-Address-List \
    packet-types=access-accept type-id=19 value-type=string vendor-id=\
    Mikrotik
set [ find default-name=Mikrotik-Wireless-MPKey ] name=\
    Mikrotik-Wireless-MPKey packet-types=access-accept type-id=20 value-type=\
    string vendor-id=Mikrotik
set [ find default-name=Mikrotik-Wireless-Comment ] name=\
    Mikrotik-Wireless-Comment packet-types=access-accept type-id=21 \
    value-type=string vendor-id=Mikrotik
set [ find default-name=Mikrotik-Delegated-IPv6-Pool ] name=\
    Mikrotik-Delegated-IPv6-Pool packet-types=access-accept type-id=22 \
    value-type=string vendor-id=Mikrotik
set [ find default-name=Mikrotik-DHCP-Option-Set ] name=\
    Mikrotik-DHCP-Option-Set packet-types=access-accept type-id=23 \
    value-type=string vendor-id=Mikrotik
set [ find default-name=Mikrotik-DHCP-Option-Param-STR1 ] name=\
    Mikrotik-DHCP-Option-Param-STR1 packet-types=access-accept type-id=24 \
    value-type=string vendor-id=Mikrotik
set [ find default-name=Mikrotik-DHCP-Option-Param-STR2 ] name=\
    Mikrotik-DHCP-Option-Param-STR2 packet-types=access-accept type-id=25 \
    value-type=string vendor-id=Mikrotik
set [ find default-name=Mikrotik-Wireless-VLANID ] name=\
    Mikrotik-Wireless-VLANID packet-types=access-accept type-id=26 \
    value-type=uint32 vendor-id=Mikrotik
set [ find default-name=Mikrotik-Wireless-VLANIDtype ] name=\
    Mikrotik-Wireless-VLANIDtype packet-types=access-accept type-id=27 \
    value-type=uint32 vendor-id=Mikrotik
set [ find default-name=Mikrotik-Wireless-Minsignal ] name=\
    Mikrotik-Wireless-Minsignal packet-types=access-accept type-id=28 \
    value-type=string vendor-id=Mikrotik
set [ find default-name=Mikrotik-Wireless-Maxsignal ] name=\
    Mikrotik-Wireless-Maxsignal packet-types=access-accept type-id=29 \
    value-type=string vendor-id=Mikrotik
set [ find default-name=Mikrotik-Switching-Filter ] name=\
    Mikrotik-Switching-Filter packet-types=access-accept type-id=30 \
    value-type=string vendor-id=Mikrotik
/user-manager user group
set [ find default-name=default ] attributes="" inner-auths=\
    ttls-pap,ttls-chap,ttls-mschap1,ttls-mschap2,peap-mschap2 name=default \
    outer-auths=\
    pap,chap,mschap1,mschap2,eap-tls,eap-ttls,eap-peap,eap-mschap2
set [ find default-name=default-anonymous ] attributes="" inner-auths="" \
    name=default-anonymous outer-auths=eap-ttls,eap-peap
/user-manager user
add attributes="" disabled=no group=default name=kevin shared-users=1
/zerotier
set zt1 comment="ZeroTier Central controller - https://my.zerotier.com/" \
    disabled=no disabled=no interfaces=all name=zt1 port=9993 route-distance=\
    1
/zerotier interface
add allow-default=no allow-global=no allow-managed=yes arp-timeout=auto \
    comment=zerotier disabled=no instance=zt1 name=myZeroTier network=\
    46f4a69fae912735
/queue interface
set myZeroTier queue=wireless-default
/zerotier controller
add broadcast=yes disabled=no disabled=no instance=zt1 ip-range=\
    172.27.27.10-172.27.27.20 ip6-6plane=no ip6-rfc4193=no mtu=2800 \
    multicast-limit=32 name=ZT-private network=46f4a69fae912735 private=yes \
    routes=172.27.27.0/24
/caps-man aaa
set called-format=mac:ssid interim-update=disabled mac-caching=disabled \
    mac-format=XX:XX:XX:XX:XX:XX mac-mode=as-username
/queue interface
set ether3 queue=*1E
set ether4 queue=*1E
set ether5 queue=*1E
set ether6 queue=*1E
set ether7 queue=*1E
set "ether8-MGMT Port" queue=*1E
set sfp-10gSwitch queue=*1E
/caps-man manager
set ca-certificate=none certificate=none enabled=no package-path=/ \
    require-peer-certificate=no upgrade-policy=suggest-same-version
/caps-man manager interface
set [ find default=yes ] disabled=no forbid=yes interface=all
/certificate settings
set builtin-trust-anchors=not-trusted crl-download=no crl-store=ram crl-use=\
    no
/console settings
set log-script-errors=yes sanitize-names=no tab-width=4
/container config
set layer-dir="" memory-high=unlimited !registry-url tmpdir=usb1/pull \
    username=""
/disk settings
set auto-media-interface=none auto-media-sharing=no auto-smb-sharing=no \
    auto-smb-user=guest default-mount-point-template="[slot]"
/ip smb
set comment=MikrotikSMB domain=MSHOME enabled=auto interfaces=all
/interface bridge port
add auto-isolate=no bpdu-guard=no bridge=bridge1 broadcast-flood=yes \
    disabled=no edge=auto fast-leave=no frame-types=admit-only-vlan-tagged \
    horizon=none hw=no ingress-filtering=yes interface=sfp-10gSwitch \
    internal-path-cost=10 learn=auto multicast-router=temporary-query \
    mvrp-applicant-state=normal-participant mvrp-registrar-state=fixed \
    path-cost=10 point-to-point=auto priority=0x80 pvid=1 restricted-role=no \
    restricted-tcn=no tag-stacking=no trusted=no unknown-multicast-flood=yes \
    unknown-unicast-flood=yes
add auto-isolate=no bpdu-guard=no bridge=bridge1 broadcast-flood=yes \
    disabled=no edge=auto fast-leave=no frame-types=\
    admit-only-untagged-and-priority-tagged horizon=none hw=no \
    ingress-filtering=yes interface=ether3 internal-path-cost=10 learn=auto \
    multicast-router=temporary-query mvrp-applicant-state=normal-participant \
    mvrp-registrar-state=fixed path-cost=10 point-to-point=auto priority=0x80 \
    pvid=1 restricted-role=no restricted-tcn=no tag-stacking=no trusted=no \
    unknown-multicast-flood=yes unknown-unicast-flood=yes
add auto-isolate=no bpdu-guard=no bridge=bridge1 broadcast-flood=yes \
    disabled=no edge=auto fast-leave=no frame-types=\
    admit-only-untagged-and-priority-tagged horizon=none hw=no \
    ingress-filtering=yes interface=ether7 internal-path-cost=10 learn=auto \
    multicast-router=temporary-query mvrp-applicant-state=normal-participant \
    mvrp-registrar-state=fixed path-cost=10 point-to-point=auto priority=0x80 \
    pvid=1 restricted-role=no restricted-tcn=no tag-stacking=no trusted=no \
    unknown-multicast-flood=yes unknown-unicast-flood=yes
add auto-isolate=no bpdu-guard=no bridge=bridge1 broadcast-flood=yes \
    disabled=no edge=auto fast-leave=no frame-types=\
    admit-only-untagged-and-priority-tagged horizon=none hw=no \
    ingress-filtering=yes interface=ether6 internal-path-cost=10 learn=auto \
    multicast-router=temporary-query mvrp-applicant-state=normal-participant \
    mvrp-registrar-state=fixed path-cost=10 point-to-point=auto priority=0x80 \
    pvid=1 restricted-role=no restricted-tcn=no tag-stacking=no trusted=no \
    unknown-multicast-flood=yes unknown-unicast-flood=yes
add auto-isolate=no bpdu-guard=no bridge=bridge1 broadcast-flood=yes \
    disabled=no edge=auto fast-leave=no frame-types=\
    admit-only-untagged-and-priority-tagged horizon=none hw=no \
    ingress-filtering=yes interface=ether4 internal-path-cost=10 learn=auto \
    multicast-router=temporary-query mvrp-applicant-state=normal-participant \
    mvrp-registrar-state=fixed path-cost=10 point-to-point=auto priority=0x80 \
    pvid=1 restricted-role=no restricted-tcn=no tag-stacking=no trusted=no \
    unknown-multicast-flood=yes unknown-unicast-flood=yes
add auto-isolate=no bpdu-guard=no bridge=bridge1 broadcast-flood=yes \
    disabled=no edge=auto fast-leave=no frame-types=\
    admit-only-untagged-and-priority-tagged horizon=none hw=no \
    ingress-filtering=yes interface=ether5 internal-path-cost=10 learn=auto \
    multicast-router=temporary-query mvrp-applicant-state=normal-participant \
    mvrp-registrar-state=fixed path-cost=10 point-to-point=auto priority=0x80 \
    pvid=1 restricted-role=no restricted-tcn=no tag-stacking=no trusted=no \
    unknown-multicast-flood=yes unknown-unicast-flood=yes
add auto-isolate=no bpdu-guard=no bridge=bridge1 broadcast-flood=yes \
    disabled=no edge=auto fast-leave=no frame-types=admit-all horizon=none \
    hw=yes ingress-filtering=yes interface="ether8-MGMT Port" \
    !internal-path-cost learn=auto multicast-router=temporary-query \
    mvrp-applicant-state=normal-participant mvrp-registrar-state=normal \
    !path-cost point-to-point=auto priority=0x80 pvid=99 restricted-role=no \
    restricted-tcn=no tag-stacking=no trusted=no unknown-multicast-flood=yes \
    unknown-unicast-flood=yes
/interface bridge settings
set allow-fast-path=yes use-ip-firewall=yes use-ip-firewall-for-pppoe=no \
    use-ip-firewall-for-vlan=yes
/ip firewall connection tracking
set enabled=yes generic-timeout=10m icmp-timeout=10s liberal-tcp-tracking=no \
    loose-tcp-tracking=yes tcp-close-timeout=10s tcp-close-wait-timeout=10s \
    tcp-established-timeout=1h tcp-fin-wait-timeout=30s tcp-last-ack-timeout=\
    10s tcp-max-retrans-timeout=5m tcp-syn-received-timeout=5s \
    tcp-syn-sent-timeout=5s tcp-time-wait-timeout=10s tcp-unacked-timeout=5m \
    udp-stream-timeout=3m udp-timeout=30s
/ip neighbor discovery-settings
set discover-interface-list=LAN discover-interval=30s lldp-mac-phy-config=no \
    lldp-max-frame-size=no lldp-med-net-policy-vlan=disabled lldp-vlan-info=\
    no mode=tx-and-rx protocol=cdp,lldp,mndp
/ip settings
set accept-redirects=no accept-source-route=no allow-fast-path=no \
    arp-timeout=30s icmp-errors-use-inbound-interface-address=no \
    icmp-rate-limit=10 icmp-rate-mask=0x1818 ip-forward=yes \
    ipv4-multipath-hash-policy=l3 max-neighbor-entries=16384 rp-filter=no \
    secure-redirects=yes send-redirects=yes tcp-syncookies=yes \
    tcp-timestamps=random-offset
/ipv6 settings
set accept-redirects=yes-if-forwarding-disabled accept-router-advertisements=\
    yes-if-forwarding-disabled allow-fast-path=yes disable-ipv6=no \
    disable-link-local-address=no forward=yes max-neighbor-entries=16384 \
    min-neighbor-entries=4096 multipath-hash-policy=l3 \
    soft-max-neighbor-entries=8192 stale-neighbor-detect-interval=30 \
    stale-neighbor-timeout=60
/interface bridge vlan
add bridge=bridge1 comment=Trusted disabled=no mvrp-forbidden="" tagged=\
    bridge1,sfp-10gSwitch untagged="" vlan-ids=110
add bridge=bridge1 comment=IoT disabled=no mvrp-forbidden="" tagged=\
    bridge1,sfp-10gSwitch untagged="" vlan-ids=120
add bridge=bridge1 comment=Camera disabled=no mvrp-forbidden="" tagged=\
    sfp-10gSwitch,bridge1 untagged="" vlan-ids=130
add bridge=bridge1 comment=MGMT disabled=no mvrp-forbidden="" tagged=\
    bridge1,sfp-10gSwitch untagged="ether8-MGMT Port" vlan-ids=99
add bridge=bridge1 disabled=no mvrp-forbidden="" tagged=bridge1,sfp-10gSwitch \
    untagged="" vlan-ids=1
/interface detect-internet
set detect-interface-list=none internet-interface-list=WAN \
    lan-interface-list=VLAN wan-interface-list=WAN
/interface l2tp-server server
set accept-proto-version=all accept-pseudowire-type=all allow-fast-path=no \
    authentication=pap,chap,mschap1,mschap2 caller-id-type=ip-address \
    default-profile=default-encryption enabled=no keepalive-timeout=30 \
    l2tpv3-circuit-id="" l2tpv3-cookie-length=0 l2tpv3-digest-hash=md5 \
    !l2tpv3-ether-interface-list max-mru=1450 max-mtu=1450 max-sessions=\
    unlimited mrru=disabled one-session-per-host=no use-ipsec=no
/interface list member
add disabled=no interface=ether1-WAN-Spectrum list=WAN
add disabled=no interface=bridge1 list=LAN
add disabled=no interface=vlan120-IOT list=VLAN
add disabled=no interface=vlan110-trusted list=VLAN
add disabled=no interface=ether2-WAN-ATT list=WAN
add disabled=no interface=vlan99-mgmt list=VLAN
add disabled=no interface=wireguard1 list=VPN
/interface lte settings
set esim-channel=auto firmware-path=firmware link-recovery-timer=120 mode=\
    auto
/interface ovpn-server server
add auth=sha1,md5 certificate=*0 cipher=blowfish128,aes128-cbc \
    default-profile=default disabled=yes enable-tun-ipv6=no ipv6-prefix-len=\
    64 keepalive-timeout=60 mac-address=FE:C9:92:4E:A4:F6 max-mtu=1500 mode=\
    ip name=ovpn-server1 netmask=24 port=1194 protocol=tcp push-routes="" \
    redirect-gateway=disabled reneg-sec=3600 require-client-certificate=no \
    tls-version=any tun-server-ipv6=:: user-auth-method=pap vrf=main
/interface pptp-server server
# PPTP connections are considered unsafe, it is suggested to use a more modern VPN protocol instead
set authentication=mschap1,mschap2 default-profile=default-encryption \
    enabled=no keepalive-timeout=30 max-mru=1450 max-mtu=1450 mrru=disabled
/interface sstp-server server
set authentication=pap,chap,mschap1,mschap2 certificate=none ciphers=\
    aes256-sha,aes256-gcm-sha384 default-profile=default enabled=no \
    keepalive-timeout=60 max-mru=1500 max-mtu=1500 mrru=disabled pfs=no port=\
    443 tls-version=any verify-client-certificate=no
/interface wifi cap
set enabled=no
/interface wifi capsman
set enabled=no
/interface wireguard peers
add allowed-address=10.255.255.2/32 client-endpoint="" comment=phone \
    disabled=no endpoint-address="" endpoint-port=0 interface=wireguard1 \
    name=peer3 preshared-key="" private-key="" public-key=\
    "o6SaJg4YOUPpvN2C9ugih9boK+zlleywBELqFy7xNTo="
/interface wireless align
set active-mode=yes audio-max=-20 audio-min=-100 audio-monitor=\
    00:00:00:00:00:00 filter-mac=00:00:00:00:00:00 frame-size=300 \
    frames-per-second=25 receive-all=no ssid-all=no
/interface wireless cap
set bridge=none caps-man-addresses="" caps-man-certificate-common-names="" \
    caps-man-names="" certificate=none discovery-interfaces="" enabled=no \
    interfaces="" lock-to-caps-man=no static-virtual=no
/interface wireless sniffer
set channel-time=200ms file-limit=10 file-name="" memory-limit=10 \
    multiple-channels=no only-headers=no receive-errors=no streaming-enabled=\
    no streaming-max-rate=0 streaming-server=0.0.0.0
/interface wireless snooper
set channel-time=200ms multiple-channels=yes receive-errors=no
/ip address
add address=10.10.130.1/24 comment=Camera disabled=no interface=\
    vlan130-camera network=10.10.130.0
add address=10.10.120.1/24 comment=IoT disabled=no interface=vlan120-IOT \
    network=10.10.120.0
add address=10.10.110.1/24 comment=Trusted disabled=no interface=\
    vlan110-trusted network=10.10.110.0
add address=10.255.255.1/24 disabled=no interface=wireguard1 network=\
    10.255.255.0
add address=192.168.2.100/24 disabled=no interface=ether2-WAN-ATT network=\
    192.168.2.0
add address=10.10.99.1/24 comment=MGMT disabled=no interface=vlan99-mgmt \
    network=10.10.99.0
add address=172.17.0.1/24 disabled=no interface=*66 network=172.17.0.0
add address=10.10.250.1/24 disabled=no interface=*69 network=10.10.250.0
/ip cloud
set back-to-home-vpn=revoked-and-disabled ddns-enabled=yes \
    ddns-update-interval=none update-time=yes
/ip cloud advanced
set use-local-address=no
/ip dhcp-client
add add-default-route=no allow-reconfigure=no check-gateway=none \
    default-route-tables=default dhcp-options=hostname,clientid disabled=no \
    interface=ether1-WAN-Spectrum use-broadcast=both use-peer-dns=no \
    use-peer-ntp=no
add add-default-route=no allow-reconfigure=no check-gateway=none \
    default-route-tables=default dhcp-options=hostname,clientid disabled=no \
    interface=ether2-WAN-ATT use-broadcast=both use-peer-dns=no use-peer-ntp=\
    no
/ip dhcp-server
# Interface not running
add address-lists="" address-pool=ap_pool disabled=no interface=*69 \
    lease-script="" lease-time=30m name=ap_recovery_dhcp use-radius=no \
    use-reconfigure=no
/ip dhcp-server config
set accounting=yes interim-update=0s radius-password=empty store-leases-disk=\
    5m
/ip dhcp-server lease
add address=10.10.130.253 address-lists="" !allow-dual-stack-queue client-id=\
    1:ec:71:db:87:f1:4a dhcp-option="" disabled=no !insert-queue-before \
    mac-address=EC:71:DB:87:F1:4A !parent-queue !queue-type server=vlan130
add address=10.10.110.217 address-lists="" !allow-dual-stack-queue client-id=\
    ff:70:9e:3a:1:0:2:0:0:ab:11:3a:32:a3:eb:7a:5f:47:f9 dhcp-option="" \
    disabled=no !insert-queue-before mac-address=86:16:B6:D3:4D:96 \
    !parent-queue !queue-type server=vlan110
add address=10.10.110.225 address-lists="" !allow-dual-stack-queue client-id=\
    1:c0:25:e9:99:f8:86 comment=atlas dhcp-option="" disabled=no \
    !insert-queue-before mac-address=C0:25:E9:99:F8:86 !parent-queue \
    !queue-type server=vlan110
add address=10.10.110.219 address-lists="" !allow-dual-stack-queue client-id=\
    1:0:25:90:f5:a5:7e dhcp-option="" disabled=no !insert-queue-before \
    mac-address=00:25:90:F5:A5:7E !parent-queue !queue-type server=vlan110
add address=10.10.110.216 address-lists="" !allow-dual-stack-queue client-id=\
    ff:65:e8:e:20:0:1:0:1:2b:e1:b4:66:2:a0:20:c8:9a:cc dhcp-option="" \
    disabled=no !insert-queue-before mac-address=0E:AD:65:E8:0E:20 \
    !parent-queue !queue-type server=vlan110
add address=10.10.110.228 address-lists="" !allow-dual-stack-queue client-id=\
    ff:47:41:21:1b:0:1:0:1:2b:c5:52:10:76:de:47:41:21:1b dhcp-option="" \
    disabled=no !insert-queue-before mac-address=76:DE:47:41:21:1B \
    !parent-queue !queue-type server=vlan110
add address=10.10.110.241 address-lists="" !allow-dual-stack-queue client-id=\
    ff:b6:22:f:eb:0:2:0:0:ab:11:1d:8:af:6c:c6:48:51:18 dhcp-option="" \
    disabled=no !insert-queue-before mac-address=94:C6:91:1F:79:05 \
    !parent-queue !queue-type server=vlan110
add address=10.10.110.229 address-lists="" !allow-dual-stack-queue comment=zm \
    dhcp-option="" disabled=no !insert-queue-before mac-address=\
    C2:90:82:7D:2A:4E !parent-queue !queue-type server=vlan110
add address=10.10.120.250 address-lists="" !allow-dual-stack-queue client-id=\
    1:58:d3:49:eb:49:ba comment="Apple TV Livingroom" dhcp-option="" \
    disabled=no !insert-queue-before mac-address=58:D3:49:EB:49:BA \
    !parent-queue !queue-type server=vlan120
add address=10.10.110.202 address-lists="" !allow-dual-stack-queue client-id=\
    1:dc:a6:32:ec:2:ad dhcp-option="" disabled=no !insert-queue-before \
    mac-address=DC:A6:32:EC:02:AD !parent-queue !queue-type server=vlan110
add address=10.10.110.230 address-lists="" !allow-dual-stack-queue client-id=\
    ff:49:72:1f:47:0:2:0:0:ab:11:cc:d:7d:85:41:fb:a2:3d comment=desktop \
    dhcp-option="" disabled=no !insert-queue-before mac-address=\
    80:61:5F:0D:E0:72 !parent-queue !queue-type server=vlan110
add address=10.10.110.243 address-lists="" !allow-dual-stack-queue \
    dhcp-option="" disabled=no !insert-queue-before mac-address=\
    A0:D3:C1:2F:8C:3C !parent-queue !queue-type server=vlan110
add address=10.10.130.252 address-lists="" !allow-dual-stack-queue client-id=\
    1:ec:71:db:e0:30:6b dhcp-option="" disabled=no !insert-queue-before \
    mac-address=EC:71:DB:E0:30:6B !parent-queue !queue-type server=vlan130
add address=10.10.110.211 address-lists="" !allow-dual-stack-queue client-id=\
    1:54:ec:2f:30:52:70 dhcp-option="" disabled=no !insert-queue-before \
    mac-address=54:EC:2F:30:52:70 !parent-queue !queue-type server=vlan110
add address=10.10.130.250 address-lists="" !allow-dual-stack-queue client-id=\
    ff:ca:53:9:5a:0:2:0:0:ab:11:96:af:77:e5:d0:f4:8a:94 dhcp-option="" \
    disabled=no !insert-queue-before mac-address=BC:24:11:87:28:69 \
    !parent-queue !queue-type server=vlan130
add address=10.10.120.248 address-lists="" !allow-dual-stack-queue comment=\
    fusion dhcp-option="" disabled=no !insert-queue-before mac-address=\
    64:52:99:AC:00:48 !parent-queue !queue-type server=vlan120
add address=10.10.120.247 address-lists="" !allow-dual-stack-queue comment=\
    cake-att dhcp-option="" disabled=no !insert-queue-before mac-address=\
    D8:28:C9:39:6C:43 !parent-queue !queue-type server=vlan120
add address=10.10.110.207 address-lists="" !allow-dual-stack-queue client-id=\
    ff:60:65:8f:c8:0:2:0:0:ab:11:cc:35:4d:2f:68:5e:d3:5b comment=Kevin \
    dhcp-option="" disabled=no !insert-queue-before mac-address=\
    60:CF:84:AC:C8:46 !parent-queue !queue-type server=vlan110
add address=10.10.110.208 address-lists="" !allow-dual-stack-queue client-id=\
    ff:11:dd:fc:56:0:1:0:1:2f:82:78:4f:bc:24:11:dd:fc:56 dhcp-option="" \
    disabled=no !insert-queue-before mac-address=BC:24:11:DD:FC:56 \
    !parent-queue !queue-type server=vlan110
add address=10.10.120.246 address-lists="" !allow-dual-stack-queue comment=\
    cake-spectrum dhcp-option="" disabled=no !insert-queue-before \
    mac-address=D8:28:C9:76:46:94 !parent-queue !queue-type server=vlan120
add address=10.10.110.205 address-lists="" !allow-dual-stack-queue client-id=\
    1:66:b7:a3:97:2:76 comment=Kevin dhcp-option="" disabled=no \
    !insert-queue-before mac-address=66:B7:A3:97:02:76 !parent-queue \
    !queue-type server=vlan110
add address=10.10.110.221 address-lists="" !allow-dual-stack-queue client-id=\
    ff:74:9:e9:13:0:2:0:0:ab:11:ff:63:b1:9a:af:70:87:7d dhcp-option="" \
    disabled=no !insert-queue-before mac-address=BC:24:11:5C:6A:01 \
    !parent-queue !queue-type server=vlan110
add address=10.10.110.224 address-lists="" !allow-dual-stack-queue client-id=\
    ff:74:9:e9:13:0:2:0:0:ab:11:ff:26:0:ae:25:b4:cf:70 dhcp-option="" \
    disabled=no !insert-queue-before mac-address=BC:24:11:63:71:C1 \
    !parent-queue !queue-type server=vlan110
add address=10.10.120.203 address-lists="" !allow-dual-stack-queue \
    dhcp-option="" disabled=no !insert-queue-before mac-address=\
    E0:D3:62:A4:5B:EE !parent-queue !queue-type server=vlan120
add address=10.10.120.202 address-lists="" !allow-dual-stack-queue \
    dhcp-option="" disabled=no !insert-queue-before mac-address=\
    98:03:8E:BD:8E:F1 !parent-queue !queue-type server=vlan120
add address=10.10.110.213 address-lists="" !allow-dual-stack-queue client-id=\
    1:80:3:84:33:91:90 comment=ruckus dhcp-option="" disabled=no \
    !insert-queue-before mac-address=80:03:84:33:91:90 !parent-queue \
    !queue-type server=vlan110
add address=10.10.110.218 address-lists="" !allow-dual-stack-queue client-id=\
    1:34:20:e3:22:2d:b0 comment=ruckus dhcp-option="" disabled=no \
    !insert-queue-before mac-address=34:20:E3:22:2D:B0 !parent-queue \
    !queue-type server=vlan110
add address=10.10.110.245 address-lists="" !allow-dual-stack-queue client-id=\
    1:7e:f6:c5:aa:c:67 comment=Kevin dhcp-option="" disabled=no \
    !insert-queue-before mac-address=7E:F6:C5:AA:0C:67 !parent-queue \
    !queue-type server=vlan110
/ip dhcp-server network
add address=10.10.110.0/24 caps-manager="" comment=Trusted dhcp-option=\
    ruckus-tftp dns-server=10.10.110.202,10.10.110.4,10.10.110.214 domain=\
    home.arpa gateway=10.10.110.1 netmask=24 !next-server ntp-server=\
    10.10.110.1 wins-server=""
add address=10.10.120.0/24 caps-manager="" comment=";; IoT" dhcp-option="" \
    dns-server=10.10.110.202,10.10.110.4,10.10.110.214 domain=home.arpa \
    gateway=10.10.120.1 netmask=24 !next-server ntp-server=10.10.110.1 \
    wins-server=""
add address=10.10.130.0/24 caps-manager="" comment=Camera dhcp-option="" \
    dns-server=10.10.110.202,10.10.110.4,10.10.110.214 gateway=10.10.130.1 \
    !next-server ntp-server=10.10.110.1 wins-server=""
add address=10.10.250.0/24 caps-manager="" dhcp-option="" dns-server=\
    10.10.250.1 gateway=10.10.250.1 !next-server ntp-server="" wins-server=""
/ip dns
set address-list-extra-time=0s allow-remote-requests=yes cache-max-ttl=1w \
    cache-size=20480KiB doh-max-concurrent-queries=100 \
    doh-max-server-connections=30 doh-timeout=5s max-concurrent-queries=1000 \
    max-concurrent-tcp-sessions=100 max-udp-packet-size=4096 \
    mdns-repeat-ifaces="" query-server-timeout=2s query-total-timeout=10s \
    servers=10.10.110.202,8.8.8.8,1.1.1.1 use-doh-server="" verify-doh-cert=\
    yes vrf=main
/ip dns adlist
add disabled=no ssl-verify=no url=\
    https://raw.githubusercontent.com/StevenBlack/hosts/master/hosts
/ip dns static
add address=10.10.110.4 disabled=no name=pihole2 ttl=1d type=A
add address=10.10.110.4 disabled=no name=pihole2.lab.zylone.org ttl=1d type=A
add address=10.10.110.209 disabled=no name=asus ttl=1d type=A
add address=10.10.110.232 disabled=no name=atlas ttl=1d type=A
add address=10.10.110.203 disabled=no name=unifi ttl=1d type=A
add address=10.10.110.125 disabled=no name=thor ttl=1d type=A
add address=10.10.110.126 disabled=no name=slayer ttl=1d type=A
add address=10.10.110.126 disabled=no name=slayer.lab.zylone.org ttl=1d type=\
    A
add address=10.10.110.125 disabled=no name=thor.lab.zylone.org ttl=1d type=A
add address=10.10.130.254 disabled=no name=cam-dw ttl=1d type=A
add address=10.10.130.254 disabled=no name=cam-dw.lab.zylone.org ttl=1d type=\
    A
add address=10.10.130.253 disabled=no name=cam-fd ttl=1d type=A
add address=10.10.130.253 disabled=no name=cam-fd.lab.zylone.org ttl=1d type=\
    A
add address=10.10.110.1 disabled=no name=router.lab.zylone.org ttl=1d type=A
add address=10.10.110.1 disabled=no name=router ttl=1d type=A
add address=10.10.110.11 disabled=no name=kitchen ttl=1d type=A
add address=10.10.110.11 disabled=no name=kitchen.lab.zylone.org ttl=1d type=\
    A
add address=10.10.100.2 disabled=no name=switch ttl=1d type=A
add address=10.10.100.2 disabled=no name=switch.lab.zylone.org ttl=1d type=A
add address=10.10.110.204 disabled=no name=loki.lab.zylone.org ttl=1d type=A
add address=10.10.110.204 disabled=no name=loki ttl=1d type=A
add address=10.10.110.100 disabled=no name=bbs.lab.zylone.org ttl=1d type=A
add address=10.10.110.100 disabled=no name=bbs ttl=1d type=A
add address=10.10.110.206 disabled=no name=debian.lab.zylone.org ttl=1d type=\
    A
add address=10.10.110.206 disabled=no name=debian ttl=1d type=A
add address=10.10.110.203 disabled=no name=unifi.lab.zylone.org ttl=1d type=A
add address=10.10.110.212 disabled=no name=Living-Room-10.lab.zylone.org ttl=\
    1d type=A
add address=10.10.110.212 disabled=no name=Living-Room-10 ttl=1d type=A
add address=10.10.110.222 disabled=no name=Office.lab.zylone.org ttl=1d type=\
    A
add address=10.10.110.222 disabled=no name=Office ttl=1d type=A
add address=10.10.110.200 disabled=no name=librenms ttl=1d type=A
add address=10.10.110.200 disabled=no name=librenms.lab.zylone.org ttl=1d \
    type=A
add address=10.10.110.217 disabled=no name=heimdall.lab.zylone.org ttl=1d \
    type=A
add address=10.10.110.217 disabled=no name=heimdall ttl=1d type=A
add address=10.10.110.229 disabled=no name=zm ttl=1d type=A
add address=10.10.110.229 disabled=no name=zm.lab.zylone.org ttl=1d type=A
add address=10.10.110.214 disabled=no name=pihole ttl=1d type=A
add address=10.10.110.214 disabled=no name=pihole.lab.zylone.org ttl=1d type=\
    A
add address=10.10.110.224 disabled=no name=rust.lab.zylone.org ttl=1d type=A
add address=10.10.110.224 disabled=no name=rust ttl=1d type=A
add address=10.10.110.212 comment=dhcp-lease-script_vlan110_lease-hostname \
    disabled=no name=KevinsMacStudio.home.arpa ttl=15m type=A
add address=10.10.110.212 comment=dhcp-lease-script_vlan110_lease-hostname \
    disabled=no name=KevinsMacStudio ttl=15m type=A
add address=10.10.110.246 comment=dhcp-lease-script_vlan110_lease-hostname \
    disabled=no name=cake-spectrum.home.arpa ttl=15m type=A
add address=10.10.110.246 comment=dhcp-lease-script_vlan110_lease-hostname \
    disabled=no name=cake-spectrum ttl=15m type=A
add address=10.10.110.247 comment=dhcp-lease-script_vlan110_lease-hostname \
    disabled=no name=cake-att.home.arpa ttl=15m type=A
add address=10.10.110.247 comment=dhcp-lease-script_vlan110_lease-hostname \
    disabled=no name=cake-att ttl=15m type=A
add address=10.10.110.245 comment=dhcp-lease-script_vlan110_lease-hostname \
    disabled=no name=iPhone.home.arpa ttl=15m type=A
add address=10.10.110.245 comment=dhcp-lease-script_vlan110_lease-hostname \
    disabled=no name=iPhone ttl=15m type=A
add address=10.10.110.203 comment=dhcp-lease-script_vlan110_lease-hostname \
    disabled=no name=LivingRoom1440.home.arpa ttl=15m type=A
add address=10.10.110.203 comment=dhcp-lease-script_vlan110_lease-hostname \
    disabled=no name=LivingRoom1440 ttl=15m type=A
add address=10.10.110.205 comment=dhcp-lease-script_vlan110_lease-hostname \
    disabled=no name=MacBookPro.home.arpa ttl=15m type=A
add address=10.10.110.205 comment=dhcp-lease-script_vlan110_lease-hostname \
    disabled=no name=MacBookPro ttl=15m type=A
add address=10.10.110.221 comment=dhcp-lease-script_vlan110_lease-hostname \
    disabled=no name=ai-ubuntu.home.arpa ttl=15m type=A
add address=10.10.110.240 comment=dhcp-lease-script_vlan110_lease-hostname \
    disabled=no name=bloatslayer.home.arpa ttl=15m type=A
add address=10.10.110.221 comment=dhcp-lease-script_vlan110_lease-hostname \
    disabled=no name=ai-ubuntu ttl=15m type=A
add address=10.10.110.240 comment=dhcp-lease-script_vlan110_lease-hostname \
    disabled=no name=bloatslayer ttl=15m type=A
add address=10.10.110.224 comment=dhcp-lease-script_vlan110_lease-hostname \
    disabled=no name=media.home.arpa ttl=15m type=A
add address=10.10.110.224 comment=dhcp-lease-script_vlan110_lease-hostname \
    disabled=no name=media ttl=15m type=A
add address=10.10.110.228 comment=dhcp-lease-script_vlan110_lease-hostname \
    disabled=no name=wikijs.home.arpa ttl=15m type=A
add address=10.10.110.228 comment=dhcp-lease-script_vlan110_lease-hostname \
    disabled=no name=wikijs ttl=15m type=A
add address=10.10.110.208 comment=dhcp-lease-script_vlan110_lease-hostname \
    disabled=no name=docker.home.arpa ttl=15m type=A
add address=10.10.110.208 comment=dhcp-lease-script_vlan110_lease-hostname \
    disabled=no name=docker ttl=15m type=A
add address=10.10.110.215 comment=dhcp-lease-script_vlan110_lease-hostname \
    disabled=no name=laptop.home.arpa ttl=15m type=A
add address=10.10.110.215 comment=dhcp-lease-script_vlan110_lease-hostname \
    disabled=no name=laptop ttl=15m type=A
/ip firewall address-list
add address=0.0.0.0/8 comment="defconf: RFC6890" disabled=no dynamic=no list=\
    not_global_ipv4
add address=10.0.0.0/8 comment="defconf: RFC6890" disabled=no dynamic=no \
    list=not_global_ipv4
add address=100.64.0.0/10 comment="defconf: RFC6890" disabled=no dynamic=no \
    list=not_global_ipv4
add address=169.254.0.0/16 comment="defconf: RFC6890" disabled=no dynamic=no \
    list=not_global_ipv4
add address=172.16.0.0/12 comment="defconf: RFC6890" disabled=no dynamic=no \
    list=not_global_ipv4
add address=192.0.0.0/29 comment="defconf: RFC6890" disabled=no dynamic=no \
    list=not_global_ipv4
add address=192.168.0.0/16 comment="defconf: RFC6890" disabled=no dynamic=no \
    list=not_global_ipv4
add address=198.18.0.0/15 comment="defconf: RFC6890 benchmark" disabled=no \
    dynamic=no list=not_global_ipv4
add address=255.255.255.255 comment="defconf: RFC6890" disabled=no dynamic=no \
    list=not_global_ipv4
add address=10.10.110.202 comment="DNS servers" disabled=no dynamic=no list=\
    pihole
add address=10.10.110.4 comment="DNS servers" disabled=no dynamic=no list=\
    pihole
add address=176.56.236.175 disabled=no dynamic=no list=dohdns-blacklist
add address=168.235.81.167 disabled=no dynamic=no list=dohdns-blacklist
add address=176.103.130.130 disabled=no dynamic=no list=dohdns-blacklist
add address=176.103.130.131 disabled=no dynamic=no list=dohdns-blacklist
add address=51.15.124.208 disabled=no dynamic=no list=dohdns-blacklist
add address=104.168.247.138 disabled=no dynamic=no list=dohdns-blacklist
add address=45.153.187.96 disabled=no dynamic=no list=dohdns-blacklist
add address=223.5.5.5 disabled=no dynamic=no list=dohdns-blacklist
add address=223.6.6.6 disabled=no dynamic=no list=dohdns-blacklist
add address=217.169.20.22 disabled=no dynamic=no list=dohdns-blacklist
add address=217.169.20.23 disabled=no dynamic=no list=dohdns-blacklist
add address=206.189.142.179 disabled=no dynamic=no list=dohdns-blacklist
add address=185.216.27.142 disabled=no dynamic=no list=dohdns-blacklist
add address=13.89.120.251 disabled=no dynamic=no list=dohdns-blacklist
add address=40.76.112.230 disabled=no dynamic=no list=dohdns-blacklist
add address=95.216.212.177 disabled=no dynamic=no list=dohdns-blacklist
add address=45.32.55.94 disabled=no dynamic=no list=dohdns-blacklist
add address=159.69.198.101 disabled=no dynamic=no list=dohdns-blacklist
add address=139.180.141.57 disabled=no dynamic=no list=dohdns-blacklist
add address=134.209.146.16 disabled=no dynamic=no list=dohdns-blacklist
add address=139.59.48.222 disabled=no dynamic=no list=dohdns-blacklist
add address=149.112.121.10 disabled=no dynamic=no list=dohdns-blacklist
add address=149.112.122.10 disabled=no dynamic=no list=dohdns-blacklist
add address=149.112.121.20 disabled=no dynamic=no list=dohdns-blacklist
add address=149.112.122.20 disabled=no dynamic=no list=dohdns-blacklist
add address=149.112.122.30 disabled=no dynamic=no list=dohdns-blacklist
add address=149.112.121.30 disabled=no dynamic=no list=dohdns-blacklist
add address=185.228.168.168 disabled=no dynamic=no list=dohdns-blacklist
add address=185.228.168.10 disabled=no dynamic=no list=dohdns-blacklist
add address=185.228.168.9 disabled=no dynamic=no list=dohdns-blacklist
add address=1.1.1.1 disabled=no dynamic=no list=dohdns-blacklist
add address=1.0.0.1 disabled=no dynamic=no list=dohdns-blacklist
add address=1.1.1.2 disabled=no dynamic=no list=dohdns-blacklist
add address=1.0.0.2 disabled=no dynamic=no list=dohdns-blacklist
add address=1.1.1.3 disabled=no dynamic=no list=dohdns-blacklist
add address=1.0.0.3 disabled=no dynamic=no list=dohdns-blacklist
add address=104.16.248.249 disabled=no dynamic=no list=dohdns-blacklist
add address=104.16.249.249 disabled=no dynamic=no list=dohdns-blacklist
add address=104.17.64.4 disabled=no dynamic=no list=dohdns-blacklist
add address=104.17.65.4 disabled=no dynamic=no list=dohdns-blacklist
add address=104.18.2.55 disabled=no dynamic=no list=dohdns-blacklist
add address=104.18.3.55 disabled=no dynamic=no list=dohdns-blacklist
add address=104.18.27.128 disabled=no dynamic=no list=dohdns-blacklist
add address=104.18.26.128 disabled=no dynamic=no list=dohdns-blacklist
add address=96.113.151.149 disabled=no dynamic=no list=dohdns-blacklist
add address=8.26.56.26 disabled=no dynamic=no list=dohdns-blacklist
add address=8.20.247.20 disabled=no dynamic=no list=dohdns-blacklist
add address=178.79.156.39 disabled=no dynamic=no list=dohdns-blacklist
add address=139.162.131.245 disabled=no dynamic=no list=dohdns-blacklist
add address=45.77.180.10 disabled=no dynamic=no list=dohdns-blacklist
add address=174.68.248.77 disabled=no dynamic=no list=dohdns-blacklist
add address=104.28.1.106 disabled=no dynamic=no list=dohdns-blacklist
add address=104.28.0.106 disabled=no dynamic=no list=dohdns-blacklist
add address=185.95.218.43 disabled=no dynamic=no list=dohdns-blacklist
add address=185.95.218.42 disabled=no dynamic=no list=dohdns-blacklist
add address=35.231.247.227 disabled=no dynamic=no list=dohdns-blacklist
add address=5.45.107.88 disabled=no dynamic=no list=dohdns-blacklist
add address=172.64.105.36 disabled=no dynamic=no list=dohdns-blacklist
add address=172.64.104.36 disabled=no dynamic=no list=dohdns-blacklist
add address=46.101.66.244 disabled=no dynamic=no list=dohdns-blacklist
add address=146.148.56.78 disabled=no dynamic=no list=dohdns-blacklist
add address=185.157.233.92 disabled=no dynamic=no list=dohdns-blacklist
add address=167.114.220.125 disabled=no dynamic=no list=dohdns-blacklist
add address=149.56.228.45 disabled=no dynamic=no list=dohdns-blacklist
add address=185.233.106.232 disabled=no dynamic=no list=dohdns-blacklist
add address=185.233.107.4 disabled=no dynamic=no list=dohdns-blacklist
add address=185.235.81.1 disabled=no dynamic=no list=dohdns-blacklist
add address=185.235.81.2 disabled=no dynamic=no list=dohdns-blacklist
add address=185.235.81.3 disabled=no dynamic=no list=dohdns-blacklist
add address=185.235.81.4 disabled=no dynamic=no list=dohdns-blacklist
add address=185.235.81.5 disabled=no dynamic=no list=dohdns-blacklist
add address=185.235.81.6 disabled=no dynamic=no list=dohdns-blacklist
add address=173.245.58.126 disabled=no dynamic=no list=dohdns-blacklist
add address=45.76.113.31 disabled=no dynamic=no list=dohdns-blacklist
add address=139.99.222.72 disabled=no dynamic=no list=dohdns-blacklist
add address=88.198.161.8 disabled=no dynamic=no list=dohdns-blacklist
add address=116.203.35.255 disabled=no dynamic=no list=dohdns-blacklist
add address=116.203.70.156 disabled=no dynamic=no list=dohdns-blacklist
add address=104.31.90.138 disabled=no dynamic=no list=dohdns-blacklist
add address=104.31.91.138 disabled=no dynamic=no list=dohdns-blacklist
add address=94.130.224.114 disabled=no dynamic=no list=dohdns-blacklist
add address=164.132.45.112 disabled=no dynamic=no list=dohdns-blacklist
add address=51.89.22.36 disabled=no dynamic=no list=dohdns-blacklist
add address=46.239.223.80 disabled=no dynamic=no list=dohdns-blacklist
add address=176.9.93.198 disabled=no dynamic=no list=dohdns-blacklist
add address=176.9.1.117 disabled=no dynamic=no list=dohdns-blacklist
add address=198.251.90.114 disabled=no dynamic=no list=dohdns-blacklist
add address=198.251.90.89 disabled=no dynamic=no list=dohdns-blacklist
add address=209.141.34.95 disabled=no dynamic=no list=dohdns-blacklist
add address=199.195.251.84 disabled=no dynamic=no list=dohdns-blacklist
add address=104.244.78.231 disabled=no dynamic=no list=dohdns-blacklist
add address=51.38.82.198 disabled=no dynamic=no list=dohdns-blacklist
add address=80.156.145.201 disabled=no dynamic=no list=dohdns-blacklist
add address=210.17.9.228 disabled=no dynamic=no list=dohdns-blacklist
add address=216.146.35.35 disabled=no dynamic=no list=dohdns-blacklist
add address=216.146.36.36 disabled=no dynamic=no list=dohdns-blacklist
add address=195.30.94.28 disabled=no dynamic=no list=dohdns-blacklist
add address=93.177.65.183 disabled=no dynamic=no list=dohdns-blacklist
add address=104.27.164.27 disabled=no dynamic=no list=dohdns-blacklist
add address=104.27.165.27 disabled=no dynamic=no list=dohdns-blacklist
add address=125.77.154.35 disabled=no dynamic=no list=dohdns-blacklist
add address=118.24.208.197 disabled=no dynamic=no list=dohdns-blacklist
add address=114.115.240.175 disabled=no dynamic=no list=dohdns-blacklist
add address=119.29.107.85 disabled=no dynamic=no list=dohdns-blacklist
add address=172.105.241.93 disabled=no dynamic=no list=dohdns-blacklist
add address=139.162.3.123 disabled=no dynamic=no list=dohdns-blacklist
add address=8.8.4.4 disabled=no dynamic=no list=dohdns-blacklist
add address=8.8.8.8 disabled=no dynamic=no list=dohdns-blacklist
add address=216.239.32.10 disabled=no dynamic=no list=dohdns-blacklist
add address=185.26.126.37 disabled=no dynamic=no list=dohdns-blacklist
add address=35.198.2.76 disabled=no dynamic=no list=dohdns-blacklist
add address=83.77.85.7 disabled=no dynamic=no list=dohdns-blacklist
add address=178.62.214.105 disabled=no dynamic=no list=dohdns-blacklist
add address=104.28.28.34 disabled=no dynamic=no list=dohdns-blacklist
add address=104.28.29.34 disabled=no dynamic=no list=dohdns-blacklist
add address=51.158.147.50 disabled=no dynamic=no list=dohdns-blacklist
add address=116.202.176.26 disabled=no dynamic=no list=dohdns-blacklist
add address=116.203.115.192 disabled=no dynamic=no list=dohdns-blacklist
add address=139.59.55.13 disabled=no dynamic=no list=dohdns-blacklist
add address=104.24.122.53 disabled=no dynamic=no list=dohdns-blacklist
add address=104.24.123.53 disabled=no dynamic=no list=dohdns-blacklist
add address=45.90.28.0 disabled=no dynamic=no list=dohdns-blacklist
add address=192.36.27.86 disabled=no dynamic=no list=dohdns-blacklist
add address=188.172.192.71 disabled=no dynamic=no list=dohdns-blacklist
add address=146.112.41.2 disabled=no dynamic=no list=dohdns-blacklist
add address=146.112.41.3 disabled=no dynamic=no list=dohdns-blacklist
add address=208.67.222.222 disabled=no dynamic=no list=dohdns-blacklist
add address=208.67.220.220 disabled=no dynamic=no list=dohdns-blacklist
add address=208.67.222.123 disabled=no dynamic=no list=dohdns-blacklist
add address=208.67.220.123 disabled=no dynamic=no list=dohdns-blacklist
add address=74.82.42.42 disabled=no dynamic=no list=dohdns-blacklist
add address=51.38.83.141 disabled=no dynamic=no list=dohdns-blacklist
add address=31.220.42.65 disabled=no dynamic=no list=dohdns-blacklist
add address=45.67.219.208 disabled=no dynamic=no list=dohdns-blacklist
add address=88.198.91.187 disabled=no dynamic=no list=dohdns-blacklist
add address=95.216.181.228 disabled=no dynamic=no list=dohdns-blacklist
add address=185.213.26.187 disabled=no dynamic=no list=dohdns-blacklist
add address=136.144.215.158 disabled=no dynamic=no list=dohdns-blacklist
add address=103.2.57.5 disabled=no dynamic=no list=dohdns-blacklist
add address=103.2.57.6 disabled=no dynamic=no list=dohdns-blacklist
add address=9.9.9.9 disabled=no dynamic=no list=dohdns-blacklist
add address=9.9.9.10 disabled=no dynamic=no list=dohdns-blacklist
add address=9.9.9.11 disabled=no dynamic=no list=dohdns-blacklist
add address=149.112.112.112 disabled=no dynamic=no list=dohdns-blacklist
add address=149.112.112.9 disabled=no dynamic=no list=dohdns-blacklist
add address=149.112.112.10 disabled=no dynamic=no list=dohdns-blacklist
add address=149.112.112.11 disabled=no dynamic=no list=dohdns-blacklist
add address=10.10.110.214 comment="DNS servers" disabled=no dynamic=no list=\
    pihole
add address=10.10.110.230 comment=desktop disabled=no dynamic=no list=\
    "Network Admins"
add address=10.10.110.205 comment=laptop disabled=no dynamic=no list=\
    "Network Admins"
add address=10.255.255.2 comment=wireguard_roaming disabled=no dynamic=no \
    list=machines_to_all_vlan
add address=10.10.110.203 comment=Phone disabled=no dynamic=no list=\
    "Network Admins"
add address=10.10.110.207 comment=Behemoth disabled=no dynamic=no list=\
    "Network Admins"
add address=45.121.184.0/24 comment="Valve Network Range" disabled=no \
    dynamic=no list="Valve Network"
add address=103.10.124.0/24 comment="Valve Network Range" disabled=no \
    dynamic=no list="Valve Network"
add address=103.10.125.0/24 comment="Valve Network Range" disabled=no \
    dynamic=no list="Valve Network"
add address=103.28.54.0/24 comment="Valve Network Range" disabled=no dynamic=\
    no list="Valve Network"
add address=146.66.152.0/24 comment="Valve Network Range" disabled=no \
    dynamic=no list="Valve Network"
add address=146.66.155.0/24 comment="Valve Network Range" disabled=no \
    dynamic=no list="Valve Network"
add address=155.133.226.0/24 comment="Valve Network Range" disabled=no \
    dynamic=no list="Valve Network"
add address=155.133.227.0/24 comment="Valve Network Range" disabled=no \
    dynamic=no list="Valve Network"
add address=155.133.230.0/24 comment="Valve Network Range" disabled=no \
    dynamic=no list="Valve Network"
add address=155.133.238.0/24 comment="Valve Network Range" disabled=no \
    dynamic=no list="Valve Network"
add address=155.133.244.0/24 comment="Valve Network Range" disabled=no \
    dynamic=no list="Valve Network"
add address=155.133.246.0/24 comment="Valve Network Range" disabled=no \
    dynamic=no list="Valve Network"
add address=155.133.248.0/24 comment="Valve Network Range" disabled=no \
    dynamic=no list="Valve Network"
add address=155.133.250.0/24 comment="Valve Network Range" disabled=no \
    dynamic=no list="Valve Network"
add address=155.133.252.0/24 comment="Valve Network Range" disabled=no \
    dynamic=no list="Valve Network"
add address=155.133.254.0/24 comment="Valve Network Range" disabled=no \
    dynamic=no list="Valve Network"
add address=162.254.192.0/24 comment="Valve Network Range" disabled=no \
    dynamic=no list="Valve Network"
add address=162.254.193.0/24 comment="Valve Network Range" disabled=no \
    dynamic=no list="Valve Network"
add address=162.254.194.0/24 comment="Valve Network Range" disabled=no \
    dynamic=no list="Valve Network"
add address=162.254.195.0/24 comment="Valve Network Range" disabled=no \
    dynamic=no list="Valve Network"
add address=162.254.196.0/24 comment="Valve Network Range" disabled=no \
    dynamic=no list="Valve Network"
add address=162.254.197.0/24 comment="Valve Network Range" disabled=no \
    dynamic=no list="Valve Network"
add address=162.254.198.0/24 comment="Valve Network Range" disabled=no \
    dynamic=no list="Valve Network"
add address=162.254.199.0/24 comment="Valve Network Range" disabled=no \
    dynamic=no list="Valve Network"
add address=185.25.182.0/24 comment="Valve Network Range" disabled=no \
    dynamic=no list="Valve Network"
add address=185.25.183.0/24 comment="Valve Network Range" disabled=no \
    dynamic=no list="Valve Network"
add address=192.69.96.0/22 comment="Valve Network Range" disabled=no dynamic=\
    no list="Valve Network"
add address=205.196.6.0/24 comment="Valve Network Range" disabled=no dynamic=\
    no list="Valve Network"
add address=208.64.200.0/24 comment="Valve Network Range" disabled=no \
    dynamic=no list="Valve Network"
add address=208.64.201.0/24 comment="Valve Network Range" disabled=no \
    dynamic=no list="Valve Network"
add address=208.64.202.0/24 comment="Valve Network Range" disabled=no \
    dynamic=no list="Valve Network"
add address=208.64.203.0/24 comment="Valve Network Range" disabled=no \
    dynamic=no list="Valve Network"
add address=172.26.0.0/16 disabled=no dynamic=no list=\
    icsolutions_vpn_networks
add address=10.252.0.0/16 disabled=no dynamic=no list=\
    icsolutions_vpn_networks
add address=10.253.0.0/16 disabled=no dynamic=no list=\
    icsolutions_vpn_networks
add address=172.20.0.0/16 disabled=no dynamic=no list=\
    icsolutions_vpn_networks
add address=172.19.16.0/24 disabled=no dynamic=no list=\
    icsolutions_vpn_networks
add address=10.153.0.0/16 disabled=no dynamic=no list=\
    icsolutions_vpn_networks
add address=172.31.0.0/24 comment="ICS VPN Networks" disabled=no dynamic=no \
    list=icsolutions_vpn_networks
add address=10.10.110.202 disabled=no dynamic=no list="Network Admins"
add address=107.122.31.0/24 comment="AT&T WiFi Calling EPDG Subnet" disabled=\
    no dynamic=no list=ATT-WiFiCalling
add address=166.216.0.0/16 comment="AT&T Mobile Services" disabled=no \
    dynamic=no list=ATT-WiFiCalling
add address=166.137.0.0/16 comment="AT&T Mobile Services" disabled=no \
    dynamic=no list=ATT-WiFiCalling
add address=0.0.0.0/8 comment="RFC1122 - This Network" disabled=no dynamic=no \
    list=bogons
add address=127.0.0.0/8 comment="RFC1122 - Loopback" disabled=no dynamic=no \
    list=bogons
add address=169.254.0.0/16 comment="RFC3927 - Link Local" disabled=no \
    dynamic=no list=bogons
add address=224.0.0.0/4 comment="RFC5771 - Multicast" disabled=no dynamic=no \
    list=bogons
add address=240.0.0.0/4 comment="RFC6890 - Reserved" disabled=no dynamic=no \
    list=bogons
add address=192.0.2.0/24 comment="RFC5737 - TEST-NET-1" disabled=no dynamic=\
    no list=bogons
add address=198.51.100.0/24 comment="RFC5737 - TEST-NET-2" disabled=no \
    dynamic=no list=bogons
add address=203.0.113.0/24 comment="RFC5737 - TEST-NET-3" disabled=no \
    dynamic=no list=bogons
add address=63.145.117.221 comment="Work VPN server" disabled=no dynamic=no \
    list=Work-VPN
add address=1.178.0.0/23 comment=US disabled=no dynamic=no list=\
    allowed-countries
add address=1.178.4.0/22 comment=US disabled=no dynamic=no list=\
    allowed-countries
add address=1.178.8.0/21 comment=US disabled=no dynamic=no list=\
    allowed-countries
add address=1.178.16.0/20 comment=US disabled=no dynamic=no list=\
    allowed-countries
add address=1.178.64.0/23 comment=US disabled=no dynamic=no list=\
    allowed-countries
add address=1.178.68.0/22 comment=US disabled=no dynamic=no list=\
    allowed-countries
add address=1.178.72.0/21 comment=US disabled=no dynamic=no list=\
    allowed-countries
add address=1.178.81.0/24 comment=US disabled=no dynamic=no list=\
    allowed-countries
add address=1.178.86.0/23 comment=US disabled=no dynamic=no list=\
    allowed-countries
add address=1.178.88.0/21 comment=US disabled=no dynamic=no list=\
    allowed-countries
add address=1.178.100.0/22 comment=US disabled=no dynamic=no list=\
    allowed-countries
add address=1.178.104.0/21 comment=US disabled=no dynamic=no list=\
    allowed-countries
add address=1.178.144.0/20 comment=US disabled=no dynamic=no list=\
    allowed-countries
add address=1.178.160.0/21 comment=US disabled=no dynamic=no list=\
    allowed-countries
add address=1.178.168.0/22 comment=US disabled=no dynamic=no list=\
    allowed-countries
add address=1.178.172.0/23 comment=US disabled=no dynamic=no list=\
    allowed-countries
add address=1.178.174.0/24 comment=US disabled=no dynamic=no list=\
    allowed-countries
add address=1.178.180.0/22 comment=US disabled=no dynamic=no list=\
    allowed-countries
add address=1.178.184.0/21 comment=US disabled=no dynamic=no list=\
    allowed-countries
add address=1.178.192.0/20 comment=US disabled=no dynamic=no list=\
    allowed-countries
add address=1.179.2.0/23 comment=US disabled=no dynamic=no list=\
    allowed-countries
add address=1.179.14.0/23 comment=US disabled=no dynamic=no list=\
    allowed-countries
add address=1.179.24.0/21 comment=US disabled=no dynamic=no list=\
    allowed-countries
add address=1.179.32.0/21 comment=US disabled=no dynamic=no list=\
    allowed-countries
add address=1.179.52.0/22 comment=US disabled=no dynamic=no list=\
    allowed-countries
add address=1.179.56.0/22 comment=US disabled=no dynamic=no list=\
    allowed-countries
add address=1.179.60.0/23 comment=US disabled=no dynamic=no list=\
    allowed-countries
add address=1.179.64.0/21 comment=US disabled=no dynamic=no list=\
    allowed-countries
add address=1.179.80.0/21 comment=US disabled=no dynamic=no list=\
    allowed-countries
add address=1.179.100.0/22 comment=US disabled=no dynamic=no list=\
    allowed-countries
add address=1.179.104.0/21 comment=US disabled=no dynamic=no list=\
    allowed-countries
add address=2.56.8.0/23 comment=US disabled=no dynamic=no list=\
    allowed-countries
add address=2.56.11.0/24 comment=US disabled=no dynamic=no list=\
    allowed-countries
add address=2.56.32.0/22 comment=US disabled=no dynamic=no list=\
    allowed-countries
add address=2.56.164.0/22 comment=US disabled=no dynamic=no list=\
    allowed-countries
add address=2.57.28.0/22 comment=US disabled=no dynamic=no list=\
    allowed-countries
add address=2.57.68.0/22 comment=US disabled=no dynamic=no list=\
    allowed-countries
add address=2.57.76.0/22 comment=US disabled=no dynamic=no list=\
    allowed-countries
add address=2.57.164.0/22 comment=US disabled=no dynamic=no list=\
    allowed-countries
add address=2.57.232.0/22 comment=US disabled=no dynamic=no list=\
    allowed-countries
add address=2.57.248.0/22 comment=US disabled=no dynamic=no list=\
    allowed-countries
add address=2.58.176.0/22 comment=US disabled=no dynamic=no list=\
    allowed-countries
add address=2.58.252.0/22 comment=US disabled=no dynamic=no list=\
    allowed-countries
add address=2.59.8.0/23 comment=US disabled=no dynamic=no list=\
    allowed-countries
add address=2.59.14.0/24 comment=US disabled=no dynamic=no list=\
    allowed-countries
add address=3.0.0.0/8 comment=US disabled=no dynamic=no list=\
    allowed-countries
add address=4.0.0.0/8 comment=US disabled=no dynamic=no list=\
    allowed-countries
add address=5.8.251.0/24 comment=US disabled=no dynamic=no list=\
    allowed-countries
add address=5.10.232.0/21 comment=US disabled=no dynamic=no list=\
    allowed-countries
add address=5.22.155.0/24 comment=US disabled=no dynamic=no list=\
    allowed-countries
add address=5.34.176.0/21 comment=US disabled=no dynamic=no list=\
    allowed-countries
add address=5.35.192.0/21 comment=US disabled=no dynamic=no list=\
    allowed-countries
add address=5.42.160.0/19 comment=US disabled=no dynamic=no list=\
    allowed-countries
add address=5.42.198.0/24 comment=US disabled=no dynamic=no list=\
    allowed-countries
add address=5.42.203.0/24 comment=US disabled=no dynamic=no list=\
    allowed-countries
add address=5.44.255.0/24 comment=US disabled=no dynamic=no list=\
    allowed-countries
add address=5.60.0.0/16 comment=US disabled=no dynamic=no list=\
    allowed-countries
add address=5.62.152.0/21 comment=US disabled=no dynamic=no list=\
    allowed-countries
add address=5.63.144.0/21 comment=US disabled=no dynamic=no list=\
    allowed-countries
add address=5.100.152.0/21 comment=US disabled=no dynamic=no list=\
    allowed-countries
add address=5.101.96.0/20 comment=US disabled=no dynamic=no list=\
    allowed-countries
add address=5.104.64.0/21 comment=US disabled=no dynamic=no list=\
    allowed-countries
add address=5.104.72.0/22 comment=US disabled=no dynamic=no list=\
    allowed-countries
add address=5.145.180.0/22 comment=US disabled=no dynamic=no list=\
    allowed-countries
add address=5.149.120.0/21 comment=US disabled=no dynamic=no list=\
    allowed-countries
add address=5.150.156.0/22 comment=US disabled=no dynamic=no list=\
    allowed-countries
add address=5.154.240.0/24 comment=US disabled=no dynamic=no list=\
    allowed-countries
add address=5.174.0.0/16 comment=US disabled=no dynamic=no list=\
    allowed-countries
add address=5.179.96.0/20 comment=US disabled=no dynamic=no list=\
    allowed-countries
add address=5.180.76.0/22 comment=US disabled=no dynamic=no list=\
    allowed-countries
add address=5.181.180.0/22 comment=US disabled=no dynamic=no list=\
    allowed-countries
add address=5.182.48.0/22 comment=US disabled=no dynamic=no list=\
    allowed-countries
add address=5.182.100.0/22 comment=US disabled=no dynamic=no list=\
    allowed-countries
add address=5.182.120.0/22 comment=US disabled=no dynamic=no list=\
    allowed-countries
add address=5.182.184.0/22 comment=US disabled=no dynamic=no list=\
    allowed-countries
add address=5.182.192.0/21 comment=US disabled=no dynamic=no list=\
    allowed-countries
add address=5.183.76.0/23 comment=US disabled=no dynamic=no list=\
    allowed-countries
add address=5.183.78.0/24 comment=US disabled=no dynamic=no list=\
    allowed-countries
add address=5.183.88.0/22 comment=US disabled=no dynamic=no list=\
    allowed-countries
add address=5.183.100.0/22 comment=US disabled=no dynamic=no list=\
    allowed-countries
add address=5.183.240.0/22 comment=US disabled=no dynamic=no list=\
    allowed-countries
add address=5.253.84.0/22 comment=US disabled=no dynamic=no list=\
    allowed-countries
add address=5.253.184.0/22 comment=US disabled=no dynamic=no list=\
    allowed-countries
add address=6.0.0.0/7 comment=US disabled=no dynamic=no list=\
    allowed-countries
add address=8.0.0.0/9 comment=US disabled=no dynamic=no list=\
    allowed-countries
add address=8.192.0.0/12 comment=US disabled=no dynamic=no list=\
    allowed-countries
add address=8.224.0.0/11 comment=US disabled=no dynamic=no list=\
    allowed-countries
add address=9.0.0.0/9 comment=US disabled=no dynamic=no list=\
    allowed-countries
add address=9.128.0.0/16 comment=US disabled=no dynamic=no list=\
    allowed-countries
add address=9.134.0.0/16 comment=US disabled=no dynamic=no list=\
    allowed-countries
add address=9.137.0.0/16 comment=US disabled=no dynamic=no list=\
    allowed-countries
add address=9.138.0.0/15 comment=US disabled=no dynamic=no list=\
    allowed-countries
add address=9.142.0.0/16 comment=US disabled=no dynamic=no list=\
    allowed-countries
add address=9.144.0.0/16 comment=US disabled=no dynamic=no list=\
    allowed-countries
add address=9.147.0.0/16 comment=US disabled=no dynamic=no list=\
    allowed-countries
add address=9.148.0.0/16 comment=US disabled=no dynamic=no list=\
    allowed-countries
add address=9.150.0.0/15 comment=US disabled=no dynamic=no list=\
    allowed-countries
add address=9.152.0.0/15 comment=US disabled=no dynamic=no list=\
    allowed-countries
add address=9.155.0.0/16 comment=US disabled=no dynamic=no list=\
    allowed-countries
add address=9.156.0.0/16 comment=US disabled=no dynamic=no list=\
    allowed-countries
add address=2.59.21.0/24 comment=CA disabled=no dynamic=no list=\
    allowed-countries
add address=2.59.22.0/24 comment=CA disabled=no dynamic=no list=\
    allowed-countries
add address=5.23.0.0/19 comment=CA disabled=no dynamic=no list=\
    allowed-countries
add address=5.181.164.0/22 comment=CA disabled=no dynamic=no list=\
    allowed-countries
add address=5.181.224.0/22 comment=CA disabled=no dynamic=no list=\
    allowed-countries
add address=15.195.0.0/16 comment=CA disabled=no dynamic=no list=\
    allowed-countries
add address=15.208.0.0/16 comment=CA disabled=no dynamic=no list=\
    allowed-countries
add address=15.235.0.0/16 comment=CA disabled=no dynamic=no list=\
    allowed-countries
add address=23.16.0.0/15 comment=CA disabled=no dynamic=no list=\
    allowed-countries
add address=23.29.192.0/19 comment=CA disabled=no dynamic=no list=\
    allowed-countries
add address=23.83.208.0/20 comment=CA disabled=no dynamic=no list=\
    allowed-countries
add address=23.83.224.0/19 comment=CA disabled=no dynamic=no list=\
    allowed-countries
add address=23.91.80.0/20 comment=CA disabled=no dynamic=no list=\
    allowed-countries
add address=23.91.128.0/18 comment=CA disabled=no dynamic=no list=\
    allowed-countries
add address=23.91.224.0/19 comment=CA disabled=no dynamic=no list=\
    allowed-countries
add address=23.92.128.0/19 comment=CA disabled=no dynamic=no list=\
    allowed-countries
add address=23.105.192.0/19 comment=CA disabled=no dynamic=no list=\
    allowed-countries
add address=23.106.128.0/19 comment=CA disabled=no dynamic=no list=\
    allowed-countries
add address=23.111.64.0/20 comment=CA disabled=no dynamic=no list=\
    allowed-countries
add address=23.128.0.0/24 comment=CA disabled=no dynamic=no list=\
    allowed-countries
add address=23.128.12.0/24 comment=CA disabled=no dynamic=no list=\
    allowed-countries
add address=23.128.44.0/24 comment=CA disabled=no dynamic=no list=\
    allowed-countries
add address=23.128.80.0/24 comment=CA disabled=no dynamic=no list=\
    allowed-countries
add address=23.128.82.0/24 comment=CA disabled=no dynamic=no list=\
    allowed-countries
add address=23.128.92.0/24 comment=CA disabled=no dynamic=no list=\
    allowed-countries
add address=23.128.160.0/24 comment=CA disabled=no dynamic=no list=\
    allowed-countries
add address=23.128.184.0/24 comment=CA disabled=no dynamic=no list=\
    allowed-countries
add address=23.128.200.0/24 comment=CA disabled=no dynamic=no list=\
    allowed-countries
add address=23.128.224.0/24 comment=CA disabled=no dynamic=no list=\
    allowed-countries
add address=23.128.232.0/24 comment=CA disabled=no dynamic=no list=\
    allowed-countries
add address=23.129.16.0/24 comment=CA disabled=no dynamic=no list=\
    allowed-countries
add address=23.129.32.0/24 comment=CA disabled=no dynamic=no list=\
    allowed-countries
add address=23.129.36.0/24 comment=CA disabled=no dynamic=no list=\
    allowed-countries
add address=23.129.108.0/24 comment=CA disabled=no dynamic=no list=\
    allowed-countries
add address=23.129.232.0/24 comment=CA disabled=no dynamic=no list=\
    allowed-countries
add address=23.130.12.0/24 comment=CA disabled=no dynamic=no list=\
    allowed-countries
add address=23.130.32.0/24 comment=CA disabled=no dynamic=no list=\
    allowed-countries
add address=23.130.136.0/22 comment=CA disabled=no dynamic=no list=\
    allowed-countries
add address=23.130.212.0/24 comment=CA disabled=no dynamic=no list=\
    allowed-countries
add address=23.130.248.0/24 comment=CA disabled=no dynamic=no list=\
    allowed-countries
add address=23.131.16.0/24 comment=CA disabled=no dynamic=no list=\
    allowed-countries
add address=23.131.32.0/24 comment=CA disabled=no dynamic=no list=\
    allowed-countries
add address=23.131.40.0/24 comment=CA disabled=no dynamic=no list=\
    allowed-countries
add address=23.131.112.0/24 comment=CA disabled=no dynamic=no list=\
    allowed-countries
add address=23.131.120.0/24 comment=CA disabled=no dynamic=no list=\
    allowed-countries
add address=23.131.148.0/24 comment=CA disabled=no dynamic=no list=\
    allowed-countries
add address=23.132.28.0/24 comment=CA disabled=no dynamic=no list=\
    allowed-countries
add address=23.132.108.0/24 comment=CA disabled=no dynamic=no list=\
    allowed-countries
add address=23.132.148.0/24 comment=CA disabled=no dynamic=no list=\
    allowed-countries
add address=23.132.176.0/24 comment=CA disabled=no dynamic=no list=\
    allowed-countries
add address=70.112.0.0/12 comment="US - Spectrum (your ISP)" disabled=no \
    dynamic=no list=allowed-countries
add address=107.64.0.0/10 comment="AT&T WiFi Calling - Primary Range" \
    disabled=no dynamic=no list=ATT-WiFiCalling
add address=129.192.0.0/16 comment="AT&T WiFi Calling - Secondary Range" \
    disabled=no dynamic=no list=ATT-WiFiCalling
add address=141.207.0.0/16 comment="AT&T WiFi Calling - Additional Range" \
    disabled=no dynamic=no list=ATT-WiFiCalling
add address=162.115.0.0/16 comment="AT&T WiFi Calling - Additional Range" \
    disabled=no dynamic=no list=ATT-WiFiCalling
add address=166.128.0.0/9 comment="AT&T WiFi Calling - Large Block" disabled=\
    no dynamic=no list=ATT-WiFiCalling
add address=208.54.0.0/16 comment="AT&T WiFi Calling - Additional Range" \
    disabled=no dynamic=no list=ATT-WiFiCalling
add address=108.142.0.0/15 comment="Azure Cloud /15" disabled=no dynamic=no \
    list=Microsoft-Services
add address=13.80.0.0/15 comment="Azure Cloud /15" disabled=no dynamic=no \
    list=Microsoft-Services
add address=13.84.0.0/15 comment="Azure Cloud /15" disabled=no dynamic=no \
    list=Microsoft-Services
add address=172.166.0.0/15 comment="Azure Cloud /15" disabled=no dynamic=no \
    list=Microsoft-Services
add address=172.168.0.0/15 comment="Azure Cloud /15" disabled=no dynamic=no \
    list=Microsoft-Services
add address=172.176.0.0/15 comment="Azure Cloud /15" disabled=no dynamic=no \
    list=Microsoft-Services
add address=172.180.0.0/15 comment="Azure Cloud /15" disabled=no dynamic=no \
    list=Microsoft-Services
add address=172.184.0.0/15 comment="Azure Cloud /15" disabled=no dynamic=no \
    list=Microsoft-Services
add address=172.190.0.0/15 comment="Azure Cloud /15" disabled=no dynamic=no \
    list=Microsoft-Services
add address=4.152.0.0/15 comment="Azure Cloud /15" disabled=no dynamic=no \
    list=Microsoft-Services
add address=4.154.0.0/15 comment="Azure Cloud /15" disabled=no dynamic=no \
    list=Microsoft-Services
add address=4.156.0.0/15 comment="Azure Cloud /15" disabled=no dynamic=no \
    list=Microsoft-Services
add address=4.158.0.0/15 comment="Azure Cloud /15" disabled=no dynamic=no \
    list=Microsoft-Services
add address=4.170.0.0/15 comment="Azure Cloud /15" disabled=no dynamic=no \
    list=Microsoft-Services
add address=4.172.0.0/15 comment="Azure Cloud /15" disabled=no dynamic=no \
    list=Microsoft-Services
add address=4.196.0.0/15 comment="Azure Cloud /15" disabled=no dynamic=no \
    list=Microsoft-Services
add address=4.204.0.0/15 comment="Azure Cloud /15" disabled=no dynamic=no \
    list=Microsoft-Services
add address=4.208.0.0/15 comment="Azure Cloud /15" disabled=no dynamic=no \
    list=Microsoft-Services
add address=4.214.0.0/15 comment="Azure Cloud /15" disabled=no dynamic=no \
    list=Microsoft-Services
add address=104.42.0.0/16 comment="Azure Cloud /16" disabled=no dynamic=no \
    list=Microsoft-Services
add address=108.140.0.0/16 comment="Azure Cloud /16" disabled=no dynamic=no \
    list=Microsoft-Services
add address=108.141.0.0/16 comment="Azure Cloud /16" disabled=no dynamic=no \
    list=Microsoft-Services
add address=13.64.0.0/16 comment="Azure Cloud /16" disabled=no dynamic=no \
    list=Microsoft-Services
add address=13.65.0.0/16 comment="Azure Cloud /16" disabled=no dynamic=no \
    list=Microsoft-Services
add address=13.74.0.0/16 comment="Azure Cloud /16" disabled=no dynamic=no \
    list=Microsoft-Services
add address=13.76.0.0/16 comment="Azure Cloud /16" disabled=no dynamic=no \
    list=Microsoft-Services
add address=13.79.0.0/16 comment="Azure Cloud /16" disabled=no dynamic=no \
    list=Microsoft-Services
add address=13.82.0.0/16 comment="Azure Cloud /16" disabled=no dynamic=no \
    list=Microsoft-Services
add address=13.83.0.0/16 comment="Azure Cloud /16" disabled=no dynamic=no \
    list=Microsoft-Services
add address=13.89.0.0/16 comment="Azure Cloud /16" disabled=no dynamic=no \
    list=Microsoft-Services
add address=13.90.0.0/16 comment="Azure Cloud /16" disabled=no dynamic=no \
    list=Microsoft-Services
add address=13.91.0.0/16 comment="Azure Cloud /16" disabled=no dynamic=no \
    list=Microsoft-Services
add address=13.92.0.0/16 comment="Azure Cloud /16" disabled=no dynamic=no \
    list=Microsoft-Services
add address=13.95.0.0/16 comment="Azure Cloud /16" disabled=no dynamic=no \
    list=Microsoft-Services
add address=130.107.0.0/16 comment="Azure Cloud /16" disabled=no dynamic=no \
    list=Microsoft-Services
add address=130.33.0.0/16 comment="Azure Cloud /16" disabled=no dynamic=no \
    list=Microsoft-Services
add address=131.189.0.0/16 comment="Azure Cloud /16" disabled=no dynamic=no \
    list=Microsoft-Services
add address=132.220.0.0/16 comment="Azure Cloud /16" disabled=no dynamic=no \
    list=Microsoft-Services
add address=134.112.0.0/16 comment="Azure Cloud /16" disabled=no dynamic=no \
    list=Microsoft-Services
add address=135.116.0.0/16 comment="Azure Cloud /16" disabled=no dynamic=no \
    list=Microsoft-Services
add address=135.171.0.0/16 comment="Azure Cloud /16" disabled=no dynamic=no \
    list=Microsoft-Services
add address=135.220.0.0/16 comment="Azure Cloud /16" disabled=no dynamic=no \
    list=Microsoft-Services
add address=135.225.0.0/16 comment="Azure Cloud /16" disabled=no dynamic=no \
    list=Microsoft-Services
add address=158.158.0.0/16 comment="Azure Cloud /16" disabled=no dynamic=no \
    list=Microsoft-Services
add address=158.23.0.0/16 comment="Azure Cloud /16" disabled=no dynamic=no \
    list=Microsoft-Services
add address=172.160.0.0/16 comment="Azure Cloud /16" disabled=no dynamic=no \
    list=Microsoft-Services
add address=172.161.0.0/16 comment="Azure Cloud /16" disabled=no dynamic=no \
    list=Microsoft-Services
add address=172.162.0.0/16 comment="Azure Cloud /16" disabled=no dynamic=no \
    list=Microsoft-Services
add address=172.163.0.0/16 comment="Azure Cloud /16" disabled=no dynamic=no \
    list=Microsoft-Services
add address=155.133.224.0/24 comment="Valve Network Range" disabled=no \
    dynamic=no list="Valve Network"
add address=155.133.225.0/24 comment="Valve Network Range" disabled=no \
    dynamic=no list="Valve Network"
add address=155.133.228.0/24 comment="Valve Network Range" disabled=no \
    dynamic=no list="Valve Network"
add address=155.133.229.0/24 comment="Valve Network Range" disabled=no \
    dynamic=no list="Valve Network"
add address=155.133.236.0/23 comment="Valve Network Range" disabled=no \
    dynamic=no list="Valve Network"
add address=155.133.240.0/23 comment="Valve Network Range" disabled=no \
    dynamic=no list="Valve Network"
add address=155.133.249.0/24 comment="Valve Network Range" disabled=no \
    dynamic=no list="Valve Network"
add address=155.133.251.0/24 comment="Valve Network Range" disabled=no \
    dynamic=no list="Valve Network"
add address=155.133.255.0/24 comment="Valve Network Range" disabled=no \
    dynamic=no list="Valve Network"
add address=208.78.164.0/22 comment="Valve Network Range" disabled=no \
    dynamic=no list="Valve Network"
add address=9.9.9.9 comment="Quad9 Primary" disabled=no dynamic=no list=\
    DNS-over-TLS-Servers
add address=149.112.112.112 comment="Quad9 Secondary" disabled=no dynamic=no \
    list=DNS-over-TLS-Servers
add address=1.1.1.1 comment="Cloudflare DNS" disabled=no dynamic=no list=\
    DNS-over-TLS-Servers
add address=96.8.165.93 comment="ZeroTier P2P - Dad's house Pi" disabled=no \
    dynamic=no list=zerotier-peers
add address=104.29.148.0/24 comment="ZeroTier root servers (Cloudflare)" \
    disabled=no dynamic=no list=zerotier-peers
add address=10.10.110.207 comment="rtc-high: main workstation" disabled=no \
    dynamic=no list=rtc-high-clients
add address=10.10.110.245 comment="rtc-high: iPhone WiFi" disabled=no \
    dynamic=no list=rtc-high-clients
add address=10.10.110.205 comment="rtc-high: MacBook" disabled=no dynamic=no \
    list=rtc-high-clients
add address=10.10.110.206 comment="debian - forced for Work VPN web auth" \
    disabled=no dynamic=no list=FORCE_OUT_ATT
add address=10.10.110.207 comment="Kevin main gaming PC" disabled=no dynamic=\
    no list=GAMER-DEVICES
add address=10.10.110.245 comment=iphone disabled=no dynamic=no list=\
    GAMER-DEVICES
add address=3.167.246.108 comment="PoE2 backend / AWS" disabled=no dynamic=no \
    list=auto-games-promoted
add address=162.159.133.234 comment="PoE2 launcher / Cloudflare" disabled=no \
    dynamic=no list=auto-games-promoted
add address=10.10.110.205 comment=laptop disabled=no dynamic=no list=\
    GAMER-DEVICES
add address=1.1.1.1 comment="Cloudflare DoT" disabled=no dynamic=no list=\
    dot-upstream
add address=1.0.0.1 comment="Cloudflare DoT" disabled=no dynamic=no list=\
    dot-upstream
add address=9.9.9.9 comment="Quad9 DoT" disabled=no dynamic=no list=\
    dot-upstream
add address=149.112.112.112 comment="Quad9 DoT" disabled=no dynamic=no list=\
    dot-upstream
add address=94.140.14.14 comment="AdGuard DoT" disabled=no dynamic=no list=\
    dot-upstream
add address=94.140.15.15 comment="AdGuard DoT" disabled=no dynamic=no list=\
    dot-upstream
add address=23.55.0.0/16 comment="Akamai IoT tracking" disabled=no dynamic=no \
    list=bad-iot-cloud
add address=23.57.0.0/16 comment="Akamai tracking" disabled=no dynamic=no \
    list=bad-iot-cloud
add address=23.200.0.0/16 comment="Akamai - Samsung TVs" disabled=no dynamic=\
    no list=bad-iot-cloud
add address=23.210.0.0/16 comment="Akamai - LG TVs" disabled=no dynamic=no \
    list=bad-iot-cloud
add address=23.222.0.0/16 comment="Akamai - Roku analytics" disabled=no \
    dynamic=no list=bad-iot-cloud
add address=52.46.0.0/16 comment="Amazon IoT tracking" disabled=no dynamic=no \
    list=bad-iot-cloud
add address=52.94.0.0/16 comment="AWS IoT Core" disabled=no dynamic=no list=\
    bad-iot-cloud
add address=52.119.0.0/16 comment="Ring Analytics" disabled=no dynamic=no \
    list=bad-iot-cloud
add address=34.208.0.0/12 comment="Google IoT region" disabled=no dynamic=no \
    list=bad-iot-cloud
add address=34.240.0.0/13 comment="Google analytics region" disabled=no \
    dynamic=no list=bad-iot-cloud
add address=35.186.0.0/15 comment="Nest Telemetry" disabled=no dynamic=no \
    list=bad-iot-cloud
add address=52.95.255.0/24 comment="Amazon tracking (precise)" disabled=no \
    dynamic=no list=bad-iot-cloud
add address=69.28.57.0/24 comment="Roku tracking 1" disabled=no dynamic=no \
    list=bad-iot-cloud
add address=69.28.58.0/24 comment="Roku tracking 2" disabled=no dynamic=no \
    list=bad-iot-cloud
add address=208.91.112.0/22 comment="Vizio tracking" disabled=no dynamic=no \
    list=bad-iot-cloud
add address=161.117.0.0/16 comment="Xiaomi/TP-Link telemetry" disabled=no \
    dynamic=no list=bad-iot-cloud
add address=47.246.0.0/16 comment="Alibaba IoT cloud" disabled=no dynamic=no \
    list=bad-iot-cloud
add address=47.250.0.0/16 comment="AliCloud analytics" disabled=no dynamic=no \
    list=bad-iot-cloud
add address=205.251.192.0/19 comment="AWS telemetry" disabled=no dynamic=no \
    list=bad-iot-cloud
add address=193.122.0.0/17 comment="Oracle IoT ads" disabled=no dynamic=no \
    list=bad-iot-cloud
add address=93.184.220.0/24 comment="Edgecast tracking" disabled=no dynamic=\
    no list=bad-iot-cloud
add address=151.101.0.0/16 comment="Fastly telemetry" disabled=no dynamic=no \
    list=bad-iot-cloud
add address=13.35.0.0/16 comment="Amazon analytics accelerator" disabled=no \
    dynamic=no list=bad-iot-cloud
add address=15.197.0.0/16 comment="AWS tracking region" disabled=no dynamic=\
    no list=bad-iot-cloud
add address=18.160.0.0/15 comment="AWS global CDN telemetry" disabled=no \
    dynamic=no list=bad-iot-cloud
add address=10.10.110.247 comment="debian - forced for Work VPN web auth" \
    disabled=no dynamic=no list=FORCE_OUT_ATT
/ip firewall filter
add action=accept chain=input comment="IN: Accept established,related" \
    connection-state=established,related
add action=drop chain=input comment="IN: Drop invalid" connection-state=\
    invalid
add action=drop chain=input comment="IN: Drop spoofed LAN from WAN" \
    in-interface-list=WAN src-address=10.10.0.0/16
add action=drop chain=input comment="IN: Drop bogon src from WAN" \
    in-interface-list=WAN src-address-list=bogons
add action=accept chain=input comment="IN: Allow WireGuard to router" \
    in-interface=wireguard1
add action=accept chain=input comment="IN: Allow ZeroTier to router" \
    in-interface=myZeroTier
add action=accept chain=input comment="IN: Allow mgmt VLAN to router" \
    src-address=10.10.99.0/24
add action=accept chain=input comment="IN: Allow trusted VLAN to router" \
    src-address=10.10.110.0/24
add action=accept chain=input comment="IN: ICMP with rate limit" limit=20,5 \
    protocol=icmp
add action=accept chain=input comment="IN: Allow DHCP" dst-port=67 \
    in-interface-list=VLAN protocol=udp src-port=68
add action=accept chain=input comment="IN: Allow NTP" dst-port=123 \
    in-interface-list=VLAN protocol=udp
add action=accept chain=input comment="IN: Allow NTP from cameras" dst-port=\
    123 in-interface=vlan130-camera protocol=udp
add action=accept chain=input comment="IN: DNS UDP from mgmt" dst-port=53 \
    in-interface=vlan99-mgmt protocol=udp
add action=accept chain=input comment="IN: DNS TCP from mgmt" dst-port=53 \
    in-interface=vlan99-mgmt protocol=tcp
add action=accept chain=input comment="IN: Allow WINBOX" !connection-bytes \
    !connection-limit !connection-mark !connection-nat-state !connection-rate \
    !connection-state !connection-type !content disabled=no !dscp \
    !dst-address !dst-address-list !dst-address-type !dst-limit dst-port=8291 \
    !fragment !hotspot !icmp-options !in-bridge-port !in-bridge-port-list \
    !in-interface in-interface-list=!WAN !ingress-priority !ipsec-policy \
    !ipv4-options !layer7-protocol !limit log=no log-prefix="" !nth \
    !out-bridge-port !out-bridge-port-list !out-interface !out-interface-list \
    !packet-mark !packet-size !per-connection-classifier !port !priority \
    protocol=udp !psd !random !routing-mark src-address=10.10.110.0/24 \
    !src-address-list !src-address-type !src-mac-address !src-port !tcp-flags \
    !tcp-mss !time !tls-host !ttl
add action=accept chain=input comment="IN: Allow WireGuard WAN ports" \
    dst-port=13232,51820 in-interface-list=WAN protocol=udp
add action=drop chain=input comment="IN: Silent drop Plex GDM" \
    dst-address-type=broadcast dst-port=32412,32414 protocol=udp
add action=drop chain=input comment="IN: Silent drop SSDP" dst-address-type=\
    broadcast dst-port=1900 protocol=udp
add action=add-src-to-address-list address-list=ssh-brute \
    address-list-timeout=1w chain=input comment="IN: Detect brute-force" \
    connection-state=new dst-port=22,8728,8291 protocol=tcp src-address=\
    !10.10.0.0/16
add action=drop chain=input comment="IN: Drop brute-force attempts" dst-port=\
    22,8728,8291 protocol=tcp src-address-list=ssh-brute
add action=drop chain=input comment="IN: Block external NTP" dst-port=123 \
    in-interface-list=WAN protocol=udp
add action=drop chain=input comment="IN: Final drop" log=yes log-prefix=\
    "DROP INPUT"
add action=accept chain=forward comment="FW: Accept established,related" \
    !connection-bytes !connection-limit !connection-mark \
    !connection-nat-state !connection-rate connection-state=\
    established,related !connection-type !content disabled=no !dscp \
    !dst-address !dst-address-list !dst-address-type !dst-limit !dst-port \
    !fragment !hotspot !icmp-options !in-bridge-port !in-bridge-port-list \
    !in-interface !in-interface-list !ingress-priority !ipsec-policy \
    !ipv4-options !layer7-protocol !limit log=no log-prefix="" !nth \
    !out-bridge-port !out-bridge-port-list !out-interface !out-interface-list \
    !packet-mark !packet-size !per-connection-classifier !port !priority \
    !protocol !psd !random !routing-mark !src-address !src-address-list \
    !src-address-type !src-mac-address !src-port !tcp-flags !tcp-mss !time \
    !tls-host !ttl
add action=drop chain=forward comment="FW: Drop invalid" !connection-bytes \
    !connection-limit !connection-mark !connection-nat-state !connection-rate \
    connection-state=invalid !connection-type !content disabled=no !dscp \
    !dst-address !dst-address-list !dst-address-type !dst-limit !dst-port \
    !fragment !hotspot !icmp-options !in-bridge-port !in-bridge-port-list \
    !in-interface !in-interface-list !ingress-priority !ipsec-policy \
    !ipv4-options !layer7-protocol !limit log=no log-prefix="" !nth \
    !out-bridge-port !out-bridge-port-list !out-interface !out-interface-list \
    !packet-mark !packet-size !per-connection-classifier !port !priority \
    !protocol !psd !random !routing-mark !src-address !src-address-list \
    !src-address-type !src-mac-address !src-port !tcp-flags !tcp-mss !time \
    !tls-host !ttl
add action=jump chain=forward comment="FW: DNS UDP policy" !connection-bytes \
    !connection-limit !connection-mark !connection-nat-state !connection-rate \
    !connection-state !connection-type !content disabled=no !dscp \
    !dst-address !dst-address-list !dst-address-type !dst-limit dst-port=\
    53,583 !fragment !hotspot !icmp-options !in-bridge-port \
    !in-bridge-port-list !in-interface !in-interface-list !ingress-priority \
    !ipsec-policy !ipv4-options jump-target=dns !layer7-protocol !limit log=\
    no log-prefix="" !nth !out-bridge-port !out-bridge-port-list \
    !out-interface !out-interface-list !packet-mark !packet-size \
    !per-connection-classifier !port !priority protocol=udp !psd !random \
    !routing-mark !src-address !src-address-list !src-address-type \
    !src-mac-address !src-port !tcp-flags !tcp-mss !time !tls-host !ttl
add action=jump chain=forward comment="FW: DNS TCP/DoT policy" \
    !connection-bytes !connection-limit !connection-mark \
    !connection-nat-state !connection-rate !connection-state !connection-type \
    !content disabled=no !dscp !dst-address !dst-address-list \
    !dst-address-type !dst-limit dst-port=53,853 !fragment !hotspot \
    !icmp-options !in-bridge-port !in-bridge-port-list !in-interface \
    !in-interface-list !ingress-priority !ipsec-policy !ipv4-options \
    jump-target=dns !layer7-protocol !limit log=no log-prefix="" !nth \
    !out-bridge-port !out-bridge-port-list !out-interface !out-interface-list \
    !packet-mark !packet-size !per-connection-classifier !port !priority \
    protocol=tcp !psd !random !routing-mark !src-address !src-address-list \
    !src-address-type !src-mac-address !src-port !tcp-flags !tcp-mss !time \
    !tls-host !ttl
add action=accept chain=forward comment="FW: VLAN110 -> mgmt" \
    !connection-bytes !connection-limit !connection-mark \
    !connection-nat-state !connection-rate !connection-state !connection-type \
    !content disabled=no !dscp dst-address=10.10.99.0/24 !dst-address-list \
    !dst-address-type !dst-limit !dst-port !fragment !hotspot !icmp-options \
    !in-bridge-port !in-bridge-port-list !in-interface !in-interface-list \
    !ingress-priority !ipsec-policy !ipv4-options !layer7-protocol !limit \
    log=no log-prefix="" !nth !out-bridge-port !out-bridge-port-list \
    !out-interface !out-interface-list !packet-mark !packet-size \
    !per-connection-classifier !port !priority !protocol !psd !random \
    !routing-mark src-address=10.10.110.0/24 src-address-list=\
    "Network Admins" !src-address-type !src-mac-address !src-port !tcp-flags \
    !tcp-mss !time !tls-host !ttl
add action=accept chain=forward comment="FW: VLANs -> Internet (no cameras)" \
    connection-state=new in-interface=!vlan130-camera in-interface-list=VLAN \
    out-interface-list=WAN
add action=accept chain=forward comment="FW: MGMT -> ALL" !connection-bytes \
    !connection-limit !connection-mark !connection-nat-state !connection-rate \
    !connection-state !connection-type !content disabled=no !dscp \
    dst-address=10.10.0.0/16 !dst-address-list !dst-address-type !dst-limit \
    !dst-port !fragment !hotspot !icmp-options !in-bridge-port \
    !in-bridge-port-list !in-interface !in-interface-list !ingress-priority \
    !ipsec-policy !ipv4-options !layer7-protocol !limit log=no log-prefix="" \
    !nth !out-bridge-port !out-bridge-port-list !out-interface \
    !out-interface-list !packet-mark !packet-size !per-connection-classifier \
    !port !priority !protocol !psd !random !routing-mark src-address=\
    10.10.99.0/24 src-address-list="Network Admins" !src-address-type \
    !src-mac-address !src-port !tcp-flags !tcp-mss !time !tls-host !ttl
add action=drop chain=forward comment="Inter-VLAN default deny" \
    !connection-bytes !connection-limit !connection-mark \
    !connection-nat-state !connection-rate !connection-state !connection-type \
    !content disabled=yes !dscp !dst-address !dst-address-list \
    !dst-address-type !dst-limit !dst-port !fragment !hotspot !icmp-options \
    !in-bridge-port !in-bridge-port-list !in-interface in-interface-list=VLAN \
    !ingress-priority !ipsec-policy !ipv4-options !layer7-protocol !limit \
    log=no log-prefix="" !nth !out-bridge-port !out-bridge-port-list \
    !out-interface out-interface-list=VLAN !packet-mark !packet-size \
    !per-connection-classifier !port !priority !protocol !psd !random \
    !routing-mark !src-address !src-address-list !src-address-type \
    !src-mac-address !src-port !tcp-flags !tcp-mss !time !tls-host !ttl
add action=accept chain=forward comment="FW: ZeroTier -> LAN" in-interface=\
    myZeroTier out-interface-list=VLAN
add action=accept chain=forward comment="FW: LAN -> ZeroTier" \
    in-interface-list=VLAN out-interface=myZeroTier
add action=accept chain=forward comment="FW: Allow WireGuard forwarding" \
    in-interface=wireguard1
add action=drop chain=forward comment="FW: Drop bogon source from WAN" \
    in-interface-list=WAN src-address-list=bogons
add action=accept chain=forward comment="FW: Allow WiFi Calling ESP" \
    in-interface-list=WAN protocol=ipsec-esp
add action=accept chain=forward comment="FW: Monitoring host -> mgmt" \
    dst-address=10.10.99.0/24 src-address=10.10.110.208
add action=accept chain=forward comment="FW: ICMP after RAW" limit=30,30 \
    protocol=icmp
add action=drop chain=forward comment="FW: Block NDI from mgmt" dst-port=6363 \
    in-interface=vlan99-mgmt out-interface=vlan110-trusted protocol=udp
add action=jump chain=forward comment="FW: internet -> local (DSTNAT)" \
    in-interface-list=WAN jump-target=internet
add action=drop chain=forward comment="FW: Drop new WAN traffic" \
    connection-nat-state=!dstnat connection-state=new in-interface-list=WAN
add action=drop chain=forward comment="Block direct NTP to WAN" dst-port=123 \
    out-interface-list=WAN protocol=udp
add action=drop chain=forward comment=\
    "Drop QUIC to WAN (DoQ & covert channels)" dst-port=443 \
    out-interface-list=WAN protocol=udp
add action=drop chain=forward comment=\
    "Block IoT STUN/TURN (smart TV + camera hole punching)" dst-port=\
    3478-3481 in-interface=vlan120-IOT out-interface-list=WAN protocol=udp
add action=drop chain=forward comment="Block IoT tracking domains" \
    dst-address-list=bad-iot-cloud in-interface=vlan120-IOT
add action=drop chain=forward comment="FW: Final drop" log=yes log-prefix=\
    "DROP FORWARD"
add action=accept chain=dns comment="Allow Pi-hole DNS+DoT" src-address-list=\
    pihole
add action=accept chain=dns comment="Allow Pi-hole DoT upstream" \
    dst-address-list=dot-upstream dst-port=853 protocol=tcp src-address-list=\
    pihole
add action=drop chain=dns comment="Block DoQ" !connection-bytes \
    !connection-limit !connection-mark !connection-nat-state !connection-rate \
    !connection-state !connection-type !content disabled=yes !dscp \
    !dst-address !dst-address-list !dst-address-type !dst-limit dst-port=443 \
    !fragment !hotspot !icmp-options !in-bridge-port !in-bridge-port-list \
    !in-interface !in-interface-list !ingress-priority !ipsec-policy \
    !ipv4-options !layer7-protocol !limit log=no log-prefix="" !nth \
    !out-bridge-port !out-bridge-port-list !out-interface !out-interface-list \
    !packet-mark !packet-size !per-connection-classifier !port !priority \
    protocol=udp !psd !random !routing-mark !src-address !src-address-list \
    !src-address-type !src-mac-address !src-port !tcp-flags !tcp-mss !time \
    !tls-host !ttl
add action=drop chain=dns comment="Block DoH" !connection-bytes \
    !connection-limit !connection-mark !connection-nat-state !connection-rate \
    !connection-state !connection-type !content disabled=yes !dscp \
    !dst-address !dst-address-list !dst-address-type !dst-limit dst-port=443 \
    !fragment !hotspot !icmp-options !in-bridge-port !in-bridge-port-list \
    !in-interface !in-interface-list !ingress-priority !ipsec-policy \
    !ipv4-options !layer7-protocol !limit log=no log-prefix="" !nth \
    !out-bridge-port !out-bridge-port-list !out-interface !out-interface-list \
    !packet-mark !packet-size !per-connection-classifier !port !priority \
    protocol=tcp !psd !random !routing-mark !src-address !src-address-list \
    !src-address-type !src-mac-address !src-port !tcp-flags !tcp-mss !time \
    !tls-host !ttl
add action=accept chain=dns comment="dns to pihole" !connection-bytes \
    !connection-limit !connection-mark !connection-nat-state !connection-rate \
    !connection-state !connection-type !content disabled=no !dscp \
    !dst-address dst-address-list=pihole !dst-address-type !dst-limit \
    dst-port=53 !fragment !hotspot !icmp-options !in-bridge-port \
    !in-bridge-port-list !in-interface in-interface-list=VLAN \
    !ingress-priority !ipsec-policy !ipv4-options !layer7-protocol !limit \
    log=no log-prefix="" !nth !out-bridge-port !out-bridge-port-list \
    !out-interface !out-interface-list !packet-mark !packet-size \
    !per-connection-classifier !port !priority protocol=udp !psd !random \
    !routing-mark !src-address !src-address-list !src-address-type \
    !src-mac-address !src-port !tcp-flags !tcp-mss !time !tls-host !ttl
add action=drop chain=dns comment="Drop all remaining DNS/DoH/DoT" \
    !connection-bytes !connection-limit !connection-mark \
    !connection-nat-state !connection-rate !connection-state !connection-type \
    !content disabled=yes !dscp !dst-address !dst-address-list \
    !dst-address-type !dst-limit !dst-port !fragment !hotspot !icmp-options \
    !in-bridge-port !in-bridge-port-list !in-interface !in-interface-list \
    !ingress-priority !ipsec-policy !ipv4-options !layer7-protocol !limit \
    log=yes log-prefix=DNS-DROP !nth !out-bridge-port !out-bridge-port-list \
    !out-interface !out-interface-list !packet-mark !packet-size \
    !per-connection-classifier !port !priority !protocol !psd !random \
    !routing-mark !src-address !src-address-list !src-address-type \
    !src-mac-address !src-port !tcp-flags !tcp-mss !time !tls-host !ttl
/ip firewall mangle
add action=mark-routing chain=prerouting comment=\
    "ROUTING: Force selected LAN hosts out ATT WAN" !connection-bytes \
    !connection-limit !connection-mark !connection-nat-state !connection-rate \
    !connection-state !connection-type !content disabled=yes !dscp \
    dst-address=!10.10.0.0/16 !dst-address-list !dst-address-type !dst-limit \
    !dst-port !fragment !hotspot !icmp-options !in-bridge-port \
    !in-bridge-port-list !in-interface !in-interface-list !ingress-priority \
    !ipsec-policy !ipv4-options !layer7-protocol !limit log=no log-prefix="" \
    new-routing-mark=to_ATT !nth !out-bridge-port !out-bridge-port-list \
    !out-interface !out-interface-list !packet-mark !packet-size passthrough=\
    no !per-connection-classifier !port !priority !protocol !psd !random \
    !routing-mark !src-address src-address-list=FORCE_OUT_ATT \
    !src-address-type !src-mac-address !src-port !tcp-flags !tcp-mss !time \
    !tls-host !ttl
add action=change-mss chain=forward comment=\
    "ROUTING: MSS clamp for ATT WAN (forward)" !connection-bytes \
    !connection-limit !connection-mark !connection-nat-state !connection-rate \
    !connection-state !connection-type !content disabled=yes !dscp \
    !dst-address !dst-address-list !dst-address-type !dst-limit !dst-port \
    !fragment !hotspot !icmp-options !in-bridge-port !in-bridge-port-list \
    !in-interface !in-interface-list !ingress-priority !ipsec-policy \
    !ipv4-options !layer7-protocol !limit log=no log-prefix="" new-mss=1420 \
    !nth !out-bridge-port !out-bridge-port-list out-interface=ether2-WAN-ATT \
    !out-interface-list !packet-mark !packet-size passthrough=yes \
    !per-connection-classifier !port !priority protocol=tcp !psd !random \
    !routing-mark !src-address !src-address-list !src-address-type \
    !src-mac-address !src-port tcp-flags=syn !tcp-mss !time !tls-host !ttl
add action=change-mss chain=postrouting comment=\
    "ROUTING: Clamp MSS to PMTU on WAN egress" !connection-bytes \
    !connection-limit !connection-mark !connection-nat-state !connection-rate \
    !connection-state !connection-type !content disabled=yes !dscp \
    !dst-address !dst-address-list !dst-address-type !dst-limit !dst-port \
    !fragment !hotspot !icmp-options !in-bridge-port !in-bridge-port-list \
    !in-interface !in-interface-list !ingress-priority !ipsec-policy \
    !ipv4-options !layer7-protocol !limit log=no log-prefix="" new-mss=\
    clamp-to-pmtu !nth !out-bridge-port !out-bridge-port-list !out-interface \
    out-interface-list=WAN !packet-mark !packet-size passthrough=yes \
    !per-connection-classifier !port !priority protocol=tcp !psd !random \
    !routing-mark !src-address !src-address-list !src-address-type \
    !src-mac-address !src-port tcp-flags=syn !tcp-mss !time !tls-host !ttl
add action=mark-packet chain=prerouting comment=\
    "WAN: Mark Spectrum inbound (wan-in-spectrum, prerouting)" \
    !connection-bytes !connection-limit !connection-mark \
    !connection-nat-state !connection-rate !connection-state !connection-type \
    !content disabled=yes !dscp !dst-address !dst-address-list \
    !dst-address-type !dst-limit !dst-port !fragment !hotspot !icmp-options \
    !in-bridge-port !in-bridge-port-list in-interface=ether1-WAN-Spectrum \
    !in-interface-list !ingress-priority !ipsec-policy !ipv4-options \
    !layer7-protocol !limit log=no log-prefix="" new-packet-mark=\
    wan-in-spectrum !nth !out-bridge-port !out-bridge-port-list \
    !out-interface !out-interface-list !packet-mark !packet-size passthrough=\
    no !per-connection-classifier !port !priority !protocol !psd !random \
    !routing-mark !src-address !src-address-list !src-address-type \
    !src-mac-address !src-port !tcp-flags !tcp-mss !time !tls-host !ttl
add action=mark-packet chain=prerouting comment=\
    "WAN: Mark ATT inbound (wan-in-att, prerouting)" !connection-bytes \
    !connection-limit !connection-mark !connection-nat-state !connection-rate \
    !connection-state !connection-type !content disabled=yes !dscp \
    !dst-address !dst-address-list !dst-address-type !dst-limit !dst-port \
    !fragment !hotspot !icmp-options !in-bridge-port !in-bridge-port-list \
    in-interface=ether2-WAN-ATT !in-interface-list !ingress-priority \
    !ipsec-policy !ipv4-options !layer7-protocol !limit log=no log-prefix="" \
    new-packet-mark=wan-in-att !nth !out-bridge-port !out-bridge-port-list \
    !out-interface !out-interface-list !packet-mark !packet-size passthrough=\
    no !per-connection-classifier !port !priority !protocol !psd !random \
    !routing-mark !src-address !src-address-list !src-address-type \
    !src-mac-address !src-port !tcp-flags !tcp-mss !time !tls-host !ttl
add action=mark-connection chain=prerouting comment=\
    "HIGH: RTC/Discord-like voice from rtc-high-clients" !connection-bytes \
    !connection-limit !connection-mark !connection-nat-state !connection-rate \
    connection-state=new !connection-type !content disabled=yes !dscp \
    !dst-address !dst-address-list !dst-address-type !dst-limit dst-port=\
    50000-65535 !fragment !hotspot !icmp-options !in-bridge-port \
    !in-bridge-port-list !in-interface !in-interface-list !ingress-priority \
    !ipsec-policy !ipv4-options !layer7-protocol !limit log=no log-prefix="" \
    new-connection-mark=QOS_HIGH !nth !out-bridge-port !out-bridge-port-list \
    !out-interface !out-interface-list !packet-mark !packet-size passthrough=\
    no !per-connection-classifier !port !priority protocol=udp !psd !random \
    !routing-mark !src-address src-address-list=rtc-high-clients \
    !src-address-type !src-mac-address !src-port !tcp-flags !tcp-mss !time \
    !tls-host !ttl
add action=mark-connection chain=prerouting comment="HIGH: Work VPN" \
    !connection-bytes !connection-limit !connection-mark \
    !connection-nat-state !connection-rate connection-state=new \
    !connection-type !content disabled=yes !dscp !dst-address \
    dst-address-list=Work-VPN !dst-address-type !dst-limit !dst-port \
    !fragment !hotspot !icmp-options !in-bridge-port !in-bridge-port-list \
    !in-interface !in-interface-list !ingress-priority !ipsec-policy \
    !ipv4-options !layer7-protocol !limit log=no log-prefix="" \
    new-connection-mark=QOS_HIGH !nth !out-bridge-port !out-bridge-port-list \
    !out-interface !out-interface-list !packet-mark !packet-size passthrough=\
    no !per-connection-classifier !port !priority !protocol !psd !random \
    !routing-mark !src-address !src-address-list !src-address-type \
    !src-mac-address !src-port !tcp-flags !tcp-mss !time !tls-host !ttl
add action=mark-connection chain=prerouting comment=\
    "HIGH: DNS+NTP+IPsec control (UDP)" !connection-bytes !connection-limit \
    !connection-mark !connection-nat-state !connection-rate connection-state=\
    new !connection-type !content disabled=yes !dscp !dst-address \
    !dst-address-list !dst-address-type !dst-limit dst-port=53,123,500 \
    !fragment !hotspot !icmp-options !in-bridge-port !in-bridge-port-list \
    !in-interface !in-interface-list !ingress-priority !ipsec-policy \
    !ipv4-options !layer7-protocol !limit log=no log-prefix="" \
    new-connection-mark=QOS_HIGH !nth !out-bridge-port !out-bridge-port-list \
    !out-interface !out-interface-list !packet-mark !packet-size passthrough=\
    no !per-connection-classifier !port !priority protocol=udp !psd !random \
    !routing-mark !src-address !src-address-list !src-address-type \
    !src-mac-address !src-port !tcp-flags !tcp-mss !time !tls-host !ttl
add action=mark-connection chain=prerouting comment="HIGH: DNS over TCP" \
    !connection-bytes !connection-limit !connection-mark \
    !connection-nat-state !connection-rate connection-state=new \
    !connection-type !content disabled=yes !dscp !dst-address \
    !dst-address-list !dst-address-type !dst-limit dst-port=53 !fragment \
    !hotspot !icmp-options !in-bridge-port !in-bridge-port-list !in-interface \
    !in-interface-list !ingress-priority !ipsec-policy !ipv4-options \
    !layer7-protocol !limit log=no log-prefix="" new-connection-mark=QOS_HIGH \
    !nth !out-bridge-port !out-bridge-port-list !out-interface \
    !out-interface-list !packet-mark !packet-size passthrough=no \
    !per-connection-classifier !port !priority protocol=tcp !psd !random \
    !routing-mark !src-address !src-address-list !src-address-type \
    !src-mac-address !src-port !tcp-flags !tcp-mss !time !tls-host !ttl
add action=mark-connection chain=prerouting comment=\
    "HIGH: DNS over TLS (DoT)" !connection-bytes !connection-limit \
    !connection-mark !connection-nat-state !connection-rate connection-state=\
    new !connection-type !content disabled=yes !dscp !dst-address \
    !dst-address-list !dst-address-type !dst-limit dst-port=853 !fragment \
    !hotspot !icmp-options !in-bridge-port !in-bridge-port-list !in-interface \
    !in-interface-list !ingress-priority !ipsec-policy !ipv4-options \
    !layer7-protocol !limit log=no log-prefix="" new-connection-mark=QOS_HIGH \
    !nth !out-bridge-port !out-bridge-port-list !out-interface \
    !out-interface-list !packet-mark !packet-size passthrough=no \
    !per-connection-classifier !port !priority protocol=tcp !psd !random \
    !routing-mark !src-address !src-address-list !src-address-type \
    !src-mac-address !src-port !tcp-flags !tcp-mss !time !tls-host !ttl
add action=mark-connection chain=prerouting comment=\
    "HIGH: WiFi Calling (UDP 4500 ATT)" !connection-bytes !connection-limit \
    !connection-mark !connection-nat-state !connection-rate connection-state=\
    new !connection-type !content disabled=yes !dscp !dst-address \
    dst-address-list=ATT-WiFiCalling !dst-address-type !dst-limit dst-port=\
    4500 !fragment !hotspot !icmp-options !in-bridge-port \
    !in-bridge-port-list !in-interface !in-interface-list !ingress-priority \
    !ipsec-policy !ipv4-options !layer7-protocol !limit log=no log-prefix="" \
    new-connection-mark=QOS_HIGH !nth !out-bridge-port !out-bridge-port-list \
    !out-interface !out-interface-list !packet-mark !packet-size passthrough=\
    no !per-connection-classifier !port !priority protocol=udp !psd !random \
    !routing-mark !src-address !src-address-list !src-address-type \
    !src-mac-address !src-port !tcp-flags !tcp-mss !time !tls-host !ttl
add action=mark-connection chain=prerouting comment=\
    "HIGH: Real-time Voice/Video (VoIP/Zoom/etc.)" !connection-bytes \
    !connection-limit !connection-mark !connection-nat-state !connection-rate \
    connection-state=new !connection-type !content disabled=yes !dscp \
    !dst-address !dst-address-list !dst-address-type !dst-limit dst-port=\
    64737-64739,5060-5061,3478-3479,5349-5350,19302-19309,8801-8810 !fragment \
    !hotspot !icmp-options !in-bridge-port !in-bridge-port-list !in-interface \
    !in-interface-list !ingress-priority !ipsec-policy !ipv4-options \
    !layer7-protocol !limit log=no log-prefix="" new-connection-mark=QOS_HIGH \
    !nth !out-bridge-port !out-bridge-port-list !out-interface \
    !out-interface-list !packet-mark !packet-size passthrough=no \
    !per-connection-classifier !port !priority protocol=udp !psd !random \
    !routing-mark !src-address !src-address-list !src-address-type \
    !src-mac-address !src-port !tcp-flags !tcp-mss !time !tls-host !ttl
add action=mark-connection chain=prerouting comment=\
    "HIGH: Apple Push Notifications (APNs)" !connection-bytes \
    !connection-limit !connection-mark !connection-nat-state !connection-rate \
    connection-state=new !connection-type !content disabled=yes !dscp \
    !dst-address !dst-address-list !dst-address-type !dst-limit dst-port=5223 \
    !fragment !hotspot !icmp-options !in-bridge-port !in-bridge-port-list \
    !in-interface !in-interface-list !ingress-priority !ipsec-policy \
    !ipv4-options !layer7-protocol !limit log=no log-prefix="" \
    new-connection-mark=QOS_HIGH !nth !out-bridge-port !out-bridge-port-list \
    !out-interface !out-interface-list !packet-mark !packet-size passthrough=\
    no !per-connection-classifier !port !priority protocol=tcp !psd !random \
    !routing-mark !src-address !src-address-list !src-address-type \
    !src-mac-address !src-port !tcp-flags !tcp-mss !time !tls-host !ttl
add action=mark-connection chain=prerouting comment=\
    "HIGH: Google Cloud Messaging (GCM/FCM)" !connection-bytes \
    !connection-limit !connection-mark !connection-nat-state !connection-rate \
    connection-state=new !connection-type !content disabled=yes !dscp \
    !dst-address !dst-address-list !dst-address-type !dst-limit dst-port=5228 \
    !fragment !hotspot !icmp-options !in-bridge-port !in-bridge-port-list \
    !in-interface !in-interface-list !ingress-priority !ipsec-policy \
    !ipv4-options !layer7-protocol !limit log=no log-prefix="" \
    new-connection-mark=QOS_HIGH !nth !out-bridge-port !out-bridge-port-list \
    !out-interface !out-interface-list !packet-mark !packet-size passthrough=\
    no !per-connection-classifier !port !priority protocol=tcp !psd !random \
    !routing-mark !src-address !src-address-list !src-address-type \
    !src-mac-address !src-port !tcp-flags !tcp-mss !time !tls-host !ttl
add action=mark-connection chain=prerouting comment=\
    "HIGH: WireGuard tunnel subnet (QoS only)" !connection-bytes \
    !connection-limit !connection-mark !connection-nat-state !connection-rate \
    connection-state=new !connection-type !content disabled=yes !dscp \
    !dst-address !dst-address-list !dst-address-type !dst-limit !dst-port \
    !fragment !hotspot !icmp-options !in-bridge-port !in-bridge-port-list \
    !in-interface !in-interface-list !ingress-priority !ipsec-policy \
    !ipv4-options !layer7-protocol !limit log=no log-prefix="" \
    new-connection-mark=QOS_HIGH !nth !out-bridge-port !out-bridge-port-list \
    !out-interface !out-interface-list !packet-mark !packet-size passthrough=\
    no !per-connection-classifier !port !priority !protocol !psd !random \
    !routing-mark src-address=10.255.255.0/24 !src-address-list \
    !src-address-type !src-mac-address !src-port !tcp-flags !tcp-mss !time \
    !tls-host !ttl
add action=mark-connection chain=prerouting comment="MEDIUM: ICMP (pings)" \
    !connection-bytes !connection-limit !connection-mark \
    !connection-nat-state !connection-rate connection-state=new \
    !connection-type !content disabled=yes !dscp !dst-address \
    !dst-address-list !dst-address-type !dst-limit !dst-port !fragment \
    !hotspot !icmp-options !in-bridge-port !in-bridge-port-list !in-interface \
    !in-interface-list !ingress-priority !ipsec-policy !ipv4-options \
    !layer7-protocol !limit log=no log-prefix="" new-connection-mark=\
    QOS_MEDIUM !nth !out-bridge-port !out-bridge-port-list !out-interface \
    !out-interface-list !packet-mark !packet-size passthrough=no \
    !per-connection-classifier !port !priority protocol=icmp !psd !random \
    !routing-mark !src-address !src-address-list !src-address-type \
    !src-mac-address !src-port !tcp-flags !tcp-mss !time !tls-host !ttl
add action=mark-connection chain=prerouting comment=\
    "MEDIUM: Interactive Web (TCP 80/443 small)" !connection-bytes \
    !connection-limit !connection-mark !connection-nat-state !connection-rate \
    connection-state=new !connection-type !content disabled=yes !dscp \
    !dst-address !dst-address-list !dst-address-type !dst-limit dst-port=\
    80,443 !fragment !hotspot !icmp-options !in-bridge-port \
    !in-bridge-port-list !in-interface !in-interface-list !ingress-priority \
    !ipsec-policy !ipv4-options !layer7-protocol !limit log=no log-prefix="" \
    new-connection-mark=QOS_MEDIUM !nth !out-bridge-port \
    !out-bridge-port-list !out-interface !out-interface-list !packet-mark \
    packet-size=0-300 passthrough=no !per-connection-classifier !port \
    !priority protocol=tcp !psd !random !routing-mark !src-address \
    !src-address-list !src-address-type !src-mac-address !src-port !tcp-flags \
    !tcp-mss !time !tls-host !ttl
add action=mark-connection chain=prerouting comment=\
    "MEDIUM: Interactive QUIC (UDP 443 small)" !connection-bytes \
    !connection-limit !connection-mark !connection-nat-state !connection-rate \
    connection-state=new !connection-type !content disabled=yes !dscp \
    !dst-address !dst-address-list !dst-address-type !dst-limit dst-port=443 \
    !fragment !hotspot !icmp-options !in-bridge-port !in-bridge-port-list \
    !in-interface !in-interface-list !ingress-priority !ipsec-policy \
    !ipv4-options !layer7-protocol !limit log=no log-prefix="" \
    new-connection-mark=QOS_MEDIUM !nth !out-bridge-port \
    !out-bridge-port-list !out-interface !out-interface-list !packet-mark \
    packet-size=0-300 passthrough=no !per-connection-classifier !port \
    !priority protocol=udp !psd !random !routing-mark !src-address \
    !src-address-list !src-address-type !src-mac-address !src-port !tcp-flags \
    !tcp-mss !time !tls-host !ttl
add action=mark-connection chain=prerouting comment=\
    "MEDIUM: SSH / remote shells" !connection-bytes !connection-limit \
    !connection-mark !connection-nat-state !connection-rate connection-state=\
    new !connection-type !content disabled=yes !dscp !dst-address \
    !dst-address-list !dst-address-type !dst-limit dst-port=22 !fragment \
    !hotspot !icmp-options !in-bridge-port !in-bridge-port-list !in-interface \
    !in-interface-list !ingress-priority !ipsec-policy !ipv4-options \
    !layer7-protocol !limit log=no log-prefix="" new-connection-mark=\
    QOS_MEDIUM !nth !out-bridge-port !out-bridge-port-list !out-interface \
    !out-interface-list !packet-mark !packet-size passthrough=no \
    !per-connection-classifier !port !priority protocol=tcp !psd !random \
    !routing-mark !src-address !src-address-list !src-address-type \
    !src-mac-address !src-port !tcp-flags !tcp-mss !time !tls-host !ttl
add action=mark-connection chain=prerouting comment=\
    "MEDIUM: MQTT over TLS (IoT)" !connection-bytes !connection-limit \
    !connection-mark !connection-nat-state !connection-rate connection-state=\
    new !connection-type !content disabled=yes !dscp !dst-address \
    !dst-address-list !dst-address-type !dst-limit dst-port=8883 !fragment \
    !hotspot !icmp-options !in-bridge-port !in-bridge-port-list !in-interface \
    !in-interface-list !ingress-priority !ipsec-policy !ipv4-options \
    !layer7-protocol !limit log=no log-prefix="" new-connection-mark=\
    QOS_MEDIUM !nth !out-bridge-port !out-bridge-port-list !out-interface \
    !out-interface-list !packet-mark !packet-size passthrough=no \
    !per-connection-classifier !port !priority protocol=tcp !psd !random \
    !routing-mark !src-address !src-address-list !src-address-type \
    !src-mac-address !src-port !tcp-flags !tcp-mss !time !tls-host !ttl
add action=mark-connection chain=prerouting comment="MEDIUM: RDP TCP 3389" \
    !connection-bytes !connection-limit !connection-mark \
    !connection-nat-state !connection-rate connection-state=new \
    !connection-type !content disabled=yes !dscp !dst-address \
    !dst-address-list !dst-address-type !dst-limit dst-port=3389 !fragment \
    !hotspot !icmp-options !in-bridge-port !in-bridge-port-list !in-interface \
    !in-interface-list !ingress-priority !ipsec-policy !ipv4-options \
    !layer7-protocol !limit log=no log-prefix="" new-connection-mark=\
    QOS_MEDIUM !nth !out-bridge-port !out-bridge-port-list !out-interface \
    !out-interface-list !packet-mark !packet-size passthrough=no \
    !per-connection-classifier !port !priority protocol=tcp !psd !random \
    !routing-mark !src-address !src-address-list !src-address-type \
    !src-mac-address !src-port !tcp-flags !tcp-mss !time !tls-host !ttl
add action=mark-connection chain=prerouting comment=\
    "MEDIUM: RDP UDP RemoteFX 3389" !connection-bytes !connection-limit \
    !connection-mark !connection-nat-state !connection-rate connection-state=\
    new !connection-type !content disabled=yes !dscp !dst-address \
    !dst-address-list !dst-address-type !dst-limit dst-port=3389 !fragment \
    !hotspot !icmp-options !in-bridge-port !in-bridge-port-list !in-interface \
    !in-interface-list !ingress-priority !ipsec-policy !ipv4-options \
    !layer7-protocol !limit log=no log-prefix="" new-connection-mark=\
    QOS_MEDIUM !nth !out-bridge-port !out-bridge-port-list !out-interface \
    !out-interface-list !packet-mark !packet-size passthrough=no \
    !per-connection-classifier !port !priority protocol=udp !psd !random \
    !routing-mark !src-address !src-address-list !src-address-type \
    !src-mac-address !src-port !tcp-flags !tcp-mss !time !tls-host !ttl
add action=mark-connection chain=prerouting comment=\
    "MEDIUM: VNC TCP 5900-5901" !connection-bytes !connection-limit \
    !connection-mark !connection-nat-state !connection-rate connection-state=\
    new !connection-type !content disabled=yes !dscp !dst-address \
    !dst-address-list !dst-address-type !dst-limit dst-port=5900-5901 \
    !fragment !hotspot !icmp-options !in-bridge-port !in-bridge-port-list \
    !in-interface !in-interface-list !ingress-priority !ipsec-policy \
    !ipv4-options !layer7-protocol !limit log=no log-prefix="" \
    new-connection-mark=QOS_MEDIUM !nth !out-bridge-port \
    !out-bridge-port-list !out-interface !out-interface-list !packet-mark \
    !packet-size passthrough=no !per-connection-classifier !port !priority \
    protocol=tcp !psd !random !routing-mark !src-address !src-address-list \
    !src-address-type !src-mac-address !src-port !tcp-flags !tcp-mss !time \
    !tls-host !ttl
add action=mark-connection chain=prerouting comment=\
    "MEDIUM: Alt HTTPS TCP 8080/8443 small" !connection-bytes \
    !connection-limit !connection-mark !connection-nat-state !connection-rate \
    connection-state=new !connection-type !content disabled=yes !dscp \
    !dst-address !dst-address-list !dst-address-type !dst-limit dst-port=\
    8080,8443 !fragment !hotspot !icmp-options !in-bridge-port \
    !in-bridge-port-list !in-interface !in-interface-list !ingress-priority \
    !ipsec-policy !ipv4-options !layer7-protocol !limit log=no log-prefix="" \
    new-connection-mark=QOS_MEDIUM !nth !out-bridge-port \
    !out-bridge-port-list !out-interface !out-interface-list !packet-mark \
    packet-size=0-300 passthrough=no !per-connection-classifier !port \
    !priority protocol=tcp !psd !random !routing-mark !src-address \
    !src-address-list !src-address-type !src-mac-address !src-port !tcp-flags \
    !tcp-mss !time !tls-host !ttl
add action=mark-connection chain=prerouting comment=\
    "MEDIUM: High-bitrate UDP (video/real-time)" !connection-bytes \
    !connection-limit !connection-mark !connection-nat-state connection-rate=\
    500k-100M !connection-state !connection-type !content disabled=yes !dscp \
    !dst-address !dst-address-list !dst-address-type !dst-limit !dst-port \
    !fragment !hotspot !icmp-options !in-bridge-port !in-bridge-port-list \
    !in-interface !in-interface-list !ingress-priority !ipsec-policy \
    !ipv4-options !layer7-protocol !limit log=no log-prefix="" \
    new-connection-mark=QOS_MEDIUM !nth !out-bridge-port \
    !out-bridge-port-list !out-interface !out-interface-list !packet-mark \
    !packet-size passthrough=no !per-connection-classifier !port !priority \
    protocol=udp !psd !random !routing-mark !src-address !src-address-list \
    !src-address-type !src-mac-address !src-port !tcp-flags !tcp-mss !time \
    !tls-host !ttl
add action=mark-connection chain=prerouting comment=\
    "MEDIUM: ZeroTier VPN UDP 9993" !connection-bytes !connection-limit \
    !connection-mark !connection-nat-state !connection-rate connection-state=\
    new !connection-type !content disabled=yes !dscp !dst-address \
    !dst-address-list !dst-address-type !dst-limit dst-port=9993 !fragment \
    !hotspot !icmp-options !in-bridge-port !in-bridge-port-list !in-interface \
    !in-interface-list !ingress-priority !ipsec-policy !ipv4-options \
    !layer7-protocol !limit log=no log-prefix="" new-connection-mark=\
    QOS_MEDIUM !nth !out-bridge-port !out-bridge-port-list !out-interface \
    !out-interface-list !packet-mark !packet-size passthrough=no \
    !per-connection-classifier !port !priority protocol=udp !psd !random \
    !routing-mark !src-address !src-address-list !src-address-type \
    !src-mac-address !src-port !tcp-flags !tcp-mss !time !tls-host !ttl
add action=mark-connection chain=prerouting comment=\
    "NORMAL: Email (SMTP/IMAP/POP3)" !connection-bytes !connection-limit \
    !connection-mark !connection-nat-state !connection-rate connection-state=\
    new !connection-type !content disabled=yes !dscp !dst-address \
    !dst-address-list !dst-address-type !dst-limit dst-port=\
    25,465,587,110,143,993,995 !fragment !hotspot !icmp-options \
    !in-bridge-port !in-bridge-port-list !in-interface !in-interface-list \
    !ingress-priority !ipsec-policy !ipv4-options !layer7-protocol !limit \
    log=no log-prefix="" new-connection-mark=QOS_NORMAL !nth !out-bridge-port \
    !out-bridge-port-list !out-interface !out-interface-list !packet-mark \
    !packet-size passthrough=no !per-connection-classifier !port !priority \
    protocol=tcp !psd !random !routing-mark !src-address !src-address-list \
    !src-address-type !src-mac-address !src-port !tcp-flags !tcp-mss !time \
    !tls-host !ttl
add action=mark-connection chain=prerouting comment=\
    "NORMAL: Web TCP 80/443 (pre-demotion)" !connection-bytes \
    !connection-limit connection-mark=no-mark !connection-nat-state \
    !connection-rate connection-state=new !connection-type !content disabled=\
    yes !dscp !dst-address !dst-address-list !dst-address-type !dst-limit \
    dst-port=80,443 !fragment !hotspot !icmp-options !in-bridge-port \
    !in-bridge-port-list !in-interface !in-interface-list !ingress-priority \
    !ipsec-policy !ipv4-options !layer7-protocol !limit log=no log-prefix="" \
    new-connection-mark=QOS_NORMAL !nth !out-bridge-port \
    !out-bridge-port-list !out-interface !out-interface-list !packet-mark \
    !packet-size passthrough=no !per-connection-classifier !port !priority \
    protocol=tcp !psd !random !routing-mark !src-address !src-address-list \
    !src-address-type !src-mac-address !src-port !tcp-flags !tcp-mss !time \
    !tls-host !ttl
add action=mark-connection chain=prerouting comment=\
    "NORMAL: QUIC UDP 443 (pre-demotion)" !connection-bytes !connection-limit \
    connection-mark=no-mark !connection-nat-state !connection-rate \
    connection-state=new !connection-type !content disabled=yes !dscp \
    !dst-address !dst-address-list !dst-address-type !dst-limit dst-port=443 \
    !fragment !hotspot !icmp-options !in-bridge-port !in-bridge-port-list \
    !in-interface !in-interface-list !ingress-priority !ipsec-policy \
    !ipv4-options !layer7-protocol !limit log=no log-prefix="" \
    new-connection-mark=QOS_NORMAL !nth !out-bridge-port \
    !out-bridge-port-list !out-interface !out-interface-list !packet-mark \
    !packet-size passthrough=no !per-connection-classifier !port !priority \
    protocol=udp !psd !random !routing-mark !src-address !src-address-list \
    !src-address-type !src-mac-address !src-port !tcp-flags !tcp-mss !time \
    !tls-host !ttl
add action=mark-connection chain=prerouting comment=\
    "NORMAL: Alt HTTPS TCP 8080/8443 (pre-demotion)" !connection-bytes \
    !connection-limit connection-mark=no-mark !connection-nat-state \
    !connection-rate connection-state=new !connection-type !content disabled=\
    yes !dscp !dst-address !dst-address-list !dst-address-type !dst-limit \
    dst-port=8080,8443 !fragment !hotspot !icmp-options !in-bridge-port \
    !in-bridge-port-list !in-interface !in-interface-list !ingress-priority \
    !ipsec-policy !ipv4-options !layer7-protocol !limit log=no log-prefix="" \
    new-connection-mark=QOS_NORMAL !nth !out-bridge-port \
    !out-bridge-port-list !out-interface !out-interface-list !packet-mark \
    !packet-size passthrough=no !per-connection-classifier !port !priority \
    protocol=tcp !psd !random !routing-mark !src-address !src-address-list \
    !src-address-type !src-mac-address !src-port !tcp-flags !tcp-mss !time \
    !tls-host !ttl
add action=mark-connection chain=prerouting comment=\
    "LOW: Large Web from MEDIUM (>10MB)" connection-bytes=10000000-0 \
    !connection-limit connection-mark=QOS_MEDIUM !connection-nat-state \
    !connection-rate !connection-state !connection-type !content disabled=yes \
    !dscp !dst-address !dst-address-list !dst-address-type !dst-limit \
    !dst-port !fragment !hotspot !icmp-options !in-bridge-port \
    !in-bridge-port-list !in-interface !in-interface-list !ingress-priority \
    !ipsec-policy !ipv4-options !layer7-protocol !limit log=no log-prefix="" \
    new-connection-mark=QOS_LOW !nth !out-bridge-port !out-bridge-port-list \
    !out-interface !out-interface-list !packet-mark !packet-size passthrough=\
    no !per-connection-classifier !port !priority protocol=tcp !psd !random \
    !routing-mark !src-address !src-address-list !src-address-type \
    !src-mac-address !src-port !tcp-flags !tcp-mss !time !tls-host !ttl
add action=mark-connection chain=prerouting comment=\
    "LOW: Large Web from NORMAL (>10MB)" connection-bytes=10000000-0 \
    !connection-limit connection-mark=QOS_NORMAL !connection-nat-state \
    !connection-rate !connection-state !connection-type !content disabled=yes \
    !dscp !dst-address !dst-address-list !dst-address-type !dst-limit \
    dst-port=80,443 !fragment !hotspot !icmp-options !in-bridge-port \
    !in-bridge-port-list !in-interface !in-interface-list !ingress-priority \
    !ipsec-policy !ipv4-options !layer7-protocol !limit log=no log-prefix="" \
    new-connection-mark=QOS_LOW !nth !out-bridge-port !out-bridge-port-list \
    !out-interface !out-interface-list !packet-mark !packet-size passthrough=\
    no !per-connection-classifier !port !priority protocol=tcp !psd !random \
    !routing-mark !src-address !src-address-list !src-address-type \
    !src-mac-address !src-port !tcp-flags !tcp-mss !time !tls-host !ttl
add action=mark-connection chain=prerouting comment=\
    "LOW: Large QUIC from MEDIUM (>10MB)" connection-bytes=10000000-0 \
    !connection-limit connection-mark=QOS_MEDIUM !connection-nat-state \
    !connection-rate !connection-state !connection-type !content disabled=yes \
    !dscp !dst-address !dst-address-list !dst-address-type !dst-limit \
    dst-port=443 !fragment !hotspot !icmp-options !in-bridge-port \
    !in-bridge-port-list !in-interface !in-interface-list !ingress-priority \
    !ipsec-policy !ipv4-options !layer7-protocol !limit log=no log-prefix="" \
    new-connection-mark=QOS_LOW !nth !out-bridge-port !out-bridge-port-list \
    !out-interface !out-interface-list !packet-mark !packet-size passthrough=\
    no !per-connection-classifier !port !priority protocol=udp !psd !random \
    !routing-mark !src-address !src-address-list !src-address-type \
    !src-mac-address !src-port !tcp-flags !tcp-mss !time !tls-host !ttl
add action=mark-connection chain=prerouting comment=\
    "LOW: Large QUIC from NORMAL (>10MB)" connection-bytes=10000000-0 \
    !connection-limit connection-mark=QOS_NORMAL !connection-nat-state \
    !connection-rate !connection-state !connection-type !content disabled=yes \
    !dscp !dst-address !dst-address-list !dst-address-type !dst-limit \
    dst-port=443 !fragment !hotspot !icmp-options !in-bridge-port \
    !in-bridge-port-list !in-interface !in-interface-list !ingress-priority \
    !ipsec-policy !ipv4-options !layer7-protocol !limit log=no log-prefix="" \
    new-connection-mark=QOS_LOW !nth !out-bridge-port !out-bridge-port-list \
    !out-interface !out-interface-list !packet-mark !packet-size passthrough=\
    no !per-connection-classifier !port !priority protocol=udp !psd !random \
    !routing-mark !src-address !src-address-list !src-address-type \
    !src-mac-address !src-port !tcp-flags !tcp-mss !time !tls-host !ttl
add action=mark-connection chain=prerouting comment=\
    "LOW: Large Alt HTTPS from MEDIUM (>10MB)" connection-bytes=10000000-0 \
    !connection-limit connection-mark=QOS_MEDIUM !connection-nat-state \
    !connection-rate !connection-state !connection-type !content disabled=yes \
    !dscp !dst-address !dst-address-list !dst-address-type !dst-limit \
    dst-port=8080,8443 !fragment !hotspot !icmp-options !in-bridge-port \
    !in-bridge-port-list !in-interface !in-interface-list !ingress-priority \
    !ipsec-policy !ipv4-options !layer7-protocol !limit log=no log-prefix="" \
    new-connection-mark=QOS_LOW !nth !out-bridge-port !out-bridge-port-list \
    !out-interface !out-interface-list !packet-mark !packet-size passthrough=\
    no !per-connection-classifier !port !priority protocol=tcp !psd !random \
    !routing-mark !src-address !src-address-list !src-address-type \
    !src-mac-address !src-port !tcp-flags !tcp-mss !time !tls-host !ttl
add action=mark-connection chain=prerouting comment=\
    "LOW: Large Alt HTTPS from NORMAL (>10MB)" connection-bytes=10000000-0 \
    !connection-limit connection-mark=QOS_NORMAL !connection-nat-state \
    !connection-rate !connection-state !connection-type !content disabled=yes \
    !dscp !dst-address !dst-address-list !dst-address-type !dst-limit \
    dst-port=8080,8443 !fragment !hotspot !icmp-options !in-bridge-port \
    !in-bridge-port-list !in-interface !in-interface-list !ingress-priority \
    !ipsec-policy !ipv4-options !layer7-protocol !limit log=no log-prefix="" \
    new-connection-mark=QOS_LOW !nth !out-bridge-port !out-bridge-port-list \
    !out-interface !out-interface-list !packet-mark !packet-size passthrough=\
    no !per-connection-classifier !port !priority protocol=tcp !psd !random \
    !routing-mark !src-address !src-address-list !src-address-type \
    !src-mac-address !src-port !tcp-flags !tcp-mss !time !tls-host !ttl
add action=mark-connection chain=prerouting comment=\
    "LOW: Usenet NNTPS TCP 563" !connection-bytes !connection-limit \
    !connection-mark !connection-nat-state !connection-rate connection-state=\
    new !connection-type !content disabled=yes !dscp !dst-address \
    !dst-address-list !dst-address-type !dst-limit dst-port=563 !fragment \
    !hotspot !icmp-options !in-bridge-port !in-bridge-port-list !in-interface \
    !in-interface-list !ingress-priority !ipsec-policy !ipv4-options \
    !layer7-protocol !limit log=no log-prefix="" new-connection-mark=QOS_LOW \
    !nth !out-bridge-port !out-bridge-port-list !out-interface \
    !out-interface-list !packet-mark !packet-size passthrough=no \
    !per-connection-classifier !port !priority protocol=tcp !psd !random \
    !routing-mark !src-address !src-address-list !src-address-type \
    !src-mac-address !src-port !tcp-flags !tcp-mss !time !tls-host !ttl
add action=mark-connection chain=prerouting comment="LOW: BitTorrent DHT UDP" \
    !connection-bytes !connection-limit !connection-mark \
    !connection-nat-state !connection-rate connection-state=new \
    !connection-type !content disabled=yes !dscp !dst-address \
    !dst-address-list !dst-address-type !dst-limit !dst-port !fragment \
    !hotspot !icmp-options !in-bridge-port !in-bridge-port-list !in-interface \
    !in-interface-list !ingress-priority !ipsec-policy !ipv4-options \
    !layer7-protocol !limit log=no log-prefix="" new-connection-mark=QOS_LOW \
    !nth !out-bridge-port !out-bridge-port-list !out-interface \
    !out-interface-list !packet-mark !packet-size passthrough=no \
    !per-connection-classifier !port !priority protocol=udp !psd !random \
    !routing-mark !src-address !src-address-list !src-address-type \
    !src-mac-address src-port=51413 !tcp-flags !tcp-mss !time !tls-host !ttl
add action=mark-connection chain=prerouting comment=\
    "LOW: BitTorrent TCP 6881-6889" !connection-bytes !connection-limit \
    !connection-mark !connection-nat-state !connection-rate connection-state=\
    new !connection-type !content disabled=yes !dscp !dst-address \
    !dst-address-list !dst-address-type !dst-limit dst-port=6881-6889 \
    !fragment !hotspot !icmp-options !in-bridge-port !in-bridge-port-list \
    !in-interface !in-interface-list !ingress-priority !ipsec-policy \
    !ipv4-options !layer7-protocol !limit log=no log-prefix="" \
    new-connection-mark=QOS_LOW !nth !out-bridge-port !out-bridge-port-list \
    !out-interface !out-interface-list !packet-mark !packet-size passthrough=\
    no !per-connection-classifier !port !priority protocol=tcp !psd !random \
    !routing-mark !src-address !src-address-list !src-address-type \
    !src-mac-address !src-port !tcp-flags !tcp-mss !time !tls-host !ttl
add action=mark-connection chain=prerouting comment=\
    "LOW: BitTorrent UDP 6881-6889" !connection-bytes !connection-limit \
    !connection-mark !connection-nat-state !connection-rate connection-state=\
    new !connection-type !content disabled=yes !dscp !dst-address \
    !dst-address-list !dst-address-type !dst-limit dst-port=6881-6889 \
    !fragment !hotspot !icmp-options !in-bridge-port !in-bridge-port-list \
    !in-interface !in-interface-list !ingress-priority !ipsec-policy \
    !ipv4-options !layer7-protocol !limit log=no log-prefix="" \
    new-connection-mark=QOS_LOW !nth !out-bridge-port !out-bridge-port-list \
    !out-interface !out-interface-list !packet-mark !packet-size passthrough=\
    no !per-connection-classifier !port !priority protocol=udp !psd !random \
    !routing-mark !src-address !src-address-list !src-address-type \
    !src-mac-address !src-port !tcp-flags !tcp-mss !time !tls-host !ttl
add action=mark-connection chain=prerouting comment=\
    "LOW: Multicast mDNS/SSDP etc." !connection-bytes !connection-limit \
    !connection-mark !connection-nat-state !connection-rate connection-state=\
    new !connection-type !content disabled=yes !dscp dst-address=224.0.0.0/4 \
    !dst-address-list !dst-address-type !dst-limit !dst-port !fragment \
    !hotspot !icmp-options !in-bridge-port !in-bridge-port-list !in-interface \
    !in-interface-list !ingress-priority !ipsec-policy !ipv4-options \
    !layer7-protocol !limit log=no log-prefix="" new-connection-mark=QOS_LOW \
    !nth !out-bridge-port !out-bridge-port-list !out-interface \
    !out-interface-list !packet-mark !packet-size passthrough=no \
    !per-connection-classifier !port !priority protocol=udp !psd !random \
    !routing-mark !src-address !src-address-list !src-address-type \
    !src-mac-address !src-port !tcp-flags !tcp-mss !time !tls-host !ttl
add action=mark-connection chain=prerouting comment=\
    "LOW: Discovery protocols UDP 5353/1900/5678" !connection-bytes \
    !connection-limit !connection-mark !connection-nat-state !connection-rate \
    connection-state=new !connection-type !content disabled=yes !dscp \
    !dst-address !dst-address-list !dst-address-type !dst-limit dst-port=\
    5353,1900,5678 !fragment !hotspot !icmp-options !in-bridge-port \
    !in-bridge-port-list !in-interface !in-interface-list !ingress-priority \
    !ipsec-policy !ipv4-options !layer7-protocol !limit log=no log-prefix="" \
    new-connection-mark=QOS_LOW !nth !out-bridge-port !out-bridge-port-list \
    !out-interface !out-interface-list !packet-mark !packet-size passthrough=\
    no !per-connection-classifier !port !priority protocol=udp !psd !random \
    !routing-mark !src-address !src-address-list !src-address-type \
    !src-mac-address !src-port !tcp-flags !tcp-mss !time !tls-host !ttl
add action=mark-connection chain=prerouting comment=\
    "LOW: Plex discovery UDP 32412/32414" !connection-bytes !connection-limit \
    !connection-mark !connection-nat-state !connection-rate connection-state=\
    new !connection-type !content disabled=yes !dscp !dst-address \
    !dst-address-list !dst-address-type !dst-limit dst-port=32412,32414 \
    !fragment !hotspot !icmp-options !in-bridge-port !in-bridge-port-list \
    !in-interface !in-interface-list !ingress-priority !ipsec-policy \
    !ipv4-options !layer7-protocol !limit log=no log-prefix="" \
    new-connection-mark=QOS_LOW !nth !out-bridge-port !out-bridge-port-list \
    !out-interface !out-interface-list !packet-mark !packet-size passthrough=\
    no !per-connection-classifier !port !priority protocol=udp !psd !random \
    !routing-mark !src-address !src-address-list !src-address-type \
    !src-mac-address !src-port !tcp-flags !tcp-mss !time !tls-host !ttl
add action=mark-connection chain=prerouting comment=\
    "LOW: WAN inbound scans/unwanted new connections" !connection-bytes \
    !connection-limit !connection-mark !connection-nat-state !connection-rate \
    connection-state=new !connection-type !content disabled=yes !dscp \
    !dst-address !dst-address-list !dst-address-type !dst-limit !dst-port \
    !fragment !hotspot !icmp-options !in-bridge-port !in-bridge-port-list \
    !in-interface in-interface-list=WAN !ingress-priority !ipsec-policy \
    !ipv4-options !layer7-protocol !limit log=no log-prefix="" \
    new-connection-mark=QOS_LOW !nth !out-bridge-port !out-bridge-port-list \
    !out-interface !out-interface-list !packet-mark !packet-size passthrough=\
    no !per-connection-classifier !port !priority !protocol !psd !random \
    !routing-mark !src-address !src-address-list !src-address-type \
    !src-mac-address !src-port !tcp-flags !tcp-mss !time !tls-host !ttl
add action=mark-connection chain=prerouting comment=\
    "LOW: NDI/NewTek discovery UDP 6363" !connection-bytes !connection-limit \
    !connection-mark !connection-nat-state !connection-rate connection-state=\
    new !connection-type !content disabled=yes !dscp !dst-address \
    !dst-address-list !dst-address-type !dst-limit dst-port=6363 !fragment \
    !hotspot !icmp-options !in-bridge-port !in-bridge-port-list !in-interface \
    !in-interface-list !ingress-priority !ipsec-policy !ipv4-options \
    !layer7-protocol !limit log=no log-prefix="" new-connection-mark=QOS_LOW \
    !nth !out-bridge-port !out-bridge-port-list !out-interface \
    !out-interface-list !packet-mark !packet-size passthrough=no \
    !per-connection-classifier !port !priority protocol=udp !psd !random \
    !routing-mark !src-address !src-address-list !src-address-type \
    !src-mac-address !src-port !tcp-flags !tcp-mss !time !tls-host !ttl
add action=mark-connection chain=prerouting comment=\
    "LOW: Traceroute UDP 33434-33500" !connection-bytes !connection-limit \
    !connection-mark !connection-nat-state !connection-rate connection-state=\
    new !connection-type !content disabled=yes !dscp !dst-address \
    !dst-address-list !dst-address-type !dst-limit dst-port=33434-33500 \
    !fragment !hotspot !icmp-options !in-bridge-port !in-bridge-port-list \
    !in-interface !in-interface-list !ingress-priority !ipsec-policy \
    !ipv4-options !layer7-protocol !limit log=no log-prefix="" \
    new-connection-mark=QOS_LOW !nth !out-bridge-port !out-bridge-port-list \
    !out-interface !out-interface-list !packet-mark !packet-size passthrough=\
    no !per-connection-classifier !port !priority protocol=udp !psd !random \
    !routing-mark !src-address !src-address-list !src-address-type \
    !src-mac-address !src-port !tcp-flags !tcp-mss !time !tls-host !ttl
add action=log chain=prerouting comment=\
    "LOG: Unclassified NEW connections (no mark)" !connection-bytes \
    !connection-limit connection-mark=no-mark !connection-nat-state \
    !connection-rate connection-state=new !connection-type !content disabled=\
    yes !dscp !dst-address !dst-address-list !dst-address-type !dst-limit \
    !dst-port !fragment !hotspot !icmp-options !in-bridge-port \
    !in-bridge-port-list !in-interface !in-interface-list !ingress-priority \
    !ipsec-policy !ipv4-options !layer7-protocol !limit log=no log-prefix=\
    UNCLASS: !nth !out-bridge-port !out-bridge-port-list !out-interface \
    !out-interface-list !packet-mark !packet-size !per-connection-classifier \
    !port !priority !protocol !psd !random !routing-mark !src-address \
    !src-address-list !src-address-type !src-mac-address !src-port !tcp-flags \
    !tcp-mss !time !tls-host !ttl
add action=mark-connection chain=prerouting comment=\
    "DEFAULT: Unclassified NEW  QOS_NORMAL" !connection-bytes \
    !connection-limit connection-mark=no-mark !connection-nat-state \
    !connection-rate connection-state=new !connection-type !content disabled=\
    yes !dscp !dst-address !dst-address-list !dst-address-type !dst-limit \
    !dst-port !fragment !hotspot !icmp-options !in-bridge-port \
    !in-bridge-port-list !in-interface !in-interface-list !ingress-priority \
    !ipsec-policy !ipv4-options !layer7-protocol !limit log=no log-prefix="" \
    new-connection-mark=QOS_NORMAL !nth !out-bridge-port \
    !out-bridge-port-list !out-interface !out-interface-list !packet-mark \
    !packet-size passthrough=no !per-connection-classifier !port !priority \
    !protocol !psd !random !routing-mark !src-address !src-address-list \
    !src-address-type !src-mac-address !src-port !tcp-flags !tcp-mss !time \
    !tls-host !ttl
add action=mark-packet chain=postrouting comment="Upload Spectrum marking" \
    !connection-bytes !connection-limit !connection-mark \
    !connection-nat-state !connection-rate !connection-state !connection-type \
    !content disabled=yes !dscp !dst-address !dst-address-list \
    !dst-address-type !dst-limit !dst-port !fragment !hotspot !icmp-options \
    !in-bridge-port !in-bridge-port-list !in-interface !in-interface-list \
    !ingress-priority !ipsec-policy !ipv4-options !layer7-protocol !limit \
    log=no log-prefix="" new-packet-mark=wan-out-spectrum !nth \
    !out-bridge-port !out-bridge-port-list out-interface=ether1-WAN-Spectrum \
    !out-interface-list !packet-mark !packet-size passthrough=yes \
    !per-connection-classifier !port !priority !protocol !psd !random \
    !routing-mark !src-address !src-address-list !src-address-type \
    !src-mac-address !src-port !tcp-flags !tcp-mss !time !tls-host !ttl
add action=mark-packet chain=postrouting comment="upload att marking" \
    !connection-bytes !connection-limit !connection-mark \
    !connection-nat-state !connection-rate !connection-state !connection-type \
    !content disabled=yes !dscp !dst-address !dst-address-list \
    !dst-address-type !dst-limit !dst-port !fragment !hotspot !icmp-options \
    !in-bridge-port !in-bridge-port-list !in-interface !in-interface-list \
    !ingress-priority !ipsec-policy !ipv4-options !layer7-protocol !limit \
    log=no log-prefix="" new-packet-mark=wan-out-att !nth !out-bridge-port \
    !out-bridge-port-list out-interface=ether2-WAN-ATT !out-interface-list \
    !packet-mark !packet-size passthrough=yes !per-connection-classifier \
    !port !priority !protocol !psd !random !routing-mark !src-address \
    !src-address-list !src-address-type !src-mac-address !src-port !tcp-flags \
    !tcp-mss !time !tls-host !ttl
add action=mark-connection chain=postrouting comment=\
    "ZT: Mark outgoing ZeroTier connections" !connection-bytes \
    !connection-limit !connection-mark !connection-nat-state !connection-rate \
    !connection-state !connection-type !content disabled=yes !dscp \
    !dst-address !dst-address-list !dst-address-type !dst-limit !dst-port \
    !fragment !hotspot !icmp-options !in-bridge-port !in-bridge-port-list \
    !in-interface !in-interface-list !ingress-priority !ipsec-policy \
    !ipv4-options !layer7-protocol !limit log=no log-prefix="" \
    new-connection-mark=zerotier-connection !nth !out-bridge-port \
    !out-bridge-port-list out-interface=myZeroTier !out-interface-list \
    !packet-mark !packet-size passthrough=yes !per-connection-classifier \
    !port !priority !protocol !psd !random !routing-mark !src-address \
    !src-address-list !src-address-type !src-mac-address !src-port !tcp-flags \
    !tcp-mss !time !tls-host !ttl
add action=mark-packet chain=postrouting comment="ZT: Mark ZeroTier packets" \
    !connection-bytes !connection-limit connection-mark=zerotier-connection \
    !connection-nat-state !connection-rate !connection-state !connection-type \
    !content disabled=yes !dscp !dst-address !dst-address-list \
    !dst-address-type !dst-limit !dst-port !fragment !hotspot !icmp-options \
    !in-bridge-port !in-bridge-port-list !in-interface !in-interface-list \
    !ingress-priority !ipsec-policy !ipv4-options !layer7-protocol !limit \
    log=no log-prefix="" new-packet-mark=zerotier-packet !nth \
    !out-bridge-port !out-bridge-port-list !out-interface !out-interface-list \
    !packet-mark !packet-size passthrough=yes !per-connection-classifier \
    !port !priority !protocol !psd !random !routing-mark !src-address \
    !src-address-list !src-address-type !src-mac-address !src-port !tcp-flags \
    !tcp-mss !time !tls-host !ttl
add action=change-dscp chain=postrouting comment=\
    "ZT: Set DSCP EF (46) for ZeroTier traffic" !connection-bytes \
    !connection-limit !connection-mark !connection-nat-state !connection-rate \
    !connection-state !connection-type !content disabled=yes !dscp \
    !dst-address !dst-address-list !dst-address-type !dst-limit !dst-port \
    !fragment !hotspot !icmp-options !in-bridge-port !in-bridge-port-list \
    !in-interface !in-interface-list !ingress-priority !ipsec-policy \
    !ipv4-options !layer7-protocol !limit log=no log-prefix="" new-dscp=46 \
    !nth !out-bridge-port !out-bridge-port-list !out-interface \
    !out-interface-list packet-mark=zerotier-packet !packet-size passthrough=\
    yes !per-connection-classifier !port !priority !protocol !psd !random \
    !routing-mark !src-address !src-address-list !src-address-type \
    !src-mac-address !src-port !tcp-flags !tcp-mss !time !tls-host !ttl
add action=change-dscp chain=forward comment=\
    "DSCP: GAME_DL CS1 (8) - Game downloads/updates" !connection-bytes \
    !connection-limit connection-mark=QOS_GAME_DL !connection-nat-state \
    !connection-rate !connection-state !connection-type !content disabled=yes \
    !dscp !dst-address !dst-address-list !dst-address-type !dst-limit \
    !dst-port !fragment !hotspot !icmp-options !in-bridge-port \
    !in-bridge-port-list !in-interface !in-interface-list !ingress-priority \
    !ipsec-policy !ipv4-options !layer7-protocol !limit log=no log-prefix="" \
    new-dscp=8 !nth !out-bridge-port !out-bridge-port-list !out-interface \
    !out-interface-list !packet-mark !packet-size passthrough=no \
    !per-connection-classifier !port !priority !protocol !psd !random \
    !routing-mark !src-address !src-address-list !src-address-type \
    !src-mac-address !src-port !tcp-flags !tcp-mss !time !tls-host !ttl
add action=change-dscp chain=forward comment="DSCP: GAMES  EF (46) - Gaming" \
    !connection-bytes !connection-limit connection-mark=GAMES \
    !connection-nat-state !connection-rate !connection-state !connection-type \
    !content disabled=yes !dscp !dst-address !dst-address-list \
    !dst-address-type !dst-limit !dst-port !fragment !hotspot !icmp-options \
    !in-bridge-port !in-bridge-port-list !in-interface !in-interface-list \
    !ingress-priority !ipsec-policy !ipv4-options !layer7-protocol !limit \
    log=no log-prefix="" new-dscp=46 !nth !out-bridge-port \
    !out-bridge-port-list !out-interface !out-interface-list !packet-mark \
    !packet-size passthrough=no !per-connection-classifier !port !priority \
    !protocol !psd !random !routing-mark !src-address !src-address-list \
    !src-address-type !src-mac-address !src-port !tcp-flags !tcp-mss !time \
    !tls-host !ttl
add action=change-dscp chain=forward comment=\
    "DSCP: HIGH  EF (46) - Real-time" !connection-bytes !connection-limit \
    connection-mark=QOS_HIGH !connection-nat-state !connection-rate \
    !connection-state !connection-type !content disabled=yes !dscp \
    !dst-address !dst-address-list !dst-address-type !dst-limit !dst-port \
    !fragment !hotspot !icmp-options !in-bridge-port !in-bridge-port-list \
    !in-interface !in-interface-list !ingress-priority !ipsec-policy \
    !ipv4-options !layer7-protocol !limit log=no log-prefix="" new-dscp=46 \
    !nth !out-bridge-port !out-bridge-port-list !out-interface \
    !out-interface-list !packet-mark !packet-size passthrough=no \
    !per-connection-classifier !port !priority !protocol !psd !random \
    !routing-mark !src-address !src-address-list !src-address-type \
    !src-mac-address !src-port !tcp-flags !tcp-mss !time !tls-host !ttl
add action=change-dscp chain=forward comment=\
    "DSCP: MEDIUM  AF31 (26) - Interactive" !connection-bytes \
    !connection-limit connection-mark=QOS_MEDIUM !connection-nat-state \
    !connection-rate !connection-state !connection-type !content disabled=yes \
    !dscp !dst-address !dst-address-list !dst-address-type !dst-limit \
    !dst-port !fragment !hotspot !icmp-options !in-bridge-port \
    !in-bridge-port-list !in-interface !in-interface-list !ingress-priority \
    !ipsec-policy !ipv4-options !layer7-protocol !limit log=no log-prefix="" \
    new-dscp=26 !nth !out-bridge-port !out-bridge-port-list !out-interface \
    !out-interface-list !packet-mark !packet-size passthrough=no \
    !per-connection-classifier !port !priority !protocol !psd !random \
    !routing-mark !src-address !src-address-list !src-address-type \
    !src-mac-address !src-port !tcp-flags !tcp-mss !time !tls-host !ttl
add action=change-dscp chain=forward comment=\
    "DSCP: LOW  CS1 (8) - Background/Bulk" !connection-bytes \
    !connection-limit connection-mark=QOS_LOW !connection-nat-state \
    !connection-rate !connection-state !connection-type !content disabled=yes \
    !dscp !dst-address !dst-address-list !dst-address-type !dst-limit \
    !dst-port !fragment !hotspot !icmp-options !in-bridge-port \
    !in-bridge-port-list !in-interface !in-interface-list !ingress-priority \
    !ipsec-policy !ipv4-options !layer7-protocol !limit log=no log-prefix="" \
    new-dscp=8 !nth !out-bridge-port !out-bridge-port-list !out-interface \
    !out-interface-list !packet-mark !packet-size passthrough=no \
    !per-connection-classifier !port !priority !protocol !psd !random \
    !routing-mark !src-address !src-address-list !src-address-type \
    !src-mac-address !src-port !tcp-flags !tcp-mss !time !tls-host !ttl
add action=change-dscp chain=forward comment=\
    "DSCP: NORMAL  CS0 (0) - Best Effort" !connection-bytes !connection-limit \
    connection-mark=QOS_NORMAL !connection-nat-state !connection-rate \
    !connection-state !connection-type !content disabled=yes !dscp \
    !dst-address !dst-address-list !dst-address-type !dst-limit !dst-port \
    !fragment !hotspot !icmp-options !in-bridge-port !in-bridge-port-list \
    !in-interface !in-interface-list !ingress-priority !ipsec-policy \
    !ipv4-options !layer7-protocol !limit log=no log-prefix="" new-dscp=0 \
    !nth !out-bridge-port !out-bridge-port-list !out-interface \
    !out-interface-list !packet-mark !packet-size passthrough=no \
    !per-connection-classifier !port !priority !protocol !psd !random \
    !routing-mark !src-address !src-address-list !src-address-type \
    !src-mac-address !src-port !tcp-flags !tcp-mss !time !tls-host !ttl
add action=set-priority chain=postrouting comment=\
    "DSCP: Map DSCP to 802.1p priority on egress" !connection-bytes \
    !connection-limit !connection-mark !connection-nat-state !connection-rate \
    !connection-state !connection-type !content disabled=yes !dscp \
    !dst-address !dst-address-list !dst-address-type !dst-limit !dst-port \
    !fragment !hotspot !icmp-options !in-bridge-port !in-bridge-port-list \
    !in-interface !in-interface-list !ingress-priority !ipsec-policy \
    !ipv4-options !layer7-protocol !limit log=no log-prefix="" new-priority=\
    from-dscp !nth !out-bridge-port !out-bridge-port-list !out-interface \
    !out-interface-list !packet-mark !packet-size passthrough=yes \
    !per-connection-classifier !port !priority !protocol !psd !random \
    !routing-mark !src-address !src-address-list !src-address-type \
    !src-mac-address !src-port !tcp-flags !tcp-mss !time !tls-host !ttl
/ip firewall nat
add action=masquerade chain=srcnat comment="WireGuard NAT to Spectrum" log=no \
    log-prefix=WG-NAT-SPEC: out-interface=ether1-WAN-Spectrum src-address=\
    10.255.255.0/24 !to-addresses !to-ports
add action=masquerade chain=srcnat comment="NAT: LAN -> ZeroTier" \
    out-interface=myZeroTier !to-addresses !to-ports
add action=masquerade chain=srcnat comment="LAN -> Spectrum WAN" \
    out-interface=ether1-WAN-Spectrum !to-addresses !to-ports
add action=masquerade chain=srcnat comment="LAN -> ATT WAN" out-interface=\
    ether2-WAN-ATT !to-addresses !to-ports
add action=dst-nat chain=dstnat comment=\
    "Port forward: Plex Media Server (32400)" !connection-bytes \
    !connection-limit !connection-mark !connection-rate !connection-type \
    !content disabled=yes !dscp !dst-address !dst-address-list \
    !dst-address-type !dst-limit dst-port=32400 !fragment !hotspot \
    !icmp-options !in-bridge-port !in-bridge-port-list in-interface=\
    ether1-WAN-Spectrum !in-interface-list !ingress-priority !ipsec-policy \
    !ipv4-options !layer7-protocol !limit log=no log-prefix="" !nth \
    !out-bridge-port !out-bridge-port-list !out-interface !out-interface-list \
    !packet-mark !packet-size !per-connection-classifier !port !priority \
    protocol=tcp !psd !random !routing-mark !src-address !src-address-list \
    !src-address-type !src-mac-address !src-port !tcp-mss !time to-addresses=\
    10.10.110.221 to-ports=32400 !ttl
add action=dst-nat chain=dstnat comment=\
    "Port forward: Transmission torrent (51413 TCP)" !connection-bytes \
    !connection-limit !connection-mark !connection-rate !connection-type \
    !content disabled=yes !dscp !dst-address !dst-address-list \
    !dst-address-type !dst-limit dst-port=51413 !fragment !hotspot \
    !icmp-options !in-bridge-port !in-bridge-port-list in-interface=\
    ether1-WAN-Spectrum !in-interface-list !ingress-priority !ipsec-policy \
    !ipv4-options !layer7-protocol !limit log=no log-prefix="" !nth \
    !out-bridge-port !out-bridge-port-list !out-interface !out-interface-list \
    !packet-mark !packet-size !per-connection-classifier !port !priority \
    protocol=tcp !psd !random !routing-mark !src-address !src-address-list \
    !src-address-type !src-mac-address !src-port !tcp-mss !time to-addresses=\
    10.10.110.227 to-ports=51413 !ttl
add action=dst-nat chain=dstnat comment=\
    "Port forward: Transmission torrent (51413 UDP)" !connection-bytes \
    !connection-limit !connection-mark !connection-rate !connection-type \
    !content disabled=yes !dscp !dst-address !dst-address-list \
    !dst-address-type !dst-limit dst-port=51413 !fragment !hotspot \
    !icmp-options !in-bridge-port !in-bridge-port-list in-interface=\
    ether1-WAN-Spectrum !in-interface-list !ingress-priority !ipsec-policy \
    !ipv4-options !layer7-protocol !limit log=no log-prefix="" !nth \
    !out-bridge-port !out-bridge-port-list !out-interface !out-interface-list \
    !packet-mark !packet-size !per-connection-classifier !port !priority \
    protocol=udp !psd !random !routing-mark !src-address !src-address-list \
    !src-address-type !src-mac-address !src-port !tcp-mss !time to-addresses=\
    10.10.110.227 to-ports=51413 !ttl
add action=dst-nat chain=dstnat comment="Force UDP DNS to Pi-hole" \
    !connection-bytes !connection-limit !connection-mark !connection-rate \
    !connection-type !content disabled=yes !dscp !dst-address \
    !dst-address-list !dst-address-type !dst-limit dst-port=53 !fragment \
    !hotspot !icmp-options !in-bridge-port !in-bridge-port-list !in-interface \
    !in-interface-list !ingress-priority !ipsec-policy !ipv4-options \
    !layer7-protocol !limit log=no log-prefix="" !nth !out-bridge-port \
    !out-bridge-port-list !out-interface !out-interface-list !packet-mark \
    !packet-size !per-connection-classifier !port !priority protocol=udp !psd \
    !random !routing-mark !src-address !src-address-list !src-address-type \
    !src-mac-address !src-port !tcp-mss !time to-addresses=10.10.110.202 \
    !to-ports !ttl
add action=dst-nat chain=dstnat comment="Force TCP DNS to Pi-hole" \
    !connection-bytes !connection-limit !connection-mark !connection-rate \
    !connection-type !content disabled=yes !dscp !dst-address \
    !dst-address-list !dst-address-type !dst-limit dst-port=53 !fragment \
    !hotspot !icmp-options !in-bridge-port !in-bridge-port-list !in-interface \
    !in-interface-list !ingress-priority !ipsec-policy !ipv4-options \
    !layer7-protocol !limit log=no log-prefix="" !nth !out-bridge-port \
    !out-bridge-port-list !out-interface !out-interface-list !packet-mark \
    !packet-size !per-connection-classifier !port !priority protocol=tcp !psd \
    !random !routing-mark !src-address !src-address-list !src-address-type \
    !src-mac-address !src-port !tcp-mss !time to-addresses=10.10.110.202 \
    !to-ports !ttl
/ip firewall raw
add action=accept chain=prerouting comment="RAW: Allow WireGuard" !content \
    disabled=yes !dscp !dst-address !dst-address-list !dst-address-type \
    !dst-limit dst-port=51820 !fragment !hotspot !icmp-options !in-interface \
    in-interface-list=WAN !ingress-priority !ipsec-policy !ipv4-options \
    !limit log=no log-prefix="" !nth !out-interface !out-interface-list \
    !packet-size !per-connection-classifier !port !priority protocol=udp !psd \
    !random !src-address !src-address-list !src-address-type !src-mac-address \
    !src-port !tcp-flags !tcp-mss !time !tls-host !ttl
add action=accept chain=prerouting comment="RAW: Allow DHCP discover" \
    !content disabled=yes !dscp dst-address=255.255.255.255 !dst-address-list \
    !dst-address-type !dst-limit dst-port=67 !fragment !hotspot !icmp-options \
    !in-interface in-interface-list=VLAN !ingress-priority !ipsec-policy \
    !ipv4-options !limit log=no log-prefix="" !nth !out-interface \
    !out-interface-list !packet-size !per-connection-classifier !port \
    !priority protocol=udp !psd !random src-address=0.0.0.0 !src-address-list \
    !src-address-type !src-mac-address src-port=68 !tcp-flags !tcp-mss !time \
    !tls-host !ttl
add action=drop chain=prerouting comment="RAW: Drop WAN broadcast" !content \
    disabled=yes !dscp !dst-address !dst-address-list dst-address-type=\
    broadcast !dst-limit !dst-port !fragment !hotspot !icmp-options \
    !in-interface in-interface-list=WAN !ingress-priority !ipsec-policy \
    !ipv4-options !limit log=no log-prefix="" !nth !out-interface \
    !out-interface-list !packet-size !per-connection-classifier !port \
    !priority !protocol !psd !random !src-address !src-address-list \
    !src-address-type !src-mac-address !src-port !tcp-flags !tcp-mss !time \
    !tls-host !ttl
add action=drop chain=prerouting comment="RAW: Drop WAN multicast" !content \
    disabled=yes !dscp !dst-address !dst-address-list dst-address-type=\
    multicast !dst-limit !dst-port !fragment !hotspot !icmp-options \
    !in-interface in-interface-list=WAN !ingress-priority !ipsec-policy \
    !ipv4-options !limit log=no log-prefix="" !nth !out-interface \
    !out-interface-list !packet-size !per-connection-classifier !port \
    !priority !protocol !psd !random !src-address !src-address-list \
    !src-address-type !src-mac-address !src-port !tcp-flags !tcp-mss !time \
    !tls-host !ttl
add action=drop chain=prerouting comment="RAW: Block WAN-to-LAN access early" \
    !content disabled=yes !dscp dst-address=10.10.0.0/16 !dst-address-list \
    !dst-address-type !dst-limit !dst-port !fragment !hotspot !icmp-options \
    !in-interface in-interface-list=WAN !ingress-priority !ipsec-policy \
    !ipv4-options !limit log=no log-prefix="" !nth !out-interface \
    !out-interface-list !packet-size !per-connection-classifier !port \
    !priority !protocol !psd !random !src-address !src-address-list \
    !src-address-type !src-mac-address !src-port !tcp-flags !tcp-mss !time \
    !tls-host !ttl
add action=jump chain=prerouting comment="RAW: TCP sanity inspection" \
    !content disabled=yes !dscp !dst-address !dst-address-list \
    !dst-address-type !dst-limit !dst-port !fragment !hotspot !icmp-options \
    !in-interface !in-interface-list !ingress-priority !ipsec-policy \
    !ipv4-options jump-target=bad_tcp !limit log=no log-prefix="" !nth \
    !out-interface !out-interface-list !packet-size \
    !per-connection-classifier !port !priority protocol=tcp !psd !random \
    !src-address !src-address-list !src-address-type !src-mac-address \
    !src-port !tcp-flags !tcp-mss !time !tls-host !ttl
add action=drop chain=bad_tcp comment="RAW: Bad TCP FIN+SYN" !content \
    disabled=yes !dscp !dst-address !dst-address-list !dst-address-type \
    !dst-limit !dst-port !fragment !hotspot !icmp-options !in-interface \
    !in-interface-list !ingress-priority !ipsec-policy !ipv4-options !limit \
    log=no log-prefix="" !nth !out-interface !out-interface-list !packet-size \
    !per-connection-classifier !port !priority protocol=tcp !psd !random \
    !src-address !src-address-list !src-address-type !src-mac-address \
    !src-port tcp-flags=fin,syn !tcp-mss !time !tls-host !ttl
add action=drop chain=bad_tcp comment="RAW: Bad TCP SYN+RST" !content \
    disabled=yes !dscp !dst-address !dst-address-list !dst-address-type \
    !dst-limit !dst-port !fragment !hotspot !icmp-options !in-interface \
    !in-interface-list !ingress-priority !ipsec-policy !ipv4-options !limit \
    log=no log-prefix="" !nth !out-interface !out-interface-list !packet-size \
    !per-connection-classifier !port !priority protocol=tcp !psd !random \
    !src-address !src-address-list !src-address-type !src-mac-address \
    !src-port tcp-flags=syn,rst !tcp-mss !time !tls-host !ttl
add action=drop chain=bad_tcp comment="RAW: No TCP flags" !content disabled=\
    yes !dscp !dst-address !dst-address-list !dst-address-type !dst-limit \
    !dst-port !fragment !hotspot !icmp-options !in-interface \
    !in-interface-list !ingress-priority !ipsec-policy !ipv4-options !limit \
    log=no log-prefix="" !nth !out-interface !out-interface-list !packet-size \
    !per-connection-classifier !port !priority protocol=tcp !psd !random \
    !src-address !src-address-list !src-address-type !src-mac-address \
    !src-port tcp-flags=!fin,!syn,!rst,!ack !tcp-mss !time !tls-host !ttl
add action=drop chain=bad_tcp comment="RAW: Bad TCP FIN+RST" !content \
    disabled=yes !dscp !dst-address !dst-address-list !dst-address-type \
    !dst-limit !dst-port !fragment !hotspot !icmp-options !in-interface \
    !in-interface-list !ingress-priority !ipsec-policy !ipv4-options !limit \
    log=no log-prefix="" !nth !out-interface !out-interface-list !packet-size \
    !per-connection-classifier !port !priority protocol=tcp !psd !random \
    !src-address !src-address-list !src-address-type !src-mac-address \
    !src-port tcp-flags=fin,rst !tcp-mss !time !tls-host !ttl
add action=drop chain=bad_tcp comment="RAW: FIN without ACK" !content \
    disabled=yes !dscp !dst-address !dst-address-list !dst-address-type \
    !dst-limit !dst-port !fragment !hotspot !icmp-options !in-interface \
    !in-interface-list !ingress-priority !ipsec-policy !ipv4-options !limit \
    log=no log-prefix="" !nth !out-interface !out-interface-list !packet-size \
    !per-connection-classifier !port !priority protocol=tcp !psd !random \
    !src-address !src-address-list !src-address-type !src-mac-address \
    !src-port tcp-flags=fin,!ack !tcp-mss !time !tls-host !ttl
add action=drop chain=bad_tcp comment="RAW: FIN+URG" !content disabled=yes \
    !dscp !dst-address !dst-address-list !dst-address-type !dst-limit \
    !dst-port !fragment !hotspot !icmp-options !in-interface \
    !in-interface-list !ingress-priority !ipsec-policy !ipv4-options !limit \
    log=no log-prefix="" !nth !out-interface !out-interface-list !packet-size \
    !per-connection-classifier !port !priority protocol=tcp !psd !random \
    !src-address !src-address-list !src-address-type !src-mac-address \
    !src-port tcp-flags=fin,urg !tcp-mss !time !tls-host !ttl
add action=drop chain=bad_tcp comment="RAW: RST+URG" !content disabled=yes \
    !dscp !dst-address !dst-address-list !dst-address-type !dst-limit \
    !dst-port !fragment !hotspot !icmp-options !in-interface \
    !in-interface-list !ingress-priority !ipsec-policy !ipv4-options !limit \
    log=no log-prefix="" !nth !out-interface !out-interface-list !packet-size \
    !per-connection-classifier !port !priority protocol=tcp !psd !random \
    !src-address !src-address-list !src-address-type !src-mac-address \
    !src-port tcp-flags=rst,urg !tcp-mss !time !tls-host !ttl
add action=accept chain=prerouting comment="RAW: Accept rest of WAN traffic" \
    !content disabled=yes !dscp !dst-address !dst-address-list \
    !dst-address-type !dst-limit !dst-port !fragment !hotspot !icmp-options \
    !in-interface in-interface-list=WAN !ingress-priority !ipsec-policy \
    !ipv4-options !limit log=no log-prefix="" !nth !out-interface \
    !out-interface-list !packet-size !per-connection-classifier !port \
    !priority !protocol !psd !random !src-address !src-address-list \
    !src-address-type !src-mac-address !src-port !tcp-flags !tcp-mss !time \
    !tls-host !ttl
/ip firewall service-port
set ftp disabled=no ports=21
set tftp disabled=yes ports=69
set irc disabled=yes ports=6667,6668,7000
set h323 disabled=yes
set sip disabled=yes ports=5060,5061 sip-direct-media=yes sip-timeout=1h
set pptp disabled=yes
set rtsp disabled=yes ports=554
set udplite disabled=yes
set dccp disabled=no
set sctp disabled=yes
/ip hotspot service-port
set ftp disabled=no ports=21
/ip hotspot user
set [ find default=yes ] comment="counters and limits for trial users" \
    disabled=no name=default-trial
/ip ipsec identity
add auth-method=pre-shared-key disabled=no generate-policy=no peer=\
    icsolutions
/ip ipsec policy
set 0 disabled=yes dst-address=::/0 group=default proposal=default protocol=\
    all src-address=::/0 template=yes
add action=encrypt disabled=yes dst-address=172.31.0.0/24 dst-port=any \
    ipsec-protocols=esp level=require peer=icsolutions proposal=icsolutions \
    protocol=all sa-dst-address=:: sa-src-address=:: src-address=\
    10.10.110.0/24 src-port=any tunnel=yes
add action=encrypt disabled=yes dst-address=10.153.0.0/16 dst-port=any \
    ipsec-protocols=esp level=require peer=icsolutions proposal=icsolutions \
    protocol=all sa-dst-address=:: sa-src-address=:: src-address=\
    10.10.110.0/24 src-port=any tunnel=yes
add action=encrypt disabled=yes dst-address=172.26.0.0/16 dst-port=any \
    ipsec-protocols=esp level=require peer=icsolutions proposal=icsolutions \
    protocol=all sa-dst-address=:: sa-src-address=:: src-address=\
    10.10.110.0/24 src-port=any tunnel=yes
add action=encrypt disabled=yes dst-address=172.26.0.0/16 dst-port=any \
    ipsec-protocols=esp level=require peer=icsolutions proposal=icsolutions \
    protocol=all sa-dst-address=:: sa-src-address=:: src-address=\
    10.10.140.0/24 src-port=any tunnel=yes
add action=encrypt disabled=yes dst-address=172.20.0.0/16 dst-port=any \
    ipsec-protocols=esp level=require peer=icsolutions proposal=icsolutions \
    protocol=all sa-dst-address=:: sa-src-address=:: src-address=\
    10.10.110.0/24 src-port=any tunnel=yes
add action=encrypt disabled=yes dst-address=10.253.0.0/16 dst-port=any \
    ipsec-protocols=esp level=require peer=icsolutions proposal=icsolutions \
    protocol=all sa-dst-address=:: sa-src-address=:: src-address=\
    10.10.110.0/24 src-port=any tunnel=yes
add action=encrypt disabled=yes dst-address=10.252.0.0/16 dst-port=any \
    ipsec-protocols=esp level=require peer=icsolutions proposal=icsolutions \
    protocol=all sa-dst-address=:: sa-src-address=:: src-address=\
    10.10.110.0/24 src-port=any tunnel=yes
add action=encrypt disabled=yes dst-address=172.19.16.0/24 dst-port=any \
    ipsec-protocols=esp level=require peer=icsolutions proposal=icsolutions \
    protocol=all sa-dst-address=:: sa-src-address=:: src-address=\
    10.10.110.0/24 src-port=any tunnel=yes
/ip ipsec settings
set accounting=yes interim-update=0s xauth-use-radius=no
/ip media settings
set thumbnails=""
/ip nat-pmp
set enabled=no
/ip proxy
set always-from-cache=no anonymous=no cache-administrator=webmaster \
    cache-hit-dscp=4 cache-on-disk=no cache-path=web-proxy enabled=no \
    max-cache-object-size=2048KiB max-cache-size=unlimited \
    max-client-connections=600 max-fresh-time=3d max-server-connections=600 \
    parent-proxy=:: parent-proxy-port=0 port=8080 serialize-connections=no \
    src-address=::
/ip route
add check-gateway=ping comment="Force ATT_OUT to ATT WAN" disabled=no \
    distance=1 dst-address=0.0.0.0/0 gateway=99.126.112.1 pref-src="" \
    routing-table=to_ATT scope=30 suppress-hw-offload=no target-scope=10
add check-gateway=ping comment=Spectrum disabled=no distance=1 dst-address=\
    0.0.0.0/0 gateway=70.123.224.1 pref-src=0.0.0.0 routing-table=main scope=\
    30 suppress-hw-offload=no target-scope=10
add check-gateway=arp comment=ATT disabled=no distance=2 dst-address=\
    0.0.0.0/0 gateway=192.168.2.254 pref-src=0.0.0.0 routing-table=main \
    scope=30 suppress-hw-offload=no target-scope=10
add disabled=no distance=1 dst-address=10.252.255.0/24 gateway=10.255.255.3 \
    pref-src=0.0.0.0 routing-table=main scope=30 suppress-hw-offload=no \
    target-scope=10
add comment="Route to AT&T gateway via WAN-ATT" dst-address=192.168.2.254/32 \
    gateway=192.168.2.1
add check-gateway=ping comment="Backup to Spectrum if ATT fails" distance=2 \
    dst-address=0.0.0.0/0 gateway=70.123.224.1 routing-table=to_ATT
add comment="Route to ATT public gateway for check-gateway" dst-address=\
    99.126.112.1/32 gateway=192.168.2.254
/ip service
set ftp address="" disabled=yes max-sessions=20 port=21 vrf=main
set ssh address=10.10.110.0/24,10.10.99.0/24,172.27.27.0/24 disabled=no \
    max-sessions=20 port=22 vrf=main
set telnet address="" disabled=yes max-sessions=20 port=23 vrf=main
set www address="" disabled=yes max-sessions=20 port=80 vrf=main
set www-ssl address=10.10.99.0/24,10.10.110.0/24,172.27.27.0/24 certificate=\
    CAPsMAN-CA-2CC81BFF5F45 disabled=no max-sessions=20 port=443 tls-version=\
    any vrf=main
set winbox address=\
    10.10.110.0/24,10.10.99.0/24,172.27.27.0/24,10.255.255.2/32 disabled=no \
    max-sessions=20 port=8291 vrf=main
set api address=10.10.110.0/24,10.10.99.0/24,172.27.27.0/24 disabled=no \
    max-sessions=20 port=8728 vrf=main
set api-ssl address="" certificate=none disabled=yes max-sessions=20 port=\
    8729 tls-version=any vrf=main
/ip smb shares
set [ find default=yes ] comment="default share" directory=/pub disabled=yes \
    invalid-users="" name=pub read-only=no require-encryption=no valid-users=\
    ""
/ip socks
set auth-method=none connection-idle-timeout=2m enabled=no max-connections=\
    200 port=1080 version=4 vrf=main
/ip ssh
set always-allow-password-login=yes ciphers=auto forwarding-enabled=both \
    host-key-size=2048 host-key-type=rsa strong-crypto=yes
/ip tftp
add allow=yes allow-overwrite=no allow-rollover=no disabled=no ip-addresses=\
    "" read-only=yes reading-window-size=none real-filename=\
    R750_200.18.7.101.244.bl7 req-filename=R750_200.18.7.101.244.bl7
add allow=yes allow-overwrite=no allow-rollover=no disabled=no ip-addresses=\
    "" read-only=yes reading-window-size=none real-filename=dummy.rcks \
    req-filename=dummy.rcks
add allow=yes allow-overwrite=no allow-rollover=no disabled=no ip-addresses=\
    "" read-only=yes reading-window-size=none real-filename=dummy.rcks \
    req-filename=dummy.rcks
add allow=yes allow-overwrite=no allow-rollover=no disabled=no ip-addresses=\
    "" read-only=yes reading-window-size=none real-filename=\
    R750_200.18.7.101.244.bl7 req-filename=R750_200.18.7.101.244.bl7
/ip tftp settings
set max-block-size=4096
/ip traffic-flow
set active-flow-timeout=30m cache-entries=256k enabled=yes \
    inactive-flow-timeout=15s interfaces=all packet-sampling=no \
    sampling-interval=0 sampling-space=0
/ip traffic-flow ipfix
set bytes=yes dst-address=yes dst-address-mask=yes dst-mac-address=yes \
    dst-port=yes first-forwarded=yes gateway=yes icmp-code=yes icmp-type=yes \
    igmp-type=yes in-interface=yes ip-header-length=yes ip-total-length=yes \
    ipv6-flow-label=yes is-multicast=yes last-forwarded=yes nat-dst-address=\
    yes nat-dst-port=yes nat-events=no nat-src-address=yes nat-src-port=yes \
    out-interface=yes packets=yes protocol=yes src-address=yes \
    src-address-mask=yes src-mac-address=yes src-port=yes sys-init-time=yes \
    tcp-ack-num=yes tcp-flags=yes tcp-seq-num=yes tcp-window-size=yes tos=yes \
    ttl=yes udp-length=yes
/ip traffic-flow target
add disabled=no dst-address=10.10.110.226 port=6363 src-address=0.0.0.0 \
    v9-template-refresh=20 v9-template-timeout=30m version=9
/ip upnp
set allow-disable-external-interface=no enabled=no show-dummy-rule=yes
/ipv6 address
add address=::1/64 advertise=yes auto-link-local=yes disabled=yes eui-64=no \
    from-pool=ipv6-Spectrum interface=vlan120-IOT no-dad=no
add address=::1/64 advertise=yes auto-link-local=yes disabled=yes eui-64=no \
    from-pool=ipv6-Spectrum interface=vlan110-trusted no-dad=no
/ipv6 dhcp-client
add accept-prefix-without-address=yes add-default-route=yes \
    allow-reconfigure=no check-gateway=none !custom-iana-id !custom-iapd-id \
    default-route-distance=1 default-route-tables=default dhcp-options="" \
    dhcp-options="" disabled=yes interface=ether1-WAN-Spectrum pool-name=ipv6 \
    pool-prefix-length=64 prefix-address-lists="" prefix-hint=::/56 request=\
    address,prefix use-peer-dns=no validate-server-duid=yes
add accept-prefix-without-address=yes add-default-route=yes \
    allow-reconfigure=no check-gateway=none !custom-iana-id !custom-iapd-id \
    default-route-distance=1 default-route-tables=default dhcp-options="" \
    dhcp-options="" disabled=yes interface=ether2-WAN-ATT pool-name=\
    ipv6-Spectrum pool-prefix-length=64 prefix-address-lists="" prefix-hint=\
    ::/56 request=address,prefix use-peer-dns=no validate-server-duid=yes
/ipv6 firewall filter
add action=drop chain=input comment="crowdsec input drop rules" \
    !connection-bytes !connection-limit !connection-mark \
    !connection-nat-state !connection-rate !connection-state !connection-type \
    !content disabled=yes !dscp !dst-address !dst-address-list \
    !dst-address-type !dst-limit !dst-port !headers !hop-limit !icmp-options \
    !in-bridge-port !in-bridge-port-list !in-interface in-interface-list=WAN \
    !ingress-priority !ipsec-policy !limit log=no log-prefix="" !nth \
    !out-bridge-port !out-bridge-port-list !out-interface !out-interface-list \
    !packet-mark !packet-size !per-connection-classifier !port !priority \
    !protocol !random !routing-mark !src-address src-address-list=crowdsec \
    !src-address-type !src-mac-address !src-port !tcp-flags !tcp-mss !time \
    !tls-host
add action=drop chain=forward comment="crowdsec forward drop rules" \
    !connection-bytes !connection-limit !connection-mark \
    !connection-nat-state !connection-rate !connection-state !connection-type \
    !content disabled=yes !dscp !dst-address !dst-address-list \
    !dst-address-type !dst-limit !dst-port !headers !hop-limit !icmp-options \
    !in-bridge-port !in-bridge-port-list !in-interface in-interface-list=WAN \
    !ingress-priority !ipsec-policy !limit log=no log-prefix="" !nth \
    !out-bridge-port !out-bridge-port-list !out-interface !out-interface-list \
    !packet-mark !packet-size !per-connection-classifier !port !priority \
    !protocol !random !routing-mark !src-address src-address-list=crowdsec \
    !src-address-type !src-mac-address !src-port !tcp-flags !tcp-mss !time \
    !tls-host
add action=drop chain=input comment="Drop invalid" !connection-bytes \
    !connection-limit !connection-mark !connection-nat-state !connection-rate \
    connection-state=invalid !connection-type !content disabled=yes !dscp \
    !dst-address !dst-address-list !dst-address-type !dst-limit !dst-port \
    !headers !hop-limit !icmp-options !in-bridge-port !in-bridge-port-list \
    !in-interface !in-interface-list !ingress-priority !ipsec-policy !limit \
    log=no log-prefix="" !nth !out-bridge-port !out-bridge-port-list \
    !out-interface !out-interface-list !packet-mark !packet-size \
    !per-connection-classifier !port !priority !protocol !random \
    !routing-mark !src-address !src-address-list !src-address-type \
    !src-mac-address !src-port !tcp-flags !tcp-mss !time !tls-host
add action=accept chain=input comment="Accept established" !connection-bytes \
    !connection-limit !connection-mark !connection-nat-state !connection-rate \
    connection-state=established,related !connection-type !content disabled=\
    yes !dscp !dst-address !dst-address-list !dst-address-type !dst-limit \
    !dst-port !headers !hop-limit !icmp-options !in-bridge-port \
    !in-bridge-port-list !in-interface !in-interface-list !ingress-priority \
    !ipsec-policy !limit log=no log-prefix="" !nth !out-bridge-port \
    !out-bridge-port-list !out-interface !out-interface-list !packet-mark \
    !packet-size !per-connection-classifier !port !priority !protocol !random \
    !routing-mark !src-address !src-address-list !src-address-type \
    !src-mac-address !src-port !tcp-flags !tcp-mss !time !tls-host
add action=accept chain=input !connection-bytes !connection-limit \
    !connection-mark !connection-nat-state !connection-rate !connection-state \
    !connection-type !content disabled=yes !dscp !dst-address \
    !dst-address-list !dst-address-type !dst-limit !dst-port !headers \
    !hop-limit !icmp-options !in-bridge-port !in-bridge-port-list \
    in-interface=ether2-WAN-ATT !in-interface-list !ingress-priority \
    !ipsec-policy limit=10,20:packet log=no log-prefix="" !nth \
    !out-bridge-port !out-bridge-port-list !out-interface !out-interface-list \
    !packet-mark !packet-size !per-connection-classifier !port !priority \
    protocol=udp !random !routing-mark !src-address !src-address-list \
    !src-address-type !src-mac-address src-port=547 !tcp-flags !tcp-mss !time \
    !tls-host
add action=drop chain=input comment="Drop ext DHCP >10/sec" !connection-bytes \
    !connection-limit !connection-mark !connection-nat-state !connection-rate \
    !connection-state !connection-type !content disabled=yes !dscp \
    !dst-address !dst-address-list !dst-address-type !dst-limit !dst-port \
    !headers !hop-limit !icmp-options !in-bridge-port !in-bridge-port-list \
    in-interface=ether2-WAN-ATT !in-interface-list !ingress-priority \
    !ipsec-policy !limit log=no log-prefix="" !nth !out-bridge-port \
    !out-bridge-port-list !out-interface !out-interface-list !packet-mark \
    !packet-size !per-connection-classifier !port !priority protocol=udp \
    !random !routing-mark !src-address !src-address-list !src-address-type \
    !src-mac-address src-port=547 !tcp-flags !tcp-mss !time !tls-host
add action=accept chain=input !connection-bytes !connection-limit \
    !connection-mark !connection-nat-state !connection-rate !connection-state \
    !connection-type !content disabled=yes !dscp !dst-address \
    !dst-address-list !dst-address-type !dst-limit !dst-port !headers \
    !hop-limit !icmp-options !in-bridge-port !in-bridge-port-list \
    in-interface=ether2-WAN-ATT !in-interface-list !ingress-priority \
    !ipsec-policy limit=10,20:packet log=no log-prefix="" !nth \
    !out-bridge-port !out-bridge-port-list !out-interface !out-interface-list \
    !packet-mark !packet-size !per-connection-classifier !port !priority \
    protocol=icmpv6 !random !routing-mark !src-address !src-address-list \
    !src-address-type !src-mac-address !src-port !tcp-flags !tcp-mss !time \
    !tls-host
add action=drop chain=input comment="Drop ext ICMP >10/sec" !connection-bytes \
    !connection-limit !connection-mark !connection-nat-state !connection-rate \
    !connection-state !connection-type !content disabled=yes !dscp \
    !dst-address !dst-address-list !dst-address-type !dst-limit !dst-port \
    !headers !hop-limit !icmp-options !in-bridge-port !in-bridge-port-list \
    in-interface=ether2-WAN-ATT !in-interface-list !ingress-priority \
    !ipsec-policy !limit log=no log-prefix="" !nth !out-bridge-port \
    !out-bridge-port-list !out-interface !out-interface-list !packet-mark \
    !packet-size !per-connection-classifier !port !priority protocol=icmpv6 \
    !random !routing-mark !src-address !src-address-list !src-address-type \
    !src-mac-address !src-port !tcp-flags !tcp-mss !time !tls-host
add action=accept chain=input comment="Accept internal ICMP" \
    !connection-bytes !connection-limit !connection-mark \
    !connection-nat-state !connection-rate !connection-state !connection-type \
    !content disabled=yes !dscp !dst-address !dst-address-list \
    !dst-address-type !dst-limit !dst-port !headers !hop-limit !icmp-options \
    !in-bridge-port !in-bridge-port-list in-interface=!ether2-WAN-ATT \
    !in-interface-list !ingress-priority !ipsec-policy !limit log=no \
    log-prefix="" !nth !out-bridge-port !out-bridge-port-list !out-interface \
    !out-interface-list !packet-mark !packet-size !per-connection-classifier \
    !port !priority protocol=icmpv6 !random !routing-mark !src-address \
    !src-address-list !src-address-type !src-mac-address !src-port !tcp-flags \
    !tcp-mss !time !tls-host
add action=drop chain=input comment="Drop external" !connection-bytes \
    !connection-limit !connection-mark !connection-nat-state !connection-rate \
    !connection-state !connection-type !content disabled=yes !dscp \
    !dst-address !dst-address-list !dst-address-type !dst-limit !dst-port \
    !headers !hop-limit !icmp-options !in-bridge-port !in-bridge-port-list \
    in-interface=ether2-WAN-ATT !in-interface-list !ingress-priority \
    !ipsec-policy !limit log=no log-prefix="" !nth !out-bridge-port \
    !out-bridge-port-list !out-interface !out-interface-list !packet-mark \
    !packet-size !per-connection-classifier !port !priority !protocol !random \
    !routing-mark !src-address !src-address-list !src-address-type \
    !src-mac-address !src-port !tcp-flags !tcp-mss !time !tls-host
add action=reject chain=input comment="Reject everything else" \
    !connection-bytes !connection-limit !connection-mark \
    !connection-nat-state !connection-rate !connection-state !connection-type \
    !content disabled=yes !dscp !dst-address !dst-address-list \
    !dst-address-type !dst-limit !dst-port !headers !hop-limit !icmp-options \
    !in-bridge-port !in-bridge-port-list !in-interface !in-interface-list \
    !ingress-priority !ipsec-policy !limit log=no log-prefix="" !nth \
    !out-bridge-port !out-bridge-port-list !out-interface !out-interface-list \
    !packet-mark !packet-size !per-connection-classifier !port !priority \
    !protocol !random reject-with=icmp-no-route !routing-mark !src-address \
    !src-address-list !src-address-type !src-mac-address !src-port !tcp-flags \
    !tcp-mss !time !tls-host
add action=accept chain=output comment="Accept all" !connection-bytes \
    !connection-limit !connection-mark !connection-nat-state !connection-rate \
    !connection-state !connection-type !content disabled=yes !dscp \
    !dst-address !dst-address-list !dst-address-type !dst-limit !dst-port \
    !headers !hop-limit !icmp-options !in-bridge-port !in-bridge-port-list \
    !in-interface !in-interface-list !ingress-priority !ipsec-policy !limit \
    log=no log-prefix="" !nth !out-bridge-port !out-bridge-port-list \
    !out-interface !out-interface-list !packet-mark !packet-size \
    !per-connection-classifier !port !priority !protocol !random \
    !routing-mark !src-address !src-address-list !src-address-type \
    !src-mac-address !src-port !tcp-flags !tcp-mss !time !tls-host
add action=drop chain=forward comment="Drop invalid" !connection-bytes \
    !connection-limit !connection-mark !connection-nat-state !connection-rate \
    connection-state=invalid !connection-type !content disabled=yes !dscp \
    !dst-address !dst-address-list !dst-address-type !dst-limit !dst-port \
    !headers !hop-limit !icmp-options !in-bridge-port !in-bridge-port-list \
    !in-interface !in-interface-list !ingress-priority !ipsec-policy !limit \
    log=no log-prefix="" !nth !out-bridge-port !out-bridge-port-list \
    !out-interface !out-interface-list !packet-mark !packet-size \
    !per-connection-classifier !port !priority !protocol !random \
    !routing-mark !src-address !src-address-list !src-address-type \
    !src-mac-address !src-port !tcp-flags !tcp-mss !time !tls-host
add action=accept chain=forward comment="Accept established" \
    !connection-bytes !connection-limit !connection-mark \
    !connection-nat-state !connection-rate connection-state=\
    established,related !connection-type !content disabled=yes !dscp \
    !dst-address !dst-address-list !dst-address-type !dst-limit !dst-port \
    !headers !hop-limit !icmp-options !in-bridge-port !in-bridge-port-list \
    !in-interface !in-interface-list !ingress-priority !ipsec-policy !limit \
    log=no log-prefix="" !nth !out-bridge-port !out-bridge-port-list \
    !out-interface !out-interface-list !packet-mark !packet-size \
    !per-connection-classifier !port !priority !protocol !random \
    !routing-mark !src-address !src-address-list !src-address-type \
    !src-mac-address !src-port !tcp-flags !tcp-mss !time !tls-host
add action=accept chain=forward !connection-bytes !connection-limit \
    !connection-mark !connection-nat-state !connection-rate !connection-state \
    !connection-type !content disabled=yes !dscp !dst-address \
    !dst-address-list !dst-address-type !dst-limit !dst-port !headers \
    !hop-limit !icmp-options !in-bridge-port !in-bridge-port-list \
    in-interface=ether2-WAN-ATT !in-interface-list !ingress-priority \
    !ipsec-policy limit=20,50:packet log=no log-prefix="" !nth \
    !out-bridge-port !out-bridge-port-list !out-interface !out-interface-list \
    !packet-mark !packet-size !per-connection-classifier !port !priority \
    protocol=icmpv6 !random !routing-mark !src-address !src-address-list \
    !src-address-type !src-mac-address !src-port !tcp-flags !tcp-mss !time \
    !tls-host
add action=drop chain=forward comment="Drop ext ICMP >20/sec" \
    !connection-bytes !connection-limit !connection-mark \
    !connection-nat-state !connection-rate !connection-state !connection-type \
    !content disabled=yes !dscp !dst-address !dst-address-list \
    !dst-address-type !dst-limit !dst-port !headers !hop-limit !icmp-options \
    !in-bridge-port !in-bridge-port-list in-interface=ether2-WAN-ATT \
    !in-interface-list !ingress-priority !ipsec-policy !limit log=no \
    log-prefix="" !nth !out-bridge-port !out-bridge-port-list !out-interface \
    !out-interface-list !packet-mark !packet-size !per-connection-classifier \
    !port !priority protocol=icmpv6 !random !routing-mark !src-address \
    !src-address-list !src-address-type !src-mac-address !src-port !tcp-flags \
    !tcp-mss !time !tls-host
add action=accept chain=forward comment="Accept internal" !connection-bytes \
    !connection-limit !connection-mark !connection-nat-state !connection-rate \
    !connection-state !connection-type !content disabled=yes !dscp \
    !dst-address !dst-address-list !dst-address-type !dst-limit !dst-port \
    !headers !hop-limit !icmp-options !in-bridge-port !in-bridge-port-list \
    in-interface=!ether2-WAN-ATT !in-interface-list !ingress-priority \
    !ipsec-policy !limit log=no log-prefix="" !nth !out-bridge-port \
    !out-bridge-port-list !out-interface !out-interface-list !packet-mark \
    !packet-size !per-connection-classifier !port !priority !protocol !random \
    !routing-mark !src-address !src-address-list !src-address-type \
    !src-mac-address !src-port !tcp-flags !tcp-mss !time !tls-host
add action=accept chain=forward comment="Accept outgoing" !connection-bytes \
    !connection-limit !connection-mark !connection-nat-state !connection-rate \
    !connection-state !connection-type !content disabled=yes !dscp \
    !dst-address !dst-address-list !dst-address-type !dst-limit !dst-port \
    !headers !hop-limit !icmp-options !in-bridge-port !in-bridge-port-list \
    !in-interface !in-interface-list !ingress-priority !ipsec-policy !limit \
    log=no log-prefix="" !nth !out-bridge-port !out-bridge-port-list \
    out-interface=ether2-WAN-ATT !out-interface-list !packet-mark \
    !packet-size !per-connection-classifier !port !priority !protocol !random \
    !routing-mark !src-address !src-address-list !src-address-type \
    !src-mac-address !src-port !tcp-flags !tcp-mss !time !tls-host
add action=drop chain=forward comment="Drop external" !connection-bytes \
    !connection-limit !connection-mark !connection-nat-state !connection-rate \
    !connection-state !connection-type !content disabled=yes !dscp \
    !dst-address !dst-address-list !dst-address-type !dst-limit !dst-port \
    !headers !hop-limit !icmp-options !in-bridge-port !in-bridge-port-list \
    in-interface=ether2-WAN-ATT !in-interface-list !ingress-priority \
    !ipsec-policy !limit log=no log-prefix="" !nth !out-bridge-port \
    !out-bridge-port-list !out-interface !out-interface-list !packet-mark \
    !packet-size !per-connection-classifier !port !priority !protocol !random \
    !routing-mark !src-address !src-address-list !src-address-type \
    !src-mac-address !src-port !tcp-flags !tcp-mss !time !tls-host
add action=reject chain=forward comment="Reject everything else" \
    !connection-bytes !connection-limit !connection-mark \
    !connection-nat-state !connection-rate !connection-state !connection-type \
    !content disabled=yes !dscp !dst-address !dst-address-list \
    !dst-address-type !dst-limit !dst-port !headers !hop-limit !icmp-options \
    !in-bridge-port !in-bridge-port-list !in-interface !in-interface-list \
    !ingress-priority !ipsec-policy !limit log=yes log-prefix="" !nth \
    !out-bridge-port !out-bridge-port-list !out-interface !out-interface-list \
    !packet-mark !packet-size !per-connection-classifier !port !priority \
    !protocol !random reject-with=icmp-no-route !routing-mark !src-address \
    !src-address-list !src-address-type !src-mac-address !src-port !tcp-flags \
    !tcp-mss !time !tls-host
/ipv6 firewall mangle
add action=accept chain=output comment="Section Break" !connection-bytes \
    !connection-limit !connection-mark !connection-nat-state !connection-rate \
    !connection-state !connection-type !content disabled=yes !dscp \
    !dst-address !dst-address-list !dst-address-type !dst-limit !dst-port \
    !headers !hop-limit !icmp-options !in-bridge-port !in-bridge-port-list \
    !in-interface !in-interface-list !ingress-priority !ipsec-policy !limit \
    log=no log-prefix="" !nth !out-bridge-port !out-bridge-port-list \
    !out-interface !out-interface-list !packet-mark !packet-size \
    !per-connection-classifier !port !priority !protocol !random \
    !routing-mark !src-address !src-address-list !src-address-type \
    !src-mac-address !src-port !tcp-flags !tcp-mss !time !tls-host
add action=change-dscp chain=input comment=\
    "DSCP - 7 - API Port 8728 (Local Management)" !connection-bytes \
    !connection-limit !connection-mark !connection-nat-state !connection-rate \
    !connection-state !connection-type !content disabled=yes !dscp \
    !dst-address !dst-address-list !dst-address-type !dst-limit dst-port=8728 \
    !headers !hop-limit !icmp-options !in-bridge-port !in-bridge-port-list \
    !in-interface !in-interface-list !ingress-priority !ipsec-policy !limit \
    log=no log-prefix="" new-dscp=7 !nth !out-bridge-port \
    !out-bridge-port-list !out-interface !out-interface-list !packet-mark \
    !packet-size passthrough=yes !per-connection-classifier !port !priority \
    protocol=tcp !random !routing-mark !src-address !src-address-list \
    !src-address-type !src-mac-address !src-port !tcp-flags !tcp-mss !time \
    !tls-host
add action=change-dscp chain=input comment=\
    "DSCP - 7 - Secure API Port 8729 (Local Management)" !connection-bytes \
    !connection-limit !connection-mark !connection-nat-state !connection-rate \
    !connection-state !connection-type !content disabled=yes !dscp \
    !dst-address !dst-address-list !dst-address-type !dst-limit dst-port=8729 \
    !headers !hop-limit !icmp-options !in-bridge-port !in-bridge-port-list \
    !in-interface !in-interface-list !ingress-priority !ipsec-policy !limit \
    log=no log-prefix="" new-dscp=7 !nth !out-bridge-port \
    !out-bridge-port-list !out-interface !out-interface-list !packet-mark \
    !packet-size passthrough=yes !per-connection-classifier !port !priority \
    protocol=tcp !random !routing-mark !src-address !src-address-list \
    !src-address-type !src-mac-address !src-port !tcp-flags !tcp-mss !time \
    !tls-host
add action=change-dscp chain=input comment=\
    "DSCP - 7 - Secure Web Access Port 443 (Local Management)" \
    !connection-bytes !connection-limit !connection-mark \
    !connection-nat-state !connection-rate !connection-state !connection-type \
    !content disabled=yes !dscp !dst-address !dst-address-list \
    !dst-address-type !dst-limit dst-port=443 !headers !hop-limit \
    !icmp-options !in-bridge-port !in-bridge-port-list !in-interface \
    !in-interface-list !ingress-priority !ipsec-policy !limit log=no \
    log-prefix="" new-dscp=7 !nth !out-bridge-port !out-bridge-port-list \
    !out-interface !out-interface-list !packet-mark !packet-size passthrough=\
    yes !per-connection-classifier !port !priority protocol=tcp !random \
    !routing-mark !src-address !src-address-list !src-address-type \
    !src-mac-address !src-port !tcp-flags !tcp-mss !time !tls-host
add action=change-dscp chain=input comment=\
    "DSCP - 7 - Web Access Port 80 (Local Management)" !connection-bytes \
    !connection-limit !connection-mark !connection-nat-state !connection-rate \
    !connection-state !connection-type !content disabled=yes !dscp \
    !dst-address !dst-address-list !dst-address-type !dst-limit dst-port=80 \
    !headers !hop-limit !icmp-options !in-bridge-port !in-bridge-port-list \
    !in-interface !in-interface-list !ingress-priority !ipsec-policy !limit \
    log=no log-prefix="" new-dscp=7 !nth !out-bridge-port \
    !out-bridge-port-list !out-interface !out-interface-list !packet-mark \
    !packet-size passthrough=yes !per-connection-classifier !port !priority \
    protocol=tcp !random !routing-mark !src-address !src-address-list \
    !src-address-type !src-mac-address !src-port !tcp-flags !tcp-mss !time \
    !tls-host
add action=change-dscp chain=input comment=\
    "DSCP - 7 - Winbox Port 8291 (Local Management)" !connection-bytes \
    !connection-limit !connection-mark !connection-nat-state !connection-rate \
    !connection-state !connection-type !content disabled=yes !dscp \
    !dst-address !dst-address-list !dst-address-type !dst-limit dst-port=8291 \
    !headers !hop-limit !icmp-options !in-bridge-port !in-bridge-port-list \
    !in-interface !in-interface-list !ingress-priority !ipsec-policy !limit \
    log=no log-prefix="" new-dscp=7 !nth !out-bridge-port \
    !out-bridge-port-list !out-interface !out-interface-list !packet-mark \
    !packet-size passthrough=yes !per-connection-classifier !port !priority \
    protocol=tcp !random !routing-mark !src-address !src-address-list \
    !src-address-type !src-mac-address !src-port !tcp-flags !tcp-mss !time \
    !tls-host
add action=change-dscp chain=input comment=\
    "DSCP - 7 - Telnet Port 23 (Local Management)" !connection-bytes \
    !connection-limit !connection-mark !connection-nat-state !connection-rate \
    !connection-state !connection-type !content disabled=yes !dscp \
    !dst-address !dst-address-list !dst-address-type !dst-limit dst-port=23 \
    !headers !hop-limit !icmp-options !in-bridge-port !in-bridge-port-list \
    !in-interface !in-interface-list !ingress-priority !ipsec-policy !limit \
    log=no log-prefix="" new-dscp=7 !nth !out-bridge-port \
    !out-bridge-port-list !out-interface !out-interface-list !packet-mark \
    !packet-size passthrough=yes !per-connection-classifier !port !priority \
    protocol=tcp !random !routing-mark !src-address !src-address-list \
    !src-address-type !src-mac-address !src-port !tcp-flags !tcp-mss !time \
    !tls-host
add action=change-dscp chain=input comment=\
    "DSCP - 7 - SSH Port 22 (Local Management)" !connection-bytes \
    !connection-limit !connection-mark !connection-nat-state !connection-rate \
    !connection-state !connection-type !content disabled=yes !dscp \
    !dst-address !dst-address-list !dst-address-type !dst-limit dst-port=22 \
    !headers !hop-limit !icmp-options !in-bridge-port !in-bridge-port-list \
    !in-interface !in-interface-list !ingress-priority !ipsec-policy !limit \
    log=no log-prefix="" new-dscp=7 !nth !out-bridge-port \
    !out-bridge-port-list !out-interface !out-interface-list !packet-mark \
    !packet-size passthrough=yes !per-connection-classifier !port !priority \
    protocol=tcp !random !routing-mark !src-address !src-address-list \
    !src-address-type !src-mac-address !src-port !tcp-flags !tcp-mss !time \
    !tls-host
add action=change-dscp chain=input comment=\
    "DSCP - 7 - FTP Port 21 (Local Management)" !connection-bytes \
    !connection-limit !connection-mark !connection-nat-state !connection-rate \
    !connection-state !connection-type !content disabled=yes !dscp \
    !dst-address !dst-address-list !dst-address-type !dst-limit dst-port=21 \
    !headers !hop-limit !icmp-options !in-bridge-port !in-bridge-port-list \
    !in-interface !in-interface-list !ingress-priority !ipsec-policy !limit \
    log=no log-prefix="" new-dscp=7 !nth !out-bridge-port \
    !out-bridge-port-list !out-interface !out-interface-list !packet-mark \
    !packet-size passthrough=yes !per-connection-classifier !port !priority \
    protocol=tcp !random !routing-mark !src-address !src-address-list \
    !src-address-type !src-mac-address !src-port !tcp-flags !tcp-mss !time \
    !tls-host
add action=accept chain=output comment="Section Break" !connection-bytes \
    !connection-limit !connection-mark !connection-nat-state !connection-rate \
    !connection-state !connection-type !content disabled=yes !dscp \
    !dst-address !dst-address-list !dst-address-type !dst-limit !dst-port \
    !headers !hop-limit !icmp-options !in-bridge-port !in-bridge-port-list \
    !in-interface !in-interface-list !ingress-priority !ipsec-policy !limit \
    log=no log-prefix="" !nth !out-bridge-port !out-bridge-port-list \
    !out-interface !out-interface-list !packet-mark !packet-size \
    !per-connection-classifier !port !priority !protocol !random \
    !routing-mark !src-address !src-address-list !src-address-type \
    !src-mac-address !src-port !tcp-flags !tcp-mss !time !tls-host
add action=change-dscp chain=forward comment=\
    "DSCP - 7 - API Port 8728 (Remote Managemenet)" !connection-bytes \
    !connection-limit !connection-mark !connection-nat-state !connection-rate \
    !connection-state !connection-type !content disabled=yes !dscp \
    !dst-address !dst-address-list !dst-address-type !dst-limit dst-port=8728 \
    !headers !hop-limit !icmp-options !in-bridge-port !in-bridge-port-list \
    !in-interface !in-interface-list !ingress-priority !ipsec-policy !limit \
    log=no log-prefix="" new-dscp=7 !nth !out-bridge-port \
    !out-bridge-port-list !out-interface !out-interface-list !packet-mark \
    !packet-size passthrough=yes !per-connection-classifier !port !priority \
    protocol=tcp !random !routing-mark !src-address src-address-list=\
    "Network Admins" !src-address-type !src-mac-address !src-port !tcp-flags \
    !tcp-mss !time !tls-host
add action=change-dscp chain=forward comment=\
    "DSCP - 7 - Secure API Port 8729 (Remote Managemenet)" !connection-bytes \
    !connection-limit !connection-mark !connection-nat-state !connection-rate \
    !connection-state !connection-type !content disabled=yes !dscp \
    !dst-address !dst-address-list !dst-address-type !dst-limit dst-port=8729 \
    !headers !hop-limit !icmp-options !in-bridge-port !in-bridge-port-list \
    !in-interface !in-interface-list !ingress-priority !ipsec-policy !limit \
    log=no log-prefix="" new-dscp=7 !nth !out-bridge-port \
    !out-bridge-port-list !out-interface !out-interface-list !packet-mark \
    !packet-size passthrough=yes !per-connection-classifier !port !priority \
    protocol=tcp !random !routing-mark !src-address src-address-list=\
    "Network Admins" !src-address-type !src-mac-address !src-port !tcp-flags \
    !tcp-mss !time !tls-host
add action=change-dscp chain=forward comment=\
    "DSCP - 7 - Secure Web Access Port 443 (Remote Managemenet)" \
    !connection-bytes !connection-limit !connection-mark \
    !connection-nat-state !connection-rate !connection-state !connection-type \
    !content disabled=yes !dscp !dst-address !dst-address-list \
    !dst-address-type !dst-limit dst-port=443 !headers !hop-limit \
    !icmp-options !in-bridge-port !in-bridge-port-list !in-interface \
    !in-interface-list !ingress-priority !ipsec-policy !limit log=no \
    log-prefix="" new-dscp=7 !nth !out-bridge-port !out-bridge-port-list \
    !out-interface !out-interface-list !packet-mark !packet-size passthrough=\
    yes !per-connection-classifier !port !priority protocol=tcp !random \
    !routing-mark !src-address src-address-list="Network Admins" \
    !src-address-type !src-mac-address !src-port !tcp-flags !tcp-mss !time \
    !tls-host
add action=change-dscp chain=forward comment=\
    "DSCP - 7 - Web Access Port 80 (Remote Managemenet)" !connection-bytes \
    !connection-limit !connection-mark !connection-nat-state !connection-rate \
    !connection-state !connection-type !content disabled=yes !dscp \
    !dst-address !dst-address-list !dst-address-type !dst-limit dst-port=80 \
    !headers !hop-limit !icmp-options !in-bridge-port !in-bridge-port-list \
    !in-interface !in-interface-list !ingress-priority !ipsec-policy !limit \
    log=no log-prefix="" new-dscp=7 !nth !out-bridge-port \
    !out-bridge-port-list !out-interface !out-interface-list !packet-mark \
    !packet-size passthrough=yes !per-connection-classifier !port !priority \
    protocol=tcp !random !routing-mark !src-address src-address-list=\
    "Network Admins" !src-address-type !src-mac-address !src-port !tcp-flags \
    !tcp-mss !time !tls-host
add action=change-dscp chain=forward comment=\
    "DSCP - 7 - Winbox Port 8291 (Remote Managemenet)" !connection-bytes \
    !connection-limit !connection-mark !connection-nat-state !connection-rate \
    !connection-state !connection-type !content disabled=yes !dscp \
    !dst-address !dst-address-list !dst-address-type !dst-limit dst-port=8291 \
    !headers !hop-limit !icmp-options !in-bridge-port !in-bridge-port-list \
    !in-interface !in-interface-list !ingress-priority !ipsec-policy !limit \
    log=no log-prefix="" new-dscp=7 !nth !out-bridge-port \
    !out-bridge-port-list !out-interface !out-interface-list !packet-mark \
    !packet-size passthrough=yes !per-connection-classifier !port !priority \
    protocol=tcp !random !routing-mark !src-address src-address-list=\
    "Network Admins" !src-address-type !src-mac-address !src-port !tcp-flags \
    !tcp-mss !time !tls-host
add action=change-dscp chain=forward comment=\
    "DSCP - 7 - Telnet Port 23 (Remote Managemenet)" !connection-bytes \
    !connection-limit !connection-mark !connection-nat-state !connection-rate \
    !connection-state !connection-type !content disabled=yes !dscp \
    !dst-address !dst-address-list !dst-address-type !dst-limit dst-port=23 \
    !headers !hop-limit !icmp-options !in-bridge-port !in-bridge-port-list \
    !in-interface !in-interface-list !ingress-priority !ipsec-policy !limit \
    log=no log-prefix="" new-dscp=7 !nth !out-bridge-port \
    !out-bridge-port-list !out-interface !out-interface-list !packet-mark \
    !packet-size passthrough=yes !per-connection-classifier !port !priority \
    protocol=tcp !random !routing-mark !src-address src-address-list=\
    "Network Admins" !src-address-type !src-mac-address !src-port !tcp-flags \
    !tcp-mss !time !tls-host
add action=change-dscp chain=forward comment=\
    "DSCP - 7 - SSH Port 22 (Remote Managemenet)" !connection-bytes \
    !connection-limit !connection-mark !connection-nat-state !connection-rate \
    !connection-state !connection-type !content disabled=yes !dscp \
    !dst-address !dst-address-list !dst-address-type !dst-limit dst-port=22 \
    !headers !hop-limit !icmp-options !in-bridge-port !in-bridge-port-list \
    !in-interface !in-interface-list !ingress-priority !ipsec-policy !limit \
    log=no log-prefix="" new-dscp=7 !nth !out-bridge-port \
    !out-bridge-port-list !out-interface !out-interface-list !packet-mark \
    !packet-size passthrough=yes !per-connection-classifier !port !priority \
    protocol=tcp !random !routing-mark !src-address src-address-list=\
    "Network Admins" !src-address-type !src-mac-address !src-port !tcp-flags \
    !tcp-mss !time !tls-host
add action=change-dscp chain=forward comment=\
    "DSCP - 7 - FTP Port 21 (Remote Managemenet)" !connection-bytes \
    !connection-limit !connection-mark !connection-nat-state !connection-rate \
    !connection-state !connection-type !content disabled=yes !dscp \
    !dst-address !dst-address-list !dst-address-type !dst-limit dst-port=21 \
    !headers !hop-limit !icmp-options !in-bridge-port !in-bridge-port-list \
    !in-interface !in-interface-list !ingress-priority !ipsec-policy !limit \
    log=no log-prefix="" new-dscp=7 !nth !out-bridge-port \
    !out-bridge-port-list !out-interface !out-interface-list !packet-mark \
    !packet-size passthrough=yes !per-connection-classifier !port !priority \
    protocol=tcp !random !routing-mark !src-address src-address-list=\
    "Network Admins" !src-address-type !src-mac-address !src-port !tcp-flags \
    !tcp-mss !time !tls-host
add action=accept chain=output comment="Section Break" !connection-bytes \
    !connection-limit !connection-mark !connection-nat-state !connection-rate \
    !connection-state !connection-type !content disabled=yes !dscp \
    !dst-address !dst-address-list !dst-address-type !dst-limit !dst-port \
    !headers !hop-limit !icmp-options !in-bridge-port !in-bridge-port-list \
    !in-interface !in-interface-list !ingress-priority !ipsec-policy !limit \
    log=no log-prefix="" !nth !out-bridge-port !out-bridge-port-list \
    !out-interface !out-interface-list !packet-mark !packet-size \
    !per-connection-classifier !port !priority !protocol !random \
    !routing-mark !src-address !src-address-list !src-address-type \
    !src-mac-address !src-port !tcp-flags !tcp-mss !time !tls-host
add action=change-dscp chain=forward comment=\
    "DSCP - 5 - PPTP Port 1723 (LAN Traffic)" !connection-bytes \
    !connection-limit !connection-mark !connection-nat-state !connection-rate \
    !connection-state !connection-type !content disabled=yes !dscp \
    !dst-address !dst-address-list !dst-address-type !dst-limit !dst-port \
    !headers !hop-limit !icmp-options !in-bridge-port !in-bridge-port-list \
    !in-interface !in-interface-list !ingress-priority !ipsec-policy !limit \
    log=no log-prefix="" new-dscp=5 !nth !out-bridge-port \
    !out-bridge-port-list !out-interface !out-interface-list !packet-mark \
    !packet-size passthrough=yes !per-connection-classifier port=1723 \
    !priority protocol=tcp !random !routing-mark !src-address \
    !src-address-list !src-address-type !src-mac-address !src-port !tcp-flags \
    !tcp-mss !time !tls-host
add action=change-dscp chain=forward comment=\
    "DSCP - 5 - GRE Protocol (LAN Traffic)" !connection-bytes \
    !connection-limit !connection-mark !connection-nat-state !connection-rate \
    !connection-state !connection-type !content disabled=yes !dscp \
    !dst-address !dst-address-list !dst-address-type !dst-limit !dst-port \
    !headers !hop-limit !icmp-options !in-bridge-port !in-bridge-port-list \
    !in-interface !in-interface-list !ingress-priority !ipsec-policy !limit \
    log=no log-prefix="" new-dscp=5 !nth !out-bridge-port \
    !out-bridge-port-list !out-interface !out-interface-list !packet-mark \
    !packet-size passthrough=yes !per-connection-classifier !port !priority \
    protocol=gre !random !routing-mark !src-address !src-address-list \
    !src-address-type !src-mac-address !src-port !tcp-flags !tcp-mss !time \
    !tls-host
add action=change-dscp chain=forward comment=\
    "DSCP - 5 - L2TP UDP Port 500 (LAN Traffic)" !connection-bytes \
    !connection-limit !connection-mark !connection-nat-state !connection-rate \
    !connection-state !connection-type !content disabled=yes !dscp \
    !dst-address !dst-address-list !dst-address-type !dst-limit !dst-port \
    !headers !hop-limit !icmp-options !in-bridge-port !in-bridge-port-list \
    !in-interface !in-interface-list !ingress-priority !ipsec-policy !limit \
    log=no log-prefix="" new-dscp=5 !nth !out-bridge-port \
    !out-bridge-port-list !out-interface !out-interface-list !packet-mark \
    !packet-size passthrough=yes !per-connection-classifier port=500 \
    !priority protocol=udp !random !routing-mark !src-address \
    !src-address-list !src-address-type !src-mac-address !src-port !tcp-flags \
    !tcp-mss !time !tls-host
add action=change-dscp chain=forward comment=\
    "DSCP - 5 - L2TP UDP Port 1701 (LAN Traffic)" !connection-bytes \
    !connection-limit !connection-mark !connection-nat-state !connection-rate \
    !connection-state !connection-type !content disabled=yes !dscp \
    !dst-address !dst-address-list !dst-address-type !dst-limit !dst-port \
    !headers !hop-limit !icmp-options !in-bridge-port !in-bridge-port-list \
    !in-interface !in-interface-list !ingress-priority !ipsec-policy !limit \
    log=no log-prefix="" new-dscp=5 !nth !out-bridge-port \
    !out-bridge-port-list !out-interface !out-interface-list !packet-mark \
    !packet-size passthrough=yes !per-connection-classifier port=1701 \
    !priority protocol=udp !random !routing-mark !src-address \
    !src-address-list !src-address-type !src-mac-address !src-port !tcp-flags \
    !tcp-mss !time !tls-host
add action=change-dscp chain=forward comment=\
    "DSCP - 5 - L2TP UDP Port 4500 (LAN Traffic)" !connection-bytes \
    !connection-limit !connection-mark !connection-nat-state !connection-rate \
    !connection-state !connection-type !content disabled=yes !dscp \
    !dst-address !dst-address-list !dst-address-type !dst-limit !dst-port \
    !headers !hop-limit !icmp-options !in-bridge-port !in-bridge-port-list \
    !in-interface !in-interface-list !ingress-priority !ipsec-policy !limit \
    log=no log-prefix="" new-dscp=5 !nth !out-bridge-port \
    !out-bridge-port-list !out-interface !out-interface-list !packet-mark \
    !packet-size passthrough=yes !per-connection-classifier port=4500 \
    !priority protocol=udp !random !routing-mark !src-address \
    !src-address-list !src-address-type !src-mac-address !src-port !tcp-flags \
    !tcp-mss !time !tls-host
add action=change-dscp chain=forward comment=\
    "DSCP - 5 - OVPN TCP Port 1194 (LAN Traffic)" !connection-bytes \
    !connection-limit !connection-mark !connection-nat-state !connection-rate \
    !connection-state !connection-type !content disabled=yes !dscp \
    !dst-address !dst-address-list !dst-address-type !dst-limit !dst-port \
    !headers !hop-limit !icmp-options !in-bridge-port !in-bridge-port-list \
    !in-interface !in-interface-list !ingress-priority !ipsec-policy !limit \
    log=no log-prefix="" new-dscp=5 !nth !out-bridge-port \
    !out-bridge-port-list !out-interface !out-interface-list !packet-mark \
    !packet-size passthrough=yes !per-connection-classifier port=1194 \
    !priority protocol=tcp !random !routing-mark !src-address \
    !src-address-list !src-address-type !src-mac-address !src-port !tcp-flags \
    !tcp-mss !time !tls-host
add action=change-dscp chain=forward comment=\
    "DSCP - 5 - SSTP TCP Port 443 (LAN Traffic)" !connection-bytes \
    !connection-limit !connection-mark !connection-nat-state !connection-rate \
    !connection-state !connection-type !content disabled=yes !dscp \
    !dst-address !dst-address-list !dst-address-type !dst-limit !dst-port \
    !headers !hop-limit !icmp-options !in-bridge-port !in-bridge-port-list \
    !in-interface !in-interface-list !ingress-priority !ipsec-policy !limit \
    log=no log-prefix="" new-dscp=5 !nth !out-bridge-port \
    !out-bridge-port-list !out-interface !out-interface-list !packet-mark \
    !packet-size passthrough=yes !per-connection-classifier port=443 \
    !priority protocol=tcp !random !routing-mark !src-address \
    !src-address-list !src-address-type !src-mac-address !src-port !tcp-flags \
    !tcp-mss !time !tls-host
add action=change-mss chain=forward comment="Clamp MSS to PMTU" \
    !connection-bytes !connection-limit !connection-mark \
    !connection-nat-state !connection-rate !connection-state !connection-type \
    !content disabled=yes !dscp !dst-address !dst-address-list \
    !dst-address-type !dst-limit !dst-port !headers !hop-limit !icmp-options \
    !in-bridge-port !in-bridge-port-list !in-interface !in-interface-list \
    !ingress-priority !ipsec-policy !limit log=no log-prefix="" new-mss=\
    clamp-to-pmtu !nth !out-bridge-port !out-bridge-port-list !out-interface \
    out-interface-list=WAN !packet-mark !packet-size passthrough=yes \
    !per-connection-classifier !port !priority protocol=tcp !random \
    !routing-mark !src-address !src-address-list !src-address-type \
    !src-mac-address !src-port tcp-flags=syn tcp-mss=1453-65535 !time \
    !tls-host
add action=change-mss chain=forward comment="Clamp MSS to PMTU" \
    !connection-bytes !connection-limit !connection-mark \
    !connection-nat-state !connection-rate !connection-state !connection-type \
    !content disabled=yes !dscp !dst-address !dst-address-list \
    !dst-address-type !dst-limit !dst-port !headers !hop-limit !icmp-options \
    !in-bridge-port !in-bridge-port-list !in-interface in-interface-list=WAN \
    !ingress-priority !ipsec-policy !limit log=no log-prefix="" new-mss=\
    clamp-to-pmtu !nth !out-bridge-port !out-bridge-port-list !out-interface \
    !out-interface-list !packet-mark !packet-size passthrough=yes \
    !per-connection-classifier !port !priority protocol=tcp !random \
    !routing-mark !src-address !src-address-list !src-address-type \
    !src-mac-address !src-port tcp-flags=syn tcp-mss=1453-65535 !time \
    !tls-host
add action=accept chain=output comment="Section Break" !connection-bytes \
    !connection-limit !connection-mark !connection-nat-state !connection-rate \
    !connection-state !connection-type !content disabled=yes !dscp \
    !dst-address !dst-address-list !dst-address-type !dst-limit !dst-port \
    !headers !hop-limit !icmp-options !in-bridge-port !in-bridge-port-list \
    !in-interface !in-interface-list !ingress-priority !ipsec-policy !limit \
    log=no log-prefix="" !nth !out-bridge-port !out-bridge-port-list \
    !out-interface !out-interface-list !packet-mark !packet-size \
    !per-connection-classifier !port !priority !protocol !random \
    !routing-mark !src-address !src-address-list !src-address-type \
    !src-mac-address !src-port !tcp-flags !tcp-mss !time !tls-host
add action=set-priority chain=postrouting comment="Respect DSCP tagging" \
    !connection-bytes !connection-limit !connection-mark \
    !connection-nat-state !connection-rate !connection-state !connection-type \
    !content disabled=yes !dscp !dst-address !dst-address-list \
    !dst-address-type !dst-limit !dst-port !headers !hop-limit !icmp-options \
    !in-bridge-port !in-bridge-port-list !in-interface !in-interface-list \
    !ingress-priority !ipsec-policy !limit log=no log-prefix="" new-priority=\
    from-dscp-high-3-bits !nth !out-bridge-port !out-bridge-port-list \
    !out-interface !out-interface-list !packet-mark !packet-size passthrough=\
    yes !per-connection-classifier !port !priority !protocol !random \
    !routing-mark !src-address !src-address-list !src-address-type \
    !src-mac-address !src-port !tcp-flags !tcp-mss !time !tls-host
add action=set-priority chain=postrouting comment="ACK SET PRIO 6" \
    !connection-bytes !connection-limit !connection-mark \
    !connection-nat-state !connection-rate !connection-state !connection-type \
    !content disabled=yes !dscp !dst-address !dst-address-list \
    !dst-address-type !dst-limit !dst-port !headers !hop-limit !icmp-options \
    !in-bridge-port !in-bridge-port-list !in-interface !in-interface-list \
    !ingress-priority !ipsec-policy !limit log=no log-prefix="" new-priority=\
    6 !nth !out-bridge-port !out-bridge-port-list !out-interface \
    !out-interface-list !packet-mark packet-size=0-123 passthrough=no \
    !per-connection-classifier !port !priority protocol=tcp !random \
    !routing-mark !src-address !src-address-list !src-address-type \
    !src-mac-address !src-port tcp-flags=ack !tcp-mss !time !tls-host
add action=change-dscp chain=postrouting comment="ACK CHANGE DSCP 48" \
    !connection-bytes !connection-limit !connection-mark \
    !connection-nat-state !connection-rate !connection-state !connection-type \
    !content disabled=yes !dscp !dst-address !dst-address-list \
    !dst-address-type !dst-limit !dst-port !headers !hop-limit !icmp-options \
    !in-bridge-port !in-bridge-port-list !in-interface !in-interface-list \
    !ingress-priority !ipsec-policy !limit log=no log-prefix="" new-dscp=48 \
    !nth !out-bridge-port !out-bridge-port-list !out-interface \
    !out-interface-list !packet-mark packet-size=0-123 passthrough=no \
    !per-connection-classifier !port !priority protocol=tcp !random \
    !routing-mark !src-address !src-address-list !src-address-type \
    !src-mac-address !src-port tcp-flags=ack !tcp-mss !time !tls-host
add action=change-dscp chain=postrouting comment="DSCP - 7 - Skype, HTTPS" \
    !connection-bytes !connection-limit !connection-mark \
    !connection-nat-state !connection-rate !connection-state !connection-type \
    !content disabled=yes !dscp !dst-address !dst-address-list \
    !dst-address-type !dst-limit dst-port=443 !headers !hop-limit \
    !icmp-options !in-bridge-port !in-bridge-port-list !in-interface \
    !in-interface-list !ingress-priority !ipsec-policy !limit log=no \
    log-prefix="" new-dscp=7 !nth !out-bridge-port !out-bridge-port-list \
    !out-interface !out-interface-list !packet-mark !packet-size passthrough=\
    yes !per-connection-classifier !port !priority protocol=tcp !random \
    !routing-mark !src-address !src-address-list !src-address-type \
    !src-mac-address !src-port !tcp-flags !tcp-mss !time !tls-host
add action=change-dscp chain=postrouting comment="DSCP - 7 - VOIP" \
    !connection-bytes !connection-limit !connection-mark \
    !connection-nat-state !connection-rate !connection-state !connection-type \
    !content disabled=yes !dscp !dst-address !dst-address-list \
    !dst-address-type !dst-limit !dst-port !headers !hop-limit !icmp-options \
    !in-bridge-port !in-bridge-port-list !in-interface !in-interface-list \
    !ingress-priority !ipsec-policy !limit log=no log-prefix="" new-dscp=7 \
    !nth !out-bridge-port !out-bridge-port-list !out-interface \
    !out-interface-list !packet-mark !packet-size passthrough=yes \
    !per-connection-classifier port=1167,1719,1720,8010 !priority protocol=\
    udp !random !routing-mark !src-address !src-address-list \
    !src-address-type !src-mac-address !src-port !tcp-flags !tcp-mss !time \
    !tls-host
add action=change-dscp chain=postrouting comment="DSCP - 7 - VOIP" \
    !connection-bytes !connection-limit !connection-mark \
    !connection-nat-state !connection-rate !connection-state !connection-type \
    !content disabled=yes !dscp !dst-address !dst-address-list \
    !dst-address-type !dst-limit !dst-port !headers !hop-limit !icmp-options \
    !in-bridge-port !in-bridge-port-list !in-interface !in-interface-list \
    !ingress-priority !ipsec-policy !limit log=no log-prefix="" new-dscp=7 \
    !nth !out-bridge-port !out-bridge-port-list !out-interface \
    !out-interface-list !packet-mark !packet-size passthrough=yes \
    !per-connection-classifier port=1719,1720,8008,8009 !priority protocol=\
    tcp !random !routing-mark !src-address !src-address-list \
    !src-address-type !src-mac-address !src-port !tcp-flags !tcp-mss !time \
    !tls-host
add action=change-dscp chain=postrouting comment="DSCP - 7 - SIP" \
    !connection-bytes !connection-limit !connection-mark \
    !connection-nat-state !connection-rate !connection-state !connection-type \
    !content disabled=yes !dscp !dst-address !dst-address-list \
    !dst-address-type !dst-limit !dst-port !headers !hop-limit !icmp-options \
    !in-bridge-port !in-bridge-port-list !in-interface !in-interface-list \
    !ingress-priority !ipsec-policy !limit log=no log-prefix="" new-dscp=7 \
    !nth !out-bridge-port !out-bridge-port-list !out-interface \
    !out-interface-list !packet-mark !packet-size passthrough=yes \
    !per-connection-classifier port=5060,5061 !priority protocol=tcp !random \
    !routing-mark !src-address !src-address-list !src-address-type \
    !src-mac-address !src-port !tcp-flags !tcp-mss !time !tls-host
add action=change-dscp chain=postrouting comment="DSCP - 7 - SIP" \
    !connection-bytes !connection-limit !connection-mark \
    !connection-nat-state !connection-rate !connection-state !connection-type \
    !content disabled=yes !dscp !dst-address !dst-address-list \
    !dst-address-type !dst-limit !dst-port !headers !hop-limit !icmp-options \
    !in-bridge-port !in-bridge-port-list !in-interface !in-interface-list \
    !ingress-priority !ipsec-policy !limit log=no log-prefix="" new-dscp=7 \
    !nth !out-bridge-port !out-bridge-port-list !out-interface \
    !out-interface-list !packet-mark !packet-size passthrough=yes \
    !per-connection-classifier port=5060,5061 !priority protocol=udp !random \
    !routing-mark !src-address !src-address-list !src-address-type \
    !src-mac-address !src-port !tcp-flags !tcp-mss !time !tls-host
add action=change-dscp chain=postrouting comment="DSCP - 7 - SIP 5004" \
    !connection-bytes !connection-limit !connection-mark \
    !connection-nat-state !connection-rate !connection-state !connection-type \
    !content disabled=yes !dscp !dst-address !dst-address-list \
    !dst-address-type !dst-limit !dst-port !headers !hop-limit !icmp-options \
    !in-bridge-port !in-bridge-port-list !in-interface !in-interface-list \
    !ingress-priority !ipsec-policy !limit log=no log-prefix="" new-dscp=7 \
    !nth !out-bridge-port !out-bridge-port-list !out-interface \
    !out-interface-list !packet-mark !packet-size passthrough=yes \
    !per-connection-classifier port=5004 !priority protocol=udp !random \
    !routing-mark !src-address !src-address-list !src-address-type \
    !src-mac-address !src-port !tcp-flags !tcp-mss !time !tls-host
add action=set-priority chain=postrouting comment=\
    "Priority - 7 - Ventrilo VOIP" !connection-bytes !connection-limit \
    !connection-mark !connection-nat-state !connection-rate !connection-state \
    !connection-type !content disabled=yes !dscp !dst-address \
    !dst-address-list !dst-address-type !dst-limit !dst-port !headers \
    !hop-limit !icmp-options !in-bridge-port !in-bridge-port-list \
    !in-interface !in-interface-list !ingress-priority !ipsec-policy !limit \
    log=no log-prefix="" new-priority=7 !nth !out-bridge-port \
    !out-bridge-port-list !out-interface !out-interface-list !packet-mark \
    !packet-size passthrough=yes !per-connection-classifier port=3784 \
    !priority protocol=tcp !random !routing-mark !src-address \
    !src-address-list !src-address-type !src-mac-address !src-port !tcp-flags \
    !tcp-mss !time !tls-host
add action=set-priority chain=postrouting comment=\
    "Priority - 7 - Ventrilo VOIP" !connection-bytes !connection-limit \
    !connection-mark !connection-nat-state !connection-rate !connection-state \
    !connection-type !content disabled=yes !dscp !dst-address \
    !dst-address-list !dst-address-type !dst-limit !dst-port !headers \
    !hop-limit !icmp-options !in-bridge-port !in-bridge-port-list \
    !in-interface !in-interface-list !ingress-priority !ipsec-policy !limit \
    log=no log-prefix="" new-priority=7 !nth !out-bridge-port \
    !out-bridge-port-list !out-interface !out-interface-list !packet-mark \
    !packet-size passthrough=yes !per-connection-classifier port=3784,3785 \
    !priority protocol=udp !random !routing-mark !src-address \
    !src-address-list !src-address-type !src-mac-address !src-port !tcp-flags \
    !tcp-mss !time !tls-host
add action=set-priority chain=postrouting comment=\
    "Priority - 7 - Windows Live Messenger Voice" !connection-bytes \
    !connection-limit !connection-mark !connection-nat-state !connection-rate \
    !connection-state !connection-type !content disabled=yes !dscp \
    !dst-address !dst-address-list !dst-address-type !dst-limit !dst-port \
    !headers !hop-limit !icmp-options !in-bridge-port !in-bridge-port-list \
    !in-interface !in-interface-list !ingress-priority !ipsec-policy !limit \
    log=no log-prefix="" new-priority=7 !nth !out-bridge-port \
    !out-bridge-port-list !out-interface !out-interface-list !packet-mark \
    !packet-size passthrough=yes !per-connection-classifier port=6901 \
    !priority protocol=tcp !random !routing-mark !src-address \
    !src-address-list !src-address-type !src-mac-address !src-port !tcp-flags \
    !tcp-mss !time !tls-host
add action=set-priority chain=postrouting comment=\
    "Priority - 7 - Windows Live Messenger Voice" !connection-bytes \
    !connection-limit !connection-mark !connection-nat-state !connection-rate \
    !connection-state !connection-type !content disabled=yes !dscp \
    !dst-address !dst-address-list !dst-address-type !dst-limit !dst-port \
    !headers !hop-limit !icmp-options !in-bridge-port !in-bridge-port-list \
    !in-interface !in-interface-list !ingress-priority !ipsec-policy !limit \
    log=no log-prefix="" new-priority=7 !nth !out-bridge-port \
    !out-bridge-port-list !out-interface !out-interface-list !packet-mark \
    !packet-size passthrough=yes !per-connection-classifier port=6901 \
    !priority protocol=udp !random !routing-mark !src-address \
    !src-address-list !src-address-type !src-mac-address !src-port !tcp-flags \
    !tcp-mss !time !tls-host
add action=set-priority chain=postrouting comment="TEAMS FACETIME SET PRIO 4" \
    !connection-bytes !connection-limit !connection-mark \
    !connection-nat-state !connection-rate !connection-state !connection-type \
    !content disabled=yes !dscp !dst-address !dst-address-list \
    !dst-address-type !dst-limit dst-port=3478-3497 !headers !hop-limit \
    !icmp-options !in-bridge-port !in-bridge-port-list !in-interface \
    !in-interface-list !ingress-priority !ipsec-policy !limit log=no \
    log-prefix="" new-priority=4 !nth !out-bridge-port !out-bridge-port-list \
    !out-interface !out-interface-list !packet-mark !packet-size passthrough=\
    yes !per-connection-classifier !port !priority protocol=udp !random \
    !routing-mark !src-address !src-address-list !src-address-type \
    !src-mac-address !src-port !tcp-flags !tcp-mss !time !tls-host
add action=change-dscp chain=postrouting comment=\
    "TEAMS CHANGE FACETIME DSCP 34" !connection-bytes !connection-limit \
    !connection-mark !connection-nat-state !connection-rate !connection-state \
    !connection-type !content disabled=yes !dscp !dst-address \
    !dst-address-list !dst-address-type !dst-limit dst-port=3478-3497 \
    !headers !hop-limit !icmp-options !in-bridge-port !in-bridge-port-list \
    !in-interface !in-interface-list !ingress-priority !ipsec-policy !limit \
    log=no log-prefix="" new-dscp=34 !nth !out-bridge-port \
    !out-bridge-port-list !out-interface !out-interface-list !packet-mark \
    !packet-size passthrough=yes !per-connection-classifier !port !priority \
    protocol=udp !random !routing-mark !src-address !src-address-list \
    !src-address-type !src-mac-address !src-port !tcp-flags !tcp-mss !time \
    !tls-host
add action=accept chain=output comment="Section Break" !connection-bytes \
    !connection-limit !connection-mark !connection-nat-state !connection-rate \
    !connection-state !connection-type !content disabled=yes !dscp \
    !dst-address !dst-address-list !dst-address-type !dst-limit !dst-port \
    !headers !hop-limit !icmp-options !in-bridge-port !in-bridge-port-list \
    !in-interface !in-interface-list !ingress-priority !ipsec-policy !limit \
    log=no log-prefix="" !nth !out-bridge-port !out-bridge-port-list \
    !out-interface !out-interface-list !packet-mark !packet-size \
    !per-connection-classifier !port !priority !protocol !random \
    !routing-mark !src-address !src-address-list !src-address-type \
    !src-mac-address !src-port !tcp-flags !tcp-mss !time !tls-host
add action=set-priority chain=prerouting comment="set priority from ingress" \
    !connection-bytes !connection-limit !connection-mark \
    !connection-nat-state !connection-rate !connection-state !connection-type \
    !content disabled=yes !dscp !dst-address !dst-address-list \
    !dst-address-type !dst-limit !dst-port !headers !hop-limit !icmp-options \
    !in-bridge-port !in-bridge-port-list !in-interface in-interface-list=VLAN \
    !ingress-priority !ipsec-policy !limit log=no log-prefix="" new-priority=\
    from-ingress !nth !out-bridge-port !out-bridge-port-list !out-interface \
    !out-interface-list !packet-mark !packet-size passthrough=yes \
    !per-connection-classifier !port !priority !protocol !random \
    !routing-mark !src-address !src-address-list !src-address-type \
    !src-mac-address !src-port !tcp-flags !tcp-mss !time !tls-host
add action=set-priority chain=prerouting comment="Priority - 6 - SSH" \
    !connection-bytes !connection-limit !connection-mark \
    !connection-nat-state !connection-rate !connection-state !connection-type \
    !content disabled=yes !dscp !dst-address !dst-address-list \
    !dst-address-type !dst-limit !dst-port !headers !hop-limit !icmp-options \
    !in-bridge-port !in-bridge-port-list !in-interface !in-interface-list \
    !ingress-priority !ipsec-policy !limit log=no log-prefix="" new-priority=\
    6 !nth !out-bridge-port !out-bridge-port-list !out-interface \
    !out-interface-list !packet-mark !packet-size passthrough=yes \
    !per-connection-classifier port=22 !priority protocol=tcp !random \
    !routing-mark !src-address !src-address-list !src-address-type \
    !src-mac-address !src-port !tcp-flags !tcp-mss !time !tls-host
add action=set-priority chain=prerouting comment="Priority - 6 - Telnet" \
    !connection-bytes !connection-limit !connection-mark \
    !connection-nat-state !connection-rate !connection-state !connection-type \
    !content disabled=yes !dscp !dst-address !dst-address-list \
    !dst-address-type !dst-limit !dst-port !headers !hop-limit !icmp-options \
    !in-bridge-port !in-bridge-port-list !in-interface !in-interface-list \
    !ingress-priority !ipsec-policy !limit log=no log-prefix="" new-priority=\
    6 !nth !out-bridge-port !out-bridge-port-list !out-interface \
    !out-interface-list !packet-mark !packet-size passthrough=yes \
    !per-connection-classifier port=23 !priority protocol=tcp !random \
    !routing-mark !src-address !src-address-list !src-address-type \
    !src-mac-address !src-port !tcp-flags !tcp-mss !time !tls-host
add action=set-priority chain=prerouting comment="Priority - 6 - ICMP" \
    !connection-bytes !connection-limit !connection-mark \
    !connection-nat-state !connection-rate !connection-state !connection-type \
    !content disabled=yes !dscp !dst-address !dst-address-list \
    !dst-address-type !dst-limit !dst-port !headers !hop-limit !icmp-options \
    !in-bridge-port !in-bridge-port-list !in-interface !in-interface-list \
    !ingress-priority !ipsec-policy !limit log=no log-prefix="" new-priority=\
    6 !nth !out-bridge-port !out-bridge-port-list !out-interface \
    !out-interface-list !packet-mark !packet-size passthrough=yes \
    !per-connection-classifier !port !priority protocol=icmp !random \
    !routing-mark !src-address !src-address-list !src-address-type \
    !src-mac-address !src-port !tcp-flags !tcp-mss !time !tls-host
add action=set-priority chain=prerouting comment=\
    "Priority - 6 - TCP DNS Requests" !connection-bytes !connection-limit \
    !connection-mark !connection-nat-state !connection-rate !connection-state \
    !connection-type !content disabled=yes !dscp !dst-address \
    !dst-address-list !dst-address-type !dst-limit !dst-port !headers \
    !hop-limit !icmp-options !in-bridge-port !in-bridge-port-list \
    !in-interface !in-interface-list !ingress-priority !ipsec-policy !limit \
    log=no log-prefix="" new-priority=6 !nth !out-bridge-port \
    !out-bridge-port-list !out-interface !out-interface-list !packet-mark \
    !packet-size passthrough=yes !per-connection-classifier port=53 !priority \
    protocol=tcp !random !routing-mark !src-address !src-address-list \
    !src-address-type !src-mac-address !src-port !tcp-flags !tcp-mss !time \
    !tls-host
add action=set-priority chain=prerouting comment=\
    "Priority - 6 - UDP DNS & mDNS Requests" !connection-bytes \
    !connection-limit !connection-mark !connection-nat-state !connection-rate \
    !connection-state !connection-type !content disabled=yes !dscp \
    !dst-address !dst-address-list !dst-address-type !dst-limit !dst-port \
    !headers !hop-limit !icmp-options !in-bridge-port !in-bridge-port-list \
    !in-interface !in-interface-list !ingress-priority !ipsec-policy !limit \
    log=no log-prefix="" new-priority=6 !nth !out-bridge-port \
    !out-bridge-port-list !out-interface !out-interface-list !packet-mark \
    !packet-size passthrough=yes !per-connection-classifier port=53,5353 \
    !priority protocol=udp !random !routing-mark !src-address \
    !src-address-list !src-address-type !src-mac-address !src-port !tcp-flags \
    !tcp-mss !time !tls-host
add action=set-priority chain=prerouting comment=\
    "Priority - 5 - HTTP Requests" connection-bytes=0-5000000 \
    !connection-limit !connection-mark !connection-nat-state !connection-rate \
    !connection-state !connection-type !content disabled=yes !dscp \
    !dst-address !dst-address-list !dst-address-type !dst-limit dst-port=80 \
    !headers !hop-limit !icmp-options !in-bridge-port !in-bridge-port-list \
    !in-interface !in-interface-list !ingress-priority !ipsec-policy !limit \
    log=no log-prefix="" new-priority=5 !nth !out-bridge-port \
    !out-bridge-port-list !out-interface !out-interface-list !packet-mark \
    !packet-size passthrough=yes !per-connection-classifier !port !priority \
    protocol=tcp !random !routing-mark !src-address !src-address-list \
    !src-address-type !src-mac-address !src-port !tcp-flags !tcp-mss !time \
    !tls-host
add action=set-priority chain=prerouting comment="Priority - 5 - ICQ" \
    !connection-bytes !connection-limit !connection-mark \
    !connection-nat-state !connection-rate !connection-state !connection-type \
    !content disabled=yes !dscp !dst-address !dst-address-list \
    !dst-address-type !dst-limit !dst-port !headers !hop-limit !icmp-options \
    !in-bridge-port !in-bridge-port-list !in-interface !in-interface-list \
    !ingress-priority !ipsec-policy !limit log=no log-prefix="" new-priority=\
    5 !nth !out-bridge-port !out-bridge-port-list !out-interface \
    !out-interface-list !packet-mark !packet-size passthrough=yes \
    !per-connection-classifier port=5190 !priority protocol=tcp !random \
    !routing-mark !src-address !src-address-list !src-address-type \
    !src-mac-address !src-port !tcp-flags !tcp-mss !time !tls-host
add action=set-priority chain=prerouting comment="Priority - 5 - Yahoo IM" \
    !connection-bytes !connection-limit !connection-mark \
    !connection-nat-state !connection-rate !connection-state !connection-type \
    !content disabled=yes !dscp !dst-address !dst-address-list \
    !dst-address-type !dst-limit !dst-port !headers !hop-limit !icmp-options \
    !in-bridge-port !in-bridge-port-list !in-interface !in-interface-list \
    !ingress-priority !ipsec-policy !limit log=no log-prefix="" new-priority=\
    5 !nth !out-bridge-port !out-bridge-port-list !out-interface \
    !out-interface-list !packet-mark !packet-size passthrough=yes \
    !per-connection-classifier port=5050 !priority protocol=tcp !random \
    !routing-mark !src-address !src-address-list !src-address-type \
    !src-mac-address !src-port !tcp-flags !tcp-mss !time !tls-host
add action=set-priority chain=prerouting comment="Priority - 4 - AOL, IRC" \
    !connection-bytes !connection-limit !connection-mark \
    !connection-nat-state !connection-rate !connection-state !connection-type \
    !content disabled=yes !dscp !dst-address !dst-address-list \
    !dst-address-type !dst-limit !dst-port !headers !hop-limit !icmp-options \
    !in-bridge-port !in-bridge-port-list !in-interface !in-interface-list \
    !ingress-priority !ipsec-policy !limit log=no log-prefix="" new-priority=\
    4 !nth !out-bridge-port !out-bridge-port-list !out-interface \
    !out-interface-list !packet-mark !packet-size passthrough=yes \
    !per-connection-classifier port=531,5190,6660-6669,6679,6697 !priority \
    protocol=tcp !random !routing-mark !src-address !src-address-list \
    !src-address-type !src-mac-address !src-port !tcp-flags !tcp-mss !time \
    !tls-host
add action=set-priority chain=prerouting comment="Priority - 4 - AOL, IRC" \
    !connection-bytes !connection-limit !connection-mark \
    !connection-nat-state !connection-rate !connection-state !connection-type \
    !content disabled=yes !dscp !dst-address !dst-address-list \
    !dst-address-type !dst-limit !dst-port !headers !hop-limit !icmp-options \
    !in-bridge-port !in-bridge-port-list !in-interface !in-interface-list \
    !ingress-priority !ipsec-policy !limit log=no log-prefix="" new-priority=\
    4 !nth !out-bridge-port !out-bridge-port-list !out-interface \
    !out-interface-list !packet-mark !packet-size passthrough=yes \
    !per-connection-classifier port=531 !priority protocol=udp !random \
    !routing-mark !src-address !src-address-list !src-address-type \
    !src-mac-address !src-port !tcp-flags !tcp-mss !time !tls-host
add action=set-priority chain=prerouting comment="Priority - 4 - Time" \
    !connection-bytes !connection-limit !connection-mark \
    !connection-nat-state !connection-rate !connection-state !connection-type \
    !content disabled=yes !dscp !dst-address !dst-address-list \
    !dst-address-type !dst-limit !dst-port !headers !hop-limit !icmp-options \
    !in-bridge-port !in-bridge-port-list !in-interface !in-interface-list \
    !ingress-priority !ipsec-policy !limit log=no log-prefix="" new-priority=\
    4 !nth !out-bridge-port !out-bridge-port-list !out-interface \
    !out-interface-list !packet-mark !packet-size passthrough=yes \
    !per-connection-classifier port=37 !priority protocol=tcp !random \
    !routing-mark !src-address !src-address-list !src-address-type \
    !src-mac-address !src-port !tcp-flags !tcp-mss !time !tls-host
add action=set-priority chain=prerouting comment="Priority - 4 - Time" \
    !connection-bytes !connection-limit !connection-mark \
    !connection-nat-state !connection-rate !connection-state !connection-type \
    !content disabled=yes !dscp !dst-address !dst-address-list \
    !dst-address-type !dst-limit !dst-port !headers !hop-limit !icmp-options \
    !in-bridge-port !in-bridge-port-list !in-interface !in-interface-list \
    !ingress-priority !ipsec-policy !limit log=no log-prefix="" new-priority=\
    4 !nth !out-bridge-port !out-bridge-port-list !out-interface \
    !out-interface-list !packet-mark !packet-size passthrough=yes \
    !per-connection-classifier port=37,123 !priority protocol=udp !random \
    !routing-mark !src-address !src-address-list !src-address-type \
    !src-mac-address !src-port !tcp-flags !tcp-mss !time !tls-host
add action=set-priority chain=prerouting comment=\
    "Priority - 3 - Blizzard Games Online" !connection-bytes \
    !connection-limit !connection-mark !connection-nat-state !connection-rate \
    !connection-state !connection-type !content disabled=yes !dscp \
    !dst-address !dst-address-list !dst-address-type !dst-limit !dst-port \
    !headers !hop-limit !icmp-options !in-bridge-port !in-bridge-port-list \
    !in-interface !in-interface-list !ingress-priority !ipsec-policy !limit \
    log=no log-prefix="" new-priority=3 !nth !out-bridge-port \
    !out-bridge-port-list !out-interface !out-interface-list !packet-mark \
    !packet-size passthrough=yes !per-connection-classifier port=\
    1119,1120,3074,3724,4000,6112-6120 !priority protocol=tcp !random \
    !routing-mark !src-address !src-address-list !src-address-type \
    !src-mac-address !src-port !tcp-flags !tcp-mss !time !tls-host
add action=set-priority chain=prerouting comment=\
    "Priority - 3 - Blizzard Games Online" !connection-bytes \
    !connection-limit !connection-mark !connection-nat-state !connection-rate \
    !connection-state !connection-type !content disabled=yes !dscp \
    !dst-address !dst-address-list !dst-address-type !dst-limit !dst-port \
    !headers !hop-limit !icmp-options !in-bridge-port !in-bridge-port-list \
    !in-interface !in-interface-list !ingress-priority !ipsec-policy !limit \
    log=no log-prefix="" new-priority=3 !nth !out-bridge-port \
    !out-bridge-port-list !out-interface !out-interface-list !packet-mark \
    !packet-size passthrough=yes !per-connection-classifier port=\
    1119,1120,3478-3479,3724,4000,4379-4380,5060,5062,6112-6119,6250 \
    !priority protocol=udp !random !routing-mark !src-address \
    !src-address-list !src-address-type !src-mac-address !src-port !tcp-flags \
    !tcp-mss !time !tls-host
add action=set-priority chain=prerouting comment="Priority - 0 - SFTP" \
    !connection-bytes !connection-limit !connection-mark \
    !connection-nat-state !connection-rate !connection-state !connection-type \
    !content disabled=yes !dscp !dst-address !dst-address-list \
    !dst-address-type !dst-limit dst-port=22 !headers !hop-limit \
    !icmp-options !in-bridge-port !in-bridge-port-list !in-interface \
    !in-interface-list !ingress-priority !ipsec-policy !limit log=no \
    log-prefix="" new-priority=0 !nth !out-bridge-port !out-bridge-port-list \
    !out-interface !out-interface-list !packet-mark packet-size=1400-1500 \
    passthrough=yes !per-connection-classifier !port !priority protocol=tcp \
    !random !routing-mark !src-address !src-address-list !src-address-type \
    !src-mac-address !src-port !tcp-flags !tcp-mss !time !tls-host
add action=set-priority chain=prerouting comment="Priority - 0 - FTP" \
    !connection-bytes !connection-limit !connection-mark \
    !connection-nat-state !connection-rate !connection-state !connection-type \
    !content disabled=yes !dscp !dst-address !dst-address-list \
    !dst-address-type !dst-limit dst-port=20,21 !headers !hop-limit \
    !icmp-options !in-bridge-port !in-bridge-port-list !in-interface \
    !in-interface-list !ingress-priority !ipsec-policy !limit log=no \
    log-prefix="" new-priority=0 !nth !out-bridge-port !out-bridge-port-list \
    !out-interface !out-interface-list !packet-mark packet-size=1400-1500 \
    passthrough=yes !per-connection-classifier !port !priority protocol=tcp \
    !random !routing-mark !src-address !src-address-list !src-address-type \
    !src-mac-address !src-port !tcp-flags !tcp-mss !time !tls-host
add action=set-priority chain=prerouting comment=\
    "Priority - 0 - HTTP Downloads" connection-bytes=5000000-0 \
    !connection-limit !connection-mark !connection-nat-state !connection-rate \
    !connection-state !connection-type !content disabled=yes !dscp \
    !dst-address !dst-address-list !dst-address-type !dst-limit !dst-port \
    !headers !hop-limit !icmp-options !in-bridge-port !in-bridge-port-list \
    !in-interface !in-interface-list !ingress-priority !ipsec-policy !limit \
    log=no log-prefix="" new-priority=0 !nth !out-bridge-port \
    !out-bridge-port-list !out-interface !out-interface-list !packet-mark \
    !packet-size passthrough=yes !per-connection-classifier port=80 !priority \
    protocol=tcp !random !routing-mark !src-address !src-address-list \
    !src-address-type !src-mac-address !src-port !tcp-flags !tcp-mss !time \
    !tls-host
add action=set-priority chain=prerouting comment=\
    "Priority - 0 - Mail Services" !connection-bytes !connection-limit \
    !connection-mark !connection-nat-state !connection-rate !connection-state \
    !connection-type !content disabled=yes !dscp !dst-address \
    !dst-address-list !dst-address-type !dst-limit !dst-port !headers \
    !hop-limit !icmp-options !in-bridge-port !in-bridge-port-list \
    !in-interface !in-interface-list !ingress-priority !ipsec-policy !limit \
    log=no log-prefix="" new-priority=0 !nth !out-bridge-port \
    !out-bridge-port-list !out-interface !out-interface-list !packet-mark \
    !packet-size passthrough=yes !per-connection-classifier port=\
    110,995,143,993,25,57,109,465,587 !priority protocol=tcp !random \
    !routing-mark !src-address !src-address-list !src-address-type \
    !src-mac-address !src-port !tcp-flags !tcp-mss !time !tls-host
add action=set-priority chain=prerouting comment="Priority - 0 - SNMP" \
    !connection-bytes !connection-limit !connection-mark \
    !connection-nat-state !connection-rate !connection-state !connection-type \
    !content disabled=yes !dscp !dst-address !dst-address-list \
    !dst-address-type !dst-limit !dst-port !headers !hop-limit !icmp-options \
    !in-bridge-port !in-bridge-port-list !in-interface !in-interface-list \
    !ingress-priority !ipsec-policy !limit log=no log-prefix="" new-priority=\
    0 !nth !out-bridge-port !out-bridge-port-list !out-interface \
    !out-interface-list !packet-mark !packet-size passthrough=yes \
    !per-connection-classifier port=161,162 !priority protocol=udp !random \
    !routing-mark !src-address !src-address-list !src-address-type \
    !src-mac-address !src-port !tcp-flags !tcp-mss !time !tls-host
add action=set-priority chain=prerouting comment="Priority - 0 - SNMP" \
    !connection-bytes !connection-limit !connection-mark \
    !connection-nat-state !connection-rate !connection-state !connection-type \
    !content disabled=yes !dscp !dst-address !dst-address-list \
    !dst-address-type !dst-limit !dst-port !headers !hop-limit !icmp-options \
    !in-bridge-port !in-bridge-port-list !in-interface !in-interface-list \
    !ingress-priority !ipsec-policy !limit log=no log-prefix="" new-priority=\
    0 !nth !out-bridge-port !out-bridge-port-list !out-interface \
    !out-interface-list !packet-mark !packet-size passthrough=yes \
    !per-connection-classifier port=162 !priority protocol=tcp !random \
    !routing-mark !src-address !src-address-list !src-address-type \
    !src-mac-address !src-port !tcp-flags !tcp-mss !time !tls-host
add action=set-priority chain=prerouting comment="Priority - 0 - IMAP, IMAPS" \
    !connection-bytes !connection-limit !connection-mark \
    !connection-nat-state !connection-rate !connection-state !connection-type \
    !content disabled=yes !dscp !dst-address !dst-address-list \
    !dst-address-type !dst-limit !dst-port !headers !hop-limit !icmp-options \
    !in-bridge-port !in-bridge-port-list !in-interface !in-interface-list \
    !ingress-priority !ipsec-policy !limit log=no log-prefix="" new-priority=\
    0 !nth !out-bridge-port !out-bridge-port-list !out-interface \
    !out-interface-list !packet-mark !packet-size passthrough=yes \
    !per-connection-classifier port=220,993 !priority protocol=tcp !random \
    !routing-mark !src-address !src-address-list !src-address-type \
    !src-mac-address !src-port !tcp-flags !tcp-mss !time !tls-host
add action=set-priority chain=prerouting comment="Priority - 0 - IMAP" \
    !connection-bytes !connection-limit !connection-mark \
    !connection-nat-state !connection-rate !connection-state !connection-type \
    !content disabled=yes !dscp !dst-address !dst-address-list \
    !dst-address-type !dst-limit !dst-port !headers !hop-limit !icmp-options \
    !in-bridge-port !in-bridge-port-list !in-interface !in-interface-list \
    !ingress-priority !ipsec-policy !limit log=no log-prefix="" new-priority=\
    0 !nth !out-bridge-port !out-bridge-port-list !out-interface \
    !out-interface-list !packet-mark !packet-size passthrough=yes \
    !per-connection-classifier port=220 !priority protocol=udp !random \
    !routing-mark !src-address !src-address-list !src-address-type \
    !src-mac-address !src-port !tcp-flags !tcp-mss !time !tls-host
add action=set-priority chain=prerouting comment="Priority - 0 - Xbox Live" \
    !connection-bytes !connection-limit !connection-mark \
    !connection-nat-state !connection-rate !connection-state !connection-type \
    !content disabled=yes !dscp !dst-address !dst-address-list \
    !dst-address-type !dst-limit !dst-port !headers !hop-limit !icmp-options \
    !in-bridge-port !in-bridge-port-list !in-interface !in-interface-list \
    !ingress-priority !ipsec-policy !limit log=no log-prefix="" new-priority=\
    0 !nth !out-bridge-port !out-bridge-port-list !out-interface \
    !out-interface-list !packet-mark !packet-size passthrough=yes \
    !per-connection-classifier port=3074 !priority protocol=tcp !random \
    !routing-mark !src-address !src-address-list !src-address-type \
    !src-mac-address !src-port !tcp-flags !tcp-mss !time !tls-host
add action=set-priority chain=prerouting comment="Priority - 0 - Xbox Live" \
    !connection-bytes !connection-limit !connection-mark \
    !connection-nat-state !connection-rate !connection-state !connection-type \
    !content disabled=yes !dscp !dst-address !dst-address-list \
    !dst-address-type !dst-limit !dst-port !headers !hop-limit !icmp-options \
    !in-bridge-port !in-bridge-port-list !in-interface !in-interface-list \
    !ingress-priority !ipsec-policy !limit log=no log-prefix="" new-priority=\
    0 !nth !out-bridge-port !out-bridge-port-list !out-interface \
    !out-interface-list !packet-mark !packet-size passthrough=yes \
    !per-connection-classifier port=3074 !priority protocol=udp !random \
    !routing-mark !src-address !src-address-list !src-address-type \
    !src-mac-address !src-port !tcp-flags !tcp-mss !time !tls-host
add action=set-priority chain=prerouting comment=\
    "Priority - 0 - Google Desktop" !connection-bytes !connection-limit \
    !connection-mark !connection-nat-state !connection-rate !connection-state \
    !connection-type !content disabled=yes !dscp !dst-address \
    !dst-address-list !dst-address-type !dst-limit !dst-port !headers \
    !hop-limit !icmp-options !in-bridge-port !in-bridge-port-list \
    !in-interface !in-interface-list !ingress-priority !ipsec-policy !limit \
    log=no log-prefix="" new-priority=0 !nth !out-bridge-port \
    !out-bridge-port-list !out-interface !out-interface-list !packet-mark \
    !packet-size passthrough=yes !per-connection-classifier port=4664 \
    !priority protocol=tcp !random !routing-mark !src-address \
    !src-address-list !src-address-type !src-mac-address !src-port !tcp-flags \
    !tcp-mss !time !tls-host
add action=set-priority chain=prerouting comment="Priority - 0 - Teamspeak" \
    !connection-bytes !connection-limit !connection-mark \
    !connection-nat-state !connection-rate !connection-state !connection-type \
    !content disabled=yes !dscp !dst-address !dst-address-list \
    !dst-address-type !dst-limit !dst-port !headers !hop-limit !icmp-options \
    !in-bridge-port !in-bridge-port-list !in-interface !in-interface-list \
    !ingress-priority !ipsec-policy !limit log=no log-prefix="" new-priority=\
    0 !nth !out-bridge-port !out-bridge-port-list !out-interface \
    !out-interface-list !packet-mark !packet-size passthrough=yes \
    !per-connection-classifier port=8767-8768 !priority protocol=udp !random \
    !routing-mark !src-address !src-address-list !src-address-type \
    !src-mac-address !src-port !tcp-flags !tcp-mss !time !tls-host
add action=set-priority chain=prerouting comment="Priority - 0 - Teamspeak" \
    !connection-bytes !connection-limit !connection-mark \
    !connection-nat-state !connection-rate !connection-state !connection-type \
    !content disabled=yes !dscp !dst-address !dst-address-list \
    !dst-address-type !dst-limit !dst-port !headers !hop-limit !icmp-options \
    !in-bridge-port !in-bridge-port-list !in-interface !in-interface-list \
    !ingress-priority !ipsec-policy !limit log=no log-prefix="" new-priority=\
    0 !nth !out-bridge-port !out-bridge-port-list !out-interface \
    !out-interface-list !packet-mark !packet-size passthrough=yes \
    !per-connection-classifier port=9987 !priority protocol=tcp !random \
    !routing-mark !src-address !src-address-list !src-address-type \
    !src-mac-address !src-port !tcp-flags !tcp-mss !time !tls-host
add action=set-priority chain=prerouting comment=\
    "Priority - 0 - Sony Playstation" !connection-bytes !connection-limit \
    !connection-mark !connection-nat-state !connection-rate !connection-state \
    !connection-type !content disabled=yes !dscp !dst-address \
    !dst-address-list !dst-address-type !dst-limit !dst-port !headers \
    !hop-limit !icmp-options !in-bridge-port !in-bridge-port-list \
    !in-interface !in-interface-list !ingress-priority !ipsec-policy !limit \
    log=no log-prefix="" new-priority=0 !nth !out-bridge-port \
    !out-bridge-port-list !out-interface !out-interface-list !packet-mark \
    !packet-size passthrough=yes !per-connection-classifier port=9293 \
    !priority protocol=tcp !random !routing-mark !src-address \
    !src-address-list !src-address-type !src-mac-address !src-port !tcp-flags \
    !tcp-mss !time !tls-host
add action=accept chain=output comment="Section Break" !connection-bytes \
    !connection-limit !connection-mark !connection-nat-state !connection-rate \
    !connection-state !connection-type !content disabled=yes !dscp \
    !dst-address !dst-address-list !dst-address-type !dst-limit !dst-port \
    !headers !hop-limit !icmp-options !in-bridge-port !in-bridge-port-list \
    !in-interface !in-interface-list !ingress-priority !ipsec-policy !limit \
    log=no log-prefix="" !nth !out-bridge-port !out-bridge-port-list \
    !out-interface !out-interface-list !packet-mark !packet-size \
    !per-connection-classifier !port !priority !protocol !random \
    !routing-mark !src-address !src-address-list !src-address-type \
    !src-mac-address !src-port !tcp-flags !tcp-mss !time !tls-host
add action=change-mss chain=forward !connection-bytes !connection-limit \
    !connection-mark !connection-nat-state !connection-rate !connection-state \
    !connection-type !content disabled=no !dscp !dst-address \
    !dst-address-list !dst-address-type !dst-limit !dst-port !headers \
    !hop-limit !icmp-options !in-bridge-port !in-bridge-port-list \
    !in-interface !in-interface-list !ingress-priority !ipsec-policy !limit \
    log=no log-prefix="" new-mss=clamp-to-pmtu !nth !out-bridge-port \
    !out-bridge-port-list !out-interface out-interface-list=WAN !packet-mark \
    !packet-size passthrough=yes !per-connection-classifier !port !priority \
    protocol=tcp !random !routing-mark !src-address !src-address-list \
    !src-address-type !src-mac-address !src-port tcp-flags=syn !tcp-mss !time \
    !tls-host
add action=mark-packet chain=prerouting !connection-bytes !connection-limit \
    !connection-mark !connection-nat-state !connection-rate !connection-state \
    !connection-type !content disabled=no !dscp !dst-address \
    !dst-address-list !dst-address-type !dst-limit !dst-port !headers \
    !hop-limit !icmp-options !in-bridge-port !in-bridge-port-list \
    !in-interface in-interface-list=WAN !ingress-priority !ipsec-policy \
    !limit log=no log-prefix="" new-packet-mark=wan-in !nth !out-bridge-port \
    !out-bridge-port-list !out-interface !out-interface-list !packet-mark \
    !packet-size passthrough=yes !per-connection-classifier !port !priority \
    !protocol !random !routing-mark !src-address !src-address-list \
    !src-address-type !src-mac-address !src-port !tcp-flags !tcp-mss !time \
    !tls-host
add action=mark-connection chain=prerouting comment=HTTP connection-mark=\
    no-mark connection-state=new new-connection-mark=HTTP passthrough=yes \
    port=80,443 protocol=tcp
add action=mark-connection chain=prerouting connection-bytes=5000000-0 \
    connection-mark=HTTP connection-rate=2M-100M new-connection-mark=HTTP_BIG \
    passthrough=yes protocol=tcp
add action=mark-connection chain=prerouting comment=\
    "XBox Live AF21 Low Latency" connection-state=new new-connection-mark=\
    AF21 passthrough=yes port=3074,27015-27030,27036-27037 protocol=tcp
add action=mark-connection chain=prerouting comment=\
    "XBox Live AF21 Low Latency" connection-state=new dst-prefix=::/0 \
    new-connection-mark=AF21 passthrough=yes port=\
    88,500,3074,3544,4380,4500,27000-27031,27036 protocol=udp src-prefix=::/0
add action=mark-connection chain=prerouting comment="RIST AF21 Low Latency" \
    connection-state=new new-connection-mark=AF21 passthrough=yes port=5000 \
    protocol=udp
add action=mark-connection chain=prerouting comment="DNS CS6 Min Latency" \
    connection-state=new new-connection-mark=CS6 passthrough=yes port=53 \
    protocol=udp
add action=mark-connection chain=prerouting comment=\
    "SSH CS2 Interactive Shell" connection-state=new new-connection-mark=CS2 \
    passthrough=yes port=22 protocol=tcp
add action=mark-connection chain=prerouting comment=\
    "OSPF CS7 Network Control" connection-state=new new-connection-mark=CS7 \
    passthrough=yes protocol=ospf
add action=change-dscp chain=prerouting comment="HTTP_BIG Background" \
    connection-mark=HTTP_BIG dst-prefix=::/0 new-dscp=8 passthrough=no \
    src-prefix=::/0
add action=change-dscp chain=prerouting comment="HTTP Best Effort" \
    connection-mark=HTTP dst-prefix=::/0 new-dscp=0 passthrough=no \
    src-prefix=::/0
add action=change-dscp chain=prerouting comment="XBox Live AF21 Low Latency" \
    connection-mark=AF21 dst-prefix=::/0 new-dscp=18 passthrough=no \
    src-prefix=::/0
add action=change-dscp chain=prerouting comment="DNS CS6 Min Latency" \
    connection-mark=CS6 dst-prefix=::/0 new-dscp=48 passthrough=no \
    src-prefix=::/0
add action=change-dscp chain=prerouting comment="SSH CS2 Interactive Shell" \
    connection-mark=CS2 dst-prefix=::/0 new-dscp=16 passthrough=no \
    src-prefix=::/0
add action=change-dscp chain=prerouting comment="OSPF CS7 Network Control" \
    connection-mark=CS7 dst-prefix=::/0 new-dscp=56 passthrough=no \
    src-prefix=::/0
add action=set-priority chain=postrouting new-priority=from-dscp passthrough=\
    yes
/ipv6 nd
set [ find default=yes ] advertise-dns=yes advertise-mac-address=yes \
    disabled=no hop-limit=unspecified interface=vlan120-IOT \
    managed-address-configuration=no mtu=unspecified other-configuration=no \
    ra-delay=3s ra-interval=3m20s-10m ra-lifetime=30m ra-preference=medium \
    reachable-time=unspecified retransmit-interval=unspecified
add advertise-dns=yes advertise-mac-address=yes disabled=no hop-limit=\
    unspecified interface=vlan110-trusted managed-address-configuration=no \
    mtu=unspecified other-configuration=no ra-delay=3s ra-interval=3m20s-10m \
    ra-lifetime=30m ra-preference=medium reachable-time=unspecified \
    retransmit-interval=unspecified
/ipv6 nd prefix default
set autonomous=yes preferred-lifetime=1w valid-lifetime=4w2d
/mpls settings
set allow-fast-path=yes dynamic-label-range=16-1048575 propagate-ttl=yes
/ppp aaa
set accounting=yes enable-ipv6-accounting=no interim-update=0s \
    use-circuit-id-in-nas-port-id=no use-radius=no
/radius incoming
set accept=no port=3799 vrf=main
/routing igmp-proxy
set query-interval=2m5s query-response-interval=10s quick-leave=yes
/routing igmp-proxy interface
add alternative-subnets="" disabled=yes interface=vlan110-trusted threshold=1 \
    upstream=no
add alternative-subnets="" disabled=yes interface=vlan120-IOT threshold=1 \
    upstream=no
/routing settings
set single-process=no
/snmp
set contact="" enabled=yes engine-id-suffix="" location="" src-address=:: \
    trap-community=public trap-generators="" trap-interfaces=vlan110-trusted \
    trap-target="" trap-version=2 vrf=main
/system clock
set time-zone-autodetect=yes time-zone-name=America/Chicago
/system clock manual
set dst-delta=+00:00 dst-end="1970-01-01 00:00:00" dst-start=\
    "1970-01-01 00:00:00" time-zone=+00:00
/system console
set [ find port=serial0 ] channel=0 disabled=no port=serial0 term=vt102
add channel=0 disabled=no port=usb3 term=vt102
/system identity
set name=KEV_RO_OFFICE
/system leds
set 0 disabled=no interface=*1 leds="" type=interface-speed
add disabled=no interface=*1 leds="" type=interface-activity
add disabled=no interface=*2 leds="" type=interface-activity
/system leds settings
set all-leds-off=never
/system logging
set 0 action=memory disabled=no prefix="" regex="" topics=info
set 1 action=memory disabled=no prefix="" regex="" topics=error
set 2 action=memory disabled=no prefix="" regex="" topics=warning
set 3 action=echo disabled=no prefix="" regex="" topics=critical
add action=memory disabled=no prefix="" regex="" topics=e-mail
add action=memory disabled=no prefix="" regex="" topics=ipsec
add action=remotesyslog disabled=no prefix="" regex="" topics=interface
add action=remotesyslog disabled=no prefix="" regex="" topics=system
add action=remotesyslog disabled=no prefix="" regex="" topics=warning
add action=remotesyslog disabled=no prefix="" regex="" topics=error
add action=remotesyslog disabled=no prefix="" regex="" topics=firewall
add action=remotesyslog disabled=no prefix="" regex="" topics=dhcp
add action=remotesyslog disabled=no prefix="" regex="" topics=bridge,!debug
add action=remotesyslog disabled=no prefix="" regex="" topics=script
add action=remotesyslog disabled=no prefix="" regex="" topics=account
add action=remotesyslog disabled=no prefix="" regex="" topics=route
add action=remotesyslog disabled=no prefix="" regex="" topics=wireless
/system note
set note="" show-at-cli-login=no show-at-login=yes
/system ntp client
set enabled=yes mode=unicast servers="66.220.9.122,45.11.105.253,0.us.pool.ntp\
    .org,1.us.pool.ntp.org,2.us.pool.ntp.org,3.us.pool.ntp.org" vrf=main
/system ntp server
set auth-key=none broadcast=no broadcast-addresses="" enabled=yes \
    local-clock-stratum=5 manycast=yes multicast=no use-local-clock=no vrf=\
    main
/system ntp client servers
add address=66.220.9.122 auth-key=none disabled=no iburst=yes max-poll=10 \
    min-poll=6
add address=45.11.105.253 auth-key=none disabled=no iburst=yes max-poll=10 \
    min-poll=6
add address=0.us.pool.ntp.org auth-key=none disabled=no iburst=yes max-poll=\
    10 min-poll=6
add address=1.us.pool.ntp.org auth-key=none disabled=no iburst=yes max-poll=\
    10 min-poll=6
add address=2.us.pool.ntp.org auth-key=none disabled=no iburst=yes max-poll=\
    10 min-poll=6
add address=3.us.pool.ntp.org auth-key=none disabled=no iburst=yes max-poll=\
    10 min-poll=6
/system package local-update mirror
set check-interval=1d enabled=no primary-server=0.0.0.0 secondary-server=\
    0.0.0.0 user=""
/system resource hardware usb-settings
set authorization=no
/system resource irq
set 0 cpu=auto
set 1 cpu=auto
set 2 cpu=auto
set 3 cpu=auto
set 4 cpu=auto
set 5 cpu=auto
set 6 cpu=auto
set 7 cpu=auto
set 8 cpu=auto
set 9 cpu=auto
set 10 cpu=auto
set 11 cpu=auto
set 12 cpu=auto
set 13 cpu=auto
set 14 cpu=auto
set 15 cpu=auto
set 16 cpu=auto
set 17 cpu=auto
set 18 cpu=auto
/system resource irq rps
set *1 disabled=yes
set *2 disabled=yes
set *3 disabled=yes
set *4 disabled=yes
set *5 disabled=yes
set *6 disabled=yes
set *7 disabled=yes
set *8 disabled=yes
set *9 disabled=yes
set ether1-WAN-Spectrum disabled=yes
set ether2-WAN-ATT disabled=yes
set ether3 disabled=yes
set ether4 disabled=yes
set ether5 disabled=yes
set ether6 disabled=yes
set ether7 disabled=yes
set "ether8-MGMT Port" disabled=yes
set sfp-10gSwitch disabled=yes
/system routerboard reset-button
set enabled=no hold-time=0s..1m on-event=""
/system routerboard settings
# Warning: cpu not running at default frequency
set auto-upgrade=no boot-device=nand-if-fail-then-ethernet boot-protocol=\
    bootp cpu-frequency=1400MHz force-backup-booter=no preboot-etherboot=\
    disabled preboot-etherboot-server=any protected-routerboot=disabled \
    reformat-hold-button=20s reformat-hold-button-max=10m silent-boot=no
/system scheduler
add disabled=no interval=1d name="Backup and Update" on-event=\
    "/system script run BackupAndUpdate;" policy=\
    ftp,reboot,read,write,policy,test,password,sniff,sensitive,romon \
    start-date=2020-12-25 start-time=03:00:00
add disabled=no interval=6h name=blizzard-refresh on-event=blizzard-update \
    policy=ftp,reboot,read,write,policy,test,password,sniff,sensitive,romon \
    start-time=startup
add disabled=no interval=6h name=steam-refresh on-event=steam-update policy=\
    ftp,reboot,read,write,policy,test,password,sniff,sensitive,romon \
    start-time=startup
add disabled=no interval=15s name=game-qos-engine on-event=\
    "system script run game-qos-engine" policy=\
    ftp,reboot,read,write,policy,test,password,sniff,sensitive,romon \
    start-date=2025-12-08 start-time=13:24:54
/system script
add dont-require-permissions=no name=BackupAndUpdate owner=admin policy=\
    ftp,reboot,read,write,policy,test,password,sniff,sensitive,romon source="#\
    \_Script name: BackupAndUpdate\r\
    \n#\r\
    \n#----------SCRIPT INFORMATION-------------------------------------------\
    --------\r\
    \n#\r\
    \n# Script:  Mikrotik RouterOS automatic backup & update\r\
    \n# Version: 20.04.17\r\
    \n# Created: 07/08/2018\r\
    \n# Updated: 17/04/2020\r\
    \n# Author:  Alexander Tebiev\r\
    \n# Website: https://github.com/beeyev\r\
    \n# You can contact me by e-mail at tebiev@mail.com\r\
    \n#\r\
    \n# IMPORTANT!\r\
    \n# Minimum supported RouterOS version is v6.43.7\r\
    \n#\r\
    \n#----------MODIFY THIS SECTION AS NEEDED--------------------------------\
    --------\r\
    \n## Notification e-mail\r\
    \n## (Make sure you have configurated Email settings in Tools -> Email)\r\
    \n:local emailAddress \"kevin.blalock@gmail.com\";\r\
    \n\r\
    \n## Script mode, possible values: backup, osupdate, osnotify.\r\
    \n# backup     -     Only backup will be performed. (default value, if non\
    e provided)\r\
    \n#\r\
    \n# osupdate     -     The Script will install a new RouterOS if it is ava\
    ilable.\r\
    \n#                It will also create backups before and after update pro\
    cess.\r\
    \n#                Email will be sent only if a new RouterOS version is av\
    ailable.\r\
    \n#                Change parameter `forceBackup` if you need the script t\
    o create backups every time when it runs.\r\
    \n#\r\
    \n# osnotify     -     The script will send email notification only (witho\
    ut backups) if a new RouterOS is available.\r\
    \n#                Change parameter `forceBackup` if you need the script t\
    o create backups every time when it runs.\r\
    \n:local scriptMode \"backup\";\r\
    \n\r\
    \n## Additional parameter if you set `scriptMode` to `osupdate` or `osnoti\
    fy`\r\
    \n# Set `true` if you want the script to perform backup every time it's fi\
    red, whatever script mode is set.\r\
    \n:local forceBackup false;\r\
    \n\r\
    \n## Backup encryption password, no encryption if no password.\r\
    \n:local backupPassword \"\"\r\
    \n\r\
    \n## If true, passwords will be included in exported config.\r\
    \n:local sensetiveDataInConfig false;\r\
    \n\r\
    \n## Update channel. Possible values: stable, long-term, testing, developm\
    ent\r\
    \n:local updateChannel \"stable\";\r\
    \n\r\
    \n## Install only patch versions of RouterOS updates.\r\
    \n## Works only if you set scriptMode to \"osupdate\"\r\
    \n## Means that new update will be installed only if MAJOR and MINOR versi\
    on numbers remained the same as currently installed RouterOS.\r\
    \n## Example: v6.43.6 => major.minor.PATCH\r\
    \n## Script will send information if new version is greater than just patc\
    h.\r\
    \n:local installOnlyPatchUpdates    false;\r\
    \n\r\
    \n##----------------------------------------------------------------------\
    --------------------##\r\
    \n#  !!!! DO NOT CHANGE ANYTHING BELOW THIS LINE, IF YOU ARE NOT SURE WHAT\
    \_YOU ARE DOING !!!!  #\r\
    \n##----------------------------------------------------------------------\
    --------------------##\r\
    \n\r\
    \n#Script messages prefix\r\
    \n:local SMP \"Bkp&Upd:\"\r\
    \n\r\
    \n:log info \"\\r\\n\$SMP script \\\"Mikrotik RouterOS automatic backup & \
    update\\\" started.\";\r\
    \n:log info \"\$SMP Script Mode: \$scriptMode, forceBackup: \$forceBackup\
    \";\r\
    \n\r\
    \n#Check proper email config\r\
    \n:if ([:len \$emailAddress] = 0 or [:len [/tool e-mail get address]] = 0 \
    or [:len [/tool e-mail get from]] = 0) do={\r\
    \n    :log error (\"\$SMP Email configuration is not correct, please check\
    \_Tools -> Email. Script stopped.\");   \r\
    \n    :error \"\$SMP bye!\";\r\
    \n}\r\
    \n\r\
    \n#Check if proper identity name is set\r\
    \nif ([:len [/system identity get name]] = 0 or [/system identity get name\
    ] = \"MikroTik\") do={\r\
    \n    :log warning (\"\$SMP Please set identity name of your device (Syste\
    m -> Identity), keep it short and informative.\");  \r\
    \n};\r\
    \n\r\
    \n############### vvvvvvvvv GLOBALS vvvvvvvvv ###############\r\
    \n# Function converts standard mikrotik build versions to the number.\r\
    \n# Possible arguments: paramOsVer\r\
    \n# Example:\r\
    \n# :put [\$buGlobalFuncGetOsVerNum paramOsVer=[/system routerboard get cu\
    rrent-RouterOS]];\r\
    \n# result will be: 64301, because current RouterOS version is: 6.43.1\r\
    \n:global buGlobalFuncGetOsVerNum do={\r\
    \n    :local osVer \$paramOsVer;\r\
    \n    :local osVerNum;\r\
    \n    :local osVerMicroPart;\r\
    \n    :local zro 0;\r\
    \n    :local tmp;\r\
    \n    \r\
    \n    # Replace word `beta` with dot\r\
    \n    :local isBetaPos [:tonum [:find \$osVer \"beta\" 0]];\r\
    \n    :if (\$isBetaPos > 1) do={\r\
    \n        :set osVer ([:pick \$osVer 0 \$isBetaPos] . \".\" . [:pick \$osV\
    er (\$isBetaPos + 4) [:len \$osVer]]);\r\
    \n    }\r\
    \n    \r\
    \n    :local dotPos1 [:find \$osVer \".\" 0];\r\
    \n\r\
    \n    :if (\$dotPos1 > 0) do={ \r\
    \n\r\
    \n        # AA\r\
    \n        :set osVerNum  [:pick \$osVer 0 \$dotPos1];\r\
    \n        \r\
    \n        :local dotPos2 [:find \$osVer \".\" \$dotPos1];\r\
    \n                #Taking minor version, everything after first dot\r\
    \n        :if ([:len \$dotPos2] = 0)     do={:set tmp [:pick \$osVer (\$do\
    tPos1+1) [:len \$osVer]];}\r\
    \n        #Taking minor version, everything between first and second dots\
    \r\
    \n        :if (\$dotPos2 > 0)             do={:set tmp [:pick \$osVer (\$d\
    otPos1+1) \$dotPos2];}\r\
    \n        \r\
    \n        # AA 0B\r\
    \n        :if ([:len \$tmp] = 1)     do={:set osVerNum \"\$osVerNum\$zro\$\
    tmp\";}\r\
    \n        # AA BB\r\
    \n        :if ([:len \$tmp] = 2)     do={:set osVerNum \"\$osVerNum\$tmp\"\
    ;}\r\
    \n        \r\
    \n        :if (\$dotPos2 > 0) do={ \r\
    \n            :set tmp [:pick \$osVer (\$dotPos2+1) [:len \$osVer]];\r\
    \n            # AA BB 0C\r\
    \n            :if ([:len \$tmp] = 1) do={:set osVerNum \"\$osVerNum\$zro\$\
    tmp\";}\r\
    \n            # AA BB CC\r\
    \n            :if ([:len \$tmp] = 2) do={:set osVerNum \"\$osVerNum\$tmp\"\
    ;}\r\
    \n        } else={\r\
    \n            # AA BB 00\r\
    \n            :set osVerNum \"\$osVerNum\$zro\$zro\";\r\
    \n        }\r\
    \n    } else={\r\
    \n        # AA 00 00\r\
    \n        :set osVerNum \"\$osVer\$zro\$zro\$zro\$zro\";\r\
    \n    }\r\
    \n\r\
    \n    :return \$osVerNum;\r\
    \n}\r\
    \n\r\
    \n# Function creates backups (system and config) and returns array with na\
    mes\r\
    \n# Possible arguments: \r\
    \n#    `backupName`             | string    | backup file name, without ex\
    tension!\r\
    \n#    `backupPassword`        | string     |\r\
    \n#    `sensetiveDataInConfig`    | boolean     |\r\
    \n# Example:\r\
    \n# :put [\$buGlobalFuncCreateBackups name=\"daily-backup\"];\r\
    \n:global buGlobalFuncCreateBackups do={\r\
    \n    :log info (\"\$SMP Global function \\\"buGlobalFuncCreateBackups\\\"\
    \_was fired.\");  \r\
    \n    \r\
    \n    :local backupFileSys \"\$backupName.backup\";\r\
    \n    :local backupFileConfig \"\$backupName.rsc\";\r\
    \n    :local backupNames {\$backupFileSys;\$backupFileConfig};\r\
    \n\r\
    \n    ## Make system backup\r\
    \n    :if ([:len \$backupPassword] = 0) do={\r\
    \n        /system backup save dont-encrypt=yes name=\$backupName;\r\
    \n    } else={\r\
    \n        /system backup save password=\$backupPassword name=\$backupName;\
    \r\
    \n    }\r\
    \n    :log info (\"\$SMP System backup created. \$backupFileSys\");   \r\
    \n\r\
    \n    ## Export config file\r\
    \n    :if (\$sensetiveDataInConfig = true) do={\r\
    \n        /export compact file=\$backupName;\r\
    \n    } else={\r\
    \n        /export compact hide-sensitive file=\$backupName;\r\
    \n    }\r\
    \n    :log info (\"\$SMP Config file was exported. \$backupFileConfig\"); \
    \_ \r\
    \n\r\
    \n    #Delay after creating backups\r\
    \n    :delay 5s;    \r\
    \n    :return \$backupNames;\r\
    \n}\r\
    \n\r\
    \n:global buGlobalVarUpdateStep;\r\
    \n############### ^^^^^^^^^ GLOBALS ^^^^^^^^^ ###############\r\
    \n\r\
    \n#Current date time in format: 2020jan15-221324 \r\
    \n:local dateTime ([:pick [/system clock get date] 7 11] . [:pick [/system\
    \_clock get date] 0 3] . [:pick [/system clock get date] 4 6] . \"-\" . [:\
    pick [/system clock get time] 0 2] . [:pick [/system clock get time] 3 5] \
    . [:pick [/system clock get time] 6 8]);\r\
    \n\r\
    \n:local deviceOsVerInst             [/system package update get installed\
    -version];\r\
    \n:local deviceOsVerInstNum         [\$buGlobalFuncGetOsVerNum paramOsVer=\
    \$deviceOsVerInst];\r\
    \n:local deviceOsVerAvail         \"\";\r\
    \n:local deviceOsVerAvailNum         0;\r\
    \n:local deviceRbModel            [/system routerboard get model];\r\
    \n:local deviceRbSerialNumber     [/system routerboard get serial-number];\
    \r\
    \n:local deviceRbCurrentFw         [/system routerboard get current-firmwa\
    re];\r\
    \n:local deviceRbUpgradeFw         [/system routerboard get upgrade-firmwa\
    re];\r\
    \n:local deviceIdentityName         [/system identity get name];\r\
    \n:local deviceIdentityNameShort     [:pick \$deviceIdentityName 0 18]\r\
    \n:local deviceUpdateChannel         [/system package update get channel];\
    \r\
    \n\r\
    \n:local isOsUpdateAvailable     false;\r\
    \n:local isOsNeedsToBeUpdated    false;\r\
    \n\r\
    \n:local isSendEmailRequired    true;\r\
    \n\r\
    \n:local mailSubject           \"\$SMP Device - \$deviceIdentityNameShort.\
    \";\r\
    \n:local mailBody              \"\";\r\
    \n\r\
    \n:local mailBodyDeviceInfo    \"\\r\\n\\r\\nDevice information: \\r\\nIde\
    ntity: \$deviceIdentityName \\r\\nModel: \$deviceRbModel \\r\\nSerial numb\
    er: \$deviceRbSerialNumber \\r\\nCurrent RouterOS: \$deviceOsVerInst (\$[/\
    system package update get channel]) \$[/system resource get build-time] \\\
    r\\nCurrent routerboard FW: \$deviceRbCurrentFw \\r\\nDevice uptime: \$[/s\
    ystem resource get uptime]\";\r\
    \n:local mailBodyCopyright     \"\\r\\n\\r\\nMikrotik RouterOS automatic b\
    ackup & update \\r\\nhttps://github.com/beeyev/Mikrotik-RouterOS-automatic\
    -backup-and-update\";\r\
    \n:local changelogUrl            (\"Check RouterOS changelog: https://mikr\
    otik.com/download/changelogs/\" . \$updateChannel . \"-release-tree\");\r\
    \n\r\
    \n:local backupName             \"\$deviceIdentityName.\$deviceRbModel.\$d\
    eviceRbSerialNumber.v\$deviceOsVerInst.\$deviceUpdateChannel.\$dateTime\";\
    \r\
    \n:local backupNameBeforeUpd    \"backup_before_update_\$backupName\";\r\
    \n:local backupNameAfterUpd    \"backup_after_update_\$backupName\";\r\
    \n\r\
    \n:local backupNameFinal        \$backupName;\r\
    \n:local mailAttachments        [:toarray \"\"];\r\
    \n\r\
    \n:local updateStep \$buGlobalVarUpdateStep;\r\
    \n:do {/system script environment remove buGlobalVarUpdateStep;} on-error=\
    {}\r\
    \n:if ([:len \$updateStep] = 0) do={\r\
    \n    :set updateStep 1;\r\
    \n}\r\
    \n\r\
    \n\r\
    \n##     STEP ONE: Creating backups, checking for new RouterOs version and\
    \_sending email with backups,\r\
    \n##     steps 2 and 3 are fired only if script is set to automatically up\
    date device and if new RouterOs is available.\r\
    \n:if (\$updateStep = 1) do={\r\
    \n    :log info (\"\$SMP Performing the first step.\");   \r\
    \n\r\
    \n    # Checking for new RouterOS version\r\
    \n    if (\$scriptMode = \"osupdate\" or \$scriptMode = \"osnotify\") do={\
    \r\
    \n        log info (\"\$SMP Checking for new RouterOS version. Current ver\
    sion is: \$deviceOsVerInst\");\r\
    \n        /system package update set channel=\$updateChannel;\r\
    \n        /system package update check-for-updates;\r\
    \n        :delay 5s;\r\
    \n        :set deviceOsVerAvail [/system package update get latest-version\
    ];\r\
    \n\r\
    \n        # If there is a problem getting information about available Rout\
    erOS from server\r\
    \n        :if ([:len \$deviceOsVerAvail] = 0) do={\r\
    \n            :log warning (\"\$SMP There is a problem getting information\
    \_about new RouterOS from server.\");\r\
    \n            :set mailSubject    (\$mailSubject . \" Error: No data about\
    \_new RouterOS!\")\r\
    \n            :set mailBody         (\$mailBody . \"Error occured! \\r\\nM\
    ikrotik couldn't get any information about new RouterOS from server! \\r\\\
    nWatch additional information in device logs.\")\r\
    \n        } else={\r\
    \n            #Get numeric version of OS\r\
    \n            :set deviceOsVerAvailNum [\$buGlobalFuncGetOsVerNum paramOsV\
    er=\$deviceOsVerAvail];\r\
    \n\r\
    \n            # Checking if OS on server is greater than installed one.\r\
    \n            :if (\$deviceOsVerAvailNum > \$deviceOsVerInstNum) do={\r\
    \n                :set isOsUpdateAvailable true;\r\
    \n                :log info (\"\$SMP New RouterOS is available! \$deviceOs\
    VerAvail\");\r\
    \n            } else={\r\
    \n                :set isSendEmailRequired false;\r\
    \n                :log info (\"\$SMP System is already up to date.\");\r\
    \n                :set mailSubject (\$mailSubject . \" No new OS updates.\
    \");\r\
    \n                :set mailBody      (\$mailBody . \"Your system is up to \
    date.\");\r\
    \n            }\r\
    \n        };\r\
    \n    } else={\r\
    \n        :set scriptMode \"backup\";\r\
    \n    };\r\
    \n\r\
    \n    if (\$forceBackup = true) do={\r\
    \n        # In this case the script will always send email, because it has\
    \_to create backups\r\
    \n        :set isSendEmailRequired true;\r\
    \n    }\r\
    \n\r\
    \n    # if new OS version is available to install\r\
    \n    if (\$isOsUpdateAvailable = true and \$isSendEmailRequired = true) d\
    o={\r\
    \n        # If we only need to notify about new available version\r\
    \n        if (\$scriptMode = \"osnotify\") do={\r\
    \n            :set mailSubject     (\$mailSubject . \" New RouterOS is ava\
    ilable! v.\$deviceOsVerAvail.\")\r\
    \n            :set mailBody         (\$mailBody . \"New RouterOS version i\
    s available to install: v.\$deviceOsVerAvail (\$updateChannel) \\r\\n\$cha\
    ngelogUrl\")\r\
    \n        }\r\
    \n\r\
    \n        # if we need to initiate RouterOs update process\r\
    \n        if (\$scriptMode = \"osupdate\") do={\r\
    \n            :set isOsNeedsToBeUpdated true;\r\
    \n            # if we need to install only patch updates\r\
    \n            :if (\$installOnlyPatchUpdates = true) do={\r\
    \n                #Check if Major and Minor builds are the same.\r\
    \n                :if ([:pick \$deviceOsVerInstNum 0 ([:len \$deviceOsVerI\
    nstNum]-2)] = [:pick \$deviceOsVerAvailNum 0 ([:len \$deviceOsVerAvailNum]\
    -2)]) do={\r\
    \n                    :log info (\"\$SMP New patch version of RouterOS fir\
    mware is available.\");   \r\
    \n                } else={\r\
    \n                    :log info (\"\$SMP New major or minor version of Rou\
    terOS firmware is available. You need to update it manually.\");\r\
    \n                    :set mailSubject     (\$mailSubject . \" New RouterO\
    S: v.\$deviceOsVerAvail needs to be installed manually.\");\r\
    \n                    :set mailBody         (\$mailBody . \"New major or m\
    inor RouterOS version is available to install: v.\$deviceOsVerAvail (\$upd\
    ateChannel). \\r\\nYou chose to automatically install only patch updates, \
    so this major update you need to install manually. \\r\\n\$changelogUrl\")\
    ;\r\
    \n                    :set isOsNeedsToBeUpdated false;\r\
    \n                }\r\
    \n            }\r\
    \n\r\
    \n            #Check again, because this variable could be changed during \
    checking for installing only patch updats\r\
    \n            if (\$isOsNeedsToBeUpdated = true) do={\r\
    \n                :log info (\"\$SMP New RouterOS is going to be installed\
    ! v.\$deviceOsVerInst -> v.\$deviceOsVerAvail\");\r\
    \n                :set mailSubject    (\$mailSubject . \" New RouterOS is \
    going to be installed! v.\$deviceOsVerInst -> v.\$deviceOsVerAvail.\");\r\
    \n                :set mailBody         (\$mailBody . \"Your Mikrotik will\
    \_be updated to the new RouterOS version from v.\$deviceOsVerInst to v.\$d\
    eviceOsVerAvail (Update channel: \$updateChannel) \\r\\nFinal report with \
    the detailed information will be sent when update process is completed. \\\
    r\\nIf you have not received second email in the next 5 minutes, then prob\
    ably something went wrong. (Check your device logs)\");\r\
    \n                #!! There is more code connected to this part and first \
    step at the end of the script.\r\
    \n            }\r\
    \n        \r\
    \n        }\r\
    \n    }\r\
    \n\r\
    \n    ## Checking If the script needs to create a backup\r\
    \n    :log info (\"\$SMP Checking If the script needs to create a backup.\
    \");\r\
    \n    if (\$forceBackup = true or \$scriptMode = \"backup\" or \$isOsNeeds\
    ToBeUpdated = true) do={\r\
    \n        :log info (\"\$SMP Creating system backups.\");\r\
    \n        if (\$isOsNeedsToBeUpdated = true) do={\r\
    \n            :set backupNameFinal \$backupNameBeforeUpd;\r\
    \n        };\r\
    \n        if (\$scriptMode != \"backup\") do={\r\
    \n            :set mailBody (\$mailBody . \"\\r\\n\\r\\n\");\r\
    \n        };\r\
    \n\r\
    \n        :set mailSubject    (\$mailSubject . \" Backup was created.\");\
    \r\
    \n        :set mailBody        (\$mailBody . \"System backups were created\
    \_and attached to this email.\");\r\
    \n\r\
    \n        :set mailAttachments [\$buGlobalFuncCreateBackups backupName=\$b\
    ackupNameFinal backupPassword=\$backupPassword sensetiveDataInConfig=\$sen\
    setiveDataInConfig];\r\
    \n    } else={\r\
    \n        :log info (\"\$SMP There is no need to create a backup.\");\r\
    \n    }\r\
    \n\r\
    \n    # Combine fisrst step email\r\
    \n    :set mailBody (\$mailBody . \$mailBodyDeviceInfo . \$mailBodyCopyrig\
    ht);\r\
    \n}\r\
    \n\r\
    \n##     STEP TWO: (after first reboot) routerboard firmware upgrade\r\
    \n##     steps 2 and 3 are fired only if script is set to automatically up\
    date device and if new RouterOs is available.\r\
    \n:if (\$updateStep = 2) do={\r\
    \n    :log info (\"\$SMP Performing the second step.\");   \r\
    \n    ## RouterOS is the latest, let's check for upgraded routerboard firm\
    ware\r\
    \n    if (\$deviceRbCurrentFw != \$deviceRbUpgradeFw) do={\r\
    \n        :set isSendEmailRequired false;\r\
    \n        :delay 10s;\r\
    \n        :log info \"\$SMP Upgrading routerboard firmware from v.\$device\
    RbCurrentFw to v.\$deviceRbUpgradeFw\";\r\
    \n        ## Start the upgrading process\r\
    \n        /system routerboard upgrade;\r\
    \n        ## Wait until the upgrade is completed\r\
    \n        :delay 5s;\r\
    \n        :log info \"\$SMP routerboard upgrade process was completed, goi\
    ng to reboot in a moment!\";\r\
    \n        ## Set scheduled task to send final report on the next boot, tas\
    k will be deleted when is is done. (That is why you should keep original s\
    cript name)\r\
    \n        /system schedule add name=BKPUPD-FINAL-REPORT-ON-NEXT-BOOT on-ev\
    ent=\":delay 5s; /system scheduler remove BKPUPD-FINAL-REPORT-ON-NEXT-BOOT\
    ; :global buGlobalVarUpdateStep 3; :delay 10s; /system script run BackupAn\
    dUpdate;\" start-time=startup interval=0;\r\
    \n        ## Reboot system to boot with new firmware\r\
    \n        /system reboot;\r\
    \n    } else={\r\
    \n        :log info \"\$SMP It appers that your routerboard is already up \
    to date, skipping this step.\";\r\
    \n        :set updateStep 3;\r\
    \n    };\r\
    \n}\r\
    \n\r\
    \n##     STEP THREE: Last step (after second reboot) sending final report\
    \r\
    \n##     steps 2 and 3 are fired only if script is set to automatically up\
    date device and if new RouterOs is available.\r\
    \n:if (\$updateStep = 3) do={\r\
    \n    :log info (\"\$SMP Performing the third step.\");   \r\
    \n    :log info \"Bkp&Upd: RouterOS and routerboard upgrade process was co\
    mpleted. New RouterOS version: v.\$deviceOsVerInst, routerboard firmware: \
    v.\$deviceRbCurrentFw.\";\r\
    \n    ## Small delay in case mikrotik needs some time to initialize connec\
    tions\r\
    \n    :log info \"\$SMP The final email with report and backups of upgrade\
    d system will be sent in a minute.\";\r\
    \n    :delay 1m;\r\
    \n    :set mailSubject    (\$mailSubject . \" RouterOS Upgrade is complete\
    d, new version: v.\$deviceOsVerInst!\");\r\
    \n    :set mailBody           \"RouterOS and routerboard upgrade process w\
    as completed. \\r\\nNew RouterOS version: v.\$deviceOsVerInst, routerboard\
    \_firmware: v.\$deviceRbCurrentFw. \\r\\n\$changelogUrl \\r\\n\\r\\nBackup\
    s of the upgraded system are in the attachment of this email.  \$mailBodyD\
    eviceInfo \$mailBodyCopyright\";\r\
    \n    :set mailAttachments [\$buGlobalFuncCreateBackups backupName=\$backu\
    pNameAfterUpd backupPassword=\$backupPassword sensetiveDataInConfig=\$sens\
    etiveDataInConfig];\r\
    \n}\r\
    \n\r\
    \n# Remove functions from global environment to keep it fresh and clean.\r\
    \n:do {/system script environment remove buGlobalFuncGetOsVerNum;} on-erro\
    r={}\r\
    \n:do {/system script environment remove buGlobalFuncCreateBackups;} on-er\
    ror={}\r\
    \n\r\
    \n##\r\
    \n## SENDING EMAIL\r\
    \n##\r\
    \n# Trying to send email with backups in attachment.\r\
    \n\r\
    \n:if (\$isSendEmailRequired = true) do={\r\
    \n    :log info \"\$SMP Sending email message, it will take around half a \
    minute...\";\r\
    \n    :do {/tool e-mail send to=\$emailAddress subject=\$mailSubject body=\
    \$mailBody file=\$mailAttachments;} on-error={\r\
    \n        :delay 5s;\r\
    \n        :log error \"\$SMP could not send email message (\$[/tool e-mail\
    \_get last-status]). Going to try it again in a while.\"\r\
    \n\r\
    \n        :delay 5m;\r\
    \n\r\
    \n        :do {/tool e-mail send to=\$emailAddress subject=\$mailSubject b\
    ody=\$mailBody file=\$mailAttachments;} on-error={\r\
    \n            :delay 5s;\r\
    \n            :log error \"\$SMP could not send email message (\$[/tool e-\
    mail get last-status]) for the second time.\"\r\
    \n\r\
    \n            if (\$isOsNeedsToBeUpdated = true) do={\r\
    \n                :set isOsNeedsToBeUpdated false;\r\
    \n                :log warning \"\$SMP script is not going to initialise u\
    pdate process due to inability to send backups to email.\"\r\
    \n            }\r\
    \n        }\r\
    \n    }\r\
    \n\r\
    \n    :delay 30s;\r\
    \n    \r\
    \n    :if ([:len \$mailAttachments] > 0 and [/tool e-mail get last-status]\
    \_= \"succeeded\") do={\r\
    \n        :log info \"\$SMP File system cleanup.\"\r\
    \n        /file remove \$mailAttachments; \r\
    \n        :delay 2s;\r\
    \n    }\r\
    \n    \r\
    \n}\r\
    \n\r\
    \n\r\
    \n# Fire RouterOs update process\r\
    \nif (\$isOsNeedsToBeUpdated = true) do={\r\
    \n\r\
    \n    ## Set scheduled task to upgrade routerboard firmware on the next bo\
    ot, task will be deleted when upgrade is done. (That is why you should kee\
    p original script name)\r\
    \n    /system schedule add name=BKPUPD-UPGRADE-ON-NEXT-BOOT on-event=\":de\
    lay 5s; /system scheduler remove BKPUPD-UPGRADE-ON-NEXT-BOOT; :global buGl\
    obalVarUpdateStep 2; :delay 10s; /system script run BackupAndUpdate;\" sta\
    rt-time=startup interval=0;\r\
    \n   \r\
    \n   :log info \"\$SMP everything is ready to install new RouterOS, going \
    to reboot in a moment!\"\r\
    \n    ## command is reincarnation of the \"upgrade\" command - doing exact\
    ly the same but under a different name\r\
    \n    /system package update install;\r\
    \n}\r\
    \n\r\
    \n:log info \"\$SMP script \\\"Mikrotik RouterOS automatic backup & update\
    \\\" completed it's job.\\r\\n\";"
add dont-require-permissions=yes name=HostDown owner=admin policy=\
    ftp,reboot,read,write,policy,test,password,sniff,sensitive,romon source="/\
    tool e-mail send \\\r\
    \nto=\"kevin.blalock@gmail.com\" \\\r\
    \nsubject=\"HOST DOWN\" \\\r\
    \nbody=\"HOST DOWN\""
add dont-require-permissions=yes name=HostUp owner=admin policy=\
    ftp,reboot,read,write,policy,test,password,sniff,sensitive,romon source="/\
    tool e-mail send \\\r\
    \nto=\"kevin.blalock@gmail.com\" \\\r\
    \nsubject=\"HOST UP\" \\\r\
    \nbody=\"HOST UP\""
add dont-require-permissions=no name=wan-latency-test owner=admin policy=\
    read,write,test source=":put \"=== Spectrum WAN to 1.1.1.1 ===\"\
    \n/tool flood-ping 1.1.1.1 count=50 src-address=70.123.224.1\
    \n:put \"\"\
    \n:put \"=== ATT WAN to 1.1.1.1 ===\"\
    \n/tool flood-ping 1.1.1.1 count=50 src-address=99.126.112.1\
    \n:put \"\"\
    \n:put \"=== Spectrum WAN to 8.8.8.8 ===\"\
    \n/tool flood-ping 8.8.8.8 count=50 src-address=70.123.224.1\
    \n:put \"\"\
    \n:put \"=== ATT WAN to 8.8.8.8 ===\"\
    \n/tool flood-ping 8.8.8.8 count=50 src-address=99.126.112.1"
add dont-require-permissions=no name=fetch_att_modem owner=admin policy=\
    ftp,reboot,read,write,policy,test,password,sniff,sensitive,romon source="\
    \n:local result [/tool fetch url=\"http://192.168.2.254\" mode=http as-val\
    ue output=user]\
    \n:put (\$result->\"data\")\
    \n"
add dont-require-permissions=no name=test_att_tcp owner=admin policy=\
    ftp,reboot,read,write,policy,test,password,sniff,sensitive,romon source="\
    \n:log info \"Testing ATT connectivity with TCP\"\
    \n:local result [/tool fetch url=\"http://1.1.1.1\" mode=http src-address=\
    99.126.115.47 as-value output=user]\
    \n:put (\$result->\"status\")\
    \n:put (\$result->\"data\")\
    \n"
add dont-require-permissions=no name=test_spectrum_latency owner=admin \
    policy=ftp,reboot,read,write,policy,test,password,sniff,sensitive,romon \
    source="\
    \n:log info \"Testing Spectrum WAN latency\"\
    \n:local count 0\
    \n:local sum 0\
    \n:local min 999999\
    \n:local max 0\
    \n:local loss 0\
    \n\
    \n:for i from=1 to=50 do={\
    \n    :local result [/ping 1.1.1.1 count=1 interface=ether1-WAN-Spectrum a\
    s-value]\
    \n    :if ((\$result->\"received\") > 0) do={\
    \n        :local time (\$result->\"avg-rtt\")\
    \n        :set sum (\$sum + \$time)\
    \n        :set count (\$count + 1)\
    \n        :if (\$time < \$min) do={ :set min \$time }\
    \n        :if (\$time > \$max) do={ :set max \$time }\
    \n    } else={\
    \n        :set loss (\$loss + 1)\
    \n    }\
    \n}\
    \n\
    \n:if (\$count > 0) do={\
    \n    :local avg (\$sum / \$count)\
    \n    :put (\"Spectrum Results:\")\
    \n    :put (\"  Packets: sent=50 received=\$count loss=\$loss\")\
    \n    :put (\"  Latency: min=\$min avg=\$avg max=\$max\")\
    \n} else={\
    \n    :put \"Spectrum: All packets lost\"\
    \n}\
    \n"
add dont-require-permissions=no name=test_att_latency owner=admin policy=\
    ftp,reboot,read,write,policy,test,password,sniff,sensitive,romon source="\
    \n:log info \"Testing ATT WAN latency\"\
    \n:local count 0\
    \n:local sum 0\
    \n:local min 999999\
    \n:local max 0\
    \n:local loss 0\
    \n\
    \n:for i from=1 to=50 do={\
    \n    :local result [/ping 1.1.1.1 count=1 interface=ether2-WAN-ATT as-val\
    ue]\
    \n    :if ((\$result->\"received\") > 0) do={\
    \n        :local time (\$result->\"avg-rtt\")\
    \n        :set sum (\$sum + \$time)\
    \n        :set count (\$count + 1)\
    \n        :if (\$time < \$min) do={ :set min \$time }\
    \n        :if (\$time > \$max) do={ :set max \$time }\
    \n    } else={\
    \n        :set loss (\$loss + 1)\
    \n    }\
    \n}\
    \n\
    \n:if (\$count > 0) do={\
    \n    :local avg (\$sum / \$count)\
    \n    :put (\"ATT Results:\")\
    \n    :put (\"  Packets: sent=50 received=\$count loss=\$loss\")\
    \n    :put (\"  Latency: min=\$min avg=\$avg max=\$max\")\
    \n} else={\
    \n    :put \"ATT: All packets lost\"\
    \n}\
    \n"
add dont-require-permissions=no name=temp_export_1765055007 owner=admin \
    policy=ftp,reboot,read,write,policy,test,password,sniff,sensitive,romon \
    source="/export verbose file=backup_1765055007"
add dont-require-permissions=no name=qos-dashboard owner=admin policy=\
    read,policy,test source="\
    \n:log info \"[QOS] ===== QoS Dashboard =====\";\
    \n\
    \n# 1) Show summary of queue load\
    \n:put \"\
    \n[QUEUE TREE] Current rates:\";\
    \n/queue tree print stats without-paging;\
    \n\
    \n# 2) Show GAMES stats\
    \n:put \"\
    \n[MANGLE] GAMES rules (packets/bytes):\";\
    \n/ip firewall mangle print stats where comment~\"GAMES\";\
    \n\
    \n# 3) Show HIGH/RTC stats\
    \n:put \"\
    \n[MANGLE] HIGH / RTC rules (packets/bytes):\";\
    \n/ip firewall mangle print stats where comment~\"HIGH\";\
    \n\
    \n# 4) Show class usage by DSCP mapping\
    \n:put \"\
    \n[MANGLE] DSCP class mapping stats:\";\
    \n/ip firewall mangle print stats where comment~\"DSCP:\";\
    \n\
    \n# 5) Active GAMES connections\
    \n:put \"\
    \n[CONNTRACK] Active GAMES connections:\";\
    \n/ip firewall connection print where connection-mark=GAMES;\
    \n\
    \n# 6) Active HIGH connections (work VPN, RTC, etc.)\
    \n:put \"\
    \n[CONNTRACK] Active QOS_HIGH connections:\";\
    \n/ip firewall connection print where connection-mark=QOS_HIGH;\
    \n\
    \n:put \"\
    \n[QOS] ===== End QoS Dashboard =====\";\
    \n"
add dont-require-permissions=no name=qos-dashboard-2 owner=admin policy=\
    ftp,reboot,read,write,policy,test,password,sniff,sensitive,romon source="\
    \n:put \"[QOS] ===== QoS / Games Dashboard =====\";\
    \n\
    \n:put \"\
    \n[QUEUE TREE] Current rates:\";\
    \n/queue tree print stats without-paging;\
    \n\
    \n:put \"\
    \n[MANGLE] GAMES rules (bytes/packets):\";\
    \n/ip firewall mangle print stats where comment~\"GAMES\";\
    \n\
    \n:put \"\
    \n[ADDR-LIST] auto-games (short-term auto-learned):\";\
    \n/ip firewall address-list print where list=\"auto-games\";\
    \n\
    \n:put \"\
    \n[ADDR-LIST] auto-games-promoted (long-term memory):\";\
    \n/ip firewall address-list print where list=\"auto-games-promoted\";\
    \n\
    \n:put \"\
    \n[ADDR-LIST] blizzard-games (if used):\";\
    \n/ip firewall address-list print where list=\"blizzard-games\";\
    \n\
    \n:put \"\
    \n[ADDR-LIST] steam-games (if used):\";\
    \n/ip firewall address-list print where list=\"steam-games\";\
    \n\
    \n:put \"\
    \n[MANGLE] DSCP class mapping stats:\";\
    \n/ip firewall mangle print stats where comment~\"DSCP:\";\
    \n\
    \n:put \"\
    \n[CONNTRACK] Active GAMES connections:\";\
    \n/ip firewall connection print where connection-mark=GAMES;\
    \n\
    \n:put \"\
    \n[CONNTRACK] Active QOS_HIGH connections (DNS/DoT/WiFi calling/etc.):\";\
    \n/ip firewall connection print where connection-mark=QOS_HIGH;\
    \n\
    \n:put \"\
    \n[QOS] ===== End QoS / Games Dashboard =====\";\
    \n"
add dont-require-permissions=no name=blizzard-update owner=admin policy=\
    ftp,reboot,read,write,policy,test,password,sniff,sensitive,romon source="\
    \n# Refresh blizzard-games address list for Diablo / Blizzard titles\
    \n\
    \n# 1) Clear existing entries\
    \n/ip firewall address-list remove [find list=blizzard-games]\
    \n\
    \n# 2) Dynamic domains (single IPs, refreshed every run)\
    \n:local domains {\
    \n    \"us.actual.battle.net\";\
    \n    \"prod.actual.battle.net\";\
    \n    \"gameplay.blizzard.com\";\
    \n    \"instance-server.blizzard.com\";\
    \n}\
    \n\
    \n/:foreach d in=\$domains do={\
    \n    :local resolved [:resolve \$d]\
    \n    :if ([:len \$resolved] > 0) do={\
    \n        /ip firewall address-list add list=blizzard-games address=\$reso\
    lved timeout=12h comment=(\"dyn-\".\$d)\
    \n    }\
    \n}\
    \n\
    \n# 3) Static fallback subnets (Cloudflare + GCP hosting Blizzard infra)\
    \n:foreach net in={\
    \n    \"162.159.128.0/19\";\
    \n    \"162.159.136.0/22\";\
    \n    \"162.159.192.0/19\";\
    \n    \"34.125.0.0/16\";\
    \n    \"34.133.0.0/16\";\
    \n} do={\
    \n    /ip firewall address-list add list=blizzard-games address=\$net time\
    out=30d comment=\"blizzard-range\"\
    \n}\
    \n"
add dont-require-permissions=no name=steam-update owner=admin policy=\
    ftp,reboot,read,write,policy,test,password,sniff,sensitive,romon source="\
    \n# Refresh steam-games address list for Steam / Valve game traffic\
    \n\
    \n# 1) Clear existing entries\
    \n/ip firewall address-list remove [find list=steam-games]\
    \n\
    \n# 2) Dynamic Steam core domains\
    \n:local domains {\
    \n    \"steamserver.net\";\
    \n    \"steamcontent.com\";\
    \n    \"steam-chat.com\";\
    \n    \"steamconnection.com\";\
    \n}\
    \n\
    \n/:foreach d in=\$domains do={\
    \n    :local resolved [:resolve \$d]\
    \n    :if ([:len \$resolved] > 0) do={\
    \n        /ip firewall address-list add list=steam-games address=\$resolve\
    d timeout=12h comment=(\"dyn-\".\$d)\
    \n    }\
    \n}\
    \n\
    \n# 3) Copy your existing Valve Network ranges into steam-games for QoS\
    \n:foreach r in=[/ip firewall address-list find list=\"Valve Network\"] do\
    ={\
    \n    :local addr [/ip firewall address-list get \$r address]\
    \n    :local existing [/ip firewall address-list find list=steam-games add\
    ress=\$addr]\
    \n    :if (\$existing = \"\") do={\
    \n        /ip firewall address-list add list=steam-games address=\$addr ti\
    meout=30d comment=\"valve-range\"\
    \n    }\
    \n}\
    \n"
add dont-require-permissions=no name=script1 owner=admin policy=\
    ftp,reboot,read,write,policy,test,password,sniff,sensitive,romon source=":\
    foreach i in=[1,2,3] do={\
    \n    :if (\$i = 2) do={\
    \n        :continue\
    \n    }\
    \n    :put (\"i=\" . \$i)\
    \n}\
    \n"
add dont-require-permissions=no name=Disable-Spectrum owner=admin policy=\
    ftp,reboot,read,write,policy,test,password,sniff,sensitive source=\
    "\
    \n/ip route disable [find comment=\"Spectrum\"]\
    \n"
add dont-require-permissions=no name=Enable-Spectrum owner=admin policy=\
    ftp,reboot,read,write,policy,test,password,sniff,sensitive source=\
    "\
    \n:delay 5s\
    \n/ip route enable [find comment=\"Spectrum\"]\
    \n"
add dont-require-permissions=no name=Disable-ATT owner=admin policy=\
    ftp,reboot,read,write,policy,test,password,sniff,sensitive source="\
    \n/ip route disable [find comment=\"ATT\"]\
    \n/ip route disable [find comment=\"Force ATT_OUT to ATT WAN\"]\
    \n"
add dont-require-permissions=no name=Enable-ATT owner=admin policy=\
    ftp,reboot,read,write,policy,test,password,sniff,sensitive source="\
    \n:delay 5s\
    \n/ip route enable [find comment=\"ATT\"]\
    \n/ip route enable [find comment=\"Force ATT_OUT to ATT WAN\"]\
    \n"
add dont-require-permissions=no name=game-qos-engine owner=admin policy=\
    read,write,test source=":local minRateUdp 20000\
    \n:local minRateTcp 10000\
    \n:local minBytesUdp 30000\
    \n:local minBytesTcp 50000\
    \n\
    \n:foreach gd in=[/ip firewall address-list find list=GAMER-DEVICES] do={\
    \n\
    \n    :local gsrc [/ip firewall address-list get \$gd address]\
    \n\
    \n    :local slashPos [:find \$gsrc \"/\"]\
    \n    :if (\$slashPos != nil) do={ :set gsrc [:pick \$gsrc 0 \$slashPos] }\
    \n\
    \n    :foreach c in=[/ip firewall connection find src-address=\$gsrc] do={\
    \n\
    \n        :local proto [/ip firewall connection get \$c protocol]\
    \n        :local dst [/ip firewall connection get \$c dst-address]\
    \n        :local dport [/ip firewall connection get \$c dst-port]\
    \n        :local rate [/ip firewall connection get \$c orig-rate]\
    \n\
    \n        :if (\$rate < 5000) do={ :set dst \"\"; }\
    \n\
    \n        :if (\$dst != \"\") do={ \
    \n            :if ([:pick \$dst 0 3] = \"10.\") do={ :set dst \"\" }\
    \n        }\
    \n        :if (\$dst != \"\") do={ \
    \n            :if ([:pick \$dst 0 4] = \"192.\") do={ :set dst \"\" }\
    \n        }\
    \n        :if (\$dst != \"\") do={ \
    \n            :if ([:pick \$dst 0 4] = \"172.\") do={ :set dst \"\" }\
    \n        }\
    \n        :if (\$dst = \"255.255.255.255\") do={ :set dst \"\" }\
    \n        :if (\$dst != \"\") do={ \
    \n            :if ([:pick \$dst 0 4] = \"224.\") do={ :set dst \"\" }\
    \n        }\
    \n\
    \n        :if (\$dst = \"\") do={ :set gsrc \$gsrc; :set dst \"\"; :set dp\
    ort \$dport; } else={}\
    \n\
    \n        :local ignore false\
    \n\
    \n        :if (\$proto=\"udp\") do={\
    \n            :if (\$dport=53 || \$dport=67 || \$dport=68 || \$dport=123 |\
    | \$dport=500 || \$dport=1900 || \$dport=5353) do={ :set ignore true }\
    \n        }\
    \n        :if (\$proto=\"tcp\") do={\
    \n            :if (\$dport=22 || \$dport=25 || \$dport=80 || \$dport=110 |\
    | \$dport=143 || \$dport=443 || \$dport=8080 || \$dport=8443 || \$dport=99\
    3 || \$dport=995 || \$dport=853 || \$dport=5223 || \$dport=5228) do={ :set\
    \_ignore true }\
    \n        }\
    \n\
    \n        :if (\$ignore = true) do={ :set dst \"\"; }\
    \n\
    \n        :if (\$dst = \"\") do={ :set proto \$proto } else={}\
    \n\
    \n        :if (\$dst != \"\") do={\
    \n\
    \n            :local obytes [/ip firewall connection get \$c orig-bytes]\
    \n            :local rbytes [/ip firewall connection get \$c repl-bytes]\
    \n            :local bytes (\$obytes + \$rbytes)\
    \n\
    \n            :local isGame false\
    \n\
    \n            :if (\$proto=\"udp\") do={\
    \n                :if (\$dport >= 1024 && \$rate >= \$minRateUdp && \$byte\
    s >= \$minBytesUdp) do={ :set isGame true }\
    \n            }\
    \n\
    \n            :if (\$proto=\"tcp\") do={\
    \n                :if (\$dport >= 1024 && \$rate >= \$minRateTcp && \$byte\
    s >= \$minBytesTcp) do={ :set isGame true }\
    \n            }\
    \n\
    \n            :if (\$isGame = true) do={\
    \n\
    \n                :local slashPos2 [:find \$dst \"/\"]\
    \n                :if (\$slashPos2 != nil) do={ :set dst [:pick \$dst 0 \$\
    slashPos2] }\
    \n\
    \n                :if ([:len [/ip firewall address-list find list=auto-gam\
    es address=\$dst]] = 0) do={\
    \n                    /ip firewall address-list add list=auto-games addres\
    s=\$dst timeout=6h\
    \n                }\
    \n            }\
    \n        }\
    \n    }\
    \n}\
    \n\
    \n:foreach e in=[/ip firewall address-list find list=auto-games] do={\
    \n\
    \n    :local addr [/ip firewall address-list get \$e address]\
    \n    :local totalPkts 0\
    \n    :local flows 0\
    \n\
    \n    :local slashPos [:find \$addr \"/\"]\
    \n    :if (\$slashPos != nil) do={ :set addr [:pick \$addr 0 \$slashPos] }\
    \n\
    \n    :foreach c in=[/ip firewall connection find dst-address=\$addr] do={\
    \n        :local opk [/ip firewall connection get \$c orig-packets]\
    \n        :local rpk [/ip firewall connection get \$c repl-packets]\
    \n        :local p (\$opk + \$rpk)\
    \n\
    \n        :if (\$p >= 20) do={\
    \n            :set totalPkts (\$totalPkts + \$p)\
    \n            :set flows (\$flows + 1)\
    \n        }\
    \n    }\
    \n\
    \n    :if (\$flows > 0 && \$totalPkts > 3000) do={\
    \n\
    \n        :if ([:len [/ip firewall address-list find list=auto-games-promo\
    ted address=\$addr]] = 0) do={\
    \n            /ip firewall address-list add list=auto-games-promoted addre\
    ss=\$addr timeout=30d comment=\"promoted\"\
    \n        }\
    \n    }\
    \n}\
    \n"
/system watchdog
set auto-send-supout=no automatic-supout=yes ping-start-after-boot=5m \
    ping-timeout=1m watch-address=none watchdog-timer=yes
/tool bandwidth-server
set allocate-udp-ports-from=1000 allowed-addresses4="" allowed-addresses6="" \
    authenticate=yes enabled=yes max-sessions=100
/tool e-mail
set from=kevin.blalock@gmail.com port=465 server=smtp.gmail.com tls=yes user=\
    kevin.blalock@gmail.com vrf=main
/tool graphing
set page-refresh=300 store-every=5min
/tool graphing interface
add allow-address=0.0.0.0/0 disabled=no interface=all store-on-disk=yes
add allow-address=0.0.0.0/0 disabled=no interface=ether1-WAN-Spectrum \
    store-on-disk=yes
add allow-address=0.0.0.0/0 disabled=no interface=ether2-WAN-ATT \
    store-on-disk=yes
/tool graphing queue
add allow-address=0.0.0.0/0 allow-target=yes disabled=no simple-queue=all \
    store-on-disk=yes
/tool graphing resource
add allow-address=0.0.0.0/0 disabled=no store-on-disk=yes
add allow-address=0.0.0.0/0 disabled=no store-on-disk=yes
/tool mac-server
set allowed-interface-list=all
/tool mac-server mac-winbox
set allowed-interface-list=all
/tool mac-server ping
set enabled=yes
/tool netwatch
add disabled=yes down-script="system script run HostDown" host=70.123.241.22 \
    http-codes="" interval=10s test-script="" timeout=1s type=icmp up-script=\
    "system script run HostUp"
add down-script="/ip route disable [find comment='Spectrum']" host=\
    70.123.224.1 interval=2s name=Monitor-Spectrum timeout=1s200ms type=\
    simple up-script="/ip route enable [find comment='Spectrum']"
add down-script="/ip route disable [find comment='ATT']; /ip route disable [fi\
    nd comment='Force ATT_OUT to ATT WAN']" host=99.126.112.1 interval=2s \
    name=Monitor-ATT timeout=1s200ms type=simple up-script="/ip route enable [\
    find comment='ATT']; /ip route enable [find comment='Force ATT_OUT to ATT \
    WAN']"
add down-script="/system/script/run Disable-Spectrum" host=70.123.224.1 \
    interval=2s name=Monitor-Spectrum timeout=1s200ms type=simple up-script=\
    "/system/script/run Enable-Spectrum"
add down-script="/system/script/run Disable-ATT" host=99.126.112.1 interval=\
    2s name=Monitor-ATT timeout=1s200ms type=simple up-script=\
    "/system/script/run Enable-ATT"
/tool romon
set enabled=yes id=00:00:00:00:00:00
/tool romon port
set [ find default=yes ] cost=100 disabled=no forbid=no interface=all
/tool sms
set allowed-number="" channel=0 polling=no port=none receive-enabled=no \
    remove-sent-sms-after-send=no sms-storage=sim
/tool sniffer
set file-limit=1000KiB file-name=debug.pcap filter-cpu="" filter-direction=\
    any filter-dst-ip-address="" filter-dst-ipv6-address="" \
    filter-dst-mac-address="" filter-dst-port="" filter-interface=\
    ether1-WAN-Spectrum filter-ip-address=174.47.171.10/32 \
    filter-ip-protocol="" filter-ipv6-address="" filter-mac-address="" \
    filter-mac-protocol="" filter-operator-between-entries=or filter-port="" \
    filter-size="" filter-src-ip-address="" filter-src-ipv6-address="" \
    filter-src-mac-address="" filter-src-port="" filter-stream=yes \
    filter-vlan="" max-packet-size=2048 memory-limit=100KiB memory-scroll=yes \
    only-headers=no quick-rows=20 quick-show-frame=no streaming-enabled=no \
    streaming-server=10.10.110.218:37008
/tool traffic-generator
set latency-distribution-max=100us measure-out-of-order=no \
    stats-samples-to-keep=100 test-id=0
/user aaa
set accounting=yes default-group=read exclude-groups="" interim-update=0s \
    use-radius=no
/user settings
set minimum-categories=0 minimum-password-length=0
/user-manager
set accounting-port=1813 authentication-port=1812 certificate=*0 enabled=yes \
    require-message-auth=no use-profiles=no
/user-manager advanced
set paypal-allow=no paypal-currency=USD paypal-signature="" \
    paypal-use-sandbox=no paypal-user="" web-private-username=""
/zerotier controller member
add authorized=yes bridge=no disabled=no disabled=no ip-address=172.27.27.18 \
    name="" network=ZT-private zt-address=46f4a69fae
add authorized=yes bridge=no disabled=no disabled=no ip-address=172.27.27.14 \
    name="" network=ZT-private zt-address=3b60e18604
add authorized=yes bridge=no disabled=no disabled=no ip-address=172.27.27.17 \
    name="" network=ZT-private zt-address=b48025addb
add authorized=yes bridge=no disabled=no disabled=no ip-address=172.27.27.16 \
    name="" network=ZT-private zt-address=8bf63fa890
add authorized=yes bridge=no disabled=no disabled=no ip-address=172.27.27.19 \
    name="" network=ZT-private zt-address=16047ee976
add authorized=yes bridge=no disabled=no disabled=no ip-address=172.27.27.10 \
    name="" network=ZT-private zt-address=bb723ccdce
