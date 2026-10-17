#!/bin/bash
cd "$(dirname "$0")"
if [ ! -f .env ]; then
  cp .env.example .env
  for k in $(grep -oE '^TG_[A-Z_]+=$' .env.example | tr -d '='); do
    read -p "$k: " v
    sed -i "s|^$k=.*|$k=$v|" .env
  done
fi
python -u start.py
