"""
Servicio de integración con la API de Google Earth Engine (GEE).

Permite obtener índices espectrales de vegetación (NDVI) y agua en superficie (NDWI)
para las coordenadas de las regiones utilizando colecciones satelitales reales:
    - Sentinel-2 (Copernicus) para alta resolución espacial reciente.
    - MODIS (Terra/Aqua) para consistencia histórica de largo plazo.

Incluye un modo mock automático en caso de no contar con credenciales activas o
cuando `USE_REAL_SATELLITE_DATA` esté configurado como False.
"""

import logging
import random
import math
from datetime import date, timedelta
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class EarthEngineService:
    """
    Servicio de conexión y consulta a Google Earth Engine.
    """

    def __init__(self):
        from django.conf import settings
        self.use_real_data = getattr(settings, 'USE_REAL_SATELLITE_DATA', False)
        self.project_id = getattr(settings, 'GEE_PROJECT_ID', '')
        self.initialized = False

        if self.use_real_data:
            self._initialize_ee()
        else:
            logger.info("EarthEngineService: Modo desarrollo (MOCK) activo por configuración.")

    def _initialize_ee(self):
        """
        Inicializa la librería de Earth Engine con credenciales del entorno (ADC)
        o Service Account si está disponible.
        """
        try:
            import ee
            import google.auth

            logger.info("EarthEngineService: Intentando inicializar Google Earth Engine API...")
            
            # Obtener credenciales predeterminadas de la aplicación (ADC)
            # Nota: Esto autentica automáticamente si corre en Google Cloud Run
            credentials, project = google.auth.default(
                scopes=['https://www.googleapis.com/auth/earthengine']
            )
            
            project_to_use = self.project_id or project
            if not project_to_use:
                logger.warning(
                    "EarthEngineService: GEE_PROJECT_ID/PROJECT_ID no especificado. "
                    "La inicialización podría fallar si no hay proyecto configurado en gcloud."
                )

            # Inicializar API
            ee.Initialize(credentials=credentials, project=project_to_use)
            self.initialized = True
            logger.info("EarthEngineService: API de Earth Engine inicializada exitosamente.")
        except ImportError:
            logger.error(
                "EarthEngineService: No se pudo importar 'ee' o 'google.auth'. "
                "Asegúrate de instalar 'earthengine-api' y 'google-auth'. Usando modo MOCK."
            )
            self.initialized = False
        except Exception as exc:
            logger.error(
                "EarthEngineService: Error al inicializar Earth Engine: %s. "
                "Verifica tus credenciales de GCP. Usando modo MOCK como fallback.",
                exc
            )
            self.initialized = False

    def fetch_satellite_indices(
        self,
        region_name: str,
        lat: float,
        lon: float,
        target_date: date,
        buffer_meters: float = 5000
    ) -> Dict[str, Any]:
        """
        Obtiene los índices espectrales NDVI y NDWI para las coordenadas indicadas.
        Si la inicialización de Earth Engine falló o está deshabilitada, retorna datos simulados.

        Args:
            region_name: Nombre de la región (para la simulación estacional en fallback)
            lat: Latitud de la consulta
            lon: Longitud de la consulta
            target_date: Fecha objetivo del análisis satelital
            buffer_meters: Radio en metros del buffer alrededor del punto para promediar los píxeles

        Returns:
            Dict con claves: {ndvi, ndwi, cloud_cover_pct, source, error}
        """
        if not self.initialized or not self.use_real_data:
            return self._generate_mock_indices(region_name, target_date)

        # Si está inicializado, intenta Sentinel-2 primero, y MODIS como fallback
        result = self._fetch_sentinel2_indices(lat, lon, target_date, buffer_meters)
        if result:
            return result

        logger.warning("EarthEngineService: Sentinel-2 sin datos. Intentando fallback con MODIS...")
        result = self._fetch_modis_indices(lat, lon, target_date, buffer_meters * 2)
        if result:
            return result

        # Si todo falla, retorna mock marcando que hubo un error de obtención
        logger.error(
            "EarthEngineService: No se pudieron obtener datos satelitales reales para (%s, %s). "
            "Retornando datos mock de emergencia.", lat, lon
        )
        mock_data = self._generate_mock_indices(region_name, target_date)
        mock_data["error"] = "No se encontraron imágenes satelitales en el rango de fechas."
        return mock_data

    def _fetch_sentinel2_indices(
        self,
        lat: float,
        lon: float,
        target_date: date,
        buffer_meters: float
    ) -> Optional[Dict[str, Any]]:
        """
        Consulta la colección de Sentinel-2 Surface Reflectance (Copernicus)
        para calcular NDVI y NDWI de McFeeters.
        """
        try:
            import ee
            
            # Crear geometría de punto y rango de fechas (ventana de 30 días para evitar nubes)
            point = ee.Geometry.Point([lon, lat])
            start_date = (target_date - timedelta(days=15)).isoformat()
            end_date = (target_date + timedelta(days=15)).isoformat()

            # Colección Sentinel-2 Surface Reflectance con filtro de nubosidad
            collection = (ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED')
                          .filterBounds(point)
                          .filterDate(start_date, end_date)
                          .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 30)))

            # Fallback a Top-Of-Atmosphere si no hay SR disponible históricamente en esa fecha
            if collection.size().getInfo() == 0:
                logger.info("EarthEngineService: Intentando con Sentinel-2 TOA (L1C)...")
                collection = (ee.ImageCollection('COPERNICUS/S2')
                              .filterBounds(point)
                              .filterDate(start_date, end_date)
                              .filter(ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', 30)))

            if collection.size().getInfo() == 0:
                return None

            # Función interna para calcular índices espectrales
            # NDVI = (B8 - B4) / (B8 + B4)
            # NDWI (McFeeters) = (B3 - B8) / (B3 + B8)
            def add_indices(image):
                ndvi = image.normalizedDifference(['B8', 'B4']).rename('NDVI')
                ndwi = image.normalizedDifference(['B3', 'B8']).rename('NDWI')
                return image.addBands([ndvi, ndwi])

            # Reducir colección usando la mediana para remover ruido nuboso residual
            composite = collection.map(add_indices).median()
            
            # Crear el buffer de análisis alrededor del centroide
            aoi = point.buffer(buffer_meters)

            # Reducir región para obtener el promedio espacial de los píxeles
            stats = composite.reduceRegion(
                reducer=ee.Reducer.mean(),
                geometry=aoi,
                scale=30,  # 30m para balancear velocidad y resolución espacial
                maxPixels=1e6
            ).getInfo()

            ndvi = stats.get('NDVI')
            ndwi = stats.get('NDWI')

            if ndvi is None or ndwi is None:
                return None

            # Obtener nubosidad promedio de la colección procesada
            avg_cloud = collection.aggregate_mean('CLOUDY_PIXEL_PERCENTAGE').getInfo()

            return {
                "ndvi": round(ndvi, 4),
                "ndwi": round(ndwi, 4),
                "cloud_cover_pct": round(avg_cloud or 0.0, 1),
                "source": "SENTINEL_2",
                "error": None
            }
        except Exception as e:
            logger.error("EarthEngineService: Error en Sentinel-2 API: %s", e)
            return None

    def _fetch_modis_indices(
        self,
        lat: float,
        lon: float,
        target_date: date,
        buffer_meters: float
    ) -> Optional[Dict[str, Any]]:
        """
        Consulta las colecciones de MODIS (Terra/Aqua) para obtener NDVI (MOD13Q1)
        y NDWI (MOD09A1) en ventanas de 16 y 8 días respectivamente.
        """
        try:
            import ee
            
            point = ee.Geometry.Point([lon, lat])
            start_date = (target_date - timedelta(days=10)).isoformat()
            end_date = (target_date + timedelta(days=10)).isoformat()
            aoi = point.buffer(buffer_meters)

            # 1. Obtener NDVI de MOD13Q1 (Vegetation Indices 16-Day, 250m)
            modis_vi = (ee.ImageCollection('MODIS/061/MOD13Q1')
                        .filterBounds(point)
                        .filterDate(start_date, end_date))

            ndvi = None
            if modis_vi.size().getInfo() > 0:
                ndvi_img = modis_vi.median().select('NDVI')
                ndvi_raw = ndvi_img.reduceRegion(
                    reducer=ee.Reducer.mean(),
                    geometry=aoi,
                    scale=250,
                    maxPixels=1e5
                ).getInfo().get('NDVI')
                
                # MODIS NDVI viene a escala de 0.0001
                if ndvi_raw is not None:
                    ndvi = ndvi_raw * 0.0001

            # 2. Calcular NDWI de MOD09A1 (Surface Reflectance 8-Day, 500m)
            # Bandas MODIS: sur_refl_b04 es Green, sur_refl_b02 es NIR
            modis_sr = (ee.ImageCollection('MODIS/061/MOD09A1')
                        .filterBounds(point)
                        .filterDate(start_date, end_date))

            ndwi = None
            if modis_sr.size().getInfo() > 0:
                sr_img = modis_sr.median()
                ndwi_img = sr_img.normalizedDifference(['sur_refl_b04', 'sur_refl_b02'])
                ndwi = ndwi_img.reduceRegion(
                    reducer=ee.Reducer.mean(),
                    geometry=aoi,
                    scale=500,
                    maxPixels=1e5
                ).getInfo().get('nd')

            if ndvi is None:
                return None

            return {
                "ndvi": round(ndvi, 4),
                "ndwi": round(ndwi, 4) if ndwi is not None else -0.1,
                "cloud_cover_pct": 0.0,  # MODIS L3/L4 ya viene filtrado de calidad/nubes
                "source": "MODIS",
                "error": None
            }
        except Exception as e:
            logger.error("EarthEngineService: Error en MODIS API: %s", e)
            return None

    def _generate_mock_indices(self, region_name: str, target_date: date) -> Dict[str, Any]:
        """
        Genera datos satelitales simulados consistentes con la estacionalidad climática
        de cada sub-región de Santa Cruz.
        """
        # Perfiles idénticos al seeder para mantener coherencia en desarrollo
        profiles = {
            "Norte Integrado": {"ndvi_base": 0.62, "ndwi_base": -0.05, "ndvi_seasonal": 0.15, "ndwi_seasonal": 0.20},
            "Valles Cruceños": {"ndvi_base": 0.55, "ndwi_base": -0.15, "ndvi_seasonal": 0.20, "ndwi_seasonal": 0.12},
            "Chiquitania": {"ndvi_base": 0.58, "ndwi_base": -0.20, "ndvi_seasonal": 0.18, "ndwi_seasonal": 0.15},
            "Chaco Cruceño": {"ndvi_base": 0.35, "ndwi_base": -0.35, "ndvi_seasonal": 0.12, "ndwi_seasonal": 0.08},
            "Pantanal / Germán Busch": {"ndvi_base": 0.65, "ndwi_base": 0.15, "ndvi_seasonal": 0.10, "ndwi_seasonal": 0.30},
        }

        profile = profiles.get(
            region_name,
            {"ndvi_base": 0.50, "ndwi_base": -0.10, "ndvi_seasonal": 0.15, "ndwi_seasonal": 0.12}
        )

        month = target_date.month
        season_factor = math.sin(math.pi * (month - 1) / 6)

        # Simular NDVI y NDWI con ruido gaussiano
        ndvi = profile["ndvi_base"] + profile["ndvi_seasonal"] * season_factor + random.gauss(0, 0.02)
        ndvi = round(max(-0.1, min(0.95, ndvi)), 4)

        ndwi = profile["ndwi_base"] + profile["ndwi_seasonal"] * season_factor + random.gauss(0, 0.02)
        ndwi = round(max(-0.8, min(0.8, ndwi)), 4)

        cloud_cover = max(0.0, min(100.0, 15.0 + 30.0 * max(0, season_factor) + random.uniform(-10, 10)))

        return {
            "ndvi": ndvi,
            "ndwi": ndwi,
            "cloud_cover_pct": round(cloud_cover, 1),
            "source": "MOCK",
            "error": None
        }
