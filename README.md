# Word → PDF Telegram Bot

Bu bot foydalanuvchi yuborgan Word faylni (.docx, .doc, .odt, .rtf) PDF formatga aylantirib qaytaradi.

## 1. Bot tokenini olish

1. Telegram'da @BotFather ni oching
2. /newbot buyrug'ini yuboring
3. Bot nomini va username'ini kiriting
4. Sizga beriladigan tokenni saqlab qo'ying

## 2. Kerakli dasturlarni o'rnatish

Bot ishlashi uchun serverda LibreOffice o'rnatilgan bo'lishi shart.

Ubuntu / Debian serverda:
sudo apt update
sudo apt install -y libreoffice

Python kutubxonalarini o'rnatish:
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

## 3. Bot tokenini sozlash

export BOT_TOKEN="sizning_tokeningiz_shu_yerda"

## 4. Botni ishga tushirish

python3 bot.py

## 5. Production uchun systemd

/etc/systemd/system/wordpdfbot.service faylini yarating va quyidagini kiriting:

[Unit]
Description=Word to PDF Telegram Bot
After=network.target

[Service]
WorkingDirectory=/root/wordpdfbot
ExecStart=/root/wordpdfbot/venv/bin/python3 bot.py
Environment=BOT_TOKEN=sizning_tokeningiz
Restart=always
User=root

[Install]
WantedBy=multi-user.target

So'ng:
sudo systemctl daemon-reload
sudo systemctl enable wordpdfbot
sudo systemctl start wordpdfbot
