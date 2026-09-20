import logging

from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from . import db, handlers
from .config import settings

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)


def build_app() -> Application:
    app = Application.builder().token(settings.token).build()
    app.add_handler(CommandHandler("start", handlers.start))
    app.add_handler(CommandHandler("help", handlers.help_cmd))
    app.add_handler(CommandHandler("ping", handlers.ping))
    app.add_handler(CommandHandler("id", handlers.my_id))
    app.add_handler(CommandHandler("stats", handlers.stats))
    app.add_handler(CommandHandler("broadcast", handlers.broadcast))
    app.add_handler(CallbackQueryHandler(handlers.buttons))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.echo))
    app.add_error_handler(handlers.error_handler)
    return app


def main() -> None:
    db.init_db()
    app = build_app()
    if settings.webhook_url:
        app.run_webhook(
            listen="0.0.0.0",
            port=settings.port,
            webhook_url=settings.webhook_url,
            secret_token=settings.webhook_secret or None,
        )
    else:
        app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
