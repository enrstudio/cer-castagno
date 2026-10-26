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
- `motore/produzione.py`: produzione fotovoltaica con l'API PVGIS, con cache su disco.
- `strumenti/analisi_superfici.py`: azimut delle falde dal disegno, orizzonte dal DSM LiDAR e dal DTM, resa con PVGIS.
- Nel registro: cabina primaria di Seccheto e nuovo stato `verificato`.
- `motore/meteo.py`: temperature orarie dall'archivio Open-Meteo, con cache.
- `motore/calore.py`: taratura dei consumi di GPL sui gradi giorno, calore ora per ora, COP orario della pompa di calore, stufe a pellet e legna, piano a induzione.
- `strumenti/scenari_calore.py`: confronto della spesa annua fra GPL, pompa di calore e ibridi, con il clima 2016–2025.
- `strumenti/scenari_calore.py` lavora su tutte le case del file `dati/case.yaml`: tetto, luce, calore, scenari, dati mancanti; tre tabelle per i grafici.
- `calore.calibra_da_consumo_annuo`: taratura sul GPL di un anno dichiarato, per le case senza bollette.
- Registro 0.3.0: acqua calda 0,8 kWh/persona/giorno (era 1,6: con 5 persone le letture GPL non tornavano), temperatura base fra 10 e 20 °C.
- Registro 0.2.0: parametri di acqua calda, cucina, curva climatica, COP, stufe e contatore.
- Nel registro: costi di uscita dal gas (dismissione del bombolone, messa in sicurezza, smaltimento caldaia, aumento di potenza, piano a induzione) e costo dello scenario di confronto "GPL nuovo".
