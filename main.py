import logging
import os
import json
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

# Функции для работы с файлом участников
def load_members():
    try:
        with open('group_members.json', 'r', encoding='utf-8') as f:
            data = json.load(f)
            # Преобразуем списки обратно в множества
            return {int(k): set(v) for k, v in data['group_members'].items()}
    except FileNotFoundError:
        return defaultdict(set)
    except Exception as e:
        logger.error(f"Ошибка при загрузке списка участников: {e}")
        return defaultdict(set)

def save_members(members_dict):
    try:
        # Преобразуем множества в списки для JSON
        data = {
            'group_members': {
                str(k): list(v) for k, v in members_dict.items()
            }
        }
        with open('group_members.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Ошибка при сохранении списка участников: {e}")

# Загружаем список участников при запуске
group_members = load_members()

async def delete_join_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Функция для удаления сообщений о вступлении в группу
    """
    try:
        # Проверяем, является ли сообщение системным о вступлении
        if update.message and update.message.new_chat_members:
            # Добавляем новых участников в список
            for member in update.message.new_chat_members:
                if not member.is_bot:  # Игнорируем ботов
                    group_members[update.message.chat_id].add(member.id)
            # Сохраняем изменения
            save_members(group_members)
            # Удаляем сообщение
            await update.message.delete()
            logger.info(f"Удалено сообщение о вступлении в группу {update.message.chat.title}")
    except Exception as e:
        logger.error(f"Ошибка при удалении сообщения: {e}")

async def handle_left_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик выхода участника из группы
    """
    try:
        if update.message and update.message.left_chat_member:
            member = update.message.left_chat_member
            if not member.is_bot:  # Игнорируем ботов
                group_members[update.message.chat_id].discard(member.id)
                # Сохраняем изменения
                save_members(group_members)
                logger.info(f"Участник {member.first_name} удален из списка группы {update.message.chat.title}")
    except Exception as e:
        logger.error(f"Ошибка при обработке выхода участника: {e}")

async def handle_mention(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """
    Обработчик упоминания бота
    """
    try:
        if not update.message or not update.message.text:
            return

        # Проверяем, упомянут ли бот
        bot_username = context.bot.username
        if f"@{bot_username}" in update.message.text:
            chat_id = update.message.chat_id
            logger.info(f"Получено упоминание бота в группе {chat_id}")
            
            if chat_id not in group_members:
                await update.message.reply_text("В этой группе пока нет участников в списке.")
                return

            # Получаем информацию об участниках
            members = group_members[chat_id]
            if not members:
                await update.message.reply_text("В этой группе пока нет участников в списке.")
                return

            # Разбиваем на группы по 50 участников
            members_list = list(members)
            for i in range(0, len(members_list), 50):
                chunk = members_list[i:i + 50]
                mentions = " ".join([f"<a href='tg://user?id={member_id}'>⠀</a>" for member_id in chunk])
                await update.message.reply_text(f"Участники группы:\n{mentions}", parse_mode='HTML')
                logger.info(f"Отправлен список участников в группу {update.message.chat.title}")

    except Exception as e:
        logger.error(f"Ошибка при обработке упоминания: {e}")

def main():
    """
    Основная функция запуска бота
    """
    # Запускаем Flask-сервер для поддержания работы
    keep_alive()
    
    # Создаем приложение
    application = Application.builder().token(TOKEN).build()

    # Добавляем обработчики
    application.add_handler(MessageHandler(filters.ALL, delete_join_messages))
    application.add_handler(MessageHandler(filters.StatusUpdate.LEFT_CHAT_MEMBER, handle_left_member))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_mention))

    # Запускаем бота
    logger.info("Бот запущен")
    
    try:
        # Очищаем предыдущие обновления и запускаем бота
        application.bot.delete_webhook(drop_pending_updates=True)
        application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}")
        # Пробуем перезапустить бота
        application.stop()
        application.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Бот остановлен")
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}") 
