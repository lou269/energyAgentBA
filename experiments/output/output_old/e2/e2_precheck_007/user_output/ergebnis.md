# E2 Vorprüfung Gate, Lauf e2_precheck_007

## Setup

- Urlaub vacation-2015-02: 2015-02-22 bis vor 2015-03-01
- Urlaub vacation-2014-08: 2014-08-03 bis vor 2014-08-17
- Systeme: SYS1, SYS2
- Tage nach der Rückkehr: 30
- Commit: 71433df (mit lokalen Änderungen)

## vacation-2015-02: Erste Tage ab Urlaubsbeginn

| System | Gate offen [Urlaubstag] | Drift [Urlaubstag] | Reset [Urlaubstag] |
|---|---:|---:|---:|
| SYS1 | 0 | - | - |
| SYS2 | 0 | - | - |

## vacation-2015-02: Gate und Einordnung je Phase

| System | Phase | Tage | Gate offen | davon Einzeltag | davon Drift | davon nur eine Skala | new_pattern | low | peak | absence | Resets | Meldungen | Ausfalltage | MAE [W] |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| SYS1 | vor dem Urlaub | 31 | 6 | 0 | 0 | 6 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 156,6 |
| SYS1 | Urlaub | 7 | 3 | 0 | 0 | 3 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 88,9 |
| SYS1 | nach der Rückkehr | 30 | 6 | 0 | 0 | 6 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 187,7 |
| SYS2 | vor dem Urlaub | 31 | 6 | 0 | 0 | 6 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 156,6 |
| SYS2 | Urlaub | 7 | 3 | 0 | 0 | 3 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 88,9 |
| SYS2 | nach der Rückkehr | 30 | 6 | 0 | 0 | 6 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 187,7 |

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

## Hinweise

- Urlaubstag = analysierter Tag seit Beginn der Abwesenheit, 0 = erster Urlaubstag
- Gate offen: Einzeltag (daily/weekday über ihrer Schwelle), Drift (weekly und long_term halten an) oder nur eine anhaltende Skala
- Reset = new_pattern mit advance_history_start, bei SYS1 nie

## Anhang

### vacation-2015-02: Je Tag ab Urlaubsbeginn

| System | Urlaubstag | Datum | Phase | Tagesmittel [W] | erwartet Wochentag [W] | z daily | z weekday | z weekly | long_term [%] | Streak weekly | Streak long_term | Level | Drift | Einordnung | Adaption | MAE [W] |
|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---|---|---:|
| SYS1 | 0 | 2015-02-22 | Urlaub | 190,3 | 375,3 | -1,6 | -2,4 | -0,3 | 17,1 | 0,0 | 7,0 | normal | False | normal | none | 86,5 |
| SYS1 | 1 | 2015-02-23 | Urlaub | 234,7 | 341,8 | -1,4 | -1,3 | -0,4 | 14,4 | 0,0 | 7,0 | normal | False | normal | none | 70,4 |
| SYS1 | 2 | 2015-02-24 | Urlaub | 202,3 | 399,6 | -1,5 | -2,3 | -0,6 | 9,6 | 0,0 | 6,0 | normal | False | normal | none | 51,3 |
| SYS1 | 3 | 2015-02-25 | Urlaub | 212,2 | 380,2 | -1,6 | -1,9 | -1,0 | 4,1 | 0,0 | 5,0 | normal | False | normal | none | 43,1 |
| SYS1 | 4 | 2015-02-26 | Urlaub | 211,1 | 369,1 | -1,6 | -1,8 | -1,3 | 0,8 | 1,0 | 4,0 | normal | False | normal | none | 41,6 |
| SYS1 | 5 | 2015-02-27 | Urlaub | 175,7 | 393,6 | -1,9 | -2,7 | -1,6 | -6,0 | 2,0 | 3,0 | normal | False | normal | none | 95,5 |
| SYS1 | 6 | 2015-02-28 | Urlaub | 227,2 | 376,3 | -0,8 | -1,8 | -2,1 | -9,3 | 3,0 | 2,0 | normal | False | normal | none | 234,2 |
| SYS1 | 7 | 2015-03-01 | nach der Rückkehr | 398,7 | 375,3 | 0,9 | 0,3 | -1,7 | -10,7 | 4,0 | 1,0 | normal | False | normal | none | 236,8 |
| SYS1 | 8 | 2015-03-02 | nach der Rückkehr | 436,9 | 341,8 | 1,5 | 1,2 | -1,4 | -11,4 | 5,0 | 0,0 | normal | False | normal | none | 163,1 |
| SYS1 | 9 | 2015-03-03 | nach der Rückkehr | 424,8 | 399,6 | 0,0 | 0,3 | -1,1 | -11,8 | 6,0 | 0,0 | normal | False | normal | none | 181,7 |
| SYS1 | 10 | 2015-03-04 | nach der Rückkehr | 403,8 | 380,2 | 0,7 | 0,3 | -0,8 | -10,4 | 6,0 | 0,0 | normal | False | normal | none | 217,4 |
| SYS1 | 11 | 2015-03-05 | nach der Rückkehr | 533,7 | 369,1 | 2,1 | 2,2 | -0,1 | -5,6 | 5,0 | 0,0 | normal | False | normal | none | 206,0 |
| SYS1 | 12 | 2015-03-06 | nach der Rückkehr | 337,7 | 393,6 | -0,5 | -0,8 | 0,3 | -8,1 | 4,0 | 0,0 | normal | False | normal | none | 180,8 |
| SYS1 | 13 | 2015-03-07 | nach der Rückkehr | 310,3 | 376,3 | -0,7 | -1,0 | 0,5 | -9,5 | 3,0 | 0,0 | normal | False | normal | none | 214,1 |
| SYS1 | 14 | 2015-03-08 | nach der Rückkehr | 317,2 | 380,3 | 0,5 | -0,9 | 0,3 | -10,9 | 2,0 | 0,0 | normal | False | normal | none | 156,9 |
| SYS1 | 15 | 2015-03-09 | nach der Rückkehr | 380,8 | 341,8 | 0,0 | 0,5 | 0,1 | -10,6 | 1,0 | 0,0 | normal | False | normal | none | 186,3 |
| SYS1 | 16 | 2015-03-10 | nach der Rückkehr | 480,7 | 399,6 | 0,5 | 1,3 | 0,3 | -11,6 | 0,0 | 0,0 | normal | False | normal | none | 118,7 |
| SYS1 | 17 | 2015-03-11 | nach der Rückkehr | 359,1 | 380,2 | -0,5 | -0,3 | 0,2 | -11,5 | 0,0 | 0,0 | normal | False | normal | none | 201,8 |
| SYS1 | 18 | 2015-03-12 | nach der Rückkehr | 412,7 | 369,1 | 0,6 | 0,6 | -0,1 | -13,4 | 0,0 | 0,0 | normal | False | normal | none | 196,4 |
| SYS1 | 19 | 2015-03-13 | nach der Rückkehr | 446,0 | 384,8 | 0,6 | 0,9 | 0,2 | -14,2 | 0,0 | 0,0 | normal | False | normal | none | 208,4 |
| SYS1 | 20 | 2015-03-14 | nach der Rückkehr | 197,9 | 370,8 | -1,4 | -2,4 | -0,0 | -15,3 | 0,0 | 1,0 | normal | False | normal | none | 155,5 |
| SYS1 | 21 | 2015-03-15 | nach der Rückkehr | 145,6 | 378,9 | -2,0 | -3,1 | -0,5 | -18,8 | 0,0 | 2,0 | normal | False | normal | none | 265,1 |
| SYS1 | 22 | 2015-03-16 | nach der Rückkehr | 459,0 | 362,6 | 0,5 | 1,2 | -0,3 | -16,9 | 0,0 | 3,0 | normal | False | normal | none | 289,2 |
| SYS1 | 23 | 2015-03-17 | nach der Rückkehr | 521,6 | 412,7 | 1,6 | 1,3 | -0,2 | -14,3 | 0,0 | 4,0 | normal | False | normal | none | 225,1 |
| SYS1 | 24 | 2015-03-18 | nach der Rückkehr | 492,0 | 377,0 | 1,0 | 1,4 | 0,2 | -15,0 | 0,0 | 5,0 | normal | False | normal | none | 119,8 |
| SYS1 | 25 | 2015-03-19 | nach der Rückkehr | 386,7 | 376,5 | -0,6 | 0,1 | 0,1 | -15,5 | 0,0 | 6,0 | normal | False | normal | none | 78,2 |
| SYS1 | 26 | 2015-03-20 | nach der Rückkehr | 323,5 | 434,6 | -0,9 | -1,3 | -0,2 | -14,9 | 0,0 | 7,0 | normal | False | normal | none | 236,5 |
| SYS1 | 27 | 2015-03-21 | nach der Rückkehr | 486,6 | 359,6 | 1,5 | 1,5 | 0,5 | -14,5 | 0,0 | 7,0 | normal | False | normal | none | 185,9 |
| SYS1 | 28 | 2015-03-22 | nach der Rückkehr | 461,6 | 378,9 | 0,8 | 1,0 | 1,4 | -10,7 | 1,0 | 6,0 | normal | False | normal | none | 146,9 |
| SYS1 | 29 | 2015-03-23 | nach der Rückkehr | 322,9 | 362,6 | -0,2 | -0,5 | 1,0 | -9,3 | 1,0 | 5,0 | normal | False | normal | none | 231,0 |
| SYS1 | 30 | 2015-03-24 | nach der Rückkehr | 461,0 | 442,7 | 0,8 | 0,2 | 0,8 | -5,2 | 1,0 | 4,0 | normal | False | normal | none | 152,2 |
| SYS1 | 31 | 2015-03-25 | nach der Rückkehr | 314,7 | 399,4 | 0,0 | -1,0 | 0,4 | -2,2 | 1,0 | 3,0 | normal | False | normal | none | 213,1 |
| SYS1 | 32 | 2015-03-26 | nach der Rückkehr | 420,7 | 394,2 | 0,7 | 0,3 | 0,5 | 1,1 | 1,0 | 2,0 | normal | False | normal | none | 153,6 |
| SYS1 | 33 | 2015-03-27 | nach der Rückkehr | 410,6 | 391,9 | 0,2 | 0,2 | 0,7 | 7,0 | 1,0 | 1,0 | normal | False | normal | none | 188,5 |
| SYS1 | 34 | 2015-03-28 | nach der Rückkehr | 460,9 | 359,6 | 0,3 | 1,2 | 0,6 | 10,9 | 1,0 | 0,0 | normal | False | normal | none | 216,5 |
| SYS1 | 35 | 2015-03-29 | nach der Rückkehr | 474,6 | 391,3 | 0,8 | 0,9 | 0,6 | 11,5 | 0,0 | 0,0 | normal | False | normal | none | 119,2 |
| SYS1 | 36 | 2015-03-30 | nach der Rückkehr | 293,6 | 362,6 | -1,0 | -0,7 | 0,5 | 10,9 | 0,0 | 0,0 | normal | False | normal | none | 185,0 |
| SYS2 | 0 | 2015-02-22 | Urlaub | 190,3 | 375,3 | -1,6 | -2,4 | -0,3 | 17,1 | 0,0 | 7,0 | normal | False | normal | none | 86,5 |
| SYS2 | 1 | 2015-02-23 | Urlaub | 234,7 | 341,8 | -1,4 | -1,3 | -0,4 | 14,4 | 0,0 | 7,0 | normal | False | normal | none | 70,4 |
| SYS2 | 2 | 2015-02-24 | Urlaub | 202,3 | 399,6 | -1,5 | -2,3 | -0,6 | 9,6 | 0,0 | 6,0 | normal | False | normal | none | 51,3 |
| SYS2 | 3 | 2015-02-25 | Urlaub | 212,2 | 380,2 | -1,6 | -1,9 | -1,0 | 4,1 | 0,0 | 5,0 | normal | False | normal | none | 43,1 |
| SYS2 | 4 | 2015-02-26 | Urlaub | 211,1 | 369,1 | -1,6 | -1,8 | -1,3 | 0,8 | 1,0 | 4,0 | normal | False | normal | none | 41,6 |
| SYS2 | 5 | 2015-02-27 | Urlaub | 175,7 | 393,6 | -1,9 | -2,7 | -1,6 | -6,0 | 2,0 | 3,0 | normal | False | normal | none | 95,5 |
| SYS2 | 6 | 2015-02-28 | Urlaub | 227,2 | 376,3 | -0,8 | -1,8 | -2,1 | -9,3 | 3,0 | 2,0 | normal | False | normal | none | 234,2 |
| SYS2 | 7 | 2015-03-01 | nach der Rückkehr | 398,7 | 375,3 | 0,9 | 0,3 | -1,7 | -10,7 | 4,0 | 1,0 | normal | False | normal | none | 236,8 |
| SYS2 | 8 | 2015-03-02 | nach der Rückkehr | 436,9 | 341,8 | 1,5 | 1,2 | -1,4 | -11,4 | 5,0 | 0,0 | normal | False | normal | none | 163,1 |
| SYS2 | 9 | 2015-03-03 | nach der Rückkehr | 424,8 | 399,6 | 0,0 | 0,3 | -1,1 | -11,8 | 6,0 | 0,0 | normal | False | normal | none | 181,7 |
| SYS2 | 10 | 2015-03-04 | nach der Rückkehr | 403,8 | 380,2 | 0,7 | 0,3 | -0,8 | -10,4 | 6,0 | 0,0 | normal | False | normal | none | 217,4 |
| SYS2 | 11 | 2015-03-05 | nach der Rückkehr | 533,7 | 369,1 | 2,1 | 2,2 | -0,1 | -5,6 | 5,0 | 0,0 | normal | False | normal | none | 206,0 |
| SYS2 | 12 | 2015-03-06 | nach der Rückkehr | 337,7 | 393,6 | -0,5 | -0,8 | 0,3 | -8,1 | 4,0 | 0,0 | normal | False | normal | none | 180,8 |
| SYS2 | 13 | 2015-03-07 | nach der Rückkehr | 310,3 | 376,3 | -0,7 | -1,0 | 0,5 | -9,5 | 3,0 | 0,0 | normal | False | normal | none | 214,1 |
| SYS2 | 14 | 2015-03-08 | nach der Rückkehr | 317,2 | 380,3 | 0,5 | -0,9 | 0,3 | -10,9 | 2,0 | 0,0 | normal | False | normal | none | 156,9 |
| SYS2 | 15 | 2015-03-09 | nach der Rückkehr | 380,8 | 341,8 | 0,0 | 0,5 | 0,1 | -10,6 | 1,0 | 0,0 | normal | False | normal | none | 186,3 |
| SYS2 | 16 | 2015-03-10 | nach der Rückkehr | 480,7 | 399,6 | 0,5 | 1,3 | 0,3 | -11,6 | 0,0 | 0,0 | normal | False | normal | none | 118,7 |
| SYS2 | 17 | 2015-03-11 | nach der Rückkehr | 359,1 | 380,2 | -0,5 | -0,3 | 0,2 | -11,5 | 0,0 | 0,0 | normal | False | normal | none | 201,8 |
| SYS2 | 18 | 2015-03-12 | nach der Rückkehr | 412,7 | 369,1 | 0,6 | 0,6 | -0,1 | -13,4 | 0,0 | 0,0 | normal | False | normal | none | 196,4 |
| SYS2 | 19 | 2015-03-13 | nach der Rückkehr | 446,0 | 384,8 | 0,6 | 0,9 | 0,2 | -14,2 | 0,0 | 0,0 | normal | False | normal | none | 208,4 |
| SYS2 | 20 | 2015-03-14 | nach der Rückkehr | 197,9 | 370,8 | -1,4 | -2,4 | -0,0 | -15,3 | 0,0 | 1,0 | normal | False | normal | none | 155,5 |
| SYS2 | 21 | 2015-03-15 | nach der Rückkehr | 145,6 | 378,9 | -2,0 | -3,1 | -0,5 | -18,8 | 0,0 | 2,0 | normal | False | normal | none | 265,1 |
| SYS2 | 22 | 2015-03-16 | nach der Rückkehr | 459,0 | 362,6 | 0,5 | 1,2 | -0,3 | -16,9 | 0,0 | 3,0 | normal | False | normal | none | 289,2 |
| SYS2 | 23 | 2015-03-17 | nach der Rückkehr | 521,6 | 412,7 | 1,6 | 1,3 | -0,2 | -14,3 | 0,0 | 4,0 | normal | False | normal | none | 225,1 |
| SYS2 | 24 | 2015-03-18 | nach der Rückkehr | 492,0 | 377,0 | 1,0 | 1,4 | 0,2 | -15,0 | 0,0 | 5,0 | normal | False | normal | none | 119,8 |
| SYS2 | 25 | 2015-03-19 | nach der Rückkehr | 386,7 | 376,5 | -0,6 | 0,1 | 0,1 | -15,5 | 0,0 | 6,0 | normal | False | normal | none | 78,2 |
| SYS2 | 26 | 2015-03-20 | nach der Rückkehr | 323,5 | 434,6 | -0,9 | -1,3 | -0,2 | -14,9 | 0,0 | 7,0 | normal | False | normal | none | 236,5 |
| SYS2 | 27 | 2015-03-21 | nach der Rückkehr | 486,6 | 359,6 | 1,5 | 1,5 | 0,5 | -14,5 | 0,0 | 7,0 | normal | False | normal | none | 185,9 |
| SYS2 | 28 | 2015-03-22 | nach der Rückkehr | 461,6 | 378,9 | 0,8 | 1,0 | 1,4 | -10,7 | 1,0 | 6,0 | normal | False | normal | none | 146,9 |
| SYS2 | 29 | 2015-03-23 | nach der Rückkehr | 322,9 | 362,6 | -0,2 | -0,5 | 1,0 | -9,3 | 1,0 | 5,0 | normal | False | normal | none | 231,0 |
| SYS2 | 30 | 2015-03-24 | nach der Rückkehr | 461,0 | 442,7 | 0,8 | 0,2 | 0,8 | -5,2 | 1,0 | 4,0 | normal | False | normal | none | 152,2 |
| SYS2 | 31 | 2015-03-25 | nach der Rückkehr | 314,7 | 399,4 | 0,0 | -1,0 | 0,4 | -2,2 | 1,0 | 3,0 | normal | False | normal | none | 213,1 |
| SYS2 | 32 | 2015-03-26 | nach der Rückkehr | 420,7 | 394,2 | 0,7 | 0,3 | 0,5 | 1,1 | 1,0 | 2,0 | normal | False | normal | none | 153,6 |
| SYS2 | 33 | 2015-03-27 | nach der Rückkehr | 410,6 | 391,9 | 0,2 | 0,2 | 0,7 | 7,0 | 1,0 | 1,0 | normal | False | normal | none | 188,5 |
| SYS2 | 34 | 2015-03-28 | nach der Rückkehr | 460,9 | 359,6 | 0,3 | 1,2 | 0,6 | 10,9 | 1,0 | 0,0 | normal | False | normal | none | 216,5 |
| SYS2 | 35 | 2015-03-29 | nach der Rückkehr | 474,6 | 391,3 | 0,8 | 0,9 | 0,6 | 11,5 | 0,0 | 0,0 | normal | False | normal | none | 119,2 |
| SYS2 | 36 | 2015-03-30 | nach der Rückkehr | 293,6 | 362,6 | -1,0 | -0,7 | 0,5 | 10,9 | 0,0 | 0,0 | normal | False | normal | none | 185,0 |

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
