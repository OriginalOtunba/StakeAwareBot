# bots/access_bot.py
import os
import json
import requests
from aiogram import types
from aiogram.utils.keyboard import InlineKeyboardBuilder

BACKEND_BASE = os.getenv("BACKEND_BASE_URL")
BACKEND_ADMIN_KEY = os.getenv("BACKEND_ADMIN_KEY", "")

USERS_FILE = "data/users.json"
os.makedirs("data", exist_ok=True)

def _load_users():
    try:
        with open(USERS_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}

def _save_users(u):
    with open(USERS_FILE, "w") as f:
        json.dump(u, f, indent=2)

def register_handlers(dp, bot):
    dp.message.register(start_cmd, commands=["start"])
    dp.message.register(status_cmd, commands=["status"])

async def start_cmd(message: types.Message):
    # Aiogram: message.get_args() returns the deep-link argument if present
    args = message.get_args()
    keyboard = InlineKeyboardBuilder().button(text="ℹ️ Check Status", callback_data="status").as_markup()
    if args:
        ref = args.strip()
        try:
            resp = requests.post(f"{BACKEND_BASE}/link_telegram", json={"reference": ref, "chat_id": message.chat.id}, timeout=8)
            if resp.status_code == 200:
                await message.answer("✅ Payment reference linked. You now have access if the payment is valid.", reply_markup=keyboard)
                return
            else:
                await message.answer(f"❌ Could not link reference: {resp.text}", reply_markup=keyboard)
                return
        except Exception as e:
            await message.answer(f"❌ Error connecting to backend: {e}", reply_markup=keyboard)
            return

    await message.answer(
        "Welcome to StakeAware Access Bot.\n\nIf you completed payment, open the verification link from the payment page (it should open this bot with a reference). "
        "You can also use /status to check your subscription.",
        reply_markup=keyboard
    )

async def status_cmd(message: types.Message):
    try:
        headers = {}
        if BACKEND_ADMIN_KEY:
            headers["x-admin-key"] = BACKEND_ADMIN_KEY
        resp = requests.get(f"{BACKEND_BASE}/admin/users", headers=headers, timeout=8)
        if resp.status_code != 200:
            await message.answer("Could not fetch status from backend.")
            return
        users = resp.json()
        for email, u in users.items():
            if int(u.get("chat_id", 0)) == message.chat.id:
                await message.answer(f"✅ Active plan: {u.get('plan')} | Expires at (UTC): {u.get('expires_at')}")
                return
        await message.answer("❌ No active subscription found for this account.")
    except Exception as e:
        await message.answer(f"Error fetching status: {e}")
