#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CONFIG_DIR="${HOME}/.config/hyperagent"
ENV_FILE="${CONFIG_DIR}/engine.env"
SERVICE_DIR="${HOME}/.config/systemd/user"
SERVICE_FILE="${SERVICE_DIR}/hsmt-engine.service"

cd "$ROOT"
if [[ ! -x .venv/bin/python ]]; then
  bash install.sh
fi

source env.sh
python -m pip install --quiet -e '.[test]'
chmod +x "$ROOT/scripts/run_hsmt_engine.sh"

mkdir -p "$CONFIG_DIR" "$SERVICE_DIR" "$ROOT/var/hsmt-engine"
if [[ ! -f "$ENV_FILE" ]]; then
  TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(40))')"
  cat > "$ENV_FILE" <<EOF
HSMT_API_HOST=127.0.0.1
HSMT_API_PORT=8787
HSMT_MAX_UPLOAD_MB=100
HSMT_API_TOKEN=$TOKEN
EOF
  chmod 600 "$ENV_FILE"
fi

cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=HSMT Product Matcher Engine
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=$ROOT
EnvironmentFile=$ENV_FILE
ExecStart=$ROOT/scripts/run_hsmt_engine.sh
Restart=on-failure
RestartSec=5
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ReadWritePaths=$ROOT/var $CONFIG_DIR

[Install]
WantedBy=default.target
EOF

systemctl --user daemon-reload
systemctl --user enable hsmt-engine.service
systemctl --user restart hsmt-engine.service

echo "HSMT engine installed."
echo "Health: http://127.0.0.1:8787/health"
echo "Token:  $ENV_FILE"
echo "For boot without login, an administrator may run: loginctl enable-linger $USER"
