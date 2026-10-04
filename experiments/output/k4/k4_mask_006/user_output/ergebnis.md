# K4 Teil 2, peak/low für Prophet ausblenden, Lauf k4_mask_006

## Setup

- Cutover: 2013-10-15, 2014-02-12, 2014-06-12, 2014-10-10, 2015-02-07
- Entscheidungen: SYS2, danach zweimal nachgespielt: nur Resets (replay) und zusätzlich ausgeblendet (mask)
- Commit: 7cb55a7 (mit lokalen Änderungen)

## Kennzahlen MAE

| Kennzahl | Wert | Bezug |
|---|---|---|
| Ausblenden, Szenario keine Änderung: MAE-Differenz [W] | 0,2 | bei 155,4 W ohne Ausblenden, 37 von 603 Tagen ausgeblendet, bei 4/5 Cutover besser |
| Ausblenden, Szenario Dauerlast +100 W: MAE-Differenz [W] | 0,4 | bei 155,3 W ohne Ausblenden, 38 von 603 Tagen ausgeblendet, bei 4/5 Cutover besser |

## MAE mask minus replay je Cutover [W], negativ = besser

| Ereignis | Zeitraum | Tage | ausgeblendet | 2013-10-15 | 2014-02-12 | 2014-06-12 | 2014-10-10 | 2015-02-07 | Mittel | Cutover besser |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| keine Änderung | vor Cutover | 300 | 10 | 0,2 | -1,7 | -0,8 | 0,0 | 21,2 | 3,8 | 2/5 |
| keine Änderung | Tag 0-13 | 70 | 2 | -5,6 | 0,0 | 0,0 | 0,0 | 0,0 | -1,1 | 1/5 |
| keine Änderung | ab Tag 14 | 233 | 25 | -11,3 | -1,4 | -5,9 | -8,6 | 7,4 | -4,0 | 4/5 |
| keine Änderung | alle Tage | 603 | 37 | -4,9 | -1,4 | -2,7 | -3,3 | 13,4 | 0,2 | 4/5 |
| Dauerlast +100 W | vor Cutover | 300 | 10 | 0,2 | -1,7 | -0,8 | 0,0 | 21,2 | 3,8 | 2/5 |
| Dauerlast +100 W | Tag 0-13 | 70 | 5 | -5,9 | 0,0 | 0,0 | -3,1 | 0,0 | -1,8 | 2/5 |
| Dauerlast +100 W | ab Tag 14 | 233 | 23 | -6,4 | -3,0 | 0,0 | -13,6 | 6,8 | -3,2 | 3/5 |
| Dauerlast +100 W | alle Tage | 603 | 38 | -3,1 | -2,0 | -0,4 | -5,6 | 13,1 | 0,4 | 4/5 |

## Kennzahlen Tagesfehler

| Kennzahl | Wert | Bezug |
|---|---|---|
| Ausblenden, Szenario keine Änderung: Tagesfehler-Differenz [W] | -0,1 | bei 74,5 W ohne Ausblenden, 37 von 603 Tagen ausgeblendet, bei 4/5 Cutover besser |
| Ausblenden, Szenario Dauerlast +100 W: Tagesfehler-Differenz [W] | 1,7 | bei 74,1 W ohne Ausblenden, 38 von 603 Tagen ausgeblendet, bei 3/5 Cutover besser |

## Tagesfehler mask minus replay je Cutover [W], negativ = besser

| Ereignis | Zeitraum | Tage | ausgeblendet | 2013-10-15 | 2014-02-12 | 2014-06-12 | 2014-10-10 | 2015-02-07 | Mittel | Cutover besser |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| keine Änderung | vor Cutover | 300 | 10 | -0,3 | -2,6 | 0,3 | 0,0 | 25,0 | 4,5 | 2/5 |
| keine Änderung | Tag 0-13 | 70 | 2 | -10,6 | 0,0 | 0,0 | 0,0 | 0,0 | -2,1 | 1/5 |
| keine Änderung | ab Tag 14 | 233 | 25 | -8,9 | -2,1 | -3,9 | -9,9 | -2,1 | -5,4 | 5/5 |
| keine Änderung | alle Tage | 603 | 37 | -4,9 | -2,1 | -1,3 | -3,9 | 11,6 | -0,1 | 4/5 |
| Dauerlast +100 W | vor Cutover | 300 | 10 | -0,3 | -2,6 | 0,3 | 0,0 | 25,0 | 4,5 | 2/5 |
| Dauerlast +100 W | Tag 0-13 | 70 | 5 | -2,6 | 0,0 | 0,0 | -1,3 | 0,0 | -0,8 | 2/5 |
| Dauerlast +100 W | ab Tag 14 | 233 | 23 | -1,6 | 2,2 | 0,0 | -6,1 | 0,1 | -1,1 | 2/5 |
| Dauerlast +100 W | alle Tage | 603 | 38 | -1,1 | -0,5 | 0,2 | -2,5 | 12,5 | 1,7 | 3/5 |

## Hinweise

- replay trifft SYS2 an 100,0 % der Tage
- Tagesfehler wie in Teil 1: Tage mit unvollständig bewerteten Stunden zählen dort nicht mit
