# 🌾 AgriTech Backend - Platforma de Inteligencia Climática para Santa Cruz, Bolivia

Este es el repositorio base y la infraestructura fundacional para la plataforma AgriTech de predicción climática severa (inundaciones y sequías) con **12 meses de anticipación** en el Departamento de Santa Cruz, Bolivia.

El sistema está diseñado bajo una arquitectura limpia, de alta escalabilidad y desacoplada, utilizando **Django** como framework robusto de persistencia y panel administrativo, junto a **Django Ninja** para servir endpoints RESTful asíncronos y ultrarrápidos listos para ser consumidos por el frontend independiente.

---

## 🚀 Arquitectura y Pila Tecnológica

* **Core Backend:** Python 3.11 + Django 5.0
* **API asíncrona:** [Django Ninja](https://django-ninja.rest-framework.com/) (esquemas Pydantic v2, serialización de alta velocidad, documentación interactiva Swagger integrada).
* **Base de Datos:** PostgreSQL (preparado para **Google Cloud SQL**).
* **Contenedores:** Docker + Docker Compose para consistencia absoluta entre desarrollo y producción.
* **Servidor ASGI de Producción:** **Gunicorn** administrando procesos trabajadores asíncronos de **Uvicorn** (`UvicornWorker`).
* **Optimización de Estáticos:** **WhiteNoise** con compresión Gzip y Brotli, permitiendo servir el Django Admin de forma nativa sin Nginx.
* **Integración de IA:** Preparado para consumir el SDK de **Google Vertex AI**.

---

## 🛠️ Estructura del Proyecto

```text
/home/httpreen/hackaton/
├── config/                      # Ajustes principales del proyecto Django
│   ├── settings.py              # Ajustes de producción, WhiteNoise y CORS
│   ├── urls.py                  # Enrutador principal y montaje de Ninja API
│   ├── asgi.py                  # Entrypoint asíncrono ASGI
│   └── wsgi.py                  # Entrypoint síncrono WSGI
├── climate_intelligence/        # Aplicación de lógica de negocio principal
│   ├── migrations/              # Migraciones de base de datos
│   ├── admin.py                 # Panel de administración premium personalizado
│   ├── api.py                   # Esquemas y endpoints de Django Ninja
│   └── models.py                # Definición de modelos (Region, ClimatePrediction)
├── Dockerfile                   # Dockerfile multi-stage optimizado para GCP
├── docker-compose.yml           # Orquestación de desarrollo local con PostgreSQL
├── entrypoint.sh                # Script de arranque (migración, colecta y ejecución de Gunicorn)
├── requirements.txt             # Librerías y dependencias necesarias con versiones estables
├── .env                         # Variables de entorno activas locales
└── README.md                    # Esta guía completa
```

---

## 💻 Desarrollo Local (Paso a Paso con Docker Compose)

El entorno local viene 100% configurado para levantarse en segundos mediante contenedores.

### 1. Prerrequisitos
* Tener instalado **Docker** y **Docker Compose** en tu máquina.

### 2. Levantar la Aplicación
Ejecuta el siguiente comando en la raíz del proyecto:
```bash
docker compose up --build
```
Este comando realizará las siguientes tareas automáticamente:
1. Descargará y levantará un contenedor de **PostgreSQL 15-alpine** con persistencia de volumen (`postgres_data`).
2. Compilará el contenedor de Django, detectará la disponibilidad de la base de datos de forma segura, recolectará todos los archivos estáticos en `/app/staticfiles` para WhiteNoise y aplicará todas las migraciones necesarias.
3. Iniciará el servidor de desarrollo Django con **Hot Reload** en el puerto `8000`.

### 3. Acceso a la Plataforma
* **API Endpoints:** [http://localhost:8000/api/](http://localhost:8000/api/)
* **Documentación Interactiva (Swagger/OpenAPI):** [http://localhost:8000/api/docs](http://localhost:8000/api/docs)
* **Panel de Administración (Django Admin):** [http://localhost:8000/admin/](http://localhost:8000/admin/)

### 4. Crear Superusuario (para acceder al Admin)
En una nueva terminal, ejecuta:
```bash
docker compose exec web python manage.py createsuperuser
```
Sigue los pasos interactivos para asignar tu correo y contraseña.

---

## 🗺️ Cargar Datos Iniciales de Prueba

Para probar rápidamente el endpoint `/api/predictions/{region_id}`, puedes abrir una consola interactiva de Django y crear registros iniciales:

```bash
docker compose exec web python manage.py shell
```

Dentro del shell interactivo de Python, copia y pega lo siguiente:

```python
from climate_intelligence.models import Region, ClimatePrediction
from datetime import date, timedelta

# 1. Crear Regiones Productivas de Santa Cruz
region_norte = Region.objects.create(
    name="Norte Integrado",
    description="Principal zona productora de soya, maíz y arroz en Santa Cruz. Alta sensibilidad a inundaciones."
)
region_valles = Region.objects.create(
    name="Valles Cruceños",
    description="Zona hortícola y frutícola de altura. Altamente susceptible a sequías prolongadas y heladas."
)

# 2. Crear Predicciones a 12 meses
# Simulación de anomalía severa (Inundación en el Norte Integrado en 12 meses)
ClimatePrediction.objects.create(
    region=region_norte,
    prediction_date=date.today(),
    target_date=date.today() + timedelta(days=365),
    anomaly_type=ClimatePrediction.AnomalyType.INUNDACION,
    severity_level=4,
    confidence_score=0.88,
    vertex_ai_output={
        "model_id": "lstm_climate_predictor_v3_bolivia",
        "features_used": ["anomaly_sea_surface_temp", "la_nina_index", "soil_saturation"],
        "predicted_precipitation_anomaly_pct": +25.4,
        "validation_metric": "MSE: 0.04"
    }
)

# Simulación de sequía en los Valles Cruceños
ClimatePrediction.objects.create(
    region=region_valles,
    prediction_date=date.today(),
    target_date=date.today() + timedelta(days=365),
    anomaly_type=ClimatePrediction.AnomalyType.SEQUIA,
    severity_level=5,
    confidence_score=0.92,
    vertex_ai_output={
        "model_id": "xgboost_climate_drought_v1",
        "features_used": ["spi_index", "ndvi_deficit", "temperature_drift"],
        "predicted_precipitation_anomaly_pct": -42.1,
        "validation_metric": "AUC: 0.94"
    }
)

print("¡Datos de prueba cargados con éxito!")
```

Luego, puedes navegar a [http://localhost:8000/api/predictions/1](http://localhost:8000/api/predictions/1) o usar la interfaz Swagger para consumir los resultados estructurados.

---

## ☁️ Despliegue en Google Cloud Run

**Google Cloud Run** es el entorno Serverless perfecto para este backend asíncrono gracias a su capacidad de escalar a cero cuando no se usa, lo que minimiza costos durante el Hackathon.

### Pasos de Despliegue de Producción

#### 1. Iniciar sesión y seleccionar tu proyecto
```bash
gcloud auth login
gcloud config set project NOMBRE_DE_TU_PROYECTO_GCP
```

#### 2. Crear una Instancia en Google Cloud SQL (PostgreSQL)
Recomendamos crear una base de datos PostgreSQL administrada:
```bash
gcloud sql instances create agritech-db-instance \
    --database-version=POSTGRES_15 \
    --tier=db-f1-micro \
    --region=us-central1
```

Crea la base de datos interna y un usuario seguro:
```bash
gcloud sql databases create agritech --instance=agritech-db-instance
gcloud sql users create django-user --instance=agritech-db-instance --password=CAMBIA_ESTA_CONTRASEÑA
```

#### 3. Proteger Credenciales usando Google Cloud Secret Manager
Evita dejar claves expuestas. Crea un secreto para la cadena de conexión de base de datos (`DATABASE_URL`) y la clave secreta de Django (`SECRET_KEY`):

```bash
# Secreto de Django
echo -n "una-clave-secreta-muy-fuerte-para-produccion-123456" | \
gcloud secrets create DJANGO_SECRET_KEY --data-file=-

# Cadena de conexión PostgreSQL (Usa formato UNIX Socket para conectarte por Cloud SQL Auth Proxy de forma transparente)
# Formato: postgres://usuario:password@/nombre_base_datos?host=/cloudsql/gcp-project:region:instance-name
echo -n "postgres://django-user:CAMBIA_ESTA_CONTRASEÑA@/agritech?host=/cloudsql/NOMBRE_DE_TU_PROYECTO_GCP:us-central1:agritech-db-instance" | \
gcloud secrets create PRODUCTION_DATABASE_URL --data-file=-
```

#### 4. Construir y Desplegar el Contenedor
Utiliza **Google Cloud Build** para compilar el Dockerfile optimizado y desplegarlo directamente a **Cloud Run**:

```bash
# 1. Compila la imagen en la nube usando Cloud Build
gcloud builds submit --tag gcr.io/NOMBRE_DE_TU_PROYECTO_GCP/agritech-backend

# 2. Despliega en Cloud Run inyectando los secretos y conectando a Cloud SQL
gcloud run deploy agritech-backend-service \
    --image gcr.io/NOMBRE_DE_TU_PROYECTO_GCP/agritech-backend \
    --region us-central1 \
    --platform managed \
    --add-cloudsql-instances NOMBRE_DE_TU_PROYECTO_GCP:us-central1:agritech-db-instance \
    --set-secrets="SECRET_KEY=DJANGO_SECRET_KEY:latest,DATABASE_URL=PRODUCTION_DATABASE_URL:latest" \
    --set-env-vars="DEBUG=False,ALLOWED_HOSTS=*,CORS_ALLOW_ALL_ORIGINS=True" \
    --allow-unauthenticated
```

---

## 🧠 Integración con Google Vertex AI

El backend de Django Ninja actúa como el **orquestador**. En lugar de invocar modelos pesados dentro del contenedor de Django, delegas el cálculo a **Vertex AI** utilizando su SDK oficial de Python (incluido en `requirements.txt`).

### Flujo Operativo Recomendado:
1. **Ejecución Batch (Recomendado):** Un script recurrente o Cloud Run Job consulta a Vertex AI una vez al mes, procesa las predicciones a 12 meses para todas las parcelas y almacena los resultados estructurados en la base de datos PostgreSQL.
2. **Inferencia en Tiempo Real:** El endpoint realiza una consulta al SDK de Vertex AI en caliente y formatea la respuesta en milisegundos.

Ejemplo de código para importar en un servicio predictivo (`services.py`):
```python
import os
from google.cloud import aiplatform

def predecir_evento_climatico(datos_meteorologicos: list):
    """
    Invoca un modelo predictivo desplegado en un Endpoint de Google Vertex AI.
    """
    # 1. Inicializa el SDK leyendo credenciales implícitas de la cuenta de servicio de Cloud Run
    aiplatform.init(
        project=os.environ.get("GCP_PROJECT_ID"),
        location=os.environ.get("GCP_LOCATION", "us-central1")
    )
    
    # 2. Obtiene el Endpoint configurado
    endpoint = aiplatform.Endpoint(
        endpoint_name=os.environ.get("VERTEX_AI_ENDPOINT_ID")
    )
    
    # 3. Envía los datos para inferencia (ej. temperatura del mar, humedad del suelo local, viento)
    prediccion = endpoint.predict(instances=datos_meteorologicos)
    
    return prediccion.predictions
```

> [!NOTE]
> Al desplegar en Google Cloud Run, no necesitas archivos JSON de llaves de cuentas de servicio si asignas a la instancia una cuenta de servicio de IAM que tenga el rol de **Vertex AI User** (`roles/aiplatform.user`). Esto se conoce como identidades seguras sin contraseñas (GCP IAM).

---

## 🗺️ Extensión Geoespacial (GeoDjango + PostGIS)

Si quieres destacar en el Hackathon con consultas de mapas reales (ej. *"¿Qué parcelas de soya en el municipio de Yapacaní se inundarán con severidad > 4?"*), te sugerimos actualizar la base de datos a **PostGIS** y usar **GeoDjango**.

### Cómo actualizar este proyecto a PostGIS:
1. **En `requirements.txt`:** Se mantiene igual (`psycopg2-binary` soporta PostGIS perfectamente).
2. **En tu Base de Datos PostgreSQL:** Habilita la extensión ejecutando `CREATE EXTENSION postgis;` (Cloud SQL lo soporta de forma nativa).
3. **En `docker-compose.yml`:** Cambia la imagen del contenedor de base de datos a `postgis/postgis:15-3.3-alpine`.
4. **En el contenedor web (`Dockerfile`):** Instala las librerías geoespaciales requeridas por GeoDjango (`gdal-bin`, `libgdal-dev`, `binutils`, `libproj-dev`). Añádelas en el bloque de `apt-get install`.
5. **En `settings.py`:** Cambia el motor de base de datos a:
   ```python
   DATABASES = {
       'default': env.db('DATABASE_URL', default='postgis://...')
   }
   # Asegúrate de agregar django.contrib.gis en INSTALLED_APPS
   ```
6. **En `models.py`:** Utiliza `from django.contrib.gis.db import models` y añade campos geográficos:
   ```python
   # Ejemplo de campo geométrico de polígono para la región
   geom = models.PolygonField(srid=4326, verbose_name="Límites Geográficos")
   ```

---

## 🧑‍💻 Autores
Estructura fundacional generada con pasión por **Antigravity AI (Google DeepMind Team)** para el Hackathon AgriTech 2026. ¡Mucho éxito en el desarrollo de soluciones sostenibles para Bolivia! 🇧🇴🌾
