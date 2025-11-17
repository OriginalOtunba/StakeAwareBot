# app.py
import os
import hmac
import hashlib
import json
import time
import threading
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
from flask import Flask, request, jsonify

import requests

load_dotenv()

APP_PORT = int(os.environ.get("FLASK_PORT", 5000))
USERS_FILE = Path("data/users.json")
USERS_FILE.parent.mkdir(parents=True, exist_ok=True)

# Environment values
PAYSTACK_WEBHOOK_SECRET = os.environ.get("PAYSTACK_WEBHOOK_SECRET", "")
ACCESS_BOT_USERNAME = os.environ.get("ACCESS_BOT_USERNAME", "StakeAwareAccessBot")
ACCESS_BOT_TOKEN = os.environ.get("ACCESS_BOT_TOKEN", "")
ADMIN_TELEGRAM_ID = int(os.environ.get("ADMIN_TELEGRAM_ID", "0") or 0)
DAILY_PLAN_AMOUNT = int(os.environ.get("DAILY_PLAN_AMOUNT", "50000"))
WEEKEND_PLAN_AMOUNT = int(os.environ.get("WEEKEND_PLAN_AMOUNT", "20000"))
DAILY_PLAN_DURATION = int(os.environ.get("DAILY_PLAN_DURATION", "30"))
WEEKEND_PLAN_DURATION = int(os.environ.get("WEEKEND_PLAN_DURATION", "30"))
EXPIRY_ALERT_DAYS = int(os.environ.get("EXPIRY_ALERT_DAYS", "3"))
JWT_SECRET = os.environ.get("JWT_SECRET", "")
PAYSTACK_SECRET_KEY = os.environ.get("PAYSTACK_SECRET_KEY", "")

BOT_API_SEND = f"https://api.telegram.org/bot{ACCESS_BOT_TOKEN}/sendMessage" if ACCESS_BOT_TOKEN else None

app = Flask(__name__)

# ---- Helpers ----
def load_users():
    if not USERS_FILE.exists():
        return {}
    try:
        return json.loads(USERS_FILE.read_text())
    except Exception:
        return {}

def save_users(users):
    USERS_FILE.write_text(json.dumps(users, indent=2))

def verify_signature(req):
    # If no secret set, skip verification (useful for local testing)
    if not PAYSTACK_WEBHOOK_SECRET:
        return True
    sig = req.headers.get("x-paystack-signature", "")
    body = req.get_data()
    computed = hmac.new(PAYSTACK_WEBHOOK_SECRET.encode(), body, hashlib.sha512).hexdigest()
    return hmac.compare_digest(sig, computed)

def send_admin_message(text):
    if not BOT_API_SEND or not ADMIN_TELEGRAM_ID:
        print("[admin msg]", text)
        return
    try:
        requests.post(BOT_API_SEND, json={"chat_id": ADMIN_TELEGRAM_ID, "text": text}, timeout=10)
    except Exception as e:
        print("Failed to send admin message:", e)

def grant_or_renew(email, plan, reference):
    users = load_users()
    now = int(time.time())
    duration_days = DAILY_PLAN_DURATION if plan == "daily" else WEEKEND_PLAN_DURATION
    expires_at = now + duration_days * 24 * 3600

    prev = users.get(email)
    if prev and prev.get("expires_at", 0) > now:
        # extend expiry if current expiry is later
        new_expiry = max(prev["expires_at"], expires_at)
        prev.update({
            "plan": plan,
            "paystack_reference": reference,
            "expires_at": new_expiry,
            "active": True
        })
        users[email] = prev
        action = "renewed"
    else:
        users[email] = {
            "email": email,
            "plan": plan,
            "paystack_reference": reference,
            "expires_at": expires_at,
            "active": True,
            "chat_id": None
        }
        action = "activated"

    save_users(users)

    deep_link = f"https://t.me/{ACCESS_BOT_USERNAME}?start={reference}"
    send_admin_message(f"{email} {action} ({plan}). Paystack ref: {reference}\nDeep-link: {deep_link}")
    return users[email]

# ---- Flask routes ----
@app.route("/", methods=["GET"])
def index():
    return "StakeAware backend running", 200

# Main webhook handler function (used by both webhook routes)
def handle_paystack_event(event_json):
    if not event_json:
        return {"error": "empty payload"}, 400

    etype = event_json.get("event")
    if etype != "charge.success":
        # ignore other events
        return {"status": "ignored"}, 200

    data = event_json.get("data", {}) or {}
    reference = data.get("reference")
    email = (data.get("customer") or {}).get("email") or data.get("customer_email")
    amount = int(data.get("amount", 0)) // 100

    if not reference or not email:
        return {"error": "missing reference or email"}, 400

    # Optionally verify the transaction server-side before trusting it
    if PAYSTACK_SECRET_KEY:
        try:
            verify_url = f"https://api.paystack.co/transaction/verify/{reference}"
            headers = {"Authorization": f"Bearer {PAYSTACK_SECRET_KEY}"}
            r = requests.get(verify_url, headers=headers, timeout=10)
            jr = r.json()
            if not jr.get("status") or jr.get("data", {}).get("status") != "success":
                return {"error": "verification failed"}, 400
            # prefer verified data if present
            verified_data = jr.get("data", {})
            email = (verified_data.get("customer") or {}).get("email") or verified_data.get("customer_email") or email
            amount = int(verified_data.get("amount", amount * 100)) // 100
        except Exception as e:
            print("Error verifying with Paystack:", e)
            return {"error": "verification error"}, 400

    # detect plan (prefer metadata if provided)
    md = data.get("metadata") or {}
    plan = md.get("plan_type") if isinstance(md, dict) else None
    if not plan:
        plan = "daily" if amount >= DAILY_PLAN_AMOUNT else "weekend"

    # record user
    user = grant_or_renew(email, plan, reference)
    return {"status": "ok", "email": email}, 200

# Paystack webhook route
@app.route("/webhook/paystack", methods=["POST"])
def webhook_paystack():
    if not verify_signature(request):
        return "Invalid signature", 400
    try:
        event_json = request.get_json(force=True)
    except Exception:
        return jsonify({"error": "invalid json"}), 400
    result, code = handle_paystack_event(event_json)
    return jsonify(result), code

# Legacy route for backward compatibility (calls same handler)
@app.route("/stakeaware_secure_test_2025", methods=["POST"])
def legacy_webhook():
    # accept both signed and unsigned during testing
    try:
        event_json = request.get_json(force=True)
    except Exception:
        return jsonify({"error": "invalid json"}), 400
    # if signature is set, verify too
    if PAYSTACK_WEBHOOK_SECRET and not verify_signature(request):
        return "Invalid signature", 400
    result, code = handle_paystack_event(event_json)
    return jsonify(result), code

# Paystack redirect (user-facing) with server-side verify -> grant -> deep-link
@app.route("/paystack_redirect", methods=["GET"])
def paystack_redirect():
    ref = request.args.get("reference")
    if not ref:
        return "Missing reference", 400

    # verify transaction server-side
    if not PAYSTACK_SECRET_KEY:
        # cannot verify, but proceed to inform user to open bot (safer to require verification in prod)
        tg_url = f"https://t.me/{ACCESS_BOT_USERNAME}?start={ref}"
        return f"<html><body>Payment processed. <a href='{tg_url}'>Open Access Bot</a></body></html>", 200

    try:
        verify_url = f"https://api.paystack.co/transaction/verify/{ref}"
        headers = {"Authorization": f"Bearer {PAYSTACK_SECRET_KEY}"}
        r = requests.get(verify_url, headers=headers, timeout=10)
        jr = r.json()
    except Exception as e:
        return f"Error contacting Paystack: {e}", 500

    if not jr.get("status") or jr.get("data", {}).get("status") != "success":
        return "Payment verification failed", 400

    verified = jr.get("data", {})
    email = (verified.get("customer") or {}).get("email") or verified.get("customer_email")
    amount = int(verified.get("amount", 0)) // 100

    if not email:
        return "Could not determine customer email from payment", 400

    plan = "daily" if amount >= DAILY_PLAN_AMOUNT else "weekend"
    grant_or_renew(email, plan, ref)
    
  # -------------------- NEW BLOCK --------------------
    # Call admin/users endpoint automatically after verification
    try:
        admin_headers = {"x-admin-key": JWT_SECRET}
        admin_url = f"http://127.0.0.1:{APP_PORT}/admin/users"
        admin_res = requests.get(admin_url, headers=admin_headers, timeout=10)
        if admin_res.status_code == 200:
            print("✅ Admin backend /users hit successfully.")
        else:
            print(f"⚠️ Admin backend returned {admin_res.status_code}: {admin_res.text}")
    except Exception as e:
        print(f"⚠️ Error calling admin/users: {e}")
    # -----------------------------------------------------

    tg_url = f"https://t.me/{ACCESS_BOT_USERNAME}?start={ref}"
    html = f"""
    <html>
      <head><meta http-equiv="refresh" content="0; url={tg_url}" /></head>
      <body>
        <p>Payment successful. Redirecting to Telegram... <a href="{tg_url}">Click here if not redirected</a></p>
      </body>
    </html>
    """
    return html, 200

# Link Telegram endpoint (called by Access Bot deep-link /start handler)
# Link Telegram endpoint (called by Access Bot deep-link /start handler)
# Link Telegram endpoint (called by Access Bot deep-link /start handler)
@app.route("/link_telegram", methods=["POST"])
def link_telegram():
    try:
        data = request.get_json(force=True)
    except Exception:
        return jsonify({"error": "invalid json"}), 400

    chat_id = data.get("chat_id") or data.get("telegram_id")
    reference = data.get("reference") or data.get("paystack_reference")
    if not chat_id or not reference:
        return jsonify({"error": "chat_id and reference are required"}), 400

    users = load_users()
    found = None
    for email, u in users.items():
        if u.get("paystack_reference") == reference:
            found = (email, u)
            break

    if not found:
        return jsonify({"error": "user not found"}), 404

    email, u = found
    u["chat_id"] = int(chat_id)
    u["active"] = True
    users[email] = u
    save_users(users)

    # Determine group invite link
    daily_link = os.environ.get("DAILY_GROUP_LINK")   # e.g. https://t.me/joinchat/xxxx
    weekend_link = os.environ.get("WEEKEND_GROUP_LINK")
    group_link = daily_link if u.get("plan") == "daily" else weekend_link

    # Send user DM with inline "Join Group" button only
    if BOT_API_SEND and group_link:
        try:
            requests.post(BOT_API_SEND, json={
                "chat_id": chat_id,
                "text": f"Payment verified! You now have {u.get('plan')} access.",
                "reply_markup": {
                    "inline_keyboard": [
                        [{"text": "Join Group", "url": group_link}]
                    ]
                }
            }, timeout=8)
        except Exception as e:
            print("Failed to DM user:", e)



    return jsonify({"status": "linked", "email": email}), 200



# Admin users route (protected by JWT_SECRET via header x-admin-key)
@app.route("/admin/users", methods=["GET"])
def admin_users():
    key = request.headers.get("x-admin-key", "")
    if JWT_SECRET and key != JWT_SECRET:
        return "unauthorized", 401
    return jsonify(load_users()), 200

# ---- Expiry checker thread ----
def expiry_checker():
    while True:
        users = load_users()
        now = int(time.time())
        changed = False
        for email, u in list(users.items()):
            exp = u.get("expires_at", 0)
            if u.get("active") and exp:
                # send reminder if within alert window
                if 0 < exp - now <= EXPIRY_ALERT_DAYS * 24 * 3600:
                    if u.get("chat_id"):
                        try:
                            requests.post(BOT_API_SEND, json={
                                "chat_id": u["chat_id"],
                                "text": f"Reminder: your {u.get('plan')} subscription expires on {datetime.utcfromtimestamp(exp).strftime('%Y-%m-%d %H:%M:%S UTC')}"
                            }, timeout=8)
                        except Exception:
                            pass
                    else:
                        send_admin_message(f"User {email} ({u.get('plan')}) expires soon but has no chat_id. Deep-link: https://t.me/{ACCESS_BOT_USERNAME}?start={u.get('paystack_reference')}")
                # expire users
                if exp <= now:
                    u["active"] = False
                    users[email] = u
                    changed = True
                    send_admin_message(f"{email} subscription expired.")
        if changed:
            save_users(users)
        time.sleep(3600)

threading.Thread(target=expiry_checker, daemon=True).start()

if __name__ == "__main__":
    print("Starting StakeAware backend on port", APP_PORT)
    app.run(host="0.0.0.0", port=APP_PORT)
