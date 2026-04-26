"""
app.py — SAHYM
Pestañas admin: Inicio | Ventas | Inventario | Compras | Reportes | Usuarios
Pestañas cajero: Ventas
Usuario por defecto: admin / admin123
"""
import os
from datetime import date, datetime

import pandas as pd
import streamlit as st
from PIL import Image
from pyzbar.pyzbar import decode

from database import inicializar_db
from logic import (
    actualizar_producto, backup_db, buscar_producto, cambiar_password,
    confirmar_venta_carrito, crear_usuario, df_a_excel, eliminar_producto,
    eliminar_proveedor, foto_a_base64, leer_backup,
    obtener_historial_compras, obtener_historial_precios,
    obtener_inventario, obtener_proveedores, obtener_resumen_dia,
    obtener_usuarios, obtener_ventas_por_fecha, registrar_compra,
    registrar_producto, registrar_proveedor, toggle_usuario, verificar_login,
)

# ════════════════════════════════════════════════════════════
# CONFIGURACIÓN
# ════════════════════════════════════════════════════════════
st.set_page_config(page_title="SAHYM", layout="wide")
inicializar_db()

CATEGORIAS = [
    "Electrodomésticos", "Móviles y Piezas", "Accesorios Tech",
    "Hogar", "Aseo y Limpieza", "Otros",
]

for key, val in [("usuario", None), ("carrito", []),
                 ("carrito_compra", []), ("ultimo_recibo", None),
                 ("backup_ruta", None)]:
    if key not in st.session_state:
        st.session_state[key] = val


# ════════════════════════════════════════════════════════════
# LOGIN
# ════════════════════════════════════════════════════════════
def pantalla_login():
    _, col, _ = st.columns([1, 1, 1])
    with col:
        st.markdown("<br><br>", unsafe_allow_html=True)
        st.title("SAHYM")
        st.markdown("---")
        with st.form("f_login"):
            username = st.text_input("Usuario")
            password = st.text_input("Contraseña", type="password")
            if st.form_submit_button("Iniciar sesión", use_container_width=True):
                u = verificar_login(username, password)
                if u:
                    st.session_state.usuario     = u
                    st.session_state.backup_ruta = backup_db()   # backup al entrar
                    st.rerun()
                else:
                    st.error("Usuario o contraseña incorrectos.")


if st.session_state.usuario is None:
    pantalla_login()
    st.stop()

usuario  = st.session_state.usuario
es_admin = usuario["rol"] == "admin"

# ════════════════════════════════════════════════════════════
# CABECERA
# ════════════════════════════════════════════════════════════
col_t, col_u = st.columns([4, 1])
with col_t:
    st.title("SAHYM")
with col_u:
    st.markdown(f"**{usuario['username']}** `{usuario['rol']}`")
    if st.button("Cerrar sesión", use_container_width=True):
        for k in ["usuario", "carrito", "carrito_compra", "ultimo_recibo", "backup_ruta"]:
            st.session_state[k] = None if k not in ["carrito","carrito_compra"] else []
        st.rerun()

st.divider()

# ════════════════════════════════════════════════════════════
# PESTAÑAS
# ════════════════════════════════════════════════════════════
if es_admin:
    t0, t1, t2, t3, t4, t5 = st.tabs(
        ["Inicio", "Ventas", "Inventario", "Compras", "Reportes", "Usuarios"]
    )
else:
    t1 = st.tabs(["Ventas"])[0]


# ════════════════════════════════════════════════════════════
# PESTAÑA 0: DASHBOARD  (solo admin)
# ════════════════════════════════════════════════════════════
if es_admin:
    with t0:
        res = obtener_resumen_dia()
        st.subheader(f"Resumen del día — {res['fecha']}")

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Ventas realizadas",  res["n_ventas"])
        k2.metric("Ingresos del día",   f"{res['total_ventas']:,.2f} CUP")
        k3.metric("Ganancia neta",      f"{res['ganancia']:,.2f} CUP")
        k4.metric("Artículos vendidos", res["articulos"])

        st.divider()
        col_d1, col_d2 = st.columns(2)

        with col_d1:
            st.subheader("Últimas ventas")
            if res["ultimas"]:
                df_ult = pd.DataFrame(
                    res["ultimas"],
                    columns=["Producto", "Cant.", "Total CUP", "Hora", "Cajero"]
                )
                st.dataframe(df_ult, use_container_width=True, hide_index=True)
            else:
                st.info("Aún no hay ventas hoy.")

        with col_d2:
            st.subheader("Inventario")
            m1, m2 = st.columns(2)
            m1.metric("Productos distintos", res["n_productos"])
            m2.metric("Unidades en stock",   res["total_stock"])

            if res["stock_bajo"]:
                st.warning("Productos con stock bajo (≤ 3 uds):")
                for nombre, stock in res["stock_bajo"]:
                    color = "red" if stock == 0 else "orange"
                    st.markdown(
                        f"<span style='color:{color}'>● {nombre} — {stock} uds</span>",
                        unsafe_allow_html=True,
                    )
            else:
                st.success("Todo el inventario tiene stock suficiente.")

        st.divider()
        st.subheader("Respaldo de base de datos")
        col_b1, col_b2 = st.columns(2)
        with col_b1:
            if st.button("Crear respaldo ahora", use_container_width=True):
                ruta = backup_db()
                if ruta:
                    st.session_state.backup_ruta = ruta
                    st.success(f"Respaldo creado: {os.path.basename(ruta)}")
                else:
                    st.error("No se encontró la base de datos.")

        with col_b2:
            ruta_actual = st.session_state.backup_ruta
            if ruta_actual and os.path.exists(ruta_actual):
                st.download_button(
                    f"Descargar — {os.path.basename(ruta_actual)}",
                    data=leer_backup(ruta_actual),
                    file_name=os.path.basename(ruta_actual),
                    mime="application/octet-stream",
                    use_container_width=True,
                )
            else:
                st.info("Crea un respaldo para poder descargarlo.")


# ════════════════════════════════════════════════════════════
# PESTAÑA 1: VENTAS
# ════════════════════════════════════════════════════════════
with t1:
    st.header("Punto de Venta")

    # ── Mostrar recibo si acaba de confirmar una venta ───────
    if st.session_state.ultimo_recibo:
        r = st.session_state.ultimo_recibo
        recibo_html = f"""
        <div id="recibo" style="font-family:monospace;max-width:320px;
             padding:16px;border:1px solid #ccc;border-radius:8px;font-size:13px;">
          <div style="text-align:center;font-size:18px;font-weight:bold;">SAHYM</div>
          <div style="text-align:center;color:#666;margin-bottom:8px;">
            {r['fecha']} &nbsp;|&nbsp; Cajero: {r['cajero']}
          </div>
          <hr style="border:none;border-top:1px dashed #999;margin:6px 0;">
          {''.join(f"<div style='display:flex;justify-content:space-between;'>"
                   f"<span>{it['nombre']} x{it['cantidad']}</span>"
                   f"<span>{it['precio']*it['cantidad']:,.2f}</span></div>"
                   for it in r['items'])}
          <hr style="border:none;border-top:1px dashed #999;margin:6px 0;">
          <div style="display:flex;justify-content:space-between;font-weight:bold;">
            <span>TOTAL</span><span>{r['total']:,.2f} CUP</span>
          </div>
          <div style="text-align:center;margin-top:10px;color:#888;">
            Gracias por su compra
          </div>
        </div>
        <button onclick="imprimirRecibo()"
          style="margin-top:10px;padding:6px 16px;cursor:pointer;border-radius:6px;
                 border:1px solid #ccc;background:#f5f5f5;">
          Imprimir recibo
        </button>
        <script>
        function imprimirRecibo() {{
            var c = document.getElementById('recibo').innerHTML;
            var w = window.open('','','width=400,height=500');
            w.document.write('<html><body style="font-family:monospace">'+c+'</body></html>');
            w.document.close(); w.print(); w.close();
        }}
        </script>
        """
        st.components.v1.html(recibo_html, height=340)
        if st.button("Cerrar recibo"):
            st.session_state.ultimo_recibo = None
            st.rerun()
        st.divider()

    col_scan, col_cart = st.columns([1, 1])

    with col_scan:
        st.subheader("Agregar Producto")
        foto_scan = st.file_uploader(
            "Escanear código", type=["jpg","png","jpeg"], key="v_scan"
        )
        c_det = ""
        if foto_scan:
            res_s = decode(Image.open(foto_scan))
            if res_s:
                c_det = res_s[0].data.decode("utf-8")
                st.success(f"Detectado: **{c_det}**")
            else:
                st.warning("No se detectó código.")

        cod = st.text_input("O escribe el código", value=c_det, key="cod_v")
        qty = st.number_input("Cantidad", min_value=1, value=1, step=1, key="qty_v")

        if st.button("Agregar al carrito", use_container_width=True):
            prod = buscar_producto(cod)
            if not prod:
                st.error("Código no encontrado.")
            else:
                id_v, nombre, cat, talla, color, precio, stock, foto = prod
                if stock < qty:
                    st.error(f"Solo hay {stock} uds de {nombre}.")
                else:
                    existe = False
                    for it in st.session_state.carrito:
                        if it["id_v"] == id_v:
                            it["cantidad"] += qty; existe = True; break
                    if not existe:
                        st.session_state.carrito.append({
                            "id_v": id_v, "nombre": nombre,
                            "detalle": f"{talla}/{color}" if (talla or color) else "-",
                            "precio": precio, "cantidad": qty, "foto": foto,
                        })
                    st.rerun()

    with col_cart:
        st.subheader("Carrito")
        if not st.session_state.carrito:
            st.info("Carrito vacío.")
        else:
            rows = [{
                "#": i+1, "Producto": it["nombre"], "Detalle": it["detalle"],
                "Precio": f"{it['precio']:,.2f}", "Cant.": it["cantidad"],
                "Subtotal CUP": f"{it['precio']*it['cantidad']:,.2f}",
            } for i, it in enumerate(st.session_state.carrito)]
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

            total = sum(i["precio"]*i["cantidad"] for i in st.session_state.carrito)
            st.markdown(f"### Total: **{total:,.2f} CUP**")

            fotos_ok = [it for it in st.session_state.carrito
                        if it["foto"] is not None]
            if fotos_ok:
                with st.expander("Ver fotos"):
                    cf = st.columns(len(fotos_ok))
                    for i, it in enumerate(fotos_ok):
                        with cf[i]:
                            foto_data = bytes(it["foto"]) if isinstance(it["foto"], memoryview) else it["foto"]
                            st.image(foto_data, caption=it["nombre"], width=80)

            b1, b2 = st.columns(2)
            with b1:
                if st.button("Vaciar", use_container_width=True):
                    st.session_state.carrito = []; st.rerun()
            with b2:
                if st.button("Confirmar Venta", use_container_width=True, type="primary"):
                    errores = confirmar_venta_carrito(st.session_state.carrito, usuario["id"])
                    if errores:
                        for e in errores: st.error(e)
                    else:
                        # Guardar datos para el recibo
                        st.session_state.ultimo_recibo = {
                            "items":  [{"nombre": it["nombre"], "cantidad": it["cantidad"],
                                        "precio": it["precio"]}
                                       for it in st.session_state.carrito],
                            "total":  total,
                            "cajero": usuario["username"],
                            "fecha":  datetime.now().strftime("%d/%m/%Y %H:%M"),
                        }
                        st.session_state.carrito = []
                        st.rerun()

if not es_admin:
    st.stop()


# ════════════════════════════════════════════════════════════
# PESTAÑA 2: INVENTARIO
# ════════════════════════════════════════════════════════════
with t2:
    st.header("Inventario")

    with st.expander("Registrar Nuevo Producto"):
        with st.form("f_prod", clear_on_submit=True):
            c1, c2, c3 = st.columns(3)
            with c1:
                n = st.text_input("Nombre *"); m = st.text_input("Marca")
                cat = st.selectbox("Categoría", CATEGORIAS)
            with c2:
                cod2 = st.text_input("Código *"); tal = st.text_input("Talla/Modelo")
                col_p = st.text_input("Color")
            with c3:
                cos = st.number_input("Costo", min_value=0.0)
                ven = st.number_input("Precio Venta", min_value=0.0)
                sto = st.number_input("Stock", min_value=0, step=1)
                foto_p = st.file_uploader("Foto", type=["jpg","png"])
            if st.form_submit_button("Guardar"):
                if n and cod2:
                    ok, err = registrar_producto(n, m, cat, cod2, tal, col_p, cos, ven, sto, foto_p)
                    st.success("Guardado.") if ok else st.error(f"Error: {err}")
                    if ok: st.rerun()
                else:
                    st.warning("Nombre y Código obligatorios.")

    st.divider()
    df_inv = obtener_inventario()
    if not df_inv.empty:
        f_cat = st.multiselect("Filtrar:", CATEGORIAS, default=CATEGORIAS)
        df_f  = df_inv[df_inv["categoria"].isin(f_cat)].copy()

        bajo = df_f[df_f["stock"] <= 3]
        if not bajo.empty:
            st.warning(f"Stock bajo (≤3): **{', '.join(bajo['nombre'].tolist())}**")

        df_f["miniatura"] = df_f["foto"].apply(foto_a_base64)
        st.data_editor(
            df_f[["id","categoria","nombre","marca","codigo_barras",
                  "talla","color","precio_costo","precio_venta","stock","miniatura"]],
            column_config={
                "miniatura":     st.column_config.ImageColumn("Foto", width="small"),
                "id":            st.column_config.NumberColumn("ID", width="small"),
                "codigo_barras": st.column_config.TextColumn("Cod. Barras"),
                "precio_costo":  st.column_config.NumberColumn("Costo", format="%.2f"),
                "precio_venta":  st.column_config.NumberColumn("Venta", format="%.2f"),
            },
            disabled=True, use_container_width=True, hide_index=True,
        )
        df_exp = df_f.drop(columns=["foto"], errors="ignore")
        e1, e2 = st.columns(2)
        with e1:
            st.download_button("Descargar CSV",
                df_exp.to_csv(index=False).encode("utf-8"),
                f"inventario_{date.today()}.csv", "text/csv", use_container_width=True)
        with e2:
            st.download_button("Descargar Excel", df_a_excel(df_exp),
                f"inventario_{date.today()}.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True)

        st.divider()
        ed, de = st.columns(2)
        with ed:
            with st.expander("Editar Producto"):
                id_e = st.selectbox("ID", df_f["id"])
                det  = df_f[df_f["id"]==id_e].iloc[0]
                with st.form("f_edit"):
                    st.write(f"**{det['nombre']}** `{det['codigo_barras']}`")
                    ns = st.number_input("Stock",  value=int(det["stock"]),          min_value=0)
                    np = st.number_input("Precio", value=float(det["precio_venta"]), min_value=0.0)
                    nf = st.file_uploader("Foto",  type=["jpg","png"])
                    if st.form_submit_button("Actualizar"):
                        try:
                            actualizar_producto(id_e, ns, np, nf, det["codigo_barras"])
                            st.success("Actualizado."); st.rerun()
                        except Exception as e:
                            st.error(f"Error: {e}")
        with de:
            with st.expander("Borrar Producto"):
                id_d  = st.selectbox("ID", df_f["id"], key="del_id")
                det_d = df_f[df_f["id"]==id_d].iloc[0]
                st.write(f"**{det_d['nombre']}** `{det_d['codigo_barras']}`")
                if st.checkbox("Confirmo eliminar") and st.button("Eliminar"):
                    eliminar_producto(id_d); st.warning("Eliminado."); st.rerun()
    else:
        st.info("No hay productos aún.")


# ════════════════════════════════════════════════════════════
# PESTAÑA 3: COMPRAS
# ════════════════════════════════════════════════════════════
with t3:
    st.header("Compras a Proveedores")
    sub1, sub2, sub3 = st.tabs(["Nueva Compra", "Historial", "Proveedores"])

    with sub1:
        df_prov = obtener_proveedores()
        df_inv2 = obtener_inventario()

        if df_inv2.empty:
            st.warning("Registra productos primero.")
        else:
            col_form, col_lista = st.columns([1, 1])

            with col_form:
                st.subheader("Agregar producto a la compra")
                opciones_prov = {"Sin proveedor": None}
                if not df_prov.empty:
                    for _, row in df_prov.iterrows():
                        opciones_prov[row["nombre"]] = row["id"]

                prov_sel     = st.selectbox("Proveedor", list(opciones_prov.keys()))
                notas_compra = st.text_input("Notas (opcional)")
                cod_c        = st.text_input("Código del producto", key="cod_compra")
                prod_c       = buscar_producto(cod_c) if cod_c else None

                if prod_c:
                    id_v_c, nom_c, _, tal_c, col_c, _, _, _ = prod_c
                    st.info(f"**{nom_c}** {tal_c or ''} {col_c or ''}")
                    qty_c   = st.number_input("Cantidad", min_value=1, value=1, step=1, key="qty_c")
                    costo_c = st.number_input("Precio costo unitario (CUP)", min_value=0.0, key="costo_c")
                    if st.button("Agregar a la compra", use_container_width=True):
                        existe = False
                        for it in st.session_state.carrito_compra:
                            if it["variante_id"] == id_v_c:
                                it["cantidad"] += qty_c; it["precio_costo"] = costo_c
                                existe = True; break
                        if not existe:
                            st.session_state.carrito_compra.append({
                                "variante_id": id_v_c, "nombre": nom_c,
                                "cantidad": qty_c, "precio_costo": costo_c,
                            })
                        st.rerun()
                elif cod_c:
                    st.error("Código no encontrado.")

            with col_lista:
                st.subheader("Resumen de la compra")
                if not st.session_state.carrito_compra:
                    st.info("Agrega productos a la izquierda.")
                else:
                    rows_c = [{
                        "Producto": it["nombre"], "Cantidad": it["cantidad"],
                        "Costo Unit.": f"{it['precio_costo']:,.2f}",
                        "Subtotal": f"{it['cantidad']*it['precio_costo']:,.2f} CUP",
                    } for it in st.session_state.carrito_compra]
                    st.dataframe(pd.DataFrame(rows_c), use_container_width=True, hide_index=True)

                    total_c = sum(it["cantidad"]*it["precio_costo"]
                                  for it in st.session_state.carrito_compra)
                    st.markdown(f"### Total: **{total_c:,.2f} CUP**")

                    b1c, b2c = st.columns(2)
                    with b1c:
                        if st.button("Vaciar", use_container_width=True, key="vac_c"):
                            st.session_state.carrito_compra = []; st.rerun()
                    with b2c:
                        if st.button("Confirmar Compra", use_container_width=True,
                                     type="primary", key="conf_c"):
                            pid = opciones_prov[prov_sel]
                            ok, resultado = registrar_compra(
                                pid, st.session_state.carrito_compra,
                                notas_compra, usuario["id"],
                            )
                            if ok:
                                n = len(st.session_state.carrito_compra)
                                st.success(f"Compra registrada. Stock actualizado ({n} producto(s)).")
                                if resultado:
                                    st.warning("Precios de costo que subieron:")
                                    for a in resultado: st.write(f"• {a}")
                                st.session_state.carrito_compra = []; st.rerun()
                            else:
                                st.error(f"Error: {resultado}")

    with sub2:
        st.subheader("Historial de Compras")
        h1, h2 = st.columns(2)
        with h1: hfi = st.date_input("Desde", value=date.today(), key="hfi")
        with h2: hff = st.date_input("Hasta", value=date.today(), key="hff")
        df_hist = obtener_historial_compras(hfi, hff)
        if not df_hist.empty:
            st.metric("Total invertido", f"{df_hist['Subtotal'].sum():,.2f} CUP")
            st.dataframe(df_hist, use_container_width=True, hide_index=True)
            st.download_button("Descargar Excel", df_a_excel(df_hist),
                f"compras_{hfi}_{hff}.xlsx",
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                use_container_width=True)
        else:
            st.info(f"No hay compras entre {hfi} y {hff}.")

        st.divider()
        st.subheader("Historial de Precios por Producto")
        df_inv3 = obtener_inventario()
        if not df_inv3.empty:
            opts = {f"{r['nombre']} ({r['codigo_barras']})": r["id"]
                    for _, r in df_inv3.iterrows()}
            sel = st.selectbox("Producto", list(opts.keys()))
            df_p = obtener_historial_precios(opts[sel])
            if not df_p.empty:
                st.dataframe(df_p, use_container_width=True, hide_index=True)
                st.line_chart(df_p.set_index("Fecha")["Precio Costo"])
            else:
                st.info("Sin compras registradas para este producto.")

    with sub3:
        st.subheader("Gestión de Proveedores")
        with st.form("f_prov", clear_on_submit=True):
            p1, p2, p3 = st.columns(3)
            with p1: pnom = st.text_input("Nombre *")
            with p2: ptel = st.text_input("Teléfono")
            with p3: pnot = st.text_input("Notas")
            if st.form_submit_button("Agregar"):
                if pnom:
                    ok, err = registrar_proveedor(pnom, ptel, pnot)
                    st.success("Proveedor agregado.") if ok else st.error(f"Error: {err}")
                    if ok: st.rerun()
                else:
                    st.warning("El nombre es obligatorio.")

        df_prov2 = obtener_proveedores()
        if not df_prov2.empty:
            st.dataframe(df_prov2, use_container_width=True, hide_index=True)
            with st.expander("Eliminar Proveedor"):
                pid_del = st.selectbox("Proveedor", df_prov2["id"],
                    format_func=lambda x: df_prov2[df_prov2["id"]==x]["nombre"].values[0])
                if st.checkbox("Confirmo eliminar") and st.button("Eliminar"):
                    eliminar_proveedor(pid_del); st.warning("Eliminado."); st.rerun()
        else:
            st.info("No hay proveedores aún.")


# ════════════════════════════════════════════════════════════
# PESTAÑA 4: REPORTES
# ════════════════════════════════════════════════════════════
with t4:
    st.header("Reportes de Ventas")
    f1, f2 = st.columns(2)
    with f1: fi = st.date_input("Desde", value=date.today())
    with f2: ff = st.date_input("Hasta", value=date.today())

    if fi > ff:
        st.error("La fecha de inicio no puede ser mayor que la de fin.")
    else:
        dv = obtener_ventas_por_fecha(fi, ff)
        if not dv.empty:
            tv = dv["Venta"].sum(); tc = dv["Costo"].sum(); ti = dv["Cantidad"].sum()
            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Ingreso Total",      f"{tv:,.2f} CUP")
            k2.metric("Inversión Real",     f"{tc:,.2f} CUP")
            k3.metric("Utilidad Neta",      f"{tv-tc:,.2f} CUP")
            k4.metric("Artículos Vendidos", int(ti))
            st.divider()
            st.subheader("Utilidad por Categoría")
            df_cat = dv.groupby("Categoria").apply(
                lambda x: x["Venta"].sum()-x["Costo"].sum()
            ).reset_index(name="Utilidad")
            st.bar_chart(df_cat.set_index("Categoria")["Utilidad"])
            st.subheader("Ventas por Día")
            st.line_chart(dv.groupby("Fecha")["Venta"].sum())
            st.divider()
            st.dataframe(dv.drop(columns=["Categoria"]),
                         use_container_width=True, hide_index=True)
            r1, r2 = st.columns(2)
            with r1:
                st.download_button("Descargar CSV",
                    dv.to_csv(index=False).encode("utf-8"),
                    f"ventas_{fi}_{ff}.csv", "text/csv", use_container_width=True)
            with r2:
                st.download_button("Descargar Excel", df_a_excel(dv),
                    f"ventas_{fi}_{ff}.xlsx",
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True)
        else:
            st.info(f"No hay ventas entre {fi} y {ff}.")


# ════════════════════════════════════════════════════════════
# PESTAÑA 5: USUARIOS
# ════════════════════════════════════════════════════════════
with t5:
    st.header("Gestión de Usuarios")

    with st.expander("Crear Nuevo Usuario"):
        with st.form("f_user", clear_on_submit=True):
            u1, u2, u3 = st.columns(3)
            with u1: new_u = st.text_input("Usuario *")
            with u2: new_p = st.text_input("Contraseña *", type="password")
            with u3: new_r = st.selectbox("Rol", ["cajero","admin"])
            if st.form_submit_button("Crear"):
                if new_u and new_p:
                    ok, err = crear_usuario(new_u, new_p, new_r)
                    st.success(f"Usuario '{new_u}' creado.") if ok else st.error(f"Error: {err}")
                    if ok: st.rerun()
                else:
                    st.warning("Obligatorios: usuario y contraseña.")

    st.divider()
    df_u = obtener_usuarios()
    if not df_u.empty:
        df_u["estado"] = df_u["activo"].map({1:"Activo", 0:"Inactivo"})
        st.dataframe(df_u[["id","username","rol","estado"]],
                     use_container_width=True, hide_index=True)
        st.divider()
        ua, up = st.columns(2)

        with ua:
            with st.expander("Activar / Desactivar"):
                otros = df_u[df_u["username"] != usuario["username"]]
                if not otros.empty:
                    uid_t = st.selectbox("Usuario", otros["id"],
                        format_func=lambda x: df_u[df_u["id"]==x]["username"].values[0])
                    det_t  = df_u[df_u["id"]==uid_t].iloc[0]
                    accion = "Desactivar" if det_t["activo"]==1 else "Activar"
                    if st.button(f"{accion} a {det_t['username']}", use_container_width=True):
                        toggle_usuario(uid_t); st.success(f"{accion}do."); st.rerun()
                else:
                    st.info("No hay otros usuarios.")

        with up:
            with st.expander("Cambiar Contraseña"):
                uid_cp = st.selectbox("Usuario", df_u["id"], key="cp_sel",
                    format_func=lambda x: df_u[df_u["id"]==x]["username"].values[0])
                with st.form("f_pass"):
                    np1 = st.text_input("Nueva contraseña", type="password")
                    np2 = st.text_input("Confirmar", type="password")
                    if st.form_submit_button("Cambiar"):
                        if not np1:        st.warning("Escribe una contraseña.")
                        elif np1 != np2:   st.error("No coinciden.")
                        elif len(np1) < 6: st.error("Mínimo 6 caracteres.")
                        else:
                            cambiar_password(uid_cp, np1); st.success("Contraseña actualizada.")
