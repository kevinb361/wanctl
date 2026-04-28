# Security

wanctl controls production network shaping state. Treat router credentials,
systemd environment files, SSH keys, and deployment logs as sensitive.

## Credential Handling

- Keep plaintext router passwords out of YAML files.
- Store secrets in `/etc/wanctl/secrets` and load them through systemd `EnvironmentFile`.
- Reference secrets in YAML with environment-variable expansion, for example `${ROUTER_PASSWORD}`.
- Keep `/etc/wanctl/secrets` readable only by root and the service context that needs it.

## RouterOS Transports

REST is the recommended RouterOS control transport when available. Use HTTPS and
set certificate verification according to your router certificate posture.

SSH remains supported. When using SSH:

- keep the private key under `/etc/wanctl/ssh/router.key` or another root-managed path.
- set ownership and permissions so only the service user can read it.
- keep router SSH host keys in the `wanctl` service user's `known_hosts` file.

Example SSH-key setup:

```bash
sudo install -o wanctl -g wanctl -m 700 -d /var/lib/wanctl/.ssh
sudo -u wanctl ssh-keyscan -H <router_ip> >> /var/lib/wanctl/.ssh/known_hosts
sudo install -o wanctl -g wanctl -m 600 ~/.ssh/router_key /etc/wanctl/ssh/router.key
```

Do not disable SSH host-key checking globally or reintroduce `StrictHostKeyChecking=no`.

## Configuration Safety

Validate configs before restart:

```bash
wanctl-check-config --config /etc/wanctl/<wan>.yaml
```

Queue names, mangle comments, URL fields, thresholds, and cross-field transport
settings are validated before runtime use. Treat validation failures as deploy
blockers until reviewed.

## Runtime Surfaces

- `/health` and `/metrics` are intended for trusted local or management-network access.
- Do not expose health endpoints directly to the public internet.
- Logs can contain router hostnames, WAN names, queue names, and operational topology.
- Historical artifacts under `docs/archive/`, `.planning/`, and local graph outputs may contain site-specific details.

## Deployment Checklist

- Secrets are in `/etc/wanctl/secrets`, not committed config files.
- SSH keys and `known_hosts` are owned by the service user with restrictive permissions.
- REST TLS posture is intentional and documented in the target config.
- `wanctl-check-config` passes before restart.
- Post-deploy canary and `/health` checks pass after restart.
