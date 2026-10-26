# CER Castagno

Strumenti aperti per valutare insieme una **comunità energetica rinnovabile**
a Castagno di Piteccio (Pistoia), a partire dalla frazione di Seccheto.

Le case di Seccheto sono servite da un bombolone di GPL condiviso che va
rinnovato entro il 2027. Questo progetto aiuta le famiglie a capire, con i
propri numeri, cosa conviene: un nuovo impianto a GPL, una pompa di calore,
pannelli fotovoltaici, una comunità energetica fra vicini. E come la scelta
di ognuno si combina con quella degli altri.

## Stato

**Fase 0 / versione 0.1: in costruzione.** Per ora ci sono il registro delle
ipotesi e il modulo dei conti economici. La prima versione utile,
*Seccheto 1.0*, è pensata per 3–4 famiglie: il motore gira in locale e
pubblica un sito statico con concetti, mappa e scenari.

## Cosa c'è dentro

```text
ipotesi.yaml     il registro delle ipotesi: ogni parametro con valore, forchetta, fonte e stato
METODO.md        il metodo di calcolo, con formule e fonti
docs/            approfondimenti: normativa.md, le norme per pannelli e CER
motore/          il motore di calcolo in Python
  ipotesi.py     lettura e controllo del registro
  finanza.py     flussi di cassa, VAN, TIR, tempo di ritorno
  produzione.py  produzione fotovoltaica con PVGIS, con cache
  pannelli.py    quanti moduli stanno su una falda, e dove
  meteo.py       temperature orarie misurate (Open-Meteo), con cache
  calore.py      calore dalle bollette GPL, pompa di calore, stufe a pellet e legna
strumenti/       script di servizio
  estrai_bollette.py    dati dalle bollette PDF a tabelle CSV
  analisi_superfici.py  falde dal DSM LiDAR: azimut, orizzonte, moduli, resa con PVGIS
  scenari_calore.py     scheda di ogni casa: tetto, consumi, riscaldamento senza gas
  controllo_privacy.py  blocca i commit con dati personali
qgis/            schema dei layer e stili per QGIS
sito/            il sito statico (in arrivo)
test/            casi noti che il motore deve ritrovare
dati/            PRIVATO, escluso da git: GeoPackage, bollette, CSV estratti
```

## Per cominciare

Serve Python 3.10 o più recente. Per estrarre le bollette serve anche
`pdftotext`, dal pacchetto `poppler-utils`.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
git config core.hooksPath .githooks   # attiva il controllo privacy prima di ogni commit
pytest                                # i test devono passare tutti
```

Estrarre i dati dalle bollette di una famiglia:

```bash
python strumenti/estrai_bollette.py /percorso/delle/bollette dati/bollette
```

## Il registro delle ipotesi

Ogni numero usato nei calcoli sta in `ipotesi.yaml`, mai scritto
direttamente nel codice. Ogni voce dice da dove viene e quanto è affidabile:

| Stato | Significato |
| --- | --- |
| `dalle_bollette` | ricavato dalle bollette reali delle famiglie |
| `verificato` | controllato su una fonte ufficiale |
| `da_verificare` | stima iniziale, va controllata sulla fonte ufficiale |
| `decide_il_gruppo` | una scelta delle famiglie, non un fatto (es. il tasso di sconto) |
| `da_calcolare` | lo calcola il motore caso per caso (es. la produzione di ogni tetto) |

Per cambiare un'ipotesi si modifica il file, scrivendo nel commit il perché.
Ogni risultato riporta la versione del registro con cui è stato calcolato.

## Privacy

Il codice è pubblico, i dati delle famiglie no. Bollette, consumi, codici
POD e contatti stanno solo nella cartella `dati/`, esclusa da git. Un
controllo automatico blocca i commit che contengono POD, codici fiscali,
email o numeri di cellulare. Sul sito pubblico le famiglie compaiono solo
con uno pseudonimo e solo con dati aggregati.

## Come è scritto questo codice

Il codice è scritto con l'assistenza di Claude, un modello di intelligenza
artificiale di Anthropic, ed è rivisto e approvato da una persona prima di
entrare nel ramo principale. Non contiene codice copiato da altri progetti.
Le formule hanno le loro fonti in `METODO.md`, i parametri in `ipotesi.yaml`.

I commenti sono in italiano e spiegano il **perché** delle scelte. I nomi
riportano l'unità di misura (`energia_kwh`, `prezzo_eur_kwh`). Ogni modulo
del motore ha i suoi test con casi di cui si conosce già la risposta.

## Licenze

- Codice: [GNU AGPL-3.0 o successiva](LICENSE). Chi modifica il software e lo
  offre come servizio web deve rendere disponibile il codice modificato.
- Testi, metodo e documentazione: [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/deed.it).

Il progetto è pensato per essere riusato da altre frazioni e comunità.
