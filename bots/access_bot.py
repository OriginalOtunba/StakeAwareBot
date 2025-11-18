# -------------------- WEBHOOK HANDLER -------------------- #

@app.route("/access_bot", methods=["POST"])
def webhook_handler():
    if telegram_app is None:
        return "Bot not initialized", 503

    try:
        update = Update.de_json(request.get_json(force=True), telegram_app.bot)
        telegram_app.update_queue.put_nowait(update)
    except Exception as e:
        print("Webhook error:", e)
        return "error", 400

    return "ok", 200


def start_webhook():
    global telegram_app

    telegram_app = ApplicationBuilder().token(ACCESS_BOT_TOKEN).build()
    telegram_app.add_handler(CommandHandler("start", start))
    telegram_app.add_handler(CallbackQueryHandler(button_handler))
    telegram_app.add_handler(CommandHandler("status", status))

    # Assign webhook
    full_url = f"{WEBHOOK_URL}/access_bot"
    print("Setting Access Bot webhook:", full_url)
    telegram_app.bot.set_webhook(url=full_url)

    return telegram_app


# -------------------- ENTRY POINT -------------------- #

if __name__ == "__main__":
    if not ACCESS_BOT_TOKEN:
        print("❌ ACCESS_BOT_TOKEN missing")
        exit()

    mode = os.environ.get("RUN_MODE", "webhook")

    if mode == "polling":
        # Local testing only
        test_app = ApplicationBuilder().token(ACCESS_BOT_TOKEN).build()
        test_app.add_handler(CommandHandler("start", start))
        test_app.add_handler(CallbackQueryHandler(button_handler))
        test_app.add_handler(CommandHandler("status", status))
        print("Running in polling mode...")
        test_app.run_polling()
    else:
        # Render deployment
        start_webhook()
        app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
