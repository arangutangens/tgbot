import logging
import os
import json # Добавлено для работы с JSON
from telegram import Update
from telegram.constants import ParseMode # Изменено расположение ParseMode
from telegram.ext import Application, MessageHandler, filters, ContextTypes
from background import keep_alive

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Получаем токен из переменных окружения
TOKEN = os.environ['TELEGRAM_TOKEN']
BOT_USERNAME = "joinmadsbot"  # Имя вашего бота для упоминания
MEMBERS_FILE = "chat_members.json" # Файл для хранения данных об участниках

# --- Функции для работы с файлом данных --- #
def load_members_from_file() -> dict:
    """Загружает данные об участниках из JSON-файла."""
    try:
        if os.path.exists(MEMBERS_FILE):
            with open(MEMBERS_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}
    except (json.JSONDecodeError, FileNotFoundError) as e:
        logger.error(f"Ошибка при загрузке данных из {MEMBERS_FILE}: {e}")
        return {} # Возвращаем пустой словарь в случае ошибки

def save_members_to_file(data: dict):
    """Сохраняет данные об участниках в JSON-файл."""
    try:
        with open(MEMBERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    except IOError as e:
        logger.error(f"Ошибка при сохранении данных в {MEMBERS_FILE}: {e}")

# --- Вспомогательные функции --- #
def escape_markdown_v2(text: str) -> str:
    """Экранирует специальные символы для MarkdownV2."""
    escape_chars = r'_*[]()~`>#+-=|{}.!'
    return "".join(['\\' + char if char in escape_chars else char for char in text])

# --- Обработчики --- #
async def handle_new_chat_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает новых участников: добавляет в список (в bot_data и файл) и удаляет сообщение о входе."""
    if not update.message or not update.message.new_chat_members:
        return

    chat_id_str = str(update.message.chat_id)
    all_chat_members = context.bot_data.get('all_chat_members', {})
    current_chat_members = all_chat_members.setdefault(chat_id_str, {})

    member_added = False
    for member in update.message.new_chat_members:
        if not member.is_bot:
            member_id_str = str(member.id)
            current_chat_members[member_id_str] = {'id': member.id, 'name': member.first_name}
            logger.info(f"Пользователь {member.first_name} (ID: {member.id}) добавлен в список участников чата {update.message.chat.title} (ID: {chat_id_str})")
            member_added = True
        else:
            logger.info(f"Бот {member.first_name} (ID: {member.id}) присоединился к чату {update.message.chat.title}, не добавляю в список.")

    if member_added:
        context.bot_data['all_chat_members'] = all_chat_members # Обновляем bot_data
        save_members_to_file(all_chat_members)

    try:
        await update.message.delete()
        logger.info(f"Удалено сообщение о вступлении в группу {update.message.chat.title}")
    except Exception as e:
        logger.error(f"Ошибка при удалении сообщения о вступлении: {e}")

async def handle_left_chat_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает вышедших участников: удаляет из списка (из bot_data и файла)."""
    if not update.message or not update.message.left_chat_member:
        return

    chat_id_str = str(update.message.chat_id)
    member_left = update.message.left_chat_member
    member_id_str = str(member_left.id)

    all_chat_members = context.bot_data.get('all_chat_members', {})
    current_chat_members = all_chat_members.get(chat_id_str)

    member_removed = False
    if current_chat_members and member_id_str in current_chat_members:
        del current_chat_members[member_id_str]
        logger.info(f"Пользователь {member_left.first_name} (ID: {member_left.id}) удален из списка участников чата {update.message.chat.title} (ID: {chat_id_str})")
        if not current_chat_members: # Если чат стал пустым, удаляем его из общего списка
            del all_chat_members[chat_id_str]
        member_removed = True
    
    if member_removed:
        context.bot_data['all_chat_members'] = all_chat_members
        save_members_to_file(all_chat_members)

    # Опционально: удаление сообщения о выходе
    # try:
    #     await update.message.delete()
    #     logger.info(f"Удалено сообщение о выходе {member_left.first_name} из группы {update.message.chat.title}")
    # except Exception as e:
    #     logger.error(f"Ошибка при удалении сообщения о выходе: {e}")

async def handle_bot_mention(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает упоминание бота и отправляет список участников из bot_data."""
    if not update.message:
        return
        
    chat_id_str = str(update.message.chat_id)
    all_chat_members = context.bot_data.get('all_chat_members', {})
    members_map = all_chat_members.get(chat_id_str, {})
    
    if not members_map:
        await update.message.reply_text("В списке участников для этого чата пока никого нет (возможно, список еще не загружен или пуст).")
        return

    member_infos = list(members_map.values())
    mentions = []
    for member_info in member_infos:
        user_id = member_info['id']
        name = member_info.get('name', f'User {user_id}')
        escaped_name = escape_markdown_v2(name)
        mentions.append(f"[{escaped_name}](tg://user?id={user_id})")

    if not mentions:
        await update.message.reply_text("Некого упоминать в этом чате.")
        return

    logger.info(f"Получено упоминание от {update.effective_user.first_name}. Упоминаю {len(mentions)} участников в чате {update.message.chat.title} (ID: {chat_id_str}).")

    chunk_size = 45  # Снизил для большей надежности с учетом длины имен и Markdown
    for i in range(0, len(mentions), chunk_size):
        chunk = mentions[i:i + chunk_size]
        message_text = ", ".join(chunk)
        try:
            await update.message.reply_text(message_text, parse_mode=ParseMode.MARKDOWN_V2)
        except Exception as e:
            logger.error(f"Ошибка при отправке сообщения с упоминаниями: {e}")
            await update.message.reply_text("Произошла ошибка при формировании списка упоминаний.")

def main():
    """Основная функция запуска бота"""
    keep_alive()
    
    application = Application.builder().token(TOKEN).build()

    # Загружаем данные об участниках при старте и сохраняем в bot_data
    application.bot_data['all_chat_members'] = load_members_from_file()
    logger.info(f"Данные об участниках загружены из {MEMBERS_FILE}.")

    # Обработчики
    application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, handle_new_chat_members))
    application.add_handler(MessageHandler(filters.StatusUpdate.LEFT_CHAT_MEMBER, handle_left_chat_member))
    application.add_handler(MessageHandler(filters.Regex(f'@{BOT_USERNAME}'), handle_bot_mention))
    
    logger.info("Бот запущен с сохранением данных участников в файл.")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        logger.info("Бот остановлен.")
    except Exception as e:
        logger.error(f"Ошибка при запуске бота: {e}", exc_info=True) 
