#!/usr/bin/env bash
# One-time setup on a fresh Ubuntu 24.04 server. Run as root from inside the uploaded scouting folder:
#   cd /opt/scouting && bash deploy/setup_server.sh
set -euo pipefail
APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"
apt-get update -y
apt-get install -y python3 python3-venv python3-pip sqlite3 tzdata
id -u scout >/dev/null 2>&1 || useradd --system --home "$APP_DIR" --shell /usr/sbin/nologin scout
python3 -m venv "$APP_DIR/.venv-linux"
"$APP_DIR/.venv-linux/bin/pip" install --upgrade pip
"$APP_DIR/.venv-linux/bin/pip" install -r "$APP_DIR/requirements.txt"
chown -R scout:scout "$APP_DIR"
chmod 600 "$APP_DIR/.env" "$APP_DIR"/credentials.json "$APP_DIR"/token.json 2>/dev/null || true
chmod 700 "$APP_DIR/accounts" 2>/dev/null || true
sed "s#__APP_DIR__#$APP_DIR#g" "$APP_DIR/deploy/scouting-autopilot.service" > /etc/systemd/system/scouting-autopilot.service
systemctl daemon-reload
echo
echo "Installed. Check it first without sending anything:"
echo "  sudo -u scout $APP_DIR/.venv-linux/bin/python $APP_DIR/autopilot_local.py --dry-run"
echo "  sudo -u scout $APP_DIR/.venv-linux/bin/python $APP_DIR/outreach.py check"
echo "When you are ready to go live:"
echo "  systemctl enable --now scouting-autopilot"
echo "Logs:  journalctl -u scouting-autopilot -f"
