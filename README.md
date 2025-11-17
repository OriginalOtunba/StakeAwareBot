# StakeAware - Python Backend Scaffold (No Manybot)

This scaffold provides a minimal, easy-to-run Python backend for the StakeAware Telegram ecosystem (no Manybot).
It uses Flask to receive Paystack webhooks and lightweight bot scripts using `python-telegram-bot` to interact with Telegram.

IMPORTANT: This scaffold uses a simple JSON file for storage (`data/users.json`). It's intended for testing and MVP use. 
For production, replace JSON storage with a proper database and secure the endpoints.

## What is included
- `app.py` - Flask app (Paystack webhook + simple admin endpoints)
- `bots/main_bot.py` - Main bot for user onboarding and showing Paystack links
- `bots/access_bot.py` - Access bot for verifying users (via /verify command)
- `bots/results_bot.py` - Results bot to send daily messages to verified users
- `data/users.json` - Storage for users (initially empty)
- `requirements.txt`
- `.env.example` - environment variables sample

## Quick start (local testing)
1. Install dependencies:
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```
2. Copy `.env.example` to `.env` and fill with your tokens and secrets.
3. Run the Flask webhook server (app.py):
   ```bash
   export FLASK_APP=app.py
   flask run --host=0.0.0.0 --port=5000
   ```
4. Run the bots in separate terminals:
   ```bash
   python bots/main_bot.py
   python bots/access_bot.py
   python bots/results_bot.py
   ```

Notes:
- The Paystack webhook endpoint is `/webhook/paystack` in `app.py`.
- The scaffold verifies Paystack webhooks using HMAC SHA512. Set `PAYSTACK_WEBHOOK_SECRET` in `.env`.
- The Access Bot accepts `/verify <paystack_ref>`; in this MVP the admin must match Paystack subscription refs manually.
- `data/users.json` will contain entries like:
  ```json
  {
    "user@example.com": {
      "email": "user@example.com",
      "chat_id": 123456789,
      "plan": "daily",
      "expires_at": 1700000000000,
      "active": true
    }
  }
  ```
