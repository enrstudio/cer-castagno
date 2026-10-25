# Metodo di calcolo

Questo documento spiega **come** il motore arriva ai suoi numeri. È scritto
per essere letto da chi deve fidarsi dei risultati, non solo da chi scrive
il codice. Ogni sezione corrisponde a un modulo di `motore/`. Le sezioni
ancora da scrivere descrivono il metodo previsto.

Convenzioni: importi in euro IVA inclusa; tassi e quote come frazioni
(3% = 0,03); energia in kWh; anni numerati da 0 (oggi).

## 1. Registro delle ipotesi (`motore/ipotesi.py`)

Tutti i parametri vengono da `ipotesi.yaml`. Il motore si ferma se una voce
è scritta male, se un valore cade fuori dalla sua forchetta o se un valore
necessario è ancora ignoto. È meglio un calcolo che non parte che uno che
usa in silenzio un dato sbagliato.

## 2. Conti economici (`motore/finanza.py`) — scritto e testato

**Flussi di cassa.** Un investimento è una riga di importi, uno per anno.
All'anno 0 c'è l'esborso, al netto di eventuali contributi pagati subito.
Dall'anno t = 1 alla fine della vita utile *n*:

```text
beneficio_t = beneficio_1 × (1 + v)^(t−1) × (1 − d)^(t−1) + rata detrazione (se t ≤ 10)
costo_t     = costi annui + eventuali ricambi dell'anno t
flusso_t    = beneficio_t − costo_t
```

dove *v* è la variazione annua dei prezzi dell'energia e *d* il degrado
annuo dell'impianto. Il beneficio è sempre una **differenza rispetto a
un'alternativa**: per esempio la spesa con un nuovo impianto a GPL meno la
spesa con la pompa di calore.

**Attualizzazione.** Un euro all'anno t vale oggi 1/(1+i)^t, con *i* il
tasso di sconto: il rendimento della migliore alternativa ai propri soldi.
Per un importo costante per *n* anni, la somma ha la forma chiusa
(fattore di annualità):

```text
a(i, n) = (q^n − 1) / (i × q^n),   q = 1 + i
```

**Indicatori.**

| Indicatore | Definizione | Conviene se |
| --- | --- | --- |
| VAN | Σ flusso_t / (1+i)^t, da t = 0 a n | > 0 |
| TIR | il tasso *i* per cui VAN = 0, cercato per bisezione fra −99% e +100% | > tasso di sconto |
| Tempo di ritorno semplice | primo anno in cui la somma dei flussi torna ≥ 0, interpolato | < vita utile |
| Tempo di ritorno attualizzato | come sopra, con i flussi attualizzati | < vita utile |
| Rapporto B/C | valore attuale dei benefici / valore attuale dei costi (investimento compreso) | > 1 |

Con flussi che cambiano segno più volte (una batteria ricomprata a metà
vita) il TIR può non essere unico: per decidere fa fede il VAN.

**Verifica.** Il test `test_foglio_amico_van_e_rapporto_bc` ritrova i
numeri del foglio di calcolo da cui è partito il progetto: VAN −1.557,45 €
e B/C 0,9113 per un fotovoltaico da 16.000 € con 1.024,50 € l'anno di
benefici, 100 € di costi annui, al 4% per 25 anni.

## 3. Produzione fotovoltaica (`motore/produzione.py`) — da scrivere

Per ogni superficie: chiamata all'API PVGIS `seriescalc` (JRC, banca dati
SARAH3) con potenza, perdite, inclinazione, azimut (convenzione PVGIS:
0 = sud, −90 = est, +90 = ovest) e profilo d'orizzonte calcolato dal DSM
LiDAR. Le serie orarie di più anni si mediano in un anno tipo da 8.760 ore.
Le risposte sono salvate in `cache/`.

## 4. Consumi elettrici orari (`motore/consumi.py`) — da scrivere

I kWh mensili per fascia F1, F2 e F3 letti in bolletta si distribuiscono
sulle ore della fascia con un profilo domestico tipo, scalato in modo che
ogni mese e ogni fascia tornino esattamente con la bolletta.

## 5. Riscaldamento (`motore/calore.py`) — da scrivere

Calore utile = m³ di GPL × PCI × rendimento caldaia, tolta la quota per
acqua calda e cucina. Si distribuisce sulle ore con i gradi-ora ricavati
dalla temperatura oraria dell'anno tipo. Con la pompa di calore, il consumo
elettrico è il calore diviso il COP dell'ora, che scende col freddo.

## 6. Bilancio della casa (`motore/bilancio.py`) — da scrivere

Ora per ora: autoconsumo = min(produzione, consumo); poi la batteria (carica
con l'eccedenza, scarica sul deficit, efficienza di ciclo del 90%); poi
l'immissione in rete o il prelievo.

## 7. Comunità energetica (`motore/comunita.py`) — da scrivere

Energia condivisa nell'ora *h*, sui membri *m*:

```text
E_cond,h = min( Σ_m E_immessa,m,h , Σ_m E_prelevata,m,h )
```

Incentivo = Σ_h E_cond,h × (tariffa premio + valorizzazione ARERA). Tutta
l'energia immessa è anche venduta col ritiro dedicato. L'incentivo si divide
secondo le quote di statuto (`ripartizione_*` nel registro).

## Fonti

Le fonti di ogni parametro sono nel campo `fonte` di `ipotesi.yaml`.
Documento di progetto della Fase 0: modello dati, registro e piano.
