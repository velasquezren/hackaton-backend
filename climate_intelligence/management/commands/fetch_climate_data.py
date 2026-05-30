"""
Comando de gestión Django para ingestar datos climáticos históricos desde APIs externas.

Uso:
    python manage.py fetch_climate_data --region "Norte Integrado" --months 12
    python manage.py fetch_climate_data --all-regions --months 6 --source open_meteo
    python manage.py fetch_climate_data --all-regions --months 12 --dry-run
"""

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from climate_intelligence.models import Region, ClimateDataSource
from climate_intelligence.services.climate_data import ClimateDataService
from datetime import date, timedelta


class Command(BaseCommand):
    help = (
        "Ingesta datos climáticos históricos desde Open-Meteo u otras fuentes "
        "para las regiones de Santa Cruz, Bolivia."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--region", "-r",
            type=str,
            default=None,
            help="Nombre de la región a procesar (ej. 'Norte Integrado'). "
                 "Si se omite, use --all-regions."
        )
        parser.add_argument(
            "--all-regions",
            action="store_true",
            default=False,
            help="Procesar todas las regiones registradas en la base de datos."
        )
        parser.add_argument(
            "--months", "-m",
            type=int,
            default=12,
            help="Número de meses hacia atrás a ingestar (por defecto: 12)."
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Simula la operación sin guardar datos en la base de datos."
        )
        parser.add_argument(
            "--force",
            action="store_true",
            default=False,
            help="Sobreescribe datos existentes para las fechas indicadas."
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING(
            "=== Ingestión de Datos Climáticos Históricos ==="
        ))

        # Determinar regiones a procesar
        if options["all_regions"]:
            regions = list(Region.objects.all())
            if not regions:
                raise CommandError(
                    "No hay regiones en la base de datos. "
                    "Ejecute primero: python manage.py seed_climate_data"
                )
        elif options["region"]:
            try:
                regions = [Region.objects.get(name__icontains=options["region"])]
            except Region.DoesNotExist:
                raise CommandError(f"Región '{options['region']}' no encontrada.")
            except Region.MultipleObjectsReturned:
                raise CommandError(
                    f"Múltiples regiones coinciden con '{options['region']}'. "
                    "Use el nombre exacto."
                )
        else:
            raise CommandError(
                "Especifique --region 'Nombre' o --all-regions."
            )

        # Calcular rango de fechas
        end_date = date.today()
        start_date = end_date - timedelta(days=options["months"] * 30)

        self.stdout.write(
            f"Período: {start_date} → {end_date} ({options['months']} meses)"
        )
        self.stdout.write(f"Regiones: {len(regions)}")
        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("MODO DRY-RUN: no se guardarán datos."))

        # Inicializar servicio
        service = ClimateDataService()

        total_saved = 0
        total_skipped = 0
        total_errors = 0

        for region in regions:
            self.stdout.write(f"\n▶ Procesando región: {region.name}")

            try:
                data_records = service.fetch_historical_data(
                    region_name=region.name,
                    start_date=start_date,
                    end_date=end_date,
                )

                if options["dry_run"]:
                    self.stdout.write(
                        self.style.NOTICE(
                            f"  [DRY-RUN] Se generarían {len(data_records)} registros."
                        )
                    )
                    continue

                saved = 0
                skipped = 0

                with transaction.atomic():
                    for record in data_records:
                        source_choice = ClimateDataSource.SourceName.MOCK
                        source_str = record.get("source", "MOCK").upper()
                        if source_str == "OPEN_METEO":
                            source_choice = ClimateDataSource.SourceName.OPEN_METEO
                        elif source_str == "NASA_POWER":
                            source_choice = ClimateDataSource.SourceName.NASA_POWER

                        if options["force"]:
                            obj, created = ClimateDataSource.objects.update_or_create(
                                region=region,
                                source_name=source_choice,
                                variable_name=record["variable_name"],
                                date=record["date"],
                                defaults={
                                    "value": record["value"],
                                    "unit": record["unit"],
                                    "raw_response": record.get("raw_response"),
                                }
                            )
                            if created:
                                saved += 1
                            else:
                                skipped += 1
                        else:
                            _, created = ClimateDataSource.objects.get_or_create(
                                region=region,
                                source_name=source_choice,
                                variable_name=record["variable_name"],
                                date=record["date"],
                                defaults={
                                    "value": record["value"],
                                    "unit": record["unit"],
                                    "raw_response": record.get("raw_response"),
                                }
                            )
                            if created:
                                saved += 1
                            else:
                                skipped += 1

                total_saved += saved
                total_skipped += skipped
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  ✅ {saved} nuevos registros | ⏩ {skipped} ya existían"
                    )
                )

            except Exception as exc:
                total_errors += 1
                self.stdout.write(
                    self.style.ERROR(f"  ❌ Error en '{region.name}': {exc}")
                )

        # Resumen final
        self.stdout.write("\n" + "=" * 50)
        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("Dry-run completado. Ningún dato fue guardado."))
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    f"✅ Ingestión completada:\n"
                    f"   📊 Nuevos registros: {total_saved}\n"
                    f"   ⏩ Ya existían: {total_skipped}\n"
                    f"   ❌ Errores: {total_errors}"
                )
            )
