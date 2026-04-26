# Guía de Despliegue SAHYM
## Supabase (base de datos) + Streamlit Community Cloud (app)
## 100% gratis · Sin tarjeta de crédito

---

## Resumen del plan

```
GitHub (tu código)
    ↓
Streamlit Community Cloud (corre la app)
    ↓
Supabase (base de datos PostgreSQL)
```

---

## PARTE 1 — Supabase (base de datos)

### Paso 1 — Crear cuenta
1. Ve a https://supabase.com
2. Haz clic en **Start your project**
3. Regístrate con GitHub o con tu correo (no pide tarjeta)

### Paso 2 — Crear proyecto
1. Haz clic en **New Project**
2. Ponle nombre: `sahym`
3. Crea una contraseña para la base de datos — **guárdala**, la necesitarás
4. Elige la región más cercana (por ejemplo `us-east-1`)
5. Haz clic en **Create new project** y espera ~2 minutos

### Paso 3 — Obtener la cadena de conexión
1. En el menú izquierdo ve a **Project Settings → Database**
2. Baja hasta la sección **Connection string**
3. Selecciona el modo **Transaction** en el selector
4. Copia la URL — se ve así:
   ```
   postgresql://postgres.xxxx:TU_PASSWORD@aws-0-us-east-1.pooler.supabase.com:5432/postgres
   ```
5. Reemplaza `[YOUR-PASSWORD]` con la contraseña que creaste en el Paso 2
6. **Guarda esta URL**, la usarás en los siguientes pasos

---

## PARTE 2 — GitHub (actualizar tu repositorio)

### Paso 4 — Agregar nuevos archivos al repo

Tienes que agregar estos archivos nuevos a tu repositorio:
- `database.py` (versión actualizada)
- `logic.py` (versión actualizada)
- `requirements.txt`

Y crear esta carpeta y archivo (NO se sube a GitHub):
```
.streamlit/
└── secrets.toml     ← este NO va al repo
```

### Paso 5 — Crear el .gitignore
Crea un archivo llamado `.gitignore` en tu carpeta con este contenido:
```
.streamlit/secrets.toml
__pycache__/
*.pyc
tienda.db
backups/
fotos_productos/
```

### Paso 6 — Subir cambios a GitHub
```bash
git add .
git commit -m "preparar para despliegue en streamlit cloud"
git push
```

---

## PARTE 3 — Streamlit Community Cloud (la app)

### Paso 7 — Crear cuenta
1. Ve a https://share.streamlit.io
2. Haz clic en **Sign up**
3. Regístrate con tu cuenta de GitHub (no pide tarjeta)

### Paso 8 — Desplegar la app
1. Haz clic en **New app**
2. Selecciona tu repositorio `sahym`
3. En **Branch** pon: `main`
4. En **Main file path** pon: `app.py`
5. Haz clic en **Advanced settings...**

### Paso 9 — Configurar el secreto de la base de datos
En la ventana de **Advanced settings** verás un campo llamado **Secrets**.
Pega esto (con tu URL real de Supabase):

```toml
DATABASE_URL = "postgresql://postgres.TUPROYECTO:TUPASSWORD@aws-0-us-east-1.pooler.supabase.com:5432/postgres"
```

6. Haz clic en **Save**
7. Haz clic en **Deploy!**

### Paso 10 — Esperar el despliegue
- Tarda 2-4 minutos la primera vez
- Streamlit Cloud te dará una URL tipo:
  `https://sahym-xxxxxx.streamlit.app`
- ¡Esa es la URL que compartes con tus empleados!

---

## PARTE 4 — Primera vez que abres la app

1. Abre tu URL de Streamlit Cloud
2. Inicia sesión con:
   - Usuario: **admin**
   - Contraseña: **admin123**
3. Ve a la pestaña **Usuarios** y cambia la contraseña inmediatamente

---

## Límites del plan gratuito

| Servicio | Límite gratuito |
|---|---|
| Streamlit Cloud | 1 app, sin límite de tiempo |
| Supabase | 500 MB de base de datos, sin límite de tiempo |
| Supabase | 2 GB de transferencia al mes |

Para una tienda pequeña estos límites son más que suficientes.

---

## Actualizar la app después de hacer cambios

Cada vez que modifiques el código en tu computadora:
```bash
git add .
git commit -m "descripcion del cambio"
git push
```
Streamlit Cloud detecta el cambio y actualiza la app automáticamente
en 1-2 minutos.

---

## Si algo falla

### Ver los logs de error
1. Ve a https://share.streamlit.io
2. Haz clic en los tres puntos (...) de tu app
3. Selecciona **Logs**
4. Copia el error y compártelo para resolverlo

### Errores comunes
| Error | Causa | Solución |
|---|---|---|
| `connection refused` | URL de Supabase incorrecta | Revisa el secreto DATABASE_URL |
| `ModuleNotFoundError` | Falta librería | Verifica requirements.txt |
| `relation does not exist` | Tablas no creadas | La app las crea sola al arrancar |
