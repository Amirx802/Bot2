import os
from dataclasses import dataclass, field

from dotenv import load_dotenv

load_dotenv()


def _admin_ids() -> set[int]:
    raw = os.getenv("ADMIN_IDS", "")
    return {int(x) for x in raw.replace(" ", "").split(",") if x.isdigit()}


@dataclass(frozen=True)
class Settings:
    token: str = os.getenv("BOT_TOKEN", "")
    admin_ids: set[int] = field(default_factory=_admin_ids)
    db_path: str = os.getenv("DB_PATH", "data/bot.db")
    # اگر WEBHOOK_URL تنظیم باشد از webhook استفاده می‌شود، وگرنه polling
    webhook_url: str = os.getenv("WEBHOOK_URL", "")
    port: int = int(os.getenv("PORT", "8443"))
    webhook_secret: str = os.getenv("WEBHOOK_SECRET", "")


settings = Settings()

if not settings.token:
    raise SystemExit("BOT_TOKEN تنظیم نشده. فایل .env را بسازید (به .env.example نگاه کنید).")
