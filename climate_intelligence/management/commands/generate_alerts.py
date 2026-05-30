"""
Comando de gestión Django para generar alertas climáticas en lenguaje natural
usando Google Gemini o plantillas de fallback.

Uso:
    python manage.py generate_alerts                          # Todas las predicciones sin alerta
    python manage.py generate_alerts --region "Chaco Cruceño"
    python manage.py generate_alerts --min-severity 3
    python manage.py generate_alerts --regenerate             # Regenera alertas existentes también
    python manage.py generate_alerts --dry-run
"""

from django.core.management.base import BaseCommand, CommandError
from climate_intelligence.models import Region, ClimatePrediction, ClimateAlert
from climate_intelligence.services.gemini_service import GeminiAlertService
from climate_intelligence.services.climate_data import ClimateDataService


class Command(BaseCommand):
    help = (
        "Genera alertas climáticas en lenguaje natural (via Gemini o plantillas) "
        "para predicciones que no tienen alerta asociada."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--region", "-r",
            type=str,
            default=None,
            help="Filtrar por nombre de región."
        )
        parser.add_argument(
            "--min-severity", "-s",
            type=int,
            choices=[1, 2, 3, 4, 5],
            default=None,
            help="Solo procesar predicciones con severidad mínima (1-5)."
        )
        parser.add_argument(
            "--anomaly-type", "-a",
            type=str,
            choices=["SEQUIA", "INUNDACION", "NORMAL"],
            default=None,
            help="Filtrar por tipo de anomalía."
        )
        parser.add_argument(
            "--regenerate",
            action="store_true",
            default=False,
            help="Regenerar alertas incluso si ya existen."
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            default=False,
            help="Simula la generación sin guardar en base de datos."
        )

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING(
            "=== Generación de Alertas Climáticas en Lenguaje Natural ==="
        ))

        # Inicializar servicios
        gemini_service = GeminiAlertService()
        climate_service = ClimateDataService()

        if gemini_service.is_configured:
            self.stdout.write(
                self.style.SUCCESS(f"🤖 LLM activo: {gemini_service.model_name}")
            )
        else:
            self.stdout.write(
                self.style.WARNING("📝 Modo plantillas (GEMINI_API_KEY no configurada)")
            )

        # Construir queryset de predicciones
        queryset = ClimatePrediction.objects.select_related("region").all()

        if not options["regenerate"]:
            # Solo predicciones sin alerta
            predictions_with_alert = ClimateAlert.objects.values_list(
                "prediction_id", flat=True
            )
            queryset = queryset.exclude(id__in=predictions_with_alert)

        if options["region"]:
            queryset = queryset.filter(region__name__icontains=options["region"])

        if options["min_severity"]:
            queryset = queryset.filter(severity_level__gte=options["min_severity"])

        if options["anomaly_type"]:
            queryset = queryset.filter(anomaly_type=options["anomaly_type"])

        total = queryset.count()
        if total == 0:
            self.stdout.write(
                self.style.NOTICE(
                    "✅ No hay predicciones pendientes de alerta con los filtros especificados."
                )
            )
            return

        self.stdout.write(f"\n📋 Predicciones a procesar: {total}")
        if options["dry_run"]:
            self.stdout.write(self.style.WARNING("MODO DRY-RUN: no se guardarán alertas."))

        generated = 0
        regenerated = 0
        errors = 0

        for prediction in queryset.order_by("-severity_level", "-confidence_score"):
            region_name = prediction.region.name
            anomaly = prediction.anomaly_type
            severity = prediction.severity_level
            target = prediction.target_date

            self.stdout.write(
                f"\n  → {region_name} | {anomaly} | Sev {severity}/5 | {target}"
            )

            if options["dry_run"]:
                self.stdout.write(
                    self.style.NOTICE("    [DRY-RUN] Se generaría una alerta aquí.")
                )
                generated += 1
                continue

            try:
                # Obtener resumen climático reciente para contexto Gemini
                try:
                    climate_summary = climate_service.get_regional_climate_summary(
                        region_name, months_back=3
                    )
                except Exception:
                    climate_summary = None

                # Generar alerta
                alert_data = gemini_service.generate_alert(prediction, climate_summary)

                # Guardar o actualizar
                try:
                    existing = prediction.alert
                    if options["regenerate"]:
                        existing.alert_level = alert_data["alert_level"]
                        existing.title = alert_data["title"]
                        existing.message_short = alert_data["message_short"]
                        existing.message_long = alert_data["message_long"]
                        existing.agronomic_tips = alert_data["agronomic_tips"]
                        existing.generated_by = alert_data["generated_by"]
                        existing.save()
                        regenerated += 1
                        self.stdout.write(
                            self.style.SUCCESS(
                                f"    ♻️  Regenerada: [{alert_data['alert_level']}] {alert_data['title'][:60]}"
                            )
                        )
                    else:
                        self.stdout.write(
                            self.style.NOTICE("    ⏩ Ya tiene alerta (use --regenerate para actualizar)")
                        )
                except ClimateAlert.DoesNotExist:
                    ClimateAlert.objects.create(
                        prediction=prediction,
                        alert_level=alert_data["alert_level"],
                        title=alert_data["title"],
                        message_short=alert_data["message_short"],
                        message_long=alert_data["message_long"],
                        agronomic_tips=alert_data["agronomic_tips"],
                        generated_by=alert_data["generated_by"],
                    )
                    generated += 1
                    self.stdout.write(
                        self.style.SUCCESS(
                            f"    ✅ Creada: [{alert_data['alert_level']}] {alert_data['title'][:60]}"
                        )
                    )

            except Exception as exc:
                errors += 1
                self.stdout.write(
                    self.style.ERROR(f"    ❌ Error: {exc}")
                )

        # Resumen final
        self.stdout.write("\n" + "=" * 55)
        if not options["dry_run"]:
            self.stdout.write(
                self.style.SUCCESS(
                    f"✅ Proceso completado:\n"
                    f"   🆕 Alertas creadas:     {generated}\n"
                    f"   ♻️  Alertas regeneradas: {regenerated}\n"
                    f"   ❌ Errores:             {errors}"
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING(f"Dry-run: se procesarían {generated} predicciones.")
            )
