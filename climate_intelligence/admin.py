"""
Panel de administración avanzado para la plataforma AgriTech de Inteligencia Climática.

Incluye:
    - Dashboard personalizado con métricas globales
    - Gestión visual de regiones con conteo de predicciones
    - Gestión de predicciones con badges de anomalía, barras de severidad y confianza
    - Exportación masiva a CSV
    - Jerarquía de fechas para navegación temporal
"""

import csv
from django.contrib import admin
from django.db.models import Count, Avg, Max
from django.http import HttpResponse
from django.template.response import TemplateResponse
from django.urls import path
from django.utils import timezone
from django.utils.html import format_html
import json

from .models import Region, ClimatePrediction


# =============================================================================
# Personalización global del sitio de administración
# =============================================================================

admin.site.site_header = "AgriTech - Inteligencia Climática"
admin.site.site_title = "AgriTech Admin"
admin.site.index_title = "Panel de Control — Predicciones Climáticas · Santa Cruz, Bolivia"


# =============================================================================
# Clase personalizada del AdminSite para inyectar el dashboard
# =============================================================================

class ClimateAdminSite(admin.AdminSite):
    """
    Sitio de administración extendido con dashboard de métricas climáticas.

    Nota: Se utiliza el sitio por defecto de Django y se extiende a través
    de get_urls() para mantener compatibilidad total con el registro existente.
    """

    def get_urls(self):
        """Agrega la URL del dashboard personalizado al panel de administración."""
        custom_urls = [
            path(
                "climate-dashboard/",
                self.admin_view(self.climate_dashboard_view),
                name="climate_dashboard",
            ),
        ]
        return custom_urls + super().get_urls()

    def climate_dashboard_view(self, request):
        """
        Vista del dashboard personalizado con métricas globales del sistema.

        Muestra: total de regiones, predicciones, desglose por anomalía,
        y tabla con las últimas predicciones registradas.
        """
        # Conteos generales
        total_regions = Region.objects.count()
        total_predictions = ClimatePrediction.objects.count()

        # Desglose por tipo de anomalía
        anomaly_breakdown = (
            ClimatePrediction.objects
            .values("anomaly_type")
            .annotate(count=Count("id"))
            .order_by("-count")
        )

        # Últimas 15 predicciones registradas
        latest_predictions = (
            ClimatePrediction.objects
            .select_related("region")
            .order_by("-created_at")[:15]
        )

        # Promedios globales
        global_stats = ClimatePrediction.objects.aggregate(
            avg_severity=Avg("severity_level"),
            avg_confidence=Avg("confidence_score"),
            max_severity=Max("severity_level"),
        )

        context = {
            **self.each_context(request),
            "title": "Dashboard de Inteligencia Climática",
            "total_regions": total_regions,
            "total_predictions": total_predictions,
            "anomaly_breakdown": anomaly_breakdown,
            "latest_predictions": latest_predictions,
            "avg_severity": (
                round(global_stats["avg_severity"], 2)
                if global_stats["avg_severity"] else "N/A"
            ),
            "avg_confidence": (
                round(global_stats["avg_confidence"] * 100, 1)
                if global_stats["avg_confidence"] else "N/A"
            ),
            "max_severity": global_stats["max_severity"] or "N/A",
        }

        return TemplateResponse(
            request,
            "admin/climate_dashboard.html",
            context,
        )


# Inyecta las URLs del dashboard en el sitio de administración por defecto
# Esto evita tener que reemplazar admin.site y mantiene todo el registro existente
_original_get_urls = admin.AdminSite.get_urls


def _patched_get_urls(self):
    """Agrega la ruta del dashboard climático al AdminSite por defecto."""
    custom_urls = [
        path(
            "climate-dashboard/",
            self.admin_view(_climate_dashboard_view),
            name="climate_dashboard",
        ),
    ]
    return custom_urls + _original_get_urls(self)


def _climate_dashboard_view(request):
    """
    Vista del dashboard personalizado con métricas globales del sistema.

    Muestra: total de regiones, predicciones, desglose por anomalía,
    y tabla con las últimas predicciones registradas.
    """
    # Conteos generales
    total_regions = Region.objects.count()
    total_predictions = ClimatePrediction.objects.count()

    # Desglose por tipo de anomalía
    anomaly_breakdown = (
        ClimatePrediction.objects
        .values("anomaly_type")
        .annotate(count=Count("id"))
        .order_by("-count")
    )

    # Últimas 15 predicciones registradas
    latest_predictions = (
        ClimatePrediction.objects
        .select_related("region")
        .order_by("-created_at")[:15]
    )

    # Promedios globales
    global_stats = ClimatePrediction.objects.aggregate(
        avg_severity=Avg("severity_level"),
        avg_confidence=Avg("confidence_score"),
        max_severity=Max("severity_level"),
    )

    context = {
        **admin.site.each_context(request),
        "title": "Dashboard de Inteligencia Climática",
        "total_regions": total_regions,
        "total_predictions": total_predictions,
        "anomaly_breakdown": anomaly_breakdown,
        "latest_predictions": latest_predictions,
        "avg_severity": (
            round(global_stats["avg_severity"], 2)
            if global_stats["avg_severity"] else "N/A"
        ),
        "avg_confidence": (
            round(global_stats["avg_confidence"] * 100, 1)
            if global_stats["avg_confidence"] else "N/A"
        ),
        "max_severity": global_stats["max_severity"] or "N/A",
    }

    return TemplateResponse(
        request,
        "admin/climate_dashboard.html",
        context,
    )


# Aplica el parche al sitio de administración por defecto
admin.AdminSite.get_urls = _patched_get_urls


# =============================================================================
# Administración de Regiones
# =============================================================================

@admin.register(Region)
class RegionAdmin(admin.ModelAdmin):
    """
    Panel administrativo para la gestión de Regiones Agrícolas.
    """
    list_display = ('name', 'description_excerpt', 'prediction_count', 'created_at', 'updated_at')
    search_fields = ('name', 'description')
    readonly_fields = ('created_at', 'updated_at')

    # Campo calculado para no saturar la vista de lista con textos largos
    def description_excerpt(self, obj):
        if obj.description and len(obj.description) > 60:
            return f"{obj.description[:57]}..."
        return obj.description or "-"
    description_excerpt.short_description = "Descripción Corta"

    # Cuenta cuántas predicciones climáticas se han calculado para esta región
    def prediction_count(self, obj):
        count = obj.predictions.count()
        return format_html(
            '<strong style="color: {};">{}</strong>',
            '#2e7d32' if count > 0 else '#c62828',
            count
        )
    prediction_count.short_description = "Nº de Predicciones"


# =============================================================================
# Administración de Predicciones Climáticas
# =============================================================================

@admin.register(ClimatePrediction)
class ClimatePredictionAdmin(admin.ModelAdmin):
    """
    Panel administrativo avanzado para gestionar las predicciones de IA de Vertex AI.

    Incluye badges visuales, barras de severidad, exportación a CSV y
    navegación jerárquica por fecha.
    """
    list_display = (
        'region',
        'prediction_date',
        'target_date',
        'anomaly_badge',
        'severity_bar',
        'confidence_percentage',
        'created_at'
    )
    list_filter = ('anomaly_type', 'severity_level', 'region', 'target_date', 'prediction_date')
    search_fields = ('region__name', 'anomaly_type')
    readonly_fields = ('created_at', 'updated_at', 'pretty_vertex_ai_output')

    # Jerarquía de fechas para navegación temporal rápida
    date_hierarchy = 'target_date'

    # Acciones masivas disponibles
    actions = ['export_selected_to_csv']

    # Organiza el formulario detallado en secciones (fieldsets)
    fieldsets = (
        ('Ubicación y Fechas', {
            'fields': ('region', 'prediction_date', 'target_date')
        }),
        ('Métricas de la Anomalía', {
            'fields': ('anomaly_type', 'severity_level', 'confidence_score')
        }),
        ('Resultados de IA (Google Vertex AI)', {
            'classes': ('collapse',),  # Sección colapsable
            'fields': ('pretty_vertex_ai_output',),
            'description': 'Muestra el payload JSON en crudo devuelto por la plataforma Vertex AI para auditorías.'
        }),
        ('Metadatos de Registro', {
            'fields': ('created_at', 'updated_at')
        }),
    )

    # Inserta una insignia visual de color para el tipo de anomalía
    def anomaly_badge(self, obj):
        if not obj.anomaly_type:
            return "-"
        colors = {
            ClimatePrediction.AnomalyType.SEQUIA: ('#e65100', '#fff3e0', 'Sequía'),
            ClimatePrediction.AnomalyType.INUNDACION: ('#0d47a1', '#e3f2fd', 'Inundación'),
            ClimatePrediction.AnomalyType.NORMAL: ('#1b5e20', '#e8f5e9', 'Normal'),
        }
        text_color, bg_color, label = colors.get(obj.anomaly_type, ('#333', '#eee', obj.anomaly_type))
        return format_html(
            '<span style="color: {}; background-color: {}; padding: 4px 8px; border-radius: 4px; font-weight: bold;">{}</span>',
            text_color, bg_color, label
        )
    anomaly_badge.short_description = "Anomalía"

    # Genera una barra visual representativa del nivel de severidad (1 a 5)
    def severity_bar(self, obj):
        if obj.severity_level is None:
            return "-"
        colors = {
            1: '#81c784',  # Verde claro
            2: '#aed581',  # Verde-Amarillo
            3: '#ffd54f',  # Amarillo / Oro
            4: '#ffb74d',  # Naranja
            5: '#e57373',  # Rojo
        }
        color = colors.get(obj.severity_level, '#ccc')
        width_percent = obj.severity_level * 20
        return format_html(
            '<div style="background-color: #eee; width: 100px; height: 12px; border-radius: 6px; overflow: hidden; display: inline-block; vertical-align: middle; margin-right: 8px;">'
            '<div style="background-color: {}; width: {}%; height: 100%;"></div>'
            '</div><span>{}</span>',
            color, width_percent, obj.severity_level
        )
    severity_bar.short_description = "Severidad"

    # Muestra el nivel de confianza como un porcentaje limpio (ej. 85.0%)
    def confidence_percentage(self, obj):
        if obj.confidence_score is None:
            return "-"
        percentage = obj.confidence_score * 100
        color_threshold = '#2e7d32' if percentage >= 75 else '#ef6c00' if percentage >= 50 else '#c62828'
        return format_html(
            '<span style="color: {}; font-weight: 500;">{:.1f}%</span>',
            color_threshold, percentage
        )
    confidence_percentage.short_description = "Confianza"

    # Presenta el JSON de Vertex AI formateado y legible para humanos
    def pretty_vertex_ai_output(self, obj):
        if not obj.vertex_ai_output:
            return "-"
        formatted_json = json.dumps(obj.vertex_ai_output, indent=4, ensure_ascii=False)
        return format_html(
            '<pre style="background: #f5f5f5; padding: 12px; border-radius: 4px; border: 1px solid #ddd; max-height: 400px; overflow-y: auto;">{}</pre>',
            formatted_json
        )
    pretty_vertex_ai_output.short_description = "Raw JSON"

    # =========================================================================
    # Acción masiva: Exportar predicciones seleccionadas a CSV
    # =========================================================================

    @admin.action(description="📥 Exportar seleccionadas a CSV")
    def export_selected_to_csv(self, request, queryset):
        """
        Acción masiva para exportar las predicciones seleccionadas a un archivo CSV.

        Genera un archivo descargable con todas las columnas relevantes de las
        predicciones seleccionadas por el administrador.
        """
        # Genera nombre de archivo con marca de tiempo
        timestamp = timezone.now().strftime("%Y%m%d_%H%M%S")
        filename = f"predicciones_climaticas_{timestamp}.csv"

        # Prepara la respuesta HTTP con tipo MIME para CSV
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'

        # Escribe la cabecera BOM para compatibilidad con Excel en español
        response.write('\ufeff')

        writer = csv.writer(response)

        # Cabecera del CSV con nombres descriptivos en español
        writer.writerow([
            "ID",
            "Región",
            "Fecha de Predicción",
            "Fecha Objetivo",
            "Tipo de Anomalía",
            "Nivel de Severidad",
            "Confianza (%)",
            "Creado el",
            "Actualizado el",
        ])

        # Escribe cada predicción seleccionada como una fila
        for prediction in queryset.select_related("region").order_by("region__name", "target_date"):
            pred_date = prediction.prediction_date.isoformat() if prediction.prediction_date else "-"
            targ_date = prediction.target_date.isoformat() if prediction.target_date else "-"
            conf_score = f"{prediction.confidence_score * 100:.1f}" if prediction.confidence_score is not None else "-"
            created = prediction.created_at.strftime("%Y-%m-%d %H:%M:%S") if prediction.created_at else "-"
            updated = prediction.updated_at.strftime("%Y-%m-%d %H:%M:%S") if prediction.updated_at else "-"
            writer.writerow([
                prediction.id,
                prediction.region.name if prediction.region else "-",
                pred_date,
                targ_date,
                prediction.get_anomaly_type_display() if hasattr(prediction, "get_anomaly_type_display") else "-",
                prediction.severity_level if prediction.severity_level is not None else "-",
                conf_score,
                created,
                updated,
            ])

        # Mensaje informativo al usuario en el admin
        self.message_user(
            request,
            f"✅ Se exportaron {queryset.count()} predicciones al archivo {filename}.",
        )

        return response
