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

## 3. Produzione fotovoltaica (`motore/produzione.py`) — scritto e testato

Per ogni falda si chiama l'API PVGIS `PVcalc` (JRC, banca dati SARAH3) con
1 kWp, perdite, inclinazione, azimut (convenzione PVGIS: 0 = sud, −90 = est,
+90 = ovest) e il profilo d'orizzonte calcolato dal DSM LiDAR
(`strumenti/analisi_superfici.py`). Il risultato è la produzione media annua
e mensile di 1 kWp; quella della falda è questa per i kWp che ci stanno
(sezione 3 bis). Le risposte sono salvate in `cache/`. Per il bilancio ora
per ora servirà `seriescalc` (issue #11).

## 3 bis. Quanti moduli stanno su una falda (`motore/pannelli.py`) — scritto e testato

Le regole da cui vengono i parametri sono in `docs/normativa.md`.

1. **Modulo di riferimento**: misure e potenza dalla scheda tecnica di un
   modulo in commercio (`modulo_*` nel registro), da sostituire con quello
   del preventivo.
2. **Il piano della falda.** Coordinate sul tetto: x lungo il colmo, y lungo
   la pendenza, con y = (distanza in pianta lungo la discesa) / cos(inclinazione).
3. **Fasce libere ai bordi**, misurate sul tetto, diverse per lato:
   - `fascia_bordo_copertura_m` sui bordi veri del tetto (gronda, colmo,
     lati liberi);
   - `fascia_confine_m` sui lati in comune con la falda di un'altra casa.
     Un lato è "in comune" se tre suoi punti (a ¼, ½, ¾) stanno entro 0,5 m
     dal bordo di un'altra falda del layer: è una tolleranza di disegno.

   La falda ristretta è l'intersezione dei semipiani interni, ogni lato
   spostato della sua fascia.
4. **Ostacoli** (comignoli, lucernari, antenne, disegnati in pianta): resta
   libero il rettangolo, sul tetto, che contiene l'ostacolo allargato di
   `distanza_ostacoli_m` in proiezione orizzontale (lungo la pendenza, sul
   tetto, d / cos(inclinazione)). Il rettangolo è più prudente del cerchio
   della norma.
5. **File di moduli** parallele al colmo, con `spazio_tra_moduli_m` fra un
   modulo e l'altro e fra una fila e l'altra. In una fila che va da y₀ a
   y₀ + h, la falda ristretta, convessa, è larga almeno quanto lo è ai due
   bordi della fila: [max(sinistra₀, sinistra₁), min(destra₀, destra₁)].
   Tolte le parti vicine agli ostacoli, in ogni tratto libero stanno
   ⌊(L + s) / (l + s)⌋ moduli, centrati. La prima fila si prova a passi di
   5 cm lungo la pendenza; si tiene la posizione con più moduli.
6. **Orientamento**: tutti i moduli in verticale (lato lungo lungo la
   pendenza) o tutti in orizzontale; si tiene il migliore.

Si riporta anche il **massimo geometrico**, senza fasce né distanze, come
limite superiore. **Limiti**: falda convessa (se no il calcolo si ferma);
niente file miste; pochi decimi di grado di azimut possono spostare il conto
di un modulo.

## 4. Consumi elettrici orari (`motore/consumi.py`) — da scrivere

I kWh mensili per fascia F1, F2 e F3 letti in bolletta si distribuiscono
sulle ore della fascia con un profilo domestico tipo, scalato in modo che
ogni mese e ogni fascia tornino esattamente con la bolletta.

## 5. Riscaldamento (`motore/calore.py`, `motore/meteo.py`) — scritto e testato

**Temperature.** Temperature orarie a 2 m dall'archivio Open-Meteo (rianalisi
ERA5, griglia di circa 25 km, corretta per la quota della casa), in UTC.
Il clima "tipo" non è un anno solo ma i dieci anni 2016–2025: ogni risultato
si dà come media, con l'anno più mite e quello più freddo.

**Taratura sulle letture.** Si usano solo le letture *effettive* del
contatore GPL. Per ogni intervallo *i* fra due letture, di *n_i* giorni:

```text
m³_i = b × n_i + k × GG_i(T_b),     GG_i = Σ_giorni max(0, T_b − T_media,giorno)
```

- *b*, la quota fissa (acqua calda e cucina), **non si stima** dalle
  letture: con poche letture tutte a cavallo di un inverno si confonde col
  riscaldamento. Si fissa così:
  `b = persone × ACS_persona / (PCI × η_caldaia) + GPL_cucina`.
- *k* (m³ per grado giorno) si trova con i minimi quadrati per l'origine:
  `k = Σ GG_i × (m³_i − b n_i) / Σ GG_i²`.
- *T_b* (temperatura base) si cerca a passi di 0,5 °C dentro la forchetta
  del registro, tenendo quella con lo scarto minore. Se finisce al bordo
  della forchetta lo script lo segnala: il modello forse non descrive bene
  la casa (una stufa che aiuta, una quota fissa sbagliata).

**Senza bollette.** Per una casa di cui si conosce solo il GPL di un anno
tipico (dal questionario) si toglie la quota fissa e si divide il resto per
i gradi giorno medi del 2023–2025, alla temperatura base del registro. Non
c'è uno scarto da riportare: la stima vale quanto il numero dichiarato.
Una casa che si scalda a legna tiene la sua stufa: del gas si conta solo
quello che fa oggi (per esempio i fornelli).

**Calore ora per ora.** Il calore utile del giorno è `k × GG_giorno × PCI ×
η_caldaia` e si divide fra le ore in proporzione a `max(0, T_interna −
T_ora)`. L'acqua calda è `persone × ACS_persona`, uguale in ogni ora.

**Pompa di calore aria-acqua.** COP orario dalla regressione di Ruhnau e
altri (2019, banca dati When2Heat), con ΔT = T_mandata − T_esterna limitato
fra 15 e 80 °C:

```text
COP = (6,08 − 0,09 ΔT + 0,0005 ΔT²) × correzione,     COP ≥ 1
T_mandata = mandata_a_0°C − pendenza × T_esterna        (termosifoni)
T_mandata = temperatura_acqua_calda                     (acqua calda)
```

Elettricità dell'ora = calore / COP. SCOP = calore annuo fornito dalla
pompa / elettricità annua.

**Stufa (scenari ibridi).** Copre la quota `quota_stufa` del riscaldamento
in ogni ora; combustibile = calore della stufa / (PCI × rendimento).

**Cucina.** Piano a induzione: `GPL_cucina × 365 × PCI × η_fornelli /
η_induzione` kWh all'anno.

**Spesa annua di energia.** (kWh pompa di calore + kWh induzione) × prezzo
marginale della luce + kg di combustibile × prezzo + quota fissa per i kW
di contatore in più. Il riferimento GPL è il consumo previsto dal modello,
con lo stesso clima, per il prezzo medio delle fatture. Investimenti e
manutenzione entrano nei conti di `finanza.py`.

**Limiti noti.** Riscaldamento continuo, senza orari di accensione; acqua
calda uguale in ogni ora; stufa a quota costante; nessuna resistenza
integrativa (il picco elettrico è quindi una stima per difetto nei giorni
più freddi).

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
