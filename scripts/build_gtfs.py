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
import json, os, sys
from collections import defaultdict

from gtfs_lib import Fuente, paradas_con_offset

GTFS = sys.argv[1] if len(sys.argv) > 1 else "."     # carpeta o .zip
PREFIX = sys.argv[2] if len(sys.argv) > 2 else "2_"
OUT = sys.argv[3] if len(sys.argv) > 3 else "data/bahia-cadiz.json"
fuente = Fuente(GTFS)
read = fuente.filas


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
for tid, seq_n, sid in fuente.stop_times_de(set(trips)):
    seqs[tid].append((seq_n, sid))

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
    stop_list, _peor = paradas_con_offset(seq, stops, pts)
    if len(pts) < 2:
        warn += 1

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
