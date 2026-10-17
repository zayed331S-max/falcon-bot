#!/bin/bash
cd "$(dirname "$0")"
[ -n "$1" ] || { echo "الاستخدام: bash license.sh ZX-الكود"; exit 1; }
[ -f .env ] || cp .env.example .env
sed -i '/^LICENSE=/d' .env
echo "LICENSE=$1" >> .env
echo "تم حفظ الكود. شغّل: bash run.sh"
