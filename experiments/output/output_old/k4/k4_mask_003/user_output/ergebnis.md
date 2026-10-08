# K4 Teil 2, peak/low für Prophet ausblenden, Lauf k4_mask_003

## Setup

- Cutover: 2013-10-15, 2014-01-15, 2014-04-15, 2014-07-15
- Entscheidungen: SYS2, danach zweimal nachgespielt: nur Resets (replay) und zusätzlich ausgeblendet (mask)
- Commit: e0a2b96 (mit lokalen Änderungen)

## Kennzahlen

| Kennzahl | Wert | Bezug |
|---|---|---|
| Ausblenden, Szenario keine Änderung: MAE-Differenz [W] | -0,4 | bei 133,1 W ohne Ausblenden, 18 von 481 Tagen ausgeblendet, gleiche Richtung 3/4 |
| Ausblenden, Szenario Dauerlast +100 W: MAE-Differenz [W] | -0,1 | bei 136,6 W ohne Ausblenden, 19 von 481 Tagen ausgeblendet, gleiche Richtung 3/4 |

## MAE mask minus replay je Cutover [W], negativ = besser

| Ereignis | Zeitraum | Tage | ausgeblendet | 2013-10-15 | 2014-01-15 | 2014-04-15 | 2014-07-15 | Mittel | gleiche Richtung |
|---|---|---:|---:|---:|---:|---:|---:|---:|---|
| keine Änderung | vor Cutover | 239 | 8 | 0,0 | -0,5 | 1,4 | 1,2 | 0,5 | 2/4 |
| keine Änderung | Tag 0-13 | 55 | 1 | -1,2 | 0,0 | -4,4 | 0,2 | -1,3 | 2/4 |
| keine Änderung | ab Tag 14 | 187 | 9 | -2,0 | -0,0 | 0,6 | -4,1 | -1,4 | 3/4 |
| keine Änderung | alle Tage | 481 | 18 | -0,9 | -0,3 | 0,4 | -1,0 | -0,4 | 3/4 |
| Dauerlast +100 W | vor Cutover | 239 | 8 | 0,0 | -0,5 | 1,4 | 1,2 | 0,5 | 2/4 |
| Dauerlast +100 W | Tag 0-13 | 55 | 2 | -5,3 | 0,0 | -9,9 | 0,0 | -3,8 | 2/4 |
| Dauerlast +100 W | ab Tag 14 | 187 | 9 | 0,0 | 0,1 | 4,6 | -3,3 | 0,4 | 3/4 |
| Dauerlast +100 W | alle Tage | 481 | 19 | -0,6 | -0,2 | 1,3 | -0,7 | -0,1 | 3/4 |

## Hinweise

- replay trifft SYS2 an 100,0 % der Tage
