import requests
import asyncio
import logging
import time
import socket
from telegram import Bot, Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)
from bs4 import BeautifulSoup
import threading
from datetime import datetime
from flask import Flask, request  # Para el puerto en Render

# ----- CONFIGURACIÓN ANTICONFLICTOS -----
try:
    # Bloqueo para evitar múltiples instancias
    lock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    lock.bind('\0ra_monitor_lock')
    print("🔒 Bloqueo de instancia única activado")
except socket.error:
    print("🛑 ¡Ya hay una instancia en ejecución! Saliendo...")
    exit(1)

# Configuración
TOKEN = "8091750123:AAFa76yyeJK_STepks8JzK9NMjWx9KKdqEw"  # 👈 ¡REEMPLAZA CON TU TOKEN REAL!
monitored_events = {}

# Logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ----- SERVIDOR FLASK PARA EL PUERTO -----
app = Flask(__name__)

@app.route('/')
def home():
    return "🤖 Bot de monitoreo RA activo - Visita https://t.me/TuBot"

def run_flask():
    app.run(host='0.0.0.0', port=10000)

# ---- FUNCIONES DEL BOT ----
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🎟️ **Monitor de Eventos RA**\n\n"
        "Envía la URL de un evento SOLD OUT para monitorearlo.\n"
        "Comandos disponibles:\n"
        "/status - Ver eventos monitoreados\n"
        "/stop [url] - Detener monitoreo\n\n"
        "🔍 Ejemplo: https://es.ra.co/events/2072940"
    )

async def handle_url(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.message.chat_id
    url = update.message.text.strip()
    
    if not url.startswith(('http://', 'https://')):
        await update.message.reply_text("⚠️ ¡URL inválida! Debe comenzar con http:// o https://")
        return
    
    if chat_id not in monitored_events:
        monitored_events[chat_id] = {}
    
    if url not in monitored_events[chat_id]:
        monitored_events[chat_id][url] = {'last_checked': None}
        await update.message.reply_text(f"🔍 Monitoreando evento:\n{url}")
    else:
        await update.message.reply_text("ℹ️ Este evento ya está siendo monitoreado")

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

async def send_notification(chat_id: int, url: str):
    bot = Bot(token=TOKEN)
    await bot.send_message(
        chat_id=chat_id,
        text=f"🚨 ¡ENTRADAS DISPONIBLES! 🎟️\n{url}",
        disable_notification=False
    )

def check_availability():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept-Language": "en-US,en;q=0.9"
    }
    
    while True:
        try:
            # Copiamos los eventos actuales para evitar cambios durante la iteración
            current_events = {k: v.copy() for k, v in monitored_events.items()}
            
            for chat_id, events in current_events.items():
                for url, data in events.items():
                    try:
                        response = requests.get(url, headers=headers, timeout=15)
                        soup = BeautifulSoup(response.text, 'html.parser')
                        
                        # ---- DETECCIÓN ESPECÍFICA PARA ES.RA.CO ----
                        sold_out = False
                        
                        # 1. Buscar elemento de estado (clases actualizadas julio 2025)
                        status_element = soup.find(class_=["event-status", "event-tickets__status"])
                        if status_element:
                            status_text = status_element.get_text().strip().lower()
                            if "agotado" in status_text or "sold out" in status_text:
                                sold_out = True
                        
                        # 2. Buscar botón de compra
                        buy_button = soup.find('a', class_='event-tickets__btn')
                        
                        # 3. Actualizar registro (si el evento sigue activo)
                        if chat_id in monitored_events and url in monitored_events[chat_id]:
                            monitored_events[chat_id][url]['last_checked'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        
                        # 4. Notificar SI hay botón Y NO está agotado
                        if buy_button and not sold_out:
                            asyncio.run(send_notification(chat_id, url))
                            if chat_id in monitored_events and url in monitored_events[chat_id]:
                                del monitored_events[chat_id][url]
                            logger.info(f"✅ Entradas detectadas: {url}")
                            
                    except Exception as e:
                        logger.error(f"Error en {url}: {str(e)}")
                        time.sleep(5)
            
            time.sleep(5)  # Espera 5 segundos entre ciclos
            
        except Exception as e:
            logger.error(f"Error general: {str(e)}")
            time.sleep(30)

# ---- INICIO ----
def main():
    # Inicia el monitoreo en segundo plano
    monitor_thread = threading.Thread(target=check_availability, daemon=True)
    monitor_thread.start()
    
    # Inicia Flask para el puerto (requerido por Render)
    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    # Configura el bot de Telegram
    application = Application.builder() \
        .token(TOKEN) \
        .concurrent_updates(True) \
        .build()
    
    # Registra los comandos
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CommandHandler("stop", stop))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_url))
    
    logger.info("🤖 Bot iniciado - Listo para monitorear eventos RA")
    application.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
