import logging
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
import json
import os
from datetime import datetime
import pickle
import threading
import time
import base64
import sys
import io

# ======================== КОНФИГУРАЦИЯ ========================
ADMIN_IDS = [8095346561, 8163619171]
# Токен берется из переменных окружения (обязательно добавьте на Render!)
TOKEN = os.environ.get('TOKEN')
if not TOKEN:
    # На случай локального тестирования, но для Render ТОЧНО нужно добавить в переменные окружения
    TOKEN = "7989661243:AAFZpemxdz9Hy1WEUhW5_p6-lbAHWDj22T8"
    print("⚠️ ВНИМАНИЕ: Токен взят из кода. Для продакшена на Render добавьте TOKEN в Environment Variables!")

DATA_FILE = 'bot_data.pickle'
BACKUP_INTERVAL = 60
ADMIN_PASSWORD = "1478963"

# ======================== НАСТРОЙКА ЛОГОВ ========================
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ======================== СТРУКТУРЫ ДАННЫХ ========================
users_db = {}
orders_db = []
pending_carts = {}

# ======================== СИСТЕМА СОХРАНЕНИЯ ========================
def save_data():
    try:
        data = {
            'users_db': users_db,
            'orders_db': orders_db,
            'last_save': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        with open(DATA_FILE, 'wb') as f:
            pickle.dump(data, f)
        logger.info(f"✅ Данные сохранены. Пользователей: {len(users_db)}, Заказов: {len(orders_db)}")
        return True
    except Exception as e:
        logger.error(f"❌ Ошибка сохранения данных: {e}")
        return False

def load_data():
    global users_db, orders_db
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'rb') as f:
                data = pickle.load(f)
                users_db = data.get('users_db', {})
                orders_db = data.get('orders_db', [])
            logger.info(f"✅ Данные загружены. Пользователей: {len(users_db)}, Заказов: {len(orders_db)}")
        else:
            logger.info("ℹ️ Файл данных не найден, создаем новые структуры")
            save_data()
    except Exception as e:
        logger.error(f"❌ Ошибка загрузки данных: {e}")

def auto_save():
    while True:
        time.sleep(BACKUP_INTERVAL)
        save_data()

save_thread = threading.Thread(target=auto_save, daemon=True)
save_thread.start()

# ======================== ДЕКОДИРОВАНИЕ КОРЗИНЫ ========================
def decode_cart_data(encoded_data):
    """Декодирует данные корзины из параметра start"""
    try:
        logger.info(f"🔧 Декодирование данных корзины...")
        if encoded_data.startswith('cart_'):
            encoded_data = encoded_data[5:]
        
        decoded_bytes = base64.b64decode(encoded_data)
        decoded_str = decoded_bytes.decode('utf-8')
        cart_data = json.loads(decoded_str)
        logger.info(f"✅ Корзина декодирована: {len(cart_data.get('items', []))} товаров")
        return cart_data
    except Exception as e:
        logger.error(f"❌ Ошибка декодирования корзины: {e}")
        return None

# ======================== ВСПОМОГАТЕЛЬНАЯ ФУНКЦИЯ ДЛЯ АДМИНКИ ========================
async def show_admin_menu(message):
    """Показывает главное меню админ-панели"""
    keyboard = [
        [InlineKeyboardButton("📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton("👥 Пользователи", callback_data="admin_users")],
        [InlineKeyboardButton("🛒 Заказы", callback_data="admin_orders")],
        [InlineKeyboardButton("💾 Сохранить", callback_data="admin_save")]
    ]
    await message.reply_text(
        "🔐 АДМИН-ПАНЕЛЬ\n\nВыберите действие:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

# ======================== ОБРАБОТЧИКИ КОМАНД ========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start"""
    user = update.effective_user
    user_id = user.id
    
    # Сохраняем пользователя
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if user_id not in users_db:
        users_db[user_id] = {
            "first_name": user.first_name,
            "username": user.username,
            "first_seen": now,
            "last_active": now,
            "orders_count": 0
        }
    else:
        users_db[user_id]["last_active"] = now
        users_db[user_id]["first_name"] = user.first_name
        users_db[user_id]["username"] = user.username
    
    # Проверяем, есть ли данные корзины
    args = context.args
    if args and len(args) > 0:
        cart_data = decode_cart_data(args[0])
        if cart_data:
            pending_carts[user_id] = cart_data
            
            items_text = "\n".join([
                f"• {item['name']} x{item['quantity']} - {item['price'] * item['quantity']} руб"
                for item in cart_data['items']
            ])
            
            await update.message.reply_text(
                f"🛒 <b>Корзина с сайта</b>\n\n"
                f"{items_text}\n\n"
                f"💰 <b>Итого: {cart_data['total']} руб</b>\n\n"
                f"📦 Выберите способ получения:",
                parse_mode='HTML',
                reply_markup=InlineKeyboardMarkup([
                    [InlineKeyboardButton("🚶 Самовывоз (ЖК Дубровка)", callback_data="delivery_pickup")],
                    [InlineKeyboardButton("🚚 Доставка курьером", callback_data="delivery_courier")]
                ])
            )
            return
    
    # Обычный start без корзины
    keyboard = [[KeyboardButton("🔐 Админ-панель")]]
    await update.message.reply_text(
        "Добро пожаловать в магазин игрушек ЖК Дубровка!\n\n"
        "🛍 Для заказа посетите наш сайт:\n"
        "https://telegram-shop-bot.onrender.com",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /admin или кнопки 'Админ-панель'"""
    user = update.effective_user
    
    if user.id in ADMIN_IDS:
        await show_admin_menu(update.message)
    else:
        context.user_data['awaiting_admin_password'] = True
        await update.message.reply_text("🔐 Введите пароль для доступа к админ-панели:")

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик нажатий на инлайн-кнопки"""
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    user_id = user.id
    
    if query.data == "delivery_pickup":
        await process_order(query, context, "pickup", None)
    
    elif query.data == "delivery_courier":
        await query.edit_message_text(
            "🚚 <b>Доставка курьером</b>\n\n"
            "Пожалуйста, напишите ваш адрес доставки.\n\n"
            "Например: ул. Ленина, д. 10, кв. 5",
            parse_mode='HTML'
        )
        context.user_data['awaiting_address'] = True
    
    elif query.data == "confirm_delivery":
        if 'temp_address' in context.user_data:
            await process_order(query, context, "delivery", context.user_data['temp_address'])
            context.user_data.pop('temp_address', None)

async def process_order(query, context, delivery_type, address):
    """Обработка заказа"""
    user = query.from_user
    user_id = user.id
    
    if user_id not in pending_carts:
        await query.edit_message_text("❌ Корзина не найдена. Пожалуйста, вернитесь на сайт и попробуйте снова.")
        return
    
    cart_data = pending_carts.pop(user_id)
    
    order = {
        "user_id": user_id,
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "delivery_type": "Самовывоз" if delivery_type == "pickup" else "Доставка",
        "address": address,
        "items": cart_data['items'],
        "total": cart_data['total']
    }
    
    orders_db.append(order)
    if user_id in users_db:
        users_db[user_id]["orders_count"] += 1
    save_data()
    
    # Уведомление админам
    admin_text = f"🛒 НОВЫЙ ЗАКАЗ!\n\n"
    admin_text += f"👤 Покупатель: {users_db.get(user_id, {}).get('first_name', 'Неизвестно')} (@{users_db.get(user_id, {}).get('username', 'нет')})\n"
    if address:
        admin_text += f"📍 Адрес: {address}\n"
    admin_text += f"\n📦 Товары:\n"
    for item in order['items']:
        admin_text += f"• {item['name']} x{item['quantity']} - {item['price'] * item['quantity']} руб\n"
    admin_text += f"\n💰 Итого: {order['total']} руб"
    
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(admin_id, admin_text)
        except Exception as e:
            logger.error(f"Не удалось отправить уведомление админу {admin_id}: {e}")
    
    # Ответ пользователю
    user_text = "✅ Заказ оформлен!\n\n"
    if delivery_type == "pickup":
        user_text += "Самовывоз: ЖК Дубровка, Ясеневая улица, 1к1\n"
    else:
        user_text += f"Адрес доставки: {address}\n"
    user_text += "\n📞 Ожидайте сообщения от администратора.\n💵 Оплата наличными."
    
    await query.edit_message_text(
        user_text,
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🛍 На сайт", url="https://telegram-shop-bot.onrender.com")]
        ])
    )

# ======================== АДМИН-ПАНЕЛЬ (callback) ========================
async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопок админ-панели"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data == "admin_stats":
        total_users = len(users_db)
        total_orders = len(orders_db)
        total_sum = sum(o['total'] for o in orders_db)
        text = (f"📊 Статистика\n\n"
                f"👥 Пользователей: {total_users}\n"
                f"🛒 Заказов: {total_orders}\n"
                f"💰 Сумма заказов: {total_sum} руб")
        await query.edit_message_text(text)
    
    elif data == "admin_users":
        if not users_db:
            await query.edit_message_text("👥 Пользователей пока нет")
            return
        text = "👥 Последние пользователи:\n"
        for uid, info in list(users_db.items())[-5:]:
            text += f"\n• {info['first_name']} (@{info['username']}) - заказов: {info['orders_count']}"
        await query.edit_message_text(text)
    
    elif data == "admin_orders":
        if not orders_db:
            await query.edit_message_text("🛒 Заказов нет")
            return
        text = "🛒 Последние заказы:\n"
        for order in orders_db[-5:]:
            text += f"\n• {order['date'][:10]} - {order['total']} руб - {order['delivery_type']}"
        await query.edit_message_text(text)
    
    elif data == "admin_save":
        if save_data():
            await query.edit_message_text("✅ Данные сохранены")
        else:
            await query.edit_message_text("❌ Ошибка при сохранении")

# ======================== ОБРАБОТКА ТЕКСТОВЫХ СООБЩЕНИЙ ========================
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик текстовых сообщений (не команд)"""
    user = update.effective_user
    text = update.message.text
    
    # Проверка пароля для админ-панели
    if context.user_data.get('awaiting_admin_password'):
        if text == ADMIN_PASSWORD:
            context.user_data['admin_authenticated'] = True
            context.user_data['awaiting_admin_password'] = False
            await show_admin_menu(update.message)
        else:
            await update.message.reply_text("❌ Неверный пароль.")
        return
    
    # Ожидание адреса для доставки
    if context.user_data.get('awaiting_address'):
        context.user_data['temp_address'] = text
        context.user_data['awaiting_address'] = False
        
        await update.message.reply_text(
            f"📍 Подтверждение адреса:\n\n{text}\n\nВсё верно?",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("✅ Да, оформить заказ", callback_data="confirm_delivery")],
                [InlineKeyboardButton("🔄 Ввести заново", callback_data="delivery_courier")]
            ])
        )
        return
    
    # Кнопка админ-панели (если не в режиме ожидания)
    if text == "🔐 Админ-панель":
        await admin_panel(update, context)
        return
    
    # Любое другое сообщение
    await update.message.reply_text(
        "Я вас не понимаю. Используйте кнопки меню или команду /start"
    )

# ======================== ЗАПУСК ========================
if __name__ == "__main__":
    # Загружаем данные
    load_data()
    
    # Создаем приложение
    app = Application.builder().token(TOKEN).build()
    
    # Добавляем обработчики
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CallbackQueryHandler(button_callback, pattern="^(delivery_.*|confirm_delivery)$"))
    app.add_handler(CallbackQueryHandler(admin_callback, pattern="^admin_.*"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    # Настройка для Render
    PORT = int(os.environ.get('PORT', 10000))
    
    logger.info(f"🚀 Запуск бота в режиме POLLING на порту {PORT}")
    
    # СОЗДАЕМ EVENT LOOP
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    # Запускаем бота в режиме polling (вместо webhook)
    print("✅ Бот запущен и готов к работе!")
    print("📱 Откройте Telegram и отправьте /start")
    
    # Используем run_polling вместо run_webhook
    app.run_polling()
