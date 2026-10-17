import os, sys, zxlicense
KEY = os.getenv("ZX_KEY", "/workspaces/zx_private.key")
if len(sys.argv) != 2 or not sys.argv[1].isdigit():
    raise SystemExit("الاستخدام: python make_license.py <رقم تيليجرام للعميل>")
sk = bytes.fromhex(open(KEY).read().strip())
print("LICENSE for", sys.argv[1], ":")
print(zxlicense.make(int(sys.argv[1]), sk))
