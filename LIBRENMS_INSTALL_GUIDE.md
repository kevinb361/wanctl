# LibreNMS Installation on Proxmox LXC

## Overview

This guide sets up LibreNMS in an LXC container on your Proxmox host to monitor:
- Mikrotik RB5009 router (10.10.99.1)
- Network switches
- Your CAKE adaptive system
- General network health

**Time required:** ~1 hour
**Difficulty:** Medium

---

## Part 1: Create LXC Container on Proxmox

### Step 1: Download Ubuntu Template (If Not Already)

On Proxmox web UI:
```
Datacenter → Storage → local → CT Templates → Templates
Download: ubuntu-24.04-standard (or latest Ubuntu LTS)
```

Or via CLI on Proxmox host:
```bash
pveam update
pveam available | grep ubuntu
pveam download local ubuntu-24.04-standard_24.04-1_amd64.tar.zst
```

### Step 2: Create LXC Container

**Via Proxmox Web UI:**
1. Click "Create CT" (top right)
2. Fill in:
   - **Node:** Your Proxmox node
   - **CT ID:** 150 (or any available)
   - **Hostname:** librenms
   - **Password:** (set a strong password)
   - **Template:** ubuntu-24.04-standard
   - **Disk:** 20 GB
   - **CPU cores:** 2
   - **Memory:** 3072 MB (3GB)
   - **Swap:** 512 MB
   - **Network:**
     - Bridge: vmbr0 (or your bridge to VLAN 99/110)
     - IPv4: 10.10.99.60/24 (or 10.10.110.60/24 for Trusted VLAN)
     - Gateway: 10.10.99.1 (or 10.10.110.1)
   - **DNS:** 10.10.110.202 (your Pi-hole)
3. **Start container:** Check the box
4. Click "Finish"

**Via Proxmox CLI (Alternative):**
```bash
pct create 150 local:vztmpl/ubuntu-24.04-standard_24.04-1_amd64.tar.zst \
  --hostname librenms \
  --cores 2 \
  --memory 3072 \
  --swap 512 \
  --storage local-lvm \
  --rootfs local-lvm:20 \
  --net0 name=eth0,bridge=vmbr0,ip=10.10.99.60/24,gw=10.10.99.1 \
  --nameserver 10.10.110.202 \
  --password \
  --unprivileged 1 \
  --start 1
```

### Step 3: Enter Container

**Via Proxmox Web UI:**
```
Select container → Console
```

**Via Proxmox host CLI:**
```bash
pct enter 150
```

**Or SSH directly (after container starts):**
```bash
ssh root@10.10.99.60
```

---

## Part 2: Prepare Ubuntu Container

### Step 1: Update System

```bash
apt update && apt upgrade -y
```

### Step 2: Set Timezone (Important for LibreNMS)

```bash
timedatectl set-timezone America/Chicago  # Or your timezone
timedatectl status
```

### Step 3: Install Prerequisites

```bash
apt install -y \
  acl \
  curl \
  fping \
  git \
  graphviz \
  imagemagick \
  mariadb-server \
  mtr-tiny \
  nginx \
  php-cli \
  php-curl \
  php-fpm \
  php-gd \
  php-gmp \
  php-json \
  php-mbstring \
  php-mysql \
  php-snmp \
  php-xml \
  php-zip \
  python3-dotenv \
  python3-memcache \
  python3-mysqldb \
  python3-pip \
  python3-pymysql \
  python3-redis \
  python3-setuptools \
  python3-systemd \
  rrdtool \
  snmp \
  snmpd \
  unzip \
  whois
```

---

## Part 3: Install LibreNMS

### Step 1: Create LibreNMS User

```bash
useradd librenms -d /opt/librenms -M -r -s "$(which bash)"
```

### Step 2: Download LibreNMS

```bash
cd /opt
git clone https://github.com/librenms/librenms.git
cd librenms
```

### Step 3: Set Permissions

```bash
chown -R librenms:librenms /opt/librenms
chmod 771 /opt/librenms
setfacl -d -m g::rwx /opt/librenms/rrd /opt/librenms/logs /opt/librenms/bootstrap/cache/ /opt/librenms/storage/
setfacl -R -m g::rwx /opt/librenms/rrd /opt/librenms/logs /opt/librenms/bootstrap/cache/ /opt/librenms/storage/
```

### Step 4: Install PHP Dependencies

```bash
su - librenms
cd /opt/librenms
./scripts/composer_wrapper.php install --no-dev
exit  # Back to root
```

---

## Part 4: Configure Database (MariaDB)

### Step 1: Secure MariaDB

```bash
mysql -u root <<EOF
CREATE DATABASE librenms CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'librenms'@'localhost' IDENTIFIED BY 'YourSecurePassword123!';
GRANT ALL PRIVILEGES ON librenms.* TO 'librenms'@'localhost';
FLUSH PRIVILEGES;
EOF
```

**Note:** Replace `YourSecurePassword123!` with a strong password. Save it!

### Step 2: Edit MariaDB Config

```bash
nano /etc/mysql/mariadb.conf.d/50-server.cnf
```

Add under `[mysqld]` section:
```ini
innodb_file_per_table=1
lower_case_table_names=0
```

Restart MariaDB:
```bash
systemctl restart mariadb
systemctl enable mariadb
```

---

## Part 5: Configure PHP-FPM

### Step 1: Find PHP Version

```bash
php -v
# Example output: PHP 8.3.x
```

### Step 2: Edit PHP-FPM Config

```bash
# Replace 8.3 with your version
nano /etc/php/8.3/fpm/php.ini
```

Find and change these lines:
```ini
date.timezone = America/Chicago
memory_limit = 256M
```

### Step 3: Configure PHP-FPM Pool

```bash
nano /etc/php/8.3/fpm/pool.d/librenms.conf
```

Add:
```ini
[librenms]
user = librenms
group = librenms
listen = /run/php-fpm-librenms.sock
listen.owner = www-data
listen.group = www-data
pm = dynamic
pm.max_children = 50
pm.start_servers = 5
pm.min_spare_servers = 5
pm.max_spare_servers = 35
pm.max_requests = 500
```

Restart PHP-FPM:
```bash
systemctl restart php8.3-fpm
systemctl enable php8.3-fpm
```

---

## Part 6: Configure Nginx

### Step 1: Create Nginx Config

```bash
nano /etc/nginx/sites-available/librenms
```

Paste:
```nginx
server {
    listen 80;
    server_name librenms.home.arpa;  # Or use IP: 10.10.99.60
    root /opt/librenms/html;
    index index.php;

    charset utf-8;
    gzip on;
    gzip_types text/css application/javascript text/javascript application/x-javascript image/svg+xml text/plain text/xsd text/xsl text/xml image/x-icon;

    location / {
        try_files $uri $uri/ /index.php?$query_string;
    }

    location ~ [^/]\.php(/|$) {
        fastcgi_pass unix:/run/php-fpm-librenms.sock;
        fastcgi_split_path_info ^(.+\.php)(/.+)$;
        include fastcgi.conf;
    }

    location ~ /\.(?!well-known).* {
        deny all;
    }
}
```

### Step 2: Enable Site

```bash
ln -s /etc/nginx/sites-available/librenms /etc/nginx/sites-enabled/
rm /etc/nginx/sites-enabled/default  # Remove default site
nginx -t  # Test config
systemctl restart nginx
systemctl enable nginx
```

---

## Part 7: Configure LibreNMS

### Step 1: Copy Config File

```bash
cp /opt/librenms/config.php.default /opt/librenms/config.php
nano /opt/librenms/config.php
```

Add near the top:
```php
<?php

## Database config
$config['db_host'] = 'localhost';
$config['db_user'] = 'librenms';
$config['db_pass'] = 'YourSecurePassword123!';  # Same as Step 4.1
$config['db_name'] = 'librenms';

## Customize site
$config['site_style'] = 'dark';  # Optional: dark theme
$config['page_refresh'] = 300;    # Refresh every 5 minutes
$config['base_url'] = 'http://10.10.99.60';  # Or your DNS name

## Disable auto-update (we'll use git)
$config['update'] = 0;
```

### Step 2: Build Database

```bash
su - librenms
cd /opt/librenms
php build-base.php
exit
```

---

## Part 8: Web Installer

### Step 1: Access Web Interface

Open browser:
```
http://10.10.99.60
```

### Step 2: Complete Web Setup

1. Pre-Install Checks: Should be all green ✓
2. Database Setup: Already done ✓
3. **Create Admin User:**
   - Username: admin
   - Password: (strong password)
   - Email: your@email.com
4. Finish setup

### Step 3: Fix Validation Errors

After setup, click "Validate Your Install"

Fix any warnings:
```bash
chown -R librenms:librenms /opt/librenms
```

---

## Part 9: Configure Cron & Services

### Step 1: Setup Cron (Poller)

```bash
cp /opt/librenms/dist/librenms.cron /etc/cron.d/librenms
```

### Step 2: Setup Systemd Services

```bash
cp /opt/librenms/dist/librenms-scheduler.service /opt/librenms/dist/librenms-scheduler.timer /etc/systemd/system/

systemctl enable librenms-scheduler.timer
systemctl start librenms-scheduler.timer
```

### Step 3: Enable Log Rotation

```bash
cp /opt/librenms/misc/librenms.logrotate /etc/logrotate.d/librenms
```

---

## Part 10: Add Your Mikrotik Router

### Step 1: Configure SNMP on Mikrotik (Already Done!)

You already have SNMP enabled:
```routeros
/snmp community
set [find name=public] name=YourSecureString
```

**Security note:** If still using "public", change it on router first!

### Step 2: Add Device in LibreNMS

Web UI:
```
Devices → Add Device
- Hostname: 10.10.99.1
- Community: YourSecureString (from router)
- Version: v2c
- Port: 161
- Transport: udp
- Click "Add Device"
```

LibreNMS will auto-discover:
- All interfaces
- CPU/memory
- Routing tables
- Firewall rules count
- Queue statistics (CAKE!)

### Step 3: Verify Device Added

```
Devices → 10.10.99.1
```

Should show:
- Device details
- Interface graphs
- CPU graph
- Memory graph

---

## Part 11: Configure Alerting

### Step 1: Enable Email Alerts

Web UI:
```
Settings → Alerting → Email
- Enable: Yes
- From: librenms@yourdomain.com
- SMTP Server: (your mail server)
```

### Step 2: Create Alert Rules

```
Alerts → Alert Rules → Create Rule
```

**Example: High CPU Alert**
```
Name: Router CPU High
Rule: %macros.device_up = "1" && %sensors.sensor_current >= 80
Severity: critical
```

**Example: WAN Failover Alert**
```
Name: ATT WAN Became Primary
Rule: %ports.ifOperStatus = "up" && %ports.ifDescr = "ether2-WAN-ATT"
```

### Step 3: Configure Alert Transports

```
Alerts → Alert Transports
Add: Email, Slack, Discord, webhook, etc.
```

---

## Part 12: Add More Devices

### Switches

1. Enable SNMP on each switch
2. Add via LibreNMS web UI
3. Devices → Add Device

### Your CAKE Containers (Optional)

Add monitoring for adaptive_cake.py:
```bash
# On cake-att container (10.10.110.247)
apt install snmpd
# Configure basic SNMP
```

---

## Part 13: Maintenance & Backups

### Daily Validation

```bash
su - librenms
cd /opt/librenms
./validate.php
```

### Update LibreNMS

```bash
su - librenms
cd /opt/librenms
git pull
./scripts/composer_wrapper.php install --no-dev
exit

# Fix permissions
chown -R librenms:librenms /opt/librenms
```

### Backup

**Database:**
```bash
mysqldump -u librenms -p librenms > /root/librenms-backup-$(date +%Y%m%d).sql
```

**RRD files (graphs):**
```bash
tar -czf /root/librenms-rrd-$(date +%Y%m%d).tar.gz /opt/librenms/rrd/
```

**Automated backup script:**
```bash
cat > /root/backup-librenms.sh <<'EOF'
#!/bin/bash
BACKUP_DIR="/root/librenms-backups"
DATE=$(date +%Y%m%d)

mkdir -p $BACKUP_DIR

# Backup database
mysqldump -u librenms -pYourSecurePassword123! librenms | gzip > $BACKUP_DIR/librenms-db-$DATE.sql.gz

# Backup RRD
tar -czf $BACKUP_DIR/librenms-rrd-$DATE.tar.gz /opt/librenms/rrd/

# Backup config
cp /opt/librenms/config.php $BACKUP_DIR/config-$DATE.php

# Keep last 7 days
find $BACKUP_DIR -type f -mtime +7 -delete

echo "Backup complete: $DATE"
EOF

chmod +x /root/backup-librenms.sh

# Add to cron
echo "0 3 * * * /root/backup-librenms.sh" | crontab -
```

---

## Part 14: Optional Enhancements

### Enable Oxidized (Config Backup)

Backs up router configs automatically:
```bash
apt install ruby ruby-dev libsqlite3-dev libssl-dev pkg-config cmake libssh2-1-dev
gem install oxidized oxidized-script oxidized-web
```

### Enable Billing

Track bandwidth usage per interface.

### Custom Dashboards

Create dashboards for:
- WAN overview (both links)
- Per-VLAN bandwidth
- CAKE queue statistics
- Security events

### API Integration

Integrate with your adaptive_cake.py:
```python
import requests

# Post CAKE metrics to LibreNMS
requests.post('http://10.10.99.60/api/v0/customoid/...')
```

---

## Troubleshooting

### Poller Not Running

```bash
systemctl status librenms-scheduler
journalctl -u librenms-scheduler -f
```

### Database Errors

```bash
mysql -u librenms -p
SHOW DATABASES;
USE librenms;
SHOW TABLES;
```

### Permissions Issues

```bash
chown -R librenms:librenms /opt/librenms
chmod -R 775 /opt/librenms/logs /opt/librenms/rrd
```

### Can't Add Device

- Check SNMP on router: `/snmp print`
- Test from LibreNMS: `snmpwalk -v2c -c YourSecureString 10.10.99.1`
- Check firewall allows UDP 161

### Graphs Not Updating

```bash
su - librenms
cd /opt/librenms
./poller.php -h 10.10.99.1 -d
```

---

## Performance Tips

### For 10-20 Devices

Your current specs (2 CPU / 3GB RAM) are perfect.

### For 50+ Devices

Upgrade to:
- 4 CPU cores
- 6 GB RAM
- Consider distributed pollers

### Database Optimization

```bash
mysql -u root -p
```

```sql
USE librenms;
OPTIMIZE TABLE device_perf;
OPTIMIZE TABLE syslog;
```

---

## Security Hardening

### Change Default Ports

Edit nginx config to use non-standard port:
```nginx
listen 8080;
```

### Enable HTTPS

```bash
apt install certbot python3-certbot-nginx
certbot --nginx -d librenms.yourdomain.com
```

### Restrict Access

In `/opt/librenms/config.php`:
```php
$config['http_allowed_hosts'] = ['10.10.99.60', '10.10.110.0/24'];
```

### Firewall Rules on Mikrotik

```routeros
/ip firewall filter
add chain=input action=accept protocol=udp dst-port=161 src-address=10.10.99.60 comment="Allow LibreNMS SNMP polling"
```

---

## What You Get

After setup:
- 📊 Real-time bandwidth graphs (per interface, per VLAN)
- 🚨 Alerts for: CPU, memory, interface down, WAN failover
- 📈 Historical trending (30 days+)
- 🗺️ Network map (topology discovery)
- 📋 Inventory management
- 🔔 Mobile-friendly interface
- 📧 Email/Slack/Discord notifications

---

## Next Steps

1. ✅ Install LibreNMS (follow this guide)
2. ✅ Add Mikrotik router
3. ✅ Configure basic alerts
4. Add switches
5. Create custom dashboards
6. Integrate with CAKE system
7. Set up automated backups

---

**Estimated time:** 1 hour for basic setup
**Difficulty:** Medium (mostly copy-paste)
**Result:** Professional network monitoring!

Good luck! Let me know if you hit any issues during installation.
