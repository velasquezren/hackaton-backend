"""
Comando de gestión Django para poblar observaciones satelitales mock (NDVI/NDWI)
por región y mes, simulando datos de MODIS/Sentinel-2.

Uso:
    python manage.py seed_satellite_data              # 12 observaciones por región
    python manage.py seed_satellite_data --months 24  # 24 meses hacia atrás
    python manage.py seed_satellite_data --clear      # Limpia datos previos
"""

import random
import math
from datetime import date, timedelta

from django.core.management.base import BaseCommand
from django.db import transaction

from climate_intelligence.models import Region, SatelliteObservation


# Perfiles satelitales base por región (basados en datos reales de MODIS/Sentinel-2)
# NDVI: -1 a 1 (0.2-0.4 = vegetación escasa/estrés; 0.5-0.8 = vegetación densa/sana)
# NDWI: -1 a 1 (negativo = tierra seca; positivo = agua en superficie)
REGIONAL_SATELLITE_PROFILES = {
    "Norte Integrado": {
        "ndvi_base": 0.62,   # Alta productividad agrícola
        "ndwi_base": -0.05,  # Tierra agrícola semi-húmeda
        "ndvi_seasonal": 0.15,  # Variación estacional (mayor en verano lluvioso)
        "ndwi_seasonal": 0.20,  # Gran variación (riesgo de inundación en verano)
    },
    "Valles Cruceños": {
        "ndvi_base": 0.55,
        "ndwi_base": -0.15,  # Más seco en invierno
        "ndvi_seasonal": 0.20,
        "ndwi_seasonal": 0.12,
    },
    "Chiquitania": {
        "ndvi_base": 0.58,   # Sabana boscosa
        "ndwi_base": -0.20,  # Tendencia a sequía severa
        "ndvi_seasonal": 0.18,
        "ndwi_seasonal": 0.15,
    },
    "Chaco Cruceño": {
        "ndvi_base": 0.35,   # Vegetación escasa / semiárido
        "ndwi_base": -0.35,  # Déficit hídrico crónico
        "ndvi_seasonal": 0.12,
        "ndwi_seasonal": 0.08,
    },
    "Pantanal / Germán Busch": {
        "ndvi_base": 0.65,   # Humedal megadiverso
        "ndwi_base": 0.15,   # Alta presencia de agua (río Paraguay)
        "ndvi_seasonal": 0.10,
        "ndwi_seasonal": 0.30,  # Gran variación por ciclo hídrico del Pantanal
    },
}


class Command(BaseCommand):
    help = (
        "Pobla la base de datos con observaciones satelitales mock (NDVI/NDWI) "
        "para todas las regiones de Santa Cruz, con variación estacional realista."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--months", "-m",
            type=int,
            default=12,
            help="Número de meses hacia atrás a generar (por defecto: 12)."
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            default=False,
            help="Eliminar observaciones existentes antes de sembrar."
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING(
            "=== Seeder de Observaciones Satelitales (NDVI/NDWI) ==="
        ))

        regions = list(Region.objects.all())
        if not regions:
            self.stdout.write(
                self.style.ERROR(
                    "No hay regiones registradas. "
                    "Ejecute primero: python manage.py seed_climate_data"
                )
            )
            return

        with transaction.atomic():
            if options["clear"]:
                count = SatelliteObservation.objects.all().delete()[0]
                self.stdout.write(
                    self.style.WARNING(f"🗑️  {count} observaciones eliminadas.")
                )

            total_created = 0
            months = options["months"]

            for region in regions:
                profile = REGIONAL_SATELLITE_PROFILES.get(
                    region.name,
                    {"ndvi_base": 0.50, "ndwi_base": -0.10,
                     "ndvi_seasonal": 0.15, "ndwi_seasonal": 0.12}
                )
                self.stdout.write(f"\n▶ Región: {region.name}")

                for i in range(months):
                    # Fecha de la observación (primer día del mes i meses atrás)
                    obs_date = date.today().replace(day=1) - timedelta(days=30 * i)
                    month = obs_date.month

                    # Factor estacional (ciclo anual sinusoidal: máximo en enero/verano)
                    # Ajustado al hemisferio sur: máximo en enero (mes 1), mínimo en julio (mes 7)
                    season_factor = math.sin(math.pi * (month - 1) / 6)  # -1 a 1

                    # NDVI sube en verano (vegetación activa) y baja en invierno (sequía/sin lluvias)
                    ndvi = profile["ndvi_base"] + profile["ndvi_seasonal"] * season_factor
                    ndvi += random.gauss(0, 0.03)  # ruido gaussiano realista
                    ndvi = round(max(-0.10, min(0.95, ndvi)), 4)

                    # NDWI sube más en invierno en zonas de sequía, y sube en verano en zonas de inundación
                    # Para Pantanal: máximo en verano (ríos crecidos); para Chaco: estable y negativo
                    ndwi = profile["ndwi_base"] + profile["ndwi_seasonal"] * season_factor
                    ndwi += random.gauss(0, 0.02)
                    ndwi = round(max(-0.80, min(0.80, ndwi)), 4)

                    # Cobertura de nubes (mayor en verano lluvioso)
                    cloud_cover = max(0.0, min(100.0,
                        15.0 + 30.0 * max(0, season_factor) + random.uniform(-10, 10)
                    ))

                    obs, created = SatelliteObservation.objects.get_or_create(
                        region=region,
                        obs_date=obs_date,
                        source=SatelliteObservation.DataSource.MOCK,
                        defaults={
                            "ndvi": ndvi,
                            "ndwi": ndwi,
                            "cloud_cover_pct": round(cloud_cover, 1),
                            "raw_data": {
                                "satellite": "MOCK_MODIS_TERRA",
                                "pixel_count": random.randint(800, 1500),
                                "quality_flag": "GOOD",
                                "notes": f"Datos simulados con perfil estacional de {region.name}",
                            }
                        }
                    )

                    if created:
                        total_created += 1
                        self.stdout.write(
                            f"  📡 {obs_date} | NDVI={ndvi:.3f} | NDWI={ndwi:.3f} | ☁️ {cloud_cover:.0f}%"
                        )

            self.stdout.write(
                self.style.SUCCESS(
                    f"\n✅ Seeder completado: {total_created} observaciones satelitales creadas "
                    f"({len(regions)} regiones × ~{months} meses)"
                )
            )
