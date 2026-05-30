"""
API REST de alta performance para la plataforma AgriTech de Inteligencia Climática.

Construida con django-ninja, genera documentación OpenAPI/Swagger interactiva
automáticamente en /api/docs.

Endpoints disponibles:
    --- Existentes ---
    - GET /api/health                               → Estado de salud del servicio
    - GET /api/regions                              → Listado de regiones
    - GET /api/predictions/{region_id}              → Predicciones por región
    - GET /api/predictions/{region_id}/timeline     → Línea temporal de predicciones
    - GET /api/regions/{region_id}/risk-assessment  → Evaluación de riesgo regional
    - GET /api/dashboard/summary                    → Resumen global del dashboard
    --- Nuevos ---
    - GET  /api/alerts                              → Listado de alertas activas del sistema
    - GET  /api/alerts/{region_id}                  → Alertas de una región específica
    - POST /api/alerts/generate/{prediction_id}     → Genera alerta Gemini para una predicción
    - GET  /api/satellite/{region_id}               → Observaciones satelitales NDVI/NDWI
    - GET  /api/climate-data/{region_id}            → Series de tiempo climáticas históricas
"""

from datetime import date
from typing import List, Dict, Any, Optional

from django.db.models import Count, Avg, Max, Q, F
from django.shortcuts import get_object_or_404
from django.utils import timezone
from ninja import NinjaAPI, Schema
from ninja.errors import HttpError

from .models import Region, ClimatePrediction, ClimateAlert, SatelliteObservation, ClimateDataSource

# Instancia principal de NinjaAPI — genera documentación Swagger en /api/docs
api = NinjaAPI(
    title="AgriTech Climate Intelligence API",
    version="2.0.0",
    description=(
        "API del Sistema de Predicción de Eventos Climáticos Severos para Santa Cruz, Bolivia. "
        "Integra modelos de Vertex AI, datos climáticos históricos (Open-Meteo) y "
        "alertas agronómicas generadas con Google Gemini."
    ),
)


# =============================================================================
# Esquemas Pydantic / Ninja — Definición de estructuras de datos de la API
# =============================================================================

class RegionSchema(Schema):
    """Esquema de serialización para una región geográfica."""
    id: int
    name: str
    description: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    main_crops: Optional[str] = None
    area_hectares: Optional[int] = None


class ClimatePredictionSchema(Schema):
    """Esquema de serialización para una predicción climática individual."""
    id: int
    prediction_date: date
    target_date: date
    anomaly_type: str
    severity_level: int
    confidence_score: float
    vertex_ai_output: Optional[Dict[str, Any]] = None


class RegionPredictionResponse(Schema):
    """Respuesta agrupada de predicciones para una región específica."""
    region: RegionSchema
    predictions: List[ClimatePredictionSchema]
    generated_at: str


# --- Esquemas para el endpoint de salud ---

class HealthResponse(Schema):
    """Respuesta del chequeo de salud del servicio."""
    status: str
    version: str


# --- Esquemas para el resumen del dashboard ---

class AnomalyCountSchema(Schema):
    """Conteo de predicciones agrupadas por tipo de anomalía."""
    anomaly_type: str
    count: int


class HighestSeverityPredictionSchema(Schema):
    """Predicción con el nivel de severidad más alto en el sistema."""
    id: int
    region_name: str
    anomaly_type: str
    severity_level: int
    confidence_score: float
    target_date: date


class DashboardSummaryResponse(Schema):
    """Resumen global del estado de la plataforma para el dashboard principal."""
    total_regions: int
    total_predictions: int
    total_alerts: int
    active_alerts_count: int
    anomaly_counts: List[AnomalyCountSchema]
    highest_severity_prediction: Optional[HighestSeverityPredictionSchema] = None
    average_confidence: Optional[float] = None
    generated_at: str


# --- Esquemas para la línea temporal de predicciones ---

class TimelinePointSchema(Schema):
    """Punto individual en la línea temporal de predicciones."""
    target_date: date
    prediction_date: date
    anomaly_type: str
    severity_level: int
    confidence_score: float


class PredictionTimelineResponse(Schema):
    """Línea temporal cronológica de predicciones para gráficos de evolución."""
    region: RegionSchema
    timeline: List[TimelinePointSchema]
    total_points: int
    generated_at: str


# --- Esquemas para la evaluación de riesgo ---

class RiskBreakdownSchema(Schema):
    """Desglose de riesgo por tipo de anomalía dentro de una región."""
    anomaly_type: str
    count: int
    percentage: float
    avg_severity: Optional[float] = None
    avg_confidence: Optional[float] = None
    max_severity: Optional[int] = None


class RiskAssessmentResponse(Schema):
    """Evaluación detallada de riesgo combinando todas las predicciones de una región."""
    region: RegionSchema
    overall_risk_level: str
    overall_risk_score: float
    total_predictions: int
    avg_severity: Optional[float] = None
    avg_confidence: Optional[float] = None
    max_severity: Optional[int] = None
    risk_breakdown: List[RiskBreakdownSchema]
    latest_prediction_date: Optional[date] = None
    generated_at: str


# =============================================================================
# Endpoints de la API — Controladores HTTP
# =============================================================================

# --- Endpoint de salud ---

@api.get(
    "/health",
    response=HealthResponse,
    summary="Verificación de estado del servicio",
    description="Retorna el estado de salud y la versión actual de la API.",
    tags=["Sistema"],
)
def health_check(request):
    """Chequeo simple de salud para monitoreo y balanceadores de carga."""
    return {"status": "healthy", "version": "1.0.0"}


# --- Endpoints de regiones ---

@api.get(
    "/regions",
    response=List[RegionSchema],
    summary="Listar todas las regiones",
    description="Retorna una lista de todas las regiones configuradas en el sistema (ej. Norte Integrado, Valles Cruceños).",
    tags=["Regiones"],
)
def list_regions(request):
    """Listado completo de regiones geográficas registradas en la plataforma."""
    return Region.objects.all()


@api.get(
    "/regions/{region_id}/risk-assessment",
    response=RiskAssessmentResponse,
    summary="Evaluación de riesgo para una región",
    description=(
        "Genera una evaluación detallada de riesgo climático combinando todas las "
        "predicciones disponibles para una región específica. Incluye desglose por "
        "tipo de anomalía, promedios de severidad y confianza, y un nivel general de riesgo."
    ),
    tags=["Regiones"],
)
def get_region_risk_assessment(request, region_id: int):
    """
    Calcula y retorna la evaluación de riesgo integral para una región.

    El nivel de riesgo general se determina combinando la severidad promedio
    ponderada por la proporción de anomalías detectadas (excluyendo NORMAL).
    """
    # Recupera la región o devuelve HTTP 404
    region = get_object_or_404(Region, id=region_id)

    # Obtiene todas las predicciones de la región
    predictions = region.predictions.all()
    total_predictions = predictions.count()

    if total_predictions == 0:
        # Si no hay predicciones, retorna evaluación vacía
        return {
            "region": region,
            "overall_risk_level": "SIN DATOS",
            "overall_risk_score": 0.0,
            "total_predictions": 0,
            "avg_severity": None,
            "avg_confidence": None,
            "max_severity": None,
            "risk_breakdown": [],
            "latest_prediction_date": None,
            "generated_at": timezone.now().isoformat(),
        }

    # Calcula métricas agregadas globales de la región
    aggregates = predictions.aggregate(
        avg_severity=Avg("severity_level"),
        avg_confidence=Avg("confidence_score"),
        max_severity=Max("severity_level"),
        latest_date=Max("target_date"),
    )

    # Genera el desglose por tipo de anomalía con métricas detalladas
    anomaly_breakdown = (
        predictions
        .values("anomaly_type")
        .annotate(
            count=Count("id"),
            avg_severity=Avg("severity_level"),
            avg_confidence=Avg("confidence_score"),
            max_severity=Max("severity_level"),
        )
        .order_by("-count")
    )

    risk_breakdown = []
    for item in anomaly_breakdown:
        risk_breakdown.append({
            "anomaly_type": item["anomaly_type"],
            "count": item["count"],
            "percentage": round((item["count"] / total_predictions) * 100, 2),
            "avg_severity": round(item["avg_severity"], 2) if item["avg_severity"] else None,
            "avg_confidence": round(item["avg_confidence"], 4) if item["avg_confidence"] else None,
            "max_severity": item["max_severity"],
        })

    # Calcula un puntaje de riesgo compuesto (0-10)
    # Fórmula: promedio ponderado de severidad × proporción de anomalías × confianza
    anomaly_predictions = predictions.exclude(anomaly_type="NORMAL")
    anomaly_count = anomaly_predictions.count()
    anomaly_ratio = anomaly_count / total_predictions if total_predictions > 0 else 0

    if anomaly_count > 0:
        anomaly_agg = anomaly_predictions.aggregate(
            avg_sev=Avg("severity_level"),
            avg_conf=Avg("confidence_score"),
        )
        # Puntaje compuesto: severidad (escala 1-5 → 0-10) × ratio × confianza
        risk_score = round(
            (anomaly_agg["avg_sev"] / 5.0)
            * 10.0
            * anomaly_ratio
            * anomaly_agg["avg_conf"],
            2,
        )
    else:
        risk_score = 0.0

    # Determina el nivel de riesgo textual según el puntaje
    if risk_score >= 7.0:
        risk_level = "CRÍTICO"
    elif risk_score >= 5.0:
        risk_level = "ALTO"
    elif risk_score >= 3.0:
        risk_level = "MODERADO"
    elif risk_score >= 1.0:
        risk_level = "BAJO"
    else:
        risk_level = "MÍNIMO"

    return {
        "region": region,
        "overall_risk_level": risk_level,
        "overall_risk_score": risk_score,
        "total_predictions": total_predictions,
        "avg_severity": round(aggregates["avg_severity"], 2) if aggregates["avg_severity"] else None,
        "avg_confidence": round(aggregates["avg_confidence"], 4) if aggregates["avg_confidence"] else None,
        "max_severity": aggregates["max_severity"],
        "risk_breakdown": risk_breakdown,
        "latest_prediction_date": aggregates["latest_date"],
        "generated_at": timezone.now().isoformat(),
    }


# --- Endpoints de predicciones ---

@api.get(
    "/predictions/{region_id}",
    response=RegionPredictionResponse,
    summary="Obtiene las predicciones climáticas a 12 meses para una región",
    description="Devuelve el listado de predicciones activas para una región geográfica específica de Santa Cruz, Bolivia.",
    tags=["Predicciones"],
)
def get_region_predictions(request, region_id: int):
    """
    Controlador para recuperar predicciones climáticas para una región dada.
    """
    # 1. Recupera la región o retorna un HTTP 404
    region = get_object_or_404(Region, id=region_id)

    # 2. Consulta las predicciones climáticas asociadas a la región, ordenadas cronológicamente
    # En un caso de uso real de AgriTech, podrías filtrar solo las predicciones futuras:
    # predictions = region.predictions.filter(target_date__gte=timezone.now().date())
    predictions = region.predictions.all()

    # 3. Retorna la respuesta serializada y estructurada
    return {
        "region": region,
        "predictions": list(predictions),
        "generated_at": timezone.now().isoformat()
    }


@api.get(
    "/predictions/{region_id}/timeline",
    response=PredictionTimelineResponse,
    summary="Línea temporal de predicciones para gráficos",
    description=(
        "Retorna las predicciones de una región ordenadas cronológicamente por fecha objetivo, "
        "ideal para renderizar gráficos de evolución temporal en el frontend."
    ),
    tags=["Predicciones"],
)
def get_prediction_timeline(request, region_id: int):
    """
    Genera una línea temporal cronológica de predicciones para una región.

    Los puntos se ordenan por target_date ascendente para facilitar su uso
    en gráficos de línea temporal (charts) en el frontend.
    """
    # Recupera la región o devuelve HTTP 404
    region = get_object_or_404(Region, id=region_id)

    # Consulta predicciones ordenadas por fecha objetivo (ascendente para gráficos)
    predictions = (
        region.predictions
        .order_by("target_date", "prediction_date")
        .values(
            "target_date",
            "prediction_date",
            "anomaly_type",
            "severity_level",
            "confidence_score",
        )
    )

    # Construye la lista de puntos de la línea temporal
    timeline = [
        {
            "target_date": p["target_date"],
            "prediction_date": p["prediction_date"],
            "anomaly_type": p["anomaly_type"],
            "severity_level": p["severity_level"],
            "confidence_score": p["confidence_score"],
        }
        for p in predictions
    ]

    return {
        "region": region,
        "timeline": timeline,
        "total_points": len(timeline),
        "generated_at": timezone.now().isoformat(),
    }


# --- Endpoint del dashboard ---

@api.get(
    "/dashboard/summary",
    response=DashboardSummaryResponse,
    summary="Resumen global del dashboard",
    description=(
        "Retorna un resumen integral del estado de la plataforma: total de regiones, "
        "predicciones, distribución por tipo de anomalía, predicción más severa y "
        "confianza promedio global."
    ),
    tags=["Dashboard"],
)
def get_dashboard_summary(request):
    """
    Genera el resumen global de la plataforma para el panel de control principal.

    Agrega datos de todas las regiones y predicciones para ofrecer una vista
    panorámica del estado climático del Departamento de Santa Cruz.
    """
    # Conteo total de regiones y predicciones
    total_regions = Region.objects.count()
    total_predictions = ClimatePrediction.objects.count()

    # Desglose de predicciones por tipo de anomalía
    anomaly_counts_qs = (
        ClimatePrediction.objects
        .values("anomaly_type")
        .annotate(count=Count("id"))
        .order_by("-count")
    )
    anomaly_counts = [
        {"anomaly_type": item["anomaly_type"], "count": item["count"]}
        for item in anomaly_counts_qs
    ]

    # Predicción con la severidad más alta (la más crítica del sistema)
    highest_severity_prediction = None
    most_severe = (
        ClimatePrediction.objects
        .select_related("region")
        .order_by("-severity_level", "-confidence_score")
        .first()
    )
    if most_severe:
        highest_severity_prediction = {
            "id": most_severe.id,
            "region_name": most_severe.region.name,
            "anomaly_type": most_severe.anomaly_type,
            "severity_level": most_severe.severity_level,
            "confidence_score": most_severe.confidence_score,
            "target_date": most_severe.target_date,
        }

    # Confianza promedio global de todas las predicciones
    avg_confidence_result = ClimatePrediction.objects.aggregate(
        avg_conf=Avg("confidence_score")
    )
    average_confidence = (
        round(avg_confidence_result["avg_conf"], 4)
        if avg_confidence_result["avg_conf"] is not None
        else None
    )

    # Conteo de alertas activas del sistema
    total_alerts = ClimateAlert.objects.count()
    active_alerts_count = ClimateAlert.objects.filter(
        alert_level__in=[ClimateAlert.AlertLevel.HIGH, ClimateAlert.AlertLevel.EXTREME]
    ).count()

    return {
        "total_regions": total_regions,
        "total_predictions": total_predictions,
        "total_alerts": total_alerts,
        "active_alerts_count": active_alerts_count,
        "anomaly_counts": anomaly_counts,
        "highest_severity_prediction": highest_severity_prediction,
        "average_confidence": average_confidence,
        "generated_at": timezone.now().isoformat(),
    }


# =============================================================================
# Nuevos Schemas — Alertas Climáticas
# =============================================================================

class AgronomicTipSchema(Schema):
    """Un consejo agronómico individual dentro de una alerta."""
    tip: str


class ClimateAlertSchema(Schema):
    """Esquema de serialización de una alerta climática con recomendaciones agronómicas."""
    id: int
    alert_level: str
    title: str
    message_short: str
    message_long: str
    agronomic_tips: list
    generated_by: str
    is_sent: bool
    created_at: str
    prediction_id: int
    region_name: str
    anomaly_type: str
    target_date: date


class GenerateAlertResponse(Schema):
    """Respuesta al generar o regenerar una alerta climática."""
    alert_id: int
    title: str
    alert_level: str
    message_short: str
    generated_by: str
    is_new: bool


# =============================================================================
# Nuevos Schemas — Observaciones Satelitales
# =============================================================================

class SatelliteObservationSchema(Schema):
    """Esquema de serialización de una observación satelital (NDVI/NDWI)."""
    id: int
    obs_date: date
    ndvi: float
    ndwi: float
    cloud_cover_pct: Optional[float] = None
    source: str


class SatelliteDataResponse(Schema):
    """Respuesta con observaciones satelitales históricas de una región."""
    region: RegionSchema
    observations: List[SatelliteObservationSchema]
    total_observations: int
    latest_ndvi: Optional[float] = None
    latest_ndwi: Optional[float] = None
    generated_at: str


# =============================================================================
# Nuevos Schemas — Datos Climáticos Históricos
# =============================================================================

class ClimateDataPointSchema(Schema):
    """Punto de dato climático individual en la serie temporal."""
    id: int
    variable_name: str
    date: date
    value: float
    unit: str
    source_name: str


class ClimateDataResponse(Schema):
    """Respuesta con serie temporal de datos climáticos de una región."""
    region: RegionSchema
    data_points: List[ClimateDataPointSchema]
    total_records: int
    variables_available: List[str]
    generated_at: str


# =============================================================================
# Nuevos Endpoints — Alertas Climáticas
# =============================================================================

@api.get(
    "/alerts",
    response=List[ClimateAlertSchema],
    summary="Listar todas las alertas climáticas activas",
    description="Retorna todas las alertas generadas por el sistema, ordenadas por nivel de criticidad.",
    tags=["Alertas"],
)
def list_alerts(request, level: Optional[str] = None):
    """
    Lista todas las alertas climáticas del sistema.

    Filtro opcional por nivel: LOW, MEDIUM, HIGH, EXTREME.
    """
    qs = ClimateAlert.objects.select_related("prediction__region").order_by(
        "-created_at"
    )
    if level:
        level_upper = level.upper()
        valid_levels = [c.value for c in ClimateAlert.AlertLevel]
        if level_upper not in valid_levels:
            raise HttpError(400, f"Nivel inválido. Opciones: {', '.join(valid_levels)}")
        qs = qs.filter(alert_level=level_upper)

    results = []
    for alert in qs:
        results.append({
            "id": alert.id,
            "alert_level": alert.alert_level,
            "title": alert.title,
            "message_short": alert.message_short,
            "message_long": alert.message_long,
            "agronomic_tips": alert.agronomic_tips,
            "generated_by": alert.generated_by,
            "is_sent": alert.is_sent,
            "created_at": alert.created_at.isoformat(),
            "prediction_id": alert.prediction.id,
            "region_name": alert.prediction.region.name,
            "anomaly_type": alert.prediction.anomaly_type,
            "target_date": alert.prediction.target_date,
        })
    return results


@api.get(
    "/alerts/{region_id}",
    response=List[ClimateAlertSchema],
    summary="Alertas climáticas de una región específica",
    description="Retorna todas las alertas generadas para las predicciones de una región.",
    tags=["Alertas"],
)
def get_region_alerts(request, region_id: int):
    """Listado de alertas asociadas a todas las predicciones de una región."""
    region = get_object_or_404(Region, id=region_id)
    alerts = ClimateAlert.objects.filter(
        prediction__region=region
    ).select_related("prediction").order_by("-created_at")

    results = []
    for alert in alerts:
        results.append({
            "id": alert.id,
            "alert_level": alert.alert_level,
            "title": alert.title,
            "message_short": alert.message_short,
            "message_long": alert.message_long,
            "agronomic_tips": alert.agronomic_tips,
            "generated_by": alert.generated_by,
            "is_sent": alert.is_sent,
            "created_at": alert.created_at.isoformat(),
            "prediction_id": alert.prediction.id,
            "region_name": region.name,
            "anomaly_type": alert.prediction.anomaly_type,
            "target_date": alert.prediction.target_date,
        })
    return results


@api.post(
    "/alerts/generate/{prediction_id}",
    response=GenerateAlertResponse,
    summary="Genera alerta en lenguaje natural para una predicción",
    description=(
        "Invoca Google Gemini para generar una alerta agronómica personalizada "
        "para la predicción indicada. Si la alerta ya existe, la regenera. "
        "Si Gemini no está configurado, usa plantillas de fallback."
    ),
    tags=["Alertas"],
)
def generate_prediction_alert(request, prediction_id: int):
    """
    Genera o regenera una alerta climática para una predicción usando Gemini.
    """
    from .services.gemini_service import GeminiAlertService
    from .services.climate_data import ClimateDataService

    prediction = get_object_or_404(ClimatePrediction, id=prediction_id)
    is_new = not hasattr(prediction, 'alert') or prediction.alert is None

    # Obtener resumen climático reciente como contexto para Gemini
    climate_service = ClimateDataService()
    try:
        climate_summary = climate_service.get_regional_climate_summary(
            prediction.region.name, months_back=3
        )
    except Exception:
        climate_summary = None

    # Generar la alerta
    gemini_service = GeminiAlertService()
    alert_data = gemini_service.generate_alert(prediction, climate_summary)

    # Guardar o actualizar en base de datos
    try:
        existing_alert = prediction.alert
        existing_alert.alert_level = alert_data["alert_level"]
        existing_alert.title = alert_data["title"]
        existing_alert.message_short = alert_data["message_short"]
        existing_alert.message_long = alert_data["message_long"]
        existing_alert.agronomic_tips = alert_data["agronomic_tips"]
        existing_alert.generated_by = alert_data["generated_by"]
        existing_alert.save()
        saved_alert = existing_alert
        is_new = False
    except ClimateAlert.DoesNotExist:
        from .models import ClimateAlert as ClimateAlertModel
        saved_alert = ClimateAlertModel.objects.create(
            prediction=prediction,
            **{k: v for k, v in alert_data.items()}
        )
        is_new = True

    return {
        "alert_id": saved_alert.id,
        "title": saved_alert.title,
        "alert_level": saved_alert.alert_level,
        "message_short": saved_alert.message_short,
        "generated_by": saved_alert.generated_by,
        "is_new": is_new,
    }


# =============================================================================
# Nuevos Endpoints — Observaciones Satelitales
# =============================================================================

@api.get(
    "/satellite/{region_id}",
    response=SatelliteDataResponse,
    summary="Observaciones satelitales NDVI/NDWI de una región",
    description=(
        "Retorna el histórico de observaciones satelitales (NDVI y NDWI) para una región. "
        "NDVI indica salud de vegetación; NDWI indica presencia de agua en superficie."
    ),
    tags=["Monitoreo Satelital"],
)
def get_satellite_observations(request, region_id: int):
    """
    Histórico de índices satelitales NDVI y NDWI para una región.

    útil para detectar erósion de vegetación por sequía o anegamiento
    por inundación con anticipación a los eventos climáticos.
    """
    region = get_object_or_404(Region, id=region_id)
    observations = SatelliteObservation.objects.filter(
        region=region
    ).order_by("-obs_date")[:24]  # Últimas 24 observaciones

    obs_list = []
    latest_ndvi = None
    latest_ndwi = None

    for i, obs in enumerate(observations):
        if i == 0:
            latest_ndvi = obs.ndvi
            latest_ndwi = obs.ndwi
        obs_list.append({
            "id": obs.id,
            "obs_date": obs.obs_date,
            "ndvi": obs.ndvi,
            "ndwi": obs.ndwi,
            "cloud_cover_pct": obs.cloud_cover_pct,
            "source": obs.source,
        })

    return {
        "region": region,
        "observations": obs_list,
        "total_observations": len(obs_list),
        "latest_ndvi": latest_ndvi,
        "latest_ndwi": latest_ndwi,
        "generated_at": timezone.now().isoformat(),
    }


# =============================================================================
# Nuevos Endpoints — Datos Climáticos Históricos
# =============================================================================

@api.get(
    "/climate-data/{region_id}",
    response=ClimateDataResponse,
    summary="Series de tiempo climáticas históricas de una región",
    description=(
        "Retorna los datos climáticos históricos ingestados desde Open-Meteo, NASA POWER "
        "u otras fuentes. Filtrable por variable (ej. precipitation_sum, temperature_2m_max)."
    ),
    tags=["Datos Climáticos"],
)
def get_climate_data(request, region_id: int, variable: Optional[str] = None, limit: int = 365):
    """
    Serie temporal de datos climáticos históricos para una región.

    Args:
        region_id: ID de la región
        variable: Nombre de la variable a filtrar (ej. precipitation_sum)
        limit: Máximo de registros a retornar (por defecto 365)
    """
    region = get_object_or_404(Region, id=region_id)
    qs = ClimateDataSource.objects.filter(region=region).order_by("-date")

    if variable:
        qs = qs.filter(variable_name=variable)

    qs = qs[:limit]

    data_points = []
    variables_seen = set()
    for record in qs:
        variables_seen.add(record.variable_name)
        data_points.append({
            "id": record.id,
            "variable_name": record.variable_name,
            "date": record.date,
            "value": record.value,
            "unit": record.unit,
            "source_name": record.source_name,
        })

    return {
        "region": region,
        "data_points": data_points,
        "total_records": len(data_points),
        "variables_available": sorted(list(variables_seen)),
        "generated_at": timezone.now().isoformat(),
    }
