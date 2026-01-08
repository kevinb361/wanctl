# wanctl v1.0.0-rc4

**Release Candidate 4** - REST API transport for 2x faster congestion response.

## What's New in RC4

### REST API Transport (Recommended)

Added RouterOS REST API as the recommended transport method, providing significantly faster congestion control compared to SSH:

| Metric | REST API | SSH/Paramiko | Improvement |
|--------|----------|--------------|-------------|
| Peak RTT | 194ms | 404ms | **2.1x better** |
| Command latency | ~50ms | ~150-200ms | **3-4x faster** |
| RED/RED cycles | 0 | 5 | **No hard congestion** |
| Download stability | Stable | 55% reduction | **No unnecessary backoff** |

**Why it matters**: Faster command execution means the controller can reduce bandwidth before congestion spirals out of control. In stress testing, REST API prevented all RED/RED (hard congestion) cycles while SSH experienced 5.

### New Files

- `src/wanctl/routeros_rest.py` - REST API client using requests library
- `src/wanctl/router_client.py` - Transport abstraction factory
- `docs/TRANSPORT_COMPARISON.md` - Full comparison with raw stress test data

### Configuration

Select transport via config:

```yaml
router:
  transport: "rest"  # "rest" (recommended) or "ssh"
  host: "<router-ip>"
  user: "admin"

  # For REST API
  password: "${ROUTER_PASSWORD}"  # From /etc/wanctl/secrets
  port: 443
  verify_ssl: false

  # For SSH (fallback)
  ssh_key: "/etc/wanctl/ssh/router.key"
```

### Secrets Management

REST API requires password authentication. Credentials are stored securely:

```bash
# /etc/wanctl/secrets (mode 640, root:wanctl)
ROUTER_PASSWORD=your_password_here
```

The install script now creates this file with proper permissions automatically.

### RouterOS Setup

Enable REST API on your MikroTik:

```routeros
/ip service set www-ssl disabled=no port=443
/certificate add name=local-cert common-name=router
/ip service set www-ssl certificate=local-cert
```

### Other Changes

- **Paramiko persistent connections** - SSH transport now reuses connections (faster even if not using REST)
- **Deploy script fixes** - Proper file permissions (644) on deployed Python files
- **Install script updates** - Creates secrets file template with correct ownership

## Upgrade Notes

### From RC3

1. **Optional**: Switch to REST transport for better performance
   - Enable REST API on router (see above)
   - Add password to `/etc/wanctl/secrets`
   - Set `transport: "rest"` in config

2. **No breaking changes** - SSH transport continues to work unchanged

### From RC2 or earlier

See RC3 release notes for the `cake` → `wanctl` package rename.

## System Requirements

- Python 3.12+
- MikroTik RouterOS 7.x with REST API enabled (for REST transport)
- SSH key or password authentication to router
- Linux host (tested on Debian 12, Ubuntu 22.04)

## Dependencies

New dependency added:
- `requests>=2.31.0` - For REST API transport

## Testing This Release

1. **REST API** - Test with `transport: "rest"` and verify faster response
2. **SSH fallback** - Confirm SSH still works with `transport: "ssh"`
3. **Secrets** - Verify `/etc/wanctl/secrets` permissions are 640
4. **Stress test** - Run parallel uploads and observe congestion handling

## Documentation

- `docs/TRANSPORT_COMPARISON.md` - Detailed REST vs SSH comparison with raw test data
- `docs/QUICKSTART.md` - Updated with REST API setup instructions

## Known Limitations

- REST API requires password (no SSH key support)
- Self-signed certificates require `verify_ssl: false`
- RouterOS 7.x required for REST API

## Acknowledgments

- [LibreQoS](https://libreqos.io/) - Inspiration for CAKE-based QoS
- [MikroTik REST API](https://help.mikrotik.com/docs/display/ROS/REST+API) - Fast router control
- Claude (Anthropic) - AI-assisted development

## License

GPL-2.0 - See [LICENSE](LICENSE) for details.

---

**Full Changelog**: https://github.com/kevinb361/wanctl/compare/v1.0.0-rc3...v1.0.0-rc4
