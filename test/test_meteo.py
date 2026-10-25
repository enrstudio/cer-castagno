"""Test del modulo meteo, senza rete: la risposta di Open-Meteo si finge dalla cache."""

import hashlib
import json
from datetime import date, datetime

from motore.meteo import temperature_orarie


def test_legge_un_anno_dalla_cache(tmp_path):
    parametri = {"latitude": 44.0132, "longitude": 10.9151, "elevation": 525, "start_date": "2020-01-01",
                 "end_date": "2020-12-31", "hourly": "temperature_2m", "timezone": "GMT"}
    # Stessa chiave che calcola meteo._scarica_anno.
    chiave = hashlib.sha256(json.dumps(parametri, sort_keys=True).encode()).hexdigest()[:20]
    risposta = {"hourly": {"time": ["2020-03-01T00:00", "2020-03-01T01:00", "2020-03-02T00:00"],
                           "temperature_2m": [4.5, None, 6.0]}}
    (tmp_path / f"temperature_2020_{chiave}.json").write_text(json.dumps(risposta), encoding="utf-8")

    t = temperature_orarie(44.01320, 10.91510, 525.2, date(2020, 3, 1), date(2020, 3, 1), cache=tmp_path)
    # L'ora mancante (None) e il giorno fuori intervallo restano fuori.
    assert t == {datetime(2020, 3, 1, 0): 4.5}
