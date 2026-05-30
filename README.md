# 🌾 AgriTech - Plataforma de Inteligencia Climática (Backend)

Este repositorio contiene el backend de alto rendimiento para **AgriTech**, una plataforma de inteligencia climática diseñada para predecir anomalías climáticas severas (como sequías e inundaciones) con **12 meses de anticipación** en las 5 regiones agrícolas clave del **Departamento de Santa Cruz, Bolivia**.

La solución está construida sobre **Django 5.0** y **Django-Ninja**, e integra modelos de Machine Learning avanzados consumidos desde **Google Vertex AI** (o mediante un simulador local realista). Está dockerizada y lista para producción en entornos Serverless como **Google Cloud Run**.

---

## 🏗️ Arquitectura General del Sistema

El backend sigue un diseño modular y desacoplado, combinando la robustez de Django con la velocidad de ejecución asíncrona de Django-Ninja (inspirado en FastAPI) y la potencia analítica de Google Cloud.

```mermaid
graph TD
    subgraph Frontend / Clientes
        A[Dashboard Web / Mobile] -->|Consultas HTTP REST| B[Django Ninja API /api/]
        A -->|Administración| C[Panel Django Admin /admin/]
    end

    subgraph Backend Core (Django)
        B -->|Controladores REST| D[climate_intelligence/api.py]
        C -->|Dashboard & Badges| E[climate_intelligence/admin.py]
        
        D -->|Consultas ORM| F[(PostgreSQL / SQLite)]
        E -->|Consultas ORM| F
        
        G[VertexAIService] -->|Predicción Real/Mock| D
        H[CLI Commands: seed / export] -->|Operaciones Masivas| F
    end

    subgraph Nube & IA (Google Cloud)
        G -->|SDK google-cloud-aiplatform| I[Google Vertex AI Endpoints]
    end
    
    style A fill:#f9f,stroke:#333,stroke-width:2px
    style I fill:#4285F4,stroke:#333,stroke-width:2px
    style F fill:#336791,stroke:#333,stroke-width:2px
    style G fill:#34A853,stroke:#333,stroke-width:2px
```

---

## 📂 Estructura del Proyecto

El código está estructurado de la siguiente manera:

```text
hackaton-backend/
│
├── config/                         # Configuración central de Django
│   ├── settings.py                 # Variables, bases de datos, middlewares (WhiteNoise, CORS)
│   ├── urls.py                     # Enrutador principal (muta /admin y /api)
│   └── asgi.py & wsgi.py           # Puntos de entrada para servidores asíncronos y síncronos
│
├── climate_intelligence/           # Aplicación principal de la plataforma
│   ├── models.py                   # Modelos de base de datos (Regiones y Predicciones)
│   ├── api.py                      # Endpoints REST estructurados con Django-Ninja (Pydantic schemas)
│   ├── admin.py                    # Extensión avanzada del panel Django Admin + Dashboard
│   ├── services/
│   │   └── vertex_ai.py            # Servicio de integración con Google Vertex AI (Real / Mock)
│   ├── management/
│   │   └── commands/
│   │       ├── seed_climate_data.py # Inicializador de base de datos con datos geográficos reales
│   │       └── export_predictions.py # CLI para exportar reportes filtrados a CSV
│   └── templates/
│       └── admin/
│           └── climate_dashboard.html # Plantilla HTML del dashboard analítico del Administrador
│
├── Dockerfile                      # Empaquetado optimizado para Google Cloud Run (Slim, sin privilegios)
├── docker-compose.yml              # Orquestador local multi-contenedor (Django + PostgreSQL)
├── entrypoint.sh                   # Script de arranque (espera a DB, migra, recolecta estáticos, gunicorn)
├── requirements.txt                # Dependencias del sistema
└── .env.example                    # Plantilla de configuración de variables de entorno
```

---

## 🔍 Análisis Detallado de Componentes

### 1. Modelos de Datos (`climate_intelligence/models.py`)
Define la estructura persistente del negocio utilizando el ORM de Django:
*   **`Region`**: Representa una región geográfica o agrícola en Santa Cruz. Contiene campos como `name` (ej. *Norte Integrado*, *Chiquitania*) y `description`.
*   **`ClimatePrediction`**: Almacena las predicciones climáticas severas.
    *   **Tipo de anomalía (`anomaly_type`)**: Un campo `TextChoices` con opciones `SEQUIA` (Sequía), `INUNDACION` (Inundación) o `NORMAL` (Sin anomalías).
    *   **Fechas**: `prediction_date` (cuándo se ejecutó el modelo) y `target_date` (mes objetivo futuro, típicamente a 12 meses).
    *   **Métricas**: `severity_level` (escala 1 a 5 con validadores) y `confidence_score` (probabilidad/certeza de 0.0 a 1.0).
    *   **Payload crudo de IA (`vertex_ai_output`)**: Un campo `JSONField` que almacena la respuesta completa devuelta por Vertex AI para auditorías (ej. importancia de características, versión del modelo, etc.).
    *   *Restricción*: Evita la duplicación mediante una restricción única `unique_together = ('region', 'target_date', 'prediction_date')`.

### 2. Integración con Google Vertex AI (`climate_intelligence/services/vertex_ai.py`)
Módulo encargado de consumir los modelos predictivos de Machine Learning. Cuenta con dos modos de operación inteligentes:
*   **Modo Producción (`_predict_real`)**: 
    1. Importa dinámicamente el SDK oficial (`google.cloud.aiplatform`).
    2. Inicializa la conexión con el proyecto GCP (`GCP_PROJECT_ID`) en la ubicación configurada (`GCP_LOCATION`).
    3. Construye el payload de entrada con variables como anomalías de temperatura, déficit de precipitación, humedad del suelo, etc.
    4. Consulta el endpoint desplegado (`VERTEX_AI_ENDPOINT_ID`) de forma síncrona y retorna la predicción.
*   **Modo Desarrollo (`mock_predict`)**: Se activa automáticamente si las variables de entorno de producción no están configuradas. Genera predicciones climáticas realistas mediante **perfiles de probabilidad ponderados** basados en el comportamiento real de cada región:
    *   *Chaco Cruceño*: Propensión muy alta a Sequías (50%).
    *   *Pantanal*: Propensión alta a Inundaciones (50%).
    *   *Norte Integrado*: Clima balanceado (35% Inundación, 30% Sequía).
    *   Calcula de forma automática la importancia aleatoria de variables y metadatos simulados de entrenamiento.

### 3. API REST de Alta Performance (`climate_intelligence/api.py`)
Construida con **Django-Ninja**, la cual utiliza validación de tipos nativa mediante **Pydantic** y genera documentación Swagger/OpenAPI interactiva instantánea en `/api/docs`.

| Método | Endpoint | Descripción | Funcionalidad Clave |
| :--- | :--- | :--- | :--- |
| **GET** | `/api/health` | Chequeo de estado | Comprobación de salud para balanceadores de carga. |
| **GET** | `/api/regions` | Listar Regiones | Retorna la lista completa de las 5 regiones agrícolas. |
| **GET** | `/api/predictions/{id}` | Predicciones de Región | Retorna las predicciones vigentes de una región específica. |
| **GET** | `/api/predictions/{id}/timeline` | Gráficos de Línea Temporal | Retorna las predicciones ordenadas cronológicamente para charts. |
| **GET** | `/api/dashboard/summary` | Resumen Global | Consolida conteos de anomalías, promedios de confianza y la predicción más severa actual. |
| **GET** | `/api/regions/{id}/risk-assessment` | Evaluación de Riesgo | **Algoritmo Compuesto**: Calcula un puntaje de riesgo de `0.0` a `10.0` basado en severidad promedio de anomalías, la tasa de frecuencia y la confianza del modelo. Determina niveles textuales (*CRÍTICO, ALTO, MODERADO, BAJO, MÍNIMO*). |

### 4. Consola de Administración y Visualización (`climate_intelligence/admin.py` & templates)
El Panel de Administración tradicional de Django fue repotenciado para actuar como un completo centro de control:
*   **Dashboard Personalizado (`/admin/climate-dashboard/`)**: Inyecta una vista HTML (`climate_dashboard.html`) estilizada dentro del panel de administración que muestra KPIs agregados (Regiones, Predicciones, Severidad Promedio, Confianza) y un desglose interactivo de anomalías con badges visuales.
*   **Badges Dinámicos en Listados**:
    *   **Anomalía**: Badges coloreados según el tipo (Naranja para Sequía, Azul para Inundación, Verde para Normal).
    *   **Severidad**: Una barra de progreso horizontal que va de verde (leve) a rojo (extremo) según el nivel 1-5.
    *   **Confianza**: Formateado en porcentaje (ej. `85.4%`) con alertas cromáticas según el umbral.
*   **Acción Masiva de Exportación**: Permite seleccionar múltiples predicciones en el listado y exportarlas a un archivo CSV formateado de forma nativa para Excel en español (codificación `utf-8-sig` con BOM).

### 5. Herramientas CLI (`climate_intelligence/management/commands/`)
*   **`seed_climate_data`**: Inicializa la base de datos limpiándola previamente. Inserta las 5 regiones reales con descripciones productivas y genera automáticamente **60 predicciones simuladas** (12 meses por región) siguiendo las reglas lógicas del clima cruceño estacional (ej. inundaciones en el Norte Integrado durante el verano austral).
*   **`export_predictions`**: Exporta los registros a un archivo CSV con filtros CLI sumamente flexibles:
    ```bash
    python manage.py export_predictions --region "Valles Cruceños" --anomaly-type SEQUIA --min-severity 3 --output valles_sequias_criticas.csv
    ```

---

## 🐳 Infraestructura, Despliegue y DevOps

### Desarrollo Local (Docker Compose)
El backend cuenta con una configuración dockerizada de dos capas (Aplicación + Base de datos PostgreSQL):
*   La base de datos expone el puerto `5432` y persiste los archivos en un volumen local (`postgres_data`).
*   El contenedor `web` sincroniza en caliente el código del host (`hot-reload`) y arranca en el puerto `8000`.

### Despliegue de Producción (Google Cloud Run)
La configuración del `Dockerfile` y `entrypoint.sh` está optimizada para la infraestructura serverless de Google:
1.  **Seguridad**: Crea y ejecuta la app bajo un usuario de sistema no privilegiado (`appuser:8888`).
2.  **Eficiencia de Estáticos**: Utiliza **WhiteNoise** con almacenamiento comprimido (Brotli/Gzip) para servir CSS/JS sin requerir un Nginx separado.
3.  **Resiliencia de Conexión**: `entrypoint.sh` contiene un script embebido en Python que realiza un bucle de comprobación activa (*polling*) para verificar si la base de datos PostgreSQL remota (o Cloud SQL) está completamente en línea antes de aplicar migraciones estructurales automáticas (`python manage.py migrate`).
4.  **Servidor de Alto Rendimiento**: Inicia el servidor mediante **Gunicorn** administrando múltiples hilos de ejecución **Uvicorn** (`uvicorn.workers.UvicornWorker`), ideal para el procesamiento concurrente asíncrono que requiere Django-Ninja.

---

## 🛠️ Cómo Iniciar y Configurar el Proyecto

### 1. Clonar y Configurar Variables de Entorno
Crea un archivo `.env` en la raíz del backend basado en `.env.example`:
```bash
cp .env.example .env
```
*Asegúrate de ajustar los parámetros de Google Vertex AI si vas a conectar la aplicación a un endpoint real.*

### 2. Iniciar con Docker Compose
Para descargar las imágenes, compilar y ejecutar los contenedores:
```bash
docker-compose up --build
```
Este comando levantará la base de datos PostgreSQL, esperará su inicialización, aplicará las migraciones y expondrá la API en `http://localhost:8000`.

### 3. Poblar la Base de Datos (Seeder)
Abre otra consola y ejecuta el seeder para poblar las regiones y predicciones simuladas a 12 meses:
```bash
docker-compose exec web python manage.py seed_climate_data
```

### 4. Acceder a las Interfaces
*   **Documentación Interactiva de la API**: [http://localhost:8000/api/docs](http://localhost:8000/api/docs)
*   **Panel de Administración de Django**: [http://localhost:8000/admin/](http://localhost:8000/admin/)
*   **Dashboard Climático del Admin**: [http://localhost:8000/admin/climate-dashboard/](http://localhost:8000/admin/climate-dashboard/)

---

> [!TIP]
> **Crear Superusuario Administrativo**  
> Para iniciar sesión en el panel `/admin`, puedes crear un superusuario interactivo ejecutando:  
> `docker-compose exec web python manage.py createsuperuser`
