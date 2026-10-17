import os, re, runpy, getpass
raw = getpass.getpass("الصق EO_TOKEN (ما راح يظهر): ")
tok = raw.strip().strip('"').strip("'")
if tok.lower().startswith("token="):
    tok = tok[6:]
bad = [i for i, c in enumerate(tok) if not re.match(r"[0-9a-fA-F]", c)]
print("الطول:", len(tok), "| حروف غير سداسية في المواضع:", bad)
if bad and len(bad) <= 3:
    tok = re.sub(r"[^0-9a-fA-F]", "", tok)
    print("بعد التنظيف، الطول:", len(tok))
os.environ["EO_TOKEN"] = tok
runpy.run_path("telegram_expert_signal.py", run_name="__main__")
