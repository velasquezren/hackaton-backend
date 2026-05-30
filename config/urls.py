"""
URL configuration for AgriTech climate intelligence platform.
"""

from django.contrib import admin
from django.urls import path
from climate_intelligence.api import api as climate_api

urlpatterns = [
    path('admin/', admin.site.urls),
    # Mount the Django Ninja API under the /api/ prefix
    path('api/', climate_api.urls),
]
