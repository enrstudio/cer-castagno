"""Produzione fotovoltaica stimata con PVGIS, il servizio del Centro comune di ricerca UE.

PVGIS (https://re.jrc.ec.europa.eu/pvg_tools/) calcola quanta energia
produce un impianto in un punto preciso, partendo da anni di dati di
irraggiamento da satellite. Qui lo interroghiamo dal motore, non dal
browser: la sua API non accetta chiamate dirette dalle pagine web, e così
possiamo salvare le risposte in `cache/` e non chiedere due volte la
stessa cosa.

Convenzioni di PVGIS che valgono in tutto il modulo:

- azimut: 0 = sud, -90 = est, +90 = ovest (NON la convenzione della bussola,
  dove sud = 180). La funzione `azimut_da_bussola` converte.
- orizzonte: elenco di altezze dell'orizzonte in gradi, a direzioni
  equidistanti, partendo da NORD e girando in senso orario. È il profilo
  che calcoliamo dal DSM LiDAR (strumenti/analisi_superfici.py) per tenere
  conto di montagne, alberi e case vicine.
"""

from __future__ import annotations

import hashlib
import json
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

URL_PVGIS = "https://re.jrc.ec.europa.eu/api/v5_3/"
CARTELLA_CACHE = Path(__file__).resolve().parent.parent / "cache" / "pvgis"


def azimut_da_bussola(gradi_bussola: float) -> float:
    """Converte un azimut da bussola (nord = 0, est = 90, sud = 180) a PVGIS (sud = 0)."""
    a = gradi_bussola - 180.0
    # Riporta nell'intervallo -180..180, così est resta negativo e ovest positivo.
    return (a + 180.0) % 360.0 - 180.0


@dataclass(frozen=True)
class StimaAnnua:
    """Risultato di PVGIS per un impianto: totale annuo e valori mensili."""

    kwh_anno: float  # energia prodotta in un anno medio
    kwh_mese: tuple[float, ...]  # 12 valori, da gennaio a dicembre
    variabilita_kwh: float  # deviazione standard fra un anno e l'altro
    perdite_totali: float  # frazione persa rispetto all'ideale, ombre comprese
    orizzonte_usato: str  # "utente", "pvgis" o "nessuno"


def _chiama(servizio: str, parametri: dict, cache: Path | None) -> dict:
    """Chiamata all'API PVGIS, con risposta salvata su disco.

    La chiave della cache è un'impronta dei parametri: se cambiano anche di
    poco (un grado di inclinazione) si rifà la chiamata.
    """
    parametri = {**parametri, "outputformat": "json", "browser": 0}
    chiave = hashlib.sha256(json.dumps([servizio, parametri], sort_keys=True).encode()).hexdigest()[:20]
    if cache is not None:
        file = cache / f"{servizio}_{chiave}.json"
        if file.exists():
            return json.loads(file.read_text(encoding="utf-8"))

    url = URL_PVGIS + servizio + "?" + urllib.parse.urlencode(parametri)
    with urllib.request.urlopen(url, timeout=60) as risposta:
        dati = json.load(risposta)

    if cache is not None:
        cache.mkdir(parents=True, exist_ok=True)
        file.write_text(json.dumps(dati), encoding="utf-8")
    return dati


def stima_annua(
    lat: float,
    lon: float,
    kwp: float,
    inclinazione_deg: float,
    azimut_deg: float,
    perdite: float = 0.14,
    orizzonte: list[float] | None = None,
    usa_orizzonte_pvgis: bool = True,
    cache: Path | None = CARTELLA_CACHE,
) -> StimaAnnua:
    """Produzione media annua e mensile di un impianto fisso (servizio PVcalc).

    `perdite` è la frazione persa in cavi, inverter, sporco (0.14 = 14%).
    Se `orizzonte` è dato, PVGIS usa quel profilo; altrimenti usa il suo,
    ricavato da un modello del terreno a bassa risoluzione che vede le
    montagne ma non alberi e case (oppure nessuno, se `usa_orizzonte_pvgis`
    è falso: utile per misurare quanto pesano le ombre).
    """
    parametri = {
        "lat": round(lat, 5),
        "lon": round(lon, 5),
        "peakpower": kwp,
        "loss": round(perdite * 100, 2),  # PVGIS vuole la percentuale
        # float() rende la chiave della cache uguale per 20 e 20.0.
        "angle": float(round(inclinazione_deg, 1)),
        "aspect": float(round(azimut_deg, 1)),
        "mountingplace": "building",  # pannelli aderenti al tetto: si scaldano di più
    }
    if orizzonte is not None:
        parametri["userhorizon"] = ",".join(f"{h:.1f}" for h in orizzonte)
        fonte_orizzonte = "utente"
    elif usa_orizzonte_pvgis:
        fonte_orizzonte = "pvgis"
    else:
        parametri["usehorizon"] = 0
        fonte_orizzonte = "nessuno"

    dati = _chiama("PVcalc", parametri, cache)
    totali = dati["outputs"]["totals"]["fixed"]
    mesi = tuple(m["E_m"] for m in dati["outputs"]["monthly"]["fixed"])
    return StimaAnnua(
        kwh_anno=totali["E_y"],
        kwh_mese=mesi,
        variabilita_kwh=totali["SD_y"],
        perdite_totali=-totali["l_total"] / 100.0,  # PVGIS la dà come percentuale negativa
        orizzonte_usato=fonte_orizzonte,
    )
