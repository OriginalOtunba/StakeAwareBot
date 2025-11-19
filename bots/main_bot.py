# bots/main_bot.py
import os
from aiogram import types
from aiogram.utils.keyboard import InlineKeyboardBuilder

PAYSTACK_DAILY = os.getenv("PAYSTACK_DAILY_LINK")
PAYSTACK_WEEKEND = os.getenv("PAYSTACK_WEEKEND_LINK")
ACCESS_BOT_USERNAME = os.getenv("ACCESS_BOT_USERNAME", "StakeAwareAccessBot")

def register_handlers(dp, bot):
    dp.message.register(start_cmd, commands=["start"])

async def start_cmd(message: types.Message):
    builder = InlineKeyboardBuilder()
    builder.button(text="💎 Daily 3-Odds — ₦50,000", url=PAYSTACK_DAILY)
    builder.button(text="🎯 Weekend 3-Odds — ₦20,000", url=PAYSTACK_WEEKEND)
    # We will use deep-link that user clicks after payment: /start <reference>
    builder.button(text="✅ Verify Access", url=f"https://t.me/{ACCESS_BOT_USERNAME}")
    keyboard = builder.as_markup()

    text = (
        "Stake Aware provides daily 3-odds tickets based on deep analysis of sports trends and statistics.\n\n"
        "Subscribe for ₦50,000/month to receive daily predictions or ₦20,000/month for Weekend games only directly here in Telegram.\n\n"
        "💡 We study matches, form, and trends so you don’t have to.\n\n"
        "Here’s what you get as a Premium Subscriber 👇\n"
        "✅ Daily 3+ Odds Predictions carefully analyzed by our team.\n"
        "✅ Expert insights designed to maximize profits and minimize risks.\n"
        "✅ Consistent, data-backed selections that help you stay ahead of the betting market.\n"
        "✅ 24/7 access to exclusive tips — no guesswork, just strategy and precision!\n\n"
        "💰 In this group, we don’t chase luck — we create winning moments.\n"
        "Prepare to level up your betting game and start winning like a pro!\n\n"
        "Welcome once again — your journey to beating the bookies begins NOW! 🏆\n\n"
        "Choose your subscription plan below. After payment, click the verification link provided (opens Access Bot)."
    )
    await message.answer(text, reply_markup=keyboard)
