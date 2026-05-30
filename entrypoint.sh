#!/bin/sh
set -e

# entrypoint.sh: Script de inicialización optimizado para Docker Compose y Google Cloud Run

echo "=== [1/3] Recolectando Archivos Estáticos (WhiteNoise) ==="
# Colecta archivos estáticos para que WhiteNoise pueda servirlos de forma súper rápida y comprimida
python manage.py collectstatic --noinput

# Intentamos verificar si la base de datos está disponible antes de correr migraciones
# Esto es crítico para docker-compose local, donde PostgreSQL puede tardar unos segundos en inicializarse.
echo "=== [2/3] Verificando Conexión con PostgreSQL ==="
python -c "
import sys, time, psycopg2, environ
env = environ.Env()
try:
    db_conn = env.db('DATABASE_URL')
    # Si la URL usa sqlite, no necesitamos esperar
    if db_conn['ENGINE'] == 'django.db.backends.sqlite3':
        print('Usando SQLite local. No se requiere espera.')
        sys.exit(0)
        
    for i in range(20):
        try:
            conn = psycopg2.connect(
                dbname=db_conn['NAME'],
                user=db_conn['USER'],
                password=db_conn['PASSWORD'],
                host=db_conn['HOST'],
                port=db_conn['PORT'],
                connect_timeout=3
            )
            conn.close()
            print('¡PostgreSQL está listo y aceptando conexiones!')
            sys.exit(0)
        except Exception as err:
            print(f'Intento {i+1}/20: La base de datos aún no está disponible ({err}). Reintentando en 2 segundos...')
            time.sleep(2)
    print('Error: Tiempo de espera agotado al conectar a PostgreSQL.')
    sys.exit(1)
except Exception as e:
    print('No se pudo verificar la base de datos a través de DATABASE_URL. Saltando verificación...', e)
    sys.exit(0)
"

echo "=== [3/3] Aplicando Migraciones de Base de Datos ==="
# Aplica las migraciones estructurales a la base de datos de manera automatizada
python manage.py migrate --noinput

# Si se pasan argumentos al script (como python manage.py runserver en desarrollo local), los ejecutamos.
# De lo contrario, iniciamos el servidor de producción Gunicorn (como en Google Cloud Run).
if [ $# -gt 0 ]; then
    echo "🔧 Ejecutando comando de desarrollo: $@"
    exec "$@"
else
    # Iniciar el Servidor de Producción (Gunicorn + Uvicorn workers)
    # Google Cloud Run inyecta dinámicamente la variable de entorno $PORT (por defecto suele ser 8080)
    PORT="${PORT:-8080}"
    echo "🚀 Iniciando Servidor Web con Gunicorn en 0.0.0.0:$PORT ..."
    echo "🔧 Configuración: workers=4, class=uvicorn.workers.UvicornWorker"

    exec gunicorn config.asgi:application \
        --bind "0.0.0.0:$PORT" \
        --workers 4 \
        --worker-class uvicorn.workers.UvicornWorker \
        --threads 4 \
        --timeout 0
fi
