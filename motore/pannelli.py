"""Quanti moduli fotovoltaici stanno su una falda, e dove.

Il metodo (METODO.md, sezione 3 bis) in cinque passi:

1. LA FALDA NEL SUO PIANO. Il poligono è disegnato in pianta, ma il tetto
   è inclinato: lungo la pendenza è più lungo di quanto sembra dall'alto.
   Si passa a coordinate sul tetto: x lungo il colmo, y lungo la pendenza,
   con y allungata di 1/cos(inclinazione).
2. LA FASCIA LIBERA AI BORDI. Si restringe la falda di una fascia,
   misurata sul tetto, che può essere diversa per ogni lato: per esempio
   1 m sui bordi veri del tetto (gronda, colmo, lati liberi) e niente sul
   confine con la falda della casa accanto, se il tetto è uno solo.
3. GLI OSTACOLI. Comignoli, lucernari, antenne disegnati in pianta. Intorno
   a ciascuno si lascia libera una distanza misurata in proiezione
   orizzontale, come chiede la linea guida dei Vigili del fuoco per i tetti
   a falda. Per semplicità si lascia libero il rettangolo che contiene
   l'ostacolo allargato di quella distanza: è più prudente del necessario.
4. LE FILE DI MODULI. Le file corrono parallele al colmo. In ogni fila i
   moduli stanno dove la falda ristretta è larga abbastanza, per tutta
   l'altezza della fila. Si prova la prima fila a passi di 5 cm lungo la
   pendenza e si tiene la posizione che fa stare più moduli. Si provano i
   moduli tutti in verticale (lato lungo lungo la pendenza) o tutti in
   orizzontale.
5. IL RISULTATO. Numero di moduli, kWp e i rettangoli dei moduli in pianta,
   da disegnare sulla mappa.

Limiti dichiarati: la falda deve essere un poligono convesso (triangoli e
quadrilateri delle falde lo sono quasi sempre; se non lo è il calcolo si
ferma); niente file miste. Una differenza di pochi decimi di grado nella
direzione della falda può spostare il conto di un modulo.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

Punto = tuple[float, float]


@dataclass(frozen=True)
class Modulo:
    """Il modulo di riferimento, dalla sua scheda tecnica."""

    lunghezza_m: float
    larghezza_m: float
    potenza_wp: float


@dataclass(frozen=True)
class Disposizione:
    """Come stanno i moduli su una falda."""

    orientamento: str  # "verticale" (lato lungo lungo la pendenza) o "orizzontale"
    n_moduli: int
    kwp: float
    area_moduli_m2: float
    file: int  # numero di file con almeno un modulo
    rettangoli: tuple[tuple[Punto, ...], ...]  # i 4 vertici di ogni modulo, in pianta


# --- Geometria nel piano della falda ------------------------------------------------


class PianoFalda:
    """Passaggio fra coordinate in pianta (metri, x = est, y = nord) e coordinate sul tetto.

    Sul tetto: x lungo il colmo, y lungo la pendenza verso il basso, entrambe
    in metri veri. `azimut_pvgis` è la direzione verso cui guarda la falda
    (0 = sud, −90 = est, +90 = ovest).
    """

    def __init__(self, azimut_pvgis: float, inclinazione_deg: float):
        verso = math.radians(180.0 + azimut_pvgis)  # da bussola: 180 = sud
        self.v = (math.sin(verso), math.cos(verso))  # in discesa, in pianta
        self.u = (math.cos(verso), -math.sin(verso))  # lungo il colmo, in pianta
        self.cos_i = math.cos(math.radians(inclinazione_deg))

    def sul_tetto(self, p: Punto) -> Punto:
        return (p[0] * self.u[0] + p[1] * self.u[1], (p[0] * self.v[0] + p[1] * self.v[1]) / self.cos_i)

    def in_pianta(self, q: Punto) -> Punto:
        y_pianta = q[1] * self.cos_i
        return (q[0] * self.u[0] + y_pianta * self.v[0], q[0] * self.u[1] + y_pianta * self.v[1])


def _pulisci_con_lati(poligono: Sequence[Punto], fasce: Sequence[float]) -> tuple[list[Punto], list[float]]:
    """Come `_pulisci`, portandosi dietro un valore per lato (il lato i va dal vertice i al vertice i+1)."""
    punti = [tuple(p) for p in poligono]
    fasce = list(fasce)
    if len(punti) > 1 and math.dist(punti[0], punti[-1]) < 1e-9:
        punti.pop()
        fasce = fasce[: len(punti)]
    if len(fasce) != len(punti):
        raise ValueError(f"Servono {len(punti)} fasce, una per lato, non {len(fasce)}")
    # Un lato lungo zero si toglie insieme al vertice da cui parte.
    tenuti = [i for i in range(len(punti)) if math.dist(punti[i], punti[(i + 1) % len(punti)]) > 1e-9]
    punti, fasce = [punti[i] for i in tenuti], [fasce[i] for i in tenuti]
    area2 = sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(punti, punti[1:] + punti[:1]))
    if area2 > 0:
        return punti, fasce
    # Invertendo il giro, il lato j nuovo è il lato n-2-j vecchio percorso al contrario.
    n = len(punti)
    return punti[::-1], [fasce[(n - 2 - j) % n] for j in range(n)]


def _pulisci(poligono: Sequence[Punto]) -> list[Punto]:
    """Toglie il vertice di chiusura ripetuto e i vertici doppi, e mette i vertici in senso antiorario."""
    return _pulisci_con_lati(poligono, [0.0] * len(poligono))[0]


def _convesso(punti: list[Punto]) -> bool:
    """Vero se in senso antiorario si gira sempre a sinistra (vertici allineati ammessi)."""
    n = len(punti)
    for i in range(n):
        a, b, c = punti[i], punti[(i + 1) % n], punti[(i + 2) % n]
        if (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0]) < -1e-9:
            return False
    return True


def restringi(poligono: Sequence[Punto], fascia_m: float | Sequence[float]) -> list[Punto]:
    """Il poligono convesso ristretto di `fascia_m` (vuoto se non resta niente).

    `fascia_m` è un numero per tutti i lati o un elenco con un numero per
    lato. Ogni lato si sposta verso l'interno della sua fascia; la parte che
    resta è l'intersezione dei semipiani interni, ritagliata lato per lato.
    """
    fasce = [fascia_m] * len(poligono) if isinstance(fascia_m, (int, float)) else fascia_m
    punti, fasce = _pulisci_con_lati(poligono, fasce)
    risultato = list(punti)
    for a, b, fascia in zip(punti, punti[1:] + punti[:1], fasce):
        if fascia <= 0:
            continue
        lato = math.dist(a, b)
        n = (-(b[1] - a[1]) / lato, (b[0] - a[0]) / lato)  # normale verso l'interno (antiorario)
        dentro = lambda p: (p[0] - a[0]) * n[0] + (p[1] - a[1]) * n[1] - fascia  # noqa: E731
        nuovo = []
        for p, q in zip(risultato, risultato[1:] + risultato[:1]):
            dp, dq = dentro(p), dentro(q)
            if dp >= 0:
                nuovo.append(p)
            if (dp >= 0) != (dq >= 0):
                t = dp / (dp - dq)
                nuovo.append((p[0] + t * (q[0] - p[0]), p[1] + t * (q[1] - p[1])))
        risultato = nuovo
        if len(risultato) < 3:
            return []
    return risultato


def _larghezza_a(punti: list[Punto], y: float) -> tuple[float, float] | None:
    """Dove il poligono convesso taglia la retta orizzontale y: (x minima, x massima), o None."""
    eps = 1e-7  # un decimo di micron: tolleranza per gli arrotondamenti delle rotazioni
    xs = []
    for a, b in zip(punti, punti[1:] + punti[:1]):
        basso, alto = min(a[1], b[1]), max(a[1], b[1])
        if not basso - eps <= y <= alto + eps:
            continue
        if alto - basso <= eps:  # lato orizzontale proprio sulla retta: conta tutto
            xs += [a[0], b[0]]
        else:
            t = min(1.0, max(0.0, (y - a[1]) / (b[1] - a[1])))
            xs.append(a[0] + t * (b[0] - a[0]))
    return (min(xs), max(xs)) if xs else None


def _togli(intervallo: tuple[float, float], vietati: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Le parti di un intervallo che restano togliendo gli intervalli vietati."""
    liberi = [intervallo]
    for v0, v1 in vietati:
        nuovi = []
        for a, b in liberi:
            if v1 <= a or v0 >= b:
                nuovi.append((a, b))
                continue
            if v0 > a:
                nuovi.append((a, v0))
            if v1 < b:
                nuovi.append((v1, b))
        liberi = nuovi
    return liberi


# --- La disposizione --------------------------------------------------------------------


def _file_di_moduli(interno, ostacoli_tetto, larghezza, altezza, spazio, distanza_x, distanza_y, y_inizio):
    """Dispone le file dalla quota `y_inizio` in giù. Restituisce i rettangoli sul tetto."""
    rettangoli = []
    y_max = max(p[1] for p in interno)
    y0 = y_inizio
    while y0 + altezza <= y_max + 1e-9:
        sopra, sotto = _larghezza_a(interno, y0), _larghezza_a(interno, y0 + altezza)
        if sopra and sotto:
            # Falda convessa: dentro la fila la larghezza più stretta è a uno dei due bordi.
            x0, x1 = max(sopra[0], sotto[0]), min(sopra[1], sotto[1])
            vietati = [(ox0 - distanza_x, ox1 + distanza_x) for ox0, ox1, oy0, oy1 in ostacoli_tetto
                       if oy0 - distanza_y < y0 + altezza and oy1 + distanza_y > y0]
            for a, b in _togli((x0, x1), sorted(vietati)) if x1 > x0 else []:
                n = int((b - a + spazio) // (larghezza + spazio) + 1e-9)
                if n <= 0:
                    continue
                avanzo = (b - a) - (n * larghezza + (n - 1) * spazio)
                x = a + avanzo / 2  # la fila si centra nello spazio libero
                for _ in range(n):
                    rettangoli.append(((x, y0), (x + larghezza, y0), (x + larghezza, y0 + altezza), (x, y0 + altezza)))
                    x += larghezza + spazio
        y0 += altezza + spazio
    return rettangoli


def disponi(
    pianta: Sequence[Punto],
    azimut_pvgis: float,
    inclinazione_deg: float,
    modulo: Modulo,
    spazio_tra_moduli_m: float,
    fascia_bordo_m: float | Sequence[float],
    ostacoli: Sequence[Sequence[Punto]] = (),
    distanza_ostacoli_m: float = 0.0,
    passo_ricerca_m: float = 0.05,
) -> list[Disposizione]:
    """Le due disposizioni (moduli in verticale e in orizzontale), la migliore per prima.

    `pianta` e `ostacoli` sono poligoni in metri in un sistema proiettato
    (per esempio UTM); un ostacolo può essere anche un solo punto.
    `fascia_bordo_m` è un numero per tutti i lati o uno per lato, nell'ordine
    dei vertici di `pianta` (il lato i va dal vertice i al vertice i+1).
    """
    piano = PianoFalda(azimut_pvgis, inclinazione_deg)
    sul_tetto = _pulisci([piano.sul_tetto(p) for p in pianta])
    if not _convesso(sul_tetto):
        raise ValueError("La falda non è un poligono convesso: dividila in parti convesse")
    # La rotazione nel piano del tetto non cambia l'ordine dei lati: le fasce restano al loro posto.
    interno = restringi([piano.sul_tetto(p) for p in pianta], fascia_bordo_m)

    # Ostacoli: il rettangolo che li contiene, sul tetto. La distanza è in proiezione
    # orizzontale: lungo il colmo resta uguale, lungo la pendenza sul tetto diventa d / cos(i).
    ostacoli_tetto = []
    for ostacolo in ostacoli:
        q = [piano.sul_tetto(p) for p in ostacolo]
        ostacoli_tetto.append((min(p[0] for p in q), max(p[0] for p in q), min(p[1] for p in q), max(p[1] for p in q)))
    distanza_y = distanza_ostacoli_m / piano.cos_i

    risultati = []
    for orientamento, larghezza, altezza in (("verticale", modulo.larghezza_m, modulo.lunghezza_m),
                                              ("orizzontale", modulo.lunghezza_m, modulo.larghezza_m)):
        migliori: list = []
        if interno:
            y_min = min(p[1] for p in interno)
            passi = max(1, round((altezza + spazio_tra_moduli_m) / passo_ricerca_m))
            for k in range(passi):
                prova = _file_di_moduli(interno, ostacoli_tetto, larghezza, altezza, spazio_tra_moduli_m,
                                        distanza_ostacoli_m, distanza_y, y_min + k * passo_ricerca_m)
                if len(prova) > len(migliori):
                    migliori = prova
        n = len(migliori)
        risultati.append(Disposizione(
            orientamento=orientamento,
            n_moduli=n,
            kwp=n * modulo.potenza_wp / 1000.0,
            area_moduli_m2=n * modulo.lunghezza_m * modulo.larghezza_m,
            file=len({round(r[0][1], 6) for r in migliori}),
            rettangoli=tuple(tuple(piano.in_pianta(v) for v in r) for r in migliori),
        ))
    return sorted(risultati, key=lambda d: -d.n_moduli)
