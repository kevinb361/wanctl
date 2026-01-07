# wanctl Docker Image
#
# Adaptive CAKE bandwidth controller for Mikrotik RouterOS
#
# Usage:
#   docker build -t wanctl .
#   docker run -v ./configs/wan1.yaml:/etc/wanctl/wan.yaml wanctl
#
FROM python:3.12-slim

LABEL maintainer="wanctl project"
LABEL description="Adaptive CAKE bandwidth controller for Mikrotik RouterOS"
LABEL version="1.0"

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    openssh-client \
    iputils-ping \
    netperf \
    && rm -rf /var/lib/apt/lists/* \
    && apt-get clean

# Create wanctl user (non-root)
RUN useradd -r -s /usr/sbin/nologin -d /var/lib/wanctl -m wanctl

# Create FHS-compliant directory structure
RUN mkdir -p /opt/wanctl \
    /opt/wanctl/backends \
    /opt/wanctl/steering \
    /etc/wanctl \
    /etc/wanctl/ssh \
    /var/lib/wanctl \
    /var/log/wanctl \
    /run/wanctl

# Set ownership
RUN chown -R root:wanctl /etc/wanctl \
    && chown -R wanctl:wanctl /var/lib/wanctl \
    && chown -R wanctl:wanctl /var/log/wanctl \
    && chown -R wanctl:wanctl /run/wanctl \
    && chmod 750 /etc/wanctl \
    && chmod 700 /etc/wanctl/ssh \
    && chmod 750 /var/lib/wanctl \
    && chmod 750 /var/log/wanctl

# Install Python dependencies
RUN pip install --no-cache-dir pexpect==4.9.0 PyYAML==6.0.1

# Copy application code
COPY src/wanctl/*.py /opt/wanctl/
COPY src/wanctl/backends/*.py /opt/wanctl/backends/
COPY src/wanctl/steering/*.py /opt/wanctl/steering/

# Set permissions on code
RUN chmod 755 /opt/wanctl \
    && chmod 644 /opt/wanctl/*.py \
    && chmod 755 /opt/wanctl/backends \
    && chmod 644 /opt/wanctl/backends/*.py \
    && chmod 755 /opt/wanctl/steering \
    && chmod 644 /opt/wanctl/steering/*.py

# Copy entrypoint script
COPY docker/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod 755 /usr/local/bin/entrypoint.sh

# Set working directory
WORKDIR /opt/wanctl

# Environment variables (can be overridden)
ENV WANCTL_CONFIG=/etc/wanctl/wan.yaml
ENV WANCTL_MODE=continuous
ENV PYTHONPATH=/opt/wanctl
ENV PYTHONUNBUFFERED=1

# Health check - verify config exists and Python works
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python3 -c "import yaml; yaml.safe_load(open('${WANCTL_CONFIG}'))" || exit 1

# Run as wanctl user
USER wanctl

ENTRYPOINT ["/usr/local/bin/entrypoint.sh"]
CMD ["continuous"]
