from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils.translation import gettext_lazy as _


class Region(models.Model):
    """
    Representa una región geográfica o agrícola dentro del Departamento de Santa Cruz, Bolivia.
    Ejemplos: Valles Cruceños, Norte Integrado, Chiquitania, Chaco Cruceño, Pantanal.
    """
    name = models.CharField(
        max_length=100, 
        unique=True, 
        verbose_name=_("Nombre de la Región"),
        help_text=_("Ejemplo: Norte Integrado, Valles Cruceños, Chiquitania")
    )
    description = models.TextField(
        blank=True,
        verbose_name=_("Descripción"),
        help_text=_("Detalles sobre el relieve, clima predominante, principales cultivos u observaciones.")
    )
    main_crops = models.CharField(
        max_length=255,
        blank=True,
        verbose_name=_("Cultivos Principales"),
        help_text=_("Ej: Soya, Caña de Azúcar, Arroz")
    )
    area_hectares = models.IntegerField(
        null=True,
        blank=True,
        verbose_name=_("Superficie (ha)"),
        help_text=_("Superficie estimada productiva en hectáreas")
    )
    # Coordenadas del centroide de la región (para APIs satelitales y climáticas)
    latitude = models.FloatField(
        null=True,
        blank=True,
        verbose_name=_("Latitud"),
        help_text=_("Latitud del centroide de la región (ej. -16.5)")
    )
    longitude = models.FloatField(
        null=True,
        blank=True,
        verbose_name=_("Longitud"),
        help_text=_("Longitud del centroide de la región (ej. -63.2)")
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Fecha de Creación"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Última Actualización"))

    class Meta:
        verbose_name = _("Región")
        verbose_name_plural = _("Regiones")
        ordering = ['name']

    def __str__(self):
        return self.name


class ClimatePrediction(models.Model):
    """
    Almacena las predicciones climáticas severas generadas con 12 meses de anticipación
    a partir del consumo de modelos entrenados en Google Vertex AI.
    """
    class AnomalyType(models.TextChoices):
        SEQUIA = 'SEQUIA', _('Sequía')
        INUNDACION = 'INUNDACION', _('Inundación')
        NORMAL = 'NORMAL', _('Normal (Sin Anomalías)')

    region = models.ForeignKey(
        Region,
        on_delete=models.CASCADE,
        related_name='predictions',
        verbose_name=_("Región")
    )
    prediction_date = models.DateField(
        verbose_name=_("Fecha de Predicción"),
        help_text=_("Fecha en la que el modelo de IA ejecutó y guardó la predicción.")
    )
    target_date = models.DateField(
        verbose_name=_("Fecha Objetivo"),
        help_text=_("Fecha futura (habitualmente 12 meses adelante) para la cual se predice el clima.")
    )
    anomaly_type = models.CharField(
        max_length=20,
        choices=AnomalyType.choices,
        default=AnomalyType.NORMAL,
        verbose_name=_("Tipo de Anomalía Climática")
    )
    severity_level = models.IntegerField(
        validators=[
            MinValueValidator(1),
            MaxValueValidator(5)
        ],
        verbose_name=_("Nivel de Severidad (1-5)"),
        help_text=_("Escala del 1 al 5 (1: Muy Leve, 2: Leve, 3: Moderado, 4: Severo, 5: Extremo/Catastrófico)")
    )
    confidence_score = models.FloatField(
        validators=[
            MinValueValidator(0.0),
            MaxValueValidator(1.0)
        ],
        verbose_name=_("Índice de Confianza (0.0 - 1.0)"),
        help_text=_("Nivel de probabilidad o certeza calculado por Vertex AI (ej. 0.85)")
    )
    vertex_ai_output = models.JSONField(
        blank=True,
        null=True,
        verbose_name=_("Output Detallado de Vertex AI"),
        help_text=_("Payload crudo JSON devuelto por Google Vertex AI. Contiene métricas de importancia, versión del modelo, etc.")
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Registrado el"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Modificado el"))

    class Meta:
        verbose_name = _("Predicción Climática")
        verbose_name_plural = _("Predicciones Climáticas")
        ordering = ['-target_date', 'region']
        # Evita duplicar predicciones para la misma región y fecha objetivo
        unique_together = ('region', 'target_date', 'prediction_date')

    def __str__(self):
        return f"{self.region.name} - {self.get_anomaly_type_display()} ({self.target_date})"


# ==============================================================================
# NUEVOS MODELOS — Sistema de Predicción Climática Extendido
# ==============================================================================

class ClimateDataSource(models.Model):
    """
    Registra series de tiempo de variables climáticas ingestadas desde APIs externas
    (Open-Meteo, NASA POWER, CHIRPS) o simuladas en modo mock.

    Cada registro representa el valor de UNA variable climática para UNA región en UN día.
    Permite construir el historial climático base para alimentar los modelos predictivos.
    """
    class SourceName(models.TextChoices):
        OPEN_METEO = 'OPEN_METEO', _('Open-Meteo (Archivo Histórico)')
        NASA_POWER = 'NASA_POWER', _('NASA POWER API')
        CHIRPS = 'CHIRPS', _('CHIRPS (Precipitación Satelital)')
        MOCK = 'MOCK', _('Datos Simulados (Desarrollo)')

    region = models.ForeignKey(
        Region,
        on_delete=models.CASCADE,
        related_name='climate_data',
        verbose_name=_("Región")
    )
    source_name = models.CharField(
        max_length=20,
        choices=SourceName.choices,
        default=SourceName.MOCK,
        verbose_name=_("Fuente de Datos")
    )
    variable_name = models.CharField(
        max_length=60,
        verbose_name=_("Variable Climática"),
        help_text=_("Ej: precipitation_sum, temperature_2m_max, soil_moisture_0_7cm")
    )
    date = models.DateField(
        verbose_name=_("Fecha de Observación")
    )
    value = models.FloatField(
        verbose_name=_("Valor"),
        help_text=_("Valor numérico de la variable en la unidad correspondiente")
    )
    unit = models.CharField(
        max_length=30,
        verbose_name=_("Unidad"),
        help_text=_("Ej: mm, °C, m³/m³, %")
    )
    raw_response = models.JSONField(
        blank=True,
        null=True,
        verbose_name=_("Respuesta Cruda de la API"),
        help_text=_("Payload JSON completo de la respuesta de la API externa para auditoría")
    )
    fetched_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name=_("Obtenido el")
    )

    class Meta:
        verbose_name = _("Dato Climático")
        verbose_name_plural = _("Datos Climáticos")
        ordering = ['-date', 'region', 'variable_name']
        unique_together = ('region', 'source_name', 'variable_name', 'date')
        indexes = [
            models.Index(fields=['region', 'variable_name', 'date']),
        ]

    def __str__(self):
        return f"{self.region.name} | {self.variable_name} | {self.date}: {self.value} {self.unit}"


class ClimateAlert(models.Model):
    """
    Alerta climática generada por el LLM (Gemini) para productores agrícolas.

    Traduce predicciones técnicas en mensajes comprensibles en lenguaje natural,
    incluyendo recomendaciones agronómicas concretas y accionables.
    Compatible con envío por SMS, WhatsApp o notificación push.
    """
    class AlertLevel(models.TextChoices):
        LOW = 'LOW', _('Bajo')
        MEDIUM = 'MEDIUM', _('Medio')
        HIGH = 'HIGH', _('Alto')
        EXTREME = 'EXTREME', _('Extremo')

    prediction = models.OneToOneField(
        ClimatePrediction,
        on_delete=models.CASCADE,
        related_name='alert',
        verbose_name=_("Predicción Asociada")
    )
    alert_level = models.CharField(
        max_length=10,
        choices=AlertLevel.choices,
        verbose_name=_("Nivel de Alerta")
    )
    title = models.CharField(
        max_length=120,
        verbose_name=_("Título de la Alerta"),
        help_text=_("Título corto y claro para notificaciones push (máx 120 chars)")
    )
    message_short = models.TextField(
        verbose_name=_("Mensaje Corto (SMS/WhatsApp)"),
        help_text=_("Mensaje para SMS/WhatsApp en lenguaje simple para el agricultor (máx 160 chars)")
    )
    message_long = models.TextField(
        verbose_name=_("Mensaje Completo"),
        help_text=_("Explicación detallada de la alerta en 2-3 párrafos generada por Gemini")
    )
    agronomic_tips = models.JSONField(
        default=list,
        verbose_name=_("Recomendaciones Agronómicas"),
        help_text=_("Lista de 3-5 acciones concretas que el agricultor debe tomar")
    )
    generated_by = models.CharField(
        max_length=60,
        default='template_fallback',
        verbose_name=_("Generado por"),
        help_text=_("Modelo LLM utilizado (ej. 'gemini-1.5-flash') o 'template_fallback'")
    )
    is_sent = models.BooleanField(
        default=False,
        verbose_name=_("¿Enviada?"),
        help_text=_("Indica si la alerta fue enviada a los productores de la región")
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Generada el"))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_("Actualizada el"))

    class Meta:
        verbose_name = _("Alerta Climática")
        verbose_name_plural = _("Alertas Climáticas")
        ordering = ['-created_at']

    def __str__(self):
        return f"[{self.alert_level}] {self.title}"


class SatelliteObservation(models.Model):
    """
    Métricas de monitoreo satelital por región y fecha.

    Almacena índices espectrales derivados de imágenes MODIS/Sentinel-2:
    - NDVI (Normalized Difference Vegetation Index): salud de la vegetación
    - NDWI (Normalized Difference Water Index): contenido de agua en superficie

    Permite detectar anomalías de vegetación (estrés hídrico, sequía) y excesos
    de humedad (riesgo de inundación) con semanas de anticipación a los eventos.
    """
    class DataSource(models.TextChoices):
        MODIS = 'MODIS', _('MODIS (Terra/Aqua)')
        SENTINEL2 = 'SENTINEL_2', _('Sentinel-2 (ESA Copernicus)')
        LANDSAT = 'LANDSAT', _('Landsat-8/9 (USGS)')
        MOCK = 'MOCK', _('Datos Simulados (Desarrollo)')

    region = models.ForeignKey(
        Region,
        on_delete=models.CASCADE,
        related_name='satellite_observations',
        verbose_name=_("Región")
    )
    obs_date = models.DateField(
        verbose_name=_("Fecha de Observación"),
        help_text=_("Fecha de la captura satelital")
    )
    ndvi = models.FloatField(
        validators=[MinValueValidator(-1.0), MaxValueValidator(1.0)],
        verbose_name=_("NDVI"),
        help_text=_("Índice de Vegetación de Diferencia Normalizada (-1 a 1). >0.5 = vegetación densa/sana")
    )
    ndwi = models.FloatField(
        validators=[MinValueValidator(-1.0), MaxValueValidator(1.0)],
        verbose_name=_("NDWI"),
        help_text=_("Índice de Agua de Diferencia Normalizada (-1 a 1). >0 = presencia de agua en superficie")
    )
    cloud_cover_pct = models.FloatField(
        null=True,
        blank=True,
        validators=[MinValueValidator(0.0), MaxValueValidator(100.0)],
        verbose_name=_("Cobertura de Nubes (%)"),
        help_text=_("Porcentaje de nubosidad en la imagen (afecta calidad del dato)")
    )
    source = models.CharField(
        max_length=15,
        choices=DataSource.choices,
        default=DataSource.MOCK,
        verbose_name=_("Fuente Satelital")
    )
    raw_data = models.JSONField(
        blank=True,
        null=True,
        verbose_name=_("Datos Crudos"),
        help_text=_("Metadatos completos de la imagen satelital")
    )
    created_at = models.DateTimeField(auto_now_add=True, verbose_name=_("Registrado el"))

    class Meta:
        verbose_name = _("Observación Satelital")
        verbose_name_plural = _("Observaciones Satelitales")
        ordering = ['-obs_date', 'region']
        unique_together = ('region', 'obs_date', 'source')
        indexes = [
            models.Index(fields=['region', 'obs_date']),
        ]

    def __str__(self):
        return f"{self.region.name} | {self.obs_date} | NDVI={self.ndvi:.3f} NDWI={self.ndwi:.3f}"
