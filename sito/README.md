# Sito

Il sito statico di Seccheto 1.0: HTML, CSS e JavaScript senza framework né
compilazione, nessun servizio di terze parti (niente font, script o
statistiche esterne); la mappa userà Leaflet con le basi della Regione Toscana.

**Dove si pubblica**: Cloudflare Pages, con `python strumenti/pubblica_sito.py --pubblica`
(prepara `build/pubblico/` e lo carica con `wrangler`). Senza dominio il sito è su
`cer-seccheto.pages.dev`.

**Cosa è pubblico e cosa no**

| Parte | Dove | Accesso |
| --- | --- | --- |
| Capire, norme, mappa con dati aggregati, questionario | progetto `cer-seccheto` | pubblico |
| Schede delle famiglie | progetto separato, generato in locale da `dati/`, mai nel repository | Cloudflare Access: solo le email autorizzate |

Il questionario non salva niente sul server: le risposte restano sul telefono
o sul computer di chi compila finché non le manda.

Sezioni previste:

- **Capire**: i concetti su più livelli e le norme (`docs/normativa.md`)
- **Mappa**: case, superfici, moduli e potenziale solare
- **Le case**: una scheda per famiglia, solo per lei
- **Scenari**: confronto fra le ipotesi di gruppo
- **Questionario** (issue #1)
