#!/usr/bin/env bash
# setup-cloudflared-oracle.sh
#
# Run ONCE on the Oracle VM, after oracle-start.sh has the stack up and
# frontend answering on 127.0.0.1:8080. Installs cloudflared and creates
# a brand-new, SEPARATE Cloudflare Tunnel dedicated to
# career.scaledbrain.com — deliberately not a second replica of the
# laptop's existing tunnel.
#
# Why a separate tunnel, not reusing the laptop's: the laptop's single
# tunnel (~/.cloudflared/config.yml there) currently routes BOTH
# scaledbrain.com (-> localhost:8082, the Platform Identity service)
# and career.scaledbrain.com (-> localhost:8080, this app) through one
# cloudflared process. Running a second cloudflared replica of that same
# tunnel ID on this VM would not let you route one hostname to one
# machine and the other hostname to the other — Cloudflare distributes
# each incoming request across whichever replica happens to be
# connected, and this VM can't serve localhost:8082 (Platform Identity
# isn't part of this migration). A second, independent tunnel with its
# own ingress rule for just career.scaledbrain.com avoids that entirely
# and leaves the laptop's existing tunnel/scaledbrain.com untouched.
#
# This script does everything EXCEPT the actual DNS cutover
# (`cloudflared tunnel route dns`) — that's a real, immediate
# production-traffic-affecting action and is left as an explicit final
# command printed at the end, to run only when you've verified the
# migrated stack and are ready to go live.
#
# One step in here is genuinely interactive and cannot be scripted:
# `cloudflared tunnel login` opens a URL you must visit in a browser (on
# any machine) and authorize against the scaledbrain.com Cloudflare
# account.
#
# Usage:
#   cd ~/career-compass-ai
#   ./infra/setup-cloudflared-oracle.sh

set -euo pipefail

TUNNEL_NAME="career-compass-oracle"
HOSTNAME="career.scaledbrain.com"
CONFIG_DIR="$HOME/.cloudflared"

step() {
    echo ""
    echo "==> $1"
}

step "Installing cloudflared (arm64) via Cloudflare's apt repo"
sudo mkdir -p --mode=0755 /usr/share/keyrings
curl -fsSL https://pkg.cloudflare.com/cloudflare-main.gpg | sudo tee /usr/share/keyrings/cloudflare-main.gpg >/dev/null
echo 'deb [signed-by=/usr/share/keyrings/cloudflare-main.gpg] https://pkg.cloudflare.com/cloudflared any main' | \
    sudo tee /etc/apt/sources.list.d/cloudflared.list >/dev/null
sudo apt-get update
sudo apt-get install -y cloudflared
cloudflared --version

step "Logging in to Cloudflare (interactive - open the printed URL in any browser and authorize scaledbrain.com)"
if [ ! -f "$CONFIG_DIR/cert.pem" ]; then
    cloudflared tunnel login
else
    echo "Already logged in (found $CONFIG_DIR/cert.pem) - skipping"
fi

step "Creating tunnel '$TUNNEL_NAME' (skips if it already exists)"
if ! cloudflared tunnel list --name "$TUNNEL_NAME" 2>/dev/null | grep -q "$TUNNEL_NAME"; then
    cloudflared tunnel create "$TUNNEL_NAME"
else
    echo "Tunnel '$TUNNEL_NAME' already exists - skipping creation"
fi
TUNNEL_ID="$(cloudflared tunnel list --name "$TUNNEL_NAME" -o json | python3 -c 'import json,sys; print(json.load(sys.stdin)[0]["id"])')"
echo "Tunnel ID: $TUNNEL_ID"

step "Writing $CONFIG_DIR/config.yml"
cat > "$CONFIG_DIR/config.yml" <<EOF
tunnel: $TUNNEL_ID
credentials-file: $CONFIG_DIR/$TUNNEL_ID.json

ingress:
  - hostname: $HOSTNAME
    service: http://localhost:8080
  - service: http_status:404
EOF
cat "$CONFIG_DIR/config.yml"

step "Installing cloudflared as a systemd service (survives reboot on its own - no scheduled-task/lid-close workaround needed here)"
sudo cloudflared --config "$CONFIG_DIR/config.yml" service install
sudo systemctl enable cloudflared
sudo systemctl restart cloudflared
sudo systemctl status cloudflared --no-pager

step "Done - tunnel is up but NOT yet receiving real traffic"
echo "Verify locally first: curl -I http://127.0.0.1:8080"
echo ""
echo "When you're ready to cut career.scaledbrain.com over to THIS VM"
echo "(after the data migration is complete and verified), run:"
echo ""
echo "    cloudflared tunnel route dns $TUNNEL_NAME $HOSTNAME"
echo ""
echo "This overwrites the existing DNS record (currently pointing at the"
echo "laptop's tunnel) to point at this VM's tunnel instead - real user"
echo "traffic moves the moment this command succeeds and DNS propagates."
