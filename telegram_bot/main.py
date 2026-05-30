import logging
from telegram import Update, ReplyKeyboardMarkup, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, ConversationHandler, filters
)
from config import TELEGRAM_TOKEN
from db import init_db, guardar_usuario, obtener_usuario, guardar_consulta
from clima import obtener_pronostico
from reglas import (evaluar_siembra, evaluar_fumigacion,
                    evaluar_herbicida_secado, evaluar_cosecha, evaluar_riesgo_general)
from llm import generar_respuesta

logging.basicConfig(level=logging.INFO)

ESPERANDO_UBICACION, ESPERANDO_CULTIVO = range(2)

MENU_TECLADO = [
    ["🌱 Sembrar", "💨 Fumigar"],
    ["🌾 Cosechar", "🧴 Herbicida secado"],
    ["⚠️ Alerta clima", "📊 Resumen semana"]
]

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    usuario_existente = obtener_usuario(user.id)
    if usuario_existente:
        await update.message.reply_text(
            f"👋 Hola de nuevo, {usuario_existente[1]}!\n"
            "¿Qué querés consultar hoy?",
            reply_markup=ReplyKeyboardMarkup(MENU_TECLADO, resize_keyboard=True)
        )
        return ConversationHandler.END

    await update.message.reply_text(
        f"🌿 *Hola {user.first_name}! Soy CampoIA.*\n\n"
        "Te ayudo a saber si conviene sembrar, fumigar o cosechar "
        "según el clima real de tu zona.\n\n"
        "📍 ¿Dónde está tu campo? Enviame tu ubicación (botón de adjuntar > Ubicación) "
        "o escribí el nombre del municipio (ej: 'Warnes', 'Montero', 'Yapacaní').",
        parse_mode="Markdown"
    )
    return ESPERANDO_UBICACION

async def recibir_ubicacion(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    if update.message.location:
        lat = update.message.location.latitude
        lon = update.message.location.longitude
        zona = "tu zona"
    else:
        # Geocodificación simple por municipio conocido de Santa Cruz
        MUNICIPIOS = {
            "warnes":     (-17.5083, -63.1697),
            "montero":    (-17.3393, -63.2538),
            "yapacani":   (-17.3756, -64.1046),
            "santa cruz": (-17.7863, -63.1812),
            "la guardia": (-17.9300, -63.1750),
            "cotoca":     (-17.7636, -62.9897),
            "porongo":    (-17.8697, -63.3197),
            "minero":     (-17.2667, -63.0833),
            "san julian": (-17.8000, -62.5500),
            "los troncos":(-17.0500, -63.7500),
        }
        texto = update.message.text.lower().strip()
        match = next((v for k, v in MUNICIPIOS.items() if k in texto), None)
        if match:
            lat, lon = match
            zona = update.message.text
        else:
            await update.message.reply_text(
                "No reconocí ese municipio. Probá con: Warnes, Montero, Yapacaní, "
                "Santa Cruz, La Guardia, Cotoca, o enviá tu ubicación GPS."
            )
            return ESPERANDO_UBICACION

    context.user_data["lat"] = lat
    context.user_data["lon"] = lon
    context.user_data["zona"] = zona

    keyboard = [["🌱 Soya", "🌽 Maíz"], ["🌻 Girasol", "🌾 Trigo"], ["Otro"]]
    await update.message.reply_text(
        "✅ Ubicación registrada.\n\n¿Qué cultivo tenés principalmente?",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    )
    return ESPERANDO_CULTIVO

async def recibir_cultivo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    cultivo = update.message.text.replace("🌱","").replace("🌽","").replace("🌻","").replace("🌾","").strip()
    lat = context.user_data.get("lat")
    lon = context.user_data.get("lon")
    zona = context.user_data.get("zona", "")

    guardar_usuario(user.id, user.first_name, lat, lon, cultivo, zona)

    await update.message.reply_text(
        f"✅ Listo, {user.first_name}! Ya tengo tu zona y cultivo ({cultivo}).\n\n"
        "Ahora podés consultarme cuando quieras. ¿Qué necesitás saber?",
        reply_markup=ReplyKeyboardMarkup(MENU_TECLADO, resize_keyboard=True)
    )
    return ConversationHandler.END

async def consulta_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    texto = update.message.text
    usuario = obtener_usuario(user.id)

    if not usuario:
        await update.message.reply_text(
            "Primero necesito saber dónde está tu campo. Escribí /start"
        )
        return

    _, nombre, lat, lon, cultivo, zona = usuario
    pronostico = obtener_pronostico(lat, lon)

    if not pronostico:
        await update.message.reply_text(
            "⚠️ No pude obtener datos del clima ahora. Intentá en unos minutos."
        )
        return

    await update.message.reply_text("🌤️ Consultando el clima de tu zona...")

    # Determinar tipo de consulta
    if "sembrar" in texto.lower() or "siembra" in texto.lower():
        tipo = "siembra"
        resultado = evaluar_siembra(pronostico)
    elif "fumigar" in texto.lower() or "fumigacion" in texto.lower():
        tipo = "fumigación"
        resultado = evaluar_fumigacion(pronostico)
    elif "cosechar" in texto.lower() or "cosecha" in texto.lower():
        tipo = "cosecha"
        resultado = evaluar_cosecha(pronostico)
    elif "herbicida" in texto.lower() or "secar" in texto.lower() or "secado" in texto.lower():
        tipo = "herbicida de secado"
        resultado = evaluar_herbicida_secado(pronostico)
    elif "alerta" in texto.lower() or "riesgo" in texto.lower():
        tipo = "alerta general"
        alerta = evaluar_riesgo_general(pronostico)
        lluvia_3d = sum(pronostico["precipitacion"][:3])
        if alerta == "ALERTA_INUNDACIÓN":
            respuesta = (f"⛔ *ALERTA DE INUNDACIÓN* para tu zona.\n"
                        f"Se esperan {lluvia_3d:.0f}mm en los próximos 3 días. "
                        f"Tomá precauciones con maquinaria y cultivos en zonas bajas.")
        elif alerta == "RIESGO_MEDIO":
            respuesta = (f"⚠️ Riesgo medio de lluvia intensa.\n"
                        f"{lluvia_3d:.0f}mm esperados en 3 días. Monitorear.")
        else:
            respuesta = f"✅ Sin alertas activas para tu zona esta semana."
        await update.message.reply_text(respuesta, parse_mode="Markdown")
        return
    elif "resumen" in texto.lower() or "semana" in texto.lower() or "clima" in texto.lower():
        tipo = "resumen"
        p = pronostico["precipitacion"][:7]
        v = pronostico["viento_max"][:7]
        fechas = pronostico["fechas"][:7]
        resumen = "📊 *Resumen climático — próximos 7 días:*\n\n"
        for i in range(7):
            lluvia = p[i] if i < len(p) else 0
            viento = v[i] if i < len(v) else 0
            emoji = "🌧️" if lluvia > 20 else ("🌦️" if lluvia > 5 else "☀️")
            resumen += f"{emoji} {fechas[i]}: {lluvia:.0f}mm | 💨{viento:.0f}km/h\n"
        await update.message.reply_text(resumen, parse_mode="Markdown")
        return
    else:
        # Texto libre → Claude con contexto completo (AQUÍ ahora es Gemini)
        tipo = "consulta libre"
        resultado = evaluar_siembra(pronostico)  # contexto base

    # Generar respuesta con Gemini
    respuesta_ia = generar_respuesta(tipo, resultado, pronostico, cultivo)

    # Emoji según nivel
    emoji_nivel = {
        "FAVORABLE": "✅", "BAJO": "✅",
        "MEDIO": "⚠️", "PRECAUCIÓN": "⚠️", "ESPERAR": "⚠️",
        "ALTO": "⛔", "CRÍTICO": "⛔", "DESFAVORABLE": "⛔",
        "ALERTA": "🚨"
    }.get(resultado.get("nivel", ""), "ℹ️")

    mensaje_final = f"{emoji_nivel} *{tipo.upper()}*\n\n{respuesta_ia}"

    # Botones de feedback
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("👍 Útil", callback_data=f"ok_{tipo}"),
         InlineKeyboardButton("👎 No me ayudó", callback_data=f"mal_{tipo}")]
    ])

    await update.message.reply_text(
        mensaje_final,
        parse_mode="Markdown",
        reply_markup=keyboard
    )
    guardar_consulta(user.id, tipo, respuesta_ia)

async def feedback_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    if query.data.startswith("ok_"):
        await query.edit_message_reply_markup(None)
        await query.message.reply_text("¡Gracias! Me ayuda a mejorar. 🌱")
    else:
        await query.edit_message_reply_markup(None)
        await query.message.reply_text(
            "Gracias por avisarme. ¿Qué no estuvo bien? "
            "Podés escribirme y trato de ayudarte mejor."
        )

def main():
    init_db()
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            ESPERANDO_UBICACION: [
                MessageHandler(filters.LOCATION | filters.TEXT & ~filters.COMMAND, recibir_ubicacion)
            ],
            ESPERANDO_CULTIVO: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, recibir_cultivo)
            ]
        },
        fallbacks=[CommandHandler("start", start)]
    )

    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(feedback_callback))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, consulta_handler))

    print("CampoIA Bot corriendo...")
    app.run_polling()

if __name__ == "__main__":
    main()
