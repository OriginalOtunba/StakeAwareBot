# bots/results_bot.py
import os
from datetime import datetime
from aiogram import types
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder

ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_TELEGRAM_IDS", "").split(",") if x.strip()]
DAILY_GROUP_ID = int(os.getenv("DAILY_GROUP_ID", "0"))
WEEKEND_GROUP_ID = int(os.getenv("WEEKEND_GROUP_ID", "0"))
DAILY_GROUP_LINK = os.getenv("DAILY_GROUP_LINK")
WEEKEND_GROUP_LINK = os.getenv("WEEKEND_GROUP_LINK")

# in-memory store (cleared after posting)
games = []

def _is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

def main_menu_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="➕ Add Game", callback_data="add_game")
    kb.button(text="📋 List Games", callback_data="list_games")
    kb.button(text="📤 Post Games", callback_data="post_games")
    kb.button(text="🗑️ Clear Games", callback_data="clear_games")
    return kb.as_markup()

def register_handlers(dp, bot):
    dp.message.register(start_cmd, Command(commands=["start"]))
    dp.callback_query.register(handle_menu)
    dp.message.register(add_game_message, lambda m: m.text and m.reply_to_message and m.reply_to_message.text and "Send the game" in m.reply_to_message.text)

async def start_cmd(message: types.Message):
    if not _is_admin(message.from_user.id):
        await message.reply("Welcome! You will receive results in your groups.")
        return
    await message.reply("StakeAware Results Bot Menu:", reply_markup=main_menu_kb())

async def handle_menu(callback: types.CallbackQuery):
    data = callback.data
    user_id = callback.from_user.id
    if not _is_admin(user_id):
        await callback.answer("❌ Not authorized", show_alert=True)
        return

    if data == "add_game":
        await callback.message.edit_text(
            "Send the game in this format:\nTeamA vs TeamB TYPE - 1.55 odds\n\nReply the message with your game text.",
            reply_markup=main_menu_kb()
        )
        await callback.answer()
        return

    if data == "list_games":
        text = format_games_list()
        await callback.message.edit_text(text, parse_mode="Markdown", reply_markup=main_menu_kb())
        await callback.answer()
        return

    if data == "clear_games":
        games.clear()
        await callback.message.edit_text("🗑️ All added games cleared.", reply_markup=main_menu_kb())
        await callback.answer()
        return

    if data == "post_games":
        if not games:
            await callback.answer("No games to post.", show_alert=True)
            return

        msg = format_games_list()
        day = datetime.utcnow().weekday()  # Monday=0 .. Sunday=6
        targets = [DAILY_GROUP_ID]
        if day in [4, 5, 6]:  # Fri-Sun
            targets.append(WEEKEND_GROUP_ID)

        sent = 0
        for gid in targets:
            try:
                await callback.bot.send_message(chat_id=gid, text=msg, parse_mode="Markdown")
                sent += 1
            except Exception as e:
                print("Failed posting to", gid, e)

        games.clear()
        await callback.message.edit_text(f"✅ Results posted to {sent} group(s).", reply_markup=main_menu_kb())
        await callback.answer()
        return

async def add_game_message(message: types.Message):
    if not _is_admin(message.from_user.id):
        return
    text = message.text.strip()
    games.append(text)
    await message.reply(f"✅ Game added:\n*{text}*", parse_mode="Markdown")

def format_games_list():
    if not games:
        return "📭 No games added yet."

    lines = ["🎯 *STAKEAWARE OFFICIAL PREDICTION FOR THE DAY*\n"]
    total = 1.0
    for i, g in enumerate(games, start=1):
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
        lines.append(f"{i}. *{g}*")

    total_text = f"{total:.2f}" if total != 1.0 else "—"
    lines.append(f"\n💰 *Total Odds:* {total_text}")
    lines.append("\n🔥 Play Responsibly 🔥")
    return "\n".join(lines)
