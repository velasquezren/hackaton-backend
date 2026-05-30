from django.contrib import admin
from django.utils.html import format_html
import json
from .models import Region, ClimatePrediction


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


@admin.register(ClimatePrediction)
class ClimatePredictionAdmin(admin.ModelAdmin):
    """
    Panel administrativo para gestionar las predicciones de IA de Vertex AI a 12 meses.
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
    
    # Organiza el formulario detallado en secciones (fieldsets)
    fieldsets = (
        ('Ubicación y Fechas', {
            'fields': ('region', 'prediction_date', 'target_date')
        }),
        ('Métricas de la Anomalía', {
            'fields': ('anomaly_type', 'severity_level', 'confidence_score')
        }),
        ('Resultados de IA (Google Vertex AI)', {
            'classes': ('collapse',),  # Collapsible section
            'fields': ('pretty_vertex_ai_output',),
            'description': 'Muestra el payload JSON en crudo devuelto por la plataforma Vertex AI para auditorías.'
        }),
        ('Metadatos de Registro', {
            'fields': ('created_at', 'updated_at')
        }),
    )

    # Inserta una insignia visual de color para el tipo de anomalía
    def anomaly_badge(self, obj):
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
        colors = {
            1: '#81c784', # Verde claro
            2: '#aed581', # Verde-Amarillo
            3: '#ffd54f', # Amarillo / Oro
            4: '#ffb74d', # Naranja
            5: '#e57373', # Rojo
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
