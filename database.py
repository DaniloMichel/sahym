"""
database.py
Soporta SQLite (desarrollo local) y PostgreSQL (Render.com).
La variable de entorno DATABASE_URL activa PostgreSQL automáticamente.
"""
import hashlib
import os
import sqlite3

# ── Detección de entorno ─────────────────────────────────────
DATABASE_URL = os.environ.get("DATABASE_URL", "")
USE_PG       = bool(DATABASE_URL)          # True en Render, False en local
PH           = "%s" if USE_PG else "?"     # placeholder de parámetros


class _Conn:
    """
    Wrapper que hace que psycopg2 y sqlite3 se comporten igual
    dentro de un bloque `with conectar_db() as conn:`.
    Commit en éxito, rollback en excepción, close siempre.
    """
    def __init__(self):
        if USE_PG:
            import psycopg2
            url = DATABASE_URL.replace("postgres://", "postgresql://", 1)
            self._conn = psycopg2.connect(url)
        else:
            self._conn = sqlite3.connect("tienda.db")
            self._conn.row_factory = sqlite3.Row

    # Delegamos cursor, execute y commit al objeto interno
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


# ── Helpers de SQL que difieren entre motores ─────────────────
def sql_autoincrement():
    return "SERIAL PRIMARY KEY" if USE_PG else "INTEGER PRIMARY KEY AUTOINCREMENT"

def sql_date(col: str) -> str:
    """Extrae la parte DATE de un timestamp."""
    return f"{col}::date" if USE_PG else f"DATE({col})"

def sql_time(col: str) -> str:
    """Extrae HH:MM de un timestamp."""
    return f"TO_CHAR({col}, 'HH24:MI')" if USE_PG else f"strftime('%H%%M', {col})"

def sql_now() -> str:
    return "NOW()" if USE_PG else "CURRENT_TIMESTAMP"


# ── Hash de contraseña ────────────────────────────────────────
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

        # ── Migración: columnas foto en variantes ────────────
        if not USE_PG:
            cols = [r[1] for r in c.execute("PRAGMA table_info(variantes)")]
            if "foto" not in cols:
                c.execute("ALTER TABLE variantes ADD COLUMN foto BLOB")
            if "foto_mime" not in cols:
                c.execute("ALTER TABLE variantes ADD COLUMN foto_mime TEXT")
            # usuario_id en ventas
            cols_v = [r[1] for r in c.execute("PRAGMA table_info(ventas)")]
            if "usuario_id" not in cols_v:
                c.execute("ALTER TABLE ventas ADD COLUMN usuario_id INTEGER")

        conn.commit()

        # ── Seed: admin por defecto ──────────────────────────
        c.execute(f"SELECT COUNT(*) FROM usuarios")
        row = c.fetchone()
        count = row[0] if row else 0
        if count == 0:
            salt  = os.urandom(16).hex()
            phash = _hash_password("admin123", salt)
            c.execute(
                f"INSERT INTO usuarios (username, password_hash, salt, rol) "
                f"VALUES ({PH},{PH},{PH},{PH})",
                ("admin", phash, salt, "admin"),
            )
            conn.commit()
