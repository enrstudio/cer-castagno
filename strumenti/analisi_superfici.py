"""Misura le falde dei tetti dal DSM LiDAR e calcola il loro orizzonte.

Per ogni poligono disegnato in QGIS (una falda, in pianta) ricava:

- azimut, dal campo `azimut` del layer se compilato (convenzione PVGIS),
  altrimenti dal colmo: il lato del poligono più a nord. La falda guarda
  perpendicolare al colmo, dalla parte di sud;
- inclinazione, dal campo `inclinaz` del layer se compilato (misura del
  sopralluogo), altrimenti un valore provvisorio da riga di comando;
- come controllo, inclinazione e azimut stimati adattando un piano alle
  quote del DSM. Con un DSM a celle di circa 1 m e falde di 20 m², o con
  l'ortofoto un po' spostata rispetto al LiDAR, questa stima non è
  affidabile: si riporta con il suo scarto, ma non si usa;
- area reale inclinata, dall'area in pianta divisa per il coseno
  dell'inclinazione;
- profilo d'orizzonte: guardando dal centro della falda, per ogni
  direzione l'angolo più alto sotto cui si vede un ostacolo. Vicino si usa
  il DSM (vede case e alberi), lontano un DTM più grezzo (vede le montagne).
  È il formato che PVGIS accetta come `userhorizon`.

Poi interroga PVGIS per ogni falda in tre modi (orizzonte dal LiDAR,
orizzonte di PVGIS, nessun orizzonte) per far vedere quanto pesano le ombre.

Richiede GDAL con i binding Python (pacchetto python3-gdal) e numpy.

Uso:
    python strumenti/analisi_superfici.py falde.shp DSM.tif DTM.tif dati/superfici
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
from osgeo import gdal, ogr, osr

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from motore.ipotesi import carica_ipotesi  # noqa: E402
from motore.produzione import azimut_da_bussola, stima_annua  # noqa: E402

gdal.UseExceptions()

PASSO_ORIZZONTE_DEG = 7.5  # 48 direzioni: il passo usato anche da PVGIS
RAGGIO_TERRA_M = 6_371_000
RIFRAZIONE = 0.13  # la rifrazione dell'aria "solleva" un po' gli oggetti lontani
DENSITA_KWP_M2 = 0.21  # pannelli da 450 W su circa 2,1 m²
QUOTA_UTILE = 0.75  # parte della falda davvero coperta: bordi, comignoli, sicurezza


class Raster:
    """Un raster in memoria con la sua georeferenziazione, per leggere quote in un punto."""

    def __init__(self, percorso: str):
        ds = gdal.Open(percorso)
        banda = ds.GetRasterBand(1)
        # Leggo i byte grezzi come float32 invece di usare ReadAsArray: così si
        # evita gdal_array, che si rompe se GDAL e numpy installati sono di
        # versioni incompatibili (succede spesso con numpy 2).
        grezzi = banda.ReadRaster(buf_type=gdal.GDT_Float32)
        self.quote = np.frombuffer(grezzi, dtype="float32").reshape(ds.RasterYSize, ds.RasterXSize).astype("float64")
        nodata = banda.GetNoDataValue()
        if nodata is not None:
            self.quote[self.quote == nodata] = np.nan
        self.gt = ds.GetGeoTransform()  # x0, dx, 0, y0, 0, dy (dy negativo)
        self.srs = ds.GetSpatialRef()

    def quota(self, x: np.ndarray, y: np.ndarray) -> np.ndarray:
        """Quota nei punti (x, y); NaN fuori dal raster. Cella più vicina, senza interpolare."""
        col = np.floor((x - self.gt[0]) / self.gt[1]).astype(int)
        riga = np.floor((y - self.gt[3]) / self.gt[5]).astype(int)
        dentro = (col >= 0) & (riga >= 0) & (col < self.quote.shape[1]) & (riga < self.quote.shape[0])
        risultato = np.full(np.shape(x), np.nan)
        risultato[dentro] = self.quote[riga[dentro], col[dentro]]
        return risultato

    def passo_m(self) -> float:
        return min(abs(self.gt[1]), abs(self.gt[5]))


@dataclass
class Falda:
    id: str
    area_pianta_m2: float
    area_reale_m2: float
    inclinazione_deg: float
    fonte_inclinazione: str  # "sopralluogo" (campo inclinaz) o "provvisoria"
    azimut_pvgis_deg: float  # 0 = sud, -90 = est, +90 = ovest
    quota_colmo_m: float  # da dove si guarda l'orizzonte
    lat: float
    lon: float
    kwp_possibili: float
    # Controllo dal DSM: utile solo se lo scarto è piccolo (sotto 0,3 m circa).
    inclinazione_dsm_deg: float
    azimut_dsm_deg: float
    scarto_piano_dsm_m: float
    celle_dsm: int


def piano_falda(geom: ogr.Geometry, dsm: Raster) -> tuple[float, float, float, float, int]:
    """Adatta un piano z = a·x + b·y + c alle celle del DSM dentro la falda.

    La falda viene ristretta di mezzo metro, così si scartano le celle di
    bordo che cadono metà sul tetto e metà sul vuoto. Restituisce
    inclinazione, azimut PVGIS, quota al centro, scarto medio e numero di celle.
    """
    interna = geom.Buffer(-0.5)
    if interna.IsEmpty() or interna.GetArea() < 2:
        interna = geom  # falda troppo piccola per restringerla
    xmin, xmax, ymin, ymax = interna.GetEnvelope()
    passo = dsm.passo_m() / 2  # campiono più fitto della cella per non perdere celle
    xs, ys = np.meshgrid(np.arange(xmin, xmax, passo), np.arange(ymin, ymax, passo))
    xs, ys = xs.ravel(), ys.ravel()
    punto = ogr.Geometry(ogr.wkbPoint)
    dentro = []
    for x, y in zip(xs, ys):
        punto.SetPoint_2D(0, x, y)
        dentro.append(interna.Contains(punto))
    xs, ys = xs[dentro], ys[dentro]
    # Una sola quota per cella del DSM: tengo il centro di ogni cella toccata.
    col = np.floor((xs - dsm.gt[0]) / dsm.gt[1]).astype(int)
    riga = np.floor((ys - dsm.gt[3]) / dsm.gt[5]).astype(int)
    celle = sorted(set(zip(riga.tolist(), col.tolist())))
    cx = np.array([dsm.gt[0] + (c + 0.5) * dsm.gt[1] for _, c in celle])
    cy = np.array([dsm.gt[3] + (r + 0.5) * dsm.gt[5] for r, _ in celle])
    cz = np.array([dsm.quote[r, c] for r, c in celle])
    ok = ~np.isnan(cz)
    cx, cy, cz = cx[ok], cy[ok], cz[ok]
    if len(cz) < 4:
        raise ValueError("troppe poche celle del DSM dentro la falda per stimare un piano")

    # Coordinate relative al centro, per un sistema ben condizionato.
    x0, y0 = cx.mean(), cy.mean()
    A = np.column_stack([cx - x0, cy - y0, np.ones_like(cx)])
    (a, b, c), *_ = np.linalg.lstsq(A, cz, rcond=None)
    scarto = float(np.sqrt(np.mean((A @ np.array([a, b, c]) - cz) ** 2)))

    inclinazione = math.degrees(math.atan(math.hypot(a, b)))
    # La falda "guarda" verso dove scende: direzione opposta al gradiente (a, b).
    bussola = math.degrees(math.atan2(-a, -b)) % 360  # 0 = nord, 90 = est
    return inclinazione, azimut_da_bussola(bussola), float(c), scarto, len(cz)


def azimut_da_geometria(geom: ogr.Geometry) -> float:
    """Azimut PVGIS della falda, ricavato dal suo colmo.

    Le falde nel layer sono quelle esposte a sud, disegnate dal colmo alla
    gronda: il colmo è il lato più a nord fra quelli più orizzontali che
    verticali. La falda guarda perpendicolare al colmo, verso sud.
    (Il "lato più lungo" non funziona: molte falde sono quasi quadrate.)
    """
    anello = geom.GetGeometryRef(0)
    punti = [anello.GetPoint_2D(i) for i in range(anello.GetPointCount())]
    lati = [(punti[i], punti[i + 1]) for i in range(len(punti) - 1) if punti[i] != punti[i + 1]]
    orizzontali = [l for l in lati if abs(l[1][0] - l[0][0]) >= abs(l[1][1] - l[0][1])] or lati
    (x1, y1), (x2, y2) = max(orizzontali, key=lambda l: (l[0][1] + l[1][1]) / 2)
    direzione_colmo = math.degrees(math.atan2(x2 - x1, y2 - y1)) % 360  # bussola
    perpendicolare = (direzione_colmo + 90) % 360
    if not 90 <= perpendicolare <= 270:  # guarda a nord: prendo l'altra
        perpendicolare = (perpendicolare + 180) % 360
    return azimut_da_bussola(perpendicolare)


def quota_colmo(geom: ogr.Geometry, dsm: Raster) -> float:
    """Quota alta della falda nel DSM: il 90° percentile delle celle vicine.

    Serve come punto di vista per l'orizzonte. Si allarga il poligono di 1 m
    perché, se il disegno è spostato rispetto al LiDAR, almeno parte del
    tetto vero ci cada dentro; il percentile alto scarta il terreno.
    """
    largo = geom.Buffer(1.0)
    xmin, xmax, ymin, ymax = largo.GetEnvelope()
    xs, ys = np.meshgrid(np.arange(xmin, xmax, 0.5), np.arange(ymin, ymax, 0.5))
    punto = ogr.Geometry(ogr.wkbPoint)
    quote = []
    for x, y in zip(xs.ravel(), ys.ravel()):
        punto.SetPoint_2D(0, x, y)
        if largo.Contains(punto):
            quote.append(dsm.quota(np.array([x]), np.array([y]))[0])
    return float(np.nanpercentile(quote, 90))


def orizzonte(x: float, y: float, z: float, vicino: Raster, lontano: Raster,
              distanza_min_m: float = 3.0, distanza_max_m: float = 20_000.0) -> list[float]:
    """Altezza dell'orizzonte in gradi, da nord in senso orario, ogni 7,5°.

    Lungo ogni direzione si cammina dal punto verso l'esterno e si tiene
    l'angolo più alto sotto cui si vede il terreno o un ostacolo. Si parte da
    3 m per non contare il tetto stesso. Fin dove arriva il DSM si usa
    quello, poi il DTM. Oltre qualche km si tiene conto della curvatura
    terrestre, che abbassa le montagne lontane.
    """
    profilo = []
    for k in range(int(360 / PASSO_ORIZZONTE_DEG)):
        direzione = math.radians(k * PASSO_ORIZZONTE_DEG)  # 0 = nord, orario
        dx, dy = math.sin(direzione), math.cos(direzione)
        # Passi fitti vicino, più larghi lontano: la precisione serve dove gli ostacoli sono alti.
        distanze = np.concatenate([
            np.arange(distanza_min_m, 300, vicino.passo_m()),
            np.arange(300, distanza_max_m, lontano.passo_m()),
        ])
        px, py = x + dx * distanze, y + dy * distanze
        quote = vicino.quota(px, py)
        fuori = np.isnan(quote)
        quote[fuori] = lontano.quota(px[fuori], py[fuori])
        abbassamento = distanze**2 / (2 * RAGGIO_TERRA_M) * (1 - RIFRAZIONE)
        angoli = np.degrees(np.arctan((quote - abbassamento - z) / distanze))
        profilo.append(max(0.0, float(np.nanmax(angoli))))
    return profilo


def main() -> None:
    parser = argparse.ArgumentParser(description="Misura le falde dal DSM e stima la produzione con PVGIS.")
    parser.add_argument("falde", help="layer vettoriale delle falde (poligoni in pianta, con campo id)")
    parser.add_argument("dsm", help="DSM LiDAR (vede case e alberi)")
    parser.add_argument("dtm", help="DTM a copertura ampia, per le montagne lontane")
    parser.add_argument("uscita", type=Path, help="cartella dei risultati, dentro dati/")
    parser.add_argument("--inclinazione", type=float, default=20.0,
                        help="inclinazione provvisoria in gradi, per le falde senza il campo inclinaz (predefinita 20)")
    args = parser.parse_args()
    args.uscita.mkdir(parents=True, exist_ok=True)

    reg = carica_ipotesi()
    perdite = reg.valore("perdite_sistema_fv")
    dsm, dtm = Raster(args.dsm), Raster(args.dtm)

    # La sorgente va tenuta in una variabile: se Python la libera, il layer
    # punta a memoria già chiusa e GDAL va in crash.
    sorgente = ogr.Open(args.falde)
    layer = sorgente.GetLayer()
    a_wgs84 = osr.SpatialReference()
    a_wgs84.ImportFromEPSG(4326)
    a_wgs84.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    srs = layer.GetSpatialRef()
    srs.SetAxisMappingStrategy(osr.OAMS_TRADITIONAL_GIS_ORDER)
    in_gradi = osr.CoordinateTransformation(srs, a_wgs84)

    righe, orizzonti = [], {}
    for elemento in layer:
        geom = elemento.GetGeometryRef().Clone()
        fid = str(elemento.GetField("id"))
        incl_dsm, azim_dsm, _, scarto, n = piano_falda(geom, dsm)
        campo = elemento.GetFieldIndex("inclinaz")
        if campo >= 0 and elemento.IsFieldSetAndNotNull(campo):
            incl, fonte_incl = elemento.GetFieldAsDouble(campo), "sopralluogo"
        else:
            incl, fonte_incl = args.inclinazione, "provvisoria"
        campo = elemento.GetFieldIndex("azimut")
        if campo >= 0 and elemento.IsFieldSetAndNotNull(campo):
            azim = elemento.GetFieldAsDouble(campo)  # già in convenzione PVGIS
        else:
            azim = azimut_da_geometria(geom)
        colmo = quota_colmo(geom, dsm)
        centro = geom.Centroid()
        lon, lat, _ = in_gradi.TransformPoint(centro.GetX(), centro.GetY())
        area_reale = geom.GetArea() / math.cos(math.radians(incl))
        falda = Falda(fid, round(geom.GetArea(), 1), round(area_reale, 1), incl, fonte_incl, round(azim, 1),
                      round(colmo, 1), lat, lon, round(area_reale * QUOTA_UTILE * DENSITA_KWP_M2, 1),
                      round(incl_dsm, 1), round(azim_dsm, 1), round(scarto, 2), n)
        # Si guarda da mezzo metro sotto il colmo: circa il centro della falda.
        profilo = orizzonte(centro.GetX(), centro.GetY(), colmo - 0.5, dsm, dtm)
        orizzonti[fid] = profilo

        # Resa per 1 kWp, in tre modi, per vedere quanto pesano le ombre.
        lidar = stima_annua(lat, lon, 1, incl, azim, perdite, orizzonte=profilo)
        pvgis = stima_annua(lat, lon, 1, incl, azim, perdite)
        libero = stima_annua(lat, lon, 1, incl, azim, perdite, usa_orizzonte_pvgis=False)
        righe.append({**asdict(falda),
                      "resa_lidar_kwh_kwp": lidar.kwh_anno, "resa_pvgis_kwh_kwp": pvgis.kwh_anno,
                      "resa_senza_ombre_kwh_kwp": libero.kwh_anno,
                      "kwh_anno_stimati": round(lidar.kwh_anno * falda.kwp_possibili),
                      "kwh_mese_lidar_1kwp": json.dumps([round(v, 1) for v in lidar.kwh_mese])})

    with open(args.uscita / "falde.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, righe[0].keys())
        w.writeheader()
        w.writerows(righe)
    (args.uscita / "orizzonti.json").write_text(json.dumps(orizzonti, indent=1), encoding="utf-8")
    for r in righe:
        print(f"falda {r['id']}: {r['inclinazione_deg']:.0f}° ({r['fonte_inclinazione']}) verso {r['azimut_pvgis_deg']:+.0f}° (0 = sud), "
              f"{r['area_reale_m2']:.1f} m², ~{r['kwp_possibili']} kWp, "
              f"resa {r['resa_lidar_kwh_kwp']:.0f} kWh/kWp con ombre LiDAR "
              f"({r['resa_senza_ombre_kwh_kwp']:.0f} senza ombre)")


if __name__ == "__main__":
    main()
