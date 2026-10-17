#!/bin/bash
cd "$(dirname "$0")"
PY=$(command -v python || command -v python3)
if ! $PY -c "import ExpertOptionsToolsV2, telethon, dotenv" 2>/dev/null; then
  echo ">> تثبيت المكتبات..."; $PY -m pip install -r requirements.txt || $PY -m pip install --break-system-packages -r requirements.txt
fi
if [ ! -f .env ]; then
  cp .env.example .env
  echo ">> الخطوة 1: بيانات تيليجرام من my.telegram.org"
  read -p "TG_API_ID: " v;   sed -i "s|^TG_API_ID=.*|TG_API_ID=$v|" .env
  read -p "TG_API_HASH: " v; sed -i "s|^TG_API_HASH=.*|TG_API_HASH=$v|" .env
fi
echo ">> الوضع: $(grep -E '^MODE=' .env | cut -d= -f2)"
$PY -u start.py
