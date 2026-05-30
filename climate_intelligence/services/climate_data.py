"""
Servicio de obtención y procesamiento de datos climáticos históricos.

Abstrae el acceso a APIs externas (Open-Meteo, NASA POWER) y proporciona
un modo mock realista para desarrollo local sin dependencias externas.

Fuentes de datos:
    - Open-Meteo Archive API (gratuita, sin clave, alta resolución)
    - NASA POWER API (gratuita, sin clave, cobertura global)
    - Modo mock con patrones climáticos basados en datos reales de Santa Cruz
"""

import logging
import random
from datetime import date, timedelta
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

# Coordenadas geográficas de los centroides de cada región agrícola de Santa Cruz
REGION_COORDINATES = {
    "Norte Integrado": {"lat": -17.33, "lon": -63.24},
    "Valles Cruceños": {"lat": -18.50, "lon": -64.10},
    "Chiquitania": {"lat": -16.35, "lon": -61.08},
    "Chaco Cruceño": {"lat": -20.50, "lon": -62.85},
    "Pantanal / Germán Busch": {"lat": -18.10, "lon": -57.70},
}

# Variables climáticas que se obtienen de Open-Meteo
OPEN_METEO_VARIABLES = [
    "precipitation_sum",         # Precipitación total diaria (mm)
    "temperature_2m_max",        # Temperatura máxima a 2m (°C)
    "temperature_2m_min",        # Temperatura mínima a 2m (°C)
    "temperature_2m_mean",       # Temperatura media a 2m (°C)
    "soil_moisture_0_7cm",       # Humedad del suelo (0-7cm) (m³/m³)
    "et0_fao_evapotranspiration",# Evapotranspiración de referencia (mm)
]

VARIABLE_UNITS = {
    "precipitation_sum": "mm",
    "temperature_2m_max": "°C",
    "temperature_2m_min": "°C",
    "temperature_2m_mean": "°C",
    "soil_moisture_0_7cm": "m³/m³",
    "et0_fao_evapotranspiration": "mm",
}


class ClimateDataService:
    """
    Servicio de datos climáticos con soporte dual: APIs reales o datos mock realistas.

    Configuración mediante django.conf.settings:
        - USE_REAL_CLIMATE_DATA: Si True, usa Open-Meteo/NASA POWER reales
        - OPEN_METEO_BASE_URL: URL base de la API de archivo de Open-Meteo
    """

    def __init__(self):
        from django.conf import settings
        self.use_real_data = getattr(settings, 'USE_REAL_CLIMATE_DATA', False)
        self.open_meteo_url = getattr(
            settings, 'OPEN_METEO_BASE_URL',
            'https://archive-api.open-meteo.com/v1/archive'
        )

        if self.use_real_data:
            logger.info("ClimateDataService: Modo producción — usando APIs externas reales.")
        else:
            logger.info("ClimateDataService: Modo desarrollo — usando datos mock realistas.")

    def fetch_historical_data(
        self,
        region_name: str,
        start_date: date,
        end_date: date,
        variables: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        """
        Obtiene datos climáticos históricos para una región en un rango de fechas.

        Args:
            region_name: Nombre de la región (debe coincidir con REGION_COORDINATES)
            start_date: Fecha de inicio del período histórico
            end_date: Fecha de fin del período histórico
            variables: Lista de variables a obtener. Si None, usa OPEN_METEO_VARIABLES

        Returns:
            Lista de diccionarios, uno por variable/fecha con claves:
            {variable_name, date, value, unit, source, raw_response}
        """
        if variables is None:
            variables = OPEN_METEO_VARIABLES

        if self.use_real_data:
            return self._fetch_open_meteo_real(region_name, start_date, end_date, variables)
        else:
            return self._generate_mock_climate_data(region_name, start_date, end_date, variables)

    def _fetch_open_meteo_real(
        self,
        region_name: str,
        start_date: date,
        end_date: date,
        variables: List[str],
    ) -> List[Dict[str, Any]]:
        """
        Consulta la API de archivo histórico de Open-Meteo.

        Open-Meteo es gratuita y no requiere clave API. Cubre datos desde 1940
        con resolución de 1km para temperatura, precipitación y humedad del suelo.

        Documentación: https://open-meteo.com/en/docs/historical-weather-api
        """
        coords = REGION_COORDINATES.get(region_name)
        if not coords:
            logger.warning(
                "Coordenadas no encontradas para la región '%s'. "
                "Usando coordenadas por defecto de Santa Cruz.",
                region_name
            )
            coords = {"lat": -17.78, "lon": -63.18}  # Santa Cruz de la Sierra

        try:
            import httpx

            params = {
                "latitude": coords["lat"],
                "longitude": coords["lon"],
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "daily": ",".join(variables),
                "timezone": "America/La_Paz",
            }

            logger.info(
                "Consultando Open-Meteo para '%s' (%s a %s) — %d variables",
                region_name, start_date, end_date, len(variables)
            )

            with httpx.Client(timeout=30.0) as client:
                response = client.get(self.open_meteo_url, params=params)
                response.raise_for_status()
                data = response.json()

            results = []
            daily = data.get("daily", {})
            dates = daily.get("time", [])

            for var in variables:
                values = daily.get(var, [])
                for i, d_str in enumerate(dates):
                    if i < len(values) and values[i] is not None:
                        results.append({
                            "variable_name": var,
                            "date": date.fromisoformat(d_str),
                            "value": float(values[i]),
                            "unit": VARIABLE_UNITS.get(var, ""),
                            "source": "OPEN_METEO",
                            "raw_response": {"latitude": coords["lat"], "longitude": coords["lon"]},
                        })

            logger.info(
                "Open-Meteo: %d registros obtenidos para '%s'",
                len(results), region_name
            )
            return results

        except ImportError:
            logger.error("httpx no instalado. Ejecute: pip install httpx. Usando modo mock.")
            return self._generate_mock_climate_data(region_name, start_date, end_date, variables)

        except Exception as exc:
            logger.error(
                "Error al consultar Open-Meteo para '%s': %s. Fallback a mock.",
                region_name, exc
            )
            return self._generate_mock_climate_data(region_name, start_date, end_date, variables)

    def _generate_mock_climate_data(
        self,
        region_name: str,
        start_date: date,
        end_date: date,
        variables: List[str],
    ) -> List[Dict[str, Any]]:
        """
        Genera datos climáticos simulados con patrones estacionales realistas.

        Los valores siguen los patrones climáticos documentados del Departamento
        de Santa Cruz: lluvias concentradas en verano (Nov-Mar) y sequía en invierno (Jun-Sep).
        """
        # Perfiles climáticos base por región (ajustados a datos reales de Santa Cruz)
        regional_climate_profiles = {
            "Norte Integrado": {
                "base_temp": 26.5, "temp_amplitude": 6.0,
                "base_precip": 1350, "precip_season_factor": 3.5,   # lluvia intensa en verano
                "base_soil_moisture": 0.32,
            },
            "Valles Cruceños": {
                "base_temp": 20.0, "temp_amplitude": 8.0,
                "base_precip": 800, "precip_season_factor": 2.5,
                "base_soil_moisture": 0.25,
            },
            "Chiquitania": {
                "base_temp": 27.0, "temp_amplitude": 5.0,
                "base_precip": 1100, "precip_season_factor": 3.0,
                "base_soil_moisture": 0.22,
            },
            "Chaco Cruceño": {
                "base_temp": 29.0, "temp_amplitude": 7.0,
                "base_precip": 550, "precip_season_factor": 2.0,    # alta sequía
                "base_soil_moisture": 0.15,
            },
            "Pantanal / Germán Busch": {
                "base_temp": 27.5, "temp_amplitude": 4.5,
                "base_precip": 1200, "precip_season_factor": 3.2,
                "base_soil_moisture": 0.42,                          # alta humedad por el río Paraguay
            },
        }

        profile = regional_climate_profiles.get(region_name, {
            "base_temp": 25.0, "temp_amplitude": 6.0,
            "base_precip": 1000, "precip_season_factor": 3.0,
            "base_soil_moisture": 0.28,
        })

        results = []
        current = start_date
        total_days = (end_date - start_date).days + 1

        while current <= end_date:
            month = current.month
            # Factor estacional: máximo en enero (verano austral), mínimo en julio
            import math
            season_factor = math.sin(math.pi * (month - 1) / 6)  # ciclo anual
            precip_factor = max(0.1, (1 + season_factor) * 0.5)  # 0.1 a 1.0
            temp_factor = 1 + season_factor * 0.15

            for var in variables:
                value = None
                unit = VARIABLE_UNITS.get(var, "")

                if var == "precipitation_sum":
                    # Precipitación diaria con alta variabilidad estacional
                    annual_mm = profile["base_precip"]
                    daily_avg = (annual_mm * precip_factor * profile["precip_season_factor"]) / 365
                    # Alta variabilidad en días lluviosos
                    if random.random() < (0.1 + 0.4 * precip_factor):  # probabilidad de lluvia
                        value = round(max(0.0, daily_avg * random.uniform(0.5, 3.0) + random.gauss(0, 2)), 2)
                    else:
                        value = 0.0

                elif var == "temperature_2m_max":
                    value = round(
                        profile["base_temp"] * temp_factor
                        + profile["temp_amplitude"] * 0.5
                        + random.gauss(0, 1.5),
                        1
                    )

                elif var == "temperature_2m_min":
                    value = round(
                        (profile["base_temp"] * temp_factor)
                        - profile["temp_amplitude"] * 0.5
                        + random.gauss(0, 1.5),
                        1
                    )

                elif var == "temperature_2m_mean":
                    value = round(
                        profile["base_temp"] * temp_factor
                        + random.gauss(0, 1.0),
                        1
                    )

                elif var == "soil_moisture_0_7cm":
                    value = round(
                        max(0.05, min(0.60,
                            profile["base_soil_moisture"] * (0.7 + 0.6 * precip_factor)
                            + random.gauss(0, 0.03)
                        )),
                        4
                    )

                elif var == "et0_fao_evapotranspiration":
                    # ETo mayor en verano caluroso
                    value = round(
                        max(1.0, 4.5 * temp_factor + random.gauss(0, 0.5)),
                        2
                    )

                if value is not None:
                    results.append({
                        "variable_name": var,
                        "date": current,
                        "value": value,
                        "unit": unit,
                        "source": "MOCK",
                        "raw_response": None,
                    })

            current += timedelta(days=1)

        logger.info(
            "Mock: %d registros climáticos generados para '%s' (%s a %s)",
            len(results), region_name, start_date, end_date
        )
        return results

    def get_regional_climate_summary(
        self,
        region_name: str,
        months_back: int = 12,
    ) -> Dict[str, Any]:
        """
        Calcula un resumen de las condiciones climáticas recientes de una región.

        Usado como contexto adicional para el servicio de Gemini al generar alertas
        y como features para el modelo predictivo de Vertex AI.

        Args:
            region_name: Nombre de la región a consultar
            months_back: Número de meses hacia atrás a considerar

        Returns:
            Diccionario con promedios y anomalías de las variables clave
        """
        end = date.today()
        start = end - timedelta(days=months_back * 30)

        data = self.fetch_historical_data(region_name, start, end, OPEN_METEO_VARIABLES)

        # Agrupa por variable
        by_variable: Dict[str, List[float]] = {}
        for record in data:
            var = record["variable_name"]
            if var not in by_variable:
                by_variable[var] = []
            by_variable[var].append(record["value"])

        summary = {"region": region_name, "period_months": months_back}

        for var, values in by_variable.items():
            if values:
                non_zero = [v for v in values if v > 0] if var == "precipitation_sum" else values
                summary[f"{var}_avg"] = round(sum(values) / len(values), 3)
                summary[f"{var}_max"] = round(max(values), 3)
                summary[f"{var}_min"] = round(min(values), 3)
                if var == "precipitation_sum":
                    summary["total_precipitation_mm"] = round(sum(values), 1)
                    summary["rainy_days_count"] = sum(1 for v in values if v > 0.5)

        return summary
