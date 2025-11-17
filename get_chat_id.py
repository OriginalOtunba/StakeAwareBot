import os
import asyncio
from telegram import Bot
from dotenv import load_dotenv

load_dotenv(dotenv_path=r"C:\StakeAwareBot\.env")
bot_token = os.environ.get("ACCESS_BOT_TOKEN")
bot = Bot(token=bot_token)

async def get_chat_ids():
    updates = await bot.get_updates()
    for update in updates:
        if update.message:
            chat = update.message.chat
            if chat.type in ['group', 'supergroup']:
                print(f"Group Name: {chat.title}")
                print(f"Numeric Chat ID: {chat.id}")

asyncio.run(get_chat_ids())
