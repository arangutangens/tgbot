import logging
import os
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from background import keep_alive

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Получаем токен из переменных окружения
TOKEN = os.environ['TELEGRAM_TOKEN']

async def delete_join_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Функция для удаления сообщений о вступлении в группу
    """
    try:
        # Проверяем, является ли сообщение системным о вступлении
        if update.message and update.message.new_chat_members:
            # Удаляем сообщение
            await update.message.delete()
            logger.info(f"Удалено сообщение о вступлении в группу {update.message.chat.title}")
    except Exception as e:
        logger.error(f"Ошибка при удалении сообщения: {e}")

async def main():
    """
    Основная функция запуска бота
    """
    # Создаем приложение
    application = Application.builder().token(TOKEN).build()

    # Добавляем обработчик сообщений
    application.add_handler(MessageHandler(filters.ALL, delete_join_messages))

    # Запускаем Flask-сервер для поддержания работы
    keep_alive()
    
    # Запускаем бота
    logger.info("Бот запущен")
    await application.initialize()
    await application.start()
    await application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    import asyncio
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен")
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}") 
