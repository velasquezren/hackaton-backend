from groq import Groq
from config import GROQ_API_KEY

client = Groq(api_key=GROQ_API_KEY)

# Modelo: Llama 3.3 70B via Groq (open source, gratis, sin tarjeta de credito)
MODEL = "llama-3.3-70b-versatile"

# --- Modo SIMPLE (por defecto) ---
# Respuesta cortísima: sí/no + una sola razón en lenguaje llano.
SYSTEM_PROMPT_SIMPLE = """Eres CampoIA, asistente agrícola para productores de Santa Cruz, Bolivia.
Hablás con agricultores que no tienen formación técnica y necesitan una respuesta clara y rápida.

FORMATO OBLIGATORIO — exactamente 2 líneas, nada más:
Línea 1: Empezá con ✅ SÍ, ❌ NO o ⚠️ ESPERÁ según corresponda, seguido de una frase corta (máx 8 palabras).
Línea 2: Una sola razón concreta en palabras simples (máx 12 palabras). Sin números técnicos, sin siglas.

Ejemplos correctos:
✅ SÍ podés sembrar esta semana.
El suelo está seco y no se esperan lluvias fuertes.

❌ NO conviene fumigar hoy.
El viento está muy fuerte y el veneno no caerá bien.

⚠️ ESPERÁ un par de días.
Mañana hay lluvia fuerte que puede arruinar la siembra.

NUNCA uses datos técnicos (mm, km/h, grados, porcentajes). NUNCA uses más de 2 líneas."""

# --- Modo DETALLADO (cuando el usuario lo pide explícitamente) ---
# Respuesta completa con datos climáticos y justificación técnica.
SYSTEM_PROMPT_DETALLADO = """Eres CampoIA, un asistente agricola para productores de
Santa Cruz, Bolivia. El agricultor te pidió una respuesta TÉCNICA Y DETALLADA.

Reglas de comunicacion:
- Responde en espanol boliviano. Máximo 5 oraciones.
- Mencioná los datos climáticos exactos (mm de lluvia, km/h de viento, temperaturas).
- Explicá el razonamiento detrás de la recomendación.
- Si el riesgo es alto, sé claro: di "No conviene" sin ambigüedades.
- Si hay incertidumbre, dilo. Nunca inventes datos.
- El contexto es Santa Cruz: clima tropical, temporada de soya nov-mar,
  inundaciones frecuentes en verano, heladas puntuales en invierno."""

def generar_respuesta(
    pregunta_tipo,
    resultado_reglas,
    datos_pronostico,
    cultivo="soya",
    modo_detallado: bool = False,
):
    """
    Genera la respuesta del LLM.

    Args:
        modo_detallado: False → respuesta simple (sí/no + 1 línea).
                        True  → respuesta técnica con datos climáticos.
    """
    system_prompt = SYSTEM_PROMPT_DETALLADO if modo_detallado else SYSTEM_PROMPT_SIMPLE

    # En modo detallado incluimos todos los datos numéricos.
    # En modo simple solo el contexto mínimo para que el LLM decida.
    if modo_detallado:
        resumen_clima = f"""
Proximos 7 dias en la zona del agricultor:
- Precipitacion acumulada: {sum(datos_pronostico['precipitacion'][:7]):.0f}mm
- Dia mas lluvioso: {max(datos_pronostico['precipitacion'][:7]):.0f}mm
- Viento maximo hoy: {datos_pronostico['viento_max'][0]:.0f} km/h
- Temperatura max. hoy: {datos_pronostico['temp_max'][0]:.0f} grados C
- Decision del sistema: {resultado_reglas.get('decision', 'N/A')}
- Nivel de riesgo: {resultado_reglas.get('nivel', 'N/A')}
- Dato clave: {resultado_reglas.get('dato', 'N/A')}
- Consejo base: {resultado_reglas.get('consejo', 'N/A')}
- Cultivo: {cultivo}
"""
        max_tokens = 350
    else:
        resumen_clima = f"""
Situacion climatica resumida:
- Lluvia proximos 7 dias: {sum(datos_pronostico['precipitacion'][:7]):.0f}mm en total
- Viento hoy: {datos_pronostico['viento_max'][0]:.0f} km/h
- Decision del sistema: {resultado_reglas.get('decision', 'N/A')}
- Consejo base: {resultado_reglas.get('consejo', 'N/A')}
- Cultivo: {cultivo}
"""
        max_tokens = 80  # forzar respuesta corta

    mensaje_usuario = f"El agricultor pregunta sobre: {pregunta_tipo}\n{resumen_clima}"

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": mensaje_usuario},
            ],
            temperature=0.4,
            max_tokens=max_tokens,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        return f"[Error al consultar IA: {e}]\nConsejo base: {resultado_reglas.get('consejo', 'No disponible.')}"
