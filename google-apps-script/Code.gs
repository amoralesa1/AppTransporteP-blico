/**
 * Recibe los trayectos de la PWA y los añade a la hoja "Trayectos".
 * Se publica como Aplicación web (ver README, sección Google Sheets).
 *
 * Seguridad: la URL de la aplicación web es la "llave". Cualquiera que la tenga
 * podría añadir filas a tu hoja, así que no la compartas ni la subas a GitHub
 * (la app la guarda solo en tu iPhone). Además, se exige un TOKEN compartido.
 */

// Cambia este texto por uno tuyo (largo y aleatorio) y pon EL MISMO en la app.
const TOKEN = "CAMBIA-ESTE-TEXTO";

const HOJA = "Trayectos";
const CABECERA = [
  "id", "fecha", "anio", "mes", "dia_semana",
  "tipo", "ciudad", "linea", "linea_nombre",
  "origen", "destino", "km", "espera_min", "trayecto_min",
  "registrado_en"
];
const DIAS = ["domingo", "lunes", "martes", "miércoles", "jueves", "viernes", "sábado"];

function doPost(e) {
  const lock = LockService.getScriptLock();
  try {
    lock.waitLock(20000);
    const t = JSON.parse(e.postData.contents);

    if (t.token !== TOKEN) return salida({ ok: false, error: "token" });
    if (t.accion === "ping") return salida({ ok: true });
    if (!t.id || !t.fecha) return salida({ ok: false, error: "datos" });

    const hoja = obtenerHoja();

    // Idempotencia: si el id ya existe, no se duplica (reintentos seguros).
    const ids = hoja.getLastRow() > 1
      ? hoja.getRange(2, 1, hoja.getLastRow() - 1, 1).getValues().flat().map(String)
      : [];
    if (ids.indexOf(String(t.id)) !== -1) return salida({ ok: true, duplicado: true });

    const [anio, mes, dia] = String(t.fecha).split("-").map(Number);
    const f = new Date(anio, mes - 1, dia);

    hoja.appendRow([
      String(t.id),
      f,                       // fecha real (Sheets la reconoce como fecha)
      anio,
      mes,
      DIAS[f.getDay()],
      t.tipo || "",
      t.ciudad || "",
      t.lineaCodigo || "",
      t.lineaNombre || "",
      t.origen || "",
      t.destino || "",
      t.km === null || t.km === undefined || t.km === "" ? "" : Number(t.km),
      Number(t.espera) || 0,
      Number(t.trayecto) || 0,
      new Date()
    ]);
    hoja.getRange(hoja.getLastRow(), 2).setNumberFormat("yyyy-mm-dd");
    hoja.getRange(hoja.getLastRow(), 15).setNumberFormat("yyyy-mm-dd hh:mm");

    return salida({ ok: true });
  } catch (err) {
    return salida({ ok: false, error: String(err) });
  } finally {
    try { lock.releaseLock(); } catch (_) {}
  }
}

// Permite comprobar en el navegador que el despliegue está vivo.
function doGet() {
  return salida({ ok: true, servicio: "trayectos" });
}

function obtenerHoja() {
  const libro = SpreadsheetApp.getActiveSpreadsheet();
  let hoja = libro.getSheetByName(HOJA);
  if (!hoja) {
    hoja = libro.insertSheet(HOJA);
    hoja.appendRow(CABECERA);
    hoja.setFrozenRows(1);
    hoja.getRange(1, 1, 1, CABECERA.length).setFontWeight("bold");
  }
  return hoja;
}

function salida(obj) {
  return ContentService.createTextOutput(JSON.stringify(obj))
    .setMimeType(ContentService.MimeType.JSON);
}
