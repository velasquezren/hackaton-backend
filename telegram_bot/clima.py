import requests

def obtener_pronostico(lat, lon):
    """
    Llama a Open-Meteo API y devuelve 16 días de pronóstico.
    Retorna dict con listas de: fechas, precipitacion_diaria, viento_max, temp_max.
    """
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": [
            "precipitation_sum",
            "windspeed_10m_max",
            "temperature_2m_max",
            "temperature_2m_min",
            "precipitation_hours"
        ],
        "timezone": "America/La_Paz",
        "forecast_days": 16
    }
    try:
        r = requests.get(url, params=params, timeout=10)
        r.raise_for_status()
        data = r.json()
        daily = data.get("daily", {})
        return {
            "fechas":        daily.get("time", []),
            "precipitacion": daily.get("precipitation_sum", []),
            "viento_max":    daily.get("windspeed_10m_max", []),
            "temp_max":      daily.get("temperature_2m_max", []),
            "temp_min":      daily.get("temperature_2m_min", []),
            "horas_lluvia":  daily.get("precipitation_hours", [])
        }
    except Exception as e:
        return None
