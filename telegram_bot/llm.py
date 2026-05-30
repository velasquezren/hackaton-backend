from groq import Groq
from config import GROQ_API_KEY

client = Groq(api_key=GROQ_API_KEY)

# Modelo: Llama 3.3 70B via Groq (open source, gratis, sin tarjeta de credito)
MODEL = "llama-3.3-70b-versatile"

SYSTEM_PROMPT = """Eres CampoIA, un asistente agricola para productores de 
Santa Cruz, Bolivia. Tu trabajo es ayudar a agricultores -muchos sin formacion 
tecnica- a tomar decisiones de siembra, fumigacion y cosecha basadas en datos 
climaticos reales.

Reglas de comunicacion:
- Responde en espanol boliviano simple y directo. Maximo 4 oraciones.
- Siempre menciona el dato climatico especifico que justifica tu recomendacion.
- Si el riesgo es alto, se claro: di "No conviene" sin ambiGuedades.
- Si hay incertidumbre, dilo. Nunca inventes datos.
- No uses jerga tecnica (no digas NDVI, anomalia, percentil).
- Al final puedes ofrecer un recordatorio si el agricultor lo quiere.
- El contexto es Santa Cruz: clima tropical, temporada de soya nov-mar,
  inundaciones frecuentes en verano, heladas puntuales en invierno."""

def generar_respuesta(pregunta_tipo, resultado_reglas, datos_pronostico, cultivo="soya"):
    resumen_clima = f"""
Proximos 7 dias en la zona del agricultor:
- Precipitacion acumulada: {sum(datos_pronostico['precipitacion'][:7]):.0f}mm
- Dia mas lluvioso: {max(datos_pronostico['precipitacion'][:7]):.0f}mm
- Viento maximo hoy: {datos_pronostico['viento_max'][0]:.0f} km/h
- Temperatura max. hoy: {datos_pronostico['temp_max'][0]:.0f} grados C

Decision del sistema: {resultado_reglas.get('decision', 'N/A')}
Nivel de riesgo: {resultado_reglas.get('nivel', 'N/A')}
Dato clave: {resultado_reglas.get('dato', 'N/A')}
Consejo base: {resultado_reglas.get('consejo', 'N/A')}
Cultivo del productor: {cultivo}
"""
    mensaje_usuario = f"El agricultor pregunta sobre: {pregunta_tipo}\n{resumen_clima}"

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user",   "content": mensaje_usuario},
            ],
            temperature=0.7,
            max_tokens=300,
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"[Error al consultar IA: {e}]\nRecomendacion base: {resultado_reglas.get('consejo', 'No hay consejo disponible.')}"
