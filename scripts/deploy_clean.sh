#!/bin/bash
# Legacy helper retained only as a redirect stub.
set -e

echo "This script is obsolete for the current wanctl layout." >&2
echo "It still targets the removed src/cake tree and timer-based units." >&2
echo "" >&2
echo "Use instead:" >&2
echo "  ./scripts/deploy.sh <wan_name> <target_host> [--with-steering]" >&2
echo "  ./scripts/install-systemd.sh <wan_name> [wan_name...] [--steering]" >&2
exit 1
