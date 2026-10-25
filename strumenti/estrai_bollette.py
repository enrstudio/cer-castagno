"""Estrae i dati dalle bollette in PDF (luce Enel, GPL Beyfin) e li salva in CSV.

Serve a trasformare anni di fatture in tabelle che il motore può leggere,
senza ricopiare i numeri a mano. Legge il testo dei PDF con `pdftotext`
(pacchetto poppler-utils) e cerca le voci con espressioni regolari tarate
sui modelli di bolletta usati da Enel Energia (2023-2026) e Beyfin.

Produce tre file nella cartella di uscita:

- enel_fatture.csv   una riga per bolletta: periodo, spese per voce, kWh per fascia
- enel_mensile.csv   kWh mese per mese e per fascia, dalla tabella "ultimi 12/18 mesi"
                     che Enel stampa in ogni bolletta (le letture reali più recenti
                     sostituiscono le stime)
- gpl_fatture.csv    una riga per fattura GPL: periodo, m³, letture, prezzo, totale

ATTENZIONE: i CSV contengono dati personali (POD, consumi). Vanno salvati
in `dati/`, che è esclusa da git, mai altrove nel repository.

I modelli delle bollette cambiano nel tempo: se una voce esce vuota,
controllare il testo con `pdftotext -layout fattura.pdf -` e aggiornare
l'espressione regolare corrispondente.

Uso:
    python strumenti/estrai_bollette.py CARTELLA_PDF dati/bollette
"""

from __future__ import annotations

import argparse
import csv
import re
import subprocess
from pathlib import Path

MESI = {"GEN": 1, "FEB": 2, "MAR": 3, "APR": 4, "MAG": 5, "GIU": 6, "LUG": 7, "AGO": 8, "SET": 9, "OTT": 10, "NOV": 11, "DIC": 12}


# --- Utilità -------------------------------------------------------------------


def testo_pdf(percorso: Path) -> str:
    """Testo del PDF con l'impaginazione conservata (le colonne restano allineate)."""
    return subprocess.run(["pdftotext", "-layout", str(percorso), "-"], capture_output=True, text=True).stdout


def numero(s: str) -> float:
    """Converte un numero scritto all'italiana ("1.234,56") in float."""
    return float(s.replace(".", "").replace(",", "."))


def euro_dopo(testo: str, etichetta: str) -> float | None:
    """Il primo importo in euro sulla stessa riga dell'etichetta."""
    m = re.search(etichetta + r"[^\n]*?(-?[\d.]+,\d{2})\s*€", testo)
    return numero(m.group(1)) if m else None


def e_bolletta_enel(testo: str) -> bool:
    # Le ricevute di pagamento e le fatture dei servizi extra non hanno consumi in kWh.
    return "Enel Energia" in testo and "kWh" in testo and re.search(r"Totale Bolletta|TOTALE BOLLETTA", testo) is not None


def e_fattura_gpl(testo: str) -> bool:
    return "BEYFIN" in testo and re.search(r"FATTURA PER LA FORNITURA DI G\.P\.L\.|NOTA CREDITO", testo) is not None


# --- Luce (Enel) -----------------------------------------------------------------


def leggi_enel(testo: str, nome_file: str) -> dict:
    """Le voci principali di una bolletta Enel."""
    riga: dict = {"file": nome_file}
    m = re.search(r"fattura elettronica n\. \d+ del (\d{2}/\d{2}/\d{4})", testo)
    riga["data_fattura"] = m.group(1) if m else ""
    m = re.search(r"Periodo ([A-Z]{3}\. \d{4}(?: - [A-Z]{3}\. \d{4})?)", testo)
    riga["periodo"] = m.group(1) if m else ""

    # Composizione della spesa (modello 2023-2025; dal 2025 alcune voci sono raggruppate).
    riga["spesa_energia"] = euro_dopo(testo, r"Spesa per l'energia \(A\)")
    riga["spesa_trasporto"] = euro_dopo(testo, r"Spesa per il trasporto dell'energia elettrica e la gestione")
    riga["oneri_sistema"] = euro_dopo(testo, r"Spesa oneri di sistema \(A\)")
    riga["imposte_iva"] = euro_dopo(testo, r"Totale imposte e IVA \(B\)")
    riga["totale_bolletta"] = euro_dopo(testo, r"Totale Bolletta") or euro_dopo(testo, r"TOTALE BOLLETTA")
    riga["totale_da_pagare"] = euro_dopo(testo, r"Totale da pagare") or euro_dopo(testo, r"TOTALE DA PAGARE")

    # Consumo fatturato per fascia (modello 2023-2025).
    m = re.search(
        r"Consumo fatturato \(dal (\d{2}\.\d{2}\.\d{4}) al (\d{2}\.\d{2}\.\d{4})\)\s*\n\s*F1\s+F2\s+F3\s+Totale energia\s*\n"
        r"\s*([\d.]+) kWh\s+([\d.]+) kWh\s+([\d.]+) kWh\s+([\d.]+) kWh",
        testo,
    )
    if m:
        riga.update(dal=m.group(1), al=m.group(2), kwh_f1=numero(m.group(3)), kwh_f2=numero(m.group(4)),
                    kwh_f3=numero(m.group(5)), kwh_tot=numero(m.group(6)))
    else:
        # Modello 2026: solo il totale del periodo.
        m = re.search(r"Consumo del periodo\s*\n[^\n]*?([\d.]+) kWh", testo)
        if m:
            riga["kwh_tot"] = numero(m.group(1))

    m = re.search(r"(?:Potenza contrattualmente impegnata|POTENZA IMPEGNATA)[:\s]*([\d,]+) kW", testo)
    riga["potenza_kw"] = numero(m.group(1)) if m else None
    m = re.search(r"(IT\d{3}E\d{6,})", testo)  # privacy: ok (espressione regolare, non un dato)
    riga["pod"] = m.group(1) if m else ""
    m = re.search(r"(?:L'offerta che hai sottoscritto è|La tua offerta): ([^\n]+?)(?:\s{2,}|\n)", testo)
    riga["offerta"] = m.group(1).strip() if m else ""
    return riga


def leggi_tabella_mensile(testo: str) -> dict[str, dict]:
    """La tabella dei consumi mensili che Enel stampa in ogni bolletta.

    La tabella ha una riga di mesi ("Mag Giu Lug ..."), spesso una riga di
    anni e una di tipo di lettura (Reale, Stimato), poi le righe F1, F2, F3
    e Tot. Nei modelli più vecchi manca la riga degli anni: allora si
    ricavano contando all'indietro dall'ultimo mese del periodo fatturato.
    """
    righe = [r for r in testo.splitlines() if r.strip()]
    for i, riga in enumerate(righe):
        mesi = re.findall(r"\b(Gen|Feb|Mar|Apr|Mag|Giu|Lug|Ago|Set|Ott|Nov|Dic)\b", riga)
        if len(mesi) < 6:
            continue
        anni: list[str] = []
        tipi: list[str] = []
        valori: dict[str, list[float]] = {}
        for successiva in righe[i + 1 : i + 10]:
            trovati = re.findall(r"\b(20\d{2})\b", successiva)
            if len(trovati) >= len(mesi) and not anni:
                anni = trovati
            t = re.findall(r"\b(Reale|Stimato|Stimata|Misto)\b", successiva)
            if len(t) >= len(mesi) // 2 and not tipi:
                tipi = t
            r = re.match(r"\s*(F1|F2|F3|Tot)\s+([\d.\s]+)$", successiva)
            if r:
                valori[r.group(1)] = [numero(x) for x in r.group(2).split()]

        if not anni:
            anni = _anni_dal_periodo(testo, mesi)
        if not anni or "Tot" not in valori or len(valori["Tot"]) != len(mesi):
            continue

        mensile = {}
        for k, mese in enumerate(mesi):
            chiave = f"{anni[k]}-{MESI[mese.upper()]:02d}"
            mensile[chiave] = {f: (valori[f][k] if f in valori and k < len(valori[f]) else None) for f in ("F1", "F2", "F3", "Tot")}
            mensile[chiave]["tipo"] = tipi[k] if k < len(tipi) else ""
        return mensile
    return {}


def _anni_dal_periodo(testo: str, mesi: list[str]) -> list[str]:
    """Anni dei mesi della tabella, contando all'indietro dalla fine del periodo fatturato."""
    m = re.search(r"Periodo [A-Z]{3}\. \d{4} - ([A-Z]{3})\. (\d{4})", testo)
    if not m:
        return []
    anno, mese = int(m.group(2)), MESI[m.group(1)]
    sequenza = []
    for _ in mesi:
        sequenza.append((anno, mese))
        mese -= 1
        if mese == 0:
            anno, mese = anno - 1, 12
    sequenza.reverse()
    # Si accetta solo se i mesi ricostruiti coincidono con quelli stampati.
    if [MESI[x.upper()] for x in mesi] != [ms for _, ms in sequenza]:
        return []
    return [str(a) for a, _ in sequenza]


# --- GPL (Beyfin) ----------------------------------------------------------------


def leggi_gpl(testo: str, nome_file: str) -> dict:
    """Le voci principali di una fattura o nota di credito GPL Beyfin."""
    nota_credito = "NOTA CREDITO" in testo
    riga: dict = {"file": nome_file, "nota_credito": nota_credito}
    m = re.search(r"N\. [\d/\-]+\s+del (\d{2}/\d{2}/\d{4})", testo)
    riga["data_fattura"] = m.group(1) if m else ""
    m = re.search(r"Periodo ([^\n]+?)\s*\n", testo)
    riga["periodo"] = m.group(1).strip() if m else ""
    riga["conguaglio"] = "Conguaglio" in riga["periodo"]
    m = re.search(r"Consumo del periodo\s+Mc\.\s+([\d.,]+)", testo)
    riga["m3"] = numero(m.group(1)) if m else None

    # Le due letture del contatore: "Effettiva" (letta) o "Presunta" (stimata).
    m = re.search(
        r"Lettura (\w+) al (\d{2}/\d{2}/\d{4}) Mc\.\s+([\d.]+)\s*\n\s*Lettura (\w+) al (\d{2}/\d{2}/\d{4}) Mc\.\s+([\d.]+)", testo
    )
    if m:
        riga.update(lettura_da=m.group(2), lettura_a=m.group(5), tipo_lettura_finale=m.group(4),
                    lettura_iniziale=numero(m.group(3)), lettura_finale=numero(m.group(6)))

    m = re.search(r"GPL PROPANO[^\n]*?([\d.]+)\s+MC\s+([\d,]+)\s+(-?[\d.]+,\d{2})", testo)
    if m:
        riga.update(prezzo_eur_m3=numero(m.group(2)), imponibile_gas=numero(m.group(3)))
    m = re.search(r"TOTALE DOCUMENTO\s*\n(?:[^\n]*\n){0,3}?\s*Euro\s+(-?[\d.]+,\d{2})", testo)
    totale = numero(m.group(1)) if m else None
    # Una nota di credito riduce la spesa: il totale va col segno meno.
    riga["totale"] = -abs(totale) if (totale is not None and nota_credito) else totale
    return riga


# --- Scrittura -------------------------------------------------------------------


def scrivi_csv(righe: list[dict], percorso: Path) -> None:
    """Scrive le righe in CSV, con tutte le colonne che compaiono in almeno una riga."""
    colonne: list[str] = []
    for r in righe:
        colonne += [k for k in r if k not in colonne]
    with open(percorso, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, colonne)
        w.writeheader()
        w.writerows(righe)


def main() -> None:
    parser = argparse.ArgumentParser(description="Estrae i dati dalle bollette in PDF e li salva in CSV.")
    parser.add_argument("cartella_pdf", type=Path, help="cartella con le bollette (anche in sottocartelle)")
    parser.add_argument("uscita", type=Path, help="cartella dove scrivere i CSV (dentro dati/)")
    args = parser.parse_args()
    args.uscita.mkdir(parents=True, exist_ok=True)

    enel, mensile, gpl = [], {}, []
    # Ordine per nome: le bollette più recenti, lette per ultime, aggiornano i mesi già visti.
    for pdf in sorted(args.cartella_pdf.rglob("*.pdf"), key=lambda p: (p.parent.as_posix(), p.name)):
        testo = testo_pdf(pdf)
        nome = pdf.relative_to(args.cartella_pdf).as_posix()
        if e_bolletta_enel(testo):
            riga = leggi_enel(testo, nome)
            enel.append(riga)
            for mese, valori in leggi_tabella_mensile(testo).items():
                mensile[mese] = {**valori, "fonte": riga["data_fattura"] or nome}
        elif e_fattura_gpl(testo):
            gpl.append(leggi_gpl(testo, nome))

    scrivi_csv(enel, args.uscita / "enel_fatture.csv")
    scrivi_csv([{"mese": k, **v} for k, v in sorted(mensile.items())], args.uscita / "enel_mensile.csv")
    scrivi_csv(gpl, args.uscita / "gpl_fatture.csv")
    print(f"{len(enel)} bollette luce, {len(mensile)} mesi, {len(gpl)} fatture GPL -> {args.uscita}")


if __name__ == "__main__":
    main()
