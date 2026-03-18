# ======================== ЗАПУСК (ДЛЯ RENDER) ========================
if __name__ == "__main__":
    import nest_asyncio
    nest_asyncio.apply()
    
    load_data()
    
    application = Application.builder().token(TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("admin", admin_panel))
    # Если нет функции get_logs - удалите эту строку:
    # application.add_handler(CommandHandler("logs", get_logs))
    application.add_handler(CallbackQueryHandler(admin_callback, pattern="^admin_.*"))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    PORT = int(os.environ.get('PORT', 10000))
    print(f"\n🔍 ПРОВЕРКА БОТА:")
    print(f"✅ Бот готов к запуску на RENDER...")
    print(f"👥 Пользователей: {len(users_db)}")
    print(f"📦 Заказов: {len(orders_db)}")
    print(f"🌐 Запускаем webhook на порту {PORT} (слушаем 0.0.0.0)")
    
    # ВАЖНО: добавлен listen="0.0.0.0"
    application.run_webhook(
        listen="0.0.0.0",  # <--- ЭТО КЛЮЧЕВОЙ ПАРАМЕТР
        port=PORT,
        url_path=TOKEN,
        webhook_url=f"https://telegram-shop-bot.onrender.com/{TOKEN}",
        secret_token=None
    )
