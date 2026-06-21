#!/usr/bin/env bash
# Run this ONCE on a fresh Oracle Always-Free Ubuntu VM.
# Installs Docker, prepares output/ for the CV agent, prints next steps.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
HERE="$(cd "$(dirname "$0")" && pwd)"

echo "==> Installing Docker + Compose plugin..."
if ! command -v docker >/dev/null 2>&1; then
  curl -fsSL https://get.docker.com | sudo sh
  sudo usermod -aG docker "$USER"
  echo "    Installed. Run 'newgrp docker' (or log out/in) so docker works without sudo."
else
  echo "    Already present: $(docker --version)"
fi

echo "==> Preparing output/ dir (writable by container uid 1000)..."
mkdir -p "$ROOT/output"
sudo chown -R 1000:1000 "$ROOT/output" 2>/dev/null || true

echo "==> Deploy env file..."
if [ ! -f "$HERE/.env" ]; then
  cp "$HERE/.env.example" "$HERE/.env"
  echo "    Created $HERE/.env — edit DOMAIN and DUCKDNS_* values."
else
  echo "    $HERE/.env already exists."
fi

cat <<EOF

==> Remaining manual steps:
  1. Put secrets in $ROOT/.env
     (OPENAI_API_KEY, JWT_SECRET, ADMIN_PASSWORD_HASH, TELEGRAM_BOT_TOKEN, PRODUCTION=true)
     From your PC:  scp -i <key> .env ubuntu@<VM-IP>:$ROOT/.env

  2. Edit $HERE/.env  (DOMAIN, DUCKDNS_*)

  3. Build + launch:
       cd "$HERE"
       docker compose up -d --build
       # add  --profile duckdns  if you use the DuckDNS auto-updater

  4. Smoke test:
       curl https://\$DOMAIN/health        # expect {"status":"ok"}

  5. Register the Telegram webhook:
       curl "https://api.telegram.org/bot<TOKEN>/setWebhook?url=https://\$DOMAIN/webhook/telegram"
       curl "https://api.telegram.org/bot<TOKEN>/getWebhookInfo"
EOF
