#!/bin/bash
set -e

echo "=========================================="
echo "CAKE Queue Reset - Unshaping"
echo "=========================================="
echo ""

ROUTER_HOST="10.10.99.1"
ROUTER_USER="admin"
SSH_KEY="/home/kevin/.ssh/id_ed25519"

echo "Unshaping all CAKE queues..."

# ATT queues
echo "  - WAN-Download-ATT"
ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no ${ROUTER_USER}@${ROUTER_HOST} \
    '/queue tree set [find name="WAN-Download-ATT"] max-limit=0'

echo "  - WAN-Upload-ATT"
ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no ${ROUTER_USER}@${ROUTER_HOST} \
    '/queue tree set [find name="WAN-Upload-ATT"] max-limit=0'

# Spectrum queues
echo "  - WAN-Download-Spectrum"
ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no ${ROUTER_USER}@${ROUTER_HOST} \
    '/queue tree set [find name="WAN-Download-Spectrum"] max-limit=0'

echo "  - WAN-Upload-Spectrum"
ssh -i "$SSH_KEY" -o StrictHostKeyChecking=no ${ROUTER_USER}@${ROUTER_HOST} \
    '/queue tree set [find name="WAN-Upload-Spectrum"] max-limit=0'

echo ""
echo "All queues unshaped (max-limit=0)"
echo ""
echo "The continuous controllers will start from ceiling values on next cycle:"
echo "  - ATT: 85M down / 16M up"
echo "  - Spectrum: 350M down / 35M up"
echo ""
echo "To watch the controllers re-establish limits:"
echo "  ssh kevin@10.10.110.247 'tail -f /home/kevin/fusion_cake/logs/cake_auto.log'"
echo "  ssh kevin@10.10.110.246 'tail -f /home/kevin/fusion_cake/logs/cake_auto.log'"
echo ""
