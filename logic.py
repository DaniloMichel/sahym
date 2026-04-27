"""
logic.py — Lógica de negocio.
Las fotos se guardan como bytes en la base de datos (columna BYTEA/BLOB)
para que sobrevivan reinicios del servidor en Render.
"""
import os
import base64
import shutil
import sqlite3
from datetime import datetime
from io import BytesIO

import pandas as pd
from PIL import Image

from database import conectar_db, _hash_password, PH, USE_PG, sql_date, sql_time


# ══════════════════════════════════════════════════════════════
# AUTENTICACIÓN Y USUARIOS
# ══════════════════════════════════════════════════════════════

def verificar_login(username: str, password: str):
    with conectar_db() as conn:
        c = conn.cursor()
        c.execute(
            f"SELECT id, username, password_hash, salt, rol, activo "
            f"FROM usuarios WHERE username = {PH}",
            (username,),
        )
        row = c.fetchone()
    if not row:
        return None
    uid, uname, stored, salt, rol, activo = row[0], row[1], row[2], row[3], row[4], row[5]
    if not activo:
        return None
    if _hash_password(password, salt) == stored:
        return {"id": uid, "username": uname, "rol": rol}
    return None


def crear_usuario(username: str, password: str, rol: str):
    salt  = os.urandom(16).hex()
    phash = _hash_password(password, salt)
    try:
        with conectar_db() as conn:
            conn.execute(
                f"INSERT INTO usuarios (username, password_hash, salt, rol) "
                f"VALUES ({PH},{PH},{PH},{PH})",
                (username, phash, salt, rol),
            )
        return True, None
    except Exception as e:
        msg = str(e)
        if "unique" in msg.lower() or "duplicate" in msg.lower():
            return False, f"El usuario '{username}' ya existe."
        return False, msg


def cambiar_password(usuario_id: int, nueva: str):
    salt  = os.urandom(16).hex()
    phash = _hash_password(nueva, salt)
    with conectar_db() as conn:
        conn.execute(
            f"UPDATE usuarios SET password_hash={PH}, salt={PH} WHERE id={PH}",
            (phash, salt, usuario_id),
        )


def toggle_usuario(usuario_id: int):
    with conectar_db() as conn:
        conn.execute(
            f"UPDATE usuarios SET activo = CASE WHEN activo=1 THEN 0 ELSE 1 END "
            f"WHERE id={PH}",
            (usuario_id,),
        )


def obtener_usuarios() -> pd.DataFrame:
    with conectar_db() as conn:
        c = conn.cursor()
        c.execute("SELECT id, username, rol, activo FROM usuarios ORDER BY id")
        rows = c.fetchall()
    return pd.DataFrame(rows, columns=["id", "username", "rol", "activo"])


# ══════════════════════════════════════════════════════════════
# FOTOS — guardadas en base de datos como bytes
# ══════════════════════════════════════════════════════════════

def imagen_a_bytes(archivo) -> tuple:
    """
    Convierte un archivo subido a (bytes, mime_type).
    Devuelve (None, None) si no hay archivo.
    """
    if archivo is None:
        return None, None
    try:
        img  = Image.open(archivo)
        buf  = BytesIO()
        img.convert("RGB").save(buf, "JPEG")
        return buf.getvalue(), "image/jpeg"
    except Exception:
        return None, None


def foto_a_base64(foto_bytes) -> str:
    """Convierte bytes de foto a data URI para mostrar en st.data_editor."""
    if foto_bytes is None:
        return None
    try:
        if isinstance(foto_bytes, memoryview):
            foto_bytes = bytes(foto_bytes)
        data = base64.b64encode(foto_bytes).decode()
        return f"data:image/jpeg;base64,{data}"
    except Exception:
        return None


# ══════════════════════════════════════════════════════════════
# PRODUCTOS
# ══════════════════════════════════════════════════════════════

def registrar_producto(nombre, marca, categoria, codigo, talla, color,
                       costo, venta, stock, archivo_foto):
    foto_bytes, foto_mime = imagen_a_bytes(archivo_foto)
    try:
        with conectar_db() as conn:
            c = conn.cursor()
            # SQLite: INSERT OR IGNORE INTO ...
            # PostgreSQL: INSERT INTO ... ON CONFLICT DO NOTHING
            if USE_PG:
                sql_ins = (f"INSERT INTO productos (nombre, marca, categoria) "
                           f"VALUES ({PH},{PH},{PH}) ON CONFLICT DO NOTHING")
            else:
                sql_ins = (f"INSERT OR IGNORE INTO productos (nombre, marca, categoria) "
                           f"VALUES ({PH},{PH},{PH})")
            c.execute(sql_ins, (nombre, marca, categoria))
            c.execute(f"SELECT id FROM productos WHERE nombre={PH}", (nombre,))
            pid = c.fetchone()[0]
            c.execute(
                f"""INSERT INTO variantes
                    (producto_id, codigo_barras, talla, color,
                     precio_costo, precio_venta, stock, foto, foto_mime)
                    VALUES ({PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH},{PH})""",
                (pid, codigo, talla, color, costo, venta, stock, foto_bytes, foto_mime),
            )
        return True, None
    except Exception as e:
        msg = str(e)
        if "unique" in msg.lower() or "duplicate" in msg.lower():
            return False, "El código de barras ya existe."
        return False, msg


def buscar_producto(codigo):
    if not codigo:
        return None
    with conectar_db() as conn:
        c = conn.cursor()
        c.execute(
            f"""SELECT v.id, p.nombre, p.categoria, v.talla, v.color,
                       v.precio_venta, v.stock, v.foto
                FROM variantes v
                JOIN productos p ON v.producto_id = p.id
                WHERE v.codigo_barras = {PH}""",
            (codigo,),
        )
        return c.fetchone()


def eliminar_producto(id_variante):
    with conectar_db() as conn:
        c = conn.cursor()
        c.execute(f"DELETE FROM variantes WHERE id={PH}", (id_variante,))


def actualizar_producto(id_variante, nuevo_stock, nuevo_precio,
                        archivo_foto=None, codigo_barras=None):
    with conectar_db() as conn:
        c = conn.cursor()
        if archivo_foto is not None:
            foto_bytes, foto_mime = imagen_a_bytes(archivo_foto)
            c.execute(
                f"UPDATE variantes SET stock={PH}, precio_venta={PH}, "
                f"foto={PH}, foto_mime={PH} WHERE id={PH}",
                (nuevo_stock, nuevo_precio, foto_bytes, foto_mime, id_variante),
            )
        else:
            c.execute(
                f"UPDATE variantes SET stock={PH}, precio_venta={PH} WHERE id={PH}",
                (nuevo_stock, nuevo_precio, id_variante),
            )


# ══════════════════════════════════════════════════════════════
# VENTAS
# ══════════════════════════════════════════════════════════════

def confirmar_venta_carrito(carrito: list, usuario_id: int):
    errores = []
    with conectar_db() as conn:
        c = conn.cursor()
        for item in carrito:
            c.execute(f"SELECT stock FROM variantes WHERE id={PH}", (item["id_v"],))
            row = c.fetchone()
            if not row or row[0] < item["cantidad"]:
                errores.append(f"Sin stock suficiente: {item['nombre']}")
                continue
            c.execute(
                f"UPDATE variantes SET stock = stock - {PH} WHERE id={PH}",
                (item["cantidad"], item["id_v"]),
            )
            c.execute(
                f"INSERT INTO ventas (variante_id, cantidad, total_venta, usuario_id) "
                f"VALUES ({PH},{PH},{PH},{PH})",
                (item["id_v"], item["cantidad"],
                 item["precio"] * item["cantidad"], usuario_id),
            )
    return errores


# ══════════════════════════════════════════════════════════════
# PROVEEDORES
# ══════════════════════════════════════════════════════════════

def obtener_proveedores() -> pd.DataFrame:
    with conectar_db() as conn:
        c = conn.cursor()
        c.execute("SELECT id, nombre, telefono, notas FROM proveedores ORDER BY nombre")
        rows = c.fetchall()
    return pd.DataFrame(rows, columns=["id", "nombre", "telefono", "notas"])


def registrar_proveedor(nombre: str, telefono: str, notas: str):
    try:
        with conectar_db() as conn:
            conn.execute(
                f"INSERT INTO proveedores (nombre, telefono, notas) VALUES ({PH},{PH},{PH})",
                (nombre, telefono, notas),
            )
        return True, None
    except Exception as e:
        return False, str(e)


def eliminar_proveedor(proveedor_id: int):
    with conectar_db() as conn:
        conn.execute(f"DELETE FROM proveedores WHERE id={PH}", (proveedor_id,))


# ══════════════════════════════════════════════════════════════
# COMPRAS
# ══════════════════════════════════════════════════════════════

def registrar_compra(proveedor_id, items: list, notas: str, usuario_id: int):
    alertas = []
    try:
        with conectar_db() as conn:
            c = conn.cursor()
            total = sum(it["cantidad"] * it["precio_costo"] for it in items)
            c.execute(
                f"INSERT INTO compras (proveedor_id, total, notas, usuario_id) "
                f"VALUES ({PH},{PH},{PH},{PH})",
                (proveedor_id if proveedor_id else None, total, notas, usuario_id),
            )
            if USE_PG:
                c.execute("SELECT lastval()")
            else:
                c.execute("SELECT last_insert_rowid()")
            compra_id = c.fetchone()[0]

            for it in items:
                c.execute(
                    f"SELECT precio_costo FROM variantes WHERE id={PH}",
                    (it["variante_id"],)
                )
                row = c.fetchone()
                if row and row[0] and it["precio_costo"] > row[0]:
                    c.execute(
                        f"SELECT p.nombre FROM variantes v "
                        f"JOIN productos p ON v.producto_id=p.id WHERE v.id={PH}",
                        (it["variante_id"],)
                    )
                    nombre = c.fetchone()[0]
                    alertas.append(f"{nombre}: {row[0]:.2f} → {it['precio_costo']:.2f} CUP")

                c.execute(
                    f"UPDATE variantes SET stock = stock + {PH}, precio_costo = {PH} WHERE id={PH}",
                    (it["cantidad"], it["precio_costo"], it["variante_id"]),
                )
                c.execute(
                    f"INSERT INTO compras_detalle (compra_id, variante_id, cantidad, precio_costo) "
                    f"VALUES ({PH},{PH},{PH},{PH})",
                    (compra_id, it["variante_id"], it["cantidad"], it["precio_costo"]),
                )
        return True, alertas
    except Exception as e:
        return False, str(e)


def obtener_historial_compras(fecha_inicio, fecha_fin) -> pd.DataFrame:
    d = sql_date("c.fecha")
    with conectar_db() as conn:
        c = conn.cursor()
        c.execute(f"""
            SELECT c.id, {d}, COALESCE(pr.nombre,'Sin proveedor'),
                   p.nombre, cd.cantidad, cd.precio_costo,
                   cd.cantidad * cd.precio_costo,
                   COALESCE(u.username,'—')
            FROM compras c
            JOIN compras_detalle cd ON cd.compra_id   = c.id
            JOIN variantes v        ON cd.variante_id = v.id
            JOIN productos p        ON v.producto_id  = p.id
            LEFT JOIN proveedores pr ON c.proveedor_id = pr.id
            LEFT JOIN usuarios u     ON c.usuario_id   = u.id
            WHERE {d} BETWEEN {PH} AND {PH}
            ORDER BY c.fecha DESC
        """, (str(fecha_inicio), str(fecha_fin)))
        rows = c.fetchall()
    return pd.DataFrame(rows, columns=[
        "Compra", "Fecha", "Proveedor", "Producto",
        "Cantidad", "Costo Unit.", "Subtotal", "Registrado por"
    ])


def obtener_historial_precios(variante_id: int) -> pd.DataFrame:
    d = sql_date("c.fecha")
    with conectar_db() as conn:
        c = conn.cursor()
        c.execute(f"""
            SELECT {d}, cd.precio_costo, cd.cantidad, COALESCE(pr.nombre,'Sin proveedor')
            FROM compras_detalle cd
            JOIN compras c ON cd.compra_id = c.id
            LEFT JOIN proveedores pr ON c.proveedor_id = pr.id
            WHERE cd.variante_id = {PH}
            ORDER BY c.fecha DESC
        """, (variante_id,))
        rows = c.fetchall()
    return pd.DataFrame(rows, columns=["Fecha", "Precio Costo", "Cantidad", "Proveedor"])


# ══════════════════════════════════════════════════════════════
# INVENTARIO Y REPORTES
# ══════════════════════════════════════════════════════════════

def obtener_inventario() -> pd.DataFrame:
    with conectar_db() as conn:
        c = conn.cursor()
        c.execute("""
            SELECT v.id, p.categoria, p.nombre, p.marca,
                   v.codigo_barras, v.talla, v.color,
                   v.precio_costo, v.precio_venta, v.stock, v.foto
            FROM productos p
            JOIN variantes v ON p.id = v.producto_id
        """)
        rows = c.fetchall()
    return pd.DataFrame(rows, columns=[
        "id", "categoria", "nombre", "marca",
        "codigo_barras", "talla", "color",
        "precio_costo", "precio_venta", "stock", "foto"
    ])


def obtener_ventas_por_fecha(fecha_inicio, fecha_fin) -> pd.DataFrame:
    d = sql_date("ven.fecha")
    with conectar_db() as conn:
        c = conn.cursor()
        c.execute(f"""
            SELECT p.nombre, p.categoria, v.precio_costo,
                   ven.total_venta, ven.cantidad,
                   COALESCE(u.username,'—'), {d}
            FROM ventas ven
            JOIN variantes v  ON ven.variante_id = v.id
            JOIN productos p  ON v.producto_id   = p.id
            LEFT JOIN usuarios u ON ven.usuario_id = u.id
            WHERE {d} BETWEEN {PH} AND {PH}
            ORDER BY ven.fecha DESC
        """, (str(fecha_inicio), str(fecha_fin)))
        rows = c.fetchall()
    return pd.DataFrame(rows, columns=[
        "Producto", "Categoria", "Costo", "Venta", "Cantidad", "Cajero", "Fecha"
    ])


# ══════════════════════════════════════════════════════════════
# DASHBOARD
# ══════════════════════════════════════════════════════════════

def obtener_resumen_dia() -> dict:
    hoy = datetime.now().strftime("%Y-%m-%d")
    d_ven = sql_date("ven.fecha")
    d_gen = sql_date("fecha")
    t_fmt = sql_time("ven.fecha")

    with conectar_db() as conn:
        c = conn.cursor()

        c.execute(f"""
            SELECT COUNT(DISTINCT ven.id),
                   COALESCE(SUM(ven.total_venta), 0),
                   COALESCE(SUM(ven.cantidad), 0)
            FROM ventas ven WHERE {d_ven} = {PH}
        """, (hoy,))
        n_ventas, total_ventas, articulos = c.fetchone()

        c.execute(f"""
            SELECT COALESCE(SUM(ven.total_venta - v.precio_costo * ven.cantidad), 0)
            FROM ventas ven
            JOIN variantes v ON ven.variante_id = v.id
            WHERE {d_ven} = {PH}
        """, (hoy,))
        ganancia = c.fetchone()[0]

        c.execute("""
            SELECT p.nombre, v.stock FROM variantes v
            JOIN productos p ON v.producto_id = p.id
            WHERE v.stock <= 3 ORDER BY v.stock ASC
        """)
        stock_bajo = c.fetchall()

        c.execute(f"""
            SELECT p.nombre, ven.cantidad, ven.total_venta,
                   {t_fmt}, COALESCE(u.username,'desconocido')
            FROM ventas ven
            JOIN variantes v  ON ven.variante_id = v.id
            JOIN productos p  ON v.producto_id   = p.id
            LEFT JOIN usuarios u ON ven.usuario_id = u.id
            WHERE {d_ven} = {PH}
            ORDER BY ven.fecha DESC LIMIT 5
        """, (hoy,))
        ultimas = c.fetchall()

        c.execute("SELECT COUNT(*), COALESCE(SUM(stock),0) FROM variantes")
        n_productos, total_stock = c.fetchone()

    return {
        "n_ventas": int(n_ventas), "total_ventas": float(total_ventas),
        "articulos": int(articulos), "ganancia": float(ganancia),
        "stock_bajo": stock_bajo, "ultimas": ultimas,
        "n_productos": int(n_productos), "total_stock": int(total_stock),
        "fecha": hoy,
    }


# ══════════════════════════════════════════════════════════════
# RESPALDO
# ══════════════════════════════════════════════════════════════

CARPETA_BACKUPS = "backups"

def backup_db() -> str:
    """Solo funciona en local (SQLite). En Render el backup es PostgreSQL."""
    if USE_PG:
        return None
    from database import DATABASE_URL as _url
    db_path = "tienda.db"
    if not os.path.exists(db_path):
        return None
    os.makedirs(CARPETA_BACKUPS, exist_ok=True)
    ts      = datetime.now().strftime("%Y%m%d_%H%M%S")
    destino = os.path.join(CARPETA_BACKUPS, f"tienda_{ts}.db")
    shutil.copy2(db_path, destino)
    archivos = sorted(
        [f for f in os.listdir(CARPETA_BACKUPS) if f.endswith(".db")], reverse=True
    )
    for viejo in archivos[30:]:
        os.remove(os.path.join(CARPETA_BACKUPS, viejo))
    return destino


def leer_backup(ruta: str) -> bytes:
    with open(ruta, "rb") as f:
        return f.read()


# ══════════════════════════════════════════════════════════════
# EXPORTACIÓN
# ══════════════════════════════════════════════════════════════

def df_a_excel(df: pd.DataFrame) -> bytes:
    buf = BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="Datos")
    return buf.getvalue()
