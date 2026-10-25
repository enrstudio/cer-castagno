"""Test del modulo calore: casi costruiti a mano, di cui si conosce la risposta giusta."""

import math
from datetime import date, datetime, timedelta

import pytest

from motore.calore import (
    Intervallo, OraDiCalore, ParametriPdc, Stufa, calibra, cop_aria_acqua, costo_potenza_in_piu,
    domanda_oraria, elettricita_induzione_kwh_anno, gradi_giorno, mandata_termosifoni,
    medie_giornaliere, quota_fissa_m3_giorno, simula,
)


def _clima_finto(dal: date, giorni: int) -> dict[datetime, float]:
    """Temperature orarie con un'onda annua (5 °C a gennaio, 21 °C a luglio) e una giornaliera di ±4 °C."""
    temperature = {}
    for g in range(giorni):
        giorno = dal + timedelta(days=g)
        media = 13 - 8 * math.cos(2 * math.pi * (giorno.timetuple().tm_yday - 15) / 365)
        for h in range(24):
            temperature[datetime(giorno.year, giorno.month, giorno.day, h)] = media + 4 * math.sin(
                2 * math.pi * (h - 9) / 24)
    return temperature


def test_gradi_giorno():
    medie = {date(2025, 1, 1): 10.0, date(2025, 1, 2): 18.0, date(2025, 1, 3): 4.0}
    # Il 3 gennaio è escluso: l'intervallo arriva al giorno della lettura senza contarlo.
    assert gradi_giorno(medie, date(2025, 1, 1), date(2025, 1, 3), 16) == pytest.approx(6.0)
    with pytest.raises(ValueError, match="Manca la temperatura"):
        gradi_giorno(medie, date(2025, 1, 1), date(2025, 1, 5), 16)


def test_medie_giornaliere_scarta_i_giorni_incompleti():
    temperature = {datetime(2025, 1, 1, h): float(h) for h in range(24)}
    temperature[datetime(2025, 1, 2, 0)] = 5.0
    assert medie_giornaliere(temperature) == {date(2025, 1, 1): pytest.approx(11.5)}


def test_calibra_ritrova_il_modello_che_ha_generato_le_letture():
    medie = medie_giornaliere(_clima_finto(date(2023, 1, 1), 3 * 365))
    date_letture = [date(2023, 1, 1), date(2023, 4, 30), date(2023, 12, 20), date(2024, 4, 25),
                    date(2024, 12, 22), date(2025, 4, 24), date(2025, 12, 20)]
    intervalli = [Intervallo(a, b, 0.15 * (b - a).days + 0.25 * gradi_giorno(medie, a, b, 15.0))
                  for a, b in zip(date_letture, date_letture[1:])]
    cal = calibra(intervalli, medie, base_m3_giorno=0.15, t_base_min=12, t_base_max=20)
    assert cal.t_base == pytest.approx(15.0)
    assert cal.m3_per_grado_giorno == pytest.approx(0.25)
    assert cal.scarto_m3 == pytest.approx(0.0, abs=1e-9)


def test_quota_fissa():
    # 2 persone × 1,6 kWh / (24 kWh/m³ × 0,9) = 0,148 m³ di acqua calda, più 0,06 di cucina.
    assert quota_fissa_m3_giorno(2, True, True, 1.6, 0.06, 24, 0.9) == pytest.approx(3.2 / 21.6 + 0.06)
    assert quota_fissa_m3_giorno(2, False, False, 1.6, 0.06, 24, 0.9) == 0.0


def test_domanda_oraria_conserva_il_calore_di_ogni_giorno():
    temperature = _clima_finto(date(2025, 1, 1), 3)
    medie = medie_giornaliere(temperature)
    cal = calibra([Intervallo(date(2025, 1, 1), date(2025, 1, 2), 3.0)] * 3, medie, 0.0, 15, 15)
    ore = domanda_oraria(temperature, cal, pci_gpl=24, rendimento_caldaia=0.9, acs_kwh_giorno=4.8, t_interna=20)
    primo = [h for h in ore if h.ora.date() == date(2025, 1, 1)]
    atteso = cal.m3_per_grado_giorno * (15 - medie[date(2025, 1, 1)]) * 24 * 0.9
    assert sum(h.riscaldamento_kwh for h in primo) == pytest.approx(atteso)
    assert sum(h.acqua_calda_kwh for h in primo) == pytest.approx(4.8)
    # L'ora più fredda (alle 3) chiede più calore dell'ora più calda (alle 15).
    assert primo[3].riscaldamento_kwh > primo[15].riscaldamento_kwh


def test_cop():
    # ΔT = 40: 6,08 − 3,6 + 0,8 = 3,28, per la correzione 0,85.
    assert cop_aria_acqua(0, 40, 0.85) == pytest.approx(3.28 * 0.85)
    assert cop_aria_acqua(-5, 45, 0.85) < cop_aria_acqua(5, 35, 0.85)  # col freddo rende meno
    assert cop_aria_acqua(-60, 80, 0.85) == cop_aria_acqua(-30, 50, 0.85)  # oltre 80 °C di salto si ferma
    assert cop_aria_acqua(-30, 50, 0.3) == 1.0  # mai sotto una resistenza elettrica
    assert cop_aria_acqua(30, 35, 1.0) == cop_aria_acqua(20, 35, 1.0)  # sotto 15 °C di salto si ferma
    assert mandata_termosifoni(-5, 40, 1.0) == 45


def _ore(n, t, risc, acs):
    return [OraDiCalore(datetime(2025, 1, 1) + timedelta(hours=i), t, risc, acs) for i in range(n)]


def test_simula_solo_pompa_di_calore():
    pdc = ParametriPdc(mandata_a_zero_gradi=40, pendenza_curva=1.0, t_acqua_calda=50, correzione_cop=0.85)
    (anno,) = simula(_ore(10, 0.0, 2.0, 0.5), pdc)
    cop_r, cop_a = cop_aria_acqua(0, 40, 0.85), cop_aria_acqua(0, 50, 0.85)
    assert anno.elettricita_pdc_kwh == pytest.approx(10 * (2.0 / cop_r + 0.5 / cop_a))
    assert anno.scop == pytest.approx(25 / anno.elettricita_pdc_kwh)
    assert anno.picco_termico_kw == pytest.approx(2.5)
    assert anno.combustibile_kg == 0.0
    assert sum(anno.elettricita_mese_kwh) == pytest.approx(anno.elettricita_pdc_kwh)


def test_simula_con_stufa():
    pdc = ParametriPdc(40, 1.0, 50, 0.85)
    tutta_stufa = Stufa("legna", quota=1.0, pci_kwh_kg=4.0, rendimento=0.75, prezzo_eur_kg=0.18)
    (anno,) = simula(_ore(10, 0.0, 3.0, 0.0), pdc, tutta_stufa)
    assert anno.elettricita_pdc_kwh == 0.0
    assert anno.combustibile_kg == pytest.approx(30 / (4.0 * 0.75))


def test_cucina_e_contatore():
    # 0,06 m³/giorno × 365 × 24 kWh/m³ × 0,40 / 0,85
    assert elettricita_induzione_kwh_anno(0.06, 24, 0.40, 0.85) == pytest.approx(0.06 * 365 * 24 * 0.40 / 0.85)
    assert costo_potenza_in_piu(3, 6, 1.91, 0.10) == pytest.approx(3 * 1.91 * 12 * 1.1)
    assert costo_potenza_in_piu(6, 3, 1.91, 0.10) == 0.0
