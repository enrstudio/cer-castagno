"""Blocca i commit che contengono dati personali delle famiglie.

Il repository è pubblico, i dati delle famiglie no. Questo controllo cerca
nei file pronti per il commit (o in quelli indicati a riga di comando) le
tracce più comuni di dati personali:

- codici POD (IT001E seguito da cifre)
- codici fiscali
- indirizzi email
- numeri di cellulare italiani

Viene lanciato in automatico dal hook `.githooks/pre-commit` e dalla CI.
Se una riga contiene un falso positivo voluto (per esempio un esempio di
formato nella documentazione), si aggiunge in fondo alla riga il
commento `privacy: ok`.

Uso:
    python strumenti/controllo_privacy.py            # file in stage per il commit
    python strumenti/controllo_privacy.py --tutti    # tutti i file tracciati
    python strumenti/controllo_privacy.py file1 file2
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

CONTROLLI = {
    "codice POD": re.compile(r"\bIT\d{3}E\d{6,}\b"),
    "codice fiscale": re.compile(r"\b[A-Z]{6}\d{2}[A-EHLMPRST]\d{2}[A-Z]\d{3}[A-Z]\b"),
    "email": re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b"),
    "cellulare": re.compile(r"(?<![\d.,])(?:\+39[\s.]?)?3\d{2}[\s.]?\d{6,7}(?![\d.,])"),
}

# File che per natura contengono testo di terzi (la licenza) o che non vanno letti.
ESCLUSI = {"LICENSE"}
ESTENSIONI_BINARIE = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".gpkg", ".zip", ".gz", ".woff", ".woff2"}


def _file_in_stage() -> list[str]:
    uscita = subprocess.run(
        ["git", "diff", "--cached", "--name-only", "--diff-filter=ACM"], capture_output=True, text=True, check=True
    )
    return [r for r in uscita.stdout.splitlines() if r]


def _file_tracciati() -> list[str]:
    uscita = subprocess.run(["git", "ls-files"], capture_output=True, text=True, check=True)
    return [r for r in uscita.stdout.splitlines() if r]


def controlla(percorsi: list[str]) -> list[str]:
    """Restituisce un messaggio per ogni sospetto trovato."""
    problemi = []
    for percorso in percorsi:
        p = Path(percorso)
        if p.name in ESCLUSI or p.suffix.lower() in ESTENSIONI_BINARIE or not p.is_file():
            continue
        try:
            righe = p.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue  # file binario senza estensione nota
        for numero, riga in enumerate(righe, start=1):
            if "privacy: ok" in riga:
                continue
            for nome, regola in CONTROLLI.items():
                if regola.search(riga):
                    problemi.append(f"{percorso}:{numero}: possibile {nome}")
    return problemi


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("file", nargs="*", help="file da controllare (predefinito: quelli in stage)")
    parser.add_argument("--tutti", action="store_true", help="controlla tutti i file tracciati da git")
    args = parser.parse_args()

    percorsi = args.file or (_file_tracciati() if args.tutti else _file_in_stage())
    problemi = controlla(percorsi)
    if problemi:
        print("Possibili dati personali, commit bloccato:", file=sys.stderr)
        for p in problemi:
            print("  " + p, file=sys.stderr)
        print("Se è un falso positivo, aggiungi 'privacy: ok' in fondo alla riga.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
