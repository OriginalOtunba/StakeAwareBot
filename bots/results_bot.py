import os
import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes, ConversationHandler

TOKEN = os.environ.get("RESULTS_BOT_TOKEN")
ADMIN_IDS = [int(os.environ.get("ADMIN_TELEGRAM_ID"))]  # list of admin IDs
DAILY_GROUP_ID = os.environ.get("DAILY_GROUP_ID")
WEEKEND_GROUP_ID = os.environ.get("WEEKEND_GROUP_ID")

logging.basicConfig(level=logging.INFO)

ADDING_GAME = range(1)
games = []

def is_admin(user_id):
    return user_id in ADMIN_IDS

def format_games_list():
    if not games:
        return "📭 No games added yet."
    msg = "🎯 *STAKEAWARE OFFICIAL PREDICTION FOR THE DAY*\n\n"
    total_odds = 1.0
    for i, g in enumerate(games):
        try:
            odds = float(g.split()[-2])
            total_odds *= odds
        except:
            pass
        msg += f"{i+1}. *{g}*\n"
    msg += f"\n💰 *Total Odds:* {total_odds:.2f}" if total_odds != 1.0 else "\n💰 *Total Odds:* —"
    msg += "\n\n🔥 Play Responsibly 🔥"
    return msg

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("Welcome! You will receive results in your groups.")
        return
    keyboard = [
        [InlineKeyboardButton("➕ Add Game", callback_data="add_game")],
        [InlineKeyboardButton("📋 List Games", callback_data="list_games")],
        [InlineKeyboardButton("📤 Post Games", callback_data="post_games")],
        [InlineKeyboardButton("🗑️ Clear Games", callback_data="clear_games")]
    ]
    await update.message.reply_text("StakeAware Results Bot Menu:", reply_markup=InlineKeyboardMarkup(keyboard))

async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if not is_admin(user_id):
        await query.answer("❌ Not authorized.", show_alert=True)
        return

    if query.data == "add_game":
        await query.edit_message_text("Send game like:\nTeamA vs TeamB GG - 1.55 odds")
        return ADDING_GAME
    elif query.data == "list_games":
        await query.edit_message_text(format_games_list())
    elif query.data == "post_games":
        await post_games(update, context)
    elif query.data == "clear_games":
        games.clear()
        await query.edit_message_text("🗑️ Cleared all games.")

async def add_game_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return
    games.append(update.message.text.strip())
    await update.message.reply_text(f"✅ Game added:\n*{update.message.text.strip()}*", parse_mode="Markdown")
    return ADDING_GAME

async def post_games(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not games:
        await update.callback_query.message.reply_text("📭 No games to post.")
        return
    msg = format_games_list()
    for group in [DAILY_GROUP_ID, WEEKEND_GROUP_ID]:
        try:
            await context.bot.send_message(chat_id=group, text=msg, parse_mode="Markdown")
        except Exception as e:
            logging.error(f"Failed to post to {group}: {e}")
    games.clear()
    await update.callback_query.message.reply_text("✅ Results posted.")

def run_bot():
    if not TOKEN:
        print("RESULTS_BOT_TOKEN missing")
        return
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(handle_menu)],
        states={ADDING_GAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_game_message)]},
        fallbacks=[]
    )
    app.add_handler(conv)
    print("Results Bot running...")
    app.run_polling()
