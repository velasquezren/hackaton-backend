"""
Comando de gestión Django para poblar observaciones satelitales (NDVI/NDWI)
por región y mes, usando Google Earth Engine (real) o datos simulados (mock).

Uso:
    python manage.py seed_satellite_data              # 12 observaciones por región
    python manage.py seed_satellite_data --months 24  # 24 meses hacia atrás
    python manage.py seed_satellite_data --clear      # Limpia datos previos
"""

from datetime import date, timedelta

from django.core.management.base import BaseCommand
from django.db import transaction

from climate_intelligence.models import Region, SatelliteObservation


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

            # Inicializar el servicio de Earth Engine
            from climate_intelligence.services import EarthEngineService
            ee_service = EarthEngineService()

            for region in regions:
                self.stdout.write(f"\n▶ Región: {region.name}")

                for i in range(months):
                    # Fecha de la observación (primer día del mes i meses atrás)
                    obs_date = date.today().replace(day=1) - timedelta(days=30 * i)

                    # Coordenadas por defecto si no están definidas
                    lat = region.latitude or -17.7830
                    lon = region.longitude or -63.1820

                    # Obtener los datos reales (o mock) del servicio
                    sat_data = ee_service.fetch_satellite_indices(
                        region_name=region.name,
                        lat=lat,
                        lon=lon,
                        target_date=obs_date
                    )

                    ndvi = sat_data["ndvi"]
                    ndwi = sat_data["ndwi"]
                    cloud_cover = sat_data["cloud_cover_pct"]
                    source = sat_data["source"]

                    # Determinar qué etiqueta de fuente de datos del modelo guardar
                    db_source = SatelliteObservation.DataSource.MOCK
                    if source == "SENTINEL_2":
                        db_source = SatelliteObservation.DataSource.SENTINEL2
                    elif source == "MODIS":
                        db_source = SatelliteObservation.DataSource.MODIS

                    obs, created = SatelliteObservation.objects.get_or_create(
                        region=region,
                        obs_date=obs_date,
                        source=db_source,
                        defaults={
                            "ndvi": ndvi,
                            "ndwi": ndwi,
                            "cloud_cover_pct": cloud_cover,
                            "raw_data": {
                                "satellite": source,
                                "quality_flag": "GOOD" if not sat_data.get("error") else "ERROR_FALLBACK",
                                "notes": sat_data.get("error") or f"Datos procesados mediante {source} para la región {region.name}",
                            }
                        }
                    )

                    if created:
                        total_created += 1
                        self.stdout.write(
                            f"  📡 {obs_date} | Fuente: {source} | NDVI={ndvi:.3f} | NDWI={ndwi:.3f} | ☁️ {cloud_cover:.0f}%"
                        )

            self.stdout.write(
                self.style.SUCCESS(
                    f"\n✅ Seeder completado: {total_created} observaciones satelitales creadas "
                    f"({len(regions)} regiones × ~{months} meses)"
                )
            )
