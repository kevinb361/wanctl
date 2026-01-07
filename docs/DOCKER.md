# Docker Deployment Guide

This guide explains how to run wanctl in Docker containers.

## Overview

Docker provides an alternative deployment method for wanctl. Each WAN gets its own container running the continuous monitoring daemon.

**When to use Docker:**
- You prefer container-based deployments
- You want easy updates via image rebuilds
- You need isolation between WAN controllers

**When to use bare metal/LXC:**
- Lower latency overhead is critical
- You're already using systemd-based infrastructure
- Resource constraints (Docker has ~5-10MB memory overhead)

## Quick Start

### 1. Build the Image

```bash
cd /path/to/wanctl
docker build -t wanctl -f docker/Dockerfile .
```

### 2. Prepare Configuration

```bash
# Create directories
mkdir -p docker/configs docker/ssh docker/state docker/logs

# Copy and customize config
cp configs/examples/wan1.yaml.example docker/configs/wan1.yaml
# Edit docker/configs/wan1.yaml with your settings

# Copy SSH key for router access
cp ~/.ssh/router_key docker/ssh/router.key
chmod 600 docker/ssh/router.key
```

### 3. Run Single WAN

```bash
docker run -d \
  --name wanctl-wan1 \
  --network host \
  -v $(pwd)/docker/configs/wan1.yaml:/etc/wanctl/wan.yaml:ro \
  -v $(pwd)/docker/ssh/router.key:/etc/wanctl/ssh/router.key:ro \
  -v $(pwd)/docker/state/wan1:/var/lib/wanctl \
  wanctl
```

### 4. View Logs

```bash
docker logs -f wanctl-wan1
```

## Docker Compose

For multi-WAN deployments, use docker-compose:

```bash
cd docker

# Start all WANs
docker-compose up -d

# Start specific WAN
docker-compose up -d wan1

# Start with steering daemon
docker-compose --profile steering up -d

# View logs
docker-compose logs -f wan1

# Stop all
docker-compose down
```

## Directory Structure

```
docker/
├── Dockerfile
├── docker-compose.yml
├── entrypoint.sh
├── configs/              # Your config files
│   ├── wan1.yaml
│   ├── wan2.yaml
│   └── steering.yaml
├── ssh/                  # SSH keys
│   └── router.key
├── state/                # Persistent state (auto-created)
│   ├── wan1/
│   └── wan2/
└── logs/                 # Log files (optional)
    ├── wan1/
    └── wan2/
```

## Container Modes

The container supports multiple operating modes:

### Continuous Monitoring (Default)

```bash
docker run ... wanctl continuous
# or just:
docker run ... wanctl
```

Runs continuous RTT monitoring and CAKE adjustment. This is the primary operating mode.

### Calibration

```bash
docker run -it ... wanctl calibrate
```

Interactive calibration wizard to discover optimal bandwidth settings.

### Steering Daemon

```bash
docker run ... \
  -v ./steering.yaml:/etc/wanctl/steering.yaml:ro \
  wanctl steering
```

Runs the multi-WAN steering daemon for latency-sensitive traffic routing.

### One-Shot

```bash
docker run ... wanctl oneshot
```

Runs a single measurement cycle and exits. Useful for testing.

### Shell

```bash
docker run -it ... wanctl shell
```

Interactive shell for debugging.

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `WANCTL_CONFIG` | `/etc/wanctl/wan.yaml` | Main config path |
| `WANCTL_STEERING_CONFIG` | `/etc/wanctl/steering.yaml` | Steering config path |
| `PYTHONUNBUFFERED` | `1` | Unbuffered Python output |

### Volume Mounts

| Mount Point | Purpose | Required |
|-------------|---------|----------|
| `/etc/wanctl/wan.yaml` | Main configuration | Yes |
| `/etc/wanctl/ssh/router.key` | Router SSH key | Yes |
| `/var/lib/wanctl/` | State persistence | Recommended |
| `/var/log/wanctl/` | Log files | Optional |

### Network Mode

**Important:** Use `--network host` for accurate RTT measurements. Bridge networking adds latency that corrupts readings.

```bash
# Correct - host networking
docker run --network host ...

# Wrong - bridge networking adds latency
docker run -p 8080:8080 ...  # Don't do this
```

## Multi-WAN Setup

### docker-compose.yml

```yaml
services:
  wan1:
    build:
      context: ..
      dockerfile: docker/Dockerfile
    network_mode: host
    volumes:
      - ./configs/wan1.yaml:/etc/wanctl/wan.yaml:ro
      - ./ssh/router.key:/etc/wanctl/ssh/router.key:ro
      - ./state/wan1:/var/lib/wanctl

  wan2:
    build:
      context: ..
      dockerfile: docker/Dockerfile
    network_mode: host
    volumes:
      - ./configs/wan2.yaml:/etc/wanctl/wan.yaml:ro
      - ./ssh/router.key:/etc/wanctl/ssh/router.key:ro
      - ./state/wan2:/var/lib/wanctl

  steering:
    build:
      context: ..
      dockerfile: docker/Dockerfile
    network_mode: host
    volumes:
      - ./configs/steering.yaml:/etc/wanctl/steering.yaml:ro
      - ./ssh/router.key:/etc/wanctl/ssh/router.key:ro
      - ./state/wan1:/var/lib/wanctl:ro
    command: ["steering"]
    profiles:
      - steering
```

## State Persistence

State files contain EWMA values and measurement history. Mount `/var/lib/wanctl/` to preserve state across container restarts:

```bash
docker run ... -v ./state:/var/lib/wanctl wanctl
```

Without persistence:
- Container restart = cold start
- Takes 60-120 minutes to re-converge

With persistence:
- Container restart = warm start
- Continues from previous EWMA state

## Health Checks

The container includes a health check:

```bash
# Check container health
docker inspect --format='{{.State.Health.Status}}' wanctl-wan1

# View health check logs
docker inspect --format='{{json .State.Health}}' wanctl-wan1 | jq
```

## Updating

```bash
# Rebuild image
docker build -t wanctl -f docker/Dockerfile .

# Recreate containers
docker-compose up -d --force-recreate
```

## Troubleshooting

### Container Won't Start

```bash
# Check logs
docker logs wanctl-wan1

# Common issues:
# - Config file not mounted
# - YAML syntax error in config
# - SSH key permissions wrong (should be 600)
```

### SSH Connection Failed

```bash
# Test SSH from inside container
docker run -it --network host \
  -v ./ssh/router.key:/etc/wanctl/ssh/router.key:ro \
  wanctl shell

# Then inside container:
ssh -i /etc/wanctl/ssh/router.key admin@192.168.1.1 'echo ok'
```

### High Latency Readings

If RTT measurements are higher than expected:

1. Verify `--network host` is used
2. Check CPU usage (container competing for resources)
3. Compare with bare-metal ping to same target

### State Not Persisting

```bash
# Verify mount
docker inspect wanctl-wan1 | grep -A10 Mounts

# Check permissions inside container
docker exec wanctl-wan1 ls -la /var/lib/wanctl/
```

## Resource Usage

Typical resource consumption per container:

| Resource | Usage |
|----------|-------|
| Memory | ~50-60 MB |
| CPU | <1% (idle), <5% (measuring) |
| Disk | ~10 MB state, ~1 MB/day logs |
| Network | ~1 KB/s (ping only mode) |

## Comparison: Docker vs Bare Metal

| Aspect | Docker | Bare Metal/LXC |
|--------|--------|----------------|
| Setup complexity | Lower | Higher |
| Latency overhead | ~0.1-0.5ms | None |
| Memory overhead | ~10 MB | None |
| Isolation | Full | Shared kernel |
| Updates | Image rebuild | File copy |
| Systemd integration | External | Native |

## Security Notes

1. **SSH Key**: Mount as read-only (`:ro`)
2. **Network Mode**: Host mode required but grants full network access
3. **User**: Container runs as non-root `wanctl` user
4. **Config Files**: Mount as read-only where possible
