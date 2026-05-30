import sqlite3
from config import DB_PATH

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS usuarios (
            user_id INTEGER PRIMARY KEY,
            nombre TEXT,
            lat REAL,
            lon REAL,
            cultivo TEXT DEFAULT 'soya',
            zona TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS consultas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            tipo TEXT,
            respuesta TEXT,
            feedback INTEGER,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()

def guardar_usuario(user_id, nombre, lat, lon, cultivo='soya', zona=''):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""
        INSERT OR REPLACE INTO usuarios (user_id, nombre, lat, lon, cultivo, zona)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (user_id, nombre, lat, lon, cultivo, zona))
    conn.commit()
    conn.close()

def obtener_usuario(user_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT * FROM usuarios WHERE user_id = ?", (user_id,))
    row = c.fetchone()
    conn.close()
    return row

def guardar_consulta(user_id, tipo, respuesta):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute(
        "INSERT INTO consultas (user_id, tipo, respuesta) VALUES (?, ?, ?)",
        (user_id, tipo, respuesta)
    )
    conn.commit()
    conn.close()
