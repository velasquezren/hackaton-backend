# ==========================================
# Dockerfile optimizado para Google Cloud Run
# ==========================================

# Usamos la versión oficial de Python Slim como base (segura y de tamaño reducido)
FROM python:3.11-slim as base

# Evita que Python escriba archivos .pyc en el disco
ENV PYTHONDONTWRITEBYTECODE=1

# Asegura que los outputs de logs se envíen directamente a stdout/stderr sin buffer
ENV PYTHONUNBUFFERED=1

# Define el directorio de trabajo dentro del contenedor
WORKDIR /app

# Instalamos dependencias del sistema necesarias para compilar librerías si fuera necesario
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copiamos primero solo el archivo de requerimientos para aprovechar la caché de Docker
COPY requirements.txt /app/

# Instalamos las dependencias de Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiamos todo el código fuente del proyecto al contenedor
COPY . /app/

# Creamos un usuario de sistema no privilegiado por razones de seguridad (Best Practice en GCP)
# Google Cloud Run corre los contenedores con privilegios limitados, pero es una buena práctica forzarlo a nivel Docker.
RUN useradd -u 8888 appuser && chown -R appuser:appuser /app
USER appuser

# Hacemos ejecutable el script de arranque (entrypoint.sh)
USER root
RUN chmod +x /app/entrypoint.sh
USER appuser

# Exponemos el puerto por defecto de Google Cloud Run (8080)
EXPOSE 8080

# Usamos entrypoint.sh para gestionar migraciones automáticas y colecta de estáticos al arrancar
ENTRYPOINT ["/app/entrypoint.sh"]
