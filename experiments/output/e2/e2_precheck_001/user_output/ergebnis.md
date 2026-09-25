# E2 Vorprüfung Gate, Lauf e2_precheck_001

## Setup

- Abwesenheit: vacation-2013-06, 2013-06-06 bis vor 2013-06-13
- Systeme: SYS1, SYS2
- Tage nach der Rückkehr: 30
- Commit: 15a8a44 (mit lokalen Änderungen)

## Erste Tage ab Urlaubsbeginn

| System | Gate offen [Urlaubstag] | Drift [Urlaubstag] | Reset [Urlaubstag] |
|---|---:|---:|---:|
| SYS1 | - | - | - |
| SYS2 | 13 | - | - |

## Gate und Einordnung je Phase

| System | Phase | Tage | Gate offen | davon Einzeltag | davon Drift | new_pattern | low | peak | Resets | Meldungen | MAE [W] |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| SYS1 | Urlaub | 7 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 80,5 |
| SYS1 | nach der Rückkehr | 30 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 94,7 |
| SYS1 | vor dem Urlaub | 8 | 4 | 0 | 4 | 0 | 0 | 0 | 0 | 0 | 104,6 |
| SYS2 | Urlaub | 7 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 79,3 |
| SYS2 | nach der Rückkehr | 30 | 5 | 5 | 0 | 0 | 3 | 2 | 0 | 5 | 96,9 |
| SYS2 | vor dem Urlaub | 8 | 2 | 1 | 1 | 1 | 0 | 1 | 1 | 2 | 116,0 |

## Hinweise

- Urlaubstag = analysierter Tag seit Beginn der Abwesenheit, 0 = erster Urlaubstag
- Gate Einzeltag: daily/weekday über unusual_threshold, Gate Drift: sustained_drift (Streak auf mindestens zwei Skalen)
- Reset = new_pattern mit advance_history_start, bei SYS1 nie

## Anhang

### Je Tag ab Urlaubsbeginn

| System | Urlaubstag | Datum | Phase | Tagesmittel [W] | erwartet Wochentag [W] | z daily | z weekday | z weekly | z long_term | Streak weekly | Streak long_term | Level | Drift | Einordnung | Adaption | MAE [W] |
|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---|---|---:|
| SYS1 | 0 | 2013-06-06 | Urlaub | 182,9 | 285,0 | -0,7 | -0,4 | -0,2 | -1,8 | 3,0 | 7,0 | normal | False | - | none | 99,6 |
| SYS1 | 1 | 2013-06-07 | Urlaub | 180,0 | 281,6 | -0,8 | -0,4 | -0,3 | -1,8 | 2,0 | 7,0 | normal | False | - | none | 43,7 |
| SYS1 | 2 | 2013-06-08 | Urlaub | 193,9 | 312,0 | -0,8 | -0,6 | -0,2 | -1,7 | 1,0 | 7,0 | normal | False | - | none | 41,3 |
| SYS1 | 3 | 2013-06-09 | Urlaub | 205,4 | 317,2 | -0,7 | -0,5 | -0,6 | -1,8 | 0,0 | 7,0 | normal | False | - | none | 45,0 |
| SYS1 | 4 | 2013-06-10 | Urlaub | 179,0 | 258,3 | -1,0 | -0,2 | -0,7 | -2,0 | 0,0 | 7,0 | normal | False | - | none | 47,0 |
| SYS1 | 5 | 2013-06-11 | Urlaub | 172,5 | 279,7 | -0,8 | -0,5 | -0,9 | -2,1 | 0,0 | 7,0 | normal | False | - | none | 50,3 |
| SYS1 | 6 | 2013-06-12 | Urlaub | 211,5 | 285,8 | -0,8 | -0,2 | -1,2 | -2,0 | 0,0 | 7,0 | normal | False | - | none | 237,0 |
| SYS1 | 7 | 2013-06-13 | nach der Rückkehr | 415,4 | 259,2 | 0,8 | 2,2 | -0,5 | -1,8 | 0,0 | 7,0 | normal | False | - | none | 78,2 |
| SYS1 | 8 | 2013-06-14 | nach der Rückkehr | 174,7 | 265,9 | -0,9 | -0,4 | -0,4 | -2,0 | 0,0 | 7,0 | normal | False | - | none | 65,7 |
| SYS1 | 9 | 2013-06-15 | nach der Rückkehr | 151,5 | 278,9 | -1,2 | -0,7 | -0,5 | -2,2 | 0,0 | 7,0 | normal | False | - | none | 43,4 |
| SYS1 | 10 | 2013-06-16 | nach der Rückkehr | 178,6 | 299,2 | -0,8 | -0,7 | -0,6 | -2,4 | 0,0 | 7,0 | normal | False | - | none | 72,4 |
| SYS1 | 11 | 2013-06-17 | nach der Rückkehr | 223,0 | 245,5 | 0,0 | 0,3 | -0,4 | -2,6 | 0,0 | 7,0 | normal | False | - | none | 130,3 |
| SYS1 | 12 | 2013-06-18 | nach der Rückkehr | 301,0 | 254,6 | 0,6 | 1,0 | -0,0 | -2,6 | 0,0 | 7,0 | normal | False | - | none | 200,1 |
| SYS1 | 13 | 2013-06-19 | nach der Rückkehr | 388,0 | 272,6 | 2,3 | 1,8 | 0,5 | -2,3 | 0,0 | 7,0 | normal | False | - | none | 86,4 |
| SYS1 | 14 | 2013-06-20 | nach der Rückkehr | 206,6 | 267,1 | -0,3 | 0,0 | -0,0 | -2,4 | 0,0 | 7,0 | normal | False | - | none | 62,8 |
| SYS1 | 15 | 2013-06-21 | nach der Rückkehr | 200,3 | 247,9 | -0,4 | 0,1 | 0,0 | -2,3 | 0,0 | 7,0 | normal | False | - | none | 63,9 |
| SYS1 | 16 | 2013-06-22 | nach der Rückkehr | 219,6 | 256,2 | -0,1 | 0,2 | 0,2 | -2,1 | 0,0 | 7,0 | normal | False | - | none | 130,1 |
| SYS1 | 17 | 2013-06-23 | nach der Rückkehr | 316,0 | 280,6 | 0,7 | 1,0 | 0,7 | -1,6 | 0,0 | 7,0 | normal | False | - | none | 81,9 |
| SYS1 | 18 | 2013-06-24 | nach der Rückkehr | 204,5 | 230,1 | -0,3 | 0,4 | 0,6 | -1,4 | 0,0 | 7,0 | normal | False | - | none | 50,8 |
| SYS1 | 19 | 2013-06-25 | nach der Rückkehr | 237,3 | 260,0 | -0,4 | 0,5 | 0,4 | -1,2 | 0,0 | 7,0 | normal | False | - | none | 77,7 |
| SYS1 | 20 | 2013-06-26 | nach der Rückkehr | 283,6 | 287,7 | 0,4 | 0,7 | 0,1 | -0,9 | 0,0 | 6,0 | normal | False | - | none | 74,3 |
| SYS1 | 21 | 2013-06-27 | nach der Rückkehr | 217,0 | 257,0 | -0,2 | 0,3 | 0,2 | -0,7 | 0,0 | 4,0 | normal | False | - | none | 162,5 |
| SYS1 | 22 | 2013-06-28 | nach der Rückkehr | 362,0 | 228,4 | 1,3 | 2,2 | 0,6 | -0,3 | 0,0 | 3,0 | normal | False | - | none | 102,5 |
| SYS1 | 23 | 2013-06-29 | nach der Rückkehr | 289,0 | 243,0 | 0,5 | 1,2 | 0,8 | 0,0 | 0,0 | 2,0 | normal | False | - | none | 96,2 |
| SYS1 | 24 | 2013-06-30 | nach der Rückkehr | 264,2 | 279,6 | 0,4 | 0,4 | 0,7 | 0,1 | 0,0 | 1,0 | normal | False | - | none | 97,9 |
| SYS1 | 25 | 2013-07-01 | nach der Rückkehr | 297,9 | 218,1 | 0,3 | 1,4 | 1,0 | 0,3 | 0,0 | 0,0 | normal | False | - | none | 99,3 |
| SYS1 | 26 | 2013-07-02 | nach der Rückkehr | 281,9 | 258,1 | 0,2 | 0,6 | 1,1 | 0,3 | 0,0 | 0,0 | normal | False | - | none | 88,1 |
| SYS1 | 27 | 2013-07-03 | nach der Rückkehr | 302,0 | 278,9 | 0,3 | 0,6 | 1,2 | 0,5 | 0,0 | 0,0 | normal | False | - | none | 135,5 |
| SYS1 | 28 | 2013-07-04 | nach der Rückkehr | 319,3 | 238,6 | 0,9 | 1,2 | 1,4 | 0,6 | 1,0 | 0,0 | normal | False | - | none | 97,8 |
| SYS1 | 29 | 2013-07-05 | nach der Rückkehr | 278,3 | 241,8 | 0,4 | 0,6 | 1,1 | 0,6 | 1,0 | 0,0 | normal | False | - | none | 130,7 |
| SYS1 | 30 | 2013-07-06 | nach der Rückkehr | 280,9 | 245,2 | 0,6 | 0,5 | 1,1 | 0,8 | 1,0 | 0,0 | normal | False | - | none | 69,6 |
| SYS1 | 31 | 2013-07-07 | nach der Rückkehr | 217,4 | 267,2 | -0,5 | -0,6 | 0,9 | 0,8 | 1,0 | 0,0 | normal | False | - | none | 121,5 |
| SYS1 | 32 | 2013-07-08 | nach der Rückkehr | 271,9 | 226,0 | 0,7 | 0,6 | 0,8 | 1,0 | 0,0 | 0,0 | normal | False | - | none | 98,7 |
| SYS1 | 33 | 2013-07-09 | nach der Rückkehr | 143,1 | 267,7 | -1,2 | -1,7 | 0,4 | 0,9 | 0,0 | 0,0 | normal | False | - | none | 50,1 |
| SYS1 | 34 | 2013-07-10 | nach der Rückkehr | 138,2 | 283,4 | -1,1 | -1,9 | -0,1 | 0,8 | 0,0 | 0,0 | normal | False | - | none | 34,5 |
| SYS1 | 35 | 2013-07-11 | nach der Rückkehr | 137,1 | 252,5 | -1,1 | -1,5 | -0,6 | 0,8 | 0,0 | 1,0 | normal | False | - | none | 135,1 |
| SYS1 | 36 | 2013-07-12 | nach der Rückkehr | 261,8 | 236,5 | 0,2 | 0,3 | -0,6 | 0,9 | 0,0 | 1,0 | normal | False | - | none | 103,3 |
| SYS2 | 0 | 2013-06-06 | Urlaub | 182,9 | - | -0,7 | - | 3,6 | - | 3,0 | - | normal | False | normal | none | 78,3 |
| SYS2 | 1 | 2013-06-07 | Urlaub | 180,0 | - | -1,0 | - | 1,9 | - | 3,0 | - | normal | False | normal | none | 44,4 |
| SYS2 | 2 | 2013-06-08 | Urlaub | 193,9 | - | -1,2 | - | 0,8 | - | 1,0 | - | normal | False | normal | none | 46,8 |
| SYS2 | 3 | 2013-06-09 | Urlaub | 205,4 | - | -1,1 | - | -0,7 | - | 0,0 | - | normal | False | normal | none | 41,3 |
| SYS2 | 4 | 2013-06-10 | Urlaub | 179,0 | - | -1,2 | - | -1,2 | - | 1,0 | - | normal | False | normal | none | 50,2 |
| SYS2 | 5 | 2013-06-11 | Urlaub | 172,5 | - | -0,9 | - | -2,3 | - | 4,0 | - | normal | False | normal | none | 53,1 |
| SYS2 | 6 | 2013-06-12 | Urlaub | 211,5 | - | -0,9 | - | -2,9 | - | 3,0 | - | normal | False | normal | none | 240,7 |
| SYS2 | 7 | 2013-06-13 | nach der Rückkehr | 415,4 | - | 0,9 | - | -1,0 | - | 2,0 | - | normal | False | normal | none | 123,8 |
| SYS2 | 8 | 2013-06-14 | nach der Rückkehr | 174,7 | - | -1,0 | - | -0,8 | - | 2,0 | - | normal | False | normal | none | 80,7 |
| SYS2 | 9 | 2013-06-15 | nach der Rückkehr | 151,5 | - | -1,3 | - | -0,8 | - | 1,0 | - | normal | False | normal | none | 43,8 |
| SYS2 | 10 | 2013-06-16 | nach der Rückkehr | 178,6 | - | -0,9 | - | -0,9 | - | 2,0 | - | normal | False | normal | none | 70,9 |
| SYS2 | 11 | 2013-06-17 | nach der Rückkehr | 223,0 | - | 0,0 | - | -0,7 | - | 1,0 | - | normal | False | normal | none | 132,9 |
| SYS2 | 12 | 2013-06-18 | nach der Rückkehr | 301,0 | - | 0,8 | - | 0,1 | - | 1,0 | - | normal | False | normal | none | 197,0 |
| SYS2 | 13 | 2013-06-19 | nach der Rückkehr | 388,0 | - | 2,7 | - | 1,2 | - | 0,0 | - | unusual | False | peak | none | 91,8 |
| SYS2 | 14 | 2013-06-20 | nach der Rückkehr | 206,6 | - | -0,2 | - | -0,0 | - | 1,0 | - | normal | False | normal | none | 65,6 |
| SYS2 | 15 | 2013-06-21 | nach der Rückkehr | 200,3 | - | -0,5 | - | 0,1 | - | 0,0 | - | normal | False | normal | none | 62,2 |
| SYS2 | 16 | 2013-06-22 | nach der Rückkehr | 219,6 | 165,6 | -0,3 | - | 0,3 | -0,3 | 0,0 | 0,0 | normal | False | normal | none | 128,7 |
| SYS2 | 17 | 2013-06-23 | nach der Rückkehr | 316,0 | 218,1 | 0,6 | - | 1,2 | 0,5 | 0,0 | 1,0 | normal | False | normal | none | 81,9 |
| SYS2 | 18 | 2013-06-24 | nach der Rückkehr | 204,5 | 183,4 | -0,4 | - | 1,1 | 1,5 | 0,0 | 2,0 | normal | False | normal | none | 50,8 |
| SYS2 | 19 | 2013-06-25 | nach der Rückkehr | 237,3 | 216,7 | -0,5 | - | 0,6 | 2,9 | 1,0 | 3,0 | normal | False | normal | none | 77,7 |
| SYS2 | 20 | 2013-06-26 | nach der Rückkehr | 283,6 | 266,1 | 0,2 | - | -0,3 | 5,0 | 0,0 | 3,0 | normal | False | normal | none | 74,3 |
| SYS2 | 21 | 2013-06-27 | nach der Rückkehr | 217,0 | 239,7 | -0,5 | - | -0,3 | 5,8 | 0,0 | 4,0 | normal | False | normal | none | 162,5 |
| SYS2 | 22 | 2013-06-28 | nach der Rückkehr | 362,0 | 199,1 | 1,2 | 3,1 | 0,7 | 7,1 | 0,0 | 5,0 | strong_anomaly | False | peak | none | 102,5 |
| SYS2 | 23 | 2013-06-29 | nach der Rückkehr | 289,0 | 176,4 | 0,4 | 2,0 | 1,2 | 5,8 | 0,0 | 4,0 | normal | False | normal | none | 96,2 |
| SYS2 | 24 | 2013-06-30 | nach der Rückkehr | 264,2 | 237,7 | 0,3 | -0,1 | 0,8 | 4,4 | 0,0 | 5,0 | normal | False | normal | none | 97,9 |
| SYS2 | 25 | 2013-07-01 | nach der Rückkehr | 297,9 | 187,6 | 0,1 | 1,0 | 1,4 | 3,4 | 1,0 | 5,0 | normal | False | normal | none | 99,3 |
| SYS2 | 26 | 2013-07-02 | nach der Rückkehr | 281,9 | 220,8 | 0,0 | 0,1 | 1,6 | 2,0 | 2,0 | 5,0 | normal | False | normal | none | 88,1 |
| SYS2 | 27 | 2013-07-03 | nach der Rückkehr | 302,0 | 269,6 | 0,0 | -0,4 | 1,7 | 2,0 | 2,0 | 6,0 | normal | False | normal | none | 135,5 |
| SYS2 | 28 | 2013-07-04 | nach der Rückkehr | 319,3 | 235,1 | 0,7 | 0,4 | 2,3 | 1,8 | 3,0 | 7,0 | normal | False | normal | none | 97,8 |
| SYS2 | 29 | 2013-07-05 | nach der Rückkehr | 278,3 | 231,7 | 0,1 | -0,2 | 1,5 | 1,3 | 4,0 | 7,0 | normal | False | normal | none | 130,7 |
| SYS2 | 30 | 2013-07-06 | nach der Rückkehr | 280,9 | 195,2 | 0,2 | 0,5 | 1,3 | 1,5 | 5,0 | 6,0 | normal | False | normal | none | 69,6 |
| SYS2 | 31 | 2013-07-07 | nach der Rückkehr | 217,4 | 242,1 | -0,9 | -1,7 | 0,8 | 1,4 | 1,0 | 5,0 | normal | False | normal | none | 121,5 |
| SYS2 | 32 | 2013-07-08 | nach der Rückkehr | 271,9 | 206,0 | 0,6 | 0,1 | 0,5 | 1,5 | 1,0 | 5,0 | normal | False | normal | none | 98,7 |
| SYS2 | 33 | 2013-07-09 | nach der Rückkehr | 143,1 | 231,0 | -1,8 | -3,1 | -0,5 | 1,1 | 1,0 | 5,0 | strong_anomaly | False | low | none | 50,1 |
| SYS2 | 34 | 2013-07-10 | nach der Rückkehr | 138,2 | 275,0 | -1,8 | -3,8 | -1,7 | 0,7 | 2,0 | 2,0 | strong_anomaly | False | low | none | 34,5 |
| SYS2 | 35 | 2013-07-11 | nach der Rückkehr | 137,1 | 249,2 | -1,8 | -3,4 | -3,0 | 0,4 | 2,0 | 1,0 | strong_anomaly | False | low | none | 135,1 |
| SYS2 | 36 | 2013-07-12 | nach der Rückkehr | 261,8 | 239,5 | -0,2 | -0,4 | -3,2 | 0,5 | 3,0 | 1,0 | normal | False | normal | none | 103,3 |
