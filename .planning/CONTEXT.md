# Context: wanctl

## Glossary

### QoS classification contract
The explicit handoff between the host-aware RouterOS classifier and the inline cake-shaper enforcer. RouterOS emits normalized EF, AF31, CS0, or CS1; cake-shaper trusts those values only from router-facing interfaces, stores the class in bridge conntrack, washes carrier markings, and restores the class before download CAKE.

### Classifier
The component that decides traffic intent using identity and policy. RouterOS is authoritative because it sees original LAN addresses, VLAN/device policy, connection state, and the routing decision before NAT.

### Enforcer
The component that controls the bottleneck queue. cake-shaper is authoritative for CAKE scheduling and autorate; its bridge rules translate the classification contract but do not become a second application-policy source.

### Steering eligibility
A routing-policy decision distinct from queue priority. High-priority traffic is not automatically eligible for AT&T steering; eligibility must be explicit and apply without changing established connection paths.
