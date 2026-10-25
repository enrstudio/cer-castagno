"""Test del modulo finanza con casi di cui conosciamo già la risposta.

Il caso principale è il foglio di calcolo da cui è partito il progetto
("Preventivo metano.xlsx", scheda "Conv pannelli"): un fotovoltaico da
6 kW con batteria, valutato al 4% su 25 anni. I numeri attesi sono quelli
che il foglio stesso calcola.
"""

import pytest

from motore.finanza import (
    Investimento,
    fattore_annualita,
    fattore_sconto,
    rapporto_benefici_costi,
    tempo_ritorno,
    tir,
    valuta,
    van,
)

# Dal foglio: 13.000 € di impianto + 1.000 € di pratiche + 2.000 € di linea vita,
# 1.024,50 € l'anno di benefici (cella B4), 100 € l'anno di costi, 4% per 25 anni.
FOGLIO_AMICO = Investimento(investimento=16_000, beneficio_anno1=1024.496, costi_annui=100, durata=25)


def test_fattore_sconto():
    # 1.000 € fra 10 anni al 3% valgono oggi circa 744 € (esempio della guida).
    assert 1000 * fattore_sconto(0.03, 10) == pytest.approx(744.09, abs=0.01)
    assert fattore_sconto(0.05, 0) == 1.0


def test_fattore_annualita_come_nel_foglio():
    assert fattore_annualita(0.04, 25) == pytest.approx(15.6221, abs=1e-4)


def test_fattore_annualita_somma_dei_fattori_di_sconto():
    # La forma chiusa deve coincidere con la somma anno per anno.
    somma = sum(fattore_sconto(0.035, t) for t in range(1, 21))
    assert fattore_annualita(0.035, 20) == pytest.approx(somma)


def test_fattore_annualita_tasso_zero():
    assert fattore_annualita(0.0, 15) == 15.0


def test_foglio_amico_van_e_rapporto_bc():
    v = valuta(FOGLIO_AMICO, 0.04)
    assert v.van == pytest.approx(-1557.45, abs=0.01)  # cella B12 del foglio
    assert v.benefici_costi == pytest.approx(0.9113, abs=1e-4)  # cella B13


def test_foglio_amico_tir_sotto_il_tasso():
    # VAN negativo al 4% vuol dire TIR sotto il 4%; e al TIR il VAN è zero.
    flussi = FOGLIO_AMICO.flussi()
    r = tir(flussi)
    assert r is not None and r < 0.04
    assert van(flussi, r) == pytest.approx(0.0, abs=1e-4)


def test_tempo_ritorno_semplice():
    # 1.000 € investiti, 300 € l'anno: si rientra dopo 3,33 anni.
    assert tempo_ritorno([-1000, 300, 300, 300, 300, 300]) == pytest.approx(10 / 3)


def test_tempo_ritorno_attualizzato_piu_lungo():
    flussi = [-1000] + [300] * 10
    semplice = tempo_ritorno(flussi)
    attualizzato = tempo_ritorno(flussi, 0.05)
    assert attualizzato > semplice


def test_tempo_ritorno_mai():
    assert tempo_ritorno([-1000, 100, 100]) is None


def test_tir_negativo_se_non_si_ripaga():
    # Si rientra di 20 € su 1.000: il TIR esiste ma è negativo, si perdono soldi.
    assert tir([-1000, 10, 10]) < 0


def test_tir_assente_senza_esborso():
    # Senza un esborso il VAN è sempre positivo e nessun tasso lo porta a zero.
    assert tir([100, 10, 10]) is None


def test_rapporto_bc_senza_costi():
    assert rapporto_benefici_costi([0, 100], [0, 0], 0.03) is None


def test_detrazione_in_dieci_rate():
    inv = Investimento(investimento=10_000, beneficio_anno1=0, durata=12, detrazione=0.5)
    benefici = inv.benefici()
    assert benefici[1:11] == [500.0] * 10  # 50% di 10.000 € in 10 rate
    assert benefici[11] == 0.0  # finite le rate


def test_variazione_prezzi_e_degrado():
    inv = Investimento(investimento=0, beneficio_anno1=1000, durata=3, variazione_prezzi=0.02, degrado=0.005)
    b = inv.benefici()
    assert b[1] == pytest.approx(1000)  # l'anno 1 è il valore di partenza
    assert b[2] == pytest.approx(1000 * 1.02 * 0.995)
    assert b[3] == pytest.approx(1000 * 1.02**2 * 0.995**2)


def test_ricambi_e_contributo():
    inv = Investimento(
        investimento=8000, contributo_iniziale=3000, beneficio_anno1=900, costi_annui=50, durata=15, ricambi={8: 1200}
    )
    costi = inv.costi()
    assert costi[0] == 5000  # investimento al netto del contributo
    assert costi[8] == 1250  # costi annui + inverter
    assert len(inv.flussi()) == 16  # anno 0 + 15 anni
