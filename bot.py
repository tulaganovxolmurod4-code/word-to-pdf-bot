import os
import json
import logging
import subprocess
import tempfile
import uuid
import threading
from datetime import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    MessageHandler,
    CommandHandler,
    CallbackQueryHandler,
    filters,
)

# ==== SOZLAMALAR ====
BOT_TOKEN = os.environ.get("BOT_TOKEN", "SIZNING_BOT_TOKENINGIZ_BU_YERGA")
ADMIN_ID = 8490356906  # Sizning Telegram ID'ingiz
MAX_FILE_SIZE_MB = 20
ALLOWED_EXTENSIONS = (".doc", ".docx", ".rtf", ".odt")
PORT = int(os.environ.get("PORT", 10000))
USERS_FILE = "users.json"

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


# ==== FOYDALANUVCHILARNI SAQLASH ====
def load_users():
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_users(users):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump(users, f, ensure_ascii=False, indent=2)


def register_user(user):
    users = load_users()
    uid = str(user.id)
    if uid not in users:
        users[uid] = {
            "first_name": user.first_name or "",
            "last_name": user.last_name or "",
            "username": user.username or "",
            "joined": datetime.now().strftime("%Y-%m-%d %H:%M"),
        }
        save_users(users)
    return users


# ==== RENDER UCHUN SOXTA VEB-SERVER ====
class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"Bot is running")

    def log_message(self, format, *args):
        pass


def run_health_server():
    server = HTTPServer(("0.0.0.0", PORT), HealthHandler)
    server.serve_forever()


# ==== ASOSIY MENYU ====
def main_menu(user_id: int):
    keyboard = [[InlineKeyboardButton("ℹ️ Yordam", callback_data="help")]]
    if user_id == ADMIN_ID:
        keyboard.append([InlineKeyboardButton("⚙️ Admin panel", callback_data="admin")])
    return InlineKeyboardMarkup(keyboard)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    register_user(update.effective_user)
    await update.message.reply_text(
        "Salom! 👋\n\n"
        "Men Word (.doc, .docx, .odt, .rtf) faylni PDF ga aylantirib beraman.\n\n"
        "Shunchaki fayl yuboring — men qolganini qilaman ✅",
        reply_markup=main_menu(update.effective_user.id),
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📄 Qanday ishlataman:\n"
        "1. Menga Word faylni (.docx yoki .doc) yuboring\n"
        "2. Men uni PDF ga aylantiraman\n"
        "3. Tayyor PDF faylni sizga qaytaraman\n\n"
        f"Fayl hajmi cheklovi: {MAX_FILE_SIZE_MB} MB"
    )


# ==== TUGMALAR BOSILGANDA ====
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "help":
        await query.message.reply_text(
            "📄 Qanday ishlataman:\n"
            "1. Menga Word faylni (.docx yoki .doc) yuboring\n"
            "2. Men uni PDF ga aylantiraman\n"
            "3. Tayyor PDF faylni sizga qaytaraman"
        )

    elif query.data == "admin":
        if query.from_user.id != ADMIN_ID:
            await query.message.reply_text("⛔ Sizda ruxsat yo'q.")
            return

        users = load_users()
        total = len(users)

        text = f"⚙️ <b>Admin panel</b>\n\n👥 Jami foydalanuvchilar: <b>{total}</b>\n\n"

        # oxirgi 15 ta foydalanuvchini ko'rsatish
        text += "<b>Oxirgi foydalanuvchilar:</b>\n"
        sorted_users = sorted(
            users.items(), key=lambda x: x[1]["joined"], reverse=True
        )[:15]

        for uid, info in sorted_users:
            name = info["first_name"]
            if info["last_name"]:
                name += " " + info["last_name"]
            uname = f"@{info['username']}" if info["username"] else "—"
            text += f"• {name} ({uname}) — {info['joined']}\n"

        await query.message.reply_text(text, parse_mode="HTML")


def convert_to_pdf(input_path: str, output_dir: str) -> str:
    cmd = [
        "libreoffice",
        "--headless",
        "--convert-to",
        "pdf",
        "--outdir",
        output_dir,
        input_path,
    ]
    result = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        timeout=120,
    )
    if result.returncode != 0:
        logger.error("LibreOffice xatosi: %s", result.stderr.decode(errors="ignore"))
        raise RuntimeError("Konvertatsiya muvaffaqiyatsiz tugadi")

    base_name = os.path.splitext(os.path.basename(input_path))[0]
    pdf_path = os.path.join(output_dir, base_name + ".pdf")

    if not os.path.exists(pdf_path):
        raise RuntimeError("PDF fayl yaratilmadi")

    return pdf_path


async def handle_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    register_user(update.effective_user)
    document = update.message.document

    if document is None:
        await update.message.reply_text("Iltimos, fayl sifatida yuboring 📎")
        return

    file_name = document.file_name or ""
    ext = os.path.splitext(file_name)[1].lower()

    if ext not in ALLOWED_EXTENSIONS:
        await update.message.reply_text(
            "❌ Bu fayl turi qo'llab-quvvatlanmaydi.\n"
            "Faqat .doc, .docx, .odt, .rtf fayllarni yuboring."
        )
        return

    file_size_mb = document.file_size / (1024 * 1024)
    if file_size_mb > MAX_FILE_SIZE_MB:
        await update.message.reply_text(
            f"❌ Fayl juda katta ({file_size_mb:.1f} MB). "
            f"Maksimal hajm: {MAX_FILE_SIZE_MB} MB."
        )
        return

    status_msg = await update.message.reply_text("⏳ Konvertatsiya qilinmoqda...")

    with tempfile.TemporaryDirectory() as tmp_dir:
        unique_name = f"{uuid.uuid4().hex}{ext}"
        input_path = os.path.join(tmp_dir, unique_name)

        tg_file = await document.get_file()
        await tg_file.download_to_drive(custom_path=input_path)

        try:
            pdf_path = convert_to_pdf(input_path, tmp_dir)
        except Exception as e:
            logger.exception("Konvertatsiya xatosi")
            await status_msg.edit_text(
                "❌ Konvertatsiya vaqtida xatolik yuz berdi.\n"
                "Fayl shikastlangan yoki formatda muammo bo'lishi mumkin."
            )
            return

        original_name = os.path.splitext(file_name)[0]
        with open(pdf_path, "rb") as f:
            await update.message.reply_document(
                document=f,
                filename=f"{original_name}.pdf",
                caption="✅ Tayyor!",
            )

        await status_msg.delete()


async def handle_wrong_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📎 Menga Word fayl (.docx, .doc, .odt, .rtf) yuboring, men uni PDF qilib beraman."
    )


def main():
    if BOT_TOKEN == "SIZNING_BOT_TOKENINGIZ_BU_YERGA":
        print("❗ BOT_TOKEN o'rnatilmagan.")
        return

    health_thread = threading.Thread(target=run_health_server, daemon=True)
    health_thread.start()

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(MessageHandler(~filters.Document.ALL, handle_wrong_message))

    logger.info("Bot ishga tushdi...")
    app.run_polling()


if __name__ == "__main__":
    main()
