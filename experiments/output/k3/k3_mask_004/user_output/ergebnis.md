# K3 Teil 2, Spitzen-Tage für Prophet ausblenden, Lauf k3_mask_004

## Setup

- Cutover: CO1 (2014-07-31), CO2 (2015-02-12), CO3 (2015-05-24), CO4 (2015-09-26), CO5 (2016-01-12)
- Ereignis: Spitze +670 W über 6 h an Tag 0, 8, 17 nach dem Cutover (Orakel, ohne Einordnung)
- Vergleich: Ereignistage für Prophet ausgeblendet (mask) gegen nicht ausgeblendet (none), 60 Tage Trainingsfenster
- Commit: 83412b7 (mit lokalen Änderungen)

## Kennzahlen MAE

| Kennzahl | Wert | Bezug |
|---|---|---|
| Ausblenden bei Spitze +670 W über 6 h: MAE-Differenz [W] | -2,4 | bei 171,7 W ohne Ausblenden, 300 Tage, bei 3/5 Cutover besser |

## MAE mask minus none je Cutover [W], negativ = besser

| Ereignis | Tage | 2014-07-31 | 2015-02-12 | 2015-05-24 | 2015-09-26 | 2016-01-12 | Mittel | Cutover besser |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| Spitze +670 W über 6 h | 300 | 1,5 | -5,2 | 0,6 | -3,9 | -5,1 | -2,4 | 3/5 |

## Kennzahlen Tagesfehler

| Kennzahl | Wert | Bezug |
|---|---|---|
| Ausblenden bei Spitze +670 W über 6 h: Tagesfehler-Differenz [W] | 0,6 | bei 76,8 W ohne Ausblenden, 300 Tage, bei 2/5 Cutover besser |

## Tagesfehler mask minus none je Cutover [W], negativ = besser

| Ereignis | Tage | 2014-07-31 | 2015-02-12 | 2015-05-24 | 2015-09-26 | 2016-01-12 | Mittel | Cutover besser |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| Spitze +670 W über 6 h | 300 | 1,0 | -1,1 | 3,1 | -0,9 | 0,7 | 0,6 | 2/5 |

## Hinweise

- mask minus none: negativ = Ausblenden besser, beide gegen dieselbe Reihe mit Spitzen bewertet, ausgeblendet ist nur das Training
- Tagesfehler wie in Teil 1: Tage mit unvollständig bewerteten Stunden zählen dort nicht mit
