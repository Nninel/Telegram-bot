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

# База данных маркеров с аналогами (ключи - только номера)
MARKERS_DB = {
    "GuangNa": {
        "prefix": "G",
        "markers": {
            "1": {
                "name": "GuangNa G-001 (Cool Gray 1)",
                "analogs": [
                    {"brand": "Languo", "model": "L-100", "note": "Аналог, теплее на 5%"},
                    {"brand": "Copic", "model": "C-1", "note": "Дорогой аналог"},
                    {"brand": "Ohuhu", "model": "CG-1", "note": "Бюджетный вариант"}
                ]
            },
            "2": {
                "name": "GuangNa G-002 (Cool Gray 2)",
                "analogs": [
                    {"brand": "Languo", "model": "L-101", "note": "Полный аналог"},
                    {"brand": "Copic", "model": "C-2", "note": "Более насыщенный"}
                ]
            },
            "3": {
                "name": "GuangNa G-003 (Cool Gray 3)",
                "analogs": [
                    {"brand": "Languo", "model": "L-102", "note": "Хороший аналог"},
                    {"brand": "Copic", "model": "C-3", "note": "Дорогой аналог"}
                ]
            },
            "12": {
                "name": "GuangNa G-012",
                "analogs": [
                    {"brand": "Languo", "model": "L-013", "note": "Аналог 1"}
                ]
            },
            "14": {
                "name": "GuangNa G-014",
                "analogs": [
                    {"brand": "Languo", "model": "L-015", "note": "Аналог 2"}
                ]
            }
        }
    },
    "Languo": {
        "prefix": "L",
        "markers": {
            "100": {
                "name": "Languo L-100 (Warm Gray 1)",
                "analogs": [
                    {"brand": "GuangNa", "model": "G-001", "note": "Холоднее на 10%"},
                    {"brand": "Copic", "model": "W-1", "note": "Дорогой аналог"}
                ]
            },
            "101": {
                "name": "Languo L-101 (Warm Gray 2)",
                "analogs": [
                    {"brand": "GuangNa", "model": "G-002", "note": "Полный аналог"},
                    {"brand": "Copic", "model": "W-2", "note": "Более теплый"}
                ]
            },
            "102": {
                "name": "Languo L-102 (Warm Gray 3)",
                "analogs": [
                    {"brand": "GuangNa", "model": "G-003", "note": "Хороший аналог"}
                ]
            },
            "13": {
                "name": "Languo L-013",
                "analogs": [
                    {"brand": "GuangNa", "model": "G-012", "note": "Аналог 1"}
                ]
            },
            "15": {
                "name": "Languo L-015",
                "analogs": [
                    {"brand": "GuangNa", "model": "G-014", "note": "Аналог 2"}
                ]
            }
        }
    }
}

# -------------------- СОСТОЯНИЯ ПОЛЬЗОВАТЕЛЕЙ --------------------
user_states = {}  # user_id -> {"brand": str, "waiting_for_number": bool}


# -------------------- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ --------------------
def find_marker_by_brand_and_number(brand: str, number: str) -> dict:
    """Поиск маркера по бренду и номеру (без префикса)"""
    brand_data = MARKERS_DB.get(brand)
    if not brand_data:
        return None

    marker_data = brand_data["markers"].get(number)
    if not marker_data:
        return None

    prefix = brand_data["prefix"]
    full_id = f"{prefix}-{number.zfill(3)}"

    return {
        "brand": brand,
        "number": number,
        "full_id": full_id,
        "name": marker_data["name"],
        "analogs": marker_data["analogs"]
    }


def find_marker_by_full_id(full_id: str) -> dict:
    """Поиск маркера по полному номеру (с префиксом) - для обратной совместимости"""
    full_id = full_id.strip().upper()
    for brand, brand_data in MARKERS_DB.items():
        prefix = brand_data["prefix"]
        for number, marker_data in brand_data["markers"].items():
            if f"{prefix}-{number.zfill(3)}" == full_id:
                return {
                    "brand": brand,
                    "number": number,
                    "full_id": full_id,
                    "name": marker_data["name"],
                    "analogs": marker_data["analogs"]
                }
    return None


def format_analogs(marker_data: dict) -> str:
    """Форматирование результата поиска"""
    text = f"🔍 *Результат поиска:*\n"
    text += f"📌 *Маркер:* {marker_data['name']}\n"
    text += f"🏷️ *Бренд:* {marker_data['brand']}\n"
    text += f"🔢 *Номер:* {marker_data['full_id']}\n\n"

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


def get_available_numbers(brand: str) -> list:
    """Получить список доступных номеров для бренда"""
    brand_data = MARKERS_DB.get(brand, {})
    numbers = list(brand_data.get("markers", {}).keys())
    numbers.sort(key=lambda x: int(x) if x.isdigit() else 0)
    return numbers


# -------------------- ОБРАБОТЧИКИ БОТА --------------------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Команда /start - показывает главное меню"""
    user_id = update.effective_user.id
    user_states[user_id] = {"brand": None, "waiting_for_number": False}

    keyboard = [
        [InlineKeyboardButton("🏷️ Выбрать бренд", callback_data="select_brand")],
        [InlineKeyboardButton("🔍 Поиск по полному номеру", callback_data="search_by_full_id")],
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
    user_id = update.effective_user.id

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
        # Пользователь выбрал бренд - теперь ждем ввода номера
        brand = query.data.replace("brand_", "")
        user_states[user_id] = {"brand": brand, "waiting_for_number": True}

        # Показываем доступные номера
        available = get_available_numbers(brand)
        examples = ", ".join(available[:10])
        if len(available) > 10:
            examples += f" и еще {len(available) - 10}"

        keyboard = [
            [InlineKeyboardButton("📋 Показать все маркеры", callback_data=f"show_markers_{brand}")],
            [InlineKeyboardButton("⬅️ Назад к брендам", callback_data="select_brand")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(
            f"🏷️ *Бренд: {brand}*\n\n"
            f"📝 *Введите номер маркера* (только цифры)\n\n"
            f"Доступные номера: {examples}\n\n"
            f"Пример: введите `1` для маркера {brand} 1\n\n"
            f"*Или* просто напишите номер в чат.",
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )

    elif query.data.startswith("show_markers_"):
        # Показываем все маркеры выбранного бренда
        brand = query.data.replace("show_markers_", "")
        brand_data = MARKERS_DB.get(brand, {})
        prefix = brand_data.get("prefix", "")
        markers = brand_data.get("markers", {})

        if markers:
            text = f"📋 *Все маркеры {brand}:*\n\n"
            for number, marker_data in sorted(markers.items(), key=lambda x: int(x[0]) if x[0].isdigit() else 0):
                full_id = f"{prefix}-{number.zfill(3)}"
                text += f"• {full_id} — {marker_data['name'][:30]}...\n"

            keyboard = [
                [InlineKeyboardButton("🔍 Найти по номеру", callback_data=f"brand_{brand}")],
                [InlineKeyboardButton("⬅️ Назад к брендам", callback_data="select_brand")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(text, reply_markup=reply_markup, parse_mode="Markdown")
        else:
            await query.edit_message_text(f"❌ В бренде {brand} пока нет маркеров.")

    elif query.data == "search_by_full_id":
        user_states[user_id] = {"brand": None, "waiting_for_number": False}
        await query.edit_message_text(
            "🔍 *Введите полный номер маркера*\n\n"
            "Примеры: G-001, L-100, G-012\n\n"
            "Я покажу все доступные аналоги.",
            parse_mode="Markdown"
        )

    elif query.data == "help":
        help_text = (
            "📖 *Справка*\n\n"
            "🔹 *Поиск по бренду (рекомендуется):*\n"
            "1. Выберите бренд в меню\n"
            "2. Введите номер маркера (только цифры)\n"
            "   Например: 1, 2, 12, 13\n\n"
            "🔹 *Поиск по полному номеру:*\n"
            "Просто введите номер с префиксом\n"
            "Примеры: G-001, L-100, G-012\n\n"
            "🔹 *Доступные бренды:*\n"
            f"{', '.join(MARKERS_DB.keys())}\n\n"
            "💡 *Совет:* Для быстрого поиска выберите бренд, затем введите только номер."
        )

        keyboard = [[InlineKeyboardButton("⬅️ Назад", callback_data="back_to_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(help_text, reply_markup=reply_markup, parse_mode="Markdown")

    elif query.data == "back_to_menu":
        user_states[user_id] = {"brand": None, "waiting_for_number": False}
        keyboard = [
            [InlineKeyboardButton("🏷️ Выбрать бренд", callback_data="select_brand")],
            [InlineKeyboardButton("🔍 Поиск по полному номеру", callback_data="search_by_full_id")],
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
    """Обработка текстовых сообщений"""
    user_id = update.effective_user.id
    user_input = update.message.text.strip()

    # Проверяем, ждет ли пользователь ввод номера после выбора бренда
    if user_id in user_states and user_states[user_id].get("waiting_for_number") and user_states[user_id].get("brand"):
        brand = user_states[user_id]["brand"]
        number = user_input

        # Ищем маркер по бренду и номеру
        marker_data = find_marker_by_brand_and_number(brand, number)

        if marker_data:
            response = format_analogs(marker_data)
            keyboard = [
                [InlineKeyboardButton("🔍 Найти другой", callback_data=f"brand_{brand}")],
                [InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_menu")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply_text(response, reply_markup=reply_markup, parse_mode="Markdown")
        else:
            # Проверяем доступные номера
            available = get_available_numbers(brand)

            keyboard = [
                [InlineKeyboardButton(f"🔍 Попробовать снова", callback_data=f"brand_{brand}")],
                [InlineKeyboardButton("📋 Показать все маркеры", callback_data=f"show_markers_{brand}")],
                [InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_menu")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply_text(
                f"❌ *Маркер {brand} {number} не найден*\n\n"
                f"Доступные номера для {brand}:\n"
                f"{', '.join(available)}\n\n"
                f"Пожалуйста, введите один из этих номеров.",
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
        return

    # Если не ждет ввода - пробуем найти по полному номеру
    marker_data = find_marker_by_full_id(user_input)

    if marker_data:
        response = format_analogs(marker_data)

        keyboard = [
            [InlineKeyboardButton("🔍 Новый поиск", callback_data="search_by_full_id")],
            [InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(response, reply_markup=reply_markup, parse_mode="Markdown")
    else:
        # Пробуем найти среди всех брендов по номеру без префикса
        found = False
        for brand in MARKERS_DB.keys():
            marker_data = find_marker_by_brand_and_number(brand, user_input)
            if marker_data:
                response = format_analogs(marker_data)
                keyboard = [
                    [InlineKeyboardButton("🔍 Новый поиск", callback_data="search_by_full_id")],
                    [InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_menu")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await update.message.reply_text(response, reply_markup=reply_markup, parse_mode="Markdown")
                found = True
                break

        if not found:
            keyboard = [
                [InlineKeyboardButton("🏷️ Выбрать бренд", callback_data="select_brand")],
                [InlineKeyboardButton("🏠 Главное меню", callback_data="back_to_menu")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply_text(
                f"❌ *Маркер '{user_input}' не найден*\n\n"
                "Проверьте правильность ввода.\n"
                "Примеры полных номеров: G-001, L-100\n"
                "Или выберите бренд из меню.",
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