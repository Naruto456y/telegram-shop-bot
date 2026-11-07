# 🧸 Telegram Shop Bot

Telegram-бот магазина игрушек. Покупатель смотрит каталог с фотографиями, собирает корзину и оформляет заказ, а администратор получает уведомление и ведёт заказы прямо в Telegram.

![Python](https://img.shields.io/badge/Python-3.10+-blue?logo=python)
![python-telegram-bot](https://img.shields.io/badge/python--telegram--bot-21-2CA5E0?logo=telegram)
![License](https://img.shields.io/badge/License-MIT-green)

## Возможности

**Для покупателя**
- каталог в двух категориях, плюшевые и обычные игрушки;
- у каждого товара есть альбом фотографий, цена и описание;
- корзина: добавить, убрать, очистить, посчитать итог;
- оформление заказа с самовывозом;
- раздел помощи с контактом поддержки.

**Для администратора**
- уведомления о новых пользователях и заказах;
- админ-панель `/admin` под паролем: статистика, пользователи, заказы, товары;
- `/send <id> <текст>` для ответа покупателю от имени бота;
- `/stats` и `/save` для быстрой статистики и ручного сохранения;
- корзины, пользователи и заказы сохраняются в `bot_data.pickle` раз в минуту и переживают перезапуск.

## Как устроено

```
info_about_toys_*.json ──► каталог ──► карточка товара (альбом фото из toys_for_girls/)
                                            │
                                            ▼
                                        корзина ──► заказ ──► уведомление админам
```

Товары описаны в JSON, так что новый товар добавляется без правки кода: нужна запись с названием, ценой, описанием и именами фото.

```json
"toy1": {
    "name": "Розовый стич",
    "price": "199 рублей",
    "about": "Новая в хорошем качестве, с подвеской",
    "img": ["Розовый стич спереди.jpg", "Розовый стич сбоку.jpg"]
}
```

## Установка

```bash
git clone https://github.com/Naruto456y/telegram-shop-bot.git
cd telegram-shop-bot
python -m venv .venv
.venv\Scripts\activate          # Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
```

Скопируйте `.env.example` в `.env` и заполните:

| Переменная | Что это |
|---|---|
| `BOT_TOKEN` | токен бота от [@BotFather](https://t.me/BotFather) |
| `ADMIN_IDS` | Telegram ID администраторов через запятую |
| `ADMIN_PASSWORD` | пароль для входа в `/admin` |
| `PICKUP_ADDRESS` | адрес самовывоза, его видит покупатель |
| `SUPPORT_CONTACT` | контакт поддержки, например `@username` |
| `WEBHOOK_URL` | только для хостинга; если пусто, бот работает через polling |

## Запуск

```bash
python bot.py
```

Откройте бота в Telegram и отправьте `/start`.

## Деплой на Render

В `render.yaml` описан веб-сервис. Значения переменных задаются в панели Render, в `WEBHOOK_URL` укажите адрес сервиса (например `https://telegram-shop-bot.onrender.com`), тогда бот переключится на webhook и будет слушать порт из `PORT`.

## Структура

```
bot.py                      бот: каталог, корзина, заказы, админ-панель
info_about_toys_plush.json  плюшевые игрушки
info_about_toys_simple.json обычные игрушки
toys_for_girls/             фото товаров
render.yaml                 конфигурация Render
.env.example                пример настроек
```

## Автор

Yusuf ([@Naruto456y](https://github.com/Naruto456y)). Лицензия [MIT](LICENSE).
