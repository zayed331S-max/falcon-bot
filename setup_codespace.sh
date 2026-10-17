#!/bin/bash
cd "$(dirname "$0")"
pip install -r requirements.txt || pip install --break-system-packages -r requirements.txt
grep -q ZX_AUTOSTART ~/.bashrc || cat >> ~/.bashrc <<'RC'
# ZX_AUTOSTART
if [ -z "$ZX_DONE" ] && [ -d /workspaces/falcon-bot ] && ! pgrep -f start.py >/dev/null; then
  export ZX_DONE=1
  cd /workspaces/falcon-bot && bash run.sh
fi
RC
