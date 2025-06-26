import requests
import asyncio
import logging
import time
from telegram import Bot, Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)
from bs4 import BeautifulSoup
from flask import Flask
import threading
from datetime import datetime

# Configuración
TOKEN = "7999602264:AAFQeUYuJM8iL4lnsak1Mn6Wo7qGEMENeFg"  # 👈 ¡Reemplaza con tu token real!
monitored_events = {}

# Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Flask para Render
app = Flask(__name__)

@app.route('/')
def home():
    return "🤖 Bot activo - Monitoreando Resident Advisor"

def run_flask():
    app.run(host='0.0.0.0', port=10000)

# ---- FUNCIONES MEJORADAS ----
async def send_notification(chat_id: int, url: str):
    """Envía notificaciones de forma confiable"""
    bot = Bot(token=TOKEN)
    await bot.send_message(
        chat_id=chat_id,
        text=f"🚨 ¡ENTRADAS DISPONIBLES! 🎟️\n{url}",
        disable_notification=False  # Asegura notificación con sonido
    )

def check_availability():
    """Monitoreo mejorado con detección precisa"""
    while True:
        try:
            for chat_id in list(monitored_events.keys()):
                for url in list(monitored_events[chat_id].keys()):
                    try:
                        headers = {
                            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                            "Accept-Language": "en-US,en;q=0.9"
                        }
                        response = requests.get(url, headers=headers, timeout=15)
                        soup = BeautifulSoup(response.text, 'html.parser')
                        
                        # Detección MEJORADA (julio 2025)
                        buy_button = soup.find('a', class_='buy-ticket')
                        sold_out = any(
                            text in element.text.lower()
                            for element in soup.find_all(class_=["event-status", "tickets-status"])
                            for text in ["sold out", "agotado", "no tickets", "ha terminado", "ended"]
                        )
                        
                        monitored_events[chat_id][url]['last_checked'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        
                        if buy_button and not sold_out:
                            asyncio.run(send_notification(chat_id, url))
                            del monitored_events[chat_id][url]
                            logger.info(f"✅ Entradas disponibles detectadas para {url}")
                            
                    except Exception as e:
                        logger.error(f"Error al verificar {url}: {str(e)}")
                        time.sleep(10)
            
            time.sleep(5)  # Espera entre verificaciones
            
        except Exception as e:
            logger.error(f"Error general: {str(e)}")
            time.sleep(30)

# ... (Mantén el resto de funciones start/status/stop igual que antes) ...

def main():
    # Inicia el monitoreo en segundo plano
    monitor_thread = threading.Thread(target=check_availability, daemon=True)
    monitor_thread.start()
    
    # Inicia Flask para Render
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    # Configura el bot
    application = Application.builder().token(TOKEN).build()
    
    # Handlers
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CommandHandler("stop", stop))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))
    
    logger.info("🤖 Bot iniciado correctamente")
    application.run_polling()

if __name__ == "__main__":
    main()
