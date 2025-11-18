import os
import asyncio
from dotenv import load_dotenv
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

load_dotenv()

# ================= CONFIG =================
MAIN_BOT_TOKEN = os.environ.get("MAIN_BOT_TOKEN")
PAYSTACK_DAILY = os.environ.get("PAYSTACK_DAILY_LINK")
PAYSTACK_WEEKEND = os.environ.get("PAYSTACK_WEEKEND_LINK")
ACCESS_BOT_USERNAME = os.environ.get("ACCESS_BOT_USERNAME")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")  # e.g. https://stakeawarebot.onrender.com/main_bot

# ================= FLASK =================
app = Flask(__name__)
telegram_app = None  # Will hold the telegram Application instance

# ================= TELEGRAM HANDLERS =================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "Stake Aware provides daily 3-odds tickets based on deep analysis of sports trends and statistics.\n\n"
        "Subscribe for ₦50,000/month to receive daily predictions or ₦20,000/month for Weekend games only directly here in Telegram.\n\n"
        "💡 We study matches, form, and trends so you do not have to.\n\n"
        "Here is what you get as a Premium Subscriber 👇\n"
        "✅ Daily 3+ Odds Predictions carefully analyzed by our team.\n"
        "✅ Expert insights designed to maximize profits and minimize risks.\n"
        "✅ Consistent, data-backed selections that help you stay ahead of the betting market.\n"
        "✅ 24/7 access to exclusive tips — no guesswork, just strategy and precision!\n\n"
        "💰 In this group, we don’t chase luck — we create winning moments.\n"
        "Prepare to level up your betting game and start winning like a pro!\n\n"
        "Welcome once again — your journey to beating the bookies begins NOW! 🏆\n"
        "Choose your subscription plan below. After payment, click the link to automatically verify your Telegram account."
    )

    keyboard = [
        [InlineKeyboardButton("💎 Daily 3-Odds — ₦50,000", url=PAYSTACK_DAILY)],
        [InlineKeyboardButton("🎯 Weekend 3-Odds — ₦20,000", url=PAYSTACK_WEEKEND)],
        [InlineKeyboardButton("✅ Verify Access", url=f"https://t.me/{ACCESS_BOT_USERNAME}")]
    ]

    await update.message.reply_text(
        text=text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )

# ================= FLASK WEBHOOK =================
@app.route("/main_bot", methods=["POST"])
def webhook_handler():
    if telegram_app is None:
        return "Bot not ready", 503

    try:
        update = Update.de_json(request.get_json(force=True), telegram_app.bot)
        telegram_app.update_queue.put_nowait(update)
    except Exception as e:
        print("Webhook error:", e)
        return "error", 400

    return "ok", 200

# ================= START TELEGRAM APP =================
async def start_webhook():
    global telegram_app

    telegram_app = ApplicationBuilder().token(MAIN_BOT_TOKEN).build()
    telegram_app.add_handler(CommandHandler("start", start))

    print("Setting webhook:", WEBHOOK_URL)
    await telegram_app.bot.set_webhook(url=WEBHOOK_URL)

# ================= MAIN =================
if __name__ == "__main__":
    if not MAIN_BOT_TOKEN:
        print("❌ MAIN_BOT_TOKEN missing")
        exit()

    # Run webhook async then start Flask
    asyncio.run(start_webhook())
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
