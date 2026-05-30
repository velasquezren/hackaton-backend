from datetime import date
from typing import List, Dict, Any, Optional
from django.shortcuts import get_object_or_404
from django.utils import timezone
from ninja import NinjaAPI, Schema
from ninja.errors import HttpError
from .models import Region, ClimatePrediction

# Instantiate high-performance NinjaAPI
# Generates interactive OpenAPI/Swagger docs at /api/docs automatically!
api = NinjaAPI(
    title="AgriTech Climate Intelligence API",
    version="1.0.0",
    description="Backend API for climate anomaly predictions in Santa Cruz, Bolivia using Google Vertex AI.",
)

# --- Pydantic & Ninja Schemas ---

class RegionSchema(Schema):
    id: int
    name: str
    description: str

class ClimatePredictionSchema(Schema):
    id: int
    prediction_date: date
    target_date: date
    anomaly_type: str
    severity_level: int
    confidence_score: float
    vertex_ai_output: Optional[Dict[str, Any]] = None

class RegionPredictionResponse(Schema):
    region: RegionSchema
    predictions: List[ClimatePredictionSchema]
    generated_at: str


# --- Vertex AI Orchestrator Sample Code ---
"""
Guía de Integración con Google Vertex AI:
-----------------------------------------
Para conectar tu modelo predictivo en vivo, puedes usar el SDK oficial de GCP.
A continuación se muestra un ejemplo conceptual de cómo integrarlo en tu lógica:

from google.cloud import aiplatform

def predict_anomaly_with_vertex_ai(region_name: str, historical_data: Dict[str, Any]) -> Dict[str, Any]:
    # Inicializa el cliente con las credenciales de GCP (inyectadas a través de variables de entorno)
    aiplatform.init(
        project=os.environ.get("GCP_PROJECT_ID"),
        location=os.environ.get("GCP_LOCATION", "us-central1")
    )
    
    # Obtiene una referencia al Endpoint desplegado
    endpoint = aiplatform.Endpoint(endpoint_name=os.environ.get("VERTEX_AI_ENDPOINT_ID"))
    
    # Formatea los datos de entrada
    instances = [{
        "region": region_name,
        "temperature_anomaly": historical_data.get("temp"),
        "precipitation_anomaly": historical_data.get("precip"),
        "soil_moisture": historical_data.get("moisture"),
    }]
    
    # Invoca al modelo predictivo
    prediction_response = endpoint.predict(instances=instances)
    
    # Retorna la estructura JSON limpia
    return prediction_response.predictions[0]
"""


# --- API Endpoints ---

@api.get(
    "/predictions/{region_id}",
    response=RegionPredictionResponse,
    summary="Obtiene las predicciones climáticas a 12 meses para una región",
    description="Devuelve el listado de predicciones activas para una región geográfica específica de Santa Cruz, Bolivia."
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
    "/regions",
    response=List[RegionSchema],
    summary="Listar todas las regiones",
    description="Retorna una lista de todas las regiones configuradas en el sistema (ej. Norte Integrado, Valles Cruceños)."
)
def list_regions(request):
    return Region.objects.all()
