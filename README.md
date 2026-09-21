# Mis trayectos

PWA para registrar trayectos en transporte público (fecha, operador, línea, sentido,
paradas, km reales, tiempo de espera y de trayecto). Funciona offline y guarda los
datos solo en tu iPhone (localStorage).

## Publicar en GitHub Pages

1. Crea un repositorio nuevo en GitHub (por ejemplo `mis-trayectos`), público.
2. Sube todo el contenido de esta carpeta a la raíz del repositorio.
3. En el repositorio: **Settings → Pages → Build and deployment**
   - Source: *Deploy from a branch*
   - Branch: `main`, carpeta `/ (root)` → Save
4. Espera 1-2 minutos. La app quedará en `https://TU_USUARIO.github.io/mis-trayectos/`

## Instalar en el iPhone

1. Abre esa URL **con Safari** (no funciona desde otros navegadores en iOS).
2. Botón Compartir → **Añadir a pantalla de inicio**.

## Guardar los trayectos en Google Sheets

Cada trayecto se guarda primero en el iPhone y después se envía a tu hoja. Si no hay
conexión queda como «pendiente» y se reenvía solo al abrir la app o al volver la red.
Cada trayecto lleva un ID único, así que un reintento nunca duplica filas.
Los trayectos guardados antes de activar esto no se suben.

**1. Crear la hoja y el script**
1. Crea una hoja de cálculo nueva en Google Sheets (el nombre da igual).
2. Menú **Extensiones → Apps Script**. Borra lo que haya y pega el contenido de
   `google-apps-script/Code.gs`.
3. Cambia `CAMBIA-ESTE-TEXTO` por un token tuyo (largo y aleatorio). Guarda.
4. Engranaje **Configuración del proyecto** → zona horaria `Europe/Madrid`.

**2. Publicarlo**
1. **Implementar → Nueva implementación** → tipo **Aplicación web**.
2. *Ejecutar como*: **Yo**. *Quién tiene acceso*: **Cualquier persona**. → Implementar.
3. Autoriza los permisos. Si sale «Google no ha verificado esta aplicación»:
   *Configuración avanzada → Ir a (nombre del proyecto)*. Es tu propio script.
4. Copia la **URL de la aplicación web** (termina en `/exec`).

**3. Conectar la app**
1. Abre la app **desde el icono de la pantalla de inicio** (no desde Safari: en iOS la app
   instalada tiene su propio almacenamiento, aparte del de Safari).
2. Sección **Google Sheets → Configuración**: pega la URL y el token → **Probar conexión**.

La URL y el token se guardan solo en tu iPhone. No los subas a GitHub.

Si cambias `Code.gs` más adelante: **Implementar → Gestionar implementaciones → editar →
Versión nueva**. Si no, Google sigue sirviendo la versión anterior.

**Columnas de la hoja:** `id, fecha, anio, mes, dia_semana, tipo, ciudad, linea, linea_nombre,
origen, destino, km, espera_min, trayecto_min, registrado_en`. Las columnas `anio`, `mes`
y `dia_semana` están para facilitar las tablas dinámicas del análisis anual.

**Borrar en la app no borra en la hoja.** La hoja es el registro histórico; si quieres quitar
una fila, hazlo en la propia hoja.

## Actualizar los datos de una ciudad

```bash
# 1. Descarga el GTFS unificado y descomprímelo en una carpeta
#    https://api.ctan.es/v1/datos/UNIFICADO/gtfs.zip
# 2. Genera el JSON (prefijo del consorcio: 1_ Sevilla, 2_ Bahía de Cádiz,
#    3_ Granada, 4_ Málaga, 5_ Campo de Gibraltar, 6_ Almería,
#    7_ Jaén, 8_ Córdoba, 9_ Huelva)
python3 scripts/build_gtfs.py RUTA_GTFS 2_ data/bahia-cadiz.json
```

## Añadir otro operador

1. Genera su JSON con el script y guárdalo en `data/`.
2. En `app.js`, dentro de `CIUDADES`, añade `data: "data/su-archivo.json"` a la entrada.
3. Añade el archivo a `ARCHIVOS` en `sw.js` y sube `VERSION` (por ejemplo a `"v2"`).

## Actualizar la app tras cambios

Cada vez que cambies cualquier archivo, sube `VERSION` en `sw.js`; si no, el iPhone
seguirá mostrando la versión cacheada.
