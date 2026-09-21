"""Utilidades comunes para convertir feeds GTFS en los JSON que usa la PWA."""
import csv, io, math, os, zipfile

R_TIERRA = 6371008.8


class Fuente:
    """Carpeta con los .txt del GTFS, o el .zip directamente (se lee sin descomprimir)."""

    def __init__(self, ruta):
        self.ruta = ruta
        self.zip = zipfile.ZipFile(ruta) if ruta.lower().endswith(".zip") else None

    def abrir(self, nombre):
        if self.zip:
            return io.TextIOWrapper(self.zip.open(nombre), encoding="utf-8-sig", newline="")
        return open(os.path.join(self.ruta, nombre), encoding="utf-8-sig", newline="")

    def filas(self, nombre):
        """Filas como dict, con cabeceras y valores sin espacios (Renfe rellena con espacios)."""
        with self.abrir(nombre) as f:
            for row in csv.DictReader(f):
                yield {k.strip(): (v or "").strip() for k, v in row.items() if k}

    def stop_times_de(self, trip_ids):
        """(trip_id, stop_sequence, stop_id) solo de los viajes pedidos. Rápido con ficheros enormes."""
        with self.abrir("stop_times.txt") as f:
            r = csv.reader(f)
            cab = [c.strip() for c in next(r)]
            it, is_, iq = cab.index("trip_id"), cab.index("stop_id"), cab.index("stop_sequence")
            for row in r:
                t = row[it].strip()
                if t in trip_ids:
                    yield t, int(row[iq]), row[is_].strip()


def hav(lat1, lon1, lat2, lon2):
    """Distancia haversine en metros."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R_TIERRA * math.asin(math.sqrt(a))


def project(px, py, ax, ay, bx, by):
    """Proyecta P sobre el segmento AB (plano local). Devuelve (t, dist2)."""
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L2))
    qx, qy = ax + t * dx, ay + t * dy
    return t, (px - qx) ** 2 + (py - qy) ** 2


def cumulative(pts):
    cum = [0.0]
    for i in range(1, len(pts)):
        cum.append(cum[-1] + hav(pts[i - 1][0], pts[i - 1][1], pts[i][0], pts[i][1]))
    return cum


def stop_offset(lat, lon, pts, cum, start_idx):
    """Metros a lo largo del trazado donde queda la parada, y a que distancia (m) del trazado esta.
    Solo busca desde start_idx en adelante para respetar el orden y evitar
    saltos en lineas circulares o con tramos que se solapan."""
    k = math.cos(math.radians(lat))
    best_d2, best_off, best_i = None, 0.0, start_idx
    for i in range(start_idx, len(pts) - 1):
        ax, ay = pts[i][1] * k, pts[i][0]
        bx, by = pts[i + 1][1] * k, pts[i + 1][0]
        t, d2 = project(lon * k, lat, ax, ay, bx, by)
        if best_d2 is None or d2 < best_d2:
            seg = cum[i + 1] - cum[i]
            best_d2, best_off, best_i = d2, cum[i] + t * seg, i
    dist_m = math.sqrt(best_d2) * (math.pi / 180 * R_TIERRA) if best_d2 is not None else 0.0
    return best_off, best_i, dist_m


def paradas_con_offset(seq, stops, pts):
    """seq: ids de parada en orden. pts: [(lat, lon)] del trazado.
    Devuelve ([[id, metros_desde_el_inicio_del_trazado], ...], distancia_maxima_parada_trazado_m).
    Sin trazado, acumula linea recta entre paradas consecutivas (y devuelve None como distancia)."""
    out = []
    if len(pts) >= 2:
        cum = cumulative(pts)
        start, last_off, peor = 0, 0.0, 0.0
        for s in seq:
            off, start, d = stop_offset(float(stops[s]["stop_lat"]), float(stops[s]["stop_lon"]), pts, cum, start)
            off = max(off, last_off)  # nunca retrocede
            last_off = off
            peor = max(peor, d)
            out.append([s, round(off)])
        return out, peor
    acc, prev = 0.0, None
    for s in seq:
        la, lo = float(stops[s]["stop_lat"]), float(stops[s]["stop_lon"])
        if prev:
            acc += hav(prev[0], prev[1], la, lo)
        prev = (la, lo)
        out.append([s, round(acc)])
    return out, None
