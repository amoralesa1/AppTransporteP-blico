#!/usr/bin/env python3
"""
Genera data/bahia-cadiz.json a partir del GTFS unificado del Consorcio de Andalucia.

Uso:
    python3 scripts/build_gtfs.py RUTA_GTFS [PREFIJO] [SALIDA]

Ejemplo:
    python3 scripts/build_gtfs.py /mnt/user-data/uploads 2_ data/bahia-cadiz.json

Para anadir otra ciudad del Consorcio basta con cambiar el prefijo (1_ Sevilla,
3_ Granada, 4_ Malaga...) y el nombre del fichero de salida.
"""
import csv, json, math, os, sys
from collections import defaultdict

GTFS = sys.argv[1] if len(sys.argv) > 1 else "."
PREFIX = sys.argv[2] if len(sys.argv) > 2 else "2_"
OUT = sys.argv[3] if len(sys.argv) > 3 else "data/bahia-cadiz.json"


def read(name):
    with open(os.path.join(GTFS, name), encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            yield {k.strip(): (v or "").strip() for k, v in row.items() if k}


def hav(lat1, lon1, lat2, lon2):
    """Distancia haversine en metros."""
    R = 6371008.8
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(a))


def project(px, py, ax, ay, bx, by):
    """Proyecta P sobre el segmento AB (plano local). Devuelve (t, dist2)."""
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    t = 0.0 if L2 == 0 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L2))
    qx, qy = ax + t * dx, ay + t * dy
    return t, (px - qx) ** 2 + (py - qy) ** 2


print("Leyendo routes/stops/trips...")
routes = {r["route_id"]: r for r in read("routes.txt") if r["route_id"].startswith(PREFIX)}
stops = {s["stop_id"]: s for s in read("stops.txt") if s["stop_id"].startswith(PREFIX)}

# route_id, direction_id -> {shape_id, trip_ids}
trips = {}
trip_meta = {}
for t in read("trips.txt"):
    if t["route_id"] in routes:
        trips[t["trip_id"]] = t
print(f"  {len(routes)} lineas, {len(stops)} paradas, {len(trips)} viajes")

print("Leyendo stop_times...")
seqs = defaultdict(list)
for st in read("stop_times.txt"):
    if st["trip_id"] in trips:
        seqs[st["trip_id"]].append((int(st["stop_sequence"]), st["stop_id"]))

# Patron representativo: por (linea, sentido) el viaje con MAS paradas.
best = {}
for tid, lst in seqs.items():
    t = trips[tid]
    key = (t["route_id"], t["direction_id"])
    if key not in best or len(lst) > len(seqs[best[key]]):
        best[key] = tid

print("Leyendo shapes...")
needed = {trips[tid]["shape_id"] for tid in best.values() if trips[tid]["shape_id"]}
shape_pts = defaultdict(list)
for sp in read("shapes.txt"):
    if sp["shape_id"] in needed:
        shape_pts[sp["shape_id"]].append(
            (int(sp["shape_pt_sequence"]), float(sp["shape_pt_lat"]), float(sp["shape_pt_lon"]))
        )
for k in shape_pts:
    shape_pts[k].sort()


def cumulative(pts):
    cum = [0.0]
    for i in range(1, len(pts)):
        cum.append(cum[-1] + hav(pts[i - 1][0], pts[i - 1][1], pts[i][0], pts[i][1]))
    return cum


def stop_offset(lat, lon, pts, cum, start_idx):
    """Metros a lo largo del trazado donde queda la parada.
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
    return best_off, best_i


print("Calculando patrones y distancias...")
out_routes = {}
used_stops = set()
warn = 0

for (rid, direction), tid in sorted(best.items()):
    trip = trips[tid]
    sid = trip["shape_id"]
    seq = [s for _, s in sorted(seqs[tid])]
    seq = [s for s in seq if s in stops]
    if len(seq) < 2:
        continue

    pts = [(lat, lon) for _, lat, lon in shape_pts.get(sid, [])]
    stop_list = []
    if len(pts) >= 2:
        cum = cumulative(pts)
        start = 0
        last_off = 0.0
        for s in seq:
            off, start = stop_offset(float(stops[s]["stop_lat"]), float(stops[s]["stop_lon"]), pts, cum, start)
            off = max(off, last_off)  # nunca retrocede
            last_off = off
            stop_list.append([s, round(off)])
    else:
        # Sin trazado: acumulamos linea recta entre paradas consecutivas.
        warn += 1
        acc = 0.0
        prev = None
        for s in seq:
            la, lo = float(stops[s]["stop_lat"]), float(stops[s]["stop_lon"])
            if prev:
                acc += hav(prev[0], prev[1], la, lo)
            prev = (la, lo)
            stop_list.append([s, round(acc)])

    used_stops.update(seq)
    r = routes[rid]
    entry = out_routes.setdefault(rid, {
        "code": r["route_short_name"],
        "name": r["route_long_name"],
        "color": r["route_color"],
        "dirs": {},
    })
    entry["dirs"][direction or "0"] = {
        "headsign": trip["trip_headsign"],
        "stops": stop_list,          # [stop_id, metros desde el inicio del trazado]
    }

out = {
    "consorcio": PREFIX,
    "stops": {
        s: [stops[s]["stop_name"], round(float(stops[s]["stop_lat"]), 5), round(float(stops[s]["stop_lon"]), 5)]
        for s in sorted(used_stops)
    },
    "routes": dict(sorted(out_routes.items(), key=lambda kv: kv[1]["code"])),
}

os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, separators=(",", ":"))

kb = os.path.getsize(OUT) / 1024
print(f"OK -> {OUT}  ({kb:.0f} KB) | {len(out_routes)} lineas, {len(used_stops)} paradas")
if warn:
    print(f"Aviso: {warn} patrones sin trazado (distancia en linea recta entre paradas).")
