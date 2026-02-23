import logging
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
import requests
import json
import os
import asyncio
from datetime import datetime
from collections import defaultdict
import pickle
import threading
import time

# ======================== КОНФИГУРАЦИЯ ========================
ADMIN_IDS = [8095346561]  # Список админов (ваш ID)
USER_ID = 8095346561      # Ваш ID (админ)
TOKEN = "7989661243:AAFZpemxdz9Hy1WEUhW5_p6-lbAHWDj22T8"
DATA_FILE = 'bot_data.pickle'
BACKUP_INTERVAL = 60

# Пароль для доступа к админ-панели
ADMIN_PASSWORD = "1478963"

# ======================== СТРУКТУРЫ ДАННЫХ ========================
carts = {}                # Корзины пользователей
users_db = {}             # База данных пользователей
orders_db = []            # История заказов

# ======================== ЛОГИРОВАНИЕ ========================
import sys
import io

if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

file_handler = logging.FileHandler('bot.log', encoding='utf-8')
file_handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))

class ConsoleHandler(logging.StreamHandler):
    def emit(self, record):
        try:
            msg = self.format(record)
            if sys.platform == 'win32':
                msg = msg.replace('✅', '[OK]')
                msg = msg.replace('❌', '[ERROR]')
                msg = msg.replace('📅', '[DATE]')
                msg = msg.replace('🔍', '[SEARCH]')
                msg = msg.replace('🚀', '[START]')
                msg = msg.replace('ℹ️', '[INFO]')
                msg = msg.replace('💾', '[SAVE]')
                msg = msg.replace('📊', '[STATS]')
                msg = msg.replace('👥', '[USERS]')
                msg = msg.replace('🛒', '[CART]')
                msg = msg.replace('📦', '[BOX]')
                msg = msg.replace('📢', '[BROADCAST]')
                msg = msg.replace('⚙️', '[SETTINGS]')
                msg = msg.replace('🔐', '[LOCK]')
                msg = msg.replace('⛔', '[STOP]')
                msg = msg.replace('📝', '[NOTE]')
                msg = msg.replace('💰', '[MONEY]')
                msg = msg.replace('👇', '[DOWN]')
                msg = msg.replace('🆔', '[ID]')
                msg = msg.replace('🧸', '[TOY]')
                msg = msg.replace('🎲', '[DICE]')
                msg = msg.replace('🛠', '[TOOLS]')
                msg = msg.replace('📞', '[PHONE]')
                msg = msg.replace('🚶', '[WALK]')
                msg = msg.replace('🚚', '[TRUCK]')
                msg = msg.replace('🗑', '[TRASH]')
                msg = msg.replace('✉️', '[MAIL]')
            stream = self.stream
            stream.write(msg + self.terminator)
            self.flush()
        except Exception:
            self.handleError(record)

console_handler = ConsoleHandler()
console_handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))

logging.basicConfig(
    level=logging.INFO,
    handlers=[file_handler, console_handler]
)

logger = logging.getLogger(__name__)

# ======================== СИСТЕМА СОХРАНЕНИЯ ДАННЫХ ========================
def save_data():
    try:
        data = {
            'carts': carts,
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
    global carts, users_db, orders_db
    try:
        if os.path.exists(DATA_FILE):
            with open(DATA_FILE, 'rb') as f:
                data = pickle.load(f)
                carts = data.get('carts', {})
                users_db = data.get('users_db', {})
                orders_db = data.get('orders_db', [])
                last_save = data.get('last_save', 'неизвестно')
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

# ======================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ========================
def send_message(text):
    try:
        url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
        params = {
            "chat_id": USER_ID,
            "text": text,
            "parse_mode": "HTML"
        }
        requests.get(url, params=params)
    except Exception as e:
        logger.error(f"Ошибка отправки сообщения админу: {e}")

def update_user_info(user):
    user_id = user.id
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    if user_id not in users_db:
        users_db[user_id] = {
            "first_name": user.first_name,
            "username": user.username,
            "first_seen": now,
            "last_active": now,
            "orders_count": 0
        }
        save_data()
    else:
        users_db[user_id]["last_active"] = now
        users_db[user_id]["first_name"] = user.first_name
        users_db[user_id]["username"] = user.username

def read_info_plush():
    try:
        with open('info_about_toys_plush.json', 'r', encoding='utf-8') as f:
            content = json.load(f) 
        return content
    except FileNotFoundError:
        return {"toysp": []}
    except json.JSONDecodeError as e:
        logger.error(f"Ошибка в JSON файле плюшевых игрушек: {e}")
        return {"toysp": []}

def read_info_simple():
    try:
        with open('info_about_toys_simple.json', 'r', encoding='utf-8') as f:
            content = json.load(f)
        return content
    except FileNotFoundError:
        return {"toysp": []}
    except json.JSONDecodeError as e:
        logger.error(f"Ошибка в JSON файле обычных игрушек: {e}")
        return {"toysp": []}

def find_photo_file(filename):
    current_dir = os.path.dirname(os.path.abspath(__file__))
    
    if os.path.exists(filename):
        return filename
    
    full_path = os.path.join(current_dir, filename)
    if os.path.exists(full_path):
        return full_path
    
    plush_path = os.path.join(current_dir, "toys_plush", filename)
    if os.path.exists(plush_path):
        return plush_path
    
    simple_path = os.path.join(current_dir, "toys_simple", filename)
    if os.path.exists(simple_path):
        return simple_path
    
    filename_lower = filename.lower()
    for root, dirs, files in os.walk(current_dir):
        for file in files:
            if filename_lower in file.lower():
                return os.path.join(root, file)
    
    return None

# ======================== АДМИН ПАНЕЛЬ ========================
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    # Если пользователь в списке ADMIN_IDS - пускаем сразу
    if user.id in ADMIN_IDS:
        keyboard = [
            [InlineKeyboardButton("📊 Статистика", callback_data="admin_stats")],
            [InlineKeyboardButton("👥 Пользователи", callback_data="admin_users")],
            [InlineKeyboardButton("🛒 Заказы", callback_data="admin_orders")],
            [InlineKeyboardButton("📦 Товары", callback_data="admin_products")],
            [InlineKeyboardButton("📢 Рассылка", callback_data="admin_broadcast")],
            [InlineKeyboardButton("⚙️ Настройки", callback_data="admin_settings")],
            [InlineKeyboardButton("💾 Сохранить данные", callback_data="admin_save")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "🔐 <b>Админ-панель</b>\n\nВыберите раздел для управления:",
            parse_mode='HTML',
            reply_markup=reply_markup
        )
    else:
        # Если не админ - запрашиваем пароль
        context.user_data['awaiting_admin_password'] = True
        await update.message.reply_text(
            "🔐 Введите пароль для доступа к админ-панели:",
            reply_markup=ReplyKeyboardMarkup([["/cancel"]], resize_keyboard=True, one_time_keyboard=True)
        )

async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    user = query.from_user
    
    # Проверяем доступ: либо ID в списке админов, либо авторизован по паролю
    if not (user.id in ADMIN_IDS or context.user_data.get('admin_authenticated')):
        await query.edit_message_text("⛔ Доступ запрещен. Введите /admin для авторизации.")
        return
    
    data = query.data
    print(f"Нажата кнопка: {data}")  # Для отладки
    
    if data == "admin_stats":
        await show_admin_stats(query, context)
    elif data == "admin_users":
        await show_admin_users(query, context)
    elif data == "admin_orders":
        await show_admin_orders(query, context)
    elif data == "admin_products":
        await show_admin_products(query, context)
    elif data == "admin_broadcast":
        await start_broadcast(query, context)
    elif data == "admin_settings":
        await show_admin_settings(query, context)
    elif data == "admin_save":
        if save_data():
            await query.edit_message_text("✅ Данные успешно сохранены")
        else:
            await query.edit_message_text("❌ Ошибка при сохранении")
    elif data.startswith("user_"):
        user_id = int(data.split("_")[1])
        await show_user_details(query, context, user_id)
    elif data.startswith("order_"):
        order_index = int(data.split("_")[1])
        await show_order_details(query, context, order_index)
    elif data.startswith("delete_order_"):
        order_index = int(data.split("_")[2])
        await delete_order(query, context, order_index)
    elif data == "admin_back":
        keyboard = [
            [InlineKeyboardButton("📊 Статистика", callback_data="admin_stats")],
            [InlineKeyboardButton("👥 Пользователи", callback_data="admin_users")],
            [InlineKeyboardButton("🛒 Заказы", callback_data="admin_orders")],
            [InlineKeyboardButton("📦 Товары", callback_data="admin_products")],
            [InlineKeyboardButton("📢 Рассылка", callback_data="admin_broadcast")],
            [InlineKeyboardButton("⚙️ Настройки", callback_data="admin_settings")],
            [InlineKeyboardButton("💾 Сохранить данные", callback_data="admin_save")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "🔐 <b>Админ-панель</b>\n\nВыберите раздел для управления:",
            parse_mode='HTML',
            reply_markup=reply_markup
        )

async def show_admin_stats(query, context):
    total_users = len(users_db)
    active_today = sum(1 for u in users_db.values() if u["last_active"].startswith(datetime.now().strftime("%Y-%m-%d")))
    total_orders = len(orders_db)
    
    carts_count = sum(1 for cart in carts.values() if cart["items"])
    items_in_carts = sum(len(cart["items"]) for cart in carts.values())
    
    plush_data = read_info_plush()
    simple_data = read_info_simple()
    plush_count = len(plush_data.get("toysp", []))
    simple_count = len(simple_data.get("toysp", []))
    
    stats_text = (
        "📊 <b>СТАТИСТИКА БОТА</b>\n\n"
        f"👥 <b>Пользователи:</b>\n"
        f"• Всего: {total_users}\n"
        f"• Активных сегодня: {active_today}\n"
        f"• С корзинами: {carts_count}\n\n"
        f"🛒 <b>Заказы:</b>\n"
        f"• Всего заказов: {total_orders}\n"
        f"• Товаров в корзинах: {items_in_carts}\n\n"
        f"📦 <b>Товары:</b>\n"
        f"• Плюшевых игрушек: {plush_count}\n"
        f"• Обычных игрушек: {simple_count}\n"
        f"• Всего позиций: {plush_count + simple_count}\n\n"
        f"💾 <b>Последнее сохранение:</b> {datetime.now().strftime('%H:%M:%S')}"
    )
    
    keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="admin_back")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(stats_text, parse_mode='HTML', reply_markup=reply_markup)

async def show_admin_users(query, context):
    if not users_db:
        await query.edit_message_text(
            "👥 Пользователи пока отсутствуют",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="admin_back")]])
        )
        return
    
    sorted_users = sorted(users_db.items(), key=lambda x: x[1]["last_active"], reverse=True)
    
    users_text = "👥 <b>ПОЛЬЗОВАТЕЛИ</b>\n\n"
    
    for i, (user_id, info) in enumerate(sorted_users[:10], 1):
        username = f"@{info['username']}" if info['username'] else "нет username"
        users_text += f"{i}. <b>{info['first_name']}</b>\n"
        users_text += f"   ID: <code>{user_id}</code>\n"
        users_text += f"   Username: {username}\n"
        users_text += f"   Заказов: {info['orders_count']}\n"
        users_text += f"   Был: {info['last_active']}\n\n"
    
    if len(sorted_users) > 10:
        users_text += f"<i>... и еще {len(sorted_users) - 10} пользователей</i>\n\n"
    
    keyboard = []
    for user_id, info in sorted_users[:5]:
        btn_text = f"👤 {info['first_name'][:10]}"
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"user_{user_id}")])
    
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="admin_back")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(users_text, parse_mode='HTML', reply_markup=reply_markup)

async def show_user_details(query, context, user_id):
    if user_id not in users_db:
        await query.edit_message_text(
            "❌ Пользователь не найден",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="admin_users")]])
        )
        return
    
    info = users_db[user_id]
    username = f"@{info['username']}" if info['username'] else "не установлен"
    
    user_cart = carts.get(user_id, {"items": {}})
    cart_items = len(user_cart["items"])
    
    user_orders = [o for o in orders_db if o["user_id"] == user_id]
    
    details_text = (
        f"👤 <b>ДЕТАЛИ ПОЛЬЗОВАТЕЛЯ</b>\n\n"
        f"<b>ID:</b> <code>{user_id}</code>\n"
        f"<b>Имя:</b> {info['first_name']}\n"
        f"<b>Username:</b> {username}\n"
        f"<b>Впервые:</b> {info['first_seen']}\n"
        f"<b>Последний раз:</b> {info['last_active']}\n\n"
        f"<b>Заказов:</b> {info['orders_count']}\n"
        f"<b>Товаров в корзине:</b> {cart_items}\n"
    )
    
    if user_orders:
        details_text += f"\n<b>Последний заказ:</b>\n"
        last_order = user_orders[-1]
        details_text += f"• {last_order['date']}\n"
        details_text += f"• Сумма: {last_order['total']} руб\n"
    
    keyboard = [
        [InlineKeyboardButton("📱 Написать пользователю", callback_data=f"reply_{user_id}")],
        [InlineKeyboardButton("◀️ Назад к списку", callback_data="admin_users")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(details_text, parse_mode='HTML', reply_markup=reply_markup)

async def show_admin_orders(query, context):
    if not orders_db:
        await query.edit_message_text(
            "🛒 Заказов пока нет",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="admin_back")]])
        )
        return
    
    # Показываем последние 10 заказов
    recent_orders = orders_db[-10:]
    recent_orders.reverse()
    
    orders_text = "🛒 <b>ПОСЛЕДНИЕ ЗАКАЗЫ</b>\n\n"
    
    # Создаем список кнопок для каждого заказа
    keyboard = []
    
    for i, order in enumerate(recent_orders, 1):
        user_info = users_db.get(order["user_id"], {})
        user_name = user_info.get("first_name", "Неизвестно")
        order_num = len(orders_db) - recent_orders.index(order)
        
        orders_text += f"{i}. <b>{user_name}</b>\n"
        orders_text += f"   Дата: {order['date']}\n"
        orders_text += f"   Сумма: {order['total']} руб\n"
        orders_text += f"   Способ: {order['delivery_type']}\n\n"
        
        # Добавляем кнопку для этого заказа
        order_index = orders_db.index(order)
        keyboard.append([InlineKeyboardButton(f"📦 Заказ #{order_num}", callback_data=f"order_{order_index}")])
    
    keyboard.append([InlineKeyboardButton("◀️ Назад", callback_data="admin_back")])
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(orders_text, parse_mode='HTML', reply_markup=reply_markup)

async def show_order_details(query, context, order_index):
    print(f"Показываем детали заказа {order_index}")  # Для отладки
    
    if order_index >= len(orders_db):
        await query.edit_message_text(
            "❌ Заказ не найден",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад", callback_data="admin_orders")]])
        )
        return
    
    order = orders_db[order_index]
    user_info = users_db.get(order["user_id"], {})
    
    details_text = (
        f"📦 <b>ДЕТАЛИ ЗАКАЗА #{order_index + 1}</b>\n\n"
        f"<b>Дата:</b> {order['date']}\n"
        f"<b>Покупатель:</b> {user_info.get('first_name', 'Неизвестно')}\n"
        f"<b>ID:</b> <code>{order['user_id']}</code>\n"
        f"<b>Способ:</b> {order['delivery_type']}\n"
    )
    
    details_text += f"\n<b>Товары:</b>\n"
    
    for item in order['items']:
        details_text += f"• {item['name']} x{item['quantity']} - {item['total']} руб\n"
    
    details_text += f"\n💰 <b>ИТОГО: {order['total']} рублей</b>"
    
    keyboard = [
        [InlineKeyboardButton("❌ Удалить заказ", callback_data=f"delete_order_{order_index}")],
        [InlineKeyboardButton("◀️ Назад к заказам", callback_data="admin_orders")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(details_text, parse_mode='HTML', reply_markup=reply_markup)

async def delete_order(query, context, order_index):
    print(f"Пытаемся удалить заказ {order_index}")  # Для отладки
    
    if order_index < len(orders_db):
        # Удаляем заказ
        deleted_order = orders_db.pop(order_index)
        save_data()
        
        await query.edit_message_text(
            f"✅ Заказ успешно удален!\n\n"
            f"Удален заказ от {deleted_order['date']} на сумму {deleted_order['total']} руб",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Назад к заказам", callback_data="admin_orders")]])
        )
    else:
        await query.edit_message_text("❌ Ошибка: заказ не найден")

async def show_admin_products(query, context):
    plush_data = read_info_plush()
    simple_data = read_info_simple()
    
    plush_toys = plush_data.get("toysp", [])
    simple_toys = simple_data.get("toysp", [])
    
    products_text = (
        "📦 <b>УПРАВЛЕНИЕ ТОВАРАМИ</b>\n\n"
        f"🧸 <b>Плюшевые игрушки:</b> {len(plush_toys)} шт.\n"
        f"🎲 <b>Обычные игрушки:</b> {len(simple_toys)} шт.\n"
        f"📊 <b>Всего:</b> {len(plush_toys) + len(simple_toys)} шт.\n\n"
    )
    
    keyboard = [
        [InlineKeyboardButton("🔄 Обновить каталог", callback_data="admin_refresh_products")],
        [InlineKeyboardButton("📸 Проверить фото", callback_data="admin_check_photos")],
        [InlineKeyboardButton("◀️ Назад", callback_data="admin_back")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(products_text, parse_mode='HTML', reply_markup=reply_markup)

async def start_broadcast(query, context):
    context.user_data['broadcast_mode'] = True
    
    await query.edit_message_text(
        "📢 <b>РЕЖИМ РАССЫЛКИ</b>\n\n"
        "Введите сообщение для рассылки всем пользователям.\n"
        "Поддерживается HTML-разметка.\n\n"
        "Для отмены введите /cancel",
        parse_mode='HTML'
    )

async def show_admin_settings(query, context):
    settings_text = (
        "⚙️ <b>НАСТРОЙКИ БОТА</b>\n\n"
        f"👤 <b>Администраторы:</b>\n"
    )
    
    for admin_id in ADMIN_IDS:
        admin_info = users_db.get(admin_id, {})
        admin_name = admin_info.get('first_name', 'Неизвестно')
        settings_text += f"• {admin_name} (ID: <code>{admin_id}</code>)\n"
    
    settings_text += f"\n📊 <b>Системная информация:</b>\n"
    settings_text += f"• Бот запущен: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
    settings_text += f"• Всего пользователей: {len(users_db)}\n"
    settings_text += f"• Всего заказов: {len(orders_db)}\n"
    
    keyboard = [[InlineKeyboardButton("◀️ Назад", callback_data="admin_back")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await query.edit_message_text(settings_text, parse_mode='HTML', reply_markup=reply_markup)

# ======================== КОМАНДА ДЛЯ ОТВЕТА ПОЛЬЗОВАТЕЛЮ ========================
async def reply_to_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    
    if user.id not in ADMIN_IDS:
        await update.message.reply_text("⛔ У вас нет прав для этой команды")
        return
    
    try:
        args = context.args
        if len(args) < 2:
            await update.message.reply_text(
                "❌ Использование: /send user_id текст сообщения\n"
                "Пример: /send 123456789 Привет, ваш заказ готов!"
            )
            return
        
        target_id = int(args[0])
        message_text = ' '.join(args[1:])
        
        await context.bot.send_message(
            chat_id=target_id,
            text=f"✉️ <b>Сообщение от администратора</b>\n\n{message_text}",
            parse_mode='HTML'
        )
        
        await update.message.reply_text(f"✅ Сообщение отправлено пользователю {target_id}")
        
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}")

# ======================== ДОПОЛНИТЕЛЬНЫЕ КОМАНДЫ ========================
async def save_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id in ADMIN_IDS:
        if save_data():
            await update.message.reply_text("✅ Данные успешно сохранены")
        else:
            await update.message.reply_text("❌ Ошибка при сохранении данных")
    else:
        await update.message.reply_text("⛔ У вас нет прав для этой команды")

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if user.id in ADMIN_IDS:
        stats = (
            f"📊 <b>Статистика бота</b>\n\n"
            f"👥 Пользователей: {len(users_db)}\n"
            f"🛒 Заказов: {len(orders_db)}\n"
            f"🛍 Активных корзин: {sum(1 for cart in carts.values() if cart['items'])}\n"
            f"💾 Последнее сохранение: {datetime.now().strftime('%H:%M:%S')}"
        )
        await update.message.reply_text(stats, parse_mode='HTML')
    else:
        await update.message.reply_text("⛔ У вас нет прав для этой команды")

# ======================== ОСНОВНЫЕ ФУНКЦИИ БОТА ========================
async def send_toy(update: Update, toy_info: dict, toy_key: str, category: str):
    name = toy_info.get('name', 'Игрушка')
    price = toy_info.get('price', 'Цена не указана')
    about = toy_info.get('about', '')
    img_data = toy_info.get('img', [])
    
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🛒 Добавить в корзину", callback_data=f"add_{category}_{toy_key}")]
    ])
    
    caption = f"🆔 <b>{name}</b>\n\n"
    caption += f"💰 <b>Цена:</b> {price}\n"
    
    if about:
        caption += f"📝 {about}\n"
    
    if isinstance(img_data, str):
        img_paths = [img_data]
    elif isinstance(img_data, list):
        img_paths = img_data
    else:
        img_paths = []
    
    if img_paths:
        try:
            existing_files = []
            for img_path in img_paths:
                found_path = find_photo_file(img_path.strip())
                if found_path:
                    existing_files.append(found_path)
            
            if existing_files:
                if len(existing_files) > 1:
                    media_group = []
                    for i, file_path in enumerate(existing_files):
                        with open(file_path, 'rb') as photo:
                            if i == 0:
                                media_group.append(InputMediaPhoto(photo.read(), caption=caption, parse_mode='HTML'))
                            else:
                                media_group.append(InputMediaPhoto(photo.read()))
                    
                    if media_group:
                        await update.message.reply_media_group(media=media_group)
                        await update.message.reply_text("👇 Действия с товаром:", reply_markup=keyboard)
                else:
                    with open(existing_files[0], 'rb') as photo:
                        await update.message.reply_photo(
                            photo=photo,
                            caption=caption,
                            parse_mode='HTML',
                            reply_markup=keyboard
                        )
            else:
                await update.message.reply_text(caption, parse_mode='HTML', reply_markup=keyboard)
        except Exception as e:
            logger.error(f"Ошибка при отправке фото: {e}")
            await update.message.reply_text(caption, parse_mode='HTML', reply_markup=keyboard)
    else:
        await update.message.reply_text(caption, parse_mode='HTML', reply_markup=keyboard)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    callback_data = query.data
    user = query.from_user
    user_id = user.id
    
    update_user_info(user)
    
    if callback_data.startswith("add_"):
        parts = callback_data.split("_")
        category = parts[1]
        toy_key = parts[2]
        
        if category == "plush":
            data = read_info_plush()
        elif category == "simple":
            data = read_info_simple()
        else:
            return
        
        toy_info = None
        for toy_item in data.get("toysp", []):
            if toy_key in toy_item:
                toy_info = toy_item[toy_key]
                break
        
        if toy_info:
            name = toy_info.get('name', 'Игрушка')
            price = toy_info.get('price', 'Цена не указана')
            
            if user_id not in carts:
                carts[user_id] = {"items": {}}
            
            if toy_key in carts[user_id]["items"]:
                carts[user_id]["items"][toy_key]["quantity"] += 1
                await query.edit_message_text(
                    f"✅ Товар <b>{name}</b> добавлен в корзину!\n"
                    f"Количество: {carts[user_id]['items'][toy_key]['quantity']}",
                    parse_mode='HTML'
                )
            else:
                carts[user_id]["items"][toy_key] = {
                    "name": name,
                    "price": price,
                    "quantity": 1,
                    "category": category
                }
                await query.edit_message_text(
                    f"✅ Товар <b>{name}</b> добавлен в корзину!",
                    parse_mode='HTML'
                )
            save_data()
    
    elif callback_data == "view_cart":
        await show_cart(query, context)
    
    elif callback_data.startswith("remove_"):
        toy_key = callback_data.replace("remove_", "")
        
        if user_id in carts and toy_key in carts[user_id]["items"]:
            name = carts[user_id]["items"][toy_key]["name"]
            del carts[user_id]["items"][toy_key]
            await query.edit_message_text(
                f"✅ Товар <b>{name}</b> удален из корзины",
                parse_mode='HTML'
            )
            save_data()
    
    elif callback_data == "clear_cart":
        if user_id in carts:
            carts[user_id]["items"] = {}
        await query.edit_message_text("✅ Корзина очищена", parse_mode='HTML')
        save_data()
    
    elif callback_data == "checkout":
        await show_delivery_options(query, context)
    
    elif callback_data == "delivery_pickup":
        await process_order(query, context, "pickup")
    
    elif callback_data == "continue_shopping":
        await query.message.reply_text(
            "Выберите категорию товаров:",
            reply_markup=get_main_keyboard()
        )
        await query.message.delete()
    
    elif callback_data.startswith("info_"):
        parts = callback_data.split("_")
        category = parts[1]
        toy_key = parts[2]
        
        if category == "plush":
            data = read_info_plush()
        elif category == "simple":
            data = read_info_simple()
        else:
            return
        
        for toy_item in data.get("toysp", []):
            if toy_key in toy_item:
                toy_info = toy_item[toy_key]
                info_text = f"📋 <b>Подробная информация</b>\n\n"
                info_text += f"<b>{toy_info.get('name')}</b>\n"
                info_text += f"💰 Цена: {toy_info.get('price')}\n"
                info_text += f"📝 {toy_info.get('about', 'Нет описания')}\n"
                await query.message.reply_text(info_text, parse_mode='HTML')
                break

async def show_cart(query, context):
    user_id = query.from_user.id
    cart = carts.get(user_id, {"items": {}})
    
    if not cart["items"]:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🛍 Продолжить покупки", callback_data="continue_shopping")]
        ])
        await query.edit_message_text(
            "🛒 <b>Корзина пуста</b>\n\nДобавьте товары в корзину!",
            parse_mode='HTML',
            reply_markup=keyboard
        )
        return
    
    cart_text = "🛒 <b>Ваша корзина:</b>\n\n"
    total = 0
    
    for toy_key, item in cart["items"].items():
        price_str = item['price'].replace(' рублей', '').replace(' руб', '').strip()
        try:
            price = int(price_str)
        except:
            price = 0
        
        item_total = price * item['quantity']
        total += item_total
        
        cart_text += f"<b>{item['name']}</b>\n"
        cart_text += f"  Цена: {item['price']}\n"
        cart_text += f"  Количество: {item['quantity']}\n"
        cart_text += f"  Сумма: {item_total} рублей\n\n"
    
    cart_text += f"\n💰 <b>ИТОГО: {total} рублей</b>"
    
    keyboard = []
    
    for toy_key in cart["items"].keys():
        keyboard.append([InlineKeyboardButton(f"❌ Удалить {cart['items'][toy_key]['name']}", 
                                             callback_data=f"remove_{toy_key}")])
    
    keyboard.append([
        InlineKeyboardButton("🗑 Очистить корзину", callback_data="clear_cart"),
        InlineKeyboardButton("✅ Оформить заказ", callback_data="checkout")
    ])
    keyboard.append([InlineKeyboardButton("🛍 Продолжить покупки", callback_data="continue_shopping")])
    
    await query.edit_message_text(
        cart_text,
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def show_delivery_options(query, context):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🚶 Самовывоз (ЖК Дубровка)", callback_data="delivery_pickup")],
        [InlineKeyboardButton("◀️ Назад в корзину", callback_data="view_cart")]
    ])
    
    await query.edit_message_text(
        "📦 <b>Выберите способ получения</b>\n\n"
        "🚶 <b>Самовывоз:</b> ЖК Дубровка (бесплатно)\n\n"
        "👇 Сделайте выбор:",
        parse_mode='HTML',
        reply_markup=keyboard
    )

async def process_order(query, context, delivery_type):
    user = query.from_user
    user_id = user.id
    cart = carts.get(user_id, {"items": {}})
    
    if not cart["items"]:
        await query.edit_message_text("❌ Корзина пуста!")
        return
    
    total = 0
    items_list = []
    for toy_key, item in cart["items"].items():
        price_str = item['price'].replace(' рублей', '').replace(' руб', '').strip()
        try:
            price = int(price_str)
        except:
            price = 0
        
        item_total = price * item['quantity']
        total += item_total
        items_list.append({
            "name": item['name'],
            "quantity": item['quantity'],
            "total": item_total
        })
    
    order_record = {
        "user_id": user_id,
        "date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "delivery_type": "Самовывоз",
        "items": items_list,
        "items_count": len(cart["items"]),
        "total": total
    }
    orders_db.append(order_record)
    
    if user_id in users_db:
        users_db[user_id]["orders_count"] += 1
    
    # Отправляем уведомления админам
    order_text = f"🛒 <b>НОВЫЙ ЗАКАЗ!</b>\n\n"
    order_text += f"👤 <b>Покупатель:</b> {user.first_name}\n"
    order_text += f"🆔 ID: <code>{user.id}</code>\n"
    order_text += f"📦 Способ: Самовывоз\n"
    order_text += f"💰 Сумма: {total} руб\n"
    
    await context.bot.send_message(chat_id=USER_ID, text=order_text, parse_mode='HTML')
    await context.bot.send_message(chat_id=8163619171, text=order_text, parse_mode='HTML')
    
    # Очищаем корзину
    if user_id in carts:
        carts[user_id]["items"] = {}
    
    save_data()
    
    await query.edit_message_text(
        f"✅ <b>Заказ успешно оформлен!</b>\n\n"
        f"Способ получения: Самовывоз (ЖК Дубровка)\n"
        f"Сумма: {total} руб\n\n"
        f"📞 Администратор свяжется с вами.",
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🛍 Продолжить покупки", callback_data="continue_shopping")]
        ])
    )

def get_main_keyboard():
    keyboard = [
        [KeyboardButton("🧸 Плюшевые игрушки"), KeyboardButton("🎲 Обычные игрушки")],
        [KeyboardButton("🛒 Корзина"), KeyboardButton("🛠 Тех. поддержка")]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    update_user_info(user)
    
    await update.message.reply_text(
        "Привет! Я бот для покупки игрушек в ЖК Дубровка.\n"
        "Выберите ниже что вы хотите купить:",
        reply_markup=get_main_keyboard()
    )
    
    if user.id not in users_db or users_db[user.id]["first_seen"] == users_db[user.id]["last_active"]:
        username = f"@{user.username}" if user.username else "без username"
        send_message(f"🆕 Новый пользователь: {user.first_name} ({username}, ID: {user.id})")

async def get_toys_plush(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = read_info_plush()
    toys_list = data.get("toysp", [])
    
    if not toys_list:
        await update.message.reply_text("Плюшевые игрушки временно отсутствуют")
        return
    
    await update.message.reply_text(f"🧸 Загружаю плюшевые игрушки...")
    
    sent_count = 0
    for toy_item in toys_list:
        try:
            for toy_key, toy_info in toy_item.items():
                await send_toy(update, toy_info, toy_key, "plush")
                sent_count += 1
                await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"Ошибка при отправке игрушки: {e}")
            continue
    
    keyboard = [[KeyboardButton("◀️ Назад в главное меню")]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        f"✅ Все плюшевые игрушки показаны! Всего: {sent_count}",
        reply_markup=reply_markup
    )

async def get_toys_simple(update: Update, context: ContextTypes.DEFAULT_TYPE):
    data = read_info_simple()
    toys_list = data.get("toysp", [])
    
    if not toys_list:
        await update.message.reply_text("Обычные игрушки временно отсутствуют")
        return
    
    await update.message.reply_text(f"🎲 Загружаю обычные игрушки...")
    
    sent_count = 0
    for toy_item in toys_list:
        try:
            for toy_key, toy_info in toy_item.items():
                await send_toy(update, toy_info, toy_key, "simple")
                sent_count += 1
                await asyncio.sleep(1)
        except Exception as e:
            logger.error(f"Ошибка при отправке игрушки: {e}")
            continue
    
    keyboard = [[KeyboardButton("◀️ Назад в главное меню")]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(
        f"✅ Все обычные игрушки показаны! Всего: {sent_count}",
        reply_markup=reply_markup
    )

async def support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[KeyboardButton("◀️ Назад в главное меню")]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    
    await update.message.reply_text(
        "🛠 Техническая поддержка:\n"
        "• По вопросам заказа и по работе бота: @Yusuf_Guseinov\n"
        "• Сайт бота: https://naruto456y.github.io",
        reply_markup=reply_markup
    )

async def show_cart_from_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    cart = carts.get(user_id, {"items": {}})
    
    if not cart["items"]:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🛍 Продолжить покупки", callback_data="continue_shopping")]
        ])
        await update.message.reply_text(
            "🛒 <b>Корзина пуста</b>\n\nДобавьте товары в корзину!",
            parse_mode='HTML',
            reply_markup=keyboard
        )
        return
    
    cart_text = "🛒 <b>Ваша корзина:</b>\n\n"
    total = 0
    
    for toy_key, item in cart["items"].items():
        price_str = item['price'].replace(' рублей', '').replace(' руб', '').strip()
        try:
            price = int(price_str)
        except:
            price = 0
        
        item_total = price * item['quantity']
        total += item_total
        
        cart_text += f"<b>{item['name']}</b>\n"
        cart_text += f"  Цена: {item['price']}\n"
        cart_text += f"  Количество: {item['quantity']}\n"
        cart_text += f"  Сумма: {item_total} рублей\n\n"
    
    cart_text += f"\n💰 <b>ИТОГО: {total} рублей</b>"
    
    keyboard = []
    for toy_key in cart["items"].keys():
        keyboard.append([InlineKeyboardButton(f"❌ Удалить {cart['items'][toy_key]['name']}", 
                                             callback_data=f"remove_{toy_key}")])
    
    keyboard.append([
        InlineKeyboardButton("🗑 Очистить корзину", callback_data="clear_cart"),
        InlineKeyboardButton("✅ Оформить заказ", callback_data="checkout")
    ])
    keyboard.append([InlineKeyboardButton("🛍 Продолжить покупки", callback_data="continue_shopping")])
    
    await update.message.reply_text(
        cart_text,
        parse_mode='HTML',
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    update_user_info(user)
    
    text = update.message.text
    
    # Обработка ввода пароля для админки
    if context.user_data.get('awaiting_admin_password'):
        if text == ADMIN_PASSWORD:
            context.user_data['admin_authenticated'] = True
            context.user_data['awaiting_admin_password'] = False
            # Показываем админ-панель
            keyboard = [
                [InlineKeyboardButton("📊 Статистика", callback_data="admin_stats")],
                [InlineKeyboardButton("👥 Пользователи", callback_data="admin_users")],
                [InlineKeyboardButton("🛒 Заказы", callback_data="admin_orders")],
                [InlineKeyboardButton("📦 Товары", callback_data="admin_products")],
                [InlineKeyboardButton("📢 Рассылка", callback_data="admin_broadcast")],
                [InlineKeyboardButton("⚙️ Настройки", callback_data="admin_settings")],
                [InlineKeyboardButton("💾 Сохранить данные", callback_data="admin_save")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                "🔐 <b>Админ-панель</b>\n\nВыберите раздел для управления:",
                parse_mode='HTML',
                reply_markup=reply_markup
            )
        else:
            await update.message.reply_text("❌ Неверный пароль. Попробуйте ещё раз или введите /cancel.")
        return
    
    # Обработка рассылки
    if context.user_data.get('broadcast_mode') and (user.id in ADMIN_IDS or context.user_data.get('admin_authenticated')):
        await send_broadcast(update, context)
        return
    
    # Стандартные текстовые команды
    if text == "🧸 Плюшевые игрушки":
        await get_toys_plush(update, context)
    elif text == "🎲 Обычные игрушки":
        await get_toys_simple(update, context)
    elif text == "🛒 Корзина":
        await show_cart_from_button(update, context)
    elif text == "🛠 Тех. поддержка":
        await support(update, context)
    elif text == "◀️ Назад в главное меню":
        await start(update, context)
    elif text == "/cancel":
        if context.user_data.get('awaiting_admin_password'):
            context.user_data['awaiting_admin_password'] = False
            await update.message.reply_text("❌ Вход в админ-панель отменен", reply_markup=get_main_keyboard())
        elif context.user_data.get('broadcast_mode'):
            context.user_data['broadcast_mode'] = False
            await update.message.reply_text("❌ Рассылка отменена", reply_markup=get_main_keyboard())
        else:
            await update.message.reply_text("❌ Нет активной операции для отмены")
    else:
        await update.message.reply_text(
            "Я не понимаю эту команду. Пожалуйста, воспользуйтесь кнопками ниже:",
            reply_markup=get_main_keyboard()
        )

async def send_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message_text = update.message.text
    
    if message_text.lower() == '/cancel':
        context.user_data['broadcast_mode'] = False
        await update.message.reply_text("❌ Рассылка отменена", reply_markup=get_main_keyboard())
        return
    
    await update.message.reply_text(f"📢 Начинаю рассылку {len(users_db)} пользователям...")
    
    success_count = 0
    fail_count = 0
    
    for user_id in users_db.keys():
        try:
            await context.bot.send_message(
                chat_id=user_id,
                text=f"📢 <b>Рассылка от администратора:</b>\n\n{message_text}",
                parse_mode='HTML'
            )
            success_count += 1
            await asyncio.sleep(0.05)
        except Exception as e:
            logger.error(f"Не удалось отправить сообщение пользователю {user_id}: {e}")
            fail_count += 1
    
    await update.message.reply_text(
        f"✅ Рассылка завершена!\n"
        f"• Успешно: {success_count}\n"
        f"• Ошибок: {fail_count}",
        reply_markup=get_main_keyboard()
    )
    
    context.user_data['broadcast_mode'] = False

def main():
    load_data()
    
    app = Application.builder().token(TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("admin", admin_panel))
    app.add_handler(CommandHandler("send", reply_to_user))
    app.add_handler(CommandHandler("save", save_command))
    app.add_handler(CommandHandler("stats", stats_command))
    
    # ВАЖНО: сначала обрабатываем admin_callback, потом button_callback
    app.add_handler(CallbackQueryHandler(admin_callback, pattern="^admin_.*|^user_.*|^order_.*|^delete_order_.*"))
    app.add_handler(CallbackQueryHandler(button_callback))  # Без pattern, чтобы ловить все остальные
    
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("\n🔍 ПРОВЕРКА ФАЙЛОВ:")
    
    plush_file = 'info_about_toys_plush.json'
    simple_file = 'info_about_toys_simple.json'
    
    if os.path.exists(plush_file):
        try:
            with open(plush_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                toys_count = len(data.get('toysp', []))
                print(f"✅ {plush_file} - загружен, плюшевых игрушек: {toys_count}")
        except json.JSONDecodeError as e:
            print(f"❌ {plush_file} - ошибка в JSON: {e}")
    else:
        print(f"❌ {plush_file} - НЕ НАЙДЕН!")
    
    if os.path.exists(simple_file):
        try:
            with open(simple_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                toys_count = len(data.get('toysp', []))
                print(f"✅ {simple_file} - загружен, обычных игрушек: {toys_count}")
        except json.JSONDecodeError as e:
            print(f"❌ {simple_file} - ошибка в JSON: {e}")
    else:
        print(f"❌ {simple_file} - НЕ НАЙДЕН!")
    
    print(f"\n🚀 Бот запущен... Данные загружены. Пользователей: {len(users_db)}")
    app.run_polling()

if __name__ == "__main__":
    main()