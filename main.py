# 🔥 CLEAN VERSION (NO PREMIUM FEATURE)

import os
import time
import logging
import csv
from datetime import datetime
import requests

from telegram import Update, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, filters, ContextTypes

from pcloud_utils import create_folder, upload_file, generate_share_link, delete_file
from firebase_db import update_user_status, db

from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")

file_schedule = {}

# ---------------- ADMIN UI ----------------
def admin_keyboard():
    return ReplyKeyboardMarkup([
        ["📊 Stats", "📢 Broadcast"],
        ["📈 Graph", "💾 Export"],
        ["🚫 Ban"]
    ], resize_keyboard=True)

# ---------------- HELP ----------------
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        """
Commands available:
/start - Start the bot
/help - Show this help message
"""
    )

# ---------------- START ----------------
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    update_user_status(user.id, user.username, user.first_name)

    db.collection("bot_users").document(str(user.id)).set({
        "created_at": datetime.now().strftime("%Y-%m-%d")
    }, merge=True)

    msg = (
        """
🔰Welcome to ShareFile Link Bot!🔰

1️⃣ Send me any file (max 1GB).
2️⃣ I’ll upload it to cloud and give you a short download link.
3️⃣ The link will expire automatically after 30 days.
🔒 Files are stored securely and automatically deleted.

🆘 Need help? Contact the bot admin Coding Services (https://t.me/coding_services)
"""
    )

    if str(user.id) == str(ADMIN_ID):
        kb = ReplyKeyboardMarkup([
            ["⬆️ 🙂  Upload"],
            ["📊 Stats", "📢 Broadcast"],
            ["📈 Graph", "💾 Export"],
            ["🚫 Ban"]
        ], resize_keyboard=True)
        await update.message.reply_text(msg, reply_markup=kb)
    else:
        kb = ReplyKeyboardMarkup([["⬆️ Upload"]], resize_keyboard=True)
        await update.message.reply_text(msg, reply_markup=kb)

# ---------------- ACTIVE USERS ----------------
def get_active_users():
    users = db.collection("bot_users").stream()
    active = []

    for u in users:
        data = u.to_dict()
        if not data.get("is_blocked"):
            active.append(int(u.id))

    return active

# ---------------- GRAPH ----------------
def generate_graph_text():
    users = db.collection("bot_users").stream()
    daily = {}

    for u in users:
        d = u.to_dict().get("created_at")
        if d:
            daily[d] = daily.get(d, 0) + 1

    msg = "📈 User Growth (Text Chart)\n\n"

    for d, count in sorted(daily.items()):
        bar = "█" * min(count, 20)
        msg += f"{d} | {bar} ({count})\n"

    return msg

# ---------------- BUTTON & MODE HANDLER ----------------
async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    user_id = str(update.effective_user.id)

    # Check pending modes first
    if context.user_data.get('broadcast'):
        context.user_data['broadcast'] = False
        users = get_active_users()

        for uid in users:
            try:
                await context.bot.send_message(chat_id=int(uid), text=text)
            except Exception:
                update_user_status(uid, "Unknown", "Unknown", True)

        await update.message.reply_text("Broadcast Done")
        return

    elif context.user_data.get('ban'):
        context.user_data['ban'] = False
        db.collection("bot_users").document(text).set({"is_blocked": True}, merge=True)
        await update.message.reply_text("User banned")
        return

    # Handle standard buttons
    if text == "⬆️ Upload":
        await update.message.reply_text("📤 Send your file now.")
        return

    if user_id != str(ADMIN_ID):
        return

    if text == "📊 Stats":
        users = list(db.collection("bot_users").stream())
        total = len(users)
        blocked = sum(1 for u in users if u.to_dict().get("is_blocked"))

        await update.message.reply_text(f"Total: {total}\nBlocked: {blocked}")

    elif text == "📢 Broadcast":
        context.user_data['broadcast'] = True
        await update.message.reply_text("Send message to broadcast:")

    elif text == "📈 Graph":
        await update.message.reply_text(generate_graph_text())

    elif text == "💾 Export":
        users = db.collection("bot_users").stream()

        with open("users.csv", "w", newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(["user_id", "username", "first_name", "blocked"])

            for u in users:
                data = u.to_dict()
                writer.writerow([
                    u.id,
                    data.get("username"),
                    data.get("first_name"),
                    data.get("is_blocked")
                ])

        await update.message.reply_document(open("users.csv", "rb"))

    elif text == "🚫 Ban":
        context.user_data['ban'] = True
        await update.message.reply_text("Send user ID to ban:")

# ---------------- URL SHORTENER ----------------
def shorten_url(long_url):
    base_url = "https://is.gd/create.php"
    params = {"format": "simple", "url": long_url}
    try:
        response = requests.get(base_url, params=params, timeout=5)
        response.raise_for_status()
        return response.text.strip()
    except requests.RequestException as e:
        print(f"Error shortening URL: {e}")
        return long_url

# ---------------- FILE ----------------
async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    if not doc:
        return

    if doc.file_size and doc.file_size > 1024 * 1024 * 1024:  # 1GB limit
        await update.message.reply_text("🚫 File too large. Limit: 1GB")
        return

    status = await update.message.reply_text("♻️ Uploading to pCloud...")
    file_path = None

    try:
        tg_file = await doc.get_file()
        os.makedirs("temp", exist_ok=True)
        file_path = os.path.join("temp", doc.file_name)
        await tg_file.download_to_drive(file_path)

        # Upload to pCloud
        folder_id = create_folder("TelegramUploads")
        file_id = upload_file(folder_id, file_path)
        share_data = generate_share_link(file_id)
        short_link = share_data.get("shortlink") or share_data.get("link")

        await status.edit_text(f"✅ Here is your link (valid for 30 days):\n{short_link}")

    except Exception as e:
        logging.exception("Failed to upload file to pCloud:")
        await status.edit_text(f"❌ Failed to upload file: {str(e)}")

    finally:
        if file_path and os.path.exists(file_path):
            try:
                os.remove(file_path)
            except OSError as e:
                logging.warning(f"Could not remove temp file: {e}")

# ---------------- MAIN ----------------
def main():
    app = ApplicationBuilder().token(TOKEN).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("help", help_command))

    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file))

    print("Bot is running with pCloud...")
    app.run_polling()

if __name__ == "__main__":
    main()
