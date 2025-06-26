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
from bs4 import BeautifulSoup
from flask import Flask
import threading
from datetime import datetime

# Configuración
TOKEN = "7220704086:AAHIooBbtT-Tei70ZodcsJY35RdE-Vp-oTA"  # 👈 ¡Reemplaza esto!
monitored_events = {}  # {chat_id: {'url': url, 'last_checked': timestamp}}

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
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎟️ **Monitor de Eventos RA**\n\n"
        "Envía la URL de un evento SOLD OUT para monitorearlo.\n"
        "Comandos disponibles:\n"
        "/status - Ver eventos monitoreados\n"
        "/stop [url] - Detener monitoreo"
    )

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    url = update.message.text.strip()
    
    if not url.startswith(('http://', 'https://')):
        await update.message.reply_text("⚠️ ¡URL inválida! Debe comenzar con http:// o https://")
        return
    
    if chat_id not in monitored_events:
        monitored_events[chat_id] = {}
    
    monitored_events[chat_id][url] = {'last_checked': None}
    await update.message.reply_text(f"🔍 Monitoreando nuevo evento:\n{url}")
    
    # Inicia monitoreo si no está activo
    if len(monitored_events[chat_id]) == 1:
        threading.Thread(target=check_availability, args=(chat_id,), daemon=True).start()

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    if chat_id not in monitored_events or not monitored_events[chat_id]:
        await update.message.reply_text("ℹ️ No hay eventos en monitoreo")
        return
    
    message = "📋 **Eventos monitoreados:**\n"
    for url, data in monitored_events[chat_id].items():
        last_checked = data['last_checked'] or "No verificado aún"
        message += f"\n• {url}\n  Última verificación: {last_checked}\n"
    
    await update.message.reply_text(message)

async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    url = ' '.join(context.args).strip()
    
    if not url:
        await update.message.reply_text("⚠️ Uso: /stop [url]")
        return
    
    if chat_id in monitored_events and url in monitored_events[chat_id]:
        del monitored_events[chat_id][url]
        await update.message.reply_text(f"⏹️ Monitoreo detenido para:\n{url}")
    else:
        await update.message.reply_text("ℹ️ URL no encontrada en monitoreo")

def check_availability(chat_id: int):
    bot = Bot(token=TOKEN)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept-Language": "en-US,en;q=0.9"
    }
    
    while chat_id in monitored_events and monitored_events[chat_id]:
        try:
            for url in list(monitored_events[chat_id].keys()):
                response = requests.get(url, headers=headers, timeout=15)
                soup = BeautifulSoup(response.text, 'html.parser')
                
                # Detección MEJORADA
                buy_button = soup.find('a', {'class': 'buy-ticket'})
                sold_out = any(
                    "sold out" in element.text.lower() or 
                    "agotado" in element.text.lower()
                    for element in soup.find_all(class_=["event-status", "tickets-status"])
                )
                
                monitored_events[chat_id][url]['last_checked'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                
                if buy_button and not sold_out:
                    asyncio.run(
                        bot.send_message(
                            chat_id=chat_id,
                            text=f"🚨 ¡ENTRADAS DISPONIBLES! 🎟️\n{url}"
                        )
                    )
                    del monitored_events[chat_id][url]
            
            time.sleep(5)  # Espera 5 segundos entre checks
            
        except Exception as e:
            logger.error(f"Error: {str(e)}")
            time.sleep(30)

# ---- INICIO ----
def main():
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
