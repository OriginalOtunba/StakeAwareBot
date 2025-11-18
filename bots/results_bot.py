import os
import logging
from dotenv import load_dotenv
from datetime import datetime
from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup, ForceReply
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    MessageHandler, filters, ContextTypes, ConversationHandler
)
load_dotenv()
# === CONFIG ===
TOKEN = os.getenv("RESULTS_BOT_TOKEN") or "RESULTS_BOT_TOKEN"
ADMIN_IDS = os.environ.get("ADMIN_TELEGRAM_ID")  # add more IDs for multiple admins
DAILY_GROUP_ID = os.environ.get("DAILY_GROUP_ID")
WEEKEND_GROUP_ID = os.environ.get("WEEKEND_GROUP_ID")

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)

# === STATES ===
ADDING_GAME = range(1)

# Temporary in-memory storage
games = []

# === INLINE KEYBOARD ===
def main_menu_keyboard():
    buttons = [
        [InlineKeyboardButton("➕ Add Game", callback_data="add_game")],
        [InlineKeyboardButton("📋 List Games", callback_data="list_games")],
        [InlineKeyboardButton("📤 Post Games", callback_data="post_games")],
        [InlineKeyboardButton("🗑️ Clear Games", callback_data="clear_games")]
    ]
    return InlineKeyboardMarkup(buttons)

# === HELPERS ===
def is_admin(user_id):
    return user_id in ADMIN_IDS

def format_games_list():
    if not games:
        return "📭 No games added yet."
    msg = "🎯 *STAKEAWARE OFFICIAL PREDICTION FOR THE DAY*\n\n"
    total_odds = 1.0
    for i, g in enumerate(games):
        # parse odds if present at end
        try:
            odds = float(g.split()[-2])
            total_odds *= odds
        except:
            odds = None
        msg += f"{i+1}. *{g}*\n"
    if total_odds != 1.0:
        msg += f"\n💰 *Total Odds:* {total_odds:.2f}"
    else:
        msg += f"\n💰 *Total Odds:* —"
    msg += "\n\n🔥 Play Responsibly 🔥"
    return msg

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        await update.message.reply_text("Welcome! You will receive results in your groups.")
        return
    await update.message.reply_text(
        "Welcome to StakeAware Results Bot.\nUse the buttons below to manage results.",
        reply_markup=main_menu_keyboard()
    )

# === INLINE CALLBACKS ===
async def handle_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    if not is_admin(user_id):
        await query.answer("❌ You are not authorized.", show_alert=True)
        return

    if query.data == "add_game":
        await query.edit_message_text(
            "Send the game in this format:\nTeamA vs TeamB GG - 1.55 odds",
            reply_markup=main_menu_keyboard()
        )
        return ADDING_GAME
    elif query.data == "list_games":
        await query.edit_message_text(format_games_list(),
                                      parse_mode="Markdown",
                                      reply_markup=main_menu_keyboard())
    elif query.data == "post_games":
        await post_games(update, context)
        await query.edit_message_text("Menu:", reply_markup=main_menu_keyboard())
        
    elif query.data == "clear_games":  # NEW
        games.clear()
        await query.edit_message_text("🗑️ All added games have been cleared.",
                                      reply_markup=main_menu_keyboard())


# === ADD GAME HANDLER ===
async def add_game_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if not is_admin(user_id):
        return

    game_text = update.message.text.strip()
    if not game_text:
        await update.message.reply_text("❌ Invalid format. Try again.")
        return ADDING_GAME

    games.append(game_text)
    await update.message.reply_text(f"✅ Game added:\n*{game_text}*",
                                    parse_mode="Markdown",
                                    reply_markup=main_menu_keyboard())
    # Stay in ADDING_GAME state for multiple entries
    return ADDING_GAME

# === POST GAMES ===
async def post_games(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not games:
        await update.callback_query.message.reply_text("📭 No games to post.")
        return

    msg = format_games_list()
    day = datetime.now().weekday()
    targets = [DAILY_GROUP_ID]
    if day in [4,5,6]:  # Friday-Sunday
        targets.append(WEEKEND_GROUP_ID)

    for group_id in targets:
        try:
            await context.bot.send_message(chat_id=group_id, text=msg, parse_mode="Markdown")
        except Exception as e:
            logging.error(f"Failed to post to {group_id}: {e}")

    await update.callback_query.message.reply_text(f"✅ Results posted to {len(targets)} group(s).",
                                                   reply_markup=main_menu_keyboard())
    games.clear()

# === MAIN ===
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    # Command handlers
    app.add_handler(CommandHandler("start", start))

    # Inline buttons
    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(handle_menu)],
        states={
            ADDING_GAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_game_message)]
        },
        fallbacks=[],
        allow_reentry=True
    )

    app.add_handler(conv_handler)
   print("✅ Results Bot running...")
    app.run_polling()

if __name__ == "__main__":
    main()
