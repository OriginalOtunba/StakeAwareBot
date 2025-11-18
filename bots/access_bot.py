import os
import requests
import json
import threading
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes

load_dotenv()

ACCESS_BOT_TOKEN = os.environ.get("ACCESS_BOT_TOKEN")
BACKEND_BASE_URL = os.environ.get("BACKEND_BASE_URL")  # e.g., https://your-render-app.onrender.com
USERS_FILE = "data/users.json"

def load_users():
    try:
        with open(USERS_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_users(u):
    with open(USERS_FILE, "w") as f:
        json.dump(u, f, indent=2)

def datetime_from_ts(ts):
    try:
        return datetime.utcfromtimestamp(int(ts)).strftime("%Y-%m-%d %H:%M:%S")
    except:
        return str(ts)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    args = context.args  # deep-link param: paystack reference
    keyboard = [[InlineKeyboardButton("ℹ️ Check Status", callback_data="status")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if args:
        ref = args[0]
        try:
            url = f"{BACKEND_BASE_URL}/link_telegram"
            resp = requests.post(url, json={"reference": ref, "chat_id": chat_id}, timeout=10)
            if resp.status_code == 200:
                await update.message.reply_text("✅ Payment reference linked.", reply_markup=reply_markup)
                return
            else:
                await update.message.reply_text(f"❌ Could not link reference: {resp.text}", reply_markup=reply_markup)
                return
        except Exception as e:
            await update.message.reply_text(f"❌ Backend error: {e}", reply_markup=reply_markup)
            return

    await update.message.reply_text(
        "Welcome to StakeAware Access Bot. Use the button below to check /status.",
        reply_markup=reply_markup
    )

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    try:
        resp = requests.get(f"{BACKEND_BASE_URL}/admin/users", timeout=10)
        if resp.status_code != 200:
            await update.message.reply_text("Could not fetch status from backend.")
            return
        users = resp.json()
        for email, u in users.items():
            if u.get("chat_id") == chat_id:
                await update.message.reply_text(
                    f"✅ Plan: {u.get('plan')} | Expires (UTC): {datetime_from_ts(u.get('expires_at'))}"
                )
                return
        await update.message.reply_text("❌ No active subscription found.")
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")

def run_bot():
    if not ACCESS_BOT_TOKEN:
        print("ACCESS_BOT_TOKEN missing")
        return
    app = ApplicationBuilder().token(ACCESS_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("status", status))
    print("Access Bot running...")
    app.run_polling()
