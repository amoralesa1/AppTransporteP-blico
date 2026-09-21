#!/usr/bin/env python3
"""
Genera el JSON de una red de Renfe (Cercanias, Trambahia...) a partir del GTFS de Cercanias de Renfe.

Descarga oficial (un solo zip para toda Espana):
    https://ssl.renfe.com/ftransit/Fichero_CER_FOMENTO/fomento_transit.zip

Uso:
    python3 scripts/build_renfe.py ZIP_O_CARPETA NUCLEO FILTRO SALIDA

    NUCLEO  prefijo del route_id del nucleo (31T = Cadiz)
    FILTRO  el route_short_name debe empezar por esto (C = Cercanias, T = tranvia)

Ejemplos:
    python3 scripts/build_renfe.py fomento_transit.zip 31T C data/cercanias-cadiz.json
    python3 scripts/build_renfe.py fomento_transit.zip 31T T data/trambahia.json

Notas sobre el formato de Renfe: no trae direction_id (cada sentido es una ruta distinta) y cada
sentido tiene su propio trazado (p. ej. 31_T1 y 31_T1_INV). Por eso el sentido se identifica por el
shape_id. OJO: el trazado no siempre esta dibujado en el mismo sentido que el tren que lo usa (31_T1
va de Pelagatos a Cadiz y lo usa el servicio Cadiz -> Pelagatos), asi que se prueba el trazado en
ambas orientaciones y se elige la que encaja con las paradas. Los ficheros vienen con espacios de
relleno; la libreria los recorta.
"""
import json, os, re, sys
from collections import defaultdict

from gtfs_lib import Fuente, hav, paradas_con_offset

if len(sys.argv) < 5:
    sys.exit(__doc__)
GTFS, NUCLEO, FILTRO, OUT = sys.argv[1:5]
fuente = Fuente(GTFS)

print("Leyendo routes/trips...")
routes = {r["route_id"]: r for r in fuente.filas("routes.txt")
          if r["route_id"].startswith(NUCLEO) and r["route_short_name"].upper().startswith(FILTRO.upper())}
trips = {t["trip_id"]: t for t in fuente.filas("trips.txt") if t["route_id"] in routes}
print(f"  {len(routes)} rutas, {len(trips)} viajes")
if not trips:
    sys.exit("No hay viajes para ese nucleo/filtro. Revisa los argumentos.")

print("Leyendo stop_times (puede tardar un minuto)...")
seqs = defaultdict(list)
for tid, n, sid in fuente.stop_times_de(set(trips)):
    seqs[tid].append((n, sid))
seqs = {tid: [s for _, s in sorted(l)] for tid, l in seqs.items()}

# Patron representativo de cada (linea, trazado): el viaje con mas paradas.
grupos = defaultdict(list)
for tid, t in trips.items():
    if tid in seqs and t["shape_id"]:
        grupos[(routes[t["route_id"]]["route_short_name"], t["shape_id"])].append(tid)
mejor = {}
for k, lista in grupos.items():
    mejor[k] = max(lista, key=lambda tid: len(seqs[tid]))
    # aviso si algun viaje del grupo para en una parada que el patron elegido no tiene
    extra = {s for tid in lista for s in seqs[tid]} - set(seqs[mejor[k]])
    if extra:
        print(f"  Aviso: {k} tiene paradas fuera del patron principal: {sorted(extra)}")

stops_all = {s["stop_id"]: s for s in fuente.filas("stops.txt")}
shapes_necesarios = {k[1] for k in mejor}
pts_shape = defaultdict(list)
for sp in fuente.filas("shapes.txt"):
    if sp["shape_id"] in shapes_necesarios:
        pts_shape[sp["shape_id"]].append((int(sp["shape_pt_sequence"]), float(sp["shape_pt_lat"]), float(sp["shape_pt_lon"])))

print("Calculando distancias...")
salida_rutas, usadas = {}, set()
for linea in sorted({k[0] for k in mejor}):
    shapes = sorted(k[1] for k in mejor if k[0] == linea)      # 31_T1 < 31_T1_INV  ->  sentido 0, 1
    # nombre: el de la primera ruta de la linea que tenga viajes
    rid = min(t["route_id"] for t in trips.values() if routes[t["route_id"]]["route_short_name"] == linea)
    r = routes[rid]
    nombre = re.sub(r"\s+-\s*", " – ", re.sub(r"\s+", " ", r["route_long_name"]))
    entry = {"code": linea, "name": nombre, "color": r["route_color"], "dirs": {}}
    for i, sid in enumerate(shapes):
        tid = mejor[(linea, sid)]
        seq = [s for s in seqs[tid] if s in stops_all]
        pts = [(la, lo) for _, la, lo in sorted(pts_shape[sid])]
        lista, peor = paradas_con_offset(seq, stops_all, pts)
        inv, peor_inv = paradas_con_offset(seq, stops_all, pts[::-1])
        nota = ""
        if peor_inv < peor:          # el trazado esta dibujado al reves respecto a las paradas
            lista, peor, nota = inv, peor_inv, " [trazado invertido]"
        entry["dirs"][str(i)] = {"headsign": "", "stops": lista}
        usadas.update(seq)
        a, b = stops_all[seq[0]], stops_all[seq[-1]]
        recta = hav(float(a["stop_lat"]), float(a["stop_lon"]), float(b["stop_lat"]), float(b["stop_lon"]))
        km = (lista[-1][1] - lista[0][1]) / 1000
        print(f"  {linea:4} sentido {i}: {len(seq):2} paradas | {a['stop_name']} -> {b['stop_name']} | "
              f"{km:5.1f} km (recta {recta/1000:4.1f}) | parada mas lejos del trazado: {('%.0f m' % peor) if peor is not None else 'sin trazado'}{nota}")
        if peor is not None and peor > 300:
            print(f"    !! Aviso: alguna parada queda a mas de 300 m del trazado; revisa esta linea antes de usarla.")
    salida_rutas[linea] = entry

out = {
    "fuente": f"renfe:{NUCLEO}:{FILTRO}",
    "stops": {s: [stops_all[s]["stop_name"], round(float(stops_all[s]["stop_lat"]), 5), round(float(stops_all[s]["stop_lon"]), 5)]
              for s in sorted(usadas)},
    "routes": salida_rutas,
}
os.makedirs(os.path.dirname(OUT) or ".", exist_ok=True)
with open(OUT, "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
print(f"OK -> {OUT} ({os.path.getsize(OUT)/1024:.0f} KB) | {len(salida_rutas)} lineas, {len(usadas)} paradas")
