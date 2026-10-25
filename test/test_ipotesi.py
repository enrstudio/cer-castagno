"""Test del registro delle ipotesi: quello vero deve caricarsi, quelli rotti no."""

import textwrap

import pytest

from motore.ipotesi import ErroreIpotesi, carica_ipotesi


def test_registro_vero_si_carica():
    reg = carica_ipotesi()
    assert reg.versione
    assert reg.valore("tasso_sconto") == pytest.approx(0.03)
    assert reg.forchetta("tasso_sconto") == (0.02, 0.05)


def test_ripartizione_cer_somma_a_uno():
    # Le tre quote dell'incentivo devono dividersi tutto, non di più né di meno.
    reg = carica_ipotesi()
    somma = sum(reg.valore(k) for k in ("ripartizione_produttori", "ripartizione_consumatori", "ripartizione_fondo_comune"))
    assert somma == pytest.approx(1.0)


def test_valore_ignoto_ferma_il_calcolo():
    reg = carica_ipotesi()
    with pytest.raises(ErroreIpotesi, match="non è ancora noto"):
        reg.valore("detrazione_2027")


def test_forchetta_senza_min_max_usa_il_valore():
    reg = carica_ipotesi()
    v = reg.valore("quota_potenza")
    assert reg.forchetta("quota_potenza") == (v, v)


def test_chiave_inesistente():
    with pytest.raises(ErroreIpotesi, match="inesistente"):
        carica_ipotesi().valore("prezzo_della_luna")


def _scrivi(tmp_path, voce: str):
    p = tmp_path / "ipotesi.yaml"
    p.write_text("versione: 0.0.1\naggiornato: 2026-01-01\nipotesi:\n" + textwrap.indent(voce, "  "), encoding="utf-8")
    return p


VOCE_BUONA = """\
x:
  valore: 1.0
  min: 0.5
  max: 2.0
  unita: EUR
  descrizione: prova
  fonte: test
  stato: da_verificare
"""


def test_voce_buona(tmp_path):
    assert carica_ipotesi(_scrivi(tmp_path, VOCE_BUONA)).valore("x") == 1.0


def test_stato_sbagliato(tmp_path):
    with pytest.raises(ErroreIpotesi, match="stato"):
        carica_ipotesi(_scrivi(tmp_path, VOCE_BUONA.replace("da_verificare", "boh")))


def test_valore_fuori_forchetta(tmp_path):
    with pytest.raises(ErroreIpotesi, match="sopra il massimo"):
        carica_ipotesi(_scrivi(tmp_path, VOCE_BUONA.replace("valore: 1.0", "valore: 3.0")))


def test_campo_mancante(tmp_path):
    with pytest.raises(ErroreIpotesi, match="mancano"):
        carica_ipotesi(_scrivi(tmp_path, VOCE_BUONA.replace("  fonte: test\n", "")))


def test_campo_in_piu(tmp_path):
    with pytest.raises(ErroreIpotesi, match="non previsti"):
        carica_ipotesi(_scrivi(tmp_path, VOCE_BUONA + "  nota: refuso\n"))
