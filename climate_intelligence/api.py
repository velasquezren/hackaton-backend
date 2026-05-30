"""
API REST de alta performance para la plataforma AgriTech de Inteligencia Climática.

Construida con django-ninja, genera documentación OpenAPI/Swagger interactiva
automáticamente en /api/docs.

Endpoints disponibles:
    - GET /api/health                               → Estado de salud del servicio
    - GET /api/regions                              → Listado de regiones
    - GET /api/predictions/{region_id}              → Predicciones por región
    - GET /api/predictions/{region_id}/timeline     → Línea temporal de predicciones
    - GET /api/regions/{region_id}/risk-assessment  → Evaluación de riesgo regional
    - GET /api/dashboard/summary                    → Resumen global del dashboard
"""

from datetime import date
from typing import List, Dict, Any, Optional

from django.db.models import Count, Avg, Max, Q, F
from django.shortcuts import get_object_or_404
from django.utils import timezone
from ninja import NinjaAPI, Schema
from ninja.errors import HttpError

from .models import Region, ClimatePrediction

# Instancia principal de NinjaAPI — genera documentación Swagger en /api/docs
api = NinjaAPI(
    title="AgriTech Climate Intelligence API",
    version="1.0.0",
    description="Backend API for climate anomaly predictions in Santa Cruz, Bolivia using Google Vertex AI.",
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

    return {
        "total_regions": total_regions,
        "total_predictions": total_predictions,
        "anomaly_counts": anomaly_counts,
        "highest_severity_prediction": highest_severity_prediction,
        "average_confidence": average_confidence,
        "generated_at": timezone.now().isoformat(),
    }
