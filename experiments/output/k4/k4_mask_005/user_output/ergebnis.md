# K4 Teil 2, peak/low für Prophet ausblenden, Lauf k4_mask_005

## Setup

- Cutover: 2013-10-15, 2014-02-12, 2014-06-12, 2014-10-10, 2015-02-07
- Entscheidungen: SYS2, danach zweimal nachgespielt: nur Resets (replay) und zusätzlich ausgeblendet (mask)
- Commit: 83d6802 (mit lokalen Änderungen)

## Kennzahlen

| Kennzahl | Wert | Bezug |
|---|---|---|
| Ausblenden, Szenario keine Änderung: MAE-Differenz [W] | -0,9 | bei 141,4 W ohne Ausblenden, 33 von 603 Tagen ausgeblendet, gleiche Richtung 3/5 |
| Ausblenden, Szenario Dauerlast +100 W: MAE-Differenz [W] | -0,2 | bei 142,8 W ohne Ausblenden, 23 von 603 Tagen ausgeblendet, gleiche Richtung 3/5 |

## MAE mask minus replay je Cutover [W], negativ = besser

| Ereignis | Zeitraum | Tage | ausgeblendet | 2013-10-15 | 2014-02-12 | 2014-06-12 | 2014-10-10 | 2015-02-07 | Mittel | gleiche Richtung |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| keine Änderung | vor Cutover | 300 | 4 | -0,0 | -0,6 | 0,4 | 0,0 | -0,5 | -0,1 | 3/5 |
| keine Änderung | Tag 0-13 | 70 | 3 | -2,8 | 0,0 | 0,0 | 0,9 | 0,0 | -0,4 | 1/5 |
| keine Änderung | ab Tag 14 | 233 | 26 | -4,9 | 1,3 | -3,9 | -5,0 | 2,8 | -1,9 | 3/5 |
| keine Änderung | alle Tage | 603 | 33 | -2,2 | 0,2 | -1,3 | -1,8 | 0,9 | -0,9 | 3/5 |
| Dauerlast +100 W | vor Cutover | 300 | 4 | -0,0 | -0,6 | 0,4 | 0,0 | -0,5 | -0,1 | 3/5 |
| Dauerlast +100 W | Tag 0-13 | 70 | 5 | -4,4 | 0,0 | 0,0 | -0,8 | 0,0 | -1,1 | 2/5 |
| Dauerlast +100 W | ab Tag 14 | 233 | 14 | 0,1 | 0,6 | 0,0 | -5,5 | 4,4 | -0,1 | 1/5 |
| Dauerlast +100 W | alle Tage | 603 | 23 | -0,5 | -0,1 | 0,2 | -2,2 | 1,5 | -0,2 | 3/5 |

## Hinweise

- replay trifft SYS2 an 100,0 % der Tage
