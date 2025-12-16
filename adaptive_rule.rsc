/ip firewall mangle add \
  chain=prerouting \
  action=mark-routing \
  new-routing-mark=to_ATT \
  passthrough=no \
  connection-state=new \
  connection-mark=LATENCY_SENSITIVE \
  dst-address=!10.10.0.0/16 \
  disabled=yes \
  comment="ADAPTIVE: Steer latency-sensitive to ATT"
