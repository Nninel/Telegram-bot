import logging
import os
import threading
from flask import Flask, render_template_string
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# -------------------- НАСТРОЙКА ЛОГИРОВАНИЯ --------------------
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# -------------------- ПОЛУЧАЕМ ТОКЕН --------------------
BOT_TOKEN = os.getenv('BOT_TOKEN') or os.getenv('TELEGRAM_TOKEN')

if not BOT_TOKEN:
    logger.error("❌ Токен не найден!")
else:
    logger.info(f"✅ Токен загружен: {BOT_TOKEN[:10]}...")

# -------------------- ДАННЫЕ БОТА --------------------
ADMINS = [317983266, 306843085]

# База данных маркеров с аналогами
MARKERS_DB = {
    "GuangNa": {
        "G-001": {
            "name": "GuangNa G-001 (Cool Gray 1)",
            "analogs": [
                {"brand": "Languo", "model": "L-100", "note": "Аналог, теплее на 5%"},
                {"brand": "Copic", "model": "C-1", "note": "Дорогой аналог"},
                {"brand": "Ohuhu", "model": "CG-1", "note": "Бюджетный вариант"}
            ]
        },
        "G-002": {
            "name": "GuangNa G-002 (Cool Gray 2)",
            "analogs": [
                {"brand": "Languo", "model": "L-101", "note": "Полный аналог"},
                {"brand": "Copic", "model": "C-2", "note": "Более насыщенный"}
            ]
        },
        "G-003": {
            "name": "GuangNa G-003 (Cool Gray 3)",
            "analogs": [
                {"brand": "Languo", "model": "L-102", "note": "Хороший аналог"},
                {"brand": "Copic", "model": "C-3", "note": "Дорогой аналог"}
            ]
        }
    },
    "Languo": {
        "L-100": {
            "name": "Languo L-100 (Warm Gray 1)",
            "analogs": [
                {"brand": "GuangNa", "model": "G-001", "note": "Холоднее на 10%"},
                {"brand": "Copic", "model": "W-1", "note": "Дорогой аналог"}
            ]
        },
        "L-101": {
            "name": "Languo L-101 (Warm Gray 2)",
            "analogs": [
                {"brand": "GuangNa", "model": "G-002", "note": "Полный аналог"},
                {"brand": "Copic", "model": "W-2", "note": "Более теплый"}
            ]
        },
        "L-102": {
            "name": "Languo L-102 (Warm Gray 3)",
            "analogs": [
                {"brand": "GuangNa", "model": "G-003", "note": "Хороший аналог"}
            ]
        }
    }
}

# Словарь для быстрого поиска по номеру (все маркеры)
ALL_MARKERS = {}
for brand, markers in MARKERS_DB.items():
    for marker_id, marker_data in markers.items():
        ALL_MARKERS[marker_id] = {
            "brand": brand,
            "name": marker_data["name"],
            "analogs": marker_data["analogs"]
        }


# -------------------- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ --------------------
def find_marker(query: str) -> dict:
    """Поиск маркера по номеру"""
    query = query.strip().upper()
    return ALL_MARKERS.get(query)


def format_analogs(marker_data: dict) -> str:
    """Форматирование результата поиска"""
    text = f"🔍 *Результат поиска:*\n"
    text += f"📌 *Маркер:* {marker_data['name']}\n"
    text += f"🏷️ *Бренд:* {marker_data['brand']}\n\n"

    if marker_data['analogs']:
        text += "🔄 *Доступные аналоги:*\n\n"
        for i, analog in enumerate(marker_data['analogs'], 1):
            text += f"{i}. *{analog['brand']} {analog['model']}*\n"
            if analog.get('note'):
                text += f"   📝 {analog['note']}\n"
            text += "\n"
    else:
        text += "❌ *Аналоги не найдены*\n"

    return text


# -------------------- ОБРАБОТЧИКИ БОТА --------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда /start - показывает главное меню"""
    keyboard = [
        [InlineKeyboardButton("🏷️ Выбрать бренд", callback_data="select_brand")],
        [InlineKeyboardButton("🔍 Поиск по номеру", callback_data="search_by_number")],
        [InlineKeyboardButton("📖 Справка", callback_data="help")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        '👋 Привет! Я помогу найти аналоги для маркеров.\n\n'
        'Выберите действие:',
        reply_markup=reply_markup
    )


async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик нажатий на кнопки"""
    query = update.callback_query
    await query.answer()

    if query.data == "select_brand":
        # Показываем список брендов
        keyboard = []
        for brand in MARKERS_DB.keys():
            keyboard.append([InlineKeyboardButton(f"🏷️ {brand}", callback_data=f"brand_{brand}")])
        keyboard.append([InlineKeyboardButton("⬅️ Назад", callback_data="back_to_menu")])

        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "📋 *Выберите бренд:*",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

    elif query.data.startswith("brand_"):
        # Показываем маркеры выбранного бренда
        brand = query.data.replace("brand_", "")
        markers = MARKERS_DB.get(brand, {})

        if markers:
            keyboard = []
            for marker_id, marker_info in markers.items():
                keyboard.append([
                    InlineKeyboardButton(
                        f"🖊️ {marker_id} - {marker_info['name'][:20]}...",
                        callback_data=f"marker_{brand}_{marker_id}"
                    )
                ])
            keyboard.append([InlineKeyboardButton("⬅️ Назад к брендам", callback_data="select_brand")])

            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                f"🏷️ *Бренд: {brand}*\n\nВыберите модель:",
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )

    elif query.data.startswith("marker_"):
        # Показываем информацию о маркере
        parts = query.data.split("_", 2)
        if len(parts) >= 3:
            brand = parts[1]
            marker_id = parts[2]
            marker = MARKERS_DB.get(brand, {}).get(marker_id)

            if marker:
                marker_data = {
                    "brand": brand,
                    "name": marker["name"],
                    "analogs": marker["analogs"]
                }
                response = format_analogs(marker_data)

                keyboard = [
                    [InlineKeyboardButton("🔄 Найти другой", callback_data="select_brand")],
                    [InlineKeyboardButton("⬅️ Назад к маркерам", callback_data=f"brand_{brand}")],
                    [InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_menu")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)

                await query.edit_message_text(
                    response,
                    reply_markup=reply_markup,
                    parse_mode="Markdown"
                )

    elif query.data == "search_by_number":
        await query.edit_message_text(
            "🔍 *Введите номер маркера*\n\n"
            "Примеры: G-001, L-100, G-002\n\n"
            "Я покажу все доступные аналоги.",
            parse_mode="Markdown"
        )

    elif query.data == "help":
        help_text = (
            "📖 *Справка*\n\n"
            "🔹 *Поиск по номеру:*\n"
            "Просто введите номер маркера\n"
            "Примеры: G-001, L-100\n\n"
            "🔹 *Поиск по бренду:*\n"
            "Выберите бренд в меню\n\n"
            "🔹 *Доступные бренды:*\n"
            f"{', '.join(MARKERS_DB.keys())}\n\n"
            "💡 *Совет:* Вводите номер с дефисом"
        )

        keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data="back_to_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(help_text, reply_markup=reply_markup, parse_mode="Markdown")

    elif query.data == "back_to_menu":
        # Возврат в главное меню
        keyboard = [
            [InlineKeyboardButton("🏷️ Выбрать бренд", callback_data="select_brand")],
            [InlineKeyboardButton("🔍 Поиск по номеру", callback_data="search_by_number")],
            [InlineKeyboardButton("📖 Справка", callback_data="help")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            '👋 *Главное меню*\n\n'
            'Выберите действие:',
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработка текстовых сообщений (поиск по номеру)"""
    user_input = update.message.text.strip().upper()

    # Ищем маркер
    marker_data = find_marker(user_input)

    if marker_data:
        response = format_analogs(marker_data)

        keyboard = [
            [InlineKeyboardButton("🔍 Новый поиск", callback_data="search_by_number")],
            [InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(response, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        keyboard = [
            [InlineKeyboardButton("🏷️ Выбрать бренд", callback_data="select_brand")],
            [InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            f"❌ *Маркер '{user_input}' не найден*\n\n"
            "Проверьте правильность ввода.\n"
            "Примеры: G-001, L-100\n\n"
            "Или выберите бренд из меню:",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )


# -------------------- FLASK-СЕРВЕР --------------------
flask_app = Flask(__name__)

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
        <p><strong>Бренды:</strong> GuangNa, Languo</p>
        <div class="footer">
            Работает на Render.com | Flask + python-telegram-bot
        </div>
    </div>
</body>
</html>
"""


@flask_app.route('/')
def index():
    token_status = "✅ Загружен" if BOT_TOKEN else "❌ Не загружен"
    return render_template_string(INDEX_HTML, token_status=token_status, admins=ADMINS)


@flask_app.route('/health')
def health():
    return {"status": "ok", "token": "configured" if BOT_TOKEN else "missing"}


# -------------------- ЗАПУСК FLASK В ФОНОВОМ ПОТОКЕ --------------------
def run_flask():
    port = int(os.getenv('PORT', 5000))
    logger.info(f"🌐 Flask-сервер на порту {port}")
    flask_app.run(host='0.0.0.0', port=port, threaded=True)


# -------------------- ЗАПУСК БОТА --------------------
def run_bot():
    if not BOT_TOKEN:
        logger.error("❌ Бот не запущен: отсутствует токен")
        return

    try:
        logger.info("🚀 Запускаем бота...")
        bot_app = Application.builder().token(BOT_TOKEN).build()

        # Добавляем обработчики
        bot_app.add_handler(CommandHandler("start", start))
        bot_app.add_handler(CallbackQueryHandler(button_handler))
        bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

        logger.info("🤖 Бот запущен и готов к работе!")
        logger.info(f"Администраторы: {ADMINS}")
        bot_app.run_polling(allowed_updates=Update.ALL_TYPES)
    except Exception as e:
        logger.error(f"❌ Ошибка при запуске бота: {e}")
        import traceback
        logger.error(traceback.format_exc())


# -------------------- ГЛАВНЫЙ ЗАПУСК --------------------
if __name__ == '__main__':
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    logger.info("🔄 Flask запущен в фоновом потоке")
    run_bot()
else:
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    run_bot()