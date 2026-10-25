"""Riscaldamento e acqua calda: dal GPL di oggi alla pompa di calore di domani.

Il ragionamento, in quattro passi (le formule sono in METODO.md, sezione 5):

1. QUANTO CALORE SERVE. Non lo misura nessuno, ma lo si ricava dal GPL:
   le letture effettive del contatore dicono quanti m³ sono stati bruciati
   fra due date. Una parte va in acqua calda e cucina, ed è più o meno la
   stessa ogni giorno (la "quota fissa"). Il resto va in riscaldamento ed è
   proporzionale ai GRADI GIORNO: per ogni giorno, quanti gradi la
   temperatura media esterna è stata sotto una soglia (la "temperatura
   base", sopra la quale non si accende). Si cerca il consumo per grado
   giorno che meglio spiega le letture.

2. QUANDO SERVE. Il calore di ogni giorno si distribuisce sulle sue ore in
   proporzione a quanto l'aria è più fredda della casa: di notte e
   all'alba di più, nel primo pomeriggio di meno.

3. QUANTA ELETTRICITÀ CONSUMA LA POMPA DI CALORE. Una pompa di calore aria-
   acqua "sposta" calore dall'aria esterna all'acqua dei termosifoni. Per
   ogni kWh elettrico rende COP kWh di calore, e il COP scende quando il
   salto di temperatura fra fuori e l'acqua di mandata cresce: col gelo e
   con termosifoni che vogliono acqua molto calda rende meno.

4. LE ALTERNATIVE. Una stufa a pellet o a legna può coprire una parte del
   riscaldamento; la pompa di calore fa il resto e l'acqua calda.

Unità: energia in kWh, potenze in kW, temperature in °C, GPL in m³.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, datetime, timedelta

# --- 1. Calibrazione sulle letture del contatore -------------------------------


@dataclass(frozen=True)
class Intervallo:
    """GPL consumato fra due letture EFFETTIVE (non stimate dal distributore).

    `dal` e `al` sono i giorni delle due letture: il consumo copre i giorni
    da `dal` compreso ad `al` escluso.
    """

    dal: date
    al: date
    m3: float

    @property
    def giorni(self) -> int:
        return (self.al - self.dal).days


def medie_giornaliere(temperature: dict[datetime, float]) -> dict[date, float]:
    """Temperatura media di ogni giorno. Si tengono solo i giorni con tutte le 24 ore."""
    per_giorno: dict[date, list[float]] = defaultdict(list)
    for ora, t in temperature.items():
        per_giorno[ora.date()].append(t)
    return {g: sum(v) / len(v) for g, v in per_giorno.items() if len(v) == 24}


def gradi_giorno(medie: dict[date, float], dal: date, al: date, t_base: float) -> float:
    """Somma, sui giorni da `dal` ad `al` escluso, di quanto la media sta sotto `t_base`."""
    totale = 0.0
    giorno = dal
    while giorno < al:
        if giorno not in medie:
            raise ValueError(f"Manca la temperatura del {giorno}: servono tutti i giorni dell'intervallo")
        totale += max(0.0, t_base - medie[giorno])
        giorno += timedelta(days=1)
    return totale


@dataclass(frozen=True)
class Calibrazione:
    """Il modello dei consumi di GPL di una casa, tarato sulle sue letture."""

    base_m3_giorno: float  # acqua calda e cucina: fissata in partenza, non stimata
    m3_per_grado_giorno: float  # riscaldamento: stimato dalle letture
    t_base: float  # sopra questa media giornaliera il riscaldamento resta spento
    scarto_m3: float  # errore quadratico medio sugli intervalli, in m³
    scarto_relativo: float  # lo stesso, diviso il consumo medio di un intervallo
    confronto: tuple[tuple[Intervallo, float], ...]  # (letto, previsto) per ogni intervallo

    def m3_previsti(self, medie: dict[date, float], dal: date, al: date) -> float:
        """GPL che il modello prevede fra due date."""
        return self.base_m3_giorno * (al - dal).days + self.m3_per_grado_giorno * gradi_giorno(
            medie, dal, al, self.t_base
        )


def _taratura(intervalli: Sequence[Intervallo], medie, base: float, t_base: float) -> Calibrazione:
    """Consumo per grado giorno con quota fissa e temperatura base date.

    È una retta per l'origine, (m³ letti − quota fissa) = k × gradi giorno,
    risolta con i minimi quadrati: k = Σ g·r / Σ g².
    """
    gg = [gradi_giorno(medie, iv.dal, iv.al, t_base) for iv in intervalli]
    resto = [iv.m3 - base * iv.giorni for iv in intervalli]
    somma_gg2 = sum(g * g for g in gg)
    if somma_gg2 == 0:
        raise ValueError("Negli intervalli non c'è nessun grado giorno: impossibile tarare il riscaldamento")
    k = max(0.0, sum(g * r for g, r in zip(gg, resto)) / somma_gg2)

    previsti = [base * iv.giorni + k * g for iv, g in zip(intervalli, gg)]
    scarto = (sum((p - iv.m3) ** 2 for p, iv in zip(previsti, intervalli)) / len(intervalli)) ** 0.5
    medio = sum(iv.m3 for iv in intervalli) / len(intervalli)
    return Calibrazione(
        base_m3_giorno=base,
        m3_per_grado_giorno=k,
        t_base=t_base,
        scarto_m3=scarto,
        scarto_relativo=scarto / medio,
        confronto=tuple(zip(intervalli, previsti)),
    )


def calibra(
    intervalli: Sequence[Intervallo],
    medie: dict[date, float],
    base_m3_giorno: float,
    t_base_min: float,
    t_base_max: float,
    passo: float = 0.5,
) -> Calibrazione:
    """Taratura completa: prova le temperature base nella forchetta e tiene la migliore.

    La quota fissa NON si stima dalle letture: con poche letture, tutte a
    cavallo di un inverno, quota fissa e riscaldamento si confondono (la
    stima arriva perfino a dare una quota fissa negativa). Si fissa quindi
    dalle persone in casa e dagli usi del gas, e dalle letture si ricavano
    il consumo per grado giorno e la temperatura base.
    """
    if len(intervalli) < 3:
        raise ValueError("Servono almeno 3 intervalli fra letture effettive")
    candidati = []
    t = t_base_min
    while t <= t_base_max + 1e-9:
        candidati.append(_taratura(intervalli, medie, base_m3_giorno, round(t, 2)))
        t += passo
    return min(candidati, key=lambda c: c.scarto_m3)


def quota_fissa_m3_giorno(
    persone: int, gas_per_acqua_calda: bool, gas_per_cucina: bool,
    acs_kwh_persona_giorno: float, cucina_m3_giorno: float, pci_gpl: float, rendimento_caldaia: float,
) -> float:
    """GPL bruciato ogni giorno indipendentemente dal freddo: acqua calda più cucina."""
    acs = persone * acs_kwh_persona_giorno / (pci_gpl * rendimento_caldaia) if gas_per_acqua_calda else 0.0
    return acs + (cucina_m3_giorno if gas_per_cucina else 0.0)


# --- 2. Domanda di calore ora per ora -------------------------------------------


@dataclass(frozen=True)
class OraDiCalore:
    """Il calore utile che la casa chiede in un'ora."""

    ora: datetime  # UTC
    t_esterna: float
    riscaldamento_kwh: float
    acqua_calda_kwh: float


def domanda_oraria(
    temperature: dict[datetime, float],
    calibrazione: Calibrazione,
    pci_gpl: float,
    rendimento_caldaia: float,
    acs_kwh_giorno: float,
    t_interna: float,
) -> list[OraDiCalore]:
    """Calore utile ora per ora, per tutti i giorni completi di `temperature`.

    Calore = GPL × PCI × rendimento: è l'energia che la caldaia mette davvero
    nei termosifoni, ed è quella che la pompa di calore dovrà fornire. Il
    calore di un giorno si divide fra le sue ore in proporzione a
    (t_interna − t_esterna). L'acqua calda si conta uguale in ogni ora:
    più avanti si potrà spostarla nelle ore di sole.
    """
    medie = medie_giornaliere(temperature)
    kwh_per_m3 = pci_gpl * rendimento_caldaia
    ore_per_giorno: dict[date, list[datetime]] = defaultdict(list)
    for ora in sorted(temperature):
        if ora.date() in medie:
            ore_per_giorno[ora.date()].append(ora)

    risultato = []
    for giorno, ore in ore_per_giorno.items():
        gg = max(0.0, calibrazione.t_base - medie[giorno])
        calore_giorno = calibrazione.m3_per_grado_giorno * gg * kwh_per_m3
        pesi = [max(0.0, t_interna - temperature[o]) for o in ore]
        somma = sum(pesi)
        if somma == 0:  # giornata tutta più calda della casa: non succede quando gg > 0
            pesi, somma = [1.0] * len(ore), float(len(ore))
        for o, p in zip(ore, pesi):
            risultato.append(OraDiCalore(o, temperature[o], calore_giorno * p / somma, acs_kwh_giorno / 24))
    return risultato


# --- 3. Pompa di calore ----------------------------------------------------------


def mandata_termosifoni(t_esterna: float, mandata_a_zero_gradi: float, pendenza: float) -> float:
    """Temperatura dell'acqua mandata ai termosifoni (curva climatica).

    Più fa freddo, più calda deve essere l'acqua: per esempio 40 °C con 0 °C
    fuori e 45 °C con −5 °C, se la pendenza è 1. Con il pavimento radiante
    bastano valori molto più bassi (30 °C, pendenza 0,5).
    """
    return mandata_a_zero_gradi - pendenza * t_esterna


def cop_aria_acqua(t_esterna: float, t_mandata: float, correzione: float) -> float:
    """COP di una pompa di calore aria-acqua, dalla regressione di Ruhnau e altri (2019).

    COP = 6,08 − 0,09·ΔT + 0,0005·ΔT², con ΔT = mandata − esterna, ricavata
    dalle schede tecniche di molti modelli in commercio (banca dati When2Heat).
    `correzione` (circa 0,85) tiene conto di sbrinamenti, accensioni e
    spegnimenti e di quanto le macchine vere rendono meno che in laboratorio.
    La formula viene da salti fra 15 e 80 °C: fuori da lì si ferma ai bordi
    (oltre i 90 °C la parabola tornerebbe a salire, che non ha senso fisico).
    Il COP non scende mai sotto 1, il rendimento di una resistenza elettrica.
    """
    salto = min(80.0, max(15.0, t_mandata - t_esterna))
    return max(1.0, (6.08 - 0.09 * salto + 0.0005 * salto**2) * correzione)


@dataclass(frozen=True)
class ParametriPdc:
    """Come è fatto l'impianto della casa, per calcolare il COP ora per ora."""

    mandata_a_zero_gradi: float
    pendenza_curva: float
    t_acqua_calda: float
    correzione_cop: float


@dataclass(frozen=True)
class Stufa:
    """Una stufa che copre una quota del riscaldamento degli ambienti."""

    nome: str
    quota: float  # frazione del calore per riscaldamento coperta dalla stufa (0 = nessuna stufa)
    pci_kwh_kg: float
    rendimento: float
    prezzo_eur_kg: float


@dataclass(frozen=True)
class AnnoSimulato:
    """Un anno di funzionamento con il clima di quell'anno."""

    anno: int
    calore_riscaldamento_kwh: float
    calore_acqua_calda_kwh: float
    elettricita_pdc_kwh: float
    combustibile_kg: float  # pellet o legna bruciati nella stufa
    scop: float  # calore fornito dalla pompa di calore / elettricità consumata
    picco_elettrico_kw: float  # l'ora in cui la pompa di calore assorbe di più
    picco_termico_kw: float  # l'ora in cui la casa chiede più calore
    t_minima: float
    elettricita_mese_kwh: tuple[float, ...]  # 12 valori, da gennaio a dicembre


def simula(domanda: Iterable[OraDiCalore], pdc: ParametriPdc, stufa: Stufa | None = None) -> list[AnnoSimulato]:
    """Pompa di calore (ed eventuale stufa) ora per ora, con i totali di ogni anno solare.

    La stufa copre la stessa quota del riscaldamento in ogni ora: è una
    semplificazione prudente, perché nella realtà si accende soprattutto
    nelle sere fredde, quando la pompa di calore renderebbe meno.
    """
    quota_stufa = stufa.quota if stufa else 0.0
    per_anno: dict[int, list[OraDiCalore]] = defaultdict(list)
    for h in domanda:
        per_anno[h.ora.year].append(h)

    risultati = []
    for anno, ore in sorted(per_anno.items()):
        calore_r = calore_a = el = calore_pdc = picco_el = picco_t = 0.0
        el_mese = [0.0] * 12
        for h in ore:
            risc_pdc = h.riscaldamento_kwh * (1.0 - quota_stufa)
            cop_r = cop_aria_acqua(h.t_esterna, mandata_termosifoni(h.t_esterna, pdc.mandata_a_zero_gradi,
                                                                    pdc.pendenza_curva), pdc.correzione_cop)
            cop_a = cop_aria_acqua(h.t_esterna, pdc.t_acqua_calda, pdc.correzione_cop)
            el_ora = risc_pdc / cop_r + h.acqua_calda_kwh / cop_a
            calore_r += h.riscaldamento_kwh
            calore_a += h.acqua_calda_kwh
            calore_pdc += risc_pdc + h.acqua_calda_kwh
            el += el_ora
            el_mese[h.ora.month - 1] += el_ora
            picco_el = max(picco_el, el_ora)  # kWh in un'ora = kW medi in quell'ora
            picco_t = max(picco_t, h.riscaldamento_kwh + h.acqua_calda_kwh)
        calore_stufa = calore_r * quota_stufa
        kg = calore_stufa / (stufa.pci_kwh_kg * stufa.rendimento) if stufa and quota_stufa > 0 else 0.0
        risultati.append(AnnoSimulato(
            anno=anno,
            calore_riscaldamento_kwh=calore_r,
            calore_acqua_calda_kwh=calore_a,
            elettricita_pdc_kwh=el,
            combustibile_kg=kg,
            scop=calore_pdc / el if el > 0 else 0.0,
            picco_elettrico_kw=picco_el,
            picco_termico_kw=picco_t,
            t_minima=min(h.t_esterna for h in ore),
            elettricita_mese_kwh=tuple(el_mese),
        ))
    return risultati


# --- 4. Cucina e spesa annua -------------------------------------------------------


def elettricita_induzione_kwh_anno(cucina_m3_giorno: float, pci_gpl: float,
                                   rendimento_fornelli_gas: float, rendimento_induzione: float) -> float:
    """kWh all'anno di un piano a induzione al posto dei fornelli a GPL.

    Il calore che arriva davvero nella pentola resta lo stesso; i fornelli a
    gas ne disperdono più della metà, l'induzione molto meno.
    """
    return cucina_m3_giorno * 365 * pci_gpl * rendimento_fornelli_gas / rendimento_induzione


def costo_potenza_in_piu(kw_prima: float, kw_dopo: float, quota_potenza_eur_kw_mese: float, iva: float) -> float:
    """Spesa fissa in più all'anno per un contatore più potente."""
    return max(0.0, kw_dopo - kw_prima) * quota_potenza_eur_kw_mese * 12 * (1 + iva)
