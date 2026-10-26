"""Scheda energetica di ogni casa: tetto, consumi di oggi, riscaldamento senza gas.

Per ogni casa del file YAML:
1. il tetto: kWp e produzione mese per mese della sua falda, dalla tabella
   di `analisi_superfici.py`;
2. la luce di oggi, mese per mese, se ci sono le bollette;
3. il calore. Se la casa si scalda a gas, il modello dei consumi si tara
   sulle letture EFFETTIVE del contatore GPL (motore/calore.py) o, in
   mancanza, sul GPL di un anno tipico dichiarato nel questionario. Se la
   casa si scalda a legna, il riscaldamento resta com'è;
4. senza gas: pompa di calore per riscaldamento e acqua calda dove oggi li
   fa il gas, piano a induzione dove oggi si cucina a gas. Con il clima di
   ogni anno dal 2016 all'ultimo anno completo si confronta la spesa di
   energia: GPL come oggi (riferimento), solo pompa di calore, pompa di
   calore con stufa a pellet o a legna.

I dati delle case stanno in un file YAML nella cartella privata `dati/`:

    quota_m: 525                          # quota delle case, per le temperature
    falde: superfici/falde.csv            # percorsi relativi al file YAML
    case:
      centro:
        falda: 2                          # id della falda nella tabella
        persone: 5
        riscaldamento: gas                # gas | legna
        acqua_calda: gas                  # gas | legna | elettrico
        cucina: gas                       # gas | induzione
        potenza_contatore_kw: 3
        fatture_gpl: bollette/gpl_fatture.csv   # oppure gpl_m3_anno: 300
        luce_mensile: bollette/enel_mensile.csv # facoltativo
        mandata_a_zero_gradi: 45          # facoltativo: sostituisce il registro per questa casa

Una voce mancante (per esempio il GPL di una casa che non ha ancora
risposto) non ferma il calcolo: la scheda la elenca fra i dati da chiedere.

Uso:
    python strumenti/scenari_calore.py dati/case.yaml dati/calore [--casa centro]
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
import sys
from datetime import date, datetime
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from motore.calore import (  # noqa: E402
    Calibrazione, Intervallo, ParametriPdc, Stufa, calibra, calibra_da_consumo_annuo, costo_potenza_in_piu,
    domanda_oraria, elettricita_induzione_kwh_anno, medie_giornaliere, quota_fissa_m3_giorno, simula,
)
from motore.ipotesi import carica_ipotesi  # noqa: E402
from motore.meteo import temperature_orarie  # noqa: E402

PRIMO_ANNO_CLIMA = 2016  # dieci inverni bastano a vedere la differenza fra un anno mite e uno freddo
ANNI_BOLLETTE_LUCE = ("2023", "2024", "2025")  # anni completi delle bollette Enel
# Anni a cui si riferisce il "GPL di un anno tipico" dichiarato nel questionario.
ANNI_QUESTIONARIO = (2023, 2024, 2025)


def _data(testo: str) -> date:
    return datetime.strptime(testo, "%d/%m/%Y").date()


def intervalli_da_fatture(percorso: Path) -> list[Intervallo]:
    """Gli intervalli fra due letture effettive, uno per ogni fattura che ne chiude uno."""
    intervalli = []
    with open(percorso, encoding="utf-8") as f:
        for riga in csv.DictReader(f):
            if riga["tipo_lettura_finale"] != "Effettiva" or not riga["lettura_da"]:
                continue
            m3 = float(riga["lettura_finale"]) - float(riga["lettura_iniziale"])
            intervalli.append(Intervallo(_data(riga["lettura_da"]), _data(riga["lettura_a"]), m3))
    intervalli.sort(key=lambda iv: iv.dal)
    for prima, dopo in zip(intervalli, intervalli[1:]):
        if dopo.dal < prima.al:
            raise ValueError(f"Intervalli sovrapposti: {prima} e {dopo}")
    return intervalli


def luce_media_mensile(percorso: Path) -> list[float]:
    """kWh di luce di ogni mese, media degli anni completi delle bollette."""
    per_mese: dict[int, list[float]] = {m: [] for m in range(1, 13)}
    with open(percorso, encoding="utf-8") as f:
        for riga in csv.DictReader(f):
            anno, mese = riga["mese"].split("-")
            if anno in ANNI_BOLLETTE_LUCE:
                per_mese[int(mese)].append(float(riga["Tot"]))
    return [statistics.mean(v) for v in per_mese.values()]


def leggi_falde(percorso: Path) -> dict[int, dict]:
    """La tabella delle falde: posizione, kWp e produzione mensile di 1 kWp."""
    with open(percorso, encoding="utf-8") as f:
        return {int(r["id"]): r for r in csv.DictReader(f)}


def _n(valore: float, cifre: int = 0) -> str:
    """Un numero con lo spazio fine per le migliaia: 5 313."""
    return f"{valore:,.{cifre}f}".replace(",", "\u202f")


def _forchetta(valori: list[float], cifre: int = 0) -> str:
    """Media e, fra parentesi, l'anno più mite e quello più freddo."""
    return f"{_n(statistics.mean(valori), cifre)} ({_n(min(valori), cifre)}–{_n(max(valori), cifre)})"


def analizza_casa(nome: str, casa: dict, falda: dict, cartella: Path, reg, temperature, medie, ultimo_anno) -> dict:
    """Tutti i numeri di una casa. Restituisce un dizionario per le tabelle e stampa la scheda."""
    v = reg.valore
    mancano: list[str] = []
    pci, rend = v("pci_gpl"), v("rendimento_caldaia_gpl")
    print(f"\n=== CASA {nome.upper()} (falda {casa['falda']}, {casa['persone']} persone) ===")

    # 1. Il tetto.
    kwp = float(falda["kwp_possibili"])
    fv_mese = [x * kwp for x in json.loads(falda["kwh_mese_lidar_1kwp"])]
    print(f"Tetto: {kwp:.1f} kWp, {_n(sum(fv_mese))} kWh/anno"
          f" (inclinazione {falda['fonte_inclinazione']} {float(falda['inclinazione_deg']):.0f}°)")

    # 2. La luce di oggi.
    luce_mese = luce_media_mensile(cartella / casa["luce_mensile"]) if casa.get("luce_mensile") else None
    if luce_mese:
        print(f"Luce oggi: {_n(sum(luce_mese))} kWh/anno")
    else:
        mancano.append("consumi di luce (bollette o kWh all'anno)")

    # 3. Il calore. La quota fissa conta solo gli usi che oggi fa il gas.
    acs_gas, cucina_gas, risc_gas = (casa["acqua_calda"] == "gas", casa["cucina"] == "gas",
                                     casa["riscaldamento"] == "gas")
    base = quota_fissa_m3_giorno(casa["persone"], acs_gas, cucina_gas,
                                 v("acs_kwh_persona_giorno"), v("gpl_cucina_m3_giorno"), pci, rend)
    cal: Calibrazione | None = None
    if not risc_gas:
        # Riscaldamento a legna: resta com'è, e del gas resta solo la quota fissa.
        cal = Calibrazione(base, 0.0, v("temperatura_base_riscaldamento"), float("nan"), float("nan"), ())
        print(f"Riscaldamento: {casa['riscaldamento']}, resta com'è")
    elif casa.get("fatture_gpl"):
        t_min, t_max = reg.forchetta("temperatura_base_riscaldamento")
        cal = calibra(intervalli_da_fatture(cartella / casa["fatture_gpl"]), medie, base, t_min, t_max)
        print(f"Taratura sulle letture GPL: {cal.m3_per_grado_giorno:.3f} m³ per grado giorno, temperatura base "
              f"{cal.t_base:.1f} °C, scarto {cal.scarto_m3:.0f} m³ per intervallo ({cal.scarto_relativo:.0%})")
        if cal.t_base in (t_min, t_max):
            # Il valore migliore sta fuori dalla forchetta: il modello forse non descrive bene questa casa.
            print(f"  ATTENZIONE: temperatura base al bordo della forchetta ({t_min}–{t_max} °C) del registro")
    elif casa.get("gpl_m3_anno"):
        cal = calibra_da_consumo_annuo(casa["gpl_m3_anno"], medie, ANNI_QUESTIONARIO, base,
                                       v("temperatura_base_riscaldamento"))
        print(f"Taratura sul GPL dichiarato ({casa['gpl_m3_anno']} m³/anno): {cal.m3_per_grado_giorno:.3f} m³ "
              f"per grado giorno")
    else:
        mancano.append("GPL consumato in un anno (m³ o bollette)")

    risultato = {"nome": nome, "kwp": kwp, "fv_mese": fv_mese, "luce_mese": luce_mese, "mancano": mancano,
                 "persone": casa["persone"], "falda": casa["falda"], "riscaldamento": casa["riscaldamento"],
                 "acqua_calda": casa["acqua_calda"], "cucina": casa["cucina"], "scenari": {}, "mesi": None}
    if cal is None:
        print("Senza gas: non calcolabile, manca il consumo di GPL")
        print("Dati da chiedere: " + "; ".join(mancano))
        return risultato

    # 4. Senza gas.
    clima = {o: t for o, t in temperature.items() if PRIMO_ANNO_CLIMA <= o.year <= ultimo_anno}
    acs_kwh_giorno = casa["persone"] * v("acs_kwh_persona_giorno") if acs_gas else 0.0
    domanda = domanda_oraria(clima, cal, pci, rend, acs_kwh_giorno, v("temperatura_interna"))
    pdc = ParametriPdc(casa.get("mandata_a_zero_gradi", v("mandata_a_zero_gradi")),
                       v("pendenza_curva_climatica"), v("temperatura_acqua_calda"), v("correzione_cop"))
    gpl_anno = [cal.m3_previsti(medie, date(a, 1, 1), date(a + 1, 1, 1))
                for a in range(PRIMO_ANNO_CLIMA, ultimo_anno + 1)]
    solo_pdc = simula(domanda, pdc)
    induzione = elettricita_induzione_kwh_anno(v("gpl_cucina_m3_giorno"), pci, v("rendimento_fornelli_gas"),
                                               v("rendimento_induzione")) if cucina_gas else 0.0
    kw_dopo = casa.get("potenza_dopo_kw", max(casa["potenza_contatore_kw"], v("potenza_dopo_elettrificazione")))
    potenza = costo_potenza_in_piu(casa["potenza_contatore_kw"], kw_dopo, v("quota_potenza"), v("iva_luce"))
    luce = v("prezzo_luce_marginale")

    def spesa(anni, stufa=None):
        return [(a.elettricita_pdc_kwh + induzione) * luce + potenza
                + (a.combustibile_kg * stufa.prezzo_eur_kg if stufa else 0.0) for a in anni]

    scenari = {"GPL come oggi": ([m3 * v("prezzo_gpl") for m3 in gpl_anno], None)}
    con_pdc = risc_gas or acs_gas
    scenari["Solo pompa di calore" if con_pdc else "Senza gas"] = (spesa(solo_pdc), solo_pdc)
    if risc_gas:
        for nome_stufa, chiave in (("pellet", "pellet"), ("legna", "legna")):
            stufa = Stufa(nome_stufa, v("quota_stufa"), v(f"pci_{chiave}"), v(f"rendimento_stufa_{chiave}"),
                          v(f"prezzo_{chiave}"))
            anni = simula(domanda, pdc, stufa)
            scenari[f"Pompa di calore + {nome_stufa}"] = (spesa(anni, stufa), anni)

    print(f"GPL oggi (modello, clima {PRIMO_ANNO_CLIMA}–{ultimo_anno}): {_forchetta(gpl_anno)} m³/anno")
    if con_pdc:
        print(f"Calore: riscaldamento {_forchetta([a.calore_riscaldamento_kwh for a in solo_pdc])} kWh, "
              f"acqua calda {_n(statistics.mean(a.calore_acqua_calda_kwh for a in solo_pdc))} kWh")
        print(f"Pompa di calore: {_forchetta([a.elettricita_pdc_kwh for a in solo_pdc])} kWh/anno, SCOP "
              f"{_forchetta([a.scop for a in solo_pdc], 2)}, picco {max(a.picco_elettrico_kw for a in solo_pdc):.1f} kW"
              f" (acqua ai termosifoni a {pdc.mandata_a_zero_gradi:.0f} °C con 0 °C fuori)")
    if induzione:
        print(f"Piano a induzione: {induzione:.0f} kWh/anno")
    print(f"Spesa annua di energia, euro (contatore {casa['potenza_contatore_kw']} → {kw_dopo} kW, +{potenza:.0f} €/anno):")
    for nome_s, (eur, _) in scenari.items():
        print(f"  {nome_s:28s} {_forchetta(eur)}")
    if mancano:
        print("Dati da chiedere: " + "; ".join(mancano))

    risultato["scenari"] = scenari
    risultato["gpl_anno"] = gpl_anno
    n = len(solo_pdc)
    risultato["mesi"] = {
        "pdc": [statistics.mean(a.elettricita_mese_kwh[m] for a in solo_pdc) for m in range(12)],
        "induzione": [induzione / 12] * 12,
        "riscaldamento": [sum(h.riscaldamento_kwh for h in domanda if h.ora.month == m + 1) / n for m in range(12)],
        "acqua_calda": [sum(h.acqua_calda_kwh for h in domanda if h.ora.month == m + 1) / n for m in range(12)],
    }
    return risultato


def scrivi_tabelle(risultati: list[dict], uscita: Path) -> None:
    """Tre CSV: una riga per casa, una per casa e mese, una per casa, scenario e anno."""
    uscita.mkdir(parents=True, exist_ok=True)
    with open(uscita / "case_schede.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["casa", "falda", "persone", "riscaldamento", "acqua_calda", "cucina", "kwp",
                    "fotovoltaico_kwh_anno", "luce_oggi_kwh_anno", "gpl_m3_anno", "dati_mancanti"])
        for r in risultati:
            w.writerow([r["nome"], r["falda"], r["persone"], r["riscaldamento"], r["acqua_calda"], r["cucina"],
                        round(r["kwp"], 1), round(sum(r["fv_mese"])),
                        round(sum(r["luce_mese"])) if r["luce_mese"] else "",
                        round(statistics.mean(r["gpl_anno"])) if r.get("gpl_anno") else "",
                        "; ".join(r["mancano"])])
    with open(uscita / "case_mesi.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["casa", "mese", "fotovoltaico_kwh", "luce_oggi_kwh", "pompa_di_calore_kwh", "induzione_kwh",
                    "calore_riscaldamento_kwh", "calore_acqua_calda_kwh"])
        for r in risultati:
            mesi = r["mesi"]
            for m in range(12):
                cella = lambda chiave: round(mesi[chiave][m], 1) if mesi else ""  # noqa: E731
                w.writerow([r["nome"], m + 1, round(r["fv_mese"][m], 1),
                            round(r["luce_mese"][m], 1) if r["luce_mese"] else "",
                            cella("pdc"), cella("induzione"), cella("riscaldamento"), cella("acqua_calda")])
    with open(uscita / "case_anni.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["casa", "scenario", "anno", "spesa_eur", "elettricita_pdc_kwh", "combustibile_kg", "scop",
                    "picco_elettrico_kw", "t_minima"])
        for r in risultati:
            for scenario, (eur, anni) in r["scenari"].items():
                for i, e in enumerate(eur):
                    a = anni[i] if anni else None
                    w.writerow([r["nome"], scenario, PRIMO_ANNO_CLIMA + i, round(e, 2),
                                round(a.elettricita_pdc_kwh, 1) if a else "", round(a.combustibile_kg, 1) if a else "",
                                round(a.scop, 3) if a else "", round(a.picco_elettrico_kw, 2) if a else "",
                                a.t_minima if a else ""])


def main() -> None:
    parser = argparse.ArgumentParser(description="Scheda energetica di ogni casa e scenari senza gas.")
    parser.add_argument("case", type=Path, help="file YAML con i dati delle case (in dati/)")
    parser.add_argument("uscita", type=Path, help="cartella dove scrivere i CSV dei risultati")
    parser.add_argument("--casa", help="una casa sola (di base: tutte)")
    args = parser.parse_args()

    reg = carica_ipotesi()
    config = yaml.safe_load(args.case.read_text(encoding="utf-8"))
    cartella = args.case.parent
    falde = leggi_falde(cartella / config["falde"])
    case = {k: c for k, c in config["case"].items() if args.casa in (None, k)}

    # Una sola serie di temperature per tutte: le case distano poche decine di metri.
    primo = falde[next(iter(case.values()))["falda"]]
    ultimo_anno = date.today().year - 1
    temperature = temperature_orarie(float(primo["lat"]), float(primo["lon"]), config["quota_m"],
                                     date(PRIMO_ANNO_CLIMA, 1, 1), date.today())
    medie = medie_giornaliere(temperature)

    print(f"Registro delle ipotesi versione {reg.versione}")
    risultati = [analizza_casa(nome, c, falde[c["falda"]], cartella, reg, temperature, medie, ultimo_anno)
                 for nome, c in case.items()]
    scrivi_tabelle(risultati, args.uscita)
    print(f"\nTabelle in {args.uscita}/")


if __name__ == "__main__":
    main()
