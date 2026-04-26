"""
database.py
Soporta SQLite (desarrollo local) y PostgreSQL en Supabase (producción).

En local:             usa tienda.db automáticamente
En Streamlit Cloud:   lee DATABASE_URL desde st.secrets["DATABASE_URL"]
"""
import hashlib
import os
import sqlite3

# ── Detección de entorno ─────────────────────────────────────
def _get_database_url() -> str:
    """
    Busca la URL de PostgreSQL en este orden:
    1. Variable de entorno DATABASE_URL
    2. st.secrets["DATABASE_URL"]   (Streamlit Community Cloud)
    3. Vacío → usa SQLite local
    """
    url = os.environ.get("DATABASE_URL", "")
    if url:
        return url
    try:
        import streamlit as st
        return st.secrets.get("DATABASE_URL", "")
    except Exception:
        return ""

DATABASE_URL = _get_database_url()
USE_PG       = bool(DATABASE_URL)
PH           = "%s" if USE_PG else "?"


class _Conn:
    """
    Wrapper uniforme para sqlite3 y psycopg2.
    Úsalo siempre con: `with conectar_db() as conn:`
    """
    def __init__(self):
        if USE_PG:
            import psycopg2
            url = DATABASE_URL.replace("postgres://", "postgresql://", 1)
            self._conn = psycopg2.connect(url)
        else:
            self._conn = sqlite3.connect("tienda.db")
            self._conn.row_factory = sqlite3.Row

    def cursor(self):      return self._conn.cursor()
    def execute(self, *a): return self._conn.execute(*a)
    def commit(self):      self._conn.commit()
    def rollback(self):    self._conn.rollback()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, *_):
        if exc_type is None:
            self._conn.commit()
        else:
            self._conn.rollback()
        self._conn.close()


def conectar_db():
    return _Conn()


# ── Helpers SQL compatibles entre motores ─────────────────────
def sql_autoincrement():
    return "SERIAL PRIMARY KEY" if USE_PG else "INTEGER PRIMARY KEY AUTOINCREMENT"

def sql_date(col: str) -> str:
    return f"{col}::date" if USE_PG else f"DATE({col})"

def sql_time(col: str) -> str:
    return f"TO_CHAR({col}, 'HH24:MI')" if USE_PG else f"strftime('%H:%M', {col})"

def sql_now() -> str:
    return "NOW()" if USE_PG else "CURRENT_TIMESTAMP"


# ── Hash seguro de contraseñas ────────────────────────────────
def _hash_password(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode(), salt.encode(), 260_000
    ).hex()


# ── Inicialización de tablas ──────────────────────────────────
def inicializar_db():
    ai  = sql_autoincrement()
    now = sql_now()

    with conectar_db() as conn:
        c = conn.cursor()

        c.execute(f"""
            CREATE TABLE IF NOT EXISTS productos (
                id        {ai},
                nombre    TEXT NOT NULL,
                marca     TEXT,
                categoria TEXT
            )
        """)
        c.execute(f"""
            CREATE TABLE IF NOT EXISTS variantes (
                id             {ai},
                producto_id    INTEGER,
                codigo_barras  TEXT UNIQUE,
                talla          TEXT,
                color          TEXT,
                precio_costo   REAL,
                precio_venta   REAL,
                stock          INTEGER DEFAULT 0,
                foto           BYTEA,
                foto_mime      TEXT,
                FOREIGN KEY (producto_id) REFERENCES productos(id)
            )
        """)
        c.execute(f"""
            CREATE TABLE IF NOT EXISTS usuarios (
                id            {ai},
                username      TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                salt          TEXT NOT NULL,
                rol           TEXT NOT NULL,
                activo        INTEGER DEFAULT 1
            )
        """)
        c.execute(f"""
            CREATE TABLE IF NOT EXISTS ventas (
                id           {ai},
                variante_id  INTEGER,
                cantidad     INTEGER,
                total_venta  REAL,
                fecha        TIMESTAMP DEFAULT {now},
                usuario_id   INTEGER,
                FOREIGN KEY (variante_id) REFERENCES variantes(id),
                FOREIGN KEY (usuario_id)  REFERENCES usuarios(id)
            )
        """)
        c.execute(f"""
            CREATE TABLE IF NOT EXISTS proveedores (
                id       {ai},
                nombre   TEXT NOT NULL,
                telefono TEXT,
                notas    TEXT
            )
        """)
        c.execute(f"""
            CREATE TABLE IF NOT EXISTS compras (
                id            {ai},
                proveedor_id  INTEGER,
                fecha         TIMESTAMP DEFAULT {now},
                total         REAL,
                notas         TEXT,
                usuario_id    INTEGER,
                FOREIGN KEY (proveedor_id) REFERENCES proveedores(id),
                FOREIGN KEY (usuario_id)   REFERENCES usuarios(id)
            )
        """)
        c.execute(f"""
            CREATE TABLE IF NOT EXISTS compras_detalle (
                id              {ai},
                compra_id       INTEGER,
                variante_id     INTEGER,
                cantidad        INTEGER,
                precio_costo    REAL,
                FOREIGN KEY (compra_id)   REFERENCES compras(id),
                FOREIGN KEY (variante_id) REFERENCES variantes(id)
            )
        """)

        # Migraciones solo en SQLite
        if not USE_PG:
            cols = [r[1] for r in c.execute("PRAGMA table_info(variantes)")]
            for col, tipo in [("foto", "BLOB"), ("foto_mime", "TEXT")]:
                if col not in cols:
                    c.execute(f"ALTER TABLE variantes ADD COLUMN {col} {tipo}")
            cols_v = [r[1] for r in c.execute("PRAGMA table_info(ventas)")]
            if "usuario_id" not in cols_v:
                c.execute("ALTER TABLE ventas ADD COLUMN usuario_id INTEGER")

        conn.commit()

        # Seed: crear admin por defecto si no hay usuarios
        c.execute("SELECT COUNT(*) FROM usuarios")
        if c.fetchone()[0] == 0:
            salt  = os.urandom(16).hex()
            phash = _hash_password("admin123", salt)
            c.execute(
                f"INSERT INTO usuarios (username, password_hash, salt, rol) "
                f"VALUES ({PH},{PH},{PH},{PH})",
                ("admin", phash, salt, "admin"),
            )
            conn.commit()
