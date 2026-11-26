import os
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from scanner import scan_all
from signal_engine import format_signal

load_dotenv()
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
ALLOWED = {x.strip() for x in os.getenv("ALLOWED_CHAT_IDS", "").split(",") if x.strip()}

def authorized(update: Update) -> bool:
    return not ALLOWED or str(update.effective_chat.id) in ALLOWED

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not authorized(update):
        return
    await update.message.reply_text(
        "Welcome to RABATY AI TRADER. I provide analysis signals only; I do not place trades.\\n"
        "Commands: /scan, /help"
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if authorized(update):
        await update.message.reply_text("/scan — analyze Gold, XAUT, BTC and ETH on configured timeframes.")

async def scan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not authorized(update):
        return
    msg = await update.message.reply_text("Scanning public market data…")
    results = scan_all()
    chunks = []
    for s in results:
        if s["side"] == "ERROR":
            chunks.append(f"⚠️ {s['symbol']} {s['timeframe']}: {s['error'][:180]}")
        else:
            chunks.append(format_signal(s))
    text = "\n\n".join(chunks)
    for i in range(0, len(text), 3900):
        await context.bot.send_message(chat_id=update.effective_chat.id, text=text[i:i+3900])
    await msg.delete()

def main():
    if not TOKEN:
        raise SystemExit("Set TELEGRAM_BOT_TOKEN in your .env file first.")
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("scan", scan))
    print("RABATY AI TRADER Telegram bot is running…")
    app.run_polling()

if __name__ == "__main__":
    main()
