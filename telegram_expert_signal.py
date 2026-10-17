import os
import re
import asyncio
import time
from datetime import datetime, timezone, date, timedelta
from zoneinfo import ZoneInfo

from dotenv import load_dotenv
from telethon import TelegramClient, events
from ExpertOptionsToolsV2.expertoption import ExpertOptionAsync

load_dotenv()

API_ID = int(os.environ["TG_API_ID"])
API_HASH = os.environ["TG_API_HASH"]
SESSION_NAME = os.getenv("TG_SESSION", "talal_reader")
CHANNELS = [
    int(c.strip()) if re.fullmatch(r"-?\d+", c.strip()) else c.strip()
    for c in os.getenv("TG_CHANNELS", "").split(",") if c.strip()
]
EO_TOKEN = os.environ["EO_TOKEN"]

MODE = os.getenv("MODE", "DEMO").upper()
IS_DEMO = MODE != "REAL"
TRADE_AMOUNTS = [350, 850, 1750]
amount_index = 0
MAX_AMOUNT = float(os.getenv("MAX_AMOUNT", "5"))
DEFAULT_DURATION = int(os.getenv("DEFAULT_DURATION", "60"))
MAX_LATE_SECONDS = int(os.getenv("MAX_LATE_SECONDS", "15"))
MAX_TRADES_PER_DAY = int(os.getenv("MAX_TRADES_PER_DAY", "20"))
SIGNAL_TZ = ZoneInfo(os.getenv("SIGNAL_TZ", "Europe/Athens"))
ENTRY_OFFSET = float(os.getenv("ENTRY_OFFSET", "0"))
MAX_WAIT_SECONDS = int(os.getenv("MAX_WAIT_SECONDS", "150"))

if not IS_DEMO and os.getenv("CONFIRM_REAL") != "YES":
    raise SystemExit("Set CONFIRM_REAL=YES in .env for REAL mode")

ASSETS = {
    "XAUUSD": 176,
    "SMRTY": 240,
    "EURUSDOTC": 245,
    "EURUSD": 142,
}

CALL_WORDS = r"\b(call|buy|up|higher)\b|شراء|صعود|اعلى|أعلى|🟢|⬆️"
PUT_WORDS = r"\b(put|sell|down|lower)\b|بيع|هبوط|اسفل|أسفل|🔴|⬇️"
TIME_RE = re.compile(r"(\d{1,2}):(\d{2})(?::(\d{2}))?\s*(am|pm)?")
DUR_RE = re.compile(
    r"(\d+)\s*(seconds?|secs?|s|ثانية|ثواني|minutes?|mins?|m|دقيقة|دقائق|د)\b"
)


def norm(s):
    return re.sub(r"[^A-Z0-9]", "", s.upper())


def parse_signal(text, msg_time):
    t = text.lower()
    asset = next((a for a in ASSETS if a in norm(text)), None)
    if not asset:
        return None
    is_call = re.search(CALL_WORDS, t)
    is_put = re.search(PUT_WORDS, t)
    if bool(is_call) == bool(is_put):
        return None
    direction = "call" if is_call else "put"

    entry = None
    m = TIME_RE.search(t)
    if m:
        h, mi = int(m.group(1)), int(m.group(2))
        s = int(m.group(3) or 0)
        ap = m.group(4)
        if ap == "pm" and h < 12:
            h += 12
        if ap == "am" and h == 12:
            h = 0
        try:
            base = msg_time.astimezone(SIGNAL_TZ)
            entry = base.replace(hour=h, minute=mi, second=s, microsecond=0)
        except ValueError:
            return None
        if entry < base - timedelta(hours=12):
            entry += timedelta(days=1)
        t = t[:m.start()] + " " + t[m.end():]

    duration = DEFAULT_DURATION
    d = DUR_RE.search(t)
    if d:
        val, unit = int(d.group(1)), d.group(2)
        is_sec = unit.startswith("s") or unit in ("ثانية", "ثواني")
        duration = val if is_sec else val * 60
    return asset, direction, duration, entry


eo = ExpertOptionAsync(EO_TOKEN, demo=IS_DEMO)


STEPS = {}


def step_of(asset_id):
    if asset_id not in STEPS:
        raise ValueError(f"unknown step for asset {asset_id}")
    return STEPS[asset_id]


async def place_trade(asset_id, direction, amount, duration):
    if direction == "call":
        return await eo.buy(asset_id=asset_id, amount=amount, expiration_time=duration * step_of(asset_id))
    return await eo.sell(asset_id=asset_id, amount=amount, expiration_time=duration * step_of(asset_id))


state = {"day": date.today(), "trades": 0, "seen": set()}


def can_trade():
    if state["day"] != date.today():
        state.update(day=date.today(), trades=0, seen=set())
    return state["trades"] < MAX_TRADES_PER_DAY


import csv

MAX_DAILY_LOSS = float(os.getenv("MAX_DAILY_LOSS", "0"))
SETTLE_SECONDS = int(os.getenv("SETTLE_SECONDS", "4"))
LOG_FILE = "trades_log.csv"

stats = {"day": date.today(), "wins": 0, "losses": 0, "ties": 0, "profit": 0.0}


def roll_day():
    if stats["day"] != date.today():
        stats.update(day=date.today(), wins=0, losses=0, ties=0, profit=0.0)


def summary():
    return (f"Today: W {stats['wins']} | L {stats['losses']} | "
            f"T {stats['ties']} | Net {stats['profit']:+.2f}")


def log_trade(asset, direction, amount, duration, pnl):
    new = not os.path.exists(LOG_FILE)
    with open(LOG_FILE, "a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["time", "asset", "direction", "amount", "duration", "pnl"])
        w.writerow([datetime.now().isoformat(timespec="seconds"),
                    asset, direction, amount, duration, pnl])


client = TelegramClient(SESSION_NAME, API_ID, API_HASH)


STAKES = [float(x) for x in os.getenv("STAKES", "4,8,16").split(",")]
COMP_STAKES = [float(x) for x in os.getenv("COMP_STAKES", os.getenv("STAKES", "4,8,16")).split(",")]
STATE = {"lost": False, "was_comp": False, "cur": STAKES}

def stake_for(k):
    if k == 0:
        STATE["was_comp"] = STATE["lost"]
        STATE["cur"] = COMP_STAKES if STATE["lost"] else STAKES
        STATE["lost"] = False
        if STATE["was_comp"]:
            print("COMPENSATION cycle", STATE["cur"])
    cur = STATE["cur"]
    return min(cur[min(k, len(cur) - 1)], MAX_AMOUNT)

trade_lock = asyncio.Lock()


STRAT_LOG = "strategy_log.csv"


def _ema(v, n):
    k = 2 / (n + 1)
    e = v[0]
    out = [e]
    for x in v[1:]:
        e = x * k + e * (1 - k)
        out.append(e)
    return out


def _rsi(v, n=14):
    if len(v) <= n:
        return None
    g = [max(v[i] - v[i - 1], 0) for i in range(1, len(v))]
    l = [max(v[i - 1] - v[i], 0) for i in range(1, len(v))]
    ag = sum(g[:n]) / n
    al = sum(l[:n]) / n
    for i in range(n, len(g)):
        ag = (ag * (n - 1) + g[i]) / n
        al = (al * (n - 1) + l[i]) / n
    if al == 0:
        return 100.0
    return round(100 - 100 / (1 + ag / al), 2)


async def strategy_verdict(asset_id, direction):
    try:
        rows = await asyncio.wait_for(
            eo.get_candles(asset_id, period=60, offset=0,
                           count_request=1, as_dataframe=False), 8)
        closes = [float(r["close"]) for r in rows]
        if len(closes) < 30:
            return {}
        e9 = _ema(closes, 9)[-1]
        e21 = _ema(closes, 21)[-1]
        trend = "UP" if e9 > e21 else "DOWN"
        last = rows[-1]
        candle = "UP" if float(last["close"]) >= float(last["open"]) else "DOWN"
        want = "UP" if direction == "call" else "DOWN"
        return {"ema9": round(e9, 6), "ema21": round(e21, 6),
                "rsi": _rsi(closes), "candle": candle, "trend": trend,
                "agree": int(trend == want)}
    except Exception as e:
        print(f"strategy skipped: {e}")
        return {}


def log_strategy(asset, direction, amount, pnl, v):
    new = not os.path.exists(STRAT_LOG)
    with open(STRAT_LOG, "a", newline="") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["time", "asset", "direction", "amount", "pnl", "win",
                        "ema9", "ema21", "rsi", "candle", "trend", "agree"])
        w.writerow([datetime.now().isoformat(timespec="seconds"), asset, direction,
                    amount, pnl, int(pnl > 0), v.get("ema9", ""), v.get("ema21", ""),
                    v.get("rsi", ""), v.get("candle", ""), v.get("trend", ""),
                    v.get("agree", "")])


mart = {"level": 0}


ATTEMPTS = int(os.getenv("ATTEMPTS", "3"))
SETTLE_MAX = float(os.getenv("SETTLE_MAX", "3"))


async def notify_me(msg):
    print(msg)
    try:
        await client.send_message("me", msg)
    except Exception:
        pass


async def execute(asset, direction, duration, entry):
    try:
        if entry is not None:
            delay = (entry - datetime.now(timezone.utc)).total_seconds() + ENTRY_OFFSET
            if delay > MAX_WAIT_SECONDS:
                print(f"entry too far ({delay:.0f}s) - check SIGNAL_TZ")
                return
            if delay < -MAX_LATE_SECONDS:
                print(f"entry passed {-delay:.0f}s ago - skipped")
                return
            if delay > 0:
                print(f"waiting {delay:.0f}s -> {asset} {direction.upper()}")
                await asyncio.sleep(delay)
        async with trade_lock:
            if entry is not None:
                late = (datetime.now(timezone.utc) - entry).total_seconds()
                if late > MAX_LATE_SECONDS:
                    print(f"skipped: previous cycle still running ({late:.0f}s late)")
                    return
            net = 0.0
            done = 0
            outcome = None
            for k in range(ATTEMPTS):
                roll_day()
                if MAX_DAILY_LOSS > 0 and stats["profit"] <= -MAX_DAILY_LOSS:
                    print("DAILY LOSS LIMIT reached - cycle stopped")
                    break
                if not can_trade():
                    print("daily trades limit reached - cycle stopped")
                    break
                amount = stake_for(k)
                bal_before = await eo.balance()
                if bal_before < amount:
                    print(f"balance {bal_before} < stake {amount} - cycle stopped")
                    break
                result = await place_trade(ASSETS[asset], direction, amount, duration)
                state["trades"] += 1
                done += 1
                print(f"OPENED #{k + 1} [{MODE}] {asset} {direction.upper()} {amount} / {duration}s -> {result}")
                await asyncio.sleep(duration)
                t0 = time.monotonic()
                bal_now = await eo.balance()
                while bal_now <= bal_before - amount + 0.01 and time.monotonic() - t0 < SETTLE_MAX:
                    await asyncio.sleep(0.4)
                    bal_now = await eo.balance()
                pnl = round(bal_now - bal_before, 2)
                if pnl >= 0:
                    print(f"settled in {time.monotonic() - t0:.1f}s")
                if abs(pnl) > amount + 0.01:
                    await notify_me(f"BALANCE ANOMALY {pnl} (stake {amount}) - cycle stopped, check the app")
                    return
                roll_day()
                stats["profit"] = round(stats["profit"] + pnl, 2)
                net = round(net + pnl, 2)
                log_trade(asset, direction, amount, duration, pnl)
                if pnl > 0:
                    outcome = "WIN" if k == 0 else f"WIN {k}"
                    stats["wins"] += 1
                    break
                if abs(pnl) < 0.01:
                    outcome = "DRAW"
                    stats["ties"] += 1
                    break
                print(f"attempt #{k + 1} lost {pnl:+.2f}")
            if outcome is None and done > 0:
                outcome = "LOSS" if done == ATTEMPTS else "LOSS (stopped early)"
                STATE["lost"] = (done == ATTEMPTS) and not STATE["was_comp"]
                stats["losses"] += 1
            if outcome:
                await notify_me(f"{outcome} {asset} {direction.upper()} | cycle net {net:+.2f}\n{summary()}")
    except Exception as e:
        print(f"FAILED: {e}")


@client.on(events.NewMessage(chats=CHANNELS or None))
async def handler(event):
    text = event.raw_text or ""
    if not text:
        return
    sig = parse_signal(text, event.message.date)
    if not sig:
        return
    asset, direction, duration, entry = sig
    key = (event.chat_id, event.id)
    if key in state["seen"]:
        return
    state["seen"].add(key)
    print(f"signal chat={event.chat_id}: {asset} {direction} {duration}s entry={entry}")
    if entry is None:
        age = (datetime.now(timezone.utc) - event.message.date).total_seconds()
        if age > MAX_LATE_SECONDS:
            print(f"late {age:.0f}s, skipped")
            return
    asyncio.create_task(execute(asset, direction, duration, entry))


async def main():
    await client.start()
    print("Telegram CONNECTED")
    import zxlicense
    me = await client.get_me()
    if not zxlicense.valid(me.id, os.getenv("LICENSE", "")):
        print(f"\nLICENSE REQUIRED | رقم تيليجرام حقك: {me.id}")
        print("ارسل هذا الرقم للبائع عشان يعطيك كود، ثم اكتب: bash license.sh الكود")
        return
    await eo.connect()
    for a in await eo.fetch_assets():
        STEPS[a["id"]] = a.get("expiration_step", 5)
    print(f"ExpertOption CONNECTED | MODE: {MODE}")
    try:
        print(f"Balance: {await eo.balance()}")
    except Exception:
        pass
    print(summary())
    print("Watching Telegram signals...")
    await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())
