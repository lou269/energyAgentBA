# K4 Teil 2: Jahressaisonalität

## Setup

- Lauf: k4_season_001
- Auswertung: 365 Tage ab 2014-04-02 (validation), je Tag eine 24-h-Prognose, Historie ab Datenbeginn
- Varianten: C3_60 rolling 60 Tage, C2 expanding, Y1 expanding + Jahressaison
- Naive Referenz: B2 naiv, Vortag
- Commit: 32b0600 (mit lokalen Änderungen)

## Tagesfehler je Monat [W]

| Monat | C3_60 rolling 60 Tage | C2 expanding | Y1 expanding + Jahressaison | B2 naiv, Vortag |
|---|---:|---:|---:|---:|
| 2014-04 | 76,5 | 67,7 | 74,4 | 86,0 |
| 2014-05 | 57,3 | 65,4 | 58,2 | 62,4 |
| 2014-06 | 73,5 | 61,2 | 61,3 | 64,6 |
| 2014-07 | 65,3 | 67,2 | 61,7 | 77,3 |
| 2014-08 | 91,8 | 88,1 | 85,9 | 70,4 |
| 2014-09 | 53,7 | 53,1 | 51,6 | 76,9 |
| 2014-10 | 46,0 | 53,4 | 41,1 | 44,7 |
| 2014-11 | 76,1 | 64,4 | 71,9 | 85,1 |
| 2014-12 | 85,6 | 104,4 | 107,9 | 83,6 |
| 2015-01 | 96,6 | 92,9 | 84,5 | 70,0 |
| 2015-02 | 62,1 | 57,0 | 58,4 | 88,7 |
| 2015-03 | 75,9 | 69,3 | 69,7 | 90,4 |
| 2015-04 | 25,4 | 33,6 | 55,4 | 69,9 |
| Jahr | 71,7 | 70,5 | 69,0 | 74,8 |

## Gepaarte Differenzen über das Jahr, je Prognosetag

| Vergleich | Differenz [W] | 2 Standardfehler [W] | Tage | Tage besser [%] | belastbar |
|---|---:|---:|---:|---:|---|
| Y1 − C2 | −1,5 | 3,5 | 364 | 54,9 | nein |
| C2 − C3_60 | −1,2 | 5,9 | 364 | 53,6 | nein |
| Y1 − C3_60 | −2,7 | 4,8 | 364 | 54,1 | nein |

## Hinweise

- Y1 − C2 ist der Effekt der Jahressaisonalität allein, C2 − C3_60 der der längeren Historie
- Monat 2014-04 und 2015-04 sind je ein halber Monat
- belastbar: Betrag der Differenz größer als 2 Standardfehler der gepaarten Differenzen, grobe Faustregel
