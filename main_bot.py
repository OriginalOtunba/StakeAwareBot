import os
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

load_dotenv(r"C:\StakeAwareBot\.env")

MAIN_BOT_TOKEN = os.environ.get('MAIN_BOT_TOKEN')
PAYSTACK_DAILY = os.environ.get('PAYSTACK_DAILY_LINK')
PAYSTACK_WEEKEND = os.environ.get('PAYSTACK_WEEKEND_LINK')
ACCESS_BOT_USERNAME = os.environ.get('ACCESS_BOT_USERNAME')

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
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(text=text, reply_markup=reply_markup)

def main():
    if not MAIN_BOT_TOKEN:
        print("❌ MAIN_BOT_TOKEN not set")
        return
    app = ApplicationBuilder().token(MAIN_BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    print("✅ Main Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()
