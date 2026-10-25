"""Test del modulo produzione, senza rete: la risposta di PVGIS si finge dalla cache."""

import hashlib
import json

import pytest

from motore.produzione import azimut_da_bussola, stima_annua


@pytest.mark.parametrize(
    "bussola, pvgis",
    [(180, 0), (90, -90), (270, 90), (135, -45), (225, 45), (0, -180)],
)
def test_azimut_da_bussola(bussola, pvgis):
    assert azimut_da_bussola(bussola) == pytest.approx(pvgis)


def _risposta_finta(e_y=1180.0):
    """Una risposta PVcalc ridotta all'osso, con la stessa struttura di quella vera."""
    mesi = [{"month": m, "E_m": e_y / 12} for m in range(1, 13)]
    return {"outputs": {"totals": {"fixed": {"E_y": e_y, "SD_y": 40.0, "l_total": -17.5}},
                        "monthly": {"fixed": mesi}}}


def _metti_in_cache(cartella, parametri, risposta):
    # Stessa chiave che calcola produzione._chiama.
    parametri = {**parametri, "outputformat": "json", "browser": 0}
    chiave = hashlib.sha256(json.dumps(["PVcalc", parametri], sort_keys=True).encode()).hexdigest()[:20]
    (cartella / f"PVcalc_{chiave}.json").write_text(json.dumps(risposta), encoding="utf-8")


def test_stima_annua_legge_la_risposta(tmp_path):
    parametri = {"lat": 44.01318, "lon": 10.91511, "peakpower": 1, "loss": 14.0, "angle": 20.0,
                 "aspect": 24.0, "mountingplace": "building", "userhorizon": "5.0,3.0"}
    _metti_in_cache(tmp_path, parametri, _risposta_finta())
    stima = stima_annua(44.013184, 10.915112, 1, 20, 24, 0.14, orizzonte=[5, 3], cache=tmp_path)
    assert stima.kwh_anno == 1180.0
    assert len(stima.kwh_mese) == 12
    assert stima.perdite_totali == pytest.approx(0.175)
    assert stima.orizzonte_usato == "utente"
