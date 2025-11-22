# app.py
import os
import json
import hmac
import hashlib
import asyncio
import aiohttp
from aiohttp import web
from pathlib import Path
from datetime import datetime, timezone
from dotenv import load_dotenv
from typing import Dict, Any, Optional

load_dotenv()

# --------------------
# Config / env
# --------------------
PORT = int(os.getenv("PORT", 10000))
PAYSTACK_WEBHOOK_SECRET = os.getenv("PAYSTACK_WEBHOOK_SECRET", "")
PAYSTACK_SECRET_KEY = os.getenv("PAYSTACK_SECRET_KEY", "")
ACCESS_BOT_TOKEN = os.getenv("ACCESS_BOT_TOKEN")           # Access verification bot
RESULTS_BOT_TOKEN = os.getenv("RESULTS_BOT_TOKEN")         # Results posting bot
ADMIN_TELEGRAM_IDS = [int(x) for x in (os.getenv("ADMIN_TELEGRAM_IDS","").split(",") if os.getenv("ADMIN_TELEGRAM_IDS") else [])]
DAILY_GROUP_ID = int(os.getenv("DAILY_GROUP_ID", "0"))
WEEKEND_GROUP_ID = int(os.getenv("WEEKEND_GROUP_ID", "0"))
DAILY_GROUP_LINK = os.getenv("DAILY_GROUP_LINK", "")
WEEKEND_GROUP_LINK = os.getenv("WEEKEND_GROUP_LINK", "")
ACCESS_BOT_USERNAME = os.getenv("ACCESS_BOT_USERNAME", "StakeAwareAccessBot")
JWT_SECRET = os.getenv("BACKEND_ADMIN_KEY", os.getenv("JWT_SECRET", ""))
DAILY_PLAN_AMOUNT = int(os.getenv("DAILY_PLAN_AMOUNT", "50000"))
DAILY_PLAN_DURATION = int(os.getenv("DAILY_PLAN_DURATION", "30"))
WEEKEND_PLAN_DURATION = int(os.getenv("WEEKEND_PLAN_DURATION", "30"))
EXPIRY_ALERT_DAYS = int(os.getenv("EXPIRY_ALERT_DAYS", "3"))
SELF_PING_INTERVAL = int(os.getenv("SELF_PING_INTERVAL", "600"))  # seconds

# file storage
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
USERS_FILE = DATA_DIR / "users.json"
GAMES_FILE = DATA_DIR / "games.json"

# --------------------
# Helpers: file store
# --------------------
def load_json(p: Path) -> Dict[str, Any]:
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}

def save_json(p: Path, obj: Any):
    p.write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding="utf-8")

# users structure: { email: { email, plan, paystack_reference, expires_at, active, chat_id } }
def load_users():
    return load_json(USERS_FILE)

def save_users(u):
    save_json(USERS_FILE, u)

def load_games():
    return load_json(GAMES_FILE).get("games", [])

def save_games(games):
    save_json(GAMES_FILE, {"games": games})

# --------------------
# Aiogram setup (webhook style)
# --------------------
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

# create bots
access_bot = Bot(token=ACCESS_BOT_TOKEN)
results_bot = Bot(token=RESULTS_BOT_TOKEN)

# dispatchers
access_dp = Dispatcher()
results_dp = Dispatcher()

# --------------------
# Paystack verification & grant logic (keeps your original behavior)
# --------------------
def verify_paystack_signature(body_bytes: bytes, signature_header: Optional[str]) -> bool:
    if not PAYSTACK_WEBHOOK_SECRET:
        return True
    if not signature_header:
        return False
    computed = hmac.new(PAYSTACK_WEBHOOK_SECRET.encode(), body_bytes, hashlib.sha512).hexdigest()
    return hmac.compare_digest(computed, signature_header)

async def verify_transaction_with_paystack(reference: str) -> Optional[Dict[str,Any]]:
    if not PAYSTACK_SECRET_KEY:
        return None
    url = f"https://api.paystack.co/transaction/verify/{reference}"
    headers = {"Authorization": f"Bearer {PAYSTACK_SECRET_KEY}"}
    async with aiohttp.ClientSession() as s:
        async with s.get(url, headers=headers, timeout=10) as r:
            if r.status != 200:
                return None
            j = await r.json()
            if j.get("status") and j.get("data", {}).get("status") == "success":
                return j.get("data")
            return None

def grant_or_renew(email: str, plan: str, reference: str):
    users = load_users()
    now = int(datetime.now(tz=timezone.utc).timestamp())
    duration_days = DAILY_PLAN_DURATION if plan == "daily" else WEEKEND_PLAN_DURATION
    expires_at = now + duration_days * 24 * 3600

    prev = users.get(email)
    if prev and prev.get("expires_at", 0) > now:
        new_expiry = max(prev["expires_at"], expires_at)
        prev.update({
            "plan": plan,
            "paystack_reference": reference,
            "expires_at": new_expiry,
            "active": True
        })
        users[email] = prev
        action = "renewed"
    else:
        users[email] = {
            "email": email,
            "plan": plan,
            "paystack_reference": reference,
            "expires_at": expires_at,
            "active": True,
            "chat_id": None
        }
        action = "activated"

    save_users(users)
    # notify admin(s) via Telegram bot(s) if admin IDs present
    text = f"{email} {action} ({plan}). Paystack ref: {reference}\nDeep-link: https://t.me/{ACCESS_BOT_USERNAME}?start={reference}"
    asyncio.create_task(bulk_send_admin_message(text))
    return users[email]

async def bulk_send_admin_message(text: str):
    # try using results_bot for admin notifications (either bot will work)
    for aid in ADMIN_TELEGRAM_IDS:
        try:
            await results_bot.send_message(aid, text)
        except Exception:
            try:
                await access_bot.send_message(aid, text)
            except Exception:
                print("Admin notify failed for", aid)

# --------------------
# Web routes (aiohttp)
# --------------------
routes = web.RouteTableDef()

@routes.post("/paystack/webhook")
async def paystack_webhook(request: web.Request):
    body = await request.read()
    sig = request.headers.get("x-paystack-signature") or request.headers.get("X-Paystack-Signature")
    if not verify_paystack_signature(body, sig):
        return web.Response(text="Invalid signature", status=401)

    try:
        event = await request.json()
    except Exception:
        return web.json_response({"error": "invalid json"}, status=400)

    # only handle charge.success
    if event.get("event") != "charge.success":
        return web.json_response({"status": "ignored"}, status=200)

    data = event.get("data", {}) or {}
    ref = data.get("reference")
    email = (data.get("customer") or {}).get("email") or data.get("customer_email")
    amount = int(data.get("amount", 0)) // 100 if data.get("amount") is not None else 0

    if not ref or not email:
        return web.json_response({"error": "missing reference or email"}, status=400)

    # verify server-side with Paystack if key present
    verified = None
    if PAYSTACK_SECRET_KEY:
        verified = await verify_transaction_with_paystack(ref)
        if not verified:
            return web.json_response({"error": "verification failed"}, status=400)
        email = (verified.get("customer") or {}).get("email") or verified.get("customer_email") or email
        amount = int(verified.get("amount", amount * 100)) // 100

    # determine plan
    md = data.get("metadata") or {}
    plan = md.get("plan_type") if isinstance(md, dict) else None
    if not plan:
        plan = "daily" if amount >= DAILY_PLAN_AMOUNT else "weekend"

    user = grant_or_renew(email, plan, ref)
    # Return success
    return web.json_response({"status": "ok", "email": email}, status=200)

@routes.post("/link_telegram")
async def link_telegram(request: web.Request):
    try:
        body = await request.json()
    except:
        return web.json_response({"error":"invalid json"}, status=400)
    chat_id = body.get("chat_id") or body.get("telegram_id")
    reference = body.get("reference") or body.get("paystack_reference")
    if not chat_id or not reference:
        return web.json_response({"error":"chat_id and reference required"}, status=400)

    users = load_users()
    found = None
    for email, u in users.items():
        if u.get("paystack_reference") == reference:
            found = (email, u)
            break
    if not found:
        return web.json_response({"error":"user not found"}, status=404)

    email, u = found
    u["chat_id"] = int(chat_id)
    u["active"] = True
    users[email] = u
    save_users(users)

    # choose group link based on plan
    group_link = DAILY_GROUP_LINK if u.get("plan") == "daily" else WEEKEND_GROUP_LINK
    # send DM with inline button (no raw URL in text)
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Join Group", url=group_link)]])
    try:
        await access_bot.send_message(int(chat_id), f"Payment verified! You now have {u.get('plan')} access.", reply_markup=kb)
    except Exception as e:
        print("Failed DM user:", e)

    # announce to group(s) if configured (post a plain message)
    try:
        gid_daily = DAILY_GROUP_ID
        gid_weekend = WEEKEND_GROUP_ID
        if u.get("plan") == "daily" and gid_daily:
            try:
                await results_bot.send_message(gid_daily, f"{email} joined {u.get('plan')} subscribers.")
            except Exception:
                pass
        else:
            # weekend plan -> announce to weekend only if configured
            try:
                await results_bot.send_message(gid_weekend, f"{email} joined {u.get('plan')} subscribers.")
            except Exception:
                pass
    except Exception:
        pass

    return web.json_response({"status":"linked","email":email})

@routes.get("/admin/users")
async def admin_users(request: web.Request):
    key = request.headers.get("x-admin-key", "")
    if JWT_SECRET and key != JWT_SECRET:
        return web.Response(text="unauthorized", status=401)
    return web.json_response(load_users())

@routes.get("/")
async def home(request: web.Request):
    return web.Response(text="StakeAware unified runner (aiohttp)")

# --------------------
# Results bot handlers (full logic preserved)
# --------------------
# persistent games list
games = load_games()  # list of strings

def is_admin(uid: int) -> bool:
    return uid in ADMIN_TELEGRAM_IDS

def format_betting_slip(games_list):
    if not games_list:
        return "📭 No games added yet."
    lines = ["🎯 *STAKEAWARE OFFICIAL RESULTS*","\n"]
    total = 1.0
    for i, g in enumerate(games_list, start=1):
        # try extract odds: last token numeric
        toks = g.strip().split()
        odds = None
        for t in reversed(toks):
            try:
                odds = float(t.replace(",", "."))
                break
            except:
                continue
        if odds:
            total *= odds
            lines.append(f"{i}. *{g}* — `{odds:.2f}`")
        else:
            lines.append(f"{i}. *{g}*")
    total_text = f"{total:.2f}" if total and total != 1.0 else "—"
    lines.append("\n💰 *Total Odds:* " + total_text)
    lines.append("\n🔥 Play Responsibly 🔥")
    return "\n".join(lines)

# results bot command handlers
@results_dp.message(Command("start"))
async def results_start(message: types.Message):
    if is_admin(message.from_user.id):
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton("➕ Add Game", callback_data="add_game")],
            [InlineKeyboardButton("📋 List Games", callback_data="list_games")],
            [InlineKeyboardButton("📤 Post Games", callback_data="post_games")],
            [InlineKeyboardButton("🗑️ Clear Games", callback_data="clear_games")]
        ])
        await message.answer("Welcome to StakeAware Results Bot (admin). Use buttons below.", reply_markup=kb)
    else:
        await message.answer("You will receive official results in the groups.")

@results_dp.callback_query(lambda c: True)
async def results_menu_handler(callback: types.CallbackQuery):
    data = callback.data
    uid = callback.from_user.id
    if not is_admin(uid):
        await callback.answer("❌ Not authorized", show_alert=True)
        return

    if data == "add_game":
        await callback.message.edit_text("Send the game text as a reply to this chat message: e.g. `Real vs Opp GG - 1.55`")
        await callback.answer()
        return

    if data == "list_games":
        await callback.message.edit_text(format_betting_slip(games), parse_mode="Markdown")
        await callback.answer()
        return

    if data == "clear_games":
        games.clear()
        save_games(games)
        await callback.message.edit_text("🗑️ All added games cleared.")
        await callback.answer()
        return

    if data == "post_games":
        if not games:
            await callback.answer("No games to post.", show_alert=True)
            return
        text = format_betting_slip(games)
        day = datetime.now().weekday()  # Monday=0 ... Sunday=6
        targets = [DAILY_GROUP_ID]
        if day in [4,5,6]:  # Fri(4), Sat(5), Sun(6)
            targets.append(WEEKEND_GROUP_ID)
        posted = 0
        for gid in targets:
            try:
                await results_bot.send_message(gid, text, parse_mode="Markdown")
                posted += 1
            except Exception as e:
                print("Failed to post to", gid, e)
        games.clear()
        save_games(games)
        await callback.message.edit_text(f"✅ Results posted to {posted} group(s).")
        await callback.answer()
        return

@results_dp.message()
async def results_text_handler(message: types.Message):
    # Admin sends game text as normal message after 'add_game' prompt
    if not is_admin(message.from_user.id):
        return
    txt = message.text.strip()
    if not txt:
        return
    games.append(txt)
    save_games(games)
    await message.reply(f"✅ Game added:\n*{txt}*", parse_mode="Markdown")

# --------------------
# Access bot handlers (linking /status)
# --------------------
@access_dp.message(Command("start"))
async def access_start(message: types.Message):
    # deep-link args are in message.get_args()
    args = message.get_args()
    check_kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton("ℹ️ Check Status", callback_data="status")]])
    if args:
        ref = args.strip()
        # call backend /link_telegram
        async with aiohttp.ClientSession() as s:
            try:
                payload = {"reference": ref, "chat_id": message.chat.id}
                # backend is this same app; call internal route
                url = f"http://127.0.0.1:{PORT}/link_telegram"
                async with s.post(url, json=payload, timeout=10) as r:
                    text = await r.text()
                    if r.status == 200:
                        await message.answer("✅ Payment reference linked. You now have access if the payment is valid.", reply_markup=check_kb)
                        return
                    else:
                        await message.answer(f"❌ Could not link reference: {text}", reply_markup=check_kb)
                        return
            except Exception as e:
                await message.answer(f"❌ Error connecting to backend: {e}", reply_markup=check_kb)
                return

    await message.answer(
        "Welcome to StakeAware Access Bot.\n\nIf you completed payment, open the verification deep-link from the payment page (it should open this bot with a reference). Use the button below to check status.",
        reply_markup=check_kb
    )

@access_dp.callback_query(lambda c: c.data == "status")
async def access_status_cb(callback: types.CallbackQuery):
    chat_id = callback.message.chat.id
    # call /admin/users with admin key if present
    headers = {}
    if JWT_SECRET:
        headers["x-admin-key"] = JWT_SECRET
    async with aiohttp.ClientSession() as s:
        try:
            url = f"http://127.0.0.1:{PORT}/admin/users"
            async with s.get(url, headers=headers, timeout=10) as r:
                if r.status != 200:
                    await callback.message.answer("Could not fetch status from backend.")
                    await callback.answer()
                    return
                j = await r.json()
                for email, u in j.items():
                    if int(u.get("chat_id", 0)) == chat_id:
                        exp = u.get("expires_at")
                        exp_str = datetime.fromtimestamp(int(exp), tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC") if exp else "N/A"
                        await callback.message.answer(f"✅ Active plan: {u.get('plan')} | Expires at (UTC): {exp_str}")
                        await callback.answer()
                        return
                await callback.message.answer("❌ No active subscription found for this account.")
                await callback.answer()
                return
        except Exception as e:
            await callback.message.answer(f"Error fetching status: {e}")
            await callback.answer()
            return

# --------------------
# Background expiry checker + self-pinger
# --------------------
async def expiry_checker_task():
    while True:
        users = load_users()
        now = int(datetime.now(tz=timezone.utc).timestamp())
        changed = False
        for email, u in list(users.items()):
            exp = int(u.get("expires_at", 0))
            if u.get("active") and exp:
                if 0 < exp - now <= EXPIRY_ALERT_DAYS * 24 * 3600:
                    if u.get("chat_id"):
                        try:
                            await access_bot.send_message(int(u["chat_id"]),
                                f"Reminder: your {u.get('plan')} subscription expires on {datetime.fromtimestamp(exp, tz=timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}"
                            )
                        except Exception:
                            pass
                    else:
                        await bulk_send_admin_message(f"User {email} ({u.get('plan')}) expires soon but has no chat_id. Deep-link: https://t.me/{ACCESS_BOT_USERNAME}?start={u.get('paystack_reference')}")
                if exp <= now:
                    u["active"] = False
                    users[email] = u
                    changed = True
                    await bulk_send_admin_message(f"{email} subscription expired.")
        if changed:
            save_users(users)
        await asyncio.sleep(3600)

async def self_ping_task(app_url: str):
    # keep free Render service awake
    async with aiohttp.ClientSession() as s:
        while True:
            try:
                await s.get(app_url, timeout=5)
            except Exception:
                pass
            await asyncio.sleep(SELF_PING_INTERVAL)

# --------------------
# Startup / runner
# --------------------
async def on_startup(app: web.Application):
    # set webhooks for both bots to our endpoints (use RENDER external URL env var if provided)
    public_url = os.getenv("PUBLIC_URL") or os.getenv("BACKEND_BASE_URL") or os.getenv("BACKEND_URL")
    if public_url:
        try:
            await results_bot.set_webhook(f"{public_url.rstrip('/')}/results-bot-webhook")
            await access_bot.set_webhook(f"{public_url.rstrip('/')}/access-bot-webhook")
            print("Webhooks set to:", public_url)
        except Exception as e:
            print("Failed to set webhook automatically:", e)
    else:
        print("PUBLIC_URL not set; remember to set webhooks manually.")

    # start background tasks
    app.loop.create_task(expiry_checker_task())
    app.loop.create_task(self_ping_task(f"http://127.0.0.1:{PORT}/"))

async def feed_update_to_dispatcher(dispatcher: Dispatcher, update_data: dict):
    # aiogram Dispatcher has method feed_update in 3.x: use dispatcher.feed_update or process_update
    # We'll call dispatcher.feed_update
    try:
        await dispatcher.feed_update(update_data)
    except AttributeError:
        # fallback
        await dispatcher.process_update(types.Update(**update_data))

# aiohttp endpoints to receive telegram updates (webhooks)
@routes.post("/results-bot-webhook")
async def results_bot_webhook(req: web.Request):
    upd = await req.json()
    # feed into results dispatcher
    await feed_update_to_dispatcher(results_dp, upd)
    return web.Response(text="ok")

@routes.post("/access-bot-webhook")
async def access_bot_webhook(req: web.Request):
    upd = await req.json()
    await feed_update_to_dispatcher(access_dp, upd)
    return web.Response(text="ok")

# wire routes
app = web.Application()
app.add_routes(routes)
app.on_startup.append(on_startup)

# run
if __name__ == "__main__":
    print("Starting StakeAware unified runner on port", PORT)
    web.run_app(app, host="0.0.0.0", port=PORT)
