# Layer QGIS

I layer stanno nel GeoPackage privato `dati/seccheto.gpkg`, escluso da git.
Qui stanno solo lo schema e, più avanti, gli stili (`.qml`) e i modelli di
processing (calcolo di irraggiamento SEBE, pendenza, esposizione, orizzonti).

Sistema di riferimento: **EPSG:6707** (RDN2008 / UTM zona 32N), da confermare.

## edifici (poligoni)

| Campo | Tipo | Note |
| --- | --- | --- |
| `id` | testo | es. `S01` |
| `famiglia_id` | testo | collega alla tabella `famiglie`; vuoto se la casa non aderisce |
| `nome` | testo | nome della casa, se ne ha uno |
| `fonte` | testo | `DBT`, `rilievo`, `disegnato` |
| `quota_gronda_m` | reale | quota della gronda sul livello del mare, dal DSM |

## superfici (poligoni)

Una riga per falda di tetto, tettoia o porzione di terreno utilizzabile.

| Campo | Tipo | Note |
| --- | --- | --- |
| `id` | testo | es. `S01-F1` |
| `edificio_id` | testo | vuoto per un terreno |
| `tipo` | testo | `falda`, `tettoia`, `terreno` |
| `area_m2` | reale | area reale, inclinata (non la proiezione in pianta) |
| `area_utile_m2` | reale | togliendo comignoli, lucernari, bordi di sicurezza |
| `azimut_deg` | reale | convenzione PVGIS: 0 = sud, −90 = est, +90 = ovest |
| `inclinazione_deg` | reale | 0 = piano |
| `irr_kwh_m2_anno` | reale | irraggiamento medio annuo da SEBE |
| `stato` | testo | `da_lidar`, `verificata` (dopo il sopralluogo) |
| `vincoli` | testo | paesaggistico, storico, nessuno |
| `note` | testo | |

## ostacoli (punti o poligoni)

| Campo | Tipo | Note |
| --- | --- | --- |
| `id` | testo | |
| `tipo` | testo | `albero`, `edificio`, `rilievo` |
| `altezza_m` | reale | altezza sul terreno |
| `fonte` | testo | `dsm`, `sopralluogo` |

## orizzonti (tabella senza geometria)

Profilo d'orizzonte di ogni superficie, calcolato dal DSM: è quello che
PVGIS usa per le ombre lontane e vicine.

| Campo | Tipo | Note |
| --- | --- | --- |
| `superficie_id` | testo | |
| `azimut_deg` | reale | ogni 7,5°, convenzione PVGIS |
| `elevazione_deg` | reale | altezza dell'orizzonte in quella direzione |

## bombolone (punto)

| Campo | Tipo | Note |
| --- | --- | --- |
| `id` | testo | |
| `capacita_l` | intero | |
| `proprietario` | testo | |
| `scadenza` | data | |
