import os
import requests
import json
from datetime import datetime
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, CallbackQueryHandler

load_dotenv()

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

# -------------------- BOT HANDLERS -------------------- #
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

# -------------------- WEBHOOK HANDLER -------------------- #

@app.route("/access_bot", methods=["POST"])
def webhook_handler():
    if telegram_app is None:
        return "Bot not initialized", 503

    try:
        update = Update.de_json(request.get_json(force=True), telegram_app.bot)
        telegram_app.update_queue.put_nowait(update)
    except Exception as e:
        print("Webhook error:", e)
        return "error", 400

    return "ok", 200


def start_webhook():
    global telegram_app

    telegram_app = ApplicationBuilder().token(ACCESS_BOT_TOKEN).build()
    telegram_app.add_handler(CommandHandler("start", start))
    telegram_app.add_handler(CallbackQueryHandler(button_handler))
    telegram_app.add_handler(CommandHandler("status", status))

    # Assign webhook
    full_url = f"{WEBHOOK_URL}/access_bot"
    print("Setting Access Bot webhook:", full_url)
    telegram_app.bot.set_webhook(url=full_url)

    return telegram_app


# -------------------- ENTRY POINT -------------------- #

if __name__ == "__main__":
    if not ACCESS_BOT_TOKEN:
        print("❌ ACCESS_BOT_TOKEN missing")
        exit()

    mode = os.environ.get("RUN_MODE", "webhook")

    if mode == "polling":
        # Local testing only
        test_app = ApplicationBuilder().token(ACCESS_BOT_TOKEN).build()
        test_app.add_handler(CommandHandler("start", start))
        test_app.add_handler(CallbackQueryHandler(button_handler))
        test_app.add_handler(CommandHandler("status", status))
        print("Running in polling mode...")
        test_app.run_polling()
    else:
        # Render deployment
        start_webhook()
        app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
