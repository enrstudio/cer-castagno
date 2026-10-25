"""Motore di calcolo del progetto CER Castagno.

Ogni modulo fa una cosa sola e prende i parametri da `ipotesi.yaml`:

- ipotesi   lettura e controllo del registro delle ipotesi
- finanza   flussi di cassa, VAN, TIR, tempo di ritorno
- produzione  produzione fotovoltaica con PVGIS
- meteo     temperature orarie misurate (Open-Meteo, ERA5)
- calore    fabbisogno di calore dalle bollette GPL, pompa di calore, stufe

In arrivo: consumi, bilancio, comunita.
"""

__version__ = "0.1.0"
