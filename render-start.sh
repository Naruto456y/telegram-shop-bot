#!/bin/bash
# Убиваем все старые процессы бота
pkill -f "python bot.py" || true

# Запускаем бота с правильной настройкой
python bot.py &

# Запускаем сервер для сайта
python server.py
