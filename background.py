from flask import Flask, request
from threading import Thread
import logging

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

app = Flask('')

@app.route('/')
def home():
    # Получаем информацию о запросе
    user_agent = request.headers.get('User-Agent', 'Unknown')
    ip = request.remote_addr
    logger.info(f"Получен запрос от {ip} с User-Agent: {user_agent}")
    return "Бот работает!"

def run():
    app.run(host='0.0.0.0', port=10000)

def keep_alive():
    t = Thread(target=run)
    t.start() 
