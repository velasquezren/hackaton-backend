from django.core.management.base import BaseCommand
from django.db import transaction
from climate_intelligence.models import Region, ClimatePrediction
from datetime import date, timedelta
import random

class Command(BaseCommand):
    help = 'Puebla la base de datos con regiones reales de Santa Cruz, Bolivia, y predicciones climáticas simuladas a 12 meses.'

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING('=== Iniciando el Seeder de Inteligencia Climática ==='))

        with transaction.atomic():
            # 1. Limpieza de datos previos para asegurar consistencia
            self.stdout.write('Limpiando base de datos existente...')
            ClimatePrediction.objects.all().delete()
            Region.objects.all().delete()

            # 2. Definición de las 5 regiones agrícolas reales del Departamento de Santa Cruz
            regions_data = [
                {
                    "name": "Norte Integrado",
                    "description": "La zona agroindustrial más productiva de Bolivia (Montero, Minero, Yapacaní). Principal productora de soya, caña de azúcar y arroz. Altamente vulnerable a inundaciones severas por los desbordamientos de los ríos Piraí y Grande en época de lluvias.",
                    "latitude": -17.33,
                    "longitude": -63.25,
                    "main_crops": "Soya, Caña de Azúcar, Arroz, Maíz",
                    "area_hectares": 450000,
                },
                {
                    "name": "Valles Cruceños",
                    "description": "Zona templada y montañosa (Samaipata, Vallegrande, Comarapa). Proveedora clave de hortalizas, frutas y papa para el consumo nacional. Susceptible a sequías agudas, estrés hídrico de invierno y heladas repentinas.",
                    "latitude": -18.48,
                    "longitude": -64.10,
                    "main_crops": "Papa, Tomate, Hortalizas, Frutales",
                    "area_hectares": 85000,
                },
                {
                    "name": "Chiquitania",
                    "description": "Extensa sabana boscosa y ganadera (San Ignacio de Velasco, Concepción, Roboré). Altas temperaturas y vientos secos. Críticamente vulnerable a sequías estacionales severas y a la propagación de incendios forestales incontrolables durante el invierno.",
                    "latitude": -16.37,
                    "longitude": -60.95,
                    "main_crops": "Ganadería Bovina, Sésamo, Sorgo",
                    "area_hectares": 320000,
                },
                {
                    "name": "Chaco Cruceño",
                    "description": "Ecosistema semiárido y ganadero del sur (Camiri, Charagua). Históricamente el área con el mayor déficit hídrico del departamento, registrando sequías extremas recurrentes, desertificación de suelos y alto estrés térmico ganadero.",
                    "latitude": -20.03,
                    "longitude": -63.52,
                    "main_crops": "Ganadería Caprina, Maíz, Sorgo",
                    "area_hectares": 180000,
                },
                {
                    "name": "Pantanal / Germán Busch",
                    "description": "Humedal megadiverso de la frontera este (Puerto Suárez, Puerto Quijarro). Zonas de navegación, puertos e influencia hidrológica del Río Paraguay. Presenta dinámicas cíclicas de inundación estacional y variabilidad en los niveles del río.",
                    "latitude": -18.95,
                    "longitude": -57.80,
                    "main_crops": "Ganadería Bovina, Pesca, Arroz",
                    "area_hectares": 120000,
                }
            ]

            regions = []
            for r_data in regions_data:
                region = Region.objects.create(
                    name=r_data["name"],
                    description=r_data["description"],
                    latitude=r_data["latitude"],
                    longitude=r_data["longitude"],
                    main_crops=r_data["main_crops"],
                    area_hectares=r_data["area_hectares"],
                )
                regions.append(region)
                self.stdout.write(self.style.SUCCESS(f'Región registrada: {region.name} ({region.latitude}, {region.longitude})'))

            # 3. Generación de predicciones mensuales para los siguientes 12 meses
            # Comenzamos desde Junio 2026 hasta Mayo 2027 (lead-time de 12 meses)
            start_date = date(2026, 6, 1)
            prediction_run_date = date(2026, 5, 30) # Fecha de corrida del modelo (Hoy)

            self.stdout.write('\nGenerando predicciones a 12 meses (Junio 2026 - Mayo 2027)...')

            # Definición de anomalías lógicas por mes y región
            for i in range(12):
                # Incremento de mes matemático limpio para evitar redondeos raros de días
                month = start_date.month + i
                year = start_date.year
                if month > 12:
                    year += (month - 1) // 12
                    month = (month - 1) % 12 + 1
                target_date = date(year, month, 1)

                for region in regions:
                    anomaly_type = ClimatePrediction.AnomalyType.NORMAL
                    severity_level = 1
                    confidence_score = round(random.uniform(0.70, 0.96), 2)
                    anomaly_pct = 0.0

                    # Regla Norte Integrado (Época de lluvias: Dic - Mar)
                    if region.name == "Norte Integrado":
                        if target_date.month in [12, 1, 2, 3]:
                            anomaly_type = ClimatePrediction.AnomalyType.INUNDACION
                            severity_level = random.choice([3, 4])
                            anomaly_pct = round(random.uniform(15.0, 35.0), 1) # Porcentaje de exceso de lluvias
                        else:
                            anomaly_type = ClimatePrediction.AnomalyType.NORMAL
                            severity_level = 1
                            anomaly_pct = round(random.uniform(-5.0, 5.0), 1)

                    # Regla Valles Cruceños (Déficit de agua en invierno/primavera: Jun - Oct)
                    elif region.name == "Valles Cruceños":
                        if target_date.month in [6, 7, 8, 9, 10]:
                            anomaly_type = ClimatePrediction.AnomalyType.SEQUIA
                            severity_level = random.choice([3, 4, 5])
                            anomaly_pct = round(random.uniform(-45.0, -20.0), 1) # Déficit de lluvias
                        else:
                            anomaly_type = ClimatePrediction.AnomalyType.NORMAL
                            severity_level = 2
                            anomaly_pct = round(random.uniform(-10.0, 10.0), 1)

                    # Regla Chaco Cruceño (Sequía extrema prolongada)
                    elif region.name == "Chaco Cruceño":
                        if target_date.month in [5, 6, 7, 8, 9, 10, 11]:
                            anomaly_type = ClimatePrediction.AnomalyType.SEQUIA
                            severity_level = random.choice([4, 5])
                            anomaly_pct = round(random.uniform(-55.0, -30.0), 1)
                        else:
                            anomaly_type = ClimatePrediction.AnomalyType.SEQUIA
                            severity_level = 3
                            anomaly_pct = round(random.uniform(-25.0, -10.0), 1)

                    # Regla Chiquitania (Sequía e incendios en época seca: Jul - Oct)
                    elif region.name == "Chiquitania":
                        if target_date.month in [7, 8, 9, 10]:
                            anomaly_type = ClimatePrediction.AnomalyType.SEQUIA
                            severity_level = random.choice([3, 4])
                            anomaly_pct = round(random.uniform(-40.0, -15.0), 1)
                        else:
                            anomaly_type = ClimatePrediction.AnomalyType.NORMAL
                            severity_level = 1
                            anomaly_pct = round(random.uniform(-8.0, 8.0), 1)

                    # Regla Pantanal
                    elif region.name == "Pantanal / Germán Busch":
                        if target_date.month in [1, 2, 3, 4]:
                            anomaly_type = ClimatePrediction.AnomalyType.INUNDACION
                            severity_level = 3
                            anomaly_pct = round(random.uniform(10.0, 25.0), 1)
                        else:
                            anomaly_type = ClimatePrediction.AnomalyType.NORMAL
                            severity_level = 1
                            anomaly_pct = round(random.uniform(-5.0, 5.0), 1)

                    # Telemetría de Vertex AI
                    vertex_ai_output = {
                        "model_id": "AgriTech_DeepLSTM_v4_Bolivia",
                        "validation_metric": "AUC-ROC: 0.94 / F1-Score: 0.91",
                        "features_used": [
                            "Sea_Surface_Temperature_Anomaly_ENSO (ONIv5)",
                            "Soil_Moisture_Deficit_SMAP (10cm)",
                            "NDVI_Vegetation_Deficit_MODIS",
                            "Precipitation_Deficit_CHIRPS",
                            "Air_Temperature_Anomaly_ERA5"
                        ],
                        "calculated_anomaly_pct": anomaly_pct,
                        "epochs_trained": 150,
                        "vertex_endpoint_execution_ms": 234.8
                    }

                    # Registrar la predicción
                    ClimatePrediction.objects.create(
                        region=region,
                        prediction_date=prediction_run_date,
                        target_date=target_date,
                        anomaly_type=anomaly_type,
                        severity_level=severity_level,
                        confidence_score=confidence_score,
                        vertex_ai_output=vertex_ai_output
                    )

            self.stdout.write(self.style.SUCCESS('¡Se han generado y guardado 60 registros de predicción (12 por cada región)!'))
            self.stdout.write(self.style.SUCCESS('=== Seeder ejecutado con Éxito ==='))
