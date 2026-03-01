#!/usr/bin/env bash
set -euo pipefail

APP_NAME="deepa-telegram-bot"
APP_USER="deepa-bot"
APP_GROUP="deepa-bot"
APP_DIR="/opt/deepa"
ENV_DIR="/etc/deepa"
ENV_FILE="${ENV_DIR}/deepa.env"
SERVICE_FILE="/etc/systemd/system/${APP_NAME}.service"

echo "[1/7] Cài package hệ thống..."
sudo pacman -Syu --needed --noconfirm git rsync python python-pip

echo "[2/7] Tạo user service nếu chưa có..."
if ! id -u "${APP_USER}" >/dev/null 2>&1; then
  sudo useradd --system --create-home --home-dir /var/lib/deepa --shell /usr/bin/nologin "${APP_USER}"
fi

echo "[3/7] Chuẩn bị thư mục app..."
sudo mkdir -p "${APP_DIR}"
sudo chown -R "${USER}:${USER}" "${APP_DIR}"

echo "[4/7] Copy source code hiện tại lên ${APP_DIR}..."
rsync -a --delete \
  --exclude '.git' \
  --exclude '.venv' \
  --exclude '__pycache__' \
  ./ "${APP_DIR}/"

echo "[5/7] Tạo virtualenv + cài dependencies..."
python -m venv "${APP_DIR}/.venv"
"${APP_DIR}/.venv/bin/pip" install --upgrade pip
"${APP_DIR}/.venv/bin/pip" install -r "${APP_DIR}/requirements.txt"

echo "[6/7] Tạo file env mẫu nếu chưa có..."
sudo mkdir -p "${ENV_DIR}"
if [[ ! -f "${ENV_FILE}" ]]; then
  sudo tee "${ENV_FILE}" >/dev/null <<'EOF'
OPENAI_API_KEY=your_openai_api_key
TAVILY_API_KEY=your_tavily_api_key
DEEPAGENT_MODEL=openai:gpt-4.1-mini
TELEGRAM_BOT_TOKEN=your_telegram_bot_token
TELEGRAM_ALLOWED_USER_IDS=123456789
EOF
fi
sudo chown root:root "${ENV_FILE}"
sudo chmod 600 "${ENV_FILE}"

echo "[7/7] Cài systemd service..."
sudo tee "${SERVICE_FILE}" >/dev/null <<EOF
[Unit]
Description=DeepA Telegram Bot
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${APP_USER}
Group=${APP_GROUP}
WorkingDirectory=${APP_DIR}
EnvironmentFile=${ENV_FILE}
ExecStart=${APP_DIR}/.venv/bin/python ${APP_DIR}/telegram_bot.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now "${APP_NAME}.service"

echo "Hoàn tất. Kiểm tra service bằng:"
echo "  sudo systemctl status ${APP_NAME}.service"
echo "Xem log realtime:"
echo "  journalctl -u ${APP_NAME}.service -f"
echo ""
echo "Lưu ý: chỉnh key thật trong ${ENV_FILE} rồi restart service:"
echo "  sudo systemctl restart ${APP_NAME}.service"
