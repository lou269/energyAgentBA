# K3 Teil 2, Spitzen-Tage für Prophet ausblenden, Lauf k3_mask_001

## Setup

- Cutover: CO1 (2014-07-31), CO2 (2015-02-12), CO3 (2015-05-24), CO4 (2015-09-26), CO5 (2016-01-12)
- Ereignis: Spitze +670 W über 6 h an Tag 0, 10, 20 nach dem Cutover (Orakel, ohne Einordnung)
- Vergleich: Ereignistage für Prophet ausgeblendet (mask) gegen nicht ausgeblendet (none), 30 Tage Trainingsfenster
- Commit: af277a8 (mit lokalen Änderungen)

## Kennzahlen MAE

| Kennzahl | Wert | Bezug |
|---|---|---|
| Ausblenden bei Spitze +670 W über 6 h: MAE-Differenz [W] | -3,8 | bei 177,0 W ohne Ausblenden, 250 Tage, bei 5/5 Cutover besser |

## MAE mask minus none je Cutover [W], negativ = besser

| Ereignis | Tage | 2014-07-31 | 2015-02-12 | 2015-05-24 | 2015-09-26 | 2016-01-12 | Mittel | Cutover besser |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| Spitze +670 W über 6 h | 250 | -2,2 | -5,6 | -3,8 | -1,6 | -5,8 | -3,8 | 5/5 |

## Kennzahlen Tagesfehler

| Kennzahl | Wert | Bezug |
|---|---|---|
| Ausblenden bei Spitze +670 W über 6 h: Tagesfehler-Differenz [W] | -1,8 | bei 83,6 W ohne Ausblenden, 250 Tage, bei 5/5 Cutover besser |

## Tagesfehler mask minus none je Cutover [W], negativ = besser

| Ereignis | Tage | 2014-07-31 | 2015-02-12 | 2015-05-24 | 2015-09-26 | 2016-01-12 | Mittel | Cutover besser |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| Spitze +670 W über 6 h | 250 | -2,5 | -2,6 | -1,5 | -1,6 | -1,0 | -1,8 | 5/5 |

## Hinweise

- mask minus none: negativ = Ausblenden besser, beide gegen dieselbe Reihe mit Spitzen bewertet, ausgeblendet ist nur das Training
- Tagesfehler wie in Teil 1: Tage mit unvollständig bewerteten Stunden zählen dort nicht mit
