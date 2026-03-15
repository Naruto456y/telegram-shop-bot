#!/bin/bash
# Запускаем бота в фоне
python bot.py &

# Запускаем сервер для сайта
python server.py
