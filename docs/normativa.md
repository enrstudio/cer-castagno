# Norme per i pannelli sul tetto e per la comunità energetica

Rassegna delle leggi e delle norme tecniche che contano per Seccheto, aggiornata
al 26 ottobre 2026. Serve a due cose: sapere che cosa si può fare e con quale
pratica, e dare una fonte a ogni numero del metodo dei pannelli
(`motore/pannelli.py`, registro `ipotesi.yaml`).

**Non è una consulenza.** Molti testi sono cambiati nel 2025 e nel 2026. Per
le scelte vere fa fede il testo vigente su
[Normattiva](https://www.normattiva.it) e la verifica di un tecnico abilitato.
Le copie dei documenti consultati sono nella cartella `normativa/` del progetto,
fuori dal repository. Ogni punto riporta il suo stato:

| Stato | Significato |
| --- | --- |
| **letto** | letto sul documento ufficiale, o su una sua copia fedele |
| **da sintesi** | letto in una sintesi affidabile (ANCE, ordini professionali), non sul testo di legge |
| **da verificare** | indicazione trovata, da controllare sul testo vigente o con il Comune |

## 1. Che pratica serve per mettere i pannelli

**Testo unico sulle rinnovabili**: D.Lgs. 25 novembre 2024, n. 190, in
vigore dal 30 dicembre 2024, modificato dal correttivo D.Lgs. 178/2025, in
vigore dall'11 dicembre 2025. Ha sostituito le vecchie regole del
D.Lgs. 28/2011.

- **Attività libera** (Allegato A, nessuna pratica per l'impianto): impianti
  fotovoltaici **integrati su coperture di edifici esistenti, con la stessa
  inclinazione e lo stesso orientamento della falda**, senza cambiare la
  sagoma dell'edificio e con superficie non superiore a quella del tetto.
  *Da sintesi* (ANCE, dicembre 2025).
  - Per questo il metodo dei pannelli dispone i moduli **aderenti alla
    falda**, senza telai inclinati.
- Anche in attività libera, l'intervento deve (art. 7, *da sintesi*):
  - essere compatibile con il piano urbanistico e il regolamento edilizio
    del Comune;
  - rispettare le Norme tecniche per le costruzioni, un requisito aggiunto
    dal correttivo del 2025;
  - avere la comunicazione o il titolo per eventuali opere edilizie
    collegate.
- **Si passa alla PAS** (procedura abilitativa semplificata) se l'intervento
  riguarda (*da sintesi*):
  - beni culturali, o beni paesaggistici tutelati dalla parte III del
    Codice dei beni culturali (D.Lgs. 42/2004);
  - aree naturali protette o siti Natura 2000;
  - vincoli per il rischio idrogeologico, sismico o la prevenzione incendi.
- **Vincolo paesaggistico "di zona"** (art. 136, comma 1, lettere b e c del
  D.Lgs. 42/2004). Serve l'autorizzazione paesaggistica semplificata, con
  risposta entro 30 giorni e silenzio-assenso. Non serve se l'impianto non
  si vede dagli spazi esterni e dai punti panoramici, oppure se il tetto è
  in materiali della tradizione locale (art. 7, comma 6). *Da sintesi.*

**Per Seccheto, da verificare:**
1. **Vincolo paesaggistico.** Il Piano paesaggistico della Toscana (PIT,
   Ambito 6 Pistoia) elenca il vincolo *"Zona a nord della città di
   Pistoia"*: D.M. 03/02/1966, G.U. n. 46 del 1966, 3.869 ettari, che
   comprende colline, valli e borghi a nord della città. Il documento non
   dice se ci rientra anche Piteccio: va controllato sulla mappa dei
   vincoli del PIT (Geoscopio della Regione Toscana). Ci sono anche i
   vincoli "per legge" dell'art. 142, come boschi e fasce lungo i corsi
   d'acqua, che si vedono sugli stessi layer.
2. **Vincolo idrogeologico** (R.D. 3267/1923): è frequente sulle colline
   del pistoiese. Va controllato sul layer regionale.
3. **Rischio sismico.** Il correttivo cita fra i vincoli anche la tutela
   dal rischio sismico, e secondo ANCE questo amplia molto i casi di PAS.
   Come si applichi a un comune classificato sismico va chiesto all'ufficio
   tecnico del Comune di Pistoia.
4. **Regolamento edilizio del Comune di Pistoia:** eventuali prescrizioni
   sui pannelli nei nuclei storici.

## 2. Sicurezza antincendio

**Linea guida dei Vigili del fuoco**: nota DCPREV n. 14030 del 1° settembre
2025, che aggiorna la guida del 2012 (nota 1324). *Letto.*

- **Si applica** agli impianti fotovoltaici nelle *attività soggette* ai
  controlli dei Vigili del fuoco (Allegato I del D.P.R. 151/2011). Le case
  di abitazione di solito non lo sono.
  - Per le altre attività le indicazioni *"possono costituire un utile
    riferimento"* (par. 1.2, comma 4).
  - Per gli impianti in attività non soggette la guida richiama la
    Legge 186/1968 e il D.M. 37/2008.
- **Le distanze sul tetto** (par. 3.3.5.1):
  - **1 m** di fascia libera da pannelli e altri componenti lungo **il
    limite della copertura** (comma 2);
  - **1 m** da evacuatori di fumo, **aperture** e impianti tecnici sul
    tetto, come comignoli e prese d'aria (comma 3). Sui **tetti a falda**
    il metro si misura in **proiezione orizzontale** (comma 4);
  - gruppi di pannelli non più grandi di 20 m in ogni direzione, separati
    da passaggi di 2 m (comma 2): a Seccheto le falde sono più piccole;
  - **1 m** dalla proiezione di eventuali **muri tagliafuoco** sotto il
    tetto (comma 5). Non serve se il solaio di copertura resiste al fuoco.
- Sono esclusi dalla guida gli impianti sotto 800 W e quelli plug & play
  (par. 1.2, comma 3).

**Nel metodo:** `fascia_bordo_copertura_m` e `distanza_ostacoli_m` valgono
1 m, prendendo la guida come riferimento. La forchetta va da 0, il massimo
geometrico, a 1 m. Sul lato in comune fra due case sotto lo stesso tetto
c'è `fascia_confine_m`, da decidere fra vicini, con valore di base 0.

## 3. Lavorare sul tetto in sicurezza (Toscana)

**Regolamento regionale DPGR 18 dicembre 2013, n. 75/R**, sulle misure
preventive e protettive per l'accesso, il transito e i lavori in quota sulle
coperture, con gli schemi approvati dalla D.G.R. 178/2014. *Da sintesi*
(PuntoSicuro, 2014).

- Si applica a *qualsiasi intervento edilizio e impiantistico* che riguardi
  la copertura, **compresi gli impianti fotovoltaici**.
- Serve l'**elaborato tecnico della copertura** (art. 5), redatto dal
  coordinatore per la sicurezza o dal progettista.
- Le misure contro le cadute devono essere **fisse o permanenti**, come
  linee vita e ancoraggi. Se la struttura non le regge, lo si motiva e si
  usano misure provvisorie. Una copertura bassa (non più di 4 m) può farne
  a meno solo se *priva di impianti tecnologici*: con i pannelli le misure
  fisse servono.
- Sulle coperture calpestabili con pannelli solari vanno lasciati **spazi per
  installare e usare il sistema anticaduta**.

**Per Seccheto, da verificare:** il testo vigente del 75/R, perché nel periodo
del superbonus se ne è discussa una modifica. È probabile che la linea vita
sia una voce di costo per ogni casa. Gli spazi per l'anticaduta possono
togliere posto ai moduli.

## 4. Strutture e vento

- **Norme tecniche per le costruzioni**, D.M. 17 gennaio 2018 (NTC 2018):
  carichi di neve e vento sul tetto con i pannelli. Il Testo unico sulle
  rinnovabili, dopo il correttivo, ne chiede esplicitamente il rispetto.
  *Da sintesi.*
- Le **zone di bordo e d'angolo** del tetto sono quelle dove il vento tira di
  più (EN 1991-1-4). Lì il sistema di fissaggio vuole più ancoraggi o non
  ammette moduli. La larghezza dipende dall'edificio e la dà il manuale del
  sistema di fissaggio. *Da verificare* sul manuale del preventivo.

## 5. Impianto elettrico e connessione

- **Legge 186/1968** (regola dell'arte) e **D.M. 37/2008**: impianto fatto da
  un'impresa abilitata, con la **dichiarazione di conformità**. *Richiamati
  dalla linea guida VVF.*
- **Modello unico** per la connessione, per impianti fino a **200 kW** su
  edifici, presso clienti che hanno già un contatore: D.M. MiTE n. 297 del
  2 agosto 2022 e delibera ARERA 674/2022. *Da sintesi.*
- **Norma CEI 0-21**: regole per connettere gli impianti alla rete in bassa
  tensione. Gli inverter devono esserne conformi. *Da verificare* la
  versione vigente.

## 6. Comunità energetica rinnovabile

Le voci economiche sono nel registro e vanno verificate prima dell'assemblea
(issue #16).

- **D.Lgs. 199/2021** (art. 31): definizione delle CER.
- **D.M. MASE 414/2023** e **regole operative del GSE**: tariffa premio
  sull'energia condivisa per 20 anni e contributo PNRR in conto capitale.
  Termine per l'entrata in esercizio: 31 dicembre 2027. *Da verificare.*
- **D.M. MASE 127/2025.** Estende il **contributo PNRR del 40%** ai comuni
  **fino a 50.000 abitanti** (prima erano 5.000). Toglie la riduzione della
  tariffa per le persone fisiche e porta l'anticipo al 30%. *Da sintesi.*
  - **Per Seccheto:** il Comune di Pistoia supera i 50.000 abitanti. Se il
    criterio è il comune, e non la frazione, il contributo del 40% non si
    applica e resta solo la tariffa premio. *Da verificare* sulle regole GSE.
- **ARERA, Testo integrato autoconsumo diffuso** (TIAD, delibera 727/2022):
  valorizzazione dell'energia condivisa.
- **Cabina primaria**: tutti i membri della CER devono stare sotto la stessa.
  Seccheto è sotto la AC001E00710 (mappa GSE, *letto*).

## Fonti consultate

- Vigili del fuoco, [Nota DCPREV 14030 del 01/09/2025, linea guida
  FV](https://www.vigilfuoco.it/sites/default/files/2025-09/COORD_NOTA_01_09_2025_n_14030_linee_guida_FV.pdf).
- ANCE, [I regimi amministrativi per le energie rinnovabili: le novità del
  decreto correttivo](https://ance.it/2025/12/i-regimi-amministrativi-per-le-energie-rinnovabili-le-novita-del-decreto-correttivo/)
  ([allegato](https://ance.it/wp-content/uploads/allegati/Regimi_amministrativi_FER_allegato_2025.pdf)), dicembre 2025.
- Regione Toscana, [PIT, Ambito 6 Pistoia, sezione 4: beni paesaggistici](https://www.regione.toscana.it/documents/10180/404161/ambito_06_pistoia_4/c5b677d0-aed4-4f32-8bd9-1ddedd53daf5).
- PuntoSicuro, [Regione Toscana: regole e modelli per la manutenzione sulle
  coperture](https://www.puntosicuro.it/edilizia-C-10/regione-toscana-regole-modelli-per-la-manutenzione-sulle-coperture-AR-13710/), 2014.
- VerbanoNews, [CER, il 40% a fondo perduto anche per i comuni fino a 50 mila
  abitanti](https://www.verbanonews.it/aree-geografiche/lombardia/2025/07/01/comunita-energetiche-rinnovabili-il-40-a-fondo-perduto-anche-per-i-comuni-fino-a-50mila-abitanti/1004647/), luglio 2025.
- Certifico, [Decreto MiTE n. 297 del 2 agosto 2022](https://www.certifico.com/impianti/legislazione-impianti/impianti-fotovoltaici/decreto-mite-n-297-del-02-agosto-2022) (modello unico).
- JA Solar, scheda tecnica JAM54D40 435-460/LB (2024-09), dal [portale Segen](https://portal.segen.co.uk/reseller/docs/JAM54D40%20435-460%20LB%20Black%20Frame%20Global_DE_20240909A__25-yr%20warranty.pdf).
