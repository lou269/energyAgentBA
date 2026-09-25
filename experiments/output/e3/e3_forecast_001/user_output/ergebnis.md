# E3 Prognose mit und ohne Jahressaisonalität, Lauf e3_forecast_001

## Setup

- Auswertung: 365 Tage ab 2014-04-15, je Tag eine 24-h-Prognose, Historie ab Datenbeginn
- Varianten: C3_30 rolling 30 Tage, C2 expanding, S1 expanding + Jahressaison
- Naive Referenz: B2 naiv, Vortag
- Commit: 3bef76f (mit lokalen Änderungen)

## Kennzahlen

| Kennzahl | Wert | Bezug |
|---|---|---|
| S1 − C2: MAE-Differenz über das Jahr [W] | 0,5 | negativ = Variante besser, belastbar nein |
| C2 − C3_30: MAE-Differenz über das Jahr [W] | 0,7 | negativ = Variante besser, belastbar nein |
| S1 − C3_30: MAE-Differenz über das Jahr [W] | 1,2 | negativ = Variante besser, belastbar nein |

## MAE je Monat [W]

| Monat | C3_30 rolling 30 Tage | C2 expanding | S1 expanding + Jahressaison | B2 naiv, Vortag |
|---|---:|---:|---:|---:|
| 2014-04 | 152,4 | 136,1 | 143,3 | 207,5 |
| 2014-05 | 111,8 | 119,5 | 114,8 | 157,0 |
| 2014-06 | 113,9 | 105,2 | 107,8 | 137,4 |
| 2014-07 | 120,8 | 114,9 | 116,2 | 159,3 |
| 2014-08 | 127,2 | 122,2 | 126,1 | 139,8 |
| 2014-09 | 133,3 | 131,7 | 132,5 | 176,1 |
| 2014-10 | 142,7 | 146,9 | 143,5 | 195,3 |
| 2014-11 | 159,7 | 159,3 | 160,5 | 196,1 |
| 2014-12 | 164,5 | 189,8 | 191,0 | 198,4 |
| 2015-01 | 165,5 | 169,1 | 167,6 | 196,1 |
| 2015-02 | 160,8 | 159,4 | 160,9 | 225,9 |
| 2015-03 | 179,3 | 173,6 | 174,3 | 245,8 |
| 2015-04 | 157,0 | 164,6 | 163,3 | 184,7 |
| Jahr | 144,5 | 145,2 | 145,7 | 185,2 |

## Gepaarte Differenzen über das Jahr, je Prognosetag

| Vergleich | Differenz [W] | 2 Standardfehler [W] | Tage | Tage besser [%] | belastbar |
|---|---:|---:|---:|---:|---|
| S1 − C2 | 0,5 | 1,7 | 364 | 45,6 | nein |
| C2 − C3_30 | 0,7 | 4,9 | 364 | 51,6 | nein |
| S1 − C3_30 | 1,2 | 4,2 | 364 | 50,5 | nein |

## Hinweise

- S1 − C2 ist der Effekt der Jahressaisonalität allein, C2 − C3_30 der der längeren Historie
- Monat 2014-04 und 2015-04 sind je ein halber Monat
- belastbar: Betrag der Differenz größer als 2 Standardfehler der gepaarten Differenzen, grobe Faustregel

![e3_mae_by_month.png](e3_mae_by_month.png)
