import os
import asyncio
import aiohttp
from dotenv import load_dotenv
from aiohttp import web

load_dotenv()
PORT = int(os.getenv("PORT", 10000))

# import bots (they expose `register(dispatcher, bot)` functions)
from bots import main_bot, access_bot, results_bot
from aiogram import Bot, Dispatcher

# create Bot+Dispatcher instances for each bot token
MAIN_TOKEN = os.getenv("MAIN_BOT_TOKEN")
ACCESS_TOKEN = os.getenv("ACCESS_BOT_TOKEN")
RESULTS_TOKEN = os.getenv("RESULTS_BOT_TOKEN")

bots = []

async def start_webserver():
    async def handle(request):
        return web.Response(text="🤖 StakeAware unified runner (aiohttp)")

    app = web.Application()
    app.add_routes([web.get('/', handle)])
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()
    print(f"Webserver running on port {PORT}")

    # self-ping (keep free services awake)
    async def self_ping():
        url = f"http://127.0.0.1:{PORT}/"
        while True:
            try:
                async with aiohttp.ClientSession() as session:
                    await session.get(url, timeout=5)
            except Exception:
                pass
            await asyncio.sleep(600)

    asyncio.create_task(self_ping())

async def start_bots():
    # MAIN BOT
    main_bot_bot = Bot(token=MAIN_TOKEN)
    main_dp = Dispatcher()
    main_bot.register_handlers(main_dp, main_bot_bot)
    bots.append(("main", main_dp, main_bot_bot))

    # ACCESS BOT
    access_bot_bot = Bot(token=ACCESS_TOKEN)
    access_dp = Dispatcher()
    access_bot.register_handlers(access_dp, access_bot_bot)
    bots.append(("access", access_dp, access_bot_bot))

    # RESULTS BOT
    results_bot_bot = Bot(token=RESULTS_TOKEN)
    results_dp = Dispatcher()
    results_bot.register_handlers(results_dp, results_bot_bot)
    bots.append(("results", results_dp, results_bot_bot))

    # Start polling for each dispatcher concurrently
    tasks = []
    for name, dp, bot in bots:
        print(f"Starting polling for: {name}")
        tasks.append(dp.start_polling(bot))
    await asyncio.gather(*tasks)

async def main():
    await start_webserver()
    await start_bots()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("Shutting down")
