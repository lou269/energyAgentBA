# K4 Teil 2, peak/low für Prophet ausblenden, Lauf k4_mask_008

## Setup

- Cutover: CO1 (2014-07-15), CO2 (2014-10-24), CO3 (2015-03-01), CO4 (2015-06-10), CO5 (2015-10-22)
- Entscheidungen: SYS2, danach zweimal nachgespielt: nur Resets (replay) und zusätzlich ausgeblendet (mask)
- Commit: 68202b5 (mit lokalen Änderungen)

## Kennzahlen MAE

| Kennzahl | Wert | Bezug |
|---|---|---|
| Ausblenden, Szenario keine Änderung: MAE-Differenz [W] | 98,3 | bei 145,9 W ohne Ausblenden, 29 von 503 Tagen ausgeblendet, bei 3/5 Cutover besser |
| Ausblenden, Szenario Sprung +20 %: MAE-Differenz [W] | -0,4 | bei 163,5 W ohne Ausblenden, 29 von 503 Tagen ausgeblendet, bei 4/5 Cutover besser |

## MAE mask minus replay je Cutover [W], negativ = besser

| Ereignis | Zeitraum | Tage | ausgeblendet | 2014-07-15 | 2014-10-24 | 2015-03-01 | 2015-06-10 | 2015-10-22 | Mittel | Cutover besser |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| keine Änderung | vor Cutover | 199 | 5 | -2,9 | 0,0 | 0,0 | -1,8 | -0,8 | -1,1 | 3/5 |
| keine Änderung | Tag 0-13 | 69 | 7 | -1,4 | -6,0 | 0,0 | -2,9 | -3,8 | -2,8 | 4/5 |
| keine Änderung | ab Tag 14 | 235 | 17 | 0,1 | -4,1 | 3,7 | 1056,4 | -1,3 | 211,0 | 2/5 |
| keine Änderung | alle Tage | 503 | 29 | -1,3 | -2,7 | 1,7 | 495,4 | -1,4 | 98,3 | 3/5 |
| Sprung +20 % | vor Cutover | 199 | 5 | -2,9 | 0,0 | 0,0 | -1,8 | -0,8 | -1,1 | 3/5 |
| Sprung +20 % | Tag 0-13 | 69 | 11 | -4,7 | -8,8 | 0,0 | -2,0 | -2,7 | -3,6 | 4/5 |
| Sprung +20 % | ab Tag 14 | 235 | 13 | -0,1 | -4,6 | 8,9 | 1,8 | -0,2 | 1,2 | 3/5 |
| Sprung +20 % | alle Tage | 503 | 29 | -1,8 | -3,4 | 4,1 | -0,1 | -0,8 | -0,4 | 4/5 |

## Kennzahlen Tagesfehler

| Kennzahl | Wert | Bezug |
|---|---|---|
| Ausblenden, Szenario keine Änderung: Tagesfehler-Differenz [W] | 99,0 | bei 78,5 W ohne Ausblenden, 29 von 502 Tagen ausgeblendet, bei 4/5 Cutover besser |
| Ausblenden, Szenario Sprung +20 %: Tagesfehler-Differenz [W] | 1,6 | bei 85,1 W ohne Ausblenden, 29 von 502 Tagen ausgeblendet, bei 1/5 Cutover besser |

## Tagesfehler mask minus replay je Cutover [W], negativ = besser

| Ereignis | Zeitraum | Tage | ausgeblendet | 2014-07-15 | 2014-10-24 | 2015-03-01 | 2015-06-10 | 2015-10-22 | Mittel | Cutover besser |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| keine Änderung | vor Cutover | 198 | 5 | -1,6 | 0,0 | 0,0 | -0,1 | 2,4 | 0,1 | 2/5 |
| keine Änderung | Tag 0-13 | 69 | 7 | -0,2 | -21,8 | 0,0 | -6,4 | -11,8 | -8,0 | 4/5 |
| keine Änderung | ab Tag 14 | 235 | 17 | -0,1 | 1,8 | -13,2 | 1066,1 | -1,6 | 210,6 | 3/5 |
| keine Änderung | alle Tage | 502 | 29 | -0,7 | -2,2 | -6,1 | 505,2 | -1,4 | 99,0 | 4/5 |
| Sprung +20 % | vor Cutover | 198 | 5 | -1,6 | 0,0 | 0,0 | -0,1 | 2,4 | 0,1 | 2/5 |
| Sprung +20 % | Tag 0-13 | 69 | 11 | 10,2 | -3,7 | 0,0 | 9,9 | -0,4 | 3,2 | 2/5 |
| Sprung +20 % | ab Tag 14 | 235 | 13 | 0,4 | 1,0 | 10,4 | 1,7 | -1,0 | 2,5 | 1/5 |
| Sprung +20 % | alle Tage | 502 | 29 | 0,9 | -0,0 | 4,8 | 2,2 | 0,4 | 1,6 | 1/5 |

## Hinweise

- replay trifft SYS2 an 100,0 % der Tage
- Tagesfehler wie in Teil 1: Tage mit unvollständig bewerteten Stunden zählen dort nicht mit
