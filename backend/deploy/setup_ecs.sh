#!/usr/bin/env bash
# Bootstraps a fresh Alibaba Cloud ECS free-tier instance (Ubuntu 22.04) to
# run the MemoryBench backend. Run this ON the ECS instance, as a user with
# sudo, after cloning the repo. See ../../docs/deploy.md for the full walkthrough.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
SERVICE_USER="${SUDO_USER:-$(whoami)}"

echo "==> Installing system dependencies"
sudo apt-get update -y
sudo apt-get install -y python3.11 python3.11-venv python3-pip nginx

echo "==> Creating virtualenv and installing backend requirements"
cd "$REPO_DIR"
python3.11 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r backend/requirements.txt

echo "==> Writing .env (fill in real credentials before starting the service)"
if [ ! -f "$REPO_DIR/.env" ]; then
  cp "$REPO_DIR/.env.example" "$REPO_DIR/.env"
  echo "Wrote $REPO_DIR/.env from .env.example — edit it with real DashScope/OSS credentials."
fi

echo "==> Installing systemd service"
sudo cp "$REPO_DIR/backend/deploy/memorybench-backend.service" /etc/systemd/system/memorybench-backend.service
sudo sed -i "s#__REPO_DIR__#$REPO_DIR#g; s#__SERVICE_USER__#$SERVICE_USER#g" /etc/systemd/system/memorybench-backend.service
sudo systemctl daemon-reload
sudo systemctl enable memorybench-backend
sudo systemctl restart memorybench-backend

echo "==> Installing nginx reverse proxy (port 80 -> 127.0.0.1:8000)"
sudo cp "$REPO_DIR/backend/deploy/nginx_memorybench.conf" /etc/nginx/sites-available/memorybench
sudo ln -sf /etc/nginx/sites-available/memorybench /etc/nginx/sites-enabled/memorybench
sudo nginx -t
sudo systemctl restart nginx

echo "==> Done. Check status with: sudo systemctl status memorybench-backend"
echo "==> Verify with: curl http://<ECS_PUBLIC_IP>/health"
