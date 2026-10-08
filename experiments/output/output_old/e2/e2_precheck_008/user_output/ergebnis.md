# E2 Vorprüfung Gate, Lauf e2_precheck_008

## Setup

- Urlaub vacation-2014-08: 2014-08-03 bis vor 2014-08-17
- Urlaub vacation-2015-10: 2015-10-04 bis vor 2015-10-25
- Systeme: SYS1, SYS2
- Tage nach der Rückkehr: 30
- Commit: b7f296d (mit lokalen Änderungen)

## vacation-2014-08: Erste Tage ab Urlaubsbeginn

| System | Gate offen [Urlaubstag] | Drift [Urlaubstag] | Reset [Urlaubstag] |
|---|---:|---:|---:|
| SYS1 | 5 | 15 | - |
| SYS2 | 5 | 15 | 15 |

## vacation-2014-08: Gate und Einordnung je Phase

| System | Phase | Tage | Gate offen | davon Einzeltag | davon Drift | davon nur eine Skala | new_pattern | low | peak | absence | Resets | Meldungen | Ausfalltage | MAE [W] |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| SYS1 | vor dem Urlaub | 31 | 11 | 0 | 0 | 10 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 123,9 |
| SYS1 | Urlaub | 14 | 9 | 0 | 0 | 9 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 45,5 |
| SYS1 | nach der Rückkehr | 30 | 21 | 0 | 2 | 19 | 2 | 0 | 0 | 0 | 0 | 2 | 0 | 144,4 |
| SYS2 | vor dem Urlaub | 31 | 11 | 0 | 0 | 10 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 123,9 |
| SYS2 | Urlaub | 14 | 9 | 0 | 0 | 9 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 45,5 |
| SYS2 | nach der Rückkehr | 30 | 15 | 3 | 1 | 11 | 1 | 0 | 3 | 0 | 1 | 4 | 0 | 143,8 |

## vacation-2015-10: Erste Tage ab Urlaubsbeginn

| System | Gate offen [Urlaubstag] | Drift [Urlaubstag] | Reset [Urlaubstag] |
|---|---:|---:|---:|
| SYS1 | 9 | 13 | - |
| SYS2 | 9 | 13 | 13 |

## vacation-2015-10: Gate und Einordnung je Phase

| System | Phase | Tage | Gate offen | davon Einzeltag | davon Drift | davon nur eine Skala | new_pattern | low | peak | absence | Resets | Meldungen | Ausfalltage | MAE [W] |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| SYS1 | vor dem Urlaub | 31 | 14 | 0 | 0 | 14 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 130,9 |
| SYS1 | Urlaub | 21 | 12 | 0 | 8 | 4 | 8 | 0 | 0 | 0 | 0 | 8 | 0 | 74,7 |
| SYS1 | nach der Rückkehr | 30 | 29 | 1 | 6 | 22 | 6 | 0 | 1 | 0 | 0 | 7 | 0 | 179,5 |
| SYS2 | vor dem Urlaub | 31 | 14 | 0 | 0 | 14 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 130,9 |
| SYS2 | Urlaub | 21 | 7 | 2 | 1 | 4 | 1 | 0 | 2 | 0 | 1 | 3 | 0 | 75,9 |
| SYS2 | nach der Rückkehr | 30 | 28 | 12 | 0 | 16 | 0 | 2 | 10 | 0 | 0 | 10 | 0 | 181,1 |

## Hinweise

- Urlaubstag = analysierter Tag seit Beginn der Abwesenheit, 0 = erster Urlaubstag
- Gate offen: Einzeltag (daily/weekday über ihrer Schwelle), Drift (weekly und long_term halten an) oder nur eine anhaltende Skala
- Reset = new_pattern mit advance_history_start, bei SYS1 nie

## Anhang

### vacation-2014-08: Je Tag ab Urlaubsbeginn

| System | Urlaubstag | Datum | Phase | Tagesmittel [W] | erwartet Wochentag [W] | z daily | z weekday | z weekly | long_term [%] | Streak weekly | Streak long_term | Level | Drift | Einordnung | Adaption | MAE [W] |
|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---|---|---:|
| SYS1 | 0 | 2014-08-03 | Urlaub | 139,0 | 252,1 | -1,8 | -1,6 | -1,0 | 16,8 | 1,0 | 2,0 | normal | False | normal | none | 79,0 |
| SYS1 | 1 | 2014-08-04 | Urlaub | 132,6 | 300,9 | -1,8 | -2,4 | -1,3 | 11,5 | 2,0 | 2,0 | normal | False | normal | none | 41,3 |
| SYS1 | 2 | 2014-08-05 | Urlaub | 135,7 | 299,7 | -1,8 | -2,1 | -1,4 | 10,3 | 3,0 | 2,0 | normal | False | normal | none | 29,3 |
| SYS1 | 3 | 2014-08-06 | Urlaub | 132,8 | 292,3 | -1,6 | -2,0 | -2,2 | 6,0 | 4,0 | 2,0 | normal | False | normal | none | 38,7 |
| SYS1 | 4 | 2014-08-07 | Urlaub | 147,7 | 306,3 | -1,3 | -2,5 | -2,8 | -1,5 | 5,0 | 2,0 | normal | False | normal | none | 32,0 |
| SYS1 | 5 | 2014-08-08 | Urlaub | 138,9 | 293,7 | -1,5 | -1,9 | -3,9 | -5,6 | 6,0 | 2,0 | normal | False | normal | none | 68,2 |
| SYS1 | 6 | 2014-08-09 | Urlaub | 180,8 | 258,3 | -1,1 | -0,9 | -4,0 | -10,1 | 7,0 | 1,0 | normal | False | normal | none | 53,1 |
| SYS1 | 7 | 2014-08-10 | Urlaub | 176,7 | 251,7 | -1,1 | -0,9 | -3,8 | -12,1 | 7,0 | 0,0 | normal | False | normal | none | 21,9 |
| SYS1 | 8 | 2014-08-11 | Urlaub | 159,9 | 300,3 | -1,2 | -1,7 | -3,6 | -13,7 | 7,0 | 0,0 | normal | False | normal | none | 25,8 |
| SYS1 | 9 | 2014-08-12 | Urlaub | 160,6 | 295,4 | -1,2 | -1,6 | -3,4 | -13,9 | 7,0 | 0,0 | normal | False | normal | none | 32,2 |
| SYS1 | 10 | 2014-08-13 | Urlaub | 187,5 | 292,3 | -1,0 | -1,3 | -3,1 | -17,9 | 7,0 | 1,0 | normal | False | normal | none | 28,6 |
| SYS1 | 11 | 2014-08-14 | Urlaub | 184,9 | 306,3 | -1,0 | -1,5 | -2,9 | -19,0 | 7,0 | 2,0 | normal | False | normal | none | 45,8 |
| SYS1 | 12 | 2014-08-15 | Urlaub | 217,5 | 293,7 | -1,0 | -0,9 | -2,4 | -20,2 | 7,0 | 3,0 | normal | False | normal | none | 51,7 |
| SYS1 | 13 | 2014-08-16 | Urlaub | 190,0 | 258,3 | -0,7 | -0,7 | -2,2 | -21,5 | 7,0 | 4,0 | normal | False | normal | none | 89,9 |
| SYS1 | 14 | 2014-08-17 | nach der Rückkehr | 254,3 | 251,7 | 0,0 | 0,0 | -1,8 | -22,0 | 7,0 | 5,0 | normal | False | normal | none | 134,2 |
| SYS1 | 15 | 2014-08-18 | nach der Rückkehr | 336,1 | 280,9 | 0,5 | 0,7 | -1,2 | -20,9 | 7,0 | 6,0 | normal | True | new_pattern | none | 140,0 |
| SYS1 | 16 | 2014-08-19 | nach der Rückkehr | 330,9 | 264,4 | 0,4 | 0,8 | -0,7 | -23,2 | 6,0 | 7,0 | normal | True | new_pattern | none | 116,4 |
| SYS1 | 17 | 2014-08-20 | nach der Rückkehr | 337,8 | 292,3 | 0,6 | 0,5 | -0,2 | -23,2 | 5,0 | 7,0 | normal | False | normal | none | 124,5 |
| SYS1 | 18 | 2014-08-21 | nach der Rückkehr | 269,7 | 297,3 | 0,1 | -0,3 | 0,0 | -25,9 | 4,0 | 7,0 | normal | False | normal | none | 153,3 |
| SYS1 | 19 | 2014-08-22 | nach der Rückkehr | 144,3 | 277,7 | -1,0 | -1,6 | -0,1 | -25,2 | 3,0 | 7,0 | normal | False | normal | none | 91,7 |
| SYS1 | 20 | 2014-08-23 | nach der Rückkehr | 145,8 | 226,6 | -1,0 | -1,0 | -0,2 | -27,4 | 2,0 | 7,0 | normal | False | normal | none | 41,0 |
| SYS1 | 21 | 2014-08-24 | nach der Rückkehr | 135,0 | 246,7 | -1,0 | -1,2 | -0,4 | -31,4 | 1,0 | 7,0 | normal | False | normal | none | 352,4 |
| SYS1 | 22 | 2014-08-25 | nach der Rückkehr | 479,9 | 300,3 | 1,6 | 1,9 | -0,1 | -26,5 | 0,0 | 7,0 | normal | False | normal | none | 208,5 |
| SYS1 | 23 | 2014-08-26 | nach der Rückkehr | 411,8 | 264,4 | 0,8 | 1,5 | 0,1 | -22,0 | 0,0 | 7,0 | normal | False | normal | none | 70,1 |
| SYS1 | 24 | 2014-08-27 | nach der Rückkehr | 288,7 | 309,5 | -0,1 | -0,2 | 0,1 | -23,1 | 0,0 | 7,0 | normal | False | normal | none | 125,6 |
| SYS1 | 25 | 2014-08-28 | nach der Rückkehr | 384,9 | 278,7 | 0,5 | 1,1 | 0,3 | -23,3 | 0,0 | 7,0 | normal | False | normal | none | 161,2 |
| SYS1 | 26 | 2014-08-29 | nach der Rückkehr | 404,8 | 235,6 | 0,8 | 1,6 | 1,0 | -25,3 | 0,0 | 7,0 | normal | False | normal | none | 228,2 |
| SYS1 | 27 | 2014-08-30 | nach der Rückkehr | 239,4 | 205,9 | 0,1 | 0,3 | 1,2 | -25,5 | 1,0 | 7,0 | normal | False | normal | none | 137,7 |
| SYS1 | 28 | 2014-08-31 | nach der Rückkehr | 335,9 | 219,5 | 0,7 | 1,1 | 1,7 | -22,8 | 2,0 | 7,0 | normal | False | normal | none | 147,0 |
| SYS1 | 29 | 2014-09-01 | nach der Rückkehr | 316,0 | 300,3 | 0,6 | 0,1 | 1,4 | -17,9 | 3,0 | 7,0 | normal | False | normal | none | 266,7 |
| SYS1 | 30 | 2014-09-02 | nach der Rückkehr | 479,9 | 264,4 | 2,1 | 2,0 | 1,5 | -12,1 | 4,0 | 6,0 | normal | False | normal | none | 151,7 |
| SYS1 | 31 | 2014-09-03 | nach der Rückkehr | 263,1 | 309,5 | 0,2 | -0,4 | 1,5 | -8,4 | 5,0 | 5,0 | normal | False | normal | none | 108,2 |
| SYS1 | 32 | 2014-09-04 | nach der Rückkehr | 267,9 | 300,0 | 0,1 | -0,3 | 1,2 | -3,2 | 6,0 | 4,0 | normal | False | normal | none | 119,9 |
| SYS1 | 33 | 2014-09-05 | nach der Rückkehr | 280,4 | 277,7 | 0,2 | 0,0 | 0,8 | 1,0 | 6,0 | 3,0 | normal | False | normal | none | 151,0 |
| SYS1 | 34 | 2014-09-06 | nach der Rückkehr | 323,8 | 230,6 | 1,4 | 1,0 | 1,0 | 5,3 | 5,0 | 2,0 | normal | False | normal | none | 133,4 |
| SYS1 | 35 | 2014-09-07 | nach der Rückkehr | 336,2 | 259,3 | 0,8 | 0,7 | 0,9 | 8,9 | 4,0 | 1,0 | normal | False | normal | none | 108,9 |
| SYS1 | 36 | 2014-09-08 | nach der Rückkehr | 315,7 | 300,3 | 0,3 | 0,1 | 0,9 | 13,3 | 3,0 | 0,0 | normal | False | normal | none | 119,9 |
| SYS1 | 37 | 2014-09-09 | nach der Rückkehr | 344,2 | 283,3 | 0,3 | 0,6 | 0,6 | 17,2 | 2,0 | 1,0 | normal | False | normal | none | 90,6 |
| SYS1 | 38 | 2014-09-10 | nach der Rückkehr | 273,0 | 299,2 | -0,1 | -0,2 | 0,6 | 21,9 | 1,0 | 2,0 | normal | False | normal | none | 213,6 |
| SYS1 | 39 | 2014-09-11 | nach der Rückkehr | 437,4 | 278,7 | 1,8 | 1,5 | 0,9 | 27,6 | 0,0 | 3,0 | normal | False | normal | none | 133,8 |
| SYS1 | 40 | 2014-09-12 | nach der Rückkehr | 370,1 | 267,1 | 0,2 | 1,1 | 1,2 | 31,6 | 1,0 | 4,0 | normal | False | normal | none | 100,8 |
| SYS1 | 41 | 2014-09-13 | nach der Rückkehr | 308,1 | 230,6 | 0,0 | 0,6 | 1,1 | 35,6 | 2,0 | 5,0 | normal | False | normal | none | 148,5 |
| SYS1 | 42 | 2014-09-14 | nach der Rückkehr | 376,2 | 280,0 | 0,9 | 0,9 | 1,2 | 38,6 | 3,0 | 6,0 | normal | False | normal | none | 128,4 |
| SYS1 | 43 | 2014-09-15 | nach der Rückkehr | 299,7 | 315,7 | 0,4 | -0,2 | 1,2 | 35,8 | 4,0 | 7,0 | normal | False | normal | none | 123,9 |
| SYS2 | 0 | 2014-08-03 | Urlaub | 139,0 | 252,1 | -1,8 | -1,6 | -1,0 | 16,8 | 1,0 | 2,0 | normal | False | normal | none | 79,0 |
| SYS2 | 1 | 2014-08-04 | Urlaub | 132,6 | 300,9 | -1,8 | -2,4 | -1,3 | 11,5 | 2,0 | 2,0 | normal | False | normal | none | 41,3 |
| SYS2 | 2 | 2014-08-05 | Urlaub | 135,7 | 299,7 | -1,8 | -2,1 | -1,4 | 10,3 | 3,0 | 2,0 | normal | False | normal | none | 29,3 |
| SYS2 | 3 | 2014-08-06 | Urlaub | 132,8 | 292,3 | -1,6 | -2,0 | -2,2 | 6,0 | 4,0 | 2,0 | normal | False | normal | none | 38,7 |
| SYS2 | 4 | 2014-08-07 | Urlaub | 147,7 | 306,3 | -1,3 | -2,5 | -2,8 | -1,5 | 5,0 | 2,0 | normal | False | normal | none | 32,0 |
| SYS2 | 5 | 2014-08-08 | Urlaub | 138,9 | 293,7 | -1,5 | -1,9 | -3,9 | -5,6 | 6,0 | 2,0 | normal | False | normal | none | 68,2 |
| SYS2 | 6 | 2014-08-09 | Urlaub | 180,8 | 258,3 | -1,1 | -0,9 | -4,0 | -10,1 | 7,0 | 1,0 | normal | False | normal | none | 53,1 |
| SYS2 | 7 | 2014-08-10 | Urlaub | 176,7 | 251,7 | -1,1 | -0,9 | -3,8 | -12,1 | 7,0 | 0,0 | normal | False | normal | none | 21,9 |
| SYS2 | 8 | 2014-08-11 | Urlaub | 159,9 | 300,3 | -1,2 | -1,7 | -3,6 | -13,7 | 7,0 | 0,0 | normal | False | normal | none | 25,8 |
| SYS2 | 9 | 2014-08-12 | Urlaub | 160,6 | 295,4 | -1,2 | -1,6 | -3,4 | -13,9 | 7,0 | 0,0 | normal | False | normal | none | 32,2 |
| SYS2 | 10 | 2014-08-13 | Urlaub | 187,5 | 292,3 | -1,0 | -1,3 | -3,1 | -17,9 | 7,0 | 1,0 | normal | False | normal | none | 28,6 |
| SYS2 | 11 | 2014-08-14 | Urlaub | 184,9 | 306,3 | -1,0 | -1,5 | -2,9 | -19,0 | 7,0 | 2,0 | normal | False | normal | none | 45,8 |
| SYS2 | 12 | 2014-08-15 | Urlaub | 217,5 | 293,7 | -1,0 | -0,9 | -2,4 | -20,2 | 7,0 | 3,0 | normal | False | normal | none | 51,7 |
| SYS2 | 13 | 2014-08-16 | Urlaub | 190,0 | 258,3 | -0,7 | -0,7 | -2,2 | -21,5 | 7,0 | 4,0 | normal | False | normal | none | 89,9 |
| SYS2 | 14 | 2014-08-17 | nach der Rückkehr | 254,3 | 251,7 | 0,0 | 0,0 | -1,8 | -22,0 | 7,0 | 5,0 | normal | False | normal | none | 134,2 |
| SYS2 | 15 | 2014-08-18 | nach der Rückkehr | 336,1 | 280,9 | 0,5 | 0,7 | -1,2 | -20,9 | 7,0 | 6,0 | normal | True | new_pattern | advance_history_start | 155,4 |
| SYS2 | 16 | 2014-08-19 | nach der Rückkehr | 330,9 | - | 6,8 | - | - | - | - | - | unusual | False | peak | none | 134,4 |
| SYS2 | 17 | 2014-08-20 | nach der Rückkehr | 337,8 | - | 5,9 | - | - | - | - | - | unusual | False | peak | none | 134,9 |
| SYS2 | 18 | 2014-08-21 | nach der Rückkehr | 269,7 | - | 1,7 | - | - | - | - | - | normal | False | normal | none | 126,6 |
| SYS2 | 19 | 2014-08-22 | nach der Rückkehr | 144,3 | - | -1,0 | - | - | - | - | - | normal | False | normal | none | 27,9 |
| SYS2 | 20 | 2014-08-23 | nach der Rückkehr | 145,8 | - | -0,7 | - | - | - | - | - | normal | False | normal | none | 32,3 |
| SYS2 | 21 | 2014-08-24 | nach der Rückkehr | 135,0 | - | -0,8 | - | - | - | - | - | normal | False | normal | none | 375,5 |
| SYS2 | 22 | 2014-08-25 | nach der Rückkehr | 479,9 | - | 5,4 | - | - | - | - | - | unusual | False | peak | none | 133,2 |
| SYS2 | 23 | 2014-08-26 | nach der Rückkehr | 411,8 | - | 2,9 | - | 2,6 | - | - | - | normal | False | normal | none | 226,3 |
| SYS2 | 24 | 2014-08-27 | nach der Rückkehr | 288,7 | - | 0,6 | - | 1,1 | - | - | - | normal | False | normal | none | 114,4 |
| SYS2 | 25 | 2014-08-28 | nach der Rückkehr | 384,9 | - | 1,0 | - | 1,3 | - | - | - | normal | False | normal | none | 177,6 |
| SYS2 | 26 | 2014-08-29 | nach der Rückkehr | 404,8 | - | 1,0 | - | 2,9 | - | - | - | normal | False | normal | none | 240,2 |
| SYS2 | 27 | 2014-08-30 | nach der Rückkehr | 239,4 | - | 0,1 | - | 3,8 | - | - | - | normal | False | normal | none | 123,8 |
| SYS2 | 28 | 2014-08-31 | nach der Rückkehr | 335,9 | - | 0,6 | - | 5,7 | - | 6,0 | - | normal | False | normal | none | 122,6 |
| SYS2 | 29 | 2014-09-01 | nach der Rückkehr | 316,0 | - | 0,5 | - | 4,7 | - | 7,0 | - | normal | False | normal | none | 264,1 |
| SYS2 | 30 | 2014-09-02 | nach der Rückkehr | 479,9 | - | 2,1 | - | 5,0 | - | 7,0 | - | normal | False | normal | none | 135,4 |
| SYS2 | 31 | 2014-09-03 | nach der Rückkehr | 263,1 | - | 0,1 | - | 5,0 | - | 7,0 | - | normal | False | normal | none | 100,1 |
| SYS2 | 32 | 2014-09-04 | nach der Rückkehr | 267,9 | - | -0,1 | - | 3,7 | - | 7,0 | - | normal | False | normal | none | 114,1 |
| SYS2 | 33 | 2014-09-05 | nach der Rückkehr | 280,4 | - | 0,2 | - | 1,8 | - | 7,0 | - | normal | False | normal | none | 146,2 |
| SYS2 | 34 | 2014-09-06 | nach der Rückkehr | 323,8 | - | 1,5 | - | 1,7 | - | 7,0 | - | normal | False | normal | none | 130,7 |
| SYS2 | 35 | 2014-09-07 | nach der Rückkehr | 336,2 | - | 0,8 | - | 1,2 | - | 7,0 | - | normal | False | normal | none | 106,9 |
| SYS2 | 36 | 2014-09-08 | nach der Rückkehr | 315,7 | - | 0,1 | - | 1,0 | - | 7,0 | - | normal | False | normal | none | 118,6 |
| SYS2 | 37 | 2014-09-09 | nach der Rückkehr | 344,2 | 371,4 | 0,1 | -0,4 | 0,4 | - | 6,0 | - | normal | False | normal | none | 91,0 |
| SYS2 | 38 | 2014-09-10 | nach der Rückkehr | 273,0 | 275,9 | -0,4 | -0,0 | 0,4 | - | 5,0 | - | normal | False | normal | none | 213,6 |
| SYS2 | 39 | 2014-09-11 | nach der Rückkehr | 437,4 | 268,8 | 2,1 | 2,8 | 0,9 | - | 4,0 | - | normal | False | normal | none | 133,8 |
| SYS2 | 40 | 2014-09-12 | nach der Rückkehr | 370,1 | 248,9 | 0,0 | 2,0 | 1,2 | - | 4,0 | - | normal | False | normal | none | 100,8 |
| SYS2 | 41 | 2014-09-13 | nach der Rückkehr | 308,1 | 214,7 | -0,3 | 1,2 | 1,1 | - | 4,0 | - | normal | False | normal | none | 148,5 |
| SYS2 | 42 | 2014-09-14 | nach der Rückkehr | 376,2 | 295,1 | 1,1 | 0,9 | 1,2 | - | 4,0 | - | normal | False | normal | none | 128,4 |
| SYS2 | 43 | 2014-09-15 | nach der Rückkehr | 299,7 | 326,0 | 0,2 | -0,3 | 1,1 | - | 4,0 | - | normal | False | normal | none | 123,9 |

### vacation-2015-10: Je Tag ab Urlaubsbeginn

| System | Urlaubstag | Datum | Phase | Tagesmittel [W] | erwartet Wochentag [W] | z daily | z weekday | z weekly | long_term [%] | Streak weekly | Streak long_term | Level | Drift | Einordnung | Adaption | MAE [W] |
|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---|---|---:|
| SYS1 | 0 | 2015-10-04 | Urlaub | 202,0 | 289,5 | -1,6 | -1,4 | 0,1 | 1,6 | 0,0 | 0,0 | normal | False | normal | none | 92,3 |
| SYS1 | 1 | 2015-10-05 | Urlaub | 215,1 | 340,8 | -1,4 | -2,1 | -0,4 | -2,0 | 0,0 | 0,0 | normal | False | normal | none | 52,9 |
| SYS1 | 2 | 2015-10-06 | Urlaub | 223,4 | 338,6 | -1,6 | -1,8 | -0,7 | -5,0 | 0,0 | 0,0 | normal | False | normal | none | 58,9 |
| SYS1 | 3 | 2015-10-07 | Urlaub | 243,9 | 332,1 | -1,2 | -1,3 | -0,9 | -7,9 | 0,0 | 0,0 | normal | False | normal | none | 76,0 |
| SYS1 | 4 | 2015-10-08 | Urlaub | 200,0 | 356,8 | -1,3 | -2,3 | -1,6 | -8,6 | 1,0 | 0,0 | normal | False | normal | none | 73,1 |
| SYS1 | 5 | 2015-10-09 | Urlaub | 188,9 | 327,5 | -1,0 | -2,0 | -2,2 | -9,6 | 2,0 | 0,0 | normal | False | normal | none | 62,6 |
| SYS1 | 6 | 2015-10-10 | Urlaub | 133,0 | 330,4 | -2,0 | -2,9 | -3,3 | -13,5 | 3,0 | 0,0 | normal | False | normal | none | 43,5 |
| SYS1 | 7 | 2015-10-11 | Urlaub | 135,2 | 289,5 | -1,9 | -2,3 | -3,7 | -13,9 | 4,0 | 0,0 | normal | False | normal | none | 62,5 |
| SYS1 | 8 | 2015-10-12 | Urlaub | 184,7 | 340,8 | -1,4 | -2,3 | -4,3 | -14,3 | 5,0 | 1,0 | normal | False | normal | none | 55,2 |
| SYS1 | 9 | 2015-10-13 | Urlaub | 185,1 | 338,6 | -1,3 | -2,3 | -4,8 | -16,7 | 6,0 | 2,0 | normal | False | normal | none | 73,9 |
| SYS1 | 10 | 2015-10-14 | Urlaub | 209,6 | 332,1 | -1,1 | -1,7 | -5,4 | -16,6 | 7,0 | 3,0 | normal | False | normal | none | 149,7 |
| SYS1 | 11 | 2015-10-15 | Urlaub | 299,6 | 340,3 | -0,4 | -0,5 | -5,0 | -17,4 | 7,0 | 4,0 | normal | False | normal | none | 63,4 |
| SYS1 | 12 | 2015-10-16 | Urlaub | 188,6 | 327,5 | -1,1 | -1,6 | -4,7 | -17,7 | 7,0 | 5,0 | normal | False | normal | none | 58,3 |
| SYS1 | 13 | 2015-10-17 | Urlaub | 177,7 | 307,7 | -1,1 | -1,6 | -3,8 | -18,2 | 7,0 | 6,0 | normal | True | new_pattern | none | 45,9 |
| SYS1 | 14 | 2015-10-18 | Urlaub | 201,8 | 289,5 | -1,0 | -1,2 | -3,1 | -19,5 | 7,0 | 7,0 | normal | True | new_pattern | none | 54,7 |
| SYS1 | 15 | 2015-10-19 | Urlaub | 198,7 | 323,7 | -1,0 | -1,7 | -2,6 | -19,7 | 7,0 | 7,0 | normal | True | new_pattern | none | 52,9 |
| SYS1 | 16 | 2015-10-20 | Urlaub | 227,9 | 338,6 | -0,9 | -1,3 | -2,2 | -20,7 | 7,0 | 7,0 | normal | True | new_pattern | none | 69,7 |
| SYS1 | 17 | 2015-10-21 | Urlaub | 255,3 | 312,1 | -0,5 | -0,6 | -1,9 | -22,7 | 7,0 | 7,0 | normal | True | new_pattern | none | 52,8 |
| SYS1 | 18 | 2015-10-22 | Urlaub | 207,6 | 322,0 | -0,8 | -1,4 | -2,0 | -23,3 | 7,0 | 7,0 | normal | True | new_pattern | none | 57,3 |
| SYS1 | 19 | 2015-10-23 | Urlaub | 214,5 | 299,8 | -0,8 | -1,1 | -1,8 | -25,2 | 7,0 | 7,0 | normal | True | new_pattern | none | 103,1 |
| SYS1 | 20 | 2015-10-24 | Urlaub | 256,7 | 284,0 | 0,3 | -0,3 | -1,5 | -25,9 | 7,0 | 7,0 | normal | True | new_pattern | none | 210,6 |
| SYS1 | 21 | 2015-10-25 | nach der Rückkehr | 412,0 | 252,5 | 2,0 | 2,0 | -0,9 | -26,9 | 6,0 | 7,0 | normal | True | new_pattern | none | 218,7 |
| SYS1 | 22 | 2015-10-26 | nach der Rückkehr | 398,1 | 304,4 | 1,4 | 1,0 | -0,4 | -26,7 | 5,0 | 7,0 | normal | False | normal | none | 171,9 |
| SYS1 | 23 | 2015-10-27 | nach der Rückkehr | 195,9 | 316,8 | 0,4 | -1,3 | -0,4 | -27,4 | 4,0 | 7,0 | normal | False | normal | none | 116,1 |
| SYS1 | 24 | 2015-10-28 | nach der Rückkehr | 136,0 | 312,1 | -1,3 | -1,8 | -0,7 | -29,1 | 3,0 | 7,0 | normal | False | normal | none | 82,9 |
| SYS1 | 25 | 2015-10-29 | nach der Rückkehr | 152,8 | 316,0 | -0,7 | -1,6 | -0,7 | -32,1 | 2,0 | 7,0 | normal | False | normal | none | 157,2 |
| SYS1 | 26 | 2015-10-30 | nach der Rückkehr | 283,6 | 280,2 | 1,0 | 0,0 | -0,5 | -33,3 | 1,0 | 7,0 | normal | False | normal | none | 152,4 |
| SYS1 | 27 | 2015-10-31 | nach der Rückkehr | 316,0 | 284,0 | 0,1 | 0,3 | -0,3 | -34,7 | 0,0 | 7,0 | normal | False | normal | none | 196,7 |
| SYS1 | 28 | 2015-11-01 | nach der Rückkehr | 386,9 | 252,5 | 0,9 | 1,4 | -0,4 | -32,1 | 0,0 | 7,0 | normal | False | normal | none | 225,6 |
| SYS1 | 29 | 2015-11-02 | nach der Rückkehr | 453,9 | 313,1 | 1,4 | 1,3 | -0,2 | -28,5 | 0,0 | 7,0 | normal | False | normal | none | 175,8 |
| SYS1 | 30 | 2015-11-03 | nach der Rückkehr | 383,9 | 262,9 | 1,2 | 1,1 | 0,2 | -25,9 | 0,0 | 7,0 | normal | False | normal | none | 187,7 |
| SYS1 | 31 | 2015-11-04 | nach der Rückkehr | 413,5 | 282,5 | 1,2 | 1,2 | 0,9 | -22,6 | 0,0 | 7,0 | normal | False | normal | none | 152,0 |
| SYS1 | 32 | 2015-11-05 | nach der Rückkehr | 404,9 | 292,5 | 0,3 | 1,0 | 1,5 | -19,2 | 1,0 | 7,0 | normal | False | normal | none | 177,2 |
| SYS1 | 33 | 2015-11-06 | nach der Rückkehr | 345,6 | 287,6 | 0,4 | 0,5 | 1,7 | -16,5 | 2,0 | 7,0 | normal | False | normal | none | 235,4 |
| SYS1 | 34 | 2015-11-07 | nach der Rückkehr | 438,9 | 300,0 | 1,8 | 1,2 | 2,0 | -10,0 | 3,0 | 6,0 | normal | False | normal | none | 150,7 |
| SYS1 | 35 | 2015-11-08 | nach der Rückkehr | 284,9 | 290,6 | -0,1 | -0,0 | 1,8 | -7,3 | 4,0 | 5,0 | normal | False | normal | none | 250,9 |
| SYS1 | 36 | 2015-11-09 | nach der Rückkehr | 484,1 | 313,1 | 3,4 | 1,5 | 1,9 | -2,1 | 5,0 | 4,0 | unusual | False | peak | none | 85,5 |
| SYS1 | 37 | 2015-11-10 | nach der Rückkehr | 308,7 | 262,9 | -0,2 | 0,4 | 1,7 | 1,3 | 6,0 | 3,0 | normal | False | normal | none | 214,9 |
| SYS1 | 38 | 2015-11-11 | nach der Rückkehr | 463,2 | 282,5 | 1,8 | 1,5 | 1,8 | 5,8 | 7,0 | 2,0 | normal | False | normal | none | 221,1 |
| SYS1 | 39 | 2015-11-12 | nach der Rückkehr | 475,4 | 292,5 | 0,9 | 1,5 | 1,9 | 8,8 | 7,0 | 1,0 | normal | False | normal | none | 138,6 |
| SYS1 | 40 | 2015-11-13 | nach der Rückkehr | 404,6 | 295,8 | 0,5 | 0,9 | 2,0 | 13,3 | 7,0 | 0,0 | normal | False | normal | none | 155,6 |
| SYS1 | 41 | 2015-11-14 | nach der Rückkehr | 342,9 | 300,0 | 0,5 | 0,3 | 1,7 | 17,7 | 7,0 | 1,0 | normal | False | normal | none | 144,7 |
| SYS1 | 42 | 2015-11-15 | nach der Rückkehr | 334,2 | 324,4 | 0,3 | 0,1 | 1,8 | 22,0 | 7,0 | 2,0 | normal | False | normal | none | 170,4 |
| SYS1 | 43 | 2015-11-16 | nach der Rückkehr | 378,5 | 321,5 | 0,9 | 0,5 | 1,5 | 25,9 | 7,0 | 3,0 | normal | False | normal | none | 288,8 |
| SYS1 | 44 | 2015-11-17 | nach der Rückkehr | 573,7 | 262,9 | 1,5 | 2,7 | 2,0 | 33,3 | 7,0 | 4,0 | normal | False | normal | none | 204,2 |
| SYS1 | 45 | 2015-11-18 | nach der Rückkehr | 462,6 | 284,9 | 0,5 | 1,4 | 2,0 | 38,4 | 7,0 | 5,0 | normal | False | normal | none | 145,9 |
| SYS1 | 46 | 2015-11-19 | nach der Rückkehr | 444,0 | 292,5 | 0,3 | 1,2 | 1,8 | 43,3 | 7,0 | 6,0 | normal | True | new_pattern | none | 177,4 |
| SYS1 | 47 | 2015-11-20 | nach der Rückkehr | 481,1 | 314,6 | 0,5 | 1,2 | 1,9 | 51,1 | 7,0 | 7,0 | normal | True | new_pattern | none | 247,4 |
| SYS1 | 48 | 2015-11-21 | nach der Rückkehr | 173,7 | 300,0 | -0,9 | -0,9 | 1,6 | 50,5 | 7,0 | 7,0 | normal | True | new_pattern | none | 180,5 |
| SYS1 | 49 | 2015-11-22 | nach der Rückkehr | 151,9 | 309,5 | -1,0 | -1,1 | 1,2 | 46,8 | 7,0 | 7,0 | normal | True | new_pattern | none | 175,8 |
| SYS1 | 50 | 2015-11-23 | nach der Rückkehr | 377,1 | 363,8 | 0,6 | 0,1 | 1,1 | 45,5 | 7,0 | 7,0 | normal | True | new_pattern | none | 183,1 |
| SYS2 | 0 | 2015-10-04 | Urlaub | 202,0 | 289,5 | -1,6 | -1,4 | 0,1 | 1,6 | 0,0 | 0,0 | normal | False | normal | none | 92,3 |
| SYS2 | 1 | 2015-10-05 | Urlaub | 215,1 | 340,8 | -1,4 | -2,1 | -0,4 | -2,0 | 0,0 | 0,0 | normal | False | normal | none | 52,9 |
| SYS2 | 2 | 2015-10-06 | Urlaub | 223,4 | 338,6 | -1,6 | -1,8 | -0,7 | -5,0 | 0,0 | 0,0 | normal | False | normal | none | 58,9 |
| SYS2 | 3 | 2015-10-07 | Urlaub | 243,9 | 332,1 | -1,2 | -1,3 | -0,9 | -7,9 | 0,0 | 0,0 | normal | False | normal | none | 76,0 |
| SYS2 | 4 | 2015-10-08 | Urlaub | 200,0 | 356,8 | -1,3 | -2,3 | -1,6 | -8,6 | 1,0 | 0,0 | normal | False | normal | none | 73,1 |
| SYS2 | 5 | 2015-10-09 | Urlaub | 188,9 | 327,5 | -1,0 | -2,0 | -2,2 | -9,6 | 2,0 | 0,0 | normal | False | normal | none | 62,6 |
| SYS2 | 6 | 2015-10-10 | Urlaub | 133,0 | 330,4 | -2,0 | -2,9 | -3,3 | -13,5 | 3,0 | 0,0 | normal | False | normal | none | 43,5 |
| SYS2 | 7 | 2015-10-11 | Urlaub | 135,2 | 289,5 | -1,9 | -2,3 | -3,7 | -13,9 | 4,0 | 0,0 | normal | False | normal | none | 62,5 |
| SYS2 | 8 | 2015-10-12 | Urlaub | 184,7 | 340,8 | -1,4 | -2,3 | -4,3 | -14,3 | 5,0 | 1,0 | normal | False | normal | none | 55,2 |
| SYS2 | 9 | 2015-10-13 | Urlaub | 185,1 | 338,6 | -1,3 | -2,3 | -4,8 | -16,7 | 6,0 | 2,0 | normal | False | normal | none | 73,9 |
| SYS2 | 10 | 2015-10-14 | Urlaub | 209,6 | 332,1 | -1,1 | -1,7 | -5,4 | -16,6 | 7,0 | 3,0 | normal | False | normal | none | 149,7 |
| SYS2 | 11 | 2015-10-15 | Urlaub | 299,6 | 340,3 | -0,4 | -0,5 | -5,0 | -17,4 | 7,0 | 4,0 | normal | False | normal | none | 63,4 |
| SYS2 | 12 | 2015-10-16 | Urlaub | 188,6 | 327,5 | -1,1 | -1,6 | -4,7 | -17,7 | 7,0 | 5,0 | normal | False | normal | none | 58,3 |
| SYS2 | 13 | 2015-10-17 | Urlaub | 177,7 | 307,7 | -1,1 | -1,6 | -3,8 | -18,2 | 7,0 | 6,0 | normal | True | new_pattern | advance_history_start | 54,0 |
| SYS2 | 14 | 2015-10-18 | Urlaub | 201,8 | - | 0,8 | - | - | - | - | - | normal | False | normal | none | 47,1 |
| SYS2 | 15 | 2015-10-19 | Urlaub | 198,7 | - | -0,1 | - | - | - | - | - | normal | False | normal | none | 67,1 |
| SYS2 | 16 | 2015-10-20 | Urlaub | 227,9 | - | 1,5 | - | - | - | - | - | normal | False | normal | none | 76,6 |
| SYS2 | 17 | 2015-10-21 | Urlaub | 255,3 | - | 4,6 | - | - | - | - | - | unusual | False | peak | none | 57,3 |
| SYS2 | 18 | 2015-10-22 | Urlaub | 207,6 | - | -0,4 | - | - | - | - | - | normal | False | normal | none | 55,7 |
| SYS2 | 19 | 2015-10-23 | Urlaub | 214,5 | - | -0,2 | - | - | - | - | - | normal | False | normal | none | 95,7 |
| SYS2 | 20 | 2015-10-24 | Urlaub | 256,7 | - | 13,1 | - | - | - | - | - | unusual | False | peak | none | 217,0 |
| SYS2 | 21 | 2015-10-25 | nach der Rückkehr | 412,0 | - | 31,4 | - | 7,6 | - | - | - | unusual | False | peak | none | 217,1 |
| SYS2 | 22 | 2015-10-26 | nach der Rückkehr | 398,1 | - | 19,4 | - | 12,6 | - | - | - | unusual | False | peak | none | 229,9 |
| SYS2 | 23 | 2015-10-27 | nach der Rückkehr | 195,9 | - | 9,8 | - | 9,6 | - | - | - | unusual | False | low | none | 110,0 |
| SYS2 | 24 | 2015-10-28 | nach der Rückkehr | 136,0 | - | -4,1 | - | 5,6 | - | - | - | unusual | False | low | none | 56,4 |
| SYS2 | 25 | 2015-10-29 | nach der Rückkehr | 152,8 | - | -0,0 | - | 5,3 | - | - | - | normal | False | normal | none | 167,6 |
| SYS2 | 26 | 2015-10-30 | nach der Rückkehr | 283,6 | - | 12,3 | - | 7,0 | - | 6,0 | - | unusual | False | peak | none | 160,1 |
| SYS2 | 27 | 2015-10-31 | nach der Rückkehr | 316,0 | - | 5,2 | - | 7,1 | - | 7,0 | - | unusual | False | peak | none | 197,4 |
| SYS2 | 28 | 2015-11-01 | nach der Rückkehr | 386,9 | - | 9,5 | - | 3,2 | - | 7,0 | - | unusual | False | peak | none | 194,6 |
| SYS2 | 29 | 2015-11-02 | nach der Rückkehr | 453,9 | - | 6,3 | - | 2,0 | - | 7,0 | - | unusual | False | peak | none | 198,9 |
| SYS2 | 30 | 2015-11-03 | nach der Rückkehr | 383,9 | - | 3,9 | - | 2,5 | - | 7,0 | - | unusual | False | peak | none | 192,2 |
| SYS2 | 31 | 2015-11-04 | nach der Rückkehr | 413,5 | - | 3,3 | - | 3,8 | - | 7,0 | - | unusual | False | peak | none | 159,2 |
| SYS2 | 32 | 2015-11-05 | nach der Rückkehr | 404,9 | - | 1,5 | - | 5,0 | - | 7,0 | - | normal | False | normal | none | 180,5 |
| SYS2 | 33 | 2015-11-06 | nach der Rückkehr | 345,6 | - | 1,5 | - | 5,3 | - | 7,0 | - | normal | False | normal | none | 232,2 |
| SYS2 | 34 | 2015-11-07 | nach der Rückkehr | 438,9 | - | 3,6 | - | 5,7 | - | 7,0 | - | unusual | False | peak | none | 153,4 |
| SYS2 | 35 | 2015-11-08 | nach der Rückkehr | 284,9 | 294,4 | 0,3 | -0,1 | 5,1 | - | 7,0 | - | normal | False | normal | none | 250,0 |
| SYS2 | 36 | 2015-11-09 | nach der Rückkehr | 484,1 | 298,4 | 4,5 | 1,3 | 5,1 | - | 7,0 | - | unusual | False | peak | none | 85,5 |
| SYS2 | 37 | 2015-11-10 | nach der Rückkehr | 308,7 | 211,9 | -0,1 | 0,9 | 4,3 | - | 7,0 | - | normal | False | normal | none | 214,9 |
| SYS2 | 38 | 2015-11-11 | nach der Rückkehr | 463,2 | 232,4 | 2,5 | 1,9 | 3,7 | - | 7,0 | - | normal | False | normal | none | 221,1 |
| SYS2 | 39 | 2015-11-12 | nach der Rückkehr | 475,4 | 253,6 | 1,2 | 1,8 | 3,1 | - | 7,0 | - | normal | False | normal | none | 138,6 |
| SYS2 | 40 | 2015-11-13 | nach der Rückkehr | 404,6 | 249,0 | 0,6 | 1,2 | 2,7 | - | 7,0 | - | normal | False | normal | none | 155,6 |
| SYS2 | 41 | 2015-11-14 | nach der Rückkehr | 342,9 | 286,4 | 0,5 | 0,4 | 2,1 | - | 7,0 | - | normal | False | normal | none | 144,7 |
| SYS2 | 42 | 2015-11-15 | nach der Rückkehr | 334,2 | 284,9 | 0,3 | 0,4 | 2,0 | - | 7,0 | - | normal | False | normal | none | 170,4 |
| SYS2 | 43 | 2015-11-16 | nach der Rückkehr | 378,5 | 398,1 | 0,8 | -0,2 | 1,6 | - | 7,0 | - | normal | False | normal | none | 288,8 |
| SYS2 | 44 | 2015-11-17 | nach der Rückkehr | 573,7 | 227,9 | 1,2 | 2,9 | 2,0 | - | 7,0 | - | normal | False | normal | none | 204,2 |
| SYS2 | 45 | 2015-11-18 | nach der Rückkehr | 462,6 | 255,3 | 0,3 | 1,6 | 1,9 | - | 7,0 | - | normal | False | normal | none | 145,9 |
| SYS2 | 46 | 2015-11-19 | nach der Rückkehr | 444,0 | 299,6 | 0,2 | 1,1 | 1,8 | - | 7,0 | - | normal | False | normal | none | 177,4 |
| SYS2 | 47 | 2015-11-20 | nach der Rückkehr | 481,1 | 283,6 | 0,3 | 1,5 | 1,8 | - | 7,0 | - | normal | False | normal | none | 247,4 |
| SYS2 | 48 | 2015-11-21 | nach der Rückkehr | 173,7 | 316,0 | -1,0 | -1,0 | 1,4 | 75,5 | 7,0 | - | normal | False | normal | none | 180,5 |
| SYS2 | 49 | 2015-11-22 | nach der Rückkehr | 151,9 | 309,5 | -1,1 | -1,1 | 1,0 | 60,8 | 6,0 | - | normal | False | normal | none | 175,8 |
| SYS2 | 50 | 2015-11-23 | nach der Rückkehr | 377,1 | 388,3 | 0,3 | -0,1 | 1,0 | 53,0 | 5,0 | - | normal | False | normal | none | 183,1 |
