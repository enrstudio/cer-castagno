"""Prepara il sito statico e lo pubblica su Cloudflare Pages.

Il sito pubblico nasce dai file in `sito/` (più, in futuro, le pagine
generate dal motore con dati aggregati) e finisce in `build/pubblico/`, che
è escluso da git. Le schede delle famiglie NON passano di qui: contengono
dati personali e andranno in un progetto Cloudflare separato, protetto da
Cloudflare Access (issue #10).

La pubblicazione usa `wrangler`, lo strumento di Cloudflare, tramite `npx`
(serve Node.js). La prima volta bisogna collegare il proprio account:

    npx wrangler login

Uso:
    python strumenti/pubblica_sito.py            # prepara build/pubblico/ e basta
    python strumenti/pubblica_sito.py --pubblica # prepara e pubblica
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path

RADICE = Path(__file__).resolve().parent.parent
SORGENTE = RADICE / "sito"
USCITA = RADICE / "build" / "pubblico"
PROGETTO_CLOUDFLARE = "cer-seccheto"  # diventa cer-seccheto.pages.dev
# Versione di wrangler fissata, così la pubblicazione non cambia da sola quando ne esce una nuova.
WRANGLER = "wrangler@4.149.0"  # nome@versione, non un indirizzo: privacy: ok


def prepara() -> None:
    """Copia il sito sorgente in build/pubblico/, tranne i file di servizio."""
    if USCITA.exists():
        shutil.rmtree(USCITA)
    shutil.copytree(SORGENTE, USCITA, ignore=shutil.ignore_patterns("README.md", "*.py", "__pycache__"))
    print(f"Sito pronto in {USCITA.relative_to(RADICE)}/")


def pubblica() -> None:
    subprocess.run(["npx", "--yes", WRANGLER, "pages", "deploy", str(USCITA),
                    "--project-name", PROGETTO_CLOUDFLARE, "--branch", "main"], check=True)


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepara e pubblica il sito statico.")
    parser.add_argument("--pubblica", action="store_true", help="pubblica su Cloudflare Pages dopo averlo preparato")
    args = parser.parse_args()
    prepara()
    if args.pubblica:
        pubblica()


if __name__ == "__main__":
    main()
