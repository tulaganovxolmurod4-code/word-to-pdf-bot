import os
import logging
import subprocess
import tempfile
import uuid
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    MessageHandler,
    CommandHandler,
    filters,
)

BOT_TOKEN = os.environ.get("BOT_TOKEN", "SIZNING_BOT_TOKENINGIZ_BU_YERGA")
MAX_FILE_SIZE_MB = 20
ALLOWED_EXTENSIONS = (".doc", ".docx", ".rtf", ".odt")
PORT = int(os.environ.get("PORT", 10000))

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


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


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Salom! 👋\n\n"
        "Men Word (.doc, .docx, .odt, .rtf) faylni PDF ga aylantirib beraman.\n\n"
        "Shunchaki fayl yuboring — men qolganini qilaman ✅"
    )


async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📄 Qanday ishlataman:\n"
        "1. Menga Word faylni (.docx yoki .doc) yuboring\n"
        "2. Men uni PDF ga aylantiraman\n"
        "3. Tayyor PDF faylni sizga qaytaraman\n\n"
        f"Fayl hajmi cheklovi: {MAX_FILE_SIZE_MB} MB"
    )


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
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(MessageHandler(~filters.Document.ALL, handle_wrong_message))

    logger.info("Bot ishga tushdi...")
    app.run_polling()


if __name__ == "__main__":
    main()
