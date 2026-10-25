# Registro delle modifiche

Le versioni seguono lo schema MAJOR.MINOR.PATCH. Ogni risultato pubblicato
cita la versione del motore che lo ha prodotto.

## [Non ancora rilasciato]

### Aggiunto
- Struttura del repository, licenza AGPL-3.0, README e METODO.
- `ipotesi.yaml`: prima stesura del registro delle ipotesi.
- `motore/ipotesi.py`: lettura e controllo del registro.
- `motore/finanza.py`: flussi di cassa, VAN, TIR, tempo di ritorno, rapporto benefici/costi.
- `strumenti/estrai_bollette.py`: estrazione dei dati dalle fatture Enel e Beyfin in PDF.
- `strumenti/controllo_privacy.py`: blocca i commit che contengono dati personali.
- Test automatici su GitHub Actions.
