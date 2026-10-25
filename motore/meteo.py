"""Temperature orarie misurate, dall'archivio storico di Open-Meteo.

Le temperature servono per due cose:

1. capire quanto GPL consuma una casa per ogni grado di freddo, mettendo a
   confronto le letture del contatore con le temperature dello stesso
   periodo (vedi `motore/calore.py`);
2. calcolare, ora per ora, quanto calore servirà e quanto lavorerà una
   pompa di calore, che col freddo rende meno.

L'archivio di Open-Meteo (https://open-meteo.com/en/docs/historical-weather-api)
è gratuito e non chiede registrazione. Le temperature vengono dalla
rianalisi ERA5 del servizio europeo Copernicus: una griglia di circa 25 km,
che Open-Meteo corregge per la quota del punto (`elevation`). A Seccheto,
a 530 m in una valle, il dato resta un'approssimazione: è il motivo per cui
il modello si calibra sulle letture del contatore e non si usa da solo.

Tutte le ore sono in UTC, come in PVGIS: così più avanti produzione
fotovoltaica e consumi si possono sommare ora per ora senza pasticci con
l'ora legale. Per i conti giornalieri lo scarto di una o due ore rispetto
all'ora italiana è trascurabile.
"""

from __future__ import annotations

import hashlib
import json
import urllib.parse
import urllib.request
from datetime import date, datetime
from pathlib import Path

URL_ARCHIVIO = "https://archive-api.open-meteo.com/v1/archive"
CARTELLA_CACHE = Path(__file__).resolve().parent.parent / "cache" / "meteo"


def _scarica_anno(lat: float, lon: float, quota_m: float, anno: int, cache: Path | None) -> dict:
    """Un anno di temperature orarie. Gli anni già finiti si salvano in cache.

    L'anno in corso non si salva: l'archivio si aggiorna con qualche giorno
    di ritardo, e una copia salvata oggi resterebbe incompleta per sempre.
    """
    oggi = date.today()
    fine = date(anno, 12, 31) if anno < oggi.year else oggi
    parametri = {
        "latitude": round(lat, 4),
        "longitude": round(lon, 4),
        "elevation": round(quota_m),
        "start_date": f"{anno}-01-01",
        "end_date": fine.isoformat(),
        "hourly": "temperature_2m",
        "timezone": "GMT",
    }
    anno_finito = anno < oggi.year
    chiave = hashlib.sha256(json.dumps(parametri, sort_keys=True).encode()).hexdigest()[:20]
    file = cache / f"temperature_{anno}_{chiave}.json" if cache is not None else None
    if file is not None and anno_finito and file.exists():
        return json.loads(file.read_text(encoding="utf-8"))

    url = URL_ARCHIVIO + "?" + urllib.parse.urlencode(parametri)
    with urllib.request.urlopen(url, timeout=60) as risposta:
        dati = json.load(risposta)

    if file is not None and anno_finito:
        cache.mkdir(parents=True, exist_ok=True)
        file.write_text(json.dumps(dati), encoding="utf-8")
    return dati


def temperature_orarie(
    lat: float,
    lon: float,
    quota_m: float,
    dal: date,
    al: date,
    cache: Path | None = CARTELLA_CACHE,
) -> dict[datetime, float]:
    """Temperatura dell'aria a 2 m, ora per ora (UTC), dal giorno `dal` al giorno `al` compresi.

    Le ore che l'archivio non ha ancora (gli ultimi giorni) mancano dal
    risultato: chi lo usa deve controllare di avere i giorni che gli servono.
    """
    risultato: dict[datetime, float] = {}
    for anno in range(dal.year, al.year + 1):
        orario = _scarica_anno(lat, lon, quota_m, anno, cache)["hourly"]
        for testo, t in zip(orario["time"], orario["temperature_2m"]):
            ora = datetime.fromisoformat(testo)
            if t is not None and dal <= ora.date() <= al:
                risultato[ora] = float(t)
    return risultato
