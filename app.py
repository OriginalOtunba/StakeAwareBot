import os
import json
import hmac
import hashlib
from flask import Flask, request, jsonify
from dotenv import load_dotenv

from bots.results_bot import results_dispatcher, RESULTS_BOT_TOKEN
from bots.access_bot import access_dispatcher, ACCESS_BOT_TOKEN

load_dotenv()

app = Flask(__name__)

PAYSTACK_WEBHOOK_SECRET = os.getenv("PAYSTACK_WEBHOOK_SECRET", "")
BOT_TOKENS = {
    RESULTS_BOT_TOKEN: results_dispatcher,
    ACCESS_BOT_TOKEN: access_dispatcher
}

# ------------------------
# PAYSTACK WEBHOOK
# ------------------------
@app.route("/paystack/webhook", methods=["POST"])
def paystack_webhook():
    signature = request.headers.get("X-Paystack-Signature")
    body = request.get_data()

    expected = hmac.new(
        PAYSTACK_WEBHOOK_SECRET.encode(),
        body,
        hashlib.sha512
    ).hexdigest()

    if signature != expected:
        return jsonify({"status": "invalid signature"}), 401

    data = request.json
    # You can extend this logic anytime
    print("Paystack Event:", data)

    return jsonify({"status": "success"}), 200


# ------------------------
# TELEGRAM BOT WEBHOOKS
# ------------------------
@app.route("/results-bot-webhook", methods=["POST"])
async def results_webhook():
    update_data = request.get_json(force=True)
    await results_dispatcher.feed_webhook_update(update_data)
    return jsonify({"status": "ok"}), 200


@app.route("/access-bot-webhook", methods=["POST"])
async def access_webhook():
    update_data = request.get_json(force=True)
    await access_dispatcher.feed_webhook_update(update_data)
    return jsonify({"status": "ok"}), 200


# ------------------------
# HEALTH CHECK
# ------------------------
@app.route("/", methods=["GET"])
def home():
    return "StakeAware Bot Server Running", 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
