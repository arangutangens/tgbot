import logging
import os
import json
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from background import keep_alive
from collections import defaultdict

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Получаем токен из переменных окружения
TOKEN = os.environ['TELEGRAM_TOKEN']

# Словарь для хранения участников групп
group_members = {}

def load_members():
    """Загрузка списка участников из файла"""
    global group_members
    try:
        if os.path.exists('group_members.json'):
            with open('group_members.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
                group_members = data.get('group_members', {})
                logger.info(f"Загружен список участников: {json.dumps(data, ensure_ascii=False)}")
        else:
            group_members = {}
            logger.info("Файл group_members.json не найден, создан пустой список участников")
    except Exception as e:
        logger.error(f"Ошибка при загрузке списка участников: {e}")
        group_members = {}

def save_members():
    """Сохранение списка участников в файл"""
    try:
        with open('group_members.json', 'w', encoding='utf-8') as f:
            json.dump({'group_members': group_members}, f, ensure_ascii=False, indent=4)
        logger.info(f"Список участников сохранен: {json.dumps({'group_members': group_members}, ensure_ascii=False)}")
    except Exception as e:
        logger.error(f"Ошибка при сохранении списка участников: {e}")

async def delete_join_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Удаление сообщений о новых участниках"""
    if update.message and update.message.new_chat_members:
        try:
            await update.message.delete()
            logger.info(f"Удалено сообщение о новом участнике в группе {update.message.chat_id}")
            
            # Добавляем новых участников в список
            chat_id = str(update.message.chat_id)
            if chat_id not in group_members:
                group_members[chat_id] = []
            
            for member in update.message.new_chat_members:
                if member.id not in group_members[chat_id]:
                    group_members[chat_id].append(member.id)
                    logger.info(f"Добавлен участник {member.id} в группу {chat_id}")
            
            save_members()
            
        except Exception as e:
            logger.error(f"Ошибка при удалении сообщения: {e}")

async def handle_member_left(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка выхода участника из группы"""
    if update.message and update.message.left_chat_member:
        try:
            chat_id = str(update.message.chat_id)
            member_id = update.message.left_chat_member.id
            
            if chat_id in group_members and member_id in group_members[chat_id]:
                group_members[chat_id].remove(member_id)
                logger.info(f"Удален участник {member_id} из группы {chat_id}")
                save_members()
            
            await update.message.delete()
            logger.info(f"Удалено сообщение о выходе участника из группы {chat_id}")
            
        except Exception as e:
            logger.error(f"Ошибка при обработке выхода участника: {e}")

async def handle_mention(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка упоминания бота"""
    if update.message and update.message.text:
        try:
            bot = await context.bot.get_me()
            bot_username = bot.username
            logger.info(f"Проверка упоминания. Username бота: {bot_username}, текст сообщения: {update.message.text}")
            
            if f"@{bot_username}" in update.message.text:
                chat_id = str(update.message.chat_id)
                if chat_id in group_members and group_members[chat_id]:
                    members_text = ", ".join([f"@{member_id}" for member_id in group_members[chat_id]])
                    await update.message.reply_text(f"Список участников группы:\n{members_text}")
                    logger.info(f"Отправлен список участников для группы {chat_id}")
                else:
                    await update.message.reply_text("В группе пока нет участников")
                    logger.info(f"Группа {chat_id} пуста")
        except Exception as e:
            logger.error(f"Ошибка при обработке упоминания: {e}")

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик ошибок
    """
    logger.error(f"Произошла ошибка: {context.error}")

async def main():
    """
    Основная функция запуска бота
    """
    try:
        # Загружаем список участников при запуске
        load_members()
        
        # Запускаем Flask-сервер для поддержания работы
        keep_alive()
        
        # Создаем приложение
        application = Application.builder().token(TOKEN).build()

        # Добавляем обработчики
        application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, delete_join_messages))
        application.add_handler(MessageHandler(filters.StatusUpdate.LEFT_CHAT_MEMBER, handle_member_left))
        application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_mention))
        
        # Добавляем обработчик ошибок
        application.add_error_handler(error_handler)

        # Запускаем бота
        logger.info("Бот запущен")
        
        # Очищаем предыдущие обновления и запускаем бота
        await application.bot.delete_webhook(drop_pending_updates=True)
        await application.initialize()
        await application.start()
        await application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")
        # Пробуем перезапустить бота
        await application.stop()
        await application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен")
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}") 
