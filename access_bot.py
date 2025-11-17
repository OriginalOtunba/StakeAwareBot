import os
import requests
import json
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler

load_dotenv(r"C:\StakeAwareBot\.env")

ACCESS_BOT_TOKEN = os.environ.get("ACCESS_BOT_TOKEN")
# Ensure this matches your actual backend public URL without trailing slash
BACKEND_BASE_URL = os.environ.get("BACKEND_BASE_URL", "https://pursuingly-noncommemorational-nadia.ngrok-free.dev")
USERS_FILE = "data/users.json"

def load_users():
    try:
        with open(USERS_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}

def save_users(u):
    with open(USERS_FILE, "w") as f:
        json.dump(u, f, indent=2)

def datetime_from_ts(ts):
    try:
        return datetime.utcfromtimestamp(int(ts)).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return str(ts)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    args = context.args  # deep-link param: paystack reference
    keyboard = [[InlineKeyboardButton("ℹ️ Check Status", callback_data="status")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    if args:
        ref = args[0]
        try:
            # Ensure no trailing slash mismatch
            url = f"{BACKEND_BASE_URL}/link_telegram"
            resp = requests.post(url, json={"reference": ref, "chat_id": chat_id}, timeout=10)
            if resp.status_code == 200:
                await update.message.reply_text(
                    "✅ Payment reference linked. You now have access if the payment is valid.",
                    reply_markup=reply_markup
                )
                return
            else:
                await update.message.reply_text(
                    f"❌ Could not link reference: {resp.text}", reply_markup=reply_markup
                )
                return
        except Exception as e:
            await update.message.reply_text(
                f"❌ Error connecting to backend: {e}", reply_markup=reply_markup
            )
            return

    # No args: show instructions
    await update.message.reply_text(
        "Welcome to StakeAware Access Bot.\n\n"
        "If you completed payment, click your payment deep-link from the payment page "
        "(it should open this bot). Or use the verification link provided after payment. "
        "Use the button to check /status.",
        reply_markup=reply_markup
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data == "status":
        await status_handler_query(query)

async def status_handler_query(query):
    chat_id = query.message.chat_id
    try:
        url = f"{BACKEND_BASE_URL}/admin/users"
        resp = requests.get(url, timeout=10)
        if resp.status_code != 200:
            await query.message.reply_text("Could not fetch status from backend.")
            return
        users = resp.json()
        for email, u in users.items():
            if u.get("chat_id") == chat_id:
                await query.message.reply_text(
                    f"✅ Active plan: {u.get('plan')} | Expires at (UTC): {datetime_from_ts(u.get('expires_at'))}"
                )
                return
        await query.message.reply_text("❌ No active subscription found for this account.")
    except Exception as e:
        await query.message.reply_text(f"Error fetching status: {e}")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    try:
        url = f"{BACKEND_BASE_URL}/admin/users"
        resp = requests.get(url, timeout=10)
        if resp.status_code != 200:
            await update.message.reply_text("Could not fetch status from backend.")
            return
        users = resp.json()
        for email, u in users.items():
            if u.get("chat_id") == chat_id:
                await update.message.reply_text(
                    f"✅ Active plan: {u.get('plan')} | Expires at (UTC): {datetime_from_ts(u.get('expires_at'))}"
                )
                return
        await update.message.reply_text("❌ No active subscription found for this account.")
    except Exception as e:
        await update.message.reply_text(f"Error fetching status: {e}")

def main():
    if not ACCESS_BOT_TOKEN:
        print("ACCESS_BOT_TOKEN not set")
        return
    app = ApplicationBuilder().token(ACCESS_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(CommandHandler("status", status))
    print("Access bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()
