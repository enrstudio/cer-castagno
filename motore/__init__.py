"""Motore di calcolo del progetto CER Castagno.

Ogni modulo fa una cosa sola e prende i parametri da `ipotesi.yaml`:

- ipotesi   lettura e controllo del registro delle ipotesi
- finanza   flussi di cassa, VAN, TIR, tempo di ritorno
- produzione  produzione fotovoltaica con PVGIS

In arrivo: consumi, calore, bilancio, comunita.
"""

__version__ = "0.1.0"
