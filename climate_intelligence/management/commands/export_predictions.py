"""
Comando de gestión Django para exportar todas las predicciones climáticas a CSV.

Uso:
    python manage.py export_predictions
    python manage.py export_predictions --output /ruta/personalizada/archivo.csv
    python manage.py export_predictions --region "Norte Integrado"
    python manage.py export_predictions --anomaly-type SEQUIA
    python manage.py export_predictions --min-severity 3

El archivo CSV generado incluye BOM para compatibilidad con Excel en español.
"""

import csv
import os

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from climate_intelligence.models import ClimatePrediction


class Command(BaseCommand):
    """Exporta predicciones climáticas a un archivo CSV con filtros opcionales."""

    help = (
        "Exporta todas las predicciones climáticas de la plataforma AgriTech a un archivo CSV. "
        "Permite filtrar por región, tipo de anomalía y nivel mínimo de severidad."
    )

    def add_arguments(self, parser):
        """Define los argumentos opcionales del comando."""
        parser.add_argument(
            "--output",
            "-o",
            type=str,
            default=None,
            help=(
                "Ruta del archivo CSV de salida. "
                "Por defecto: predicciones_climaticas_YYYYMMDD_HHMMSS.csv"
            ),
        )
        parser.add_argument(
            "--region",
            "-r",
            type=str,
            default=None,
            help="Filtrar por nombre de región (ej. 'Norte Integrado')",
        )
        parser.add_argument(
            "--anomaly-type",
            "-a",
            type=str,
            choices=["SEQUIA", "INUNDACION", "NORMAL"],
            default=None,
            help="Filtrar por tipo de anomalía: SEQUIA, INUNDACION o NORMAL",
        )
        parser.add_argument(
            "--min-severity",
            "-s",
            type=int,
            choices=[1, 2, 3, 4, 5],
            default=None,
            help="Filtrar predicciones con severidad mínima (1-5)",
        )

    def handle(self, *args, **options):
        """Ejecuta la exportación de predicciones a CSV con los filtros indicados."""
        # Inicia con todas las predicciones, optimizando la consulta con select_related
        queryset = ClimatePrediction.objects.select_related("region").all()

        # Aplica filtro por región si se especificó
        if options["region"]:
            queryset = queryset.filter(region__name__icontains=options["region"])
            self.stdout.write(
                self.style.NOTICE(f"🔍 Filtrando por región: '{options['region']}'")
            )

        # Aplica filtro por tipo de anomalía si se especificó
        if options["anomaly_type"]:
            queryset = queryset.filter(anomaly_type=options["anomaly_type"])
            self.stdout.write(
                self.style.NOTICE(f"🔍 Filtrando por anomalía: {options['anomaly_type']}")
            )

        # Aplica filtro por severidad mínima si se especificó
        if options["min_severity"]:
            queryset = queryset.filter(severity_level__gte=options["min_severity"])
            self.stdout.write(
                self.style.NOTICE(
                    f"🔍 Filtrando por severidad mínima: {options['min_severity']}"
                )
            )

        # Ordena por región y fecha objetivo para un CSV bien organizado
        queryset = queryset.order_by("region__name", "target_date", "prediction_date")

        # Verifica que existan predicciones que exportar
        total = queryset.count()
        if total == 0:
            self.stdout.write(
                self.style.WARNING(
                    "⚠️  No se encontraron predicciones con los filtros especificados."
                )
            )
            return

        # Genera nombre de archivo por defecto con marca de tiempo
        if options["output"]:
            output_path = options["output"]
        else:
            timestamp = timezone.now().strftime("%Y%m%d_%H%M%S")
            output_path = f"predicciones_climaticas_{timestamp}.csv"

        # Asegura que el directorio destino exista
        output_dir = os.path.dirname(output_path)
        if output_dir and not os.path.exists(output_dir):
            os.makedirs(output_dir, exist_ok=True)
            self.stdout.write(
                self.style.NOTICE(f"📁 Directorio creado: {output_dir}")
            )

        self.stdout.write(
            self.style.NOTICE(f"📊 Exportando {total} predicciones a: {output_path}")
        )

        # Escribe el archivo CSV con cabecera BOM para compatibilidad con Excel
        try:
            with open(output_path, "w", newline="", encoding="utf-8-sig") as csvfile:
                writer = csv.writer(csvfile)

                # Cabecera con nombres descriptivos en español
                writer.writerow([
                    "ID",
                    "Región",
                    "Fecha de Predicción",
                    "Fecha Objetivo",
                    "Tipo de Anomalía",
                    "Tipo de Anomalía (Código)",
                    "Nivel de Severidad",
                    "Confianza",
                    "Confianza (%)",
                    "Creado el",
                    "Actualizado el",
                ])

                # Escribe cada predicción como una fila del CSV
                exported_count = 0
                for prediction in queryset.iterator(chunk_size=500):
                    writer.writerow([
                        prediction.id,
                        prediction.region.name,
                        prediction.prediction_date.isoformat(),
                        prediction.target_date.isoformat(),
                        prediction.get_anomaly_type_display(),
                        prediction.anomaly_type,
                        prediction.severity_level,
                        f"{prediction.confidence_score:.4f}",
                        f"{prediction.confidence_score * 100:.1f}%",
                        prediction.created_at.strftime("%Y-%m-%d %H:%M:%S"),
                        prediction.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
                    ])
                    exported_count += 1

            # Obtiene el tamaño del archivo generado
            file_size = os.path.getsize(output_path)
            file_size_kb = file_size / 1024

            self.stdout.write(
                self.style.SUCCESS(
                    f"✅ Exportación completada exitosamente:\n"
                    f"   📄 Archivo: {output_path}\n"
                    f"   📊 Registros: {exported_count}\n"
                    f"   💾 Tamaño: {file_size_kb:.1f} KB"
                )
            )

        except PermissionError:
            raise CommandError(
                f"❌ Sin permisos de escritura en: {output_path}"
            )
        except OSError as exc:
            raise CommandError(
                f"❌ Error al escribir el archivo CSV: {exc}"
            )
