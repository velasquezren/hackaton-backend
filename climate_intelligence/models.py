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
