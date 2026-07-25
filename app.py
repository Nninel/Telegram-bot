import logging
import os
import threading
import time
from flask import Flask, render_template_string
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes

# -------------------- НАСТРОЙКА ЛОГИРОВАНИЯ --------------------
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# -------------------- ПОЛУЧАЕМ ТОКЕН --------------------
BOT_TOKEN = os.getenv('BOT_TOKEN') or os.getenv('TELEGRAM_TOKEN')

if not BOT_TOKEN:
    logger.error("❌ Токен не найден! Установите переменную окружения BOT_TOKEN или TELEGRAM_TOKEN")
    logger.error("Настройки Render: Environment Variables -> BOT_TOKEN = ваш_токен")

logger.info(f"✅ Токен загружен: {BOT_TOKEN[:10]}..." if BOT_TOKEN else "❌ Токен отсутствует")

# -------------------- ДАННЫЕ БОТА --------------------
ADMINS = [317983266, 306843085]

marker_replacements = {
    "001": "Подобрал замену 001",
    "002": "Замена для маркера 002",
    "003": "Замена для маркера 003",
}


# -------------------- ОБРАБОТЧИКИ БОТА --------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(
        '👋 Привет! Введите номер маркера, чтобы получить его замену.\n\n'
        '📝 Пример: 001'
    )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    marker_number = update.message.text.strip()
    replacement = marker_replacements.get(marker_number)

    if replacement:
        await update.message.reply_text(f'✅ Для маркера {marker_number}: {replacement}')
    else:
        await update.message.reply_text(
            f'❌ Извините, замена для маркера "{marker_number}" не найдена.\n'
            'Проверьте правильность ввода.'
        )


# -------------------- ЗАПУСК БОТА --------------------
def run_bot():
    """Функция для запуска бота в отдельном потоке"""
    if not BOT_TOKEN:
        logger.error("❌ Бот не запущен: отсутствует токен")
        return

    try:
        # Даем Flask время запуститься
        time.sleep(2)

        logger.info("🚀 Запускаем бота...")
        app = Application.builder().token(BOT_TOKEN).build()
        app.add_handler(CommandHandler("start", start))
        app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

        logger.info("🤖 Бот запущен и готов к работе!")
        logger.info(f"Администраторы: {ADMINS}")
        app.run_polling(allowed_updates=Update.ALL_TYPES)
    except Exception as e:
        logger.error(f"❌ Ошибка при запуске бота: {e}")


# -------------------- FLASK-СЕРВЕР ДЛЯ RENDER --------------------
app = Flask(__name__)

INDEX_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Telegram Bot</title>
    <style>
        body { font-family: Arial, sans-serif; text-align: center; padding: 50px; background: #f0f2f5; }
        .container { background: white; padding: 40px; border-radius: 10px; max-width: 500px; margin: 0 auto; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        h1 { color: #0088cc; }
        .status { font-size: 18px; margin: 20px 0; }
        .online { color: green; font-weight: bold; }
        .offline { color: red; font-weight: bold; }
        .footer { margin-top: 30px; color: #666; font-size: 14px; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🤖 Telegram Bot</h1>
        <div class="status">
            Статус: <span class="online">🟢 Бот работает</span>
        </div>
        <p>Бот для поиска аналогов маркеров</p>
        <p><strong>Токен:</strong> {{ token_status }}</p>
        <p><strong>Администраторы:</strong> {{ admins }}</p>
        <div class="footer">
            Работает на Render.com | Flask + python-telegram-bot
        </div>
    </div>
</body>
</html>
"""


@app.route('/')
def index():
    token_status = "✅ Загружен" if BOT_TOKEN else "❌ Не загружен"
    return render_template_string(INDEX_HTML, token_status=token_status, admins=ADMINS)


@app.route('/health')
def health():
    return {"status": "ok", "token": "configured" if BOT_TOKEN else "missing"}


# -------------------- ЗАПУСК ПРИЛОЖЕНИЯ --------------------
if __name__ == '__main__':
    # Запускаем бота в отдельном потоке
    bot_thread = threading.Thread(target=run_bot, daemon=True)
    bot_thread.start()
    logger.info("🔄 Поток бота запущен")

    # Запускаем Flask-сервер
    port = int(os.getenv('PORT', 5000))
    logger.info(f"🌐 Flask-сервер запущен на порту {port}")

    # Включаем threaded=True для обработки нескольких запросов
    app.run(host='0.0.0.0', port=port, threaded=True)