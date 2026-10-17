#!/bin/bash
# تغيير الوضع:  bash mode.sh demo   |   bash mode.sh real
cd "$(dirname "$0")"
[ -f .env ] || cp .env.example .env
case "$1" in
  demo)
    sed -i -E '/^(MODE|CONFIRM_REAL)=/d' .env
    echo "MODE=DEMO" >> .env
    echo "تم: الوضع التجريبي DEMO. أعد تشغيل البوت."
    ;;
  real)
    echo "تحذير: الوضع الحقيقي يتداول بفلوسك الفعلية وقد تخسرها كلها."
    read -p "اكتب YES للتأكيد: " a
    if [ "$a" != "YES" ]; then echo "تم الإلغاء."; exit 1; fi
    sed -i -E '/^(MODE|CONFIRM_REAL)=/d' .env
    printf 'MODE=REAL\nCONFIRM_REAL=YES\n' >> .env
    echo "تم: الوضع الحقيقي REAL. أعد تشغيل البوت."
    ;;
  *) echo "الاستخدام: bash mode.sh demo   أو   bash mode.sh real"; exit 1;;
esac
