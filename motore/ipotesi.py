"""Lettura e controllo del registro delle ipotesi (`ipotesi.yaml`).

Il registro è l'unica fonte dei parametri del motore. Questo modulo lo
carica, controlla che ogni voce sia scritta bene e offre due modi per
leggerla: il valore dello scenario di base e la forchetta min-max usata
nelle analisi di sensibilità.

I controlli sono severi di proposito: un errore di battitura nel registro
(uno stato scritto male, un valore fuori dalla sua forchetta) deve fermare
il calcolo, non produrre in silenzio un numero sbagliato da portare in
assemblea.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

import yaml

# Il registro sta nella radice del repository, una cartella sopra `motore/`.
PERCORSO_PREDEFINITO = Path(__file__).resolve().parent.parent / "ipotesi.yaml"

STATI_AMMESSI = {"dalle_bollette", "da_verificare", "decide_il_gruppo", "da_calcolare"}
CAMPI_OBBLIGATORI = {"valore", "min", "max", "unita", "descrizione", "fonte", "stato"}


class ErroreIpotesi(ValueError):
    """Il registro contiene una voce scritta male o una chiave inesistente."""


@dataclass(frozen=True)
class Ipotesi:
    """Una voce del registro, già controllata."""

    chiave: str
    valore: Any  # numero, data o None quando il valore non è ancora noto
    min: float | None
    max: float | None
    unita: str
    descrizione: str
    fonte: str
    stato: str


class Registro:
    """L'insieme delle ipotesi, con la versione del registro da cui vengono.

    La versione va salvata accanto a ogni risultato: se fra sei mesi un
    numero cambia, si deve poter dire se è cambiato il registro o il motore.
    """

    def __init__(self, versione: str, aggiornato: date, voci: dict[str, Ipotesi]):
        self.versione = versione
        self.aggiornato = aggiornato
        self._voci = voci

    def __contains__(self, chiave: str) -> bool:
        return chiave in self._voci

    def __iter__(self):
        return iter(self._voci.values())

    def voce(self, chiave: str) -> Ipotesi:
        """La voce completa, con fonte e stato."""
        try:
            return self._voci[chiave]
        except KeyError:
            raise ErroreIpotesi(f"Ipotesi inesistente nel registro: {chiave!r}") from None

    def valore(self, chiave: str) -> Any:
        """Il valore dello scenario di base.

        Se il valore è ancora ignoto (null nel registro) si ferma con un
        errore: meglio un calcolo che non parte che uno che usa uno zero
        al posto di un dato mancante.
        """
        v = self.voce(chiave).valore
        if v is None:
            raise ErroreIpotesi(f"Il valore di {chiave!r} non è ancora noto nel registro")
        return v

    def forchetta(self, chiave: str) -> tuple[float, float]:
        """Il minimo e il massimo plausibili, per le analisi di sensibilità.

        Se la voce non ha forchetta, minimo e massimo coincidono col valore:
        il parametro si considera certo.
        """
        ip = self.voce(chiave)
        basso = ip.min if ip.min is not None else self.valore(chiave)
        alto = ip.max if ip.max is not None else self.valore(chiave)
        return basso, alto


def _controlla_voce(chiave: str, grezza: Any) -> Ipotesi:
    """Trasforma una voce letta dal YAML in `Ipotesi`, controllandola."""
    if not isinstance(grezza, dict):
        raise ErroreIpotesi(f"{chiave}: la voce deve essere un elenco di campi")

    mancanti = CAMPI_OBBLIGATORI - grezza.keys()
    if mancanti:
        raise ErroreIpotesi(f"{chiave}: mancano i campi {sorted(mancanti)}")
    estranei = grezza.keys() - CAMPI_OBBLIGATORI
    if estranei:
        # Un campo in più è quasi sempre un errore di battitura ("unità", "fonti"...).
        raise ErroreIpotesi(f"{chiave}: campi non previsti {sorted(estranei)}")

    if grezza["stato"] not in STATI_AMMESSI:
        raise ErroreIpotesi(f"{chiave}: stato {grezza['stato']!r} non ammesso, usa uno di {sorted(STATI_AMMESSI)}")

    valore, basso, alto = grezza["valore"], grezza["min"], grezza["max"]
    if basso is not None and alto is not None and basso > alto:
        raise ErroreIpotesi(f"{chiave}: min ({basso}) maggiore di max ({alto})")
    # Il controllo valore/forchetta ha senso solo per i numeri (non per le date).
    if isinstance(valore, (int, float)) and not isinstance(valore, bool):
        if basso is not None and valore < basso:
            raise ErroreIpotesi(f"{chiave}: valore {valore} sotto il minimo {basso}")
        if alto is not None and valore > alto:
            raise ErroreIpotesi(f"{chiave}: valore {valore} sopra il massimo {alto}")

    return Ipotesi(chiave=chiave, **grezza)


def carica_ipotesi(percorso: str | Path = PERCORSO_PREDEFINITO) -> Registro:
    """Legge `ipotesi.yaml` e restituisce il registro controllato."""
    with open(percorso, encoding="utf-8") as f:
        dati = yaml.safe_load(f)

    for campo in ("versione", "aggiornato", "ipotesi"):
        if campo not in dati:
            raise ErroreIpotesi(f"Nel registro manca il campo {campo!r}")

    voci = {chiave: _controlla_voce(chiave, grezza) for chiave, grezza in dati["ipotesi"].items()}
    return Registro(versione=str(dati["versione"]), aggiornato=dati["aggiornato"], voci=voci)
