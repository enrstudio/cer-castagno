"""Conti di un investimento energetico: flussi di cassa, VAN, TIR, tempo di ritorno.

Le idee sono le stesse della guida "Conti dell'energia Seccheto" e di
METODO.md. In breve:

- Un investimento si descrive con una riga di FLUSSI DI CASSA, uno per anno.
  L'anno 0 è l'esborso iniziale (negativo); dall'anno 1 in poi ci sono
  benefici (bolletta evitata, energia venduta, incentivi) meno costi.
- Un euro fra t anni vale oggi 1 / (1 + i)^t, dove i è il tasso di sconto:
  il rendimento della migliore alternativa ai propri soldi.
- VAN (valore attuale netto) = somma dei flussi riportati a oggi.
  Se è maggiore di zero l'investimento rende più dell'alternativa.
- TIR (tasso interno di rendimento) = il tasso che porta il VAN a zero.
- Tempo di ritorno = l'anno in cui la somma dei flussi torna a zero.

Ogni conto si fa sempre RISPETTO A UN'ALTERNATIVA: i benefici sono la
differenza di spesa fra "faccio l'investimento" e "faccio l'altra cosa"
(per esempio: pompa di calore contro un nuovo impianto a GPL).

Tutti gli importi sono in euro, IVA inclusa. Tassi e quote sono frazioni
(3% = 0.03), mai percentuali, per non confondere 3 con 0.03.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

# --- Le formule di base --------------------------------------------------------


def fattore_sconto(tasso: float, anno: int) -> float:
    """Quanto vale oggi 1 € ricevuto fra `anno` anni: 1 / (1 + tasso)^anno."""
    return 1.0 / (1.0 + tasso) ** anno


def fattore_annualita(tasso: float, anni: int) -> float:
    """Quanto vale oggi 1 € ricevuto ogni anno, per `anni` anni.

    È la somma dei fattori di sconto degli anni da 1 a `anni`, che ha la
    forma chiusa (q^n - 1) / (i * q^n) con q = 1 + i: la stessa formula
    usata nel foglio di calcolo da cui è partito il progetto.
    Con tasso zero la somma è semplicemente il numero di anni.
    """
    if tasso == 0:
        return float(anni)
    q = 1.0 + tasso
    return (q**anni - 1.0) / (tasso * q**anni)


def van(flussi: Sequence[float], tasso: float) -> float:
    """Valore attuale netto: somma dei flussi, ognuno scontato al suo anno.

    `flussi[0]` è l'anno 0 (oggi, non scontato), `flussi[1]` l'anno 1 e così via.
    """
    return sum(flusso * fattore_sconto(tasso, anno) for anno, flusso in enumerate(flussi))


def tir(flussi: Sequence[float], tolleranza: float = 1e-9) -> float | None:
    """Tasso interno di rendimento: il tasso al quale il VAN vale zero.

    Non esiste una formula diretta, quindi si cerca per bisezione fra -99%
    e +100%: si dimezza l'intervallo finché il VAN cambia di segno al suo
    interno. Un investimento che non rientra dei soldi ha un TIR negativo:
    dice quanto si perde all'anno. Restituisce None se il VAN non cambia
    mai segno nell'intervallo, per esempio quando non c'è alcun esborso.

    Nota: con flussi che cambiano segno più volte (per esempio una batteria
    da ricomprare a metà vita) possono esistere più TIR. Qui si trova quello
    nell'intervallo indicato; per decidere fa fede il VAN.
    """
    basso, alto = -0.99, 1.0
    van_basso = van(flussi, basso)
    if van_basso * van(flussi, alto) > 0:
        return None
    while alto - basso > tolleranza:
        medio = (basso + alto) / 2.0
        van_medio = van(flussi, medio)
        if van_medio * van_basso > 0:
            basso, van_basso = medio, van_medio
        else:
            alto = medio
    return (basso + alto) / 2.0


def tempo_ritorno(flussi: Sequence[float], tasso: float = 0.0) -> float | None:
    """Anni necessari perché la somma dei flussi torni a zero.

    Con `tasso` = 0 è il tempo di ritorno semplice; con il tasso di sconto
    è quello attualizzato, sempre un po' più lungo. Dentro l'anno in cui
    si passa lo zero si interpola in modo lineare, quindi il risultato può
    essere 7,4 anni e non solo 7 o 8. None se non si rientra mai.
    """
    cumulato = 0.0
    for anno, flusso in enumerate(flussi):
        attualizzato = flusso * fattore_sconto(tasso, anno)
        precedente = cumulato
        cumulato += attualizzato
        if anno > 0 and precedente < 0 <= cumulato:
            return anno - 1 + (-precedente / attualizzato)
    return None


def rapporto_benefici_costi(benefici: Sequence[float], costi: Sequence[float], tasso: float) -> float | None:
    """Valore attuale dei benefici diviso valore attuale dei costi.

    I costi comprendono l'investimento all'anno 0. Sopra 1 l'investimento
    conviene. None se non ci sono costi (rapporto non definito).
    """
    va_costi = van(costi, tasso)
    if va_costi == 0:
        return None
    return van(benefici, tasso) / va_costi


# --- Un investimento descritto per intero ------------------------------------------


@dataclass
class Investimento:
    """Tutto quello che serve per costruire i flussi di cassa anno per anno.

    I benefici dell'anno 1 crescono (o calano) con i prezzi dell'energia e
    calano con il degrado dell'impianto. La detrazione fiscale torna in rate
    annuali uguali a partire dall'anno 1. I ricambi sono spese puntuali,
    indicate per anno (per esempio {12: 1200} per un inverter all'anno 12).
    """

    investimento: float  # EUR all'anno 0, chiavi in mano
    beneficio_anno1: float  # EUR/anno: bolletta evitata + energia venduta + incentivi
    durata: int  # anni di vita utile
    costi_annui: float = 0.0  # EUR/anno: manutenzione, assicurazione
    contributo_iniziale: float = 0.0  # EUR incassati subito (es. Conto Termico)
    detrazione: float = 0.0  # quota dell'investimento detratta (0.5 = 50%)
    anni_detrazione: int = 10
    variazione_prezzi: float = 0.0  # frazione/anno applicata ai benefici
    degrado: float = 0.0  # frazione/anno di calo dei benefici (pannelli)
    ricambi: dict[int, float] = field(default_factory=dict)  # anno -> EUR

    def benefici(self) -> list[float]:
        """Benefici anno per anno, anno 0 compreso (vale zero)."""
        righe = [0.0]
        quota_detrazione = self.investimento * self.detrazione / self.anni_detrazione
        for anno in range(1, self.durata + 1):
            # All'anno 1 il fattore vale 1: le variazioni partono dall'anno 2.
            fattore = (1 + self.variazione_prezzi) ** (anno - 1) * (1 - self.degrado) ** (anno - 1)
            riga = self.beneficio_anno1 * fattore
            if anno <= self.anni_detrazione:
                riga += quota_detrazione
            righe.append(riga)
        return righe

    def costi(self) -> list[float]:
        """Costi anno per anno; l'anno 0 è l'investimento al netto del contributo."""
        righe = [self.investimento - self.contributo_iniziale]
        for anno in range(1, self.durata + 1):
            righe.append(self.costi_annui + self.ricambi.get(anno, 0.0))
        return righe

    def flussi(self) -> list[float]:
        """Flussi di cassa netti: benefici meno costi, anno per anno."""
        return [b - c for b, c in zip(self.benefici(), self.costi())]


@dataclass(frozen=True)
class Valutazione:
    """I numeri che servono per decidere, calcolati a un certo tasso di sconto."""

    tasso: float
    van: float
    tir: float | None
    ritorno_semplice: float | None
    ritorno_attualizzato: float | None
    benefici_costi: float | None


def valuta(inv: Investimento, tasso: float) -> Valutazione:
    """Calcola VAN, TIR, tempi di ritorno e rapporto B/C di un investimento."""
    flussi = inv.flussi()
    return Valutazione(
        tasso=tasso,
        van=van(flussi, tasso),
        tir=tir(flussi),
        ritorno_semplice=tempo_ritorno(flussi),
        ritorno_attualizzato=tempo_ritorno(flussi, tasso),
        benefici_costi=rapporto_benefici_costi(inv.benefici(), inv.costi(), tasso),
    )
