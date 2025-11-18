import os
import threading
from flask import Flask
from bots import main_bot, access_bot, results_bot

app = Flask(__name__)

# Start Access Bot in separate thread
threading.Thread(target=access_bot.run_bot, daemon=True).start()
# Start Results Bot in separate thread
threading.Thread(target=results_bot.run_bot, daemon=True).start()
# Start Main Bot webhook
main_bot_app = main_bot.start_main_bot()


@app.route("/")
def home():
    return "StakeAware backend running ✅", 200


if __name__ == "__main__":
    PORT = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=PORT)
