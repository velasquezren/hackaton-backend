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

from .models import Region, ClimatePrediction, ClimateAlert, SatelliteObservation, ClimateDataSource


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
    list_display = ('name', 'main_crops', 'area_hectares', 'coordinates_display', 'prediction_count', 'updated_at')
    search_fields = ('name', 'description', 'main_crops')
    readonly_fields = ('created_at', 'updated_at')
    list_filter = ('main_crops',)

    fieldsets = (
        ('Información General', {
            'fields': ('name', 'description', 'main_crops', 'area_hectares')
        }),
        ('Ubicación Geoespacial (GIS)', {
            'fields': ('latitude', 'longitude'),
            'description': 'Coordenadas del epicentro agrícola de la región. Se usan para el mapa interactivo del frontend.'
        }),
        ('Metadatos', {
            'fields': ('created_at', 'updated_at')
        }),
    )

    def coordinates_display(self, obj):
        if obj.latitude and obj.longitude:
            return format_html(
                '<span style="font-family: monospace; color: #1565c0;">{}, {}</span>',
                f"{obj.latitude:.2f}", f"{obj.longitude:.2f}"
            )
        return "-"
    coordinates_display.short_description = "Coordenadas"

    # Cuenta cuántas predicciones climáticas se han calculado para esta región
    def prediction_count(self, obj):
        count = obj.predictions.count()
        return format_html(
            '<strong style="color: {};">{}</strong>',
            '#2e7d32' if count > 0 else '#c62828',
            count
        )
    prediction_count.short_description = "Predicciones"


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
        percentage_str = f"{percentage:.1f}%"
        color_threshold = '#2e7d32' if percentage >= 75 else '#ef6c00' if percentage >= 50 else '#c62828'
        return format_html(
            '<span style="color: {}; font-weight: 500;">{}</span>',
            color_threshold, percentage_str
        )
    confidence_percentage.short_description = "Confianza"

    # Presenta el JSON de Vertex AI formateado y legible para humanos
    def pretty_vertex_ai_output(self, obj):
        if not obj.vertex_ai_output:
            return "-"
        
        data = obj.vertex_ai_output
        model_id = data.get("model_id", "N/A")
        metric = data.get("validation_metric", "N/A")
        calculated_pct = data.get("calculated_anomaly_pct", 0.0)
        epochs = data.get("epochs_trained", "N/A")
        time_ms = data.get("vertex_endpoint_execution_ms", "N/A")
        features = data.get("features_used", [])
        
        features_list = "".join(f"<li style='margin-bottom: 2px;'><code>{f}</code></li>" for f in features)
        pct_color = "#e65100" if calculated_pct < 0 else "#0d47a1" if calculated_pct > 0 else "#1b5e20"
        
        html = f"""
        <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 600px; background: #1e293b; border: 1px solid #334155; border-radius: 8px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.1); padding: 16px; color: #f1f5f9;">
            <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #334155; padding-bottom: 10px; margin-bottom: 12px;">
                <span style="font-size: 1.1em; font-weight: bold; color: #38bdf8; display: flex; align-items: center; gap: 6px;">
                    🤖 {model_id}
                </span>
                <span style="font-size: 0.8em; background: #0c4a6e; color: #38bdf8; padding: 4px 8px; border-radius: 12px; font-weight: 600; border: 1px solid #0369a1;">
                    Vertex AI Live
                </span>
            </div>
            
            <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; margin-bottom: 16px;">
                <div>
                    <strong style="color: #94a3b8; font-size: 0.75em; text-transform: uppercase; letter-spacing: 0.5px;">Métrica de Validación</strong>
                    <div style="font-size: 0.95em; font-weight: 600; color: #f1f5f9; margin-top: 2px;">{metric}</div>
                </div>
                <div>
                    <strong style="color: #94a3b8; font-size: 0.75em; text-transform: uppercase; letter-spacing: 0.5px;">Desviación Estimada</strong>
                    <div style="font-size: 1.05em; font-weight: 700; color: {pct_color}; margin-top: 2px;">
                        {calculated_pct:+.1f}%
                    </div>
                </div>
                <div>
                    <strong style="color: #94a3b8; font-size: 0.75em; text-transform: uppercase; letter-spacing: 0.5px;">Épocas de Entrenamiento</strong>
                    <div style="font-size: 0.95em; font-weight: 500; color: #f1f5f9; margin-top: 2px;">{epochs}</div>
                </div>
                <div>
                    <strong style="color: #94a3b8; font-size: 0.75em; text-transform: uppercase; letter-spacing: 0.5px;">Latencia de Inferencia</strong>
                    <div style="font-size: 0.95em; font-weight: 500; color: #f1f5f9; margin-top: 2px;">{time_ms} ms</div>
                </div>
            </div>
            
            <div style="border-top: 1px solid #334155; padding-top: 12px; margin-top: 12px;">
                <strong style="color: #94a3b8; font-size: 0.75em; text-transform: uppercase; letter-spacing: 0.5px; display: block; margin-bottom: 6px;">Variables Predictivas (Features)</strong>
                <ul style="margin: 0; padding-left: 20px; font-size: 0.85em; color: #cbd5e1; line-height: 1.4;">
                    {features_list}
                </ul>
            </div>
        </div>
        """
        return format_html(html)
    pretty_vertex_ai_output.short_description = "Detalle del Modelo"

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


# =============================================================================
# Administración de Alertas Climáticas
# =============================================================================

@admin.register(ClimateAlert)
class ClimateAlertAdmin(admin.ModelAdmin):
    """
    Panel administrativo para gestionar las alertas climáticas en lenguaje natural.
    """
    list_display = (
        'alert_level_badge', 'title_excerpt', 'region_name',
        'anomaly_type_display', 'generated_by', 'is_sent', 'created_at'
    )
    list_filter = ('alert_level', 'is_sent', 'generated_by', 'prediction__region')
    search_fields = ('title', 'message_short', 'prediction__region__name')
    readonly_fields = ('created_at', 'updated_at', 'tips_list_display')
    actions = ['mark_as_sent', 'mark_as_unsent']

    fieldsets = (
        ('Identificación', {
            'fields': ('prediction', 'alert_level')
        }),
        ('Contenido de la Alerta', {
            'fields': ('title', 'message_short', 'message_long')
        }),
        ('Recomendaciones Agronómicas', {
            'fields': ('tips_list_display',)
        }),
        ('Estado y Trazabilidad', {
            'fields': ('generated_by', 'is_sent', 'created_at', 'updated_at')
        }),
    )

    def region_name(self, obj):
        return obj.prediction.region.name if obj.prediction else '-'
    region_name.short_description = 'Región'

    def anomaly_type_display(self, obj):
        if not obj.prediction:
            return '-'
        colors = {
            'SEQUIA': ('#e65100', '#fff3e0', '🌵 Sequía'),
            'INUNDACION': ('#0d47a1', '#e3f2fd', '🌊 Inundación'),
            'NORMAL': ('#1b5e20', '#e8f5e9', '✅ Normal'),
        }
        t, bg, label = colors.get(obj.prediction.anomaly_type, ('#333', '#eee', '-'))
        return format_html(
            '<span style="color:{};background:{};padding:3px 8px;border-radius:4px;font-weight:bold">{}</span>',
            t, bg, label
        )
    anomaly_type_display.short_description = 'Anomalía'

    def alert_level_badge(self, obj):
        colors = {
            'LOW': ('#2e7d32', '#e8f5e9', '🟢 Bajo'),
            'MEDIUM': ('#e65100', '#fff3e0', '🟡 Medio'),
            'HIGH': ('#b71c1c', '#ffebee', '🔴 Alto'),
            'EXTREME': ('#4a148c', '#f3e5f5', '🟣 Extremo'),
        }
        t, bg, label = colors.get(obj.alert_level, ('#333', '#eee', obj.alert_level))
        return format_html(
            '<span style="color:{};background:{};padding:4px 10px;border-radius:12px;font-weight:bold;font-size:0.85rem">{}</span>',
            t, bg, label
        )
    alert_level_badge.short_description = 'Nivel'

    def title_excerpt(self, obj):
        if obj.title and len(obj.title) > 55:
            return f'{obj.title[:52]}...'
        return obj.title or '-'
    title_excerpt.short_description = 'Título'

    def tips_list_display(self, obj):
        if not obj.agronomic_tips:
            return '-'
        items = ''.join(f'<li style="margin:4px 0">{tip}</li>' for tip in obj.agronomic_tips)
        return format_html(
            '<ul style="margin:0;padding-left:20px;list-style:disc">{}</ul>', items
        )
    tips_list_display.short_description = 'Recomendaciones Agronómicas'

    @admin.action(description='📤 Marcar seleccionadas como ENVIADAS')
    def mark_as_sent(self, request, queryset):
        updated = queryset.update(is_sent=True)
        self.message_user(request, f'✅ {updated} alertas marcadas como enviadas.')

    @admin.action(description='🔄 Marcar seleccionadas como NO enviadas')
    def mark_as_unsent(self, request, queryset):
        updated = queryset.update(is_sent=False)
        self.message_user(request, f'✅ {updated} alertas marcadas como no enviadas.')


# =============================================================================
# Administración de Observaciones Satelitales
# =============================================================================

@admin.register(SatelliteObservation)
class SatelliteObservationAdmin(admin.ModelAdmin):
    """
    Panel administrativo para monitoreo satelital NDVI/NDWI por región.
    """
    list_display = (
        'region', 'obs_date', 'ndvi_bar', 'ndwi_display',
        'cloud_cover_pct', 'source', 'created_at'
    )
    list_filter = ('source', 'region', 'obs_date')
    search_fields = ('region__name',)
    readonly_fields = ('created_at',)
    date_hierarchy = 'obs_date'

    def ndvi_bar(self, obj):
        if obj.ndvi is None:
            return '-'
        # NDVI: -1 a 1. Normalizar a 0-100% para la barra
        pct = int((obj.ndvi + 1) / 2 * 100)
        color = '#81c784' if obj.ndvi > 0.5 else '#ffb74d' if obj.ndvi > 0.3 else '#e57373'
        return format_html(
            '<div style="background:#eee;width:90px;height:10px;border-radius:5px;overflow:hidden;display:inline-block;vertical-align:middle;margin-right:6px">'
            '<div style="background:{};width:{}%;height:100%"></div></div><span>{:.3f}</span>',
            color, pct, obj.ndvi
        )
    ndvi_bar.short_description = 'NDVI'

    def ndwi_display(self, obj):
        if obj.ndwi is None:
            return '-'
        color = '#1565c0' if obj.ndwi > 0.0 else '#e65100'
        return format_html(
            '<span style="color:{};font-weight:500">{:.3f}</span>',
            color, obj.ndwi
        )
    ndwi_display.short_description = 'NDWI'


# =============================================================================
# Administración de Datos Climáticos
# =============================================================================

@admin.register(ClimateDataSource)
class ClimateDataSourceAdmin(admin.ModelAdmin):
    """
    Panel administrativo para los datos climáticos históricos ingestados.
    """
    list_display = (
        'region', 'date', 'variable_name', 'value_display', 'unit',
        'source_name', 'fetched_at'
    )
    list_filter = ('source_name', 'variable_name', 'region')
    search_fields = ('region__name', 'variable_name')
    readonly_fields = ('fetched_at',)
    date_hierarchy = 'date'

    def value_display(self, obj):
        return f'{obj.value:.3f}' if obj.value is not None else '-'
    value_display.short_description = 'Valor'
