"""Test del modulo pannelli: falde costruite a mano, di cui si contano i moduli a mente."""

import math

import pytest

from motore.pannelli import Modulo, PianoFalda, disponi, restringi

# Modulo finto da 1 × 2 m e 400 W, per contare a mente.
M = Modulo(lunghezza_m=2.0, larghezza_m=1.0, potenza_wp=400)


def _rettangolo(larghezza_est, profondita_nord):
    return [(0, 0), (larghezza_est, 0), (larghezza_est, profondita_nord), (0, profondita_nord)]


def test_piano_andata_e_ritorno():
    piano = PianoFalda(azimut_pvgis=24, inclinazione_deg=30)
    p = (653510.2, 4875120.7)
    assert piano.in_pianta(piano.sul_tetto(p)) == pytest.approx(p)


def test_falda_piana_conta_le_file():
    # 10 m da est a ovest, 5 m da nord a sud. In orizzontale (2 m lungo il colmo, 1 m lungo
    # la pendenza): 5 file da 5 moduli. In verticale: 2 file da 10.
    migliore, altra = disponi(_rettangolo(10, 5), 0, 0, M, 0.0, 0.0)
    assert (migliore.orientamento, migliore.n_moduli, migliore.file) == ("orizzontale", 25, 5)
    assert (altra.orientamento, altra.n_moduli) == ("verticale", 20)
    assert migliore.kwp == pytest.approx(10.0)
    assert migliore.area_moduli_m2 == pytest.approx(50.0)


def test_la_pendenza_allunga_la_falda():
    # 4 m in pianta con 60° di inclinazione sono 8 m sul tetto: 4 file di moduli in verticale.
    verticale = next(d for d in disponi(_rettangolo(10, 4), 0, 60, M, 0.0, 0.0) if d.orientamento == "verticale")
    assert verticale.n_moduli == 40


def test_fascia_ai_bordi_e_spazio_fra_moduli():
    # Con 1 m libero su ogni lato restano 8 × 3 m.
    migliore = disponi(_rettangolo(10, 5), 0, 0, M, 0.0, 1.0)[0]
    assert (migliore.orientamento, migliore.n_moduli) == ("orizzontale", 12)
    # Con 2 cm fra i moduli: in orizzontale 3 moduli da 2 m per fila (non 4) e 2 file in 3 m
    # (non 3), cioè 6; in verticale 7 moduli da 1 m in una fila da 2 m. Vince il verticale.
    migliore = disponi(_rettangolo(10, 5), 0, 0, M, 0.02, 1.0)[0]
    assert (migliore.orientamento, migliore.n_moduli) == ("verticale", 7)


def test_fascia_diversa_per_lato():
    # Fascia di 1 m su tutti i lati tranne il lato est (dal vertice 1 al 2), lasciato a zero:
    # restano 9 × 3 m, cioè 4 moduli in orizzontale per 3 file.
    migliore = disponi(_rettangolo(10, 5), 0, 0, M, 0.0, [1.0, 0.0, 1.0, 1.0])[0]
    assert (migliore.orientamento, migliore.n_moduli) == ("orizzontale", 12)
    assert max(v[0] for r in migliore.rettangoli for v in r) == pytest.approx(10.0 - 0.5)  # centrati in 9 m
    # Lo stesso con i vertici in senso orario: le fasce seguono i loro lati.
    orario = [(0, 0), (0, 5), (10, 5), (10, 0)]  # ora il lato est va dal vertice 2 al 3
    assert disponi(orario, 0, 0, M, 0.0, [1.0, 1.0, 0.0, 1.0])[0].rettangoli == migliore.rettangoli


def test_ostacolo_toglie_moduli_intorno():
    # Un comignolo puntiforme al centro, con 1 m di rispetto: nelle file che tocca,
    # restano libere solo le parti a più di 1 m dal comignolo.
    senza = disponi(_rettangolo(10, 5), 0, 0, M, 0.0, 0.0)[0].n_moduli
    con = disponi(_rettangolo(10, 5), 0, 0, M, 0.0, 0.0, ostacoli=[[(5.0, 2.5)]], distanza_ostacoli_m=1.0)[0]
    assert con.n_moduli < senza
    for r in con.rettangoli:
        xs, ys = [v[0] for v in r], [v[1] for v in r]
        lontano_x = max(xs) <= 4.0 + 1e-9 or min(xs) >= 6.0 - 1e-9
        lontano_y = max(ys) <= 1.5 + 1e-9 or min(ys) >= 3.5 - 1e-9
        assert lontano_x or lontano_y


def test_moduli_dentro_la_falda_triangolare():
    triangolo = [(0, 0), (8, 0), (4, 6)]
    migliore = disponi(triangolo, 0, 20, M, 0.02, 0.3)[0]
    assert migliore.n_moduli > 0
    interno = restringi(triangolo, 0.3 * math.cos(math.radians(20)))  # in pianta la fascia si accorcia
    for r in migliore.rettangoli:
        for v in r:
            # Ogni vertice sta dentro la falda (con una tolleranza per gli arrotondamenti).
            assert all((b[0] - a[0]) * (v[1] - a[1]) - (b[1] - a[1]) * (v[0] - a[0]) >= -1e-6
                       for a, b in zip(triangolo, triangolo[1:] + triangolo[:1]))
    assert interno


def test_falda_non_convessa_si_ferma():
    a_elle = [(0, 0), (6, 0), (6, 2), (2, 2), (2, 6), (0, 6)]
    with pytest.raises(ValueError, match="convesso"):
        disponi(a_elle, 0, 0, M, 0.0, 0.0)


def test_fascia_troppo_larga_niente_moduli():
    assert disponi(_rettangolo(3, 3), 0, 0, M, 0.0, 1.5)[0].n_moduli == 0
