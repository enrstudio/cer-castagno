"""Scenari di riscaldamento senza gas per una casa, a partire dalle sue bollette GPL.

Passi:
1. legge le letture EFFETTIVE del contatore GPL dalle fatture estratte con
   `estrai_bollette.py` (le letture stimate dal distributore non servono);
2. scarica le temperature orarie dello stesso periodo e tara il modello
   dei consumi (motore/calore.py);
3. con il clima di ogni anno dal 2016 all'ultimo anno completo, calcola
   il calore che serve alla casa e quanto costa produrlo in quattro modi:
   GPL come oggi (solo come riferimento), solo pompa di calore, pompa di
   calore con stufa a pellet, pompa di calore con stufa a legna.

I dati della casa (posizione, persone, usi del gas) stanno in un file YAML
nella cartella privata `dati/`, per esempio:

    case:
      casa_a:
        lat: 44.0132
        lon: 10.9151
        quota_m: 525
        fatture_gpl: bollette/gpl_fatture.csv   # relativo al file YAML
        persone: 2
        gas_per_acqua_calda: true
        gas_per_cucina: true
        potenza_contatore_kw: 3

Uso:
    python strumenti/scenari_calore.py dati/case.yaml casa_a dati/calore
"""

from __future__ import annotations

import argparse
import csv
import statistics
import sys
from dataclasses import asdict
from datetime import date, datetime
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from motore.calore import (  # noqa: E402
    Intervallo, ParametriPdc, Stufa, calibra, costo_potenza_in_piu, domanda_oraria,
    elettricita_induzione_kwh_anno, medie_giornaliere, quota_fissa_m3_giorno, simula,
)
from motore.ipotesi import carica_ipotesi  # noqa: E402
from motore.meteo import temperature_orarie  # noqa: E402

PRIMO_ANNO_CLIMA = 2016  # dieci inverni bastano a vedere la differenza fra un anno mite e uno freddo


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


def _forchetta(valori: list[float], cifre: int = 0) -> str:
    """Media e, fra parentesi, l'anno più mite e quello più freddo."""
    f = f"{{:,.{cifre}f}}"
    testo = lambda v: f.format(v).replace(",", " ")  # noqa: E731 - spazio fine per le migliaia
    return f"{testo(statistics.mean(valori))} ({testo(min(valori))}–{testo(max(valori))})"


def main() -> None:
    parser = argparse.ArgumentParser(description="Scenari di riscaldamento senza gas per una casa.")
    parser.add_argument("case", type=Path, help="file YAML con i dati delle case (in dati/)")
    parser.add_argument("casa", help="nome della casa nel file")
    parser.add_argument("uscita", type=Path, help="cartella dove scrivere i CSV dei risultati")
    args = parser.parse_args()

    reg = carica_ipotesi()
    v = reg.valore
    casa = yaml.safe_load(args.case.read_text(encoding="utf-8"))["case"][args.casa]

    intervalli = intervalli_da_fatture(args.case.parent / casa["fatture_gpl"])
    ultimo_anno = date.today().year - 1
    temperature = temperature_orarie(casa["lat"], casa["lon"], casa["quota_m"],
                                     date(min(PRIMO_ANNO_CLIMA, intervalli[0].dal.year), 1, 1),
                                     max(intervalli[-1].al, date(ultimo_anno, 12, 31)))
    medie = medie_giornaliere(temperature)

    # 1. Taratura sulle letture.
    pci, rend = v("pci_gpl"), v("rendimento_caldaia_gpl")
    base = quota_fissa_m3_giorno(casa["persone"], casa["gas_per_acqua_calda"], casa["gas_per_cucina"],
                                 v("acs_kwh_persona_giorno"), v("gpl_cucina_m3_giorno"), pci, rend)
    t_min, t_max = reg.forchetta("temperatura_base_riscaldamento")
    cal = calibra(intervalli, medie, base, t_min, t_max)

    print(f"Registro delle ipotesi versione {reg.versione}\n")
    print("TARATURA SULLE LETTURE EFFETTIVE DEL CONTATORE GPL")
    print(f"  quota fissa (acqua calda e cucina): {cal.base_m3_giorno:.3f} m³/giorno, "
          f"{cal.base_m3_giorno * 365:.0f} m³/anno (fissata, non stimata)")
    print(f"  riscaldamento: {cal.m3_per_grado_giorno:.4f} m³ per grado giorno, "
          f"temperatura base {cal.t_base:.1f} °C")
    print(f"  scarto medio: {cal.scarto_m3:.1f} m³ per intervallo ({cal.scarto_relativo:.0%})")
    if cal.t_base in (t_min, t_max):
        # Il valore migliore sta fuori dalla forchetta: il modello forse non descrive bene questa casa
        # (una stufa che aiuta nelle mezze stagioni, una quota fissa sbagliata, un riscaldamento a orari).
        print(f"  ATTENZIONE: la temperatura base è al bordo della forchetta ({t_min}–{t_max} °C) del registro")
    print(f"  {'dal':>10}  {'al':>10}  {'letti':>6}  {'previsti':>8}")
    for iv, previsto in cal.confronto:
        print(f"  {iv.dal}  {iv.al}  {iv.m3:6.0f}  {previsto:8.0f}")

    # 2. Calore e pompa di calore, con il clima di ogni anno completo.
    clima = {o: t for o, t in temperature.items() if PRIMO_ANNO_CLIMA <= o.year <= ultimo_anno}
    acs_kwh_giorno = casa["persone"] * v("acs_kwh_persona_giorno")
    domanda = domanda_oraria(clima, cal, pci, rend, acs_kwh_giorno, v("temperatura_interna"))
    pdc = ParametriPdc(v("mandata_a_zero_gradi"), v("pendenza_curva_climatica"),
                       v("temperatura_acqua_calda"), v("correzione_cop"))
    stufe = {
        "pellet": Stufa("pellet", v("quota_stufa"), v("pci_pellet"), v("rendimento_stufa_pellet"), v("prezzo_pellet")),
        "legna": Stufa("legna", v("quota_stufa"), v("pci_legna"), v("rendimento_stufa_legna"), v("prezzo_legna")),
    }
    solo_pdc = simula(domanda, pdc)
    ibridi = {nome: simula(domanda, pdc, s) for nome, s in stufe.items()}

    # GPL che il modello prevede per ogni anno: il riferimento di spesa, con lo stesso clima.
    gpl_anno = [cal.m3_previsti(medie, date(a.anno, 1, 1), date(a.anno + 1, 1, 1)) for a in solo_pdc]

    # 3. Spesa annua di energia (senza investimenti né manutenzione).
    induzione = elettricita_induzione_kwh_anno(v("gpl_cucina_m3_giorno"), pci, v("rendimento_fornelli_gas"),
                                               v("rendimento_induzione")) if casa["gas_per_cucina"] else 0.0
    potenza = costo_potenza_in_piu(casa["potenza_contatore_kw"], v("potenza_dopo_elettrificazione"),
                                   v("quota_potenza"), v("iva_luce"))
    luce = v("prezzo_luce_marginale")

    def spesa(anni, stufa=None):
        return [(a.elettricita_pdc_kwh + induzione) * luce + potenza
                + (a.combustibile_kg * stufa.prezzo_eur_kg if stufa else 0.0) for a in anni]

    print(f"\nCLIMA {PRIMO_ANNO_CLIMA}–{ultimo_anno}: media (anno più mite – anno più freddo)")
    print(f"  calore per riscaldamento: {_forchetta([a.calore_riscaldamento_kwh for a in solo_pdc])} kWh/anno")
    print(f"  calore per acqua calda:   {_forchetta([a.calore_acqua_calda_kwh for a in solo_pdc])} kWh/anno")
    print(f"  GPL equivalente:          {_forchetta(gpl_anno)} m³/anno")
    print(f"  temperatura più bassa:    {min(a.t_minima for a in solo_pdc):.1f} °C")
    print(f"  picco di calore:          {max(a.picco_termico_kw for a in solo_pdc):.1f} kW medi in un'ora")

    print("\nPOMPA DI CALORE")
    print(f"  SCOP (rendimento medio annuo): {_forchetta([a.scop for a in solo_pdc], 2)}")
    print(f"  elettricità pompa di calore:   {_forchetta([a.elettricita_pdc_kwh for a in solo_pdc])} kWh/anno")
    print(f"  piano a induzione:             {induzione:.0f} kWh/anno")
    print(f"  picco elettrico della pompa:   {max(a.picco_elettrico_kw for a in solo_pdc):.1f} kW medi in un'ora")
    for nome, mandata in zip(("termosifoni grandi", "termosifoni piccoli"), reg.forchetta("mandata_a_zero_gradi")):
        prova = simula(domanda, ParametriPdc(mandata, pdc.pendenza_curva, pdc.t_acqua_calda, pdc.correzione_cop))
        print(f"  con {nome} (acqua a {mandata:.0f} °C con 0 °C fuori): SCOP "
              f"{statistics.mean(a.scop for a in prova):.2f}, "
              f"{statistics.mean(a.elettricita_pdc_kwh for a in prova):,.0f} kWh/anno".replace(",", " "))

    print(f"\nSPESA ANNUA DI ENERGIA, euro (contatore da {casa['potenza_contatore_kw']} a "
          f"{v('potenza_dopo_elettrificazione')} kW: +{potenza:.0f} €/anno compresi)")
    print(f"  GPL come oggi (riferimento):  {_forchetta([m3 * v('prezzo_gpl') for m3 in gpl_anno])}")
    print(f"  solo pompa di calore:         {_forchetta(spesa(solo_pdc))}")
    for nome, anni in ibridi.items():
        kg = _forchetta([a.combustibile_kg for a in anni])
        print(f"  pompa di calore + {nome:7s}:   {_forchetta(spesa(anni, stufe[nome]))}   ({kg} kg di {nome})")
    print(f"  (stufa al {v('quota_stufa'):.0%} del riscaldamento; luce a {luce} €/kWh, "
          f"pellet a {v('prezzo_pellet')} €/kg, legna a {v('prezzo_legna')} €/kg)")

    # 4. CSV per i grafici e per il bilancio con il fotovoltaico.
    args.uscita.mkdir(parents=True, exist_ok=True)
    with open(args.uscita / f"{args.casa}_anni.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["scenario", *asdict(solo_pdc[0]).keys(), "gpl_m3_riferimento", "spesa_eur"])
        for nome, anni, s in [("solo_pdc", solo_pdc, None), *[(f"pdc_{n}", a, stufe[n]) for n, a in ibridi.items()]]:
            for a, m3, eur in zip(anni, gpl_anno, spesa(anni, s)):
                w.writerow([nome, *asdict(a).values(), round(m3, 1), round(eur, 2)])  # i mesi restano in una cella
    with open(args.uscita / f"{args.casa}_mesi.csv", "w", newline="", encoding="utf-8") as f:
        # Media sugli anni di clima, mese per mese: è la forma che servirà per il confronto col fotovoltaico.
        n_anni = len(solo_pdc)
        calore = [[0.0, 0.0] for _ in range(12)]
        for h in domanda:
            calore[h.ora.month - 1][0] += h.riscaldamento_kwh / n_anni
            calore[h.ora.month - 1][1] += h.acqua_calda_kwh / n_anni
        w = csv.writer(f)
        w.writerow(["mese", "calore_riscaldamento_kwh", "calore_acqua_calda_kwh", "elettricita_solo_pdc_kwh",
                    *[f"elettricita_pdc_{n}_kwh" for n in ibridi], "induzione_kwh"])
        for m in range(12):
            el = [statistics.mean(a.elettricita_mese_kwh[m] for a in anni) for anni in (solo_pdc, *ibridi.values())]
            w.writerow([m + 1, *(round(x, 1) for x in (*calore[m], *el, induzione / 12))])
    print(f"\nRisultati in {args.uscita}/")


if __name__ == "__main__":
    main()
