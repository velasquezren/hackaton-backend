"""
Servicio de generación de alertas agrícolas en lenguaje natural usando Google Gemini.

Traduce las predicciones técnicas de Vertex AI en mensajes comprensibles y
accionables para productores agrícolas de Santa Cruz, Bolivia, sin necesidad
de formación técnica avanzada.

Incluye un sistema de fallback basado en plantillas de texto que garantiza
la generación de alertas incluso sin conexión a Gemini.
"""

import json
import logging
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)


# Mapeo de niveles de alerta según severidad y tipo de anomalía
ALERT_LEVEL_MAP = {
    (1, "SEQUIA"): "LOW",
    (2, "SEQUIA"): "LOW",
    (3, "SEQUIA"): "MEDIUM",
    (4, "SEQUIA"): "HIGH",
    (5, "SEQUIA"): "EXTREME",
    (1, "INUNDACION"): "LOW",
    (2, "INUNDACION"): "MEDIUM",
    (3, "INUNDACION"): "MEDIUM",
    (4, "INUNDACION"): "HIGH",
    (5, "INUNDACION"): "EXTREME",
    (1, "NORMAL"): "LOW",
    (2, "NORMAL"): "LOW",
    (3, "NORMAL"): "LOW",
    (4, "NORMAL"): "MEDIUM",
    (5, "NORMAL"): "MEDIUM",
}

# Plantillas de fallback para cada tipo de anomalía y nivel
FALLBACK_TEMPLATES = {
    "SEQUIA": {
        "LOW": {
            "title": "⚠️ Posible Déficit Hídrico Leve — {region}",
            "sms": "Alerta leve de sequía en {region} para {target_date}. "
                   "Monitoree la humedad del suelo y prepare sistemas de riego.",
            "tips": [
                "Revise el estado de sus reservas de agua y acequias",
                "Considere siembras de cultivos resistentes a la sequía",
                "Mulch en suelos para reducir la evaporación",
                "Programe riegos nocturnos para reducir pérdidas por calor",
            ]
        },
        "MEDIUM": {
            "title": "🌵 Riesgo Moderado de Sequía — {region}",
            "sms": "Riesgo moderado de sequía detectado en {region} para {target_date}. "
                   "Active plan de riego de emergencia y proteja sus cultivos.",
            "tips": [
                "Active sistema de riego por goteo si dispone de uno",
                "Priorice el agua para cultivos de mayor valor económico",
                "Contacte a su cooperativa para coordinar uso del agua",
                "Evite siembras nuevas hasta que mejore el pronóstico",
                "Verifique seguros agrícolas vigentes",
            ]
        },
        "HIGH": {
            "title": "🚨 Sequía Severa Proyectada — {region}",
            "sms": "ALERTA ALTA: Sequía severa proyectada en {region} para {target_date}. "
                   "Tome medidas urgentes de protección de cultivos y ganado.",
            "tips": [
                "Coseche anticipadamente cultivos en etapa avanzada",
                "Reduzca carga animal en pasturas afectadas",
                "Contacte autoridades locales para acceso a agua de emergencia",
                "Almacene agua ahora mientras todavía hay disponibilidad",
                "Revise y active seguros agropecuarios de inmediato",
                "Prepare plan de contingencia para pérdida parcial de cosecha",
            ]
        },
        "EXTREME": {
            "title": "🆘 SEQUÍA EXTREMA — {region} — Riesgo Catastrófico",
            "sms": "EMERGENCIA: Sequía extrema y catastrófica proyectada en {region} para "
                   "{target_date}. Actúe hoy. Contacte autoridades.",
            "tips": [
                "URGENTE: Contacte al gobierno departamental y cooperativas",
                "Active todos los seguros agropecuarios disponibles",
                "Priorice salvaguardar vida del ganado sobre cultivos",
                "Siembre únicamente en áreas con acceso garantizado a riego",
                "Explore créditos de emergencia agropecuaria",
                "Coordine con vecinos para uso colectivo de fuentes de agua",
            ]
        },
    },
    "INUNDACION": {
        "LOW": {
            "title": "🌧️ Exceso de Lluvias Posible — {region}",
            "sms": "Posible exceso de precipitaciones en {region} para {target_date}. "
                   "Revise drenajes y proteja equipos en zonas bajas.",
            "tips": [
                "Inspeccione y limpie canales de drenaje",
                "Eleve equipos y materiales almacenados en zonas bajas",
                "Prepare semillas de reemplazo por si hay pérdidas menores",
            ]
        },
        "MEDIUM": {
            "title": "🌊 Riesgo Moderado de Inundación — {region}",
            "sms": "Riesgo moderado de inundación en {region} para {target_date}. "
                   "Refuerce drenajes y evite siembras en zonas bajas.",
            "tips": [
                "No siembre en terrenos bajos o con historial de anegamiento",
                "Refuerce diques y bordos de protección",
                "Registre sus bienes agrícolas para seguro",
                "Mantenga comunicación con sistema de alerta del municipio",
                "Tenga plan de evacuación del ganado preparado",
            ]
        },
        "HIGH": {
            "title": "🚨 Inundación Severa Proyectada — {region}",
            "sms": "ALERTA ALTA: Inundaciones severas proyectadas en {region} para "
                   "{target_date}. Proteja cultivos y traslade ganado a zonas altas.",
            "tips": [
                "Traslade ganado a terrenos elevados inmediatamente",
                "Coseche cultivos listos aunque no sea la fecha ideal",
                "Asegure maquinaria agrícola en zonas altas",
                "Coordine con autoridades locales planes de contingencia",
                "Active seguros agrícolas preventivamente",
                "Evite acceder a zonas inundables con maquinaria pesada",
            ]
        },
        "EXTREME": {
            "title": "🆘 INUNDACIÓN CATASTRÓFICA — {region} — Emergencia",
            "sms": "EMERGENCIA: Inundación catastrófica proyectada en {region} para "
                   "{target_date}. Evacúe zonas de riesgo. Proteja vidas primero.",
            "tips": [
                "PRIORIDAD: Proteja vidas humanas y seguridad familiar",
                "Evacúe ganado a zonas altas lo antes posible",
                "Contacte Defensa Civil departamental inmediatamente",
                "No ingrese a zonas inundadas con maquinaria",
                "Documente daños con fotos para reclamo de seguros",
                "Active todos los seguros agropecuarios disponibles",
            ]
        },
    },
    "NORMAL": {
        "LOW": {
            "title": "✅ Condiciones Climáticas Normales — {region}",
            "sms": "Condiciones climáticas normales proyectadas en {region} para {target_date}. "
                   "Buen momento para planificar la campaña.",
            "tips": [
                "Aproveche las condiciones estables para programar siembras",
                "Realice mantenimiento preventivo de maquinaria",
                "Planifique el calendario de riego para la temporada",
            ]
        },
        "MEDIUM": {
            "title": "📊 Monitoreo Climático Recomendado — {region}",
            "sms": "Condiciones generalmente normales con variabilidad en {region} para "
                   "{target_date}. Mantenga monitoreo activo.",
            "tips": [
                "Monitoree semanalmente el estado de sus cultivos",
                "Tenga preparado un plan B ante cambios climáticos",
                "Consulte actualizaciones del pronóstico regularmente",
            ]
        },
    }
}


class GeminiAlertService:
    """
    Servicio de generación de alertas climáticas en lenguaje natural mediante Gemini.

    Usa el LLM de Google para crear mensajes contextualizados, comprensibles
    y accionables para productores agrícolas sin formación técnica.

    Cuando Gemini no está disponible (sin clave API o error de conexión),
    usa automáticamente el sistema de plantillas de fallback.
    """

    def __init__(self):
        from django.conf import settings
        self.api_key = getattr(settings, 'GEMINI_API_KEY', '')
        self.model_name = getattr(settings, 'GEMINI_MODEL', 'gemini-1.5-flash')
        self.use_gemini = getattr(settings, 'USE_GEMINI_ALERTS', True)

        self.is_configured = bool(self.api_key and self.use_gemini)

        if not self.is_configured:
            logger.warning(
                "GeminiAlertService: Gemini no configurado. "
                "Usando sistema de plantillas de fallback. "
                "Configure GEMINI_API_KEY en .env para activar el LLM."
            )

    def generate_alert(
        self,
        prediction,
        climate_summary: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Genera una alerta climática completa para una predicción dada.

        Args:
            prediction: Instancia del modelo ClimatePrediction
            climate_summary: Resumen de condiciones climáticas recientes (opcional)

        Returns:
            Diccionario con:
                - alert_level: 'LOW' | 'MEDIUM' | 'HIGH' | 'EXTREME'
                - title: Título de la alerta
                - message_short: Mensaje para SMS/WhatsApp (≤160 chars)
                - message_long: Explicación completa en lenguaje natural
                - agronomic_tips: Lista de recomendaciones agronómicas
                - generated_by: 'gemini-X.X' o 'template_fallback'
        """
        alert_level = self._determine_alert_level(
            prediction.severity_level,
            prediction.anomaly_type
        )

        if self.is_configured:
            try:
                return self._generate_with_gemini(prediction, alert_level, climate_summary)
            except Exception as exc:
                logger.error(
                    "Error al generar alerta con Gemini para predicción %d: %s. "
                    "Usando plantilla de fallback.",
                    prediction.id, exc
                )

        return self._generate_from_template(prediction, alert_level)

    def _determine_alert_level(self, severity_level: int, anomaly_type: str) -> str:
        """Determina el nivel de alerta basado en la severidad y tipo de anomalía."""
        key = (severity_level, anomaly_type)
        return ALERT_LEVEL_MAP.get(key, "MEDIUM")

    def _generate_with_gemini(
        self,
        prediction,
        alert_level: str,
        climate_summary: Optional[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Genera la alerta usando la API de Google Gemini.

        El prompt está diseñado para obtener respuestas en JSON estructurado
        con lenguaje adaptado a productores agrícolas del Departamento de Santa Cruz.
        """
        try:
            import google.generativeai as genai
            genai.configure(api_key=self.api_key)
            model = genai.GenerativeModel(self.model_name)
        except ImportError:
            raise ConnectionError(
                "google-generativeai no instalado. Ejecute: pip install google-generativeai"
            )

        anomaly_labels = {
            "SEQUIA": "Sequía",
            "INUNDACION": "Inundación",
            "NORMAL": "Condiciones Normales",
        }
        anomaly_label = anomaly_labels.get(prediction.anomaly_type, prediction.anomaly_type)
        severity_labels = {1: "Muy Leve", 2: "Leve", 3: "Moderado", 4: "Severo", 5: "Extremo/Catastrófico"}
        severity_label = severity_labels.get(prediction.severity_level, str(prediction.severity_level))

        climate_context = ""
        if climate_summary:
            total_precip = climate_summary.get("total_precipitation_mm")
            temp_avg = climate_summary.get("temperature_2m_mean_avg")
            if total_precip:
                climate_context += f"\n- Precipitación acumulada reciente: {total_precip:.0f} mm"
            if temp_avg:
                climate_context += f"\n- Temperatura media reciente: {temp_avg:.1f}°C"

        prompt = f"""Eres un agrónomo experto en el Departamento de Santa Cruz, Bolivia.
Un sistema de inteligencia artificial basado en modelos LSTM y datos satelitales ha detectado la siguiente predicción climática:

REGIÓN: {prediction.region.name}
TIPO DE ANOMALÍA: {anomaly_label}
NIVEL DE SEVERIDAD: {prediction.severity_level}/5 ({severity_label})
NIVEL DE ALERTA: {alert_level}
CONFIANZA DEL MODELO: {prediction.confidence_score * 100:.1f}%
FECHA OBJETIVO DE LA PREDICCIÓN: {prediction.target_date.strftime('%B %Y')}
{f'CONTEXTO CLIMÁTICO RECIENTE:{climate_context}' if climate_context else ''}

Tu tarea es generar una alerta en español para productores agrícolas bolivianos (muchos con educación básica).
El lenguaje debe ser CLARO, DIRECTO y usar términos que un agricultor entienda.

Genera una respuesta en formato JSON EXACTAMENTE con esta estructura:
{{
    "title": "<Título corto y emotivo, máx 80 chars, incluye emoji>",
    "sms_message": "<Mensaje para WhatsApp, máx 160 chars, lenguaje muy simple>",
    "full_message": "<3 párrafos: 1) Qué pasará, 2) Por qué importa para sus cultivos, 3) Cuándo actuar>",
    "agronomic_tips": [
        "<Acción concreta 1 para el agricultor>",
        "<Acción concreta 2>",
        "<Acción concreta 3>",
        "<Acción concreta 4>",
        "<Acción concreta 5>"
    ]
}}

IMPORTANTE: Responde ÚNICAMENTE con el JSON válido, sin texto adicional ni markdown."""

        logger.info(
            "Enviando solicitud a Gemini (%s) para predicción %d [%s - %s]",
            self.model_name, prediction.id, prediction.region.name, prediction.anomaly_type
        )

        response = model.generate_content(prompt)
        response_text = response.text.strip()

        # Limpia posibles bloques markdown que Gemini a veces añade
        if response_text.startswith("```"):
            lines = response_text.split("\n")
            response_text = "\n".join(lines[1:-1] if lines[-1] == "```" else lines[1:])

        parsed = json.loads(response_text)

        return {
            "alert_level": alert_level,
            "title": parsed.get("title", "Alerta Climática"),
            "message_short": parsed.get("sms_message", "")[:160],
            "message_long": parsed.get("full_message", ""),
            "agronomic_tips": parsed.get("agronomic_tips", []),
            "generated_by": self.model_name,
        }

    def _generate_from_template(
        self,
        prediction,
        alert_level: str,
    ) -> Dict[str, Any]:
        """
        Genera una alerta usando las plantillas predefinidas como fallback.

        Las plantillas están diseñadas para cubrir los casos más comunes y
        proporcionar información útil aunque sin la personalización de Gemini.
        """
        anomaly_type = prediction.anomaly_type
        template_level = alert_level

        # Para NORMAL, máximo nivel disponible en plantillas es MEDIUM
        if anomaly_type == "NORMAL" and alert_level in ("HIGH", "EXTREME"):
            template_level = "MEDIUM"

        templates_for_type = FALLBACK_TEMPLATES.get(anomaly_type, FALLBACK_TEMPLATES["NORMAL"])
        template = templates_for_type.get(template_level, templates_for_type.get("LOW", {}))

        target_str = prediction.target_date.strftime("%B %Y")
        region = prediction.region.name

        title = template.get("title", "Alerta Climática").format(
            region=region, target_date=target_str
        )
        sms = template.get("sms", "").format(
            region=region, target_date=target_str
        )
        tips = template.get("tips", [])

        anomaly_labels = {"SEQUIA": "sequía", "INUNDACION": "inundación", "NORMAL": "condiciones normales"}
        severity_labels = {
            1: "muy leve", 2: "leve", 3: "moderado", 4: "severo", 5: "extremo"
        }
        anomaly_label = anomaly_labels.get(anomaly_type, anomaly_type.lower())
        severity_label = severity_labels.get(prediction.severity_level, "")

        message_long = (
            f"El sistema de predicción climática AgriTech ha detectado un riesgo de {anomaly_label} "
            f"con nivel {severity_label} (severidad {prediction.severity_level}/5) "
            f"para la región {region}, con proyección para {target_str}. "
            f"El modelo de inteligencia artificial otorga una confianza del "
            f"{prediction.confidence_score * 100:.0f}% a esta predicción.\n\n"
            f"Este pronóstico tiene un horizonte de 12 meses de anticipación, "
            f"lo que le da tiempo suficiente para tomar medidas preventivas y proteger "
            f"su producción agrícola.\n\n"
            f"Le recomendamos revisar las acciones sugeridas y mantenerse informado "
            f"a través de las actualizaciones periódicas del sistema."
        )

        logger.info(
            "Alerta generada desde plantilla para predicción %d [%s - %s - %s]",
            prediction.id, region, anomaly_type, alert_level
        )

        return {
            "alert_level": alert_level,
            "title": title,
            "message_short": sms[:160],
            "message_long": message_long,
            "agronomic_tips": tips,
            "generated_by": "template_fallback",
        }
