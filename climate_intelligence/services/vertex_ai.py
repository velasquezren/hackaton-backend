"""
Servicio de integración con Google Vertex AI para predicciones climáticas.

Este módulo encapsula toda la comunicación con la plataforma Vertex AI de Google Cloud,
proporcionando un método mock para desarrollo local y un método real para producción.
"""

import os
import logging
import random
from datetime import date, timedelta
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)


class VertexAIService:
    """
    Clase que envuelve las llamadas al SDK de Google Vertex AI.

    Configuración mediante variables de entorno:
        - GCP_PROJECT_ID: ID del proyecto en Google Cloud Platform
        - GCP_LOCATION: Ubicación del recurso (por defecto: us-central1)
        - VERTEX_AI_ENDPOINT_ID: Identificador del endpoint desplegado en Vertex AI
    """

    def __init__(self):
        # Carga las credenciales de GCP desde variables de entorno
        self.project_id: Optional[str] = os.environ.get("GCP_PROJECT_ID")
        self.location: str = os.environ.get("GCP_LOCATION", "us-central1")
        self.endpoint_id: Optional[str] = os.environ.get("VERTEX_AI_ENDPOINT_ID")

        # Determina si Vertex AI está configurado correctamente
        self.is_configured: bool = all([self.project_id, self.endpoint_id])

        if not self.is_configured:
            logger.warning(
                "Vertex AI no está configurado. Se usará el modo mock. "
                "Configure GCP_PROJECT_ID y VERTEX_AI_ENDPOINT_ID para producción."
            )

    def predict_climate_anomaly(self, region_data: dict) -> dict:
        """
        Genera una predicción de anomalía climática para una región dada.

        Si Vertex AI está configurado, invoca el endpoint real.
        De lo contrario, utiliza datos mock realistas para desarrollo.

        Args:
            region_data: Diccionario con datos de la región, por ejemplo:
                {
                    "region_name": "Norte Integrado",
                    "temperature_anomaly": 1.5,
                    "precipitation_anomaly": -20.0,
                    "soil_moisture": 0.35,
                    "historical_period": "2020-2025"
                }

        Returns:
            Diccionario con la predicción estructurada incluyendo tipo de anomalía,
            severidad, confianza y metadatos del modelo.
        """
        if self.is_configured:
            return self._predict_real(region_data)
        else:
            logger.info(
                "Usando predicción mock para región: %s",
                region_data.get("region_name", "Desconocida")
            )
            return self.mock_predict(region_data)

    def _predict_real(self, region_data: dict) -> dict:
        """
        Invoca el endpoint real de Vertex AI utilizando el SDK oficial de Google Cloud.

        Args:
            region_data: Datos de entrada para el modelo predictivo.

        Returns:
            Respuesta estructurada del modelo de Vertex AI.

        Raises:
            ConnectionError: Si no se puede conectar con Vertex AI.
            ValueError: Si la respuesta del modelo tiene formato inesperado.
        """
        try:
            # Importación diferida para no bloquear si el SDK no está instalado
            from google.cloud import aiplatform

            # Inicializa el cliente de Vertex AI con las credenciales del proyecto
            aiplatform.init(
                project=self.project_id,
                location=self.location
            )

            # Obtiene referencia al endpoint desplegado
            endpoint = aiplatform.Endpoint(
                endpoint_name=self.endpoint_id
            )

            # Prepara las instancias de entrada para el modelo
            instances = [{
                "region": region_data.get("region_name", ""),
                "temperature_anomaly": region_data.get("temperature_anomaly", 0.0),
                "precipitation_anomaly": region_data.get("precipitation_anomaly", 0.0),
                "soil_moisture": region_data.get("soil_moisture", 0.0),
            }]

            logger.info(
                "Enviando solicitud de predicción a Vertex AI para región: %s",
                region_data.get("region_name")
            )

            # Ejecuta la predicción contra el modelo desplegado
            response = endpoint.predict(instances=instances)

            if not response.predictions:
                raise ValueError(
                    "Vertex AI devolvió una respuesta vacía sin predicciones."
                )

            # Extrae la primera predicción del resultado
            raw_prediction = response.predictions[0]

            # Estructura la respuesta en formato estándar de la plataforma
            result = {
                "anomaly_type": raw_prediction.get("anomaly_type", "NORMAL"),
                "severity_level": int(raw_prediction.get("severity_level", 1)),
                "confidence_score": float(raw_prediction.get("confidence_score", 0.5)),
                "model_version": raw_prediction.get("model_version", "unknown"),
                "feature_importance": raw_prediction.get("feature_importance", {}),
                "metadata": {
                    "source": "vertex_ai_live",
                    "project_id": self.project_id,
                    "endpoint_id": self.endpoint_id,
                    "location": self.location,
                    "region_input": region_data.get("region_name"),
                },
            }

            logger.info(
                "Predicción recibida exitosamente: tipo=%s, severidad=%d, confianza=%.2f",
                result["anomaly_type"],
                result["severity_level"],
                result["confidence_score"],
            )

            return result

        except ImportError:
            logger.error(
                "SDK de Google Cloud AI Platform no instalado. "
                "Ejecute: pip install google-cloud-aiplatform"
            )
            raise ConnectionError(
                "SDK de google-cloud-aiplatform no disponible."
            )

        except Exception as exc:
            logger.error(
                "Error al comunicarse con Vertex AI: %s",
                str(exc),
                exc_info=True
            )
            raise ConnectionError(
                f"Error de comunicación con Vertex AI: {exc}"
            ) from exc

    def mock_predict(self, region_data: Optional[dict] = None) -> dict:
        """
        Genera datos de predicción mock realistas para desarrollo y pruebas.

        Simula la respuesta del modelo de Vertex AI con valores coherentes
        que reflejan patrones climáticos plausibles para Santa Cruz, Bolivia.

        Args:
            region_data: Datos opcionales de la región para personalizar la respuesta mock.

        Returns:
            Diccionario con predicción simulada que incluye tipo de anomalía,
            severidad, confianza, importancia de características y metadatos.
        """
        region_data = region_data or {}
        region_name = region_data.get("region_name", "Región Desconocida")

        # Perfiles climáticos regionales para generar predicciones realistas
        # Cada región tiene una distribución de probabilidad distinta
        regional_profiles = {
            "Norte Integrado": {
                "weights": [0.30, 0.35, 0.35],  # SEQUIA, INUNDACION, NORMAL
                "base_severity": 3,
                "base_confidence": 0.78,
            },
            "Valles Cruceños": {
                "weights": [0.25, 0.25, 0.50],
                "base_severity": 2,
                "base_confidence": 0.82,
            },
            "Chiquitania": {
                "weights": [0.45, 0.15, 0.40],
                "base_severity": 4,
                "base_confidence": 0.75,
            },
            "Chaco Cruceño": {
                "weights": [0.50, 0.10, 0.40],
                "base_severity": 4,
                "base_confidence": 0.71,
            },
            "Pantanal": {
                "weights": [0.15, 0.50, 0.35],
                "base_severity": 3,
                "base_confidence": 0.80,
            },
        }

        # Obtiene el perfil regional o usa valores por defecto
        profile = regional_profiles.get(region_name, {
            "weights": [0.33, 0.33, 0.34],
            "base_severity": 2,
            "base_confidence": 0.75,
        })

        # Selecciona el tipo de anomalía según las distribuciones de probabilidad
        anomaly_types = ["SEQUIA", "INUNDACION", "NORMAL"]
        anomaly_type = random.choices(
            anomaly_types,
            weights=profile["weights"],
            k=1
        )[0]

        # Calcula severidad con variación aleatoria sobre la base regional
        severity_variation = random.randint(-1, 1)
        severity_level = max(1, min(5, profile["base_severity"] + severity_variation))

        # Si es NORMAL, la severidad siempre es baja
        if anomaly_type == "NORMAL":
            severity_level = random.randint(1, 2)

        # Calcula confianza con ruido gaussiano realista
        confidence_noise = random.uniform(-0.10, 0.10)
        confidence_score = max(0.40, min(0.98, profile["base_confidence"] + confidence_noise))

        # Genera fecha objetivo a 12 meses en el futuro
        target_date = date.today() + timedelta(days=365)

        # Construye la respuesta mock con estructura idéntica a Vertex AI
        result = {
            "anomaly_type": anomaly_type,
            "severity_level": severity_level,
            "confidence_score": round(confidence_score, 4),
            "model_version": "agritech-climate-v2.1.0-mock",
            "feature_importance": {
                "temperature_anomaly": round(random.uniform(0.15, 0.35), 4),
                "precipitation_anomaly": round(random.uniform(0.20, 0.40), 4),
                "soil_moisture": round(random.uniform(0.10, 0.25), 4),
                "historical_pattern": round(random.uniform(0.10, 0.20), 4),
                "enso_index": round(random.uniform(0.05, 0.15), 4),
            },
            "metadata": {
                "source": "mock_prediction",
                "region_input": region_name,
                "target_date": target_date.isoformat(),
                "prediction_date": date.today().isoformat(),
                "model_training_date": "2025-12-15",
                "training_samples": 15420,
                "notes": (
                    "Predicción simulada para desarrollo. "
                    "En producción se conectará al endpoint real de Vertex AI."
                ),
            },
        }

        logger.info(
            "Predicción mock generada para '%s': tipo=%s, severidad=%d, confianza=%.2f",
            region_name,
            result["anomaly_type"],
            result["severity_level"],
            result["confidence_score"],
        )

        return result
