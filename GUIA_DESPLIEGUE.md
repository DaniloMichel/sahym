# Guía de Despliegue — SAHYM en Render.com

## Archivos que necesitas en tu carpeta del proyecto

```
sahym/
├── app.py
├── database.py
├── logic.py
├── requirements.txt
└── render.yaml
```

---

## Paso 1 — Crear cuenta en GitHub (si no tienes)

1. Ve a https://github.com y crea una cuenta gratuita.
2. Crea un repositorio nuevo llamado `sahym` (privado recomendado).
3. Sube todos tus archivos a ese repositorio.

Desde tu computadora con Git instalado:
```bash
cd tu-carpeta-sahym
git init
git add .
git commit -m "primera version"
git remote add origin https://github.com/TU_USUARIO/sahym.git
git push -u origin main
```

---

## Paso 2 — Crear cuenta en Render

1. Ve a https://render.com
2. Haz clic en **Get Started for Free**
3. Regístrate con tu cuenta de GitHub (es la opción más fácil)

---

## Paso 3 — Desplegar con render.yaml (automático)

1. En Render, haz clic en **New → Blueprint**
2. Conecta tu repositorio `sahym` de GitHub
3. Render detectará el archivo `render.yaml` automáticamente
4. Haz clic en **Apply** — Render creará:
   - Un servicio web para SAHYM
   - Una base de datos PostgreSQL gratuita
   - La variable DATABASE_URL conectada automáticamente

---

## Paso 4 — Esperar el despliegue

- El primer despliegue tarda 3-5 minutos
- Render te dará una URL tipo: `https://sahym.onrender.com`
- Esa URL es la que compartes con tus empleados

---

## Paso 5 — Primera vez que abres la app

- Usuario: **admin**
- Contraseña: **admin123**
- ¡Cámbiala inmediatamente en la pestaña Usuarios!

---

## Notas importantes

### Plan gratuito de Render
- La app se "duerme" después de 15 minutos sin uso
- Al primer acceso tarda ~30 segundos en despertar
- Para evitar esto: plan Starter ($7/mes)

### Base de datos gratuita
- PostgreSQL gratis por 90 días en Render
- Después hay que pagar $7/mes o migrar a otro proveedor
- Alternativa gratuita permanente: Supabase.com (PostgreSQL gratis)

### Actualizar la app
Cada vez que hagas cambios en tu código:
```bash
git add .
git commit -m "descripcion del cambio"
git push
```
Render detecta el push y actualiza la app automáticamente.

---

## Si algo falla

Render tiene un log de errores en tiempo real:
1. Ve a tu servicio en Render
2. Haz clic en **Logs**
3. Copia el error y compártelo para resolverlo
