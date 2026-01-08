# wanctl v1.0.0-rc5

**Release Candidate 5** - Interactive setup wizard for guided first-time installation.

## What's New in RC5

### Interactive Setup Wizard

The install script now includes a complete interactive wizard that guides you through first-time setup:

```bash
sudo ./scripts/install.sh
```

**Wizard Features:**

| Feature | Description |
|---------|-------------|
| Router Connection | Configure REST API or SSH transport |
| Connection Testing | Validates credentials with retry/re-enter/skip options |
| Queue Discovery | Auto-detects existing CAKE queues from your router |
| Connection Presets | Optimized defaults for cable/DSL/fiber |
| Multi-WAN Guidance | Architecture explanation for dual-WAN deployments |
| Steering Setup | Optional traffic steering configuration |

### Wizard Modes

```bash
# Interactive wizard (default)
sudo ./scripts/install.sh

# Non-interactive for automation
sudo ./scripts/install.sh --no-wizard

# Re-run wizard on existing installation
sudo ./scripts/install.sh --reconfigure

# Remove wanctl completely
sudo ./scripts/install.sh --uninstall
```

### Auto-Dependency Installation

The installer now automatically installs required packages:

- `python3-yaml` - YAML configuration parsing
- `python3-pexpect` - SSH command execution
- `bc` - Floor calculation scaling

### Connection Testing

After entering credentials, the wizard tests the connection:

```
[*] Testing connection to 10.10.99.1...
[+] REST API connection successful
```

If connection fails, you can:
1. Retry the connection test
2. Re-enter credentials
3. Skip and continue anyway

### Queue Discovery

The wizard queries your router for existing queue tree entries:

```
[*] Discovering queues from router...
[+] Found 4 queue(s)

Select DOWNLOAD queue:
  Discovered queues:
    1) WAN-Download-Spectrum
    2) WAN-Download-ATT
    3) WAN-Upload-Spectrum
    4) WAN-Upload-ATT
    5) Enter manually
Choice [1-5]:
```

### Connection-Type Presets

Smart defaults based on your connection type:

| Setting | Cable | DSL | Fiber |
|---------|-------|-----|-------|
| Baseline RTT | 24ms | 31ms | 8ms |
| State Model | 4-state | 3-state | 4-state |
| Floor Scaling | By speed | Fixed | By speed |
| Ping Strategy | Median of 3 | Single | Single |

## Bug Fixes

- **Password injection fix** - Passwords with special characters (`/`, `&`, `\`) now stored correctly
- **SSH key path fix** - Uses `$SUDO_USER` home directory when run with sudo
- **bc dependency** - Auto-installed; fallback to bash arithmetic if unavailable
- **Color codes** - Fixed escape sequences in multi-WAN architecture display

## Upgrade Notes

### From RC4

No breaking changes. The wizard is additive:

1. **New installs**: Run `sudo ./scripts/install.sh` for guided setup
2. **Existing installs**: Use `--reconfigure` to re-run wizard, or continue using manual config

### From RC3 or earlier

See RC3/RC4 release notes for:
- `cake` → `wanctl` package rename (RC3)
- REST API transport setup (RC4)

## System Requirements

- Python 3.11+ (3.12 recommended)
- MikroTik RouterOS 7.x
- Linux host with systemd (Debian 12, Ubuntu 22.04+)
- Root access for installation

## Testing This Release

1. **Fresh install** - Run wizard on a clean system
2. **Reconfigure** - Test `--reconfigure` on existing installation
3. **Connection test** - Verify REST and SSH connection testing work
4. **Queue discovery** - Confirm queues are discovered from router
5. **Special characters** - Test password with `@`, `/`, `&` characters

## Documentation

- `README.md` - Updated with wizard-first installation instructions
- `CHANGELOG.md` - Full feature list and bug fixes

## Known Limitations

- Queue discovery requires working router connection
- Wizard requires interactive terminal (use `--no-wizard` for scripts)
- Color output requires terminal with ANSI support

## Acknowledgments

- [LibreQoS](https://libreqos.io/) - Inspiration for CAKE-based QoS
- [MikroTik REST API](https://help.mikrotik.com/docs/display/ROS/REST+API) - Fast router control
- Claude (Anthropic) - AI-assisted development

## License

GPL-2.0 - See [LICENSE](LICENSE) for details.

---

**Full Changelog**: https://github.com/kevinb361/wanctl/compare/v1.0.0-rc4...v1.0.0-rc5
