import os
import time
import threading
import logging
import requests
import schedule
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    MessageHandler,
    CommandHandler,
    filters,
    ContextTypes
)
from telegram.request import HTTPXRequest
from pcloud_utils import create_folder, upload_file, generate_share_link, delete_file
from keep_alive import keep_alive
keep_alive()
# from dotenv import load_dotenv
# load_dotenv()

# Logging setup
logging.basicConfig(level=logging.INFO)

TOKEN = os.getenv("TOKEN")
# Track file expiry
file_schedule = {}  # file_id: {"expiry": timestamp, "filename": name}

# URL shortener
def shorten_url(long_url):
    base_url = "https://is.gd/create.php"
    params = {"format": "simple", "url": long_url}
    try:
        response = requests.get(base_url, params=params, timeout=5)
        response.raise_for_status()
        return response.text.strip()
    except requests.RequestException as e:
        print(f"Error shortening URL: {e}")
        return None

# /start command
async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🔰*Welcome to File Link Bot!*🔰\n\n"
        "✅ Send me any file and I’ll upload it to the cloud and give you a short download link. "
        "This link will be valid for 30 days.\n\n"
        "✅Type /help to see more.",
        parse_mode="Markdown",
    )

# /help command
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📌 *Bot Instructions:*\n\n"
        "1️⃣ Send me any file (max 1GB).\n"
        "2️⃣ I’ll upload it to pCloud and give you a short download link.\n"
        "3️⃣ The link will expire automatically after 30 days.\n"
        "🔒 Files are stored securely and automatically deleted.\n\n"
        "🆘 Need help? Contact the bot admin [Coding Services](https://t.me/coding_services)",
        parse_mode="Markdown",
    )

# Handle file uploads
async def handle_file(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        doc = update.message.document
        if doc.file_size > 1024 * 1024 * 1024:  # 1GB limit
            await update.message.reply_text("🚫 File too large Limit: 1GB")
            return

        # Send the initial message and store it
        status_message = await update.message.reply_text("♻️ File uploading...")

        tg_file = await doc.get_file()
        filename = doc.file_name
        os.makedirs("temp", exist_ok=True)
        file_path = f"./temp/{filename}"
        await tg_file.download_to_drive(file_path)

        folder_id = create_folder("TelegramUploads")
        file_id = upload_file(folder_id, file_path)
        link_data = generate_share_link(file_id)
        short_link = shorten_url(link_data['link'])
        # Edit the status message we stored earlier
        await status_message.edit_text(f"✅ Here is your link (valid for 30 days):\n{short_link}")

        file_schedule[file_id] = {
            "expiry": time.time() + 30 * 86400,
            "filename": filename
        }

        # delete file from temp folder after uploading to pCloud
        try:
            os.remove(file_path)
        except OSError as e:
            logging.warning(f"Could not remove temp file: {e}")

    except Exception as e:
        logging.exception("🚫 Error in handle_file:")
        await update.message.reply_text("🚫 Failed to process your file. Please try again later.")

# Auto-delete expired files
def delete_expired_files():
    now = time.time()
    expired = [fid for fid, info in file_schedule.items() if now >= info["expiry"]]
    for fid in expired:
        delete_file(fid)
        del file_schedule[fid]


# /status command
async def status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not file_schedule:
        await update.message.reply_text("📭 No files are scheduled for deletion.")
        return

    now = time.time()
    status_lines = [f"📚 Total files scheduled: {len(file_schedule)}\n"]

    for fid, info in file_schedule.items():
        remaining = info["expiry"] - now
        if remaining > 0:
            remaining_str = str(timedelta(seconds=int(remaining)))
            status_lines.append(
                f"📘 *{info['filename']}*\n"
                f"🆔 *File ID:* `{fid}`\n"
                f"⏳ *Expires in:* {remaining_str}\n"
            )

    await update.message.reply_text("\n".join(status_lines), parse_mode="Markdown")


def run_schedule():
    while True:
        schedule.run_pending()
        time.sleep(60)

# Start bot
def main():
    schedule.every(12).hours.do(delete_expired_files)
    # schedule.every(1).minutes.do(delete_expired_files)

    threading.Thread(target=run_schedule, daemon=True).start()

    request = HTTPXRequest(connect_timeout=10.0, read_timeout=30.0)
    app = ApplicationBuilder().token(TOKEN).request(request).build()

    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("status", status_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_file))

    app.run_polling()

if __name__ == "__main__":
    main()
