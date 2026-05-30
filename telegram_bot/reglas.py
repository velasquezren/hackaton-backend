"""
Motor de reglas basado en entrevista con Tiago (agricultor Santa Cruz).
Umbrales validados por conocimiento de campo real.
"""

def evaluar_siembra(pronostico):
    p = pronostico["precipitacion"]
    lluvia_7d = sum(p[:7])
    dias_lluvia_fuerte = sum(1 for x in p[:5] if x and x > 30)

    if lluvia_7d > 80 or dias_lluvia_fuerte >= 2:
        return {
            "decision": "NO_SEMBRAR",
            "nivel": "ALTO",
            "dato": f"{lluvia_7d:.0f}mm acumulados próximos 7 días / {dias_lluvia_fuerte} días con >30mm",
            "consejo": "Riesgo de inundación. Esperar ventana seca."
        }
    elif lluvia_7d > 40:
        return {
            "decision": "PRECAUCIÓN",
            "nivel": "MEDIO",
            "dato": f"{lluvia_7d:.0f}mm acumulados próximos 7 días",
            "consejo": "Monitorear el terreno. Sembrar en zonas altas primero."
        }
    else:
        return {
            "decision": "OK_SEMBRAR",
            "nivel": "BAJO",
            "dato": f"{lluvia_7d:.0f}mm acumulados próximos 7 días",
            "consejo": "Condiciones favorables para siembra."
        }

def evaluar_fumigacion(pronostico):
    vientos = pronostico["viento_max"]
    hoy = vientos[0] if vientos else 999
    manana = vientos[1] if len(vientos) > 1 else 999
    pasado = vientos[2] if len(vientos) > 2 else 999

    # Regla de Tiago: viento debe estar por debajo de 10 km/h
    if hoy < 10:
        return {
            "decision": "OK_HOY",
            "nivel": "FAVORABLE",
            "dato": f"Viento hoy: {hoy:.0f} km/h",
            "consejo": "Buen día para fumigar. Viento por debajo de 10 km/h."
        }
    elif manana < 10:
        return {
            "decision": "OK_MAÑANA",
            "nivel": "ESPERAR",
            "dato": f"Viento hoy: {hoy:.0f} km/h | Mañana: {manana:.0f} km/h",
            "consejo": "Hoy no conviene. Mañana el viento baja — mejor oportunidad."
        }
    elif pasado < 10:
        return {
            "decision": "OK_PASADO",
            "nivel": "ESPERAR",
            "dato": f"Viento hoy: {hoy:.0f} | Mañana: {manana:.0f} | Pasado: {pasado:.0f} km/h",
            "consejo": "Esperar hasta pasado mañana para fumigar."
        }
    else:
        return {
            "decision": "NO_FUMIGAR",
            "nivel": "DESFAVORABLE",
            "dato": f"Viento próximos 3 días: {hoy:.0f} / {manana:.0f} / {pasado:.0f} km/h",
            "consejo": "Viento fuerte los próximos 3 días. El veneno no cae en la tierra."
        }

def evaluar_herbicida_secado(pronostico):
    """
    Regla de Tiago: el herbicida de secado necesita 5-7 días sin lluvia intensa.
    Ninguna planta aguanta más de 7 días, tampoco hay veneno que lo haga en menos.
    """
    p = pronostico["precipitacion"]
    lluvia_7d = sum(p[:7])
    dias_criticos = sum(1 for x in p[:7] if x and x > 15)

    if dias_criticos == 0 and lluvia_7d < 10:
        return {
            "decision": "VENTANA_SEGURA",
            "nivel": "FAVORABLE",
            "dato": f"Solo {lluvia_7d:.0f}mm previstos en 7 días",
            "consejo": "Ventana segura para aplicar herbicida de secado. Podés arrancar hoy."
        }
    elif dias_criticos <= 1 and lluvia_7d < 30:
        return {
            "decision": "VENTANA_RIESGOSA",
            "nivel": "PRECAUCIÓN",
            "dato": f"{dias_criticos} día(s) con lluvia fuerte en los próximos 7 días",
            "consejo": "Ventana ajustada. Aplicar entre los días sin lluvia y monitorear."
        }
    else:
        return {
            "decision": "SIN_VENTANA",
            "nivel": "ALTO",
            "dato": f"{dias_criticos} días con lluvia fuerte / {lluvia_7d:.0f}mm en 7 días",
            "consejo": "No hay ventana segura para herbicida de secado esta semana."
        }

def evaluar_cosecha(pronostico):
    """
    Regla de Tiago: si el suelo está muy embarrado la cosechadora no puede entrar.
    Últimos días de lluvia = proxy del estado del suelo.
    """
    p = pronostico["precipitacion"]
    # Usamos los primeros días como referencia del estado actual del suelo
    lluvia_reciente = sum(p[:3])
    dia_mas_lluvioso = max(p[:3]) if p else 0

    if lluvia_reciente < 20 and dia_mas_lluvioso < 15:
        return {
            "decision": "SUELO_ACCESIBLE",
            "nivel": "FAVORABLE",
            "dato": f"Solo {lluvia_reciente:.0f}mm en últimos 3 días",
            "consejo": "Suelo en condiciones. Maquinaria puede entrar sin problemas."
        }
    elif lluvia_reciente < 50:
        return {
            "decision": "SUELO_HÚMEDO",
            "nivel": "PRECAUCIÓN",
            "dato": f"{lluvia_reciente:.0f}mm en los últimos 3 días",
            "consejo": "Suelo húmedo. Esperar 1-2 días secos antes de entrar con maquinaria pesada."
        }
    else:
        return {
            "decision": "SUELO_EMBARRADO",
            "nivel": "CRÍTICO",
            "dato": f"{lluvia_reciente:.0f}mm en los últimos 3 días",
            "consejo": "Suelo muy blando. La cosechadora puede quedar atrapada. Esperar."
        }

def evaluar_riesgo_general(pronostico):
    p = pronostico["precipitacion"]
    lluvia_3d = sum(p[:3])
    max_dia = max(p[:3]) if p else 0

    if max_dia > 40 or lluvia_3d > 60:
        return "ALERTA_INUNDACIÓN"
    elif lluvia_3d > 30:
        return "RIESGO_MEDIO"
    else:
        return "SIN_ALERTA"
