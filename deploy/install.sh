#!/usr/bin/env bash
# Install Free AutoGTM on Ubuntu/Debian VPS. Run as root, from the
# extracted free-autogtm/ folder:  bash deploy/install.sh
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

echo "== Installing Python + nginx =="
apt-get update
apt-get install -y python3 nginx apache2-utils unzip

echo "== Copying app to /opt/free-autogtm =="
mkdir -p /opt/free-autogtm
cp -r cli.py config.example.json sample-leads.csv free_autogtm /opt/free-autogtm/
cd /opt/free-autogtm
python3 cli.py init || true

echo "== Dashboard login (nginx basic auth) =="
read -rp "Dashboard username: " AUTH_USER
if [ -z "$AUTH_USER" ]; then echo "Username is required."; exit 1; fi
htpasswd -c /etc/nginx/.free-autogtm-htpasswd "$AUTH_USER"

echo "== Installing systemd service =="
cp "$SCRIPT_DIR/free-autogtm.service" /etc/systemd/system/free-autogtm.service
systemctl daemon-reload
systemctl enable --now free-autogtm

echo "== Installing nginx site =="
cp "$SCRIPT_DIR/nginx-free-autogtm.conf" /etc/nginx/sites-available/free-autogtm
ln -sf /etc/nginx/sites-available/free-autogtm /etc/nginx/sites-enabled/free-autogtm
nginx -t
systemctl reload nginx

echo ""
echo "Done. Edit /etc/nginx/sites-available/free-autogtm and set server_name"
echo "to your subdomain (e.g. tool.iftekhar.ami.bd), then: nginx -t && systemctl reload nginx"
echo "Check status with: systemctl status free-autogtm"
