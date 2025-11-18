import os
from dotenv import load_dotenv
from flask import Flask, request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
from telegram.ext import CallbackQueryHandler

load_dotenv()

MAIN_BOT_TOKEN = os.environ.get('MAIN_BOT_TOKEN')
PAYSTACK_DAILY = os.environ.get('PAYSTACK_DAILY_LINK')
PAYSTACK_WEEKEND = os.environ.get('PAYSTACK_WEEKEND_LINK')
ACCESS_BOT_USERNAME = os.environ.get('ACCESS_BOT_USERNAME')
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")  # <-- Render URL e.g. https://stakeaware.onrender.com/main_bot

app = Flask(__name__)
telegram_app = None     # Will hold python-telegram-bot instance


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
        [InlineKeyboardButton('💎 Daily 3-Odds — ₦50,000', url=PAYSTACK_DAILY)],
        [InlineKeyboardButton('🎯 Weekend 3-Odds — ₦20,000', url=PAYSTACK_WEEKEND)],
        [InlineKeyboardButton('✅ Verify Access', url=f"https://t.me/{ACCESS_BOT_USERNAME}")]
    ]

    await update.message.reply_text(
        text=text, 
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )


# ---------------- WEBHOOK HANDLER ---------------- #
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


def start_main_bot():
    global telegram_app

    telegram_app = ApplicationBuilder().token(MAIN_BOT_TOKEN).build()
    telegram_app.add_handler(CommandHandler("start", start))

    print("Setting webhook:", WEBHOOK_URL + "/main_bot")
    telegram_app.bot.set_webhook(url=WEBHOOK_URL + "/main_bot")

    return telegram_app



    # Render uses webhook mode ─ local dev can still use polling if needed
    running = os.environ.get("RUN_MODE", "webhook")

    if running == "polling":
        app = ApplicationBuilder().token(MAIN_BOT_TOKEN).build()
        app.add_handler(CommandHandler("start", start))
        print("Running in polling mode...")
        app.run_polling()
    else:
        start_webhook()
        app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
