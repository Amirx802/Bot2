# Telegram Bot Server

یک ربات تلگرام آماده با پایتون (`python-telegram-bot`) و دیتابیس SQLite.

## امکانات
- دستورات `/start` `/help` `/ping` `/id`
- دکمه‌های شیشه‌ای (Inline)
- ذخیره کاربران در SQLite
- دستورات ادمین: `/stats` و `/broadcast متن`
- پشتیبانی از polling و webhook
- Dockerfile و docker-compose
- GitHub Actions برای بررسی کد

## اجرا
```bash
git clone <repo-url> && cd telegram-bot
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # و BOT_TOKEN را بگذارید
python -m bot.main
```

## اجرا با Docker
```bash
cp .env.example .env
docker compose up -d --build
```

## حالت Webhook
`WEBHOOK_URL` را روی آدرس HTTPS عمومی سرور بگذارید (مثلاً `https://example.com/bot`). اگر خالی باشد، polling استفاده می‌شود.

## نکته امنیتی
فایل `.env` را هرگز در گیت‌هاب نگذارید (در `.gitignore` هست). اگر توکن لو رفت، از @BotFather دوباره بسازید.
