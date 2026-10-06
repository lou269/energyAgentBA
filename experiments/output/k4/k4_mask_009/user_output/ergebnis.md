# K4 Teil 2, peak/low für Prophet ausblenden, Lauf k4_mask_009

## Setup

- Cutover: CO1 (2014-07-15), CO2 (2014-10-24), CO3 (2015-03-01), CO4 (2015-06-10), CO5 (2015-10-22)
- Entscheidungen: SYS2, danach zweimal nachgespielt: nur Resets (replay) und zusätzlich ausgeblendet (mask)
- Commit: 83b23e4 (mit lokalen Änderungen)

## Kennzahlen MAE

| Kennzahl | Wert | Bezug |
|---|---|---|
| Ausblenden, Szenario keine Änderung: MAE-Differenz [W] | -0,0 | bei 159,3 W ohne Ausblenden, 29 von 503 Tagen ausgeblendet, bei 3/5 Cutover besser |
| Ausblenden, Szenario Sprung +20 %: MAE-Differenz [W] | -1,8 | bei 179,0 W ohne Ausblenden, 23 von 503 Tagen ausgeblendet, bei 4/5 Cutover besser |

## MAE mask minus replay je Cutover [W], negativ = besser

| Ereignis | Zeitraum | Tage | ausgeblendet | 2014-07-15 | 2014-10-24 | 2015-03-01 | 2015-06-10 | 2015-10-22 | Mittel | Cutover besser |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| keine Änderung | vor Cutover | 199 | 6 | -2,7 | -0,0 | 0,0 | -0,3 | -2,0 | -1,0 | 4/5 |
| keine Änderung | Tag 0-13 | 69 | 7 | -0,3 | -4,9 | 0,0 | -4,0 | -0,6 | -2,0 | 4/5 |
| keine Änderung | ab Tag 14 | 235 | 16 | 0,7 | -7,9 | 12,6 | 5,0 | -3,5 | 1,4 | 2/5 |
| keine Änderung | alle Tage | 503 | 29 | -0,8 | -4,4 | 5,9 | 1,7 | -2,5 | -0,0 | 3/5 |
| Sprung +20 % | vor Cutover | 199 | 6 | -2,7 | -0,0 | 0,0 | -0,3 | -2,0 | -1,0 | 4/5 |
| Sprung +20 % | Tag 0-13 | 69 | 10 | -12,0 | 0,8 | 0,0 | -4,4 | -9,6 | -5,0 | 3/5 |
| Sprung +20 % | ab Tag 14 | 235 | 7 | -1,0 | -8,8 | 3,1 | -1,3 | -0,1 | -1,6 | 4/5 |
| Sprung +20 % | alle Tage | 503 | 23 | -3,1 | -4,0 | 1,5 | -1,3 | -2,1 | -1,8 | 4/5 |

## Kennzahlen Tagesfehler

| Kennzahl | Wert | Bezug |
|---|---|---|
| Ausblenden, Szenario keine Änderung: Tagesfehler-Differenz [W] | 0,6 | bei 68,9 W ohne Ausblenden, 29 von 503 Tagen ausgeblendet, bei 2/5 Cutover besser |
| Ausblenden, Szenario Sprung +20 %: Tagesfehler-Differenz [W] | -0,2 | bei 79,2 W ohne Ausblenden, 23 von 503 Tagen ausgeblendet, bei 2/5 Cutover besser |

## Tagesfehler mask minus replay je Cutover [W], negativ = besser

| Ereignis | Zeitraum | Tage | ausgeblendet | 2014-07-15 | 2014-10-24 | 2015-03-01 | 2015-06-10 | 2015-10-22 | Mittel | Cutover besser |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| keine Änderung | vor Cutover | 199 | 6 | -1,7 | -0,1 | 0,0 | 0,4 | -0,0 | -0,3 | 3/5 |
| keine Änderung | Tag 0-13 | 69 | 7 | -0,2 | -19,1 | 0,0 | 2,4 | -2,2 | -3,8 | 3/5 |
| keine Änderung | ab Tag 14 | 235 | 16 | 0,3 | 0,7 | 3,9 | 6,5 | 1,9 | 2,7 | 0/5 |
| keine Änderung | alle Tage | 503 | 29 | -0,6 | -2,4 | 1,8 | 3,5 | 0,6 | 0,6 | 2/5 |
| Sprung +20 % | vor Cutover | 199 | 6 | -1,7 | -0,1 | 0,0 | 0,4 | -0,0 | -0,3 | 3/5 |
| Sprung +20 % | Tag 0-13 | 69 | 10 | -1,4 | -20,3 | 0,0 | 16,8 | 4,6 | -0,0 | 2/5 |
| Sprung +20 % | ab Tag 14 | 235 | 7 | -1,0 | -3,0 | 2,3 | 0,4 | 0,3 | -0,2 | 2/5 |
| Sprung +20 % | alle Tage | 503 | 23 | -1,3 | -4,3 | 1,1 | 2,7 | 0,8 | -0,2 | 2/5 |

## Hinweise

- replay trifft SYS2 an 100,0 % der Tage
- Tagesfehler wie in Teil 1: Tage mit unvollständig bewerteten Stunden zählen dort nicht mit
