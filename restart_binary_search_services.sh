#!/bin/bash
# Restart binary search services on both containers
# Run this after deploying config changes

echo "Restarting binary search services..."
echo ""

echo "Spectrum container:"
ssh kevin@10.10.110.246 'sudo systemctl restart cake-spectrum.service && systemctl status cake-spectrum.service | head -8'

echo ""
echo "ATT container:"
ssh kevin@10.10.110.247 'sudo systemctl restart cake-att.service && systemctl status cake-att.service | head -8'

echo ""
echo "Done! Services restarted."
