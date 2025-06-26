import requests
import asyncio
import logging
from telegram import Bot, Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)
from flask import Flask  # Nuevo: Para el puerto en Render
import threading

# Configuración
TOKEN = "7220704086:AAHIooBbtT-Tei70ZodcsJY35RdE-Vp-oTA"  # 👈 ¡REEMPLAZA ESTO!
monitored_events = {}

# Configura logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ---- FLASK PARA RENDER (OBLIGATORIO) ----
app = Flask(__name__)

@app.route('/')
def home():
    return "🤖 Bot activo - Monitoreando Resident Advisor"

def run_flask():
    app.run(host='0.0.0.0', port=10000)

# ---- FUNCIONES DEL BOT ----
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎟️ **Monitor de Eventos RA**\n\n"
        "Envía la URL de un evento SOLD OUT para monitorearlo."
    )

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    url = update.message.text.strip()
    
    if not url.startswith(('http://', 'https://')):
        await update.message.reply_text("⚠️ ¡URL inválida! Debe comenzar con http:// o https://")
        return
    
    monitored_events[chat_id] = url
    await update.message.reply_text(f"🔍 Monitoreando:\n{url}")
    
    threading.Thread(target=check_availability, args=(chat_id, url), daemon=True).start()

def check_availability(chat_id: int, url: str):
    bot = Bot(token=TOKEN)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept-Language": "en-US,en;q=0.9"
    }
    
    while chat_id in monitored_events:
        try:
            response = requests.get(url, headers=headers, timeout=10)
            if not any(
                kw in response.text.lower() 
                for kw in ["sold out", "agotado", "tickets for this event are sold out"]
            ):
                asyncio.run(
                    bot.send_message(
                        chat_id=chat_id,
                        text=f"🚨 ¡ENTRADAS DISPONIBLES! 🎟️\n{url}"
                    )
                )
                del monitored_events[chat_id]
                break
            time.sleep(5)
        except Exception as e:
            logger.error(f"Error: {str(e)}")
            time.sleep(30)

# ---- INICIO ----
def main():
    # Inicia Flask en segundo plano (para Render)
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    # Configura el bot de Telegram
    application = Application.builder().token(TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))
    
    logger.info("🤖 Bot iniciado correctamente")
    application.run_polling()

if __name__ == "__main__":
    main()
