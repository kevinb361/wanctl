#!/bin/bash
# Install logrotate configuration on both containers

echo "Installing logrotate configuration..."
echo ""

echo "Spectrum container (10.10.110.246):"
ssh kevin@10.10.110.246 'sudo tee /etc/logrotate.d/cake' < /home/kevin/CAKE/logrotate_cake.conf > /dev/null
echo "✓ Logrotate config installed"
ssh kevin@10.10.110.246 'sudo logrotate -d /etc/logrotate.d/cake | head -20'

echo ""
echo "ATT container (10.10.110.247):"
ssh kevin@10.10.110.247 'sudo tee /etc/logrotate.d/cake' < /home/kevin/CAKE/logrotate_cake.conf > /dev/null
echo "✓ Logrotate config installed"
ssh kevin@10.10.110.247 'sudo logrotate -d /etc/logrotate.d/cake | head -20'

echo ""
echo "Done! Log rotation configured on both containers."
echo "Logs will rotate daily, keep 7 days, and compress old logs."
