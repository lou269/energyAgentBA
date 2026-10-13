# E2 Vorprüfung Gate, Lauf e2_precheck_002

## Setup

- Urlaub event-2016-11: 2016-11-27 bis vor 2016-12-11
- Urlaub event-2016-12: 2016-12-17 bis vor 2016-12-31
- Urlaub event-2017-02: 2017-02-01 bis vor 2017-02-22
- Systeme: SYS1, SYS2
- Tage nach der Rückkehr: 60
- Commit: d9567b0 (mit lokalen Änderungen)

## event-2016-11: Erste Tage ab Urlaubsbeginn

| System | Gate offen [Urlaubstag] | Drift [Urlaubstag] | Reset [Urlaubstag] |
|---|---:|---:|---:|
| SYS1 | 0 | 16 | - |
| SYS2 | 0 | 16 | 16 |

## event-2016-11: Gate und Einordnung je Phase

| System | Phase | Tage | Gate offen | davon Einzeltag | davon Drift | davon nur eine Skala | new_pattern | low | peak | absence | Resets | Meldungen | Ausfalltage |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| SYS1 | vor dem Urlaub | 31 | 2 | 2 | 0 | 0 | 0 | 0 | 2 | 0 | 0 | 2 | 0 |
| SYS1 | Urlaub | 14 | 14 | 9 | 0 | 5 | 0 | 9 | 0 | 0 | 0 | 0 | 0 |
| SYS1 | nach der Rückkehr | 60 | 51 | 2 | 12 | 37 | 12 | 1 | 1 | 0 | 0 | 13 | 0 |
| SYS2 | vor dem Urlaub | 31 | 2 | 2 | 0 | 0 | 0 | 0 | 2 | 0 | 0 | 2 | 0 |
| SYS2 | Urlaub | 14 | 14 | 9 | 0 | 5 | 0 | 9 | 0 | 0 | 0 | 0 | 0 |
| SYS2 | nach der Rückkehr | 60 | 34 | 3 | 1 | 30 | 1 | 1 | 2 | 0 | 1 | 3 | 0 |

## event-2016-12: Erste Tage ab Urlaubsbeginn

| System | Gate offen [Urlaubstag] | Drift [Urlaubstag] | Reset [Urlaubstag] |
|---|---:|---:|---:|
| SYS1 | 0 | 9 | - |
| SYS2 | 0 | 9 | 9 |

## event-2016-12: Gate und Einordnung je Phase

| System | Phase | Tage | Gate offen | davon Einzeltag | davon Drift | davon nur eine Skala | new_pattern | low | peak | absence | Resets | Meldungen | Ausfalltage |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| SYS1 | vor dem Urlaub | 31 | 7 | 5 | 0 | 2 | 0 | 3 | 2 | 0 | 0 | 2 | 0 |
| SYS1 | Urlaub | 14 | 10 | 9 | 5 | 0 | 5 | 5 | 0 | 0 | 0 | 5 | 0 |
| SYS1 | nach der Rückkehr | 60 | 46 | 5 | 7 | 35 | 7 | 3 | 1 | 0 | 0 | 8 | 0 |
| SYS2 | vor dem Urlaub | 31 | 7 | 5 | 0 | 2 | 0 | 3 | 2 | 0 | 0 | 2 | 0 |
| SYS2 | Urlaub | 14 | 9 | 9 | 1 | 0 | 1 | 8 | 0 | 0 | 1 | 1 | 0 |
| SYS2 | nach der Rückkehr | 60 | 36 | 12 | 0 | 24 | 0 | 5 | 7 | 0 | 0 | 7 | 0 |

## event-2017-02: Erste Tage ab Urlaubsbeginn

| System | Gate offen [Urlaubstag] | Drift [Urlaubstag] | Reset [Urlaubstag] |
|---|---:|---:|---:|
| SYS1 | 0 | 18 | - |
| SYS2 | 0 | 18 | 18 |

## event-2017-02: Gate und Einordnung je Phase

| System | Phase | Tage | Gate offen | davon Einzeltag | davon Drift | davon nur eine Skala | new_pattern | low | peak | absence | Resets | Meldungen | Ausfalltage |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| SYS1 | vor dem Urlaub | 31 | 13 | 5 | 0 | 8 | 0 | 1 | 4 | 0 | 0 | 4 | 0 |
| SYS1 | Urlaub | 21 | 17 | 8 | 3 | 6 | 3 | 8 | 0 | 0 | 0 | 3 | 0 |
| SYS1 | nach der Rückkehr | 60 | 42 | 3 | 2 | 37 | 2 | 3 | 0 | 0 | 0 | 2 | 0 |
| SYS2 | vor dem Urlaub | 31 | 13 | 5 | 0 | 8 | 0 | 1 | 4 | 0 | 0 | 4 | 0 |
| SYS2 | Urlaub | 21 | 15 | 8 | 1 | 6 | 1 | 8 | 0 | 0 | 1 | 1 | 0 |
| SYS2 | nach der Rückkehr | 60 | 28 | 10 | 0 | 18 | 0 | 5 | 5 | 0 | 0 | 5 | 0 |

## Hinweise

- Urlaubstag = analysierter Tag seit Beginn der Abwesenheit, 0 = erster Urlaubstag
- Gate offen: Einzeltag (daily/weekday über ihrer Schwelle), Drift (weekly und long_term halten an) oder nur eine anhaltende Skala
- Reset = new_pattern mit advance_history_start, bei SYS1 nie

## Anhang

### event-2016-11: Je Tag ab Urlaubsbeginn

| System | Urlaubstag | Datum | Phase | Tagesmittel [W] | erwartet Wochentag [W] | z daily | z weekday | z weekly | long_term [%] | Streak weekly | Streak long_term | Level | Drift | Einordnung | Adaption |
|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---|---|
| SYS1 | 0 | 2016-11-27 | Urlaub | 258,7 | 439,8 | -1,5 | -2,6 | -0,5 | 4,4 | 0,0 | 0,0 | unusual | False | low | none |
| SYS1 | 1 | 2016-11-28 | Urlaub | 202,3 | 421,5 | -2,2 | -3,4 | -1,1 | 2,0 | 1,0 | 0,0 | unusual | False | low | none |
| SYS1 | 2 | 2016-11-29 | Urlaub | 226,3 | 432,4 | -2,0 | -3,2 | -1,8 | 3,2 | 2,0 | 0,0 | unusual | False | low | none |
| SYS1 | 3 | 2016-11-30 | Urlaub | 247,3 | 456,1 | -1,8 | -3,9 | -2,3 | 0,7 | 3,0 | 0,0 | unusual | False | low | none |
| SYS1 | 4 | 2016-12-01 | Urlaub | 174,8 | 393,7 | -1,7 | -3,8 | -2,8 | -3,0 | 4,0 | 0,0 | unusual | False | low | none |
| SYS1 | 5 | 2016-12-02 | Urlaub | 97,0 | 368,1 | -2,4 | -4,6 | -3,6 | -4,0 | 5,0 | 0,0 | unusual | False | low | none |
| SYS1 | 6 | 2016-12-03 | Urlaub | 104,5 | 379,0 | -2,2 | -4,4 | -4,6 | -3,6 | 6,0 | 0,0 | unusual | False | low | none |
| SYS1 | 7 | 2016-12-04 | Urlaub | 98,8 | 430,1 | -2,3 | -4,2 | -5,1 | -4,7 | 7,0 | 0,0 | unusual | False | low | none |
| SYS1 | 8 | 2016-12-05 | Urlaub | 224,7 | 420,6 | -1,2 | -2,5 | -5,0 | -6,0 | 7,0 | 0,0 | unusual | False | low | none |
| SYS1 | 9 | 2016-12-06 | Urlaub | 191,9 | 374,9 | -1,4 | -2,2 | -4,9 | -12,1 | 7,0 | 0,0 | normal | False | normal | none |
| SYS1 | 10 | 2016-12-07 | Urlaub | 257,5 | 451,1 | -0,8 | -2,3 | -4,7 | -13,9 | 7,0 | 0,0 | normal | False | normal | none |
| SYS1 | 11 | 2016-12-08 | Urlaub | 235,8 | 383,5 | -1,1 | -1,5 | -4,2 | -15,1 | 7,0 | 1,0 | normal | False | normal | none |
| SYS1 | 12 | 2016-12-09 | Urlaub | 177,4 | 346,2 | -1,4 | -1,6 | -3,7 | -18,7 | 7,0 | 2,0 | normal | False | normal | none |
| SYS1 | 13 | 2016-12-10 | Urlaub | 238,3 | 343,3 | -1,1 | -1,0 | -3,0 | -19,2 | 7,0 | 3,0 | normal | False | normal | none |
| SYS1 | 14 | 2016-12-11 | nach der Rückkehr | 460,6 | 388,8 | 0,3 | 0,7 | -1,9 | -19,4 | 7,0 | 4,0 | normal | False | normal | none |
| SYS1 | 15 | 2016-12-12 | nach der Rückkehr | 364,3 | 404,9 | -0,4 | -0,4 | -1,4 | -22,1 | 7,0 | 5,0 | normal | False | normal | none |
| SYS1 | 16 | 2016-12-13 | nach der Rückkehr | 522,0 | 299,4 | 1,3 | 2,1 | -0,7 | -22,5 | 6,0 | 6,0 | normal | True | new_pattern | none |
| SYS1 | 17 | 2016-12-14 | nach der Rückkehr | 442,4 | 390,2 | 0,6 | 0,4 | -0,3 | -20,6 | 5,0 | 7,0 | normal | False | normal | none |
| SYS1 | 18 | 2016-12-15 | nach der Rückkehr | 342,1 | 370,5 | -0,3 | -0,3 | -0,0 | -21,8 | 4,0 | 7,0 | normal | False | normal | none |
| SYS1 | 19 | 2016-12-16 | nach der Rückkehr | 460,1 | 342,0 | 0,6 | 1,0 | 0,5 | -22,2 | 3,0 | 7,0 | normal | False | normal | none |
| SYS1 | 20 | 2016-12-17 | nach der Rückkehr | 498,3 | 339,3 | 0,6 | 1,4 | 0,9 | -22,0 | 2,0 | 7,0 | normal | False | normal | none |
| SYS1 | 21 | 2016-12-18 | nach der Rückkehr | 222,6 | 388,8 | -0,2 | -1,5 | 0,6 | -24,2 | 1,0 | 7,0 | normal | False | normal | none |
| SYS1 | 22 | 2016-12-19 | nach der Rückkehr | 447,5 | 392,1 | 1,0 | 0,4 | 0,7 | -24,1 | 0,0 | 7,0 | normal | False | normal | none |
| SYS1 | 23 | 2016-12-20 | nach der Rückkehr | 365,0 | 380,7 | 0,0 | -0,1 | 0,5 | -26,1 | 0,0 | 7,0 | normal | False | normal | none |
| SYS1 | 24 | 2016-12-21 | nach der Rückkehr | 451,7 | 390,2 | 1,0 | 0,5 | 0,5 | -26,7 | 0,0 | 7,0 | normal | False | normal | none |
| SYS1 | 25 | 2016-12-22 | nach der Rückkehr | 517,0 | 354,0 | 1,2 | 1,2 | 0,8 | -26,1 | 0,0 | 7,0 | normal | False | normal | none |
| SYS1 | 26 | 2016-12-23 | nach der Rückkehr | 390,1 | 342,0 | -0,2 | 0,4 | 0,7 | -26,4 | 0,0 | 7,0 | normal | False | normal | none |
| SYS1 | 27 | 2016-12-24 | nach der Rückkehr | 400,2 | 341,8 | 0,1 | 0,5 | 0,5 | -27,8 | 0,0 | 7,0 | normal | False | normal | none |
| SYS1 | 28 | 2016-12-25 | nach der Rückkehr | 328,0 | 388,8 | -0,7 | -0,5 | 0,7 | -26,0 | 0,0 | 7,0 | normal | False | normal | none |
| SYS1 | 29 | 2016-12-26 | nach der Rückkehr | 387,9 | 404,9 | 1,9 | -0,1 | 0,6 | -22,8 | 0,0 | 7,0 | normal | False | normal | none |
| SYS1 | 30 | 2016-12-27 | nach der Rückkehr | 139,6 | 401,6 | -1,8 | -2,2 | 0,2 | -22,9 | 0,0 | 7,0 | normal | False | normal | none |
| SYS1 | 31 | 2016-12-28 | nach der Rückkehr | 118,4 | 435,8 | -1,8 | -2,9 | -0,3 | -22,5 | 0,0 | 7,0 | unusual | False | low | none |
| SYS1 | 32 | 2016-12-29 | nach der Rückkehr | 127,0 | 370,5 | -1,8 | -2,2 | -0,9 | -20,7 | 0,0 | 7,0 | normal | False | normal | none |
| SYS1 | 33 | 2016-12-30 | nach der Rückkehr | 132,6 | 367,8 | -1,2 | -2,0 | -1,4 | -18,5 | 1,0 | 7,0 | normal | False | normal | none |
| SYS1 | 34 | 2016-12-31 | nach der Rückkehr | 399,5 | 373,0 | 0,8 | 0,2 | -1,4 | -13,8 | 2,0 | 6,0 | normal | False | normal | none |
| SYS1 | 35 | 2017-01-01 | nach der Rückkehr | 611,7 | 347,9 | 2,7 | 2,1 | -0,9 | -6,5 | 2,0 | 5,0 | unusual | False | peak | none |
| SYS1 | 36 | 2017-01-02 | nach der Rückkehr | 368,8 | 392,1 | 0,8 | -0,2 | -1,0 | -3,4 | 2,0 | 4,0 | normal | False | normal | none |
| SYS1 | 37 | 2017-01-03 | nach der Rückkehr | 402,0 | 401,6 | 0,8 | 0,0 | -0,6 | 3,4 | 2,0 | 3,0 | normal | False | normal | none |
| SYS1 | 38 | 2017-01-04 | nach der Rückkehr | 425,4 | 390,2 | 0,2 | 0,3 | -0,1 | 7,6 | 2,0 | 2,0 | normal | False | normal | none |
| SYS1 | 39 | 2017-01-05 | nach der Rückkehr | 461,6 | 354,0 | 0,5 | 0,9 | 0,4 | 11,7 | 2,0 | 1,0 | normal | False | normal | none |
| SYS1 | 40 | 2017-01-06 | nach der Rückkehr | 447,2 | 367,8 | 0,5 | 0,6 | 0,9 | 18,7 | 1,0 | 1,0 | normal | False | normal | none |
| SYS1 | 41 | 2017-01-07 | nach der Rückkehr | 471,2 | 399,8 | 0,4 | 0,6 | 1,1 | 22,9 | 1,0 | 2,0 | normal | False | normal | none |
| SYS1 | 42 | 2017-01-08 | nach der Rückkehr | 472,5 | 368,9 | 1,4 | 1,0 | 0,9 | 23,0 | 1,0 | 3,0 | normal | False | normal | none |
| SYS1 | 43 | 2017-01-09 | nach der Rückkehr | 411,1 | 378,3 | 0,3 | 0,3 | 1,0 | 26,4 | 1,0 | 4,0 | normal | False | normal | none |
| SYS1 | 44 | 2017-01-10 | nach der Rückkehr | 344,9 | 383,5 | -0,7 | -0,4 | 0,9 | 23,1 | 1,0 | 5,0 | normal | False | normal | none |
| SYS1 | 45 | 2017-01-11 | nach der Rückkehr | 439,9 | 388,3 | 0,6 | 0,5 | 1,0 | 21,8 | 1,0 | 6,0 | normal | False | normal | none |
| SYS1 | 46 | 2017-01-12 | nach der Rückkehr | 455,9 | 354,0 | -0,2 | 0,9 | 1,0 | 24,6 | 1,0 | 7,0 | normal | False | normal | none |
| SYS1 | 47 | 2017-01-13 | nach der Rückkehr | 524,0 | 367,8 | 1,0 | 1,3 | 1,1 | 24,9 | 2,0 | 7,0 | normal | False | normal | none |
| SYS1 | 48 | 2017-01-14 | nach der Rückkehr | 495,2 | 409,0 | 1,2 | 0,8 | 1,1 | 23,7 | 2,0 | 7,0 | normal | False | normal | none |
| SYS1 | 49 | 2017-01-15 | nach der Rückkehr | 448,8 | 368,9 | 0,5 | 0,7 | 1,1 | 29,1 | 3,0 | 7,0 | normal | False | normal | none |
| SYS1 | 50 | 2017-01-16 | nach der Rückkehr | 557,6 | 378,3 | 0,5 | 1,6 | 1,3 | 29,9 | 4,0 | 7,0 | normal | False | normal | none |
| SYS1 | 51 | 2017-01-17 | nach der Rückkehr | 503,8 | 354,9 | 0,5 | 1,4 | 1,6 | 32,7 | 5,0 | 7,0 | normal | False | normal | none |
| SYS1 | 52 | 2017-01-18 | nach der Rückkehr | 407,6 | 427,3 | 0,2 | -0,2 | 1,5 | 31,8 | 6,0 | 7,0 | normal | True | new_pattern | none |
| SYS1 | 53 | 2017-01-19 | nach der Rückkehr | 375,0 | 354,0 | -0,2 | 0,2 | 1,4 | 27,9 | 7,0 | 7,0 | normal | True | new_pattern | none |
| SYS1 | 54 | 2017-01-20 | nach der Rückkehr | 464,5 | 367,8 | 0,2 | 0,9 | 1,3 | 28,1 | 7,0 | 7,0 | normal | True | new_pattern | none |
| SYS1 | 55 | 2017-01-21 | nach der Rückkehr | 414,7 | 433,4 | -0,7 | -0,2 | 1,2 | 29,2 | 7,0 | 7,0 | normal | True | new_pattern | none |
| SYS1 | 56 | 2017-01-22 | nach der Rückkehr | 590,9 | 388,4 | 1,3 | 1,8 | 1,4 | 31,2 | 7,0 | 7,0 | normal | True | new_pattern | none |
| SYS1 | 57 | 2017-01-23 | nach der Rückkehr | 479,5 | 378,3 | 0,3 | 0,8 | 1,2 | 29,5 | 7,0 | 7,0 | normal | True | new_pattern | none |
| SYS1 | 58 | 2017-01-24 | nach der Rückkehr | 442,3 | 354,9 | 0,2 | 0,7 | 1,1 | 34,2 | 7,0 | 7,0 | normal | True | new_pattern | none |
| SYS1 | 59 | 2017-01-25 | nach der Rückkehr | 397,9 | 416,5 | 0,0 | -0,1 | 1,1 | 39,4 | 7,0 | 7,0 | normal | True | new_pattern | none |
| SYS1 | 60 | 2017-01-26 | nach der Rückkehr | 509,1 | 358,6 | 0,4 | 1,1 | 1,2 | 44,6 | 7,0 | 7,0 | normal | True | new_pattern | none |
| SYS1 | 61 | 2017-01-27 | nach der Rückkehr | 377,8 | 418,6 | -0,7 | -0,3 | 1,1 | 46,9 | 7,0 | 7,0 | normal | True | new_pattern | none |
| SYS1 | 62 | 2017-01-28 | nach der Rückkehr | 251,0 | 407,4 | -1,3 | -1,3 | 0,8 | 40,4 | 6,0 | 7,0 | normal | True | new_pattern | none |
| SYS1 | 63 | 2017-01-29 | nach der Rückkehr | 465,7 | 454,7 | 0,5 | 0,1 | 0,6 | 31,2 | 5,0 | 7,0 | normal | False | normal | none |
| SYS1 | 64 | 2017-01-30 | nach der Rückkehr | 526,2 | 399,5 | 1,1 | 1,1 | 0,7 | 30,9 | 4,0 | 7,0 | normal | False | normal | none |
| SYS1 | 65 | 2017-01-31 | nach der Rückkehr | 432,6 | 383,5 | -0,3 | 0,5 | 0,6 | 28,4 | 3,0 | 7,0 | normal | False | normal | none |
| SYS1 | 66 | 2017-02-01 | nach der Rückkehr | 577,1 | 416,5 | 0,5 | 2,1 | 0,8 | 27,8 | 2,0 | 7,0 | normal | False | normal | none |
| SYS1 | 67 | 2017-02-02 | nach der Rückkehr | 383,0 | 415,4 | -1,1 | -0,4 | 0,6 | 24,2 | 1,0 | 7,0 | normal | False | normal | none |
| SYS1 | 68 | 2017-02-03 | nach der Rückkehr | 423,8 | 418,6 | -0,1 | 0,1 | 0,6 | 20,7 | 0,0 | 7,0 | normal | False | normal | none |
| SYS1 | 69 | 2017-02-04 | nach der Rückkehr | 502,1 | 407,4 | 0,9 | 1,2 | 1,0 | 18,4 | 0,0 | 7,0 | normal | False | normal | none |
| SYS1 | 70 | 2017-02-05 | nach der Rückkehr | 368,5 | 463,1 | -0,8 | -1,2 | 0,8 | 17,3 | 0,0 | 7,0 | normal | False | normal | none |
| SYS1 | 71 | 2017-02-06 | nach der Rückkehr | 528,4 | 429,3 | 0,6 | 1,2 | 0,8 | 17,9 | 0,0 | 7,0 | normal | False | normal | none |
| SYS1 | 72 | 2017-02-07 | nach der Rückkehr | 419,2 | 417,3 | -0,4 | 0,0 | 0,8 | 20,6 | 0,0 | 7,0 | normal | False | normal | none |
| SYS1 | 73 | 2017-02-08 | nach der Rückkehr | 463,9 | 432,6 | 0,0 | 0,4 | 0,6 | 20,8 | 0,0 | 7,0 | normal | False | normal | none |
| SYS2 | 0 | 2016-11-27 | Urlaub | 258,7 | 439,8 | -1,5 | -2,6 | -0,5 | 4,4 | 0,0 | 0,0 | unusual | False | low | none |
| SYS2 | 1 | 2016-11-28 | Urlaub | 202,3 | 421,5 | -2,2 | -3,4 | -1,1 | 2,0 | 1,0 | 0,0 | unusual | False | low | none |
| SYS2 | 2 | 2016-11-29 | Urlaub | 226,3 | 432,4 | -2,0 | -3,2 | -1,8 | 3,2 | 2,0 | 0,0 | unusual | False | low | none |
| SYS2 | 3 | 2016-11-30 | Urlaub | 247,3 | 456,1 | -1,8 | -3,9 | -2,3 | 0,7 | 3,0 | 0,0 | unusual | False | low | none |
| SYS2 | 4 | 2016-12-01 | Urlaub | 174,8 | 393,7 | -1,7 | -3,8 | -2,8 | -3,0 | 4,0 | 0,0 | unusual | False | low | none |
| SYS2 | 5 | 2016-12-02 | Urlaub | 97,0 | 368,1 | -2,4 | -4,6 | -3,6 | -4,0 | 5,0 | 0,0 | unusual | False | low | none |
| SYS2 | 6 | 2016-12-03 | Urlaub | 104,5 | 379,0 | -2,2 | -4,4 | -4,6 | -3,6 | 6,0 | 0,0 | unusual | False | low | none |
| SYS2 | 7 | 2016-12-04 | Urlaub | 98,8 | 430,1 | -2,3 | -4,2 | -5,1 | -4,7 | 7,0 | 0,0 | unusual | False | low | none |
| SYS2 | 8 | 2016-12-05 | Urlaub | 224,7 | 420,6 | -1,2 | -2,5 | -5,0 | -6,0 | 7,0 | 0,0 | unusual | False | low | none |
| SYS2 | 9 | 2016-12-06 | Urlaub | 191,9 | 374,9 | -1,4 | -2,2 | -4,9 | -12,1 | 7,0 | 0,0 | normal | False | normal | none |
| SYS2 | 10 | 2016-12-07 | Urlaub | 257,5 | 451,1 | -0,8 | -2,3 | -4,7 | -13,9 | 7,0 | 0,0 | normal | False | normal | none |
| SYS2 | 11 | 2016-12-08 | Urlaub | 235,8 | 383,5 | -1,1 | -1,5 | -4,2 | -15,1 | 7,0 | 1,0 | normal | False | normal | none |
| SYS2 | 12 | 2016-12-09 | Urlaub | 177,4 | 346,2 | -1,4 | -1,6 | -3,7 | -18,7 | 7,0 | 2,0 | normal | False | normal | none |
| SYS2 | 13 | 2016-12-10 | Urlaub | 238,3 | 343,3 | -1,1 | -1,0 | -3,0 | -19,2 | 7,0 | 3,0 | normal | False | normal | none |
| SYS2 | 14 | 2016-12-11 | nach der Rückkehr | 460,6 | 388,8 | 0,3 | 0,7 | -1,9 | -19,4 | 7,0 | 4,0 | normal | False | normal | none |
| SYS2 | 15 | 2016-12-12 | nach der Rückkehr | 364,3 | 404,9 | -0,4 | -0,4 | -1,4 | -22,1 | 7,0 | 5,0 | normal | False | normal | none |
| SYS2 | 16 | 2016-12-13 | nach der Rückkehr | 522,0 | 299,4 | 1,3 | 2,1 | -0,7 | -22,5 | 6,0 | 6,0 | normal | True | new_pattern | advance_history_start |
| SYS2 | 17 | 2016-12-14 | nach der Rückkehr | 442,4 | - | 2,1 | - | - | - | - | - | normal | False | normal | none |
| SYS2 | 18 | 2016-12-15 | nach der Rückkehr | 342,1 | - | 0,0 | - | - | - | - | - | normal | False | normal | none |
| SYS2 | 19 | 2016-12-16 | nach der Rückkehr | 460,1 | - | 1,2 | - | - | - | - | - | normal | False | normal | none |
| SYS2 | 20 | 2016-12-17 | nach der Rückkehr | 498,3 | - | 1,0 | - | - | - | - | - | normal | False | normal | none |
| SYS2 | 21 | 2016-12-18 | nach der Rückkehr | 222,6 | - | 0,0 | - | - | - | - | - | normal | False | normal | none |
| SYS2 | 22 | 2016-12-19 | nach der Rückkehr | 447,5 | - | 1,4 | - | - | - | - | - | normal | False | normal | none |
| SYS2 | 23 | 2016-12-20 | nach der Rückkehr | 365,0 | - | 0,2 | - | - | - | - | - | normal | False | normal | none |
| SYS2 | 24 | 2016-12-21 | nach der Rückkehr | 451,7 | - | 1,1 | - | 3,4 | - | - | - | normal | False | normal | none |
| SYS2 | 25 | 2016-12-22 | nach der Rückkehr | 517,0 | - | 1,2 | - | 3,7 | - | - | - | normal | False | normal | none |
| SYS2 | 26 | 2016-12-23 | nach der Rückkehr | 390,1 | - | -0,3 | - | 1,6 | - | - | - | normal | False | normal | none |
| SYS2 | 27 | 2016-12-24 | nach der Rückkehr | 400,2 | - | 0,2 | - | 0,5 | - | - | - | normal | False | normal | none |
| SYS2 | 28 | 2016-12-25 | nach der Rückkehr | 328,0 | - | -0,6 | - | 0,7 | - | - | - | normal | False | normal | none |
| SYS2 | 29 | 2016-12-26 | nach der Rückkehr | 387,9 | - | 2,0 | - | 0,4 | - | 3,0 | - | normal | False | normal | none |
| SYS2 | 30 | 2016-12-27 | nach der Rückkehr | 139,6 | - | -1,8 | - | -0,4 | - | 3,0 | - | normal | False | normal | none |
| SYS2 | 31 | 2016-12-28 | nach der Rückkehr | 118,4 | - | -1,5 | - | -1,7 | - | 1,0 | - | normal | False | normal | none |
| SYS2 | 32 | 2016-12-29 | nach der Rückkehr | 127,0 | - | -1,3 | - | -3,3 | - | 2,0 | - | normal | False | normal | none |
| SYS2 | 33 | 2016-12-30 | nach der Rückkehr | 132,6 | - | -0,8 | - | -4,6 | - | 3,0 | - | normal | False | normal | none |
| SYS2 | 34 | 2016-12-31 | nach der Rückkehr | 399,5 | - | 0,9 | - | -4,8 | - | 4,0 | - | normal | False | normal | none |
| SYS2 | 35 | 2017-01-01 | nach der Rückkehr | 611,7 | - | 2,5 | - | -3,7 | - | 5,0 | - | unusual | False | peak | none |
| SYS2 | 36 | 2017-01-02 | nach der Rückkehr | 368,8 | - | 0,8 | - | -4,0 | - | 6,0 | - | normal | False | normal | none |
| SYS2 | 37 | 2017-01-03 | nach der Rückkehr | 402,0 | - | 0,8 | - | -2,8 | - | 7,0 | - | normal | False | normal | none |
| SYS2 | 38 | 2017-01-04 | nach der Rückkehr | 425,4 | 350,0 | 0,2 | 0,5 | -1,1 | - | 7,0 | - | normal | False | normal | none |
| SYS2 | 39 | 2017-01-05 | nach der Rückkehr | 461,6 | 288,9 | 0,4 | 1,7 | 0,4 | - | 6,0 | - | normal | False | normal | none |
| SYS2 | 40 | 2017-01-06 | nach der Rückkehr | 447,2 | 283,8 | 0,5 | 1,1 | 1,2 | - | 1,0 | - | normal | False | normal | none |
| SYS2 | 41 | 2017-01-07 | nach der Rückkehr | 471,2 | 399,8 | 0,3 | 0,7 | 1,4 | - | 2,0 | - | normal | False | normal | none |
| SYS2 | 42 | 2017-01-08 | nach der Rückkehr | 472,5 | 394,3 | 1,4 | 0,8 | 1,1 | - | 3,0 | - | normal | False | normal | none |
| SYS2 | 43 | 2017-01-09 | nach der Rückkehr | 411,1 | 378,3 | 0,2 | 0,3 | 1,2 | - | 4,0 | - | normal | False | normal | none |
| SYS2 | 44 | 2017-01-10 | nach der Rückkehr | 344,9 | 383,5 | -1,0 | -0,4 | 1,2 | - | 5,0 | - | normal | False | normal | none |
| SYS2 | 45 | 2017-01-11 | nach der Rückkehr | 439,9 | 425,4 | 0,5 | 0,2 | 1,2 | - | 6,0 | - | normal | False | normal | none |
| SYS2 | 46 | 2017-01-12 | nach der Rückkehr | 455,9 | 342,1 | -0,4 | 1,3 | 1,2 | - | 7,0 | - | normal | False | normal | none |
| SYS2 | 47 | 2017-01-13 | nach der Rückkehr | 524,0 | 390,1 | 0,9 | 1,6 | 1,3 | - | 7,0 | - | normal | False | normal | none |
| SYS2 | 48 | 2017-01-14 | nach der Rückkehr | 495,2 | 400,2 | 1,1 | 1,1 | 1,3 | - | 7,0 | - | normal | False | normal | none |
| SYS2 | 49 | 2017-01-15 | nach der Rückkehr | 448,8 | 460,6 | 0,2 | -0,1 | 1,2 | - | 7,0 | - | normal | False | normal | none |
| SYS2 | 50 | 2017-01-16 | nach der Rückkehr | 557,6 | 387,9 | 0,3 | 2,3 | 1,4 | - | 7,0 | - | unusual | False | peak | none |
| SYS2 | 51 | 2017-01-17 | nach der Rückkehr | 503,8 | 365,0 | 0,2 | 2,0 | 1,8 | 11,6 | 7,0 | - | normal | False | normal | none |
| SYS2 | 52 | 2017-01-18 | nach der Rückkehr | 407,6 | 432,6 | -0,1 | -0,3 | 1,7 | 9,3 | 7,0 | - | normal | False | normal | none |
| SYS2 | 53 | 2017-01-19 | nach der Rückkehr | 375,0 | 399,0 | -0,6 | -0,3 | 1,5 | 5,2 | 7,0 | - | normal | False | normal | none |
| SYS2 | 54 | 2017-01-20 | nach der Rückkehr | 464,5 | 418,6 | -0,1 | 0,8 | 1,3 | 5,6 | 7,0 | - | normal | False | normal | none |
| SYS2 | 55 | 2017-01-21 | nach der Rückkehr | 414,7 | 435,7 | -1,5 | -0,4 | 1,1 | 5,4 | 7,0 | - | normal | False | normal | none |
| SYS2 | 56 | 2017-01-22 | nach der Rückkehr | 590,9 | 454,7 | 1,3 | 2,1 | 1,4 | 8,6 | 7,0 | 0,0 | normal | False | normal | none |
| SYS2 | 57 | 2017-01-23 | nach der Rückkehr | 479,5 | 399,5 | -0,0 | 1,1 | 1,2 | 9,3 | 7,0 | 0,0 | normal | False | normal | none |
| SYS2 | 58 | 2017-01-24 | nach der Rückkehr | 442,3 | 383,5 | -0,1 | 0,8 | 1,0 | 15,6 | 6,0 | 1,0 | normal | False | normal | none |
| SYS2 | 59 | 2017-01-25 | nach der Rückkehr | 397,9 | 425,4 | -0,2 | -0,3 | 0,9 | 22,1 | 5,0 | 2,0 | normal | False | normal | none |
| SYS2 | 60 | 2017-01-26 | nach der Rückkehr | 509,1 | 375,0 | 0,4 | 1,8 | 1,1 | 29,6 | 5,0 | 3,0 | normal | False | normal | none |
| SYS2 | 61 | 2017-01-27 | nach der Rückkehr | 377,8 | 447,2 | -1,3 | -1,0 | 0,9 | 35,6 | 4,0 | 4,0 | normal | False | normal | none |
| SYS2 | 62 | 2017-01-28 | nach der Rückkehr | 251,0 | 414,7 | -2,1 | -2,4 | 0,6 | 33,0 | 3,0 | 5,0 | unusual | False | low | none |
| SYS2 | 63 | 2017-01-29 | nach der Rückkehr | 465,7 | 460,6 | 0,6 | 0,1 | 0,3 | 27,5 | 2,0 | 6,0 | normal | False | normal | none |
| SYS2 | 64 | 2017-01-30 | nach der Rückkehr | 526,2 | 411,1 | 1,3 | 1,7 | 0,4 | 28,8 | 1,0 | 7,0 | normal | False | normal | none |
| SYS2 | 65 | 2017-01-31 | nach der Rückkehr | 432,6 | 402,0 | -0,5 | 0,4 | 0,3 | 28,4 | 1,0 | 7,0 | normal | False | normal | none |
| SYS2 | 66 | 2017-02-01 | nach der Rückkehr | 577,1 | 416,5 | 0,6 | 2,1 | 0,7 | 27,8 | 1,0 | 7,0 | normal | False | normal | none |
| SYS2 | 67 | 2017-02-02 | nach der Rückkehr | 383,0 | 415,4 | -1,3 | -0,4 | 0,4 | 24,2 | 0,0 | 7,0 | normal | False | normal | none |
| SYS2 | 68 | 2017-02-03 | nach der Rückkehr | 423,8 | 418,6 | -0,1 | 0,1 | 0,5 | 20,7 | 0,0 | 7,0 | normal | False | normal | none |
| SYS2 | 69 | 2017-02-04 | nach der Rückkehr | 502,1 | 407,4 | 0,9 | 1,2 | 1,0 | 18,4 | 0,0 | 7,0 | normal | False | normal | none |
| SYS2 | 70 | 2017-02-05 | nach der Rückkehr | 368,5 | 463,1 | -0,8 | -1,2 | 0,8 | 17,3 | 0,0 | 7,0 | normal | False | normal | none |
| SYS2 | 71 | 2017-02-06 | nach der Rückkehr | 528,4 | 429,3 | 0,6 | 1,2 | 0,8 | 17,9 | 0,0 | 7,0 | normal | False | normal | none |
| SYS2 | 72 | 2017-02-07 | nach der Rückkehr | 419,2 | 417,3 | -0,4 | 0,0 | 0,8 | 20,6 | 0,0 | 7,0 | normal | False | normal | none |
| SYS2 | 73 | 2017-02-08 | nach der Rückkehr | 463,9 | 432,6 | 0,0 | 0,4 | 0,5 | 20,8 | 0,0 | 7,0 | normal | False | normal | none |

### event-2016-12: Je Tag ab Urlaubsbeginn

| System | Urlaubstag | Datum | Phase | Tagesmittel [W] | erwartet Wochentag [W] | z daily | z weekday | z weekly | long_term [%] | Streak weekly | Streak long_term | Level | Drift | Einordnung | Adaption |
|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---|---|
| SYS1 | 0 | 2016-12-17 | Urlaub | 223,7 | 343,3 | -1,8 | -2,5 | 0,3 | -4,8 | 1,0 | 0,0 | unusual | False | low | none |
| SYS1 | 1 | 2016-12-18 | Urlaub | 164,1 | 435,1 | -1,2 | -5,7 | -0,5 | -7,6 | 1,0 | 0,0 | unusual | False | low | none |
| SYS1 | 2 | 2016-12-19 | Urlaub | 238,9 | 392,1 | -1,6 | -2,2 | -0,8 | -9,4 | 1,0 | 0,0 | normal | False | normal | none |
| SYS1 | 3 | 2016-12-20 | Urlaub | 226,3 | 443,3 | -1,4 | -2,9 | -1,6 | -12,9 | 1,0 | 0,0 | unusual | False | low | none |
| SYS1 | 4 | 2016-12-21 | Urlaub | 215,5 | 440,5 | -1,7 | -2,9 | -2,2 | -15,7 | 2,0 | 1,0 | unusual | False | low | none |
| SYS1 | 5 | 2016-12-22 | Urlaub | 262,5 | 370,5 | -1,4 | -1,4 | -2,4 | -17,4 | 3,0 | 2,0 | normal | False | normal | none |
| SYS1 | 6 | 2016-12-23 | Urlaub | 229,5 | 352,7 | -1,7 | -1,8 | -3,0 | -19,1 | 4,0 | 3,0 | normal | False | normal | none |
| SYS1 | 7 | 2016-12-24 | Urlaub | 224,8 | 341,8 | -1,7 | -1,5 | -3,0 | -22,1 | 5,0 | 4,0 | normal | False | normal | none |
| SYS1 | 8 | 2016-12-25 | Urlaub | 202,5 | 435,1 | -1,7 | -3,0 | -2,9 | -24,4 | 6,0 | 5,0 | unusual | False | low | none |
| SYS1 | 9 | 2016-12-26 | Urlaub | 156,3 | 386,6 | -1,4 | -2,8 | -3,2 | -24,8 | 7,0 | 6,0 | unusual | True | new_pattern | none |
| SYS1 | 10 | 2016-12-27 | Urlaub | 92,9 | 443,3 | -2,1 | -4,1 | -3,5 | -28,7 | 7,0 | 7,0 | unusual | True | new_pattern | none |
| SYS1 | 11 | 2016-12-28 | Urlaub | 86,9 | 440,5 | -2,1 | -4,2 | -3,7 | -31,6 | 7,0 | 7,0 | unusual | True | new_pattern | none |
| SYS1 | 12 | 2016-12-29 | Urlaub | 88,8 | 370,5 | -2,1 | -3,0 | -4,0 | -32,6 | 7,0 | 7,0 | unusual | True | new_pattern | none |
| SYS1 | 13 | 2016-12-30 | Urlaub | 97,7 | 352,7 | -1,8 | -2,3 | -4,1 | -31,7 | 7,0 | 7,0 | normal | True | new_pattern | none |
| SYS1 | 14 | 2016-12-31 | nach der Rückkehr | 399,5 | 341,8 | 0,8 | 0,5 | -3,5 | -28,1 | 7,0 | 7,0 | normal | True | new_pattern | none |
| SYS1 | 15 | 2017-01-01 | nach der Rückkehr | 611,7 | 388,8 | 2,9 | 2,0 | -2,4 | -22,3 | 7,0 | 7,0 | unusual | True | new_pattern | none |
| SYS1 | 16 | 2017-01-02 | nach der Rückkehr | 368,8 | 370,6 | 0,8 | -0,0 | -1,8 | -22,2 | 7,0 | 7,0 | normal | True | new_pattern | none |
| SYS1 | 17 | 2017-01-03 | nach der Rückkehr | 402,0 | 443,3 | 0,8 | -0,5 | -1,1 | -21,3 | 7,0 | 7,0 | normal | True | new_pattern | none |
| SYS1 | 18 | 2017-01-04 | nach der Rückkehr | 425,4 | 434,0 | 0,1 | -0,1 | -0,4 | -21,2 | 6,0 | 7,0 | normal | True | new_pattern | none |
| SYS1 | 19 | 2017-01-05 | nach der Rückkehr | 461,6 | 354,0 | 0,4 | 1,3 | 0,3 | -20,6 | 5,0 | 7,0 | normal | False | normal | none |
| SYS1 | 20 | 2017-01-06 | nach der Rückkehr | 447,2 | 352,7 | 0,5 | 1,2 | 0,9 | -18,8 | 4,0 | 7,0 | normal | False | normal | none |
| SYS1 | 21 | 2017-01-07 | nach der Rückkehr | 471,2 | 372,7 | 0,3 | 1,0 | 1,0 | -20,3 | 1,0 | 7,0 | normal | False | normal | none |
| SYS1 | 22 | 2017-01-08 | nach der Rückkehr | 472,5 | 435,2 | 1,7 | 0,4 | 0,9 | -20,2 | 1,0 | 7,0 | normal | False | normal | none |
| SYS1 | 23 | 2017-01-09 | nach der Rückkehr | 411,1 | 366,5 | 0,3 | 0,5 | 0,9 | -18,3 | 1,0 | 7,0 | normal | False | normal | none |
| SYS1 | 24 | 2017-01-10 | nach der Rückkehr | 344,9 | 438,2 | -1,0 | -1,0 | 0,9 | -20,6 | 1,0 | 7,0 | normal | False | normal | none |
| SYS1 | 25 | 2017-01-11 | nach der Rückkehr | 439,9 | 427,3 | 0,6 | 0,1 | 0,9 | -21,3 | 1,0 | 7,0 | normal | False | normal | none |
| SYS1 | 26 | 2017-01-12 | nach der Rückkehr | 455,9 | 354,0 | -0,3 | 1,2 | 0,9 | -19,5 | 1,0 | 7,0 | normal | False | normal | none |
| SYS1 | 27 | 2017-01-13 | nach der Rückkehr | 524,0 | 352,7 | 1,0 | 1,9 | 1,1 | -19,1 | 2,0 | 7,0 | normal | False | normal | none |
| SYS1 | 28 | 2017-01-14 | nach der Rückkehr | 495,2 | 408,7 | 1,3 | 1,0 | 1,1 | -15,0 | 2,0 | 7,0 | normal | False | normal | none |
| SYS1 | 29 | 2017-01-15 | nach der Rückkehr | 448,8 | 435,2 | 0,5 | 0,1 | 1,1 | -10,3 | 3,0 | 6,0 | normal | False | normal | none |
| SYS1 | 30 | 2017-01-16 | nach der Rückkehr | 557,6 | 366,5 | 0,5 | 2,4 | 1,3 | -5,6 | 4,0 | 5,0 | unusual | False | peak | none |
| SYS1 | 31 | 2017-01-17 | nach der Rückkehr | 503,8 | 420,1 | 0,5 | 1,0 | 1,5 | -0,8 | 5,0 | 4,0 | normal | False | normal | none |
| SYS1 | 32 | 2017-01-18 | nach der Rückkehr | 407,6 | 434,0 | 0,1 | -0,3 | 1,5 | 3,3 | 6,0 | 3,0 | normal | False | normal | none |
| SYS1 | 33 | 2017-01-19 | nach der Rückkehr | 375,0 | 354,0 | -0,5 | 0,3 | 1,4 | 5,6 | 7,0 | 2,0 | normal | False | normal | none |
| SYS1 | 34 | 2017-01-20 | nach der Rückkehr | 464,5 | 352,7 | 0,1 | 1,4 | 1,3 | 9,3 | 7,0 | 1,0 | normal | False | normal | none |
| SYS1 | 35 | 2017-01-21 | nach der Rückkehr | 414,7 | 433,0 | -1,1 | -0,2 | 1,1 | 14,2 | 7,0 | 0,0 | normal | False | normal | none |
| SYS1 | 36 | 2017-01-22 | nach der Rückkehr | 590,9 | 454,7 | 1,3 | 1,4 | 1,3 | 21,9 | 7,0 | 1,0 | normal | False | normal | none |
| SYS1 | 37 | 2017-01-23 | nach der Rückkehr | 479,5 | 366,5 | 0,2 | 1,0 | 1,2 | 27,6 | 7,0 | 2,0 | normal | False | normal | none |
| SYS1 | 38 | 2017-01-24 | nach der Rückkehr | 442,3 | 425,2 | 0,1 | 0,1 | 1,1 | 37,2 | 7,0 | 3,0 | normal | False | normal | none |
| SYS1 | 39 | 2017-01-25 | nach der Rückkehr | 397,9 | 432,0 | -0,1 | -0,4 | 1,0 | 47,2 | 7,0 | 4,0 | normal | False | normal | none |
| SYS1 | 40 | 2017-01-26 | nach der Rückkehr | 509,1 | 358,6 | 0,4 | 1,7 | 1,2 | 56,7 | 7,0 | 5,0 | normal | False | normal | none |
| SYS1 | 41 | 2017-01-27 | nach der Rückkehr | 377,8 | 403,5 | -1,0 | -0,3 | 1,1 | 61,0 | 7,0 | 6,0 | normal | True | new_pattern | none |
| SYS1 | 42 | 2017-01-28 | nach der Rückkehr | 251,0 | 407,1 | -1,7 | -1,3 | 0,8 | 53,9 | 6,0 | 7,0 | normal | True | new_pattern | none |
| SYS1 | 43 | 2017-01-29 | nach der Rückkehr | 465,7 | 454,7 | 0,6 | 0,1 | 0,6 | 43,7 | 5,0 | 7,0 | normal | False | normal | none |
| SYS1 | 44 | 2017-01-30 | nach der Rückkehr | 526,2 | 372,8 | 1,1 | 1,3 | 0,7 | 45,7 | 4,0 | 7,0 | normal | False | normal | none |
| SYS1 | 45 | 2017-01-31 | nach der Rückkehr | 432,6 | 422,1 | -0,2 | 0,1 | 0,6 | 46,8 | 3,0 | 7,0 | normal | False | normal | none |
| SYS1 | 46 | 2017-02-01 | nach der Rückkehr | 577,1 | 416,5 | 0,6 | 1,5 | 0,9 | 48,8 | 2,0 | 7,0 | normal | False | normal | none |
| SYS1 | 47 | 2017-02-02 | nach der Rückkehr | 383,0 | 381,9 | -1,0 | 0,0 | 0,7 | 46,6 | 1,0 | 7,0 | normal | False | normal | none |
| SYS1 | 48 | 2017-02-03 | nach der Rückkehr | 423,8 | 412,5 | 0,0 | 0,1 | 0,7 | 44,9 | 0,0 | 7,0 | normal | False | normal | none |
| SYS1 | 49 | 2017-02-04 | nach der Rückkehr | 502,1 | 407,1 | 0,9 | 0,9 | 1,0 | 45,9 | 0,0 | 7,0 | normal | False | normal | none |
| SYS1 | 50 | 2017-02-05 | nach der Rückkehr | 368,5 | 463,1 | -0,5 | -0,9 | 0,9 | 44,5 | 0,0 | 7,0 | normal | False | normal | none |
| SYS1 | 51 | 2017-02-06 | nach der Rückkehr | 528,4 | 389,9 | 0,7 | 1,2 | 0,8 | 45,0 | 0,0 | 7,0 | normal | False | normal | none |
| SYS1 | 52 | 2017-02-07 | nach der Rückkehr | 419,2 | 417,3 | -0,3 | 0,0 | 0,8 | 48,9 | 0,0 | 7,0 | normal | False | normal | none |
| SYS1 | 53 | 2017-02-08 | nach der Rückkehr | 463,9 | 416,5 | 0,1 | 0,4 | 0,6 | 49,2 | 0,0 | 7,0 | normal | False | normal | none |
| SYS1 | 54 | 2017-02-09 | nach der Rückkehr | 451,0 | 379,0 | -0,1 | 0,6 | 0,7 | 47,2 | 0,0 | 7,0 | normal | False | normal | none |
| SYS1 | 55 | 2017-02-10 | nach der Rückkehr | 424,6 | 435,5 | 1,9 | -0,1 | 0,7 | 45,0 | 0,0 | 7,0 | normal | False | normal | none |
| SYS1 | 56 | 2017-02-11 | nach der Rückkehr | 168,3 | 407,1 | -2,8 | -2,1 | 0,2 | 37,0 | 0,0 | 7,0 | unusual | False | low | none |
| SYS1 | 57 | 2017-02-12 | nach der Rückkehr | 165,2 | 457,3 | -2,8 | -2,6 | -0,0 | 29,8 | 0,0 | 7,0 | unusual | False | low | none |
| SYS1 | 58 | 2017-02-13 | nach der Rückkehr | 172,4 | 445,3 | -2,1 | -2,4 | -0,5 | 21,5 | 0,0 | 7,0 | unusual | False | low | none |
| SYS1 | 59 | 2017-02-14 | nach der Rückkehr | 166,4 | 410,6 | -2,1 | -2,2 | -0,9 | 14,6 | 0,0 | 7,0 | normal | False | normal | none |
| SYS1 | 60 | 2017-02-15 | nach der Rückkehr | 183,0 | 416,5 | -1,5 | -1,8 | -1,2 | 10,2 | 1,0 | 6,0 | normal | False | normal | none |
| SYS1 | 61 | 2017-02-16 | nach der Rückkehr | 171,8 | 417,0 | -1,7 | -2,0 | -1,6 | 7,0 | 2,0 | 5,0 | normal | False | normal | none |
| SYS1 | 62 | 2017-02-17 | nach der Rückkehr | 358,6 | 424,2 | -0,1 | -0,5 | -1,7 | 3,6 | 3,0 | 4,0 | normal | False | normal | none |
| SYS1 | 63 | 2017-02-18 | nach der Rückkehr | 413,4 | 407,1 | 0,3 | 0,1 | -1,4 | 1,7 | 4,0 | 3,0 | normal | False | normal | none |
| SYS1 | 64 | 2017-02-19 | nach der Rückkehr | 452,8 | 457,3 | -0,1 | -0,0 | -1,0 | -3,1 | 5,0 | 2,0 | normal | False | normal | none |
| SYS1 | 65 | 2017-02-20 | nach der Rückkehr | 487,6 | 445,3 | 0,4 | 0,4 | -0,6 | -5,8 | 5,0 | 1,0 | normal | False | normal | none |
| SYS1 | 66 | 2017-02-21 | nach der Rückkehr | 312,6 | 410,6 | -1,4 | -1,2 | -0,4 | -9,7 | 5,0 | 0,0 | normal | False | normal | none |
| SYS1 | 67 | 2017-02-22 | nach der Rückkehr | 446,6 | 416,5 | 0,6 | 0,4 | -0,1 | -11,6 | 4,0 | 0,0 | normal | False | normal | none |
| SYS1 | 68 | 2017-02-23 | nach der Rückkehr | 406,5 | 417,0 | -0,8 | -0,1 | 0,2 | -15,5 | 3,0 | 1,0 | normal | False | normal | none |
| SYS1 | 69 | 2017-02-24 | nach der Rückkehr | 487,5 | 424,2 | 1,6 | 0,9 | 0,4 | -16,5 | 2,0 | 2,0 | normal | False | normal | none |
| SYS1 | 70 | 2017-02-25 | nach der Rückkehr | 379,1 | 414,1 | -0,4 | -0,5 | 0,4 | -14,5 | 1,0 | 3,0 | normal | False | normal | none |
| SYS1 | 71 | 2017-02-26 | nach der Rückkehr | 393,1 | 459,2 | 0,2 | -1,0 | 0,3 | -14,0 | 0,0 | 3,0 | normal | False | normal | none |
| SYS1 | 72 | 2017-02-27 | nach der Rückkehr | 503,4 | 483,6 | 1,3 | 0,3 | 0,3 | -15,3 | 0,0 | 4,0 | normal | False | normal | none |
| SYS1 | 73 | 2017-02-28 | nach der Rückkehr | 463,3 | 410,6 | -0,5 | 0,9 | 0,5 | -15,3 | 0,0 | 5,0 | normal | False | normal | none |
| SYS2 | 0 | 2016-12-17 | Urlaub | 223,7 | 343,3 | -1,8 | -2,5 | 0,3 | -4,8 | 1,0 | 0,0 | unusual | False | low | none |
| SYS2 | 1 | 2016-12-18 | Urlaub | 164,1 | 435,1 | -1,2 | -5,7 | -0,5 | -7,6 | 1,0 | 0,0 | unusual | False | low | none |
| SYS2 | 2 | 2016-12-19 | Urlaub | 238,9 | 392,1 | -1,6 | -2,2 | -0,8 | -9,4 | 1,0 | 0,0 | normal | False | normal | none |
| SYS2 | 3 | 2016-12-20 | Urlaub | 226,3 | 443,3 | -1,4 | -2,9 | -1,6 | -12,9 | 1,0 | 0,0 | unusual | False | low | none |
| SYS2 | 4 | 2016-12-21 | Urlaub | 215,5 | 440,5 | -1,7 | -2,9 | -2,2 | -15,7 | 2,0 | 1,0 | unusual | False | low | none |
| SYS2 | 5 | 2016-12-22 | Urlaub | 262,5 | 370,5 | -1,4 | -1,4 | -2,4 | -17,4 | 3,0 | 2,0 | normal | False | normal | none |
| SYS2 | 6 | 2016-12-23 | Urlaub | 229,5 | 352,7 | -1,7 | -1,8 | -3,0 | -19,1 | 4,0 | 3,0 | normal | False | normal | none |
| SYS2 | 7 | 2016-12-24 | Urlaub | 224,8 | 341,8 | -1,7 | -1,5 | -3,0 | -22,1 | 5,0 | 4,0 | normal | False | normal | none |
| SYS2 | 8 | 2016-12-25 | Urlaub | 202,5 | 435,1 | -1,7 | -3,0 | -2,9 | -24,4 | 6,0 | 5,0 | unusual | False | low | none |
| SYS2 | 9 | 2016-12-26 | Urlaub | 156,3 | 386,6 | -1,4 | -2,8 | -3,2 | -24,8 | 7,0 | 6,0 | unusual | True | new_pattern | advance_history_start |
| SYS2 | 10 | 2016-12-27 | Urlaub | 92,9 | - | -15,8 | - | - | - | - | - | unusual | False | low | none |
| SYS2 | 11 | 2016-12-28 | Urlaub | 86,9 | - | -14,2 | - | - | - | - | - | unusual | False | low | none |
| SYS2 | 12 | 2016-12-29 | Urlaub | 88,8 | - | -9,7 | - | - | - | - | - | unusual | False | low | none |
| SYS2 | 13 | 2016-12-30 | Urlaub | 97,7 | - | -2,0 | - | - | - | - | - | normal | False | normal | none |
| SYS2 | 14 | 2016-12-31 | nach der Rückkehr | 399,5 | - | 6,4 | - | - | - | - | - | unusual | False | peak | none |
| SYS2 | 15 | 2017-01-01 | nach der Rückkehr | 611,7 | - | 12,6 | - | - | - | - | - | unusual | False | peak | none |
| SYS2 | 16 | 2017-01-02 | nach der Rückkehr | 368,8 | - | 6,0 | - | - | - | - | - | unusual | False | peak | none |
| SYS2 | 17 | 2017-01-03 | nach der Rückkehr | 402,0 | - | 4,6 | - | 6,4 | - | - | - | unusual | False | peak | none |
| SYS2 | 18 | 2017-01-04 | nach der Rückkehr | 425,4 | - | 2,6 | - | 7,7 | - | - | - | unusual | False | peak | none |
| SYS2 | 19 | 2017-01-05 | nach der Rückkehr | 461,6 | - | 2,4 | - | 7,8 | - | - | - | unusual | False | peak | none |
| SYS2 | 20 | 2017-01-06 | nach der Rückkehr | 447,2 | - | 2,0 | - | 8,3 | - | - | - | normal | False | normal | none |
| SYS2 | 21 | 2017-01-07 | nach der Rückkehr | 471,2 | - | 1,6 | - | 9,4 | - | - | - | normal | False | normal | none |
| SYS2 | 22 | 2017-01-08 | nach der Rückkehr | 472,5 | - | 2,3 | - | 7,9 | - | 6,0 | - | unusual | False | peak | none |
| SYS2 | 23 | 2017-01-09 | nach der Rückkehr | 411,1 | - | 1,3 | - | 6,6 | - | 7,0 | - | normal | False | normal | none |
| SYS2 | 24 | 2017-01-10 | nach der Rückkehr | 344,9 | - | 0,3 | - | 4,6 | - | 7,0 | - | normal | False | normal | none |
| SYS2 | 25 | 2017-01-11 | nach der Rückkehr | 439,9 | - | 1,1 | - | 3,4 | - | 7,0 | - | normal | False | normal | none |
| SYS2 | 26 | 2017-01-12 | nach der Rückkehr | 455,9 | - | 0,4 | - | 2,5 | - | 7,0 | - | normal | False | normal | none |
| SYS2 | 27 | 2017-01-13 | nach der Rückkehr | 524,0 | - | 1,1 | - | 2,0 | - | 7,0 | - | normal | False | normal | none |
| SYS2 | 28 | 2017-01-14 | nach der Rückkehr | 495,2 | - | 1,0 | - | 1,7 | - | 7,0 | - | normal | False | normal | none |
| SYS2 | 29 | 2017-01-15 | nach der Rückkehr | 448,8 | - | 0,4 | - | 1,4 | - | 7,0 | - | normal | False | normal | none |
| SYS2 | 30 | 2017-01-16 | nach der Rückkehr | 557,6 | - | 0,3 | - | 1,5 | - | 7,0 | - | normal | False | normal | none |
| SYS2 | 31 | 2017-01-17 | nach der Rückkehr | 503,8 | 285,6 | 0,2 | 1,4 | 1,6 | - | 7,0 | - | normal | False | normal | none |
| SYS2 | 32 | 2017-01-18 | nach der Rückkehr | 407,6 | 320,4 | -0,1 | 0,5 | 1,5 | - | 7,0 | - | normal | False | normal | none |
| SYS2 | 33 | 2017-01-19 | nach der Rückkehr | 375,0 | 359,2 | -0,4 | 0,1 | 1,3 | - | 7,0 | - | normal | False | normal | none |
| SYS2 | 34 | 2017-01-20 | nach der Rückkehr | 464,5 | 338,3 | 0,0 | 0,8 | 1,2 | - | 7,0 | - | normal | False | normal | none |
| SYS2 | 35 | 2017-01-21 | nach der Rückkehr | 414,7 | 435,3 | -1,1 | -0,2 | 1,0 | - | 7,0 | - | normal | False | normal | none |
| SYS2 | 36 | 2017-01-22 | nach der Rückkehr | 590,9 | 460,7 | 1,0 | 1,1 | 1,2 | - | 7,0 | - | normal | False | normal | none |
| SYS2 | 37 | 2017-01-23 | nach der Rückkehr | 479,5 | 389,9 | 0,0 | 0,7 | 1,0 | - | 6,0 | - | normal | False | normal | none |
| SYS2 | 38 | 2017-01-24 | nach der Rückkehr | 442,3 | 344,9 | -0,1 | 0,8 | 0,9 | - | 5,0 | - | normal | False | normal | none |
| SYS2 | 39 | 2017-01-25 | nach der Rückkehr | 397,9 | 407,6 | -0,1 | -0,1 | 0,8 | - | 4,0 | - | normal | False | normal | none |
| SYS2 | 40 | 2017-01-26 | nach der Rückkehr | 509,1 | 375,0 | 0,4 | 1,2 | 0,9 | - | 3,0 | - | normal | False | normal | none |
| SYS2 | 41 | 2017-01-27 | nach der Rückkehr | 377,8 | 447,2 | -1,4 | -0,7 | 0,8 | - | 2,0 | - | normal | False | normal | none |
| SYS2 | 42 | 2017-01-28 | nach der Rückkehr | 251,0 | 414,7 | -2,1 | -1,6 | 0,6 | - | 1,0 | - | normal | False | normal | none |
| SYS2 | 43 | 2017-01-29 | nach der Rückkehr | 465,7 | 472,5 | 0,5 | -0,1 | 0,4 | - | 0,0 | - | normal | False | normal | none |
| SYS2 | 44 | 2017-01-30 | nach der Rückkehr | 526,2 | 411,1 | 1,4 | 1,1 | 0,4 | 92,5 | 0,0 | - | normal | False | normal | none |
| SYS2 | 45 | 2017-01-31 | nach der Rückkehr | 432,6 | 373,5 | -0,3 | 0,5 | 0,4 | 84,1 | 0,0 | - | normal | False | normal | none |
| SYS2 | 46 | 2017-02-01 | nach der Rückkehr | 577,1 | 402,7 | 0,7 | 1,8 | 0,6 | 78,0 | 0,0 | - | normal | False | normal | none |
| SYS2 | 47 | 2017-02-02 | nach der Rückkehr | 383,0 | 415,4 | -1,4 | -0,3 | 0,4 | 68,9 | 0,0 | - | normal | False | normal | none |
| SYS2 | 48 | 2017-02-03 | nach der Rückkehr | 423,8 | 412,5 | -0,1 | 0,1 | 0,5 | 62,6 | 0,0 | - | normal | False | normal | none |
| SYS2 | 49 | 2017-02-04 | nach der Rückkehr | 502,1 | 407,1 | 1,0 | 0,9 | 0,8 | 57,2 | 0,0 | 6,0 | normal | False | normal | none |
| SYS2 | 50 | 2017-02-05 | nach der Rückkehr | 368,5 | 469,1 | -0,8 | -0,9 | 0,7 | 51,1 | 0,0 | 7,0 | normal | False | normal | none |
| SYS2 | 51 | 2017-02-06 | nach der Rückkehr | 528,4 | 445,3 | 0,7 | 0,7 | 0,7 | 49,7 | 0,0 | 7,0 | normal | False | normal | none |
| SYS2 | 52 | 2017-02-07 | nach der Rückkehr | 419,2 | 402,0 | -0,3 | 0,2 | 0,6 | 49,7 | 0,0 | 7,0 | normal | False | normal | none |
| SYS2 | 53 | 2017-02-08 | nach der Rückkehr | 463,9 | 407,6 | 0,1 | 0,5 | 0,5 | 47,1 | 0,0 | 7,0 | normal | False | normal | none |
| SYS2 | 54 | 2017-02-09 | nach der Rückkehr | 451,0 | 383,0 | -0,2 | 0,7 | 0,6 | 44,2 | 0,0 | 7,0 | normal | False | normal | none |
| SYS2 | 55 | 2017-02-10 | nach der Rückkehr | 424,6 | 423,8 | 2,0 | 0,0 | 0,6 | 39,5 | 0,0 | 7,0 | normal | False | normal | none |
| SYS2 | 56 | 2017-02-11 | nach der Rückkehr | 168,3 | 414,7 | -3,0 | -3,4 | 0,1 | 33,2 | 0,0 | 7,0 | unusual | False | low | none |
| SYS2 | 57 | 2017-02-12 | nach der Rückkehr | 165,2 | 465,7 | -2,9 | -3,6 | -0,2 | 28,4 | 0,0 | 7,0 | unusual | False | low | none |
| SYS2 | 58 | 2017-02-13 | nach der Rückkehr | 172,4 | 479,5 | -2,8 | -3,2 | -0,7 | 21,5 | 0,0 | 7,0 | unusual | False | low | none |
| SYS2 | 59 | 2017-02-14 | nach der Rückkehr | 166,4 | 410,6 | -2,7 | -2,3 | -1,0 | 14,6 | 1,0 | 7,0 | unusual | False | low | none |
| SYS2 | 60 | 2017-02-15 | nach der Rückkehr | 183,0 | 416,5 | -2,3 | -2,1 | -1,4 | 10,2 | 2,0 | 6,0 | unusual | False | low | none |
| SYS2 | 61 | 2017-02-16 | nach der Rückkehr | 171,8 | 417,0 | -2,1 | -2,1 | -1,8 | 7,0 | 3,0 | 5,0 | normal | False | normal | none |
| SYS2 | 62 | 2017-02-17 | nach der Rückkehr | 358,6 | 424,2 | -0,1 | -0,5 | -2,0 | 3,6 | 4,0 | 4,0 | normal | False | normal | none |
| SYS2 | 63 | 2017-02-18 | nach der Rückkehr | 413,4 | 407,1 | 0,3 | 0,1 | -1,6 | 1,7 | 5,0 | 3,0 | normal | False | normal | none |
| SYS2 | 64 | 2017-02-19 | nach der Rückkehr | 452,8 | 457,3 | -0,1 | -0,0 | -1,2 | -3,1 | 6,0 | 2,0 | normal | False | normal | none |
| SYS2 | 65 | 2017-02-20 | nach der Rückkehr | 487,6 | 445,3 | 0,4 | 0,4 | -0,8 | -5,8 | 6,0 | 1,0 | normal | False | normal | none |
| SYS2 | 66 | 2017-02-21 | nach der Rückkehr | 312,6 | 410,6 | -1,4 | -1,2 | -0,6 | -9,7 | 5,0 | 0,0 | normal | False | normal | none |
| SYS2 | 67 | 2017-02-22 | nach der Rückkehr | 446,6 | 416,5 | 0,6 | 0,4 | -0,1 | -11,6 | 4,0 | 0,0 | normal | False | normal | none |
| SYS2 | 68 | 2017-02-23 | nach der Rückkehr | 406,5 | 417,0 | -0,8 | -0,1 | 0,2 | -15,5 | 3,0 | 1,0 | normal | False | normal | none |
| SYS2 | 69 | 2017-02-24 | nach der Rückkehr | 487,5 | 424,2 | 1,6 | 0,9 | 0,4 | -16,5 | 2,0 | 2,0 | normal | False | normal | none |
| SYS2 | 70 | 2017-02-25 | nach der Rückkehr | 379,1 | 414,1 | -0,4 | -0,5 | 0,4 | -14,5 | 1,0 | 3,0 | normal | False | normal | none |
| SYS2 | 71 | 2017-02-26 | nach der Rückkehr | 393,1 | 459,2 | 0,2 | -1,0 | 0,3 | -14,0 | 0,0 | 3,0 | normal | False | normal | none |
| SYS2 | 72 | 2017-02-27 | nach der Rückkehr | 503,4 | 483,6 | 1,3 | 0,3 | 0,3 | -15,3 | 0,0 | 4,0 | normal | False | normal | none |
| SYS2 | 73 | 2017-02-28 | nach der Rückkehr | 463,3 | 410,6 | -0,5 | 0,9 | 0,5 | -15,3 | 0,0 | 5,0 | normal | False | normal | none |

### event-2017-02: Je Tag ab Urlaubsbeginn

| System | Urlaubstag | Datum | Phase | Tagesmittel [W] | erwartet Wochentag [W] | z daily | z weekday | z weekly | long_term [%] | Streak weekly | Streak long_term | Level | Drift | Einordnung | Adaption |
|---|---:|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---|---|
| SYS1 | 0 | 2017-02-01 | Urlaub | 279,6 | 432,0 | -1,9 | -2,3 | 0,2 | 17,7 | 1,0 | 7,0 | unusual | False | low | none |
| SYS1 | 1 | 2017-02-02 | Urlaub | 232,2 | 422,4 | -2,6 | -3,0 | -0,4 | 14,7 | 0,0 | 7,0 | unusual | False | low | none |
| SYS1 | 2 | 2017-02-03 | Urlaub | 210,6 | 418,6 | -2,8 | -3,1 | -0,8 | 11,6 | 0,0 | 6,0 | unusual | False | low | none |
| SYS1 | 3 | 2017-02-04 | Urlaub | 252,2 | 443,0 | -2,1 | -2,4 | -0,9 | 9,9 | 0,0 | 5,0 | unusual | False | low | none |
| SYS1 | 4 | 2017-02-05 | Urlaub | 235,8 | 463,1 | -2,2 | -2,6 | -1,4 | 7,6 | 1,0 | 4,0 | unusual | False | low | none |
| SYS1 | 5 | 2017-02-06 | Urlaub | 258,8 | 429,3 | -2,0 | -1,8 | -2,1 | 5,7 | 2,0 | 3,0 | normal | False | normal | none |
| SYS1 | 6 | 2017-02-07 | Urlaub | 276,7 | 417,3 | -1,5 | -1,5 | -2,6 | 6,8 | 3,0 | 2,0 | normal | False | normal | none |
| SYS1 | 7 | 2017-02-08 | Urlaub | 256,2 | 416,5 | -2,0 | -2,1 | -2,7 | 5,1 | 4,0 | 1,0 | normal | False | normal | none |
| SYS1 | 8 | 2017-02-09 | Urlaub | 281,1 | 415,4 | -1,6 | -1,7 | -2,6 | 2,3 | 5,0 | 0,0 | normal | False | normal | none |
| SYS1 | 9 | 2017-02-10 | Urlaub | 237,3 | 418,6 | -1,2 | -1,9 | -2,5 | -0,9 | 6,0 | 0,0 | normal | False | normal | none |
| SYS1 | 10 | 2017-02-11 | Urlaub | 122,0 | 407,4 | -2,2 | -2,5 | -2,7 | -4,4 | 7,0 | 0,0 | unusual | False | low | none |
| SYS1 | 11 | 2017-02-12 | Urlaub | 115,4 | 457,3 | -2,2 | -3,0 | -2,9 | -9,4 | 7,0 | 0,0 | unusual | False | low | none |
| SYS1 | 12 | 2017-02-13 | Urlaub | 128,2 | 429,3 | -1,9 | -2,4 | -3,0 | -14,2 | 7,0 | 0,0 | unusual | False | low | none |
| SYS1 | 13 | 2017-02-14 | Urlaub | 121,2 | 383,5 | -1,9 | -2,1 | -3,2 | -18,6 | 7,0 | 1,0 | normal | False | normal | none |
| SYS1 | 14 | 2017-02-15 | Urlaub | 135,8 | 402,7 | -1,5 | -2,0 | -3,2 | -20,7 | 7,0 | 2,0 | normal | False | normal | none |
| SYS1 | 15 | 2017-02-16 | Urlaub | 130,3 | 415,4 | -1,5 | -2,1 | -3,4 | -21,9 | 7,0 | 3,0 | normal | False | normal | none |
| SYS1 | 16 | 2017-02-17 | Urlaub | 201,2 | 384,0 | -1,0 | -1,4 | -3,3 | -24,8 | 7,0 | 4,0 | normal | False | normal | none |
| SYS1 | 17 | 2017-02-18 | Urlaub | 210,0 | 399,8 | -0,9 | -1,4 | -3,0 | -26,7 | 7,0 | 5,0 | normal | False | normal | none |
| SYS1 | 18 | 2017-02-19 | Urlaub | 223,0 | 457,3 | -1,0 | -1,5 | -2,7 | -31,7 | 7,0 | 6,0 | normal | True | new_pattern | none |
| SYS1 | 19 | 2017-02-20 | Urlaub | 219,1 | 399,5 | -0,9 | -1,2 | -2,3 | -34,5 | 7,0 | 7,0 | normal | True | new_pattern | none |
| SYS1 | 20 | 2017-02-21 | Urlaub | 217,6 | 373,5 | -0,7 | -0,9 | -2,0 | -38,1 | 7,0 | 7,0 | normal | True | new_pattern | none |
| SYS1 | 21 | 2017-02-22 | nach der Rückkehr | 446,6 | 338,8 | 0,7 | 0,6 | -1,4 | -39,1 | 7,0 | 7,0 | normal | True | new_pattern | none |
| SYS1 | 22 | 2017-02-23 | nach der Rückkehr | 406,5 | 328,0 | 0,1 | 0,4 | -0,9 | -41,8 | 6,0 | 7,0 | normal | True | new_pattern | none |
| SYS1 | 23 | 2017-02-24 | nach der Rückkehr | 487,5 | 307,6 | 1,1 | 1,1 | -0,4 | -42,0 | 5,0 | 7,0 | normal | False | normal | none |
| SYS1 | 24 | 2017-02-25 | nach der Rückkehr | 379,1 | 325,8 | 0,2 | 0,3 | -0,2 | -40,3 | 4,0 | 7,0 | normal | False | normal | none |
| SYS1 | 25 | 2017-02-26 | nach der Rückkehr | 393,1 | 457,3 | 0,4 | -0,4 | 0,1 | -40,2 | 3,0 | 7,0 | normal | False | normal | none |
| SYS1 | 26 | 2017-02-27 | nach der Rückkehr | 503,4 | 389,9 | 0,9 | 0,7 | 0,5 | -41,2 | 2,0 | 7,0 | normal | False | normal | none |
| SYS1 | 27 | 2017-02-28 | nach der Rückkehr | 463,3 | 373,5 | 0,0 | 0,6 | 0,8 | -41,1 | 1,0 | 7,0 | normal | False | normal | none |
| SYS1 | 28 | 2017-03-01 | nach der Rückkehr | 412,8 | 402,7 | 0,2 | 0,1 | 0,8 | -39,3 | 0,0 | 7,0 | normal | False | normal | none |
| SYS1 | 29 | 2017-03-02 | nach der Rückkehr | 508,2 | 390,7 | 0,6 | 0,8 | 0,9 | -35,9 | 0,0 | 7,0 | normal | False | normal | none |
| SYS1 | 30 | 2017-03-03 | nach der Rückkehr | 403,3 | 412,5 | 0,6 | -0,1 | 0,8 | -33,0 | 0,0 | 7,0 | normal | False | normal | none |
| SYS1 | 31 | 2017-03-04 | nach der Rückkehr | 392,2 | 315,6 | -0,1 | 0,6 | 0,8 | -30,6 | 0,0 | 7,0 | normal | False | normal | none |
| SYS1 | 32 | 2017-03-05 | nach der Rückkehr | 347,5 | 421,0 | 0,1 | -0,6 | 0,7 | -28,2 | 0,0 | 7,0 | normal | False | normal | none |
| SYS1 | 33 | 2017-03-06 | nach der Rückkehr | 509,6 | 445,3 | 0,7 | 0,5 | 0,7 | -25,0 | 0,0 | 7,0 | normal | False | normal | none |
| SYS1 | 34 | 2017-03-07 | nach der Rückkehr | 571,8 | 388,7 | 0,9 | 1,5 | 0,8 | -22,0 | 0,0 | 7,0 | normal | False | normal | none |
| SYS1 | 35 | 2017-03-08 | nach der Rückkehr | 333,4 | 402,7 | -0,4 | -0,5 | 0,7 | -20,0 | 0,0 | 7,0 | normal | False | normal | none |
| SYS1 | 36 | 2017-03-09 | nach der Rückkehr | 364,9 | 390,7 | -0,2 | -0,2 | 0,6 | -17,9 | 0,0 | 7,0 | normal | False | normal | none |
| SYS1 | 37 | 2017-03-10 | nach der Rückkehr | 407,0 | 390,6 | 0,8 | 0,1 | 0,6 | -14,1 | 0,0 | 6,0 | normal | False | normal | none |
| SYS1 | 38 | 2017-03-11 | nach der Rückkehr | 426,8 | 315,6 | 0,6 | 0,9 | 0,6 | -8,1 | 0,0 | 5,0 | normal | False | normal | none |
| SYS1 | 39 | 2017-03-12 | nach der Rückkehr | 438,3 | 370,3 | -0,0 | 0,6 | 0,7 | -1,7 | 0,0 | 4,0 | normal | False | normal | none |
| SYS1 | 40 | 2017-03-13 | nach der Rückkehr | 394,7 | 491,4 | 0,1 | -0,8 | 0,6 | 5,5 | 0,0 | 3,0 | normal | False | normal | none |
| SYS1 | 41 | 2017-03-14 | nach der Rückkehr | 431,2 | 437,4 | 0,2 | -0,1 | 0,4 | 13,3 | 0,0 | 2,0 | normal | False | normal | none |
| SYS1 | 42 | 2017-03-15 | nach der Rückkehr | 438,2 | 365,7 | 0,6 | 0,6 | 0,5 | 20,2 | 0,0 | 1,0 | normal | False | normal | none |
| SYS1 | 43 | 2017-03-16 | nach der Rückkehr | 396,8 | 369,9 | 0,5 | 0,2 | 0,6 | 26,7 | 0,0 | 2,0 | normal | False | normal | none |
| SYS1 | 44 | 2017-03-17 | nach der Rückkehr | 245,2 | 390,6 | -1,2 | -1,3 | 0,4 | 31,2 | 0,0 | 3,0 | normal | False | normal | none |
| SYS1 | 45 | 2017-03-18 | nach der Rückkehr | 356,9 | 315,6 | 0,0 | 0,3 | 0,3 | 36,3 | 0,0 | 4,0 | normal | False | normal | none |
| SYS1 | 46 | 2017-03-19 | nach der Rückkehr | 412,5 | 370,3 | -0,3 | 0,3 | 0,3 | 45,2 | 0,0 | 5,0 | normal | False | normal | none |
| SYS1 | 47 | 2017-03-20 | nach der Rückkehr | 457,3 | 437,1 | 0,4 | 0,2 | 0,4 | 53,3 | 0,0 | 6,0 | normal | False | normal | none |
| SYS1 | 48 | 2017-03-21 | nach der Rückkehr | 513,6 | 431,9 | 0,8 | 0,7 | 0,5 | 62,1 | 0,0 | 7,0 | normal | False | normal | none |
| SYS1 | 49 | 2017-03-22 | nach der Rückkehr | 544,8 | 365,7 | 0,3 | 1,6 | 0,7 | 62,4 | 0,0 | 7,0 | normal | False | normal | none |
| SYS1 | 50 | 2017-03-23 | nach der Rückkehr | 482,3 | 380,8 | 0,5 | 0,9 | 0,8 | 65,7 | 0,0 | 7,0 | normal | False | normal | none |
| SYS1 | 51 | 2017-03-24 | nach der Rückkehr | 384,7 | 311,5 | 0,9 | 0,6 | 1,0 | 61,9 | 0,0 | 7,0 | normal | False | normal | none |
| SYS1 | 52 | 2017-03-25 | nach der Rückkehr | 181,9 | 304,5 | -1,5 | -1,0 | 0,8 | 56,4 | 0,0 | 7,0 | normal | False | normal | none |
| SYS1 | 53 | 2017-03-26 | nach der Rückkehr | 289,2 | 370,3 | 0,1 | -0,6 | 0,6 | 56,6 | 0,0 | 7,0 | normal | False | normal | none |
| SYS1 | 54 | 2017-03-27 | nach der Rückkehr | 524,6 | 426,0 | 1,1 | 0,7 | 0,7 | 57,3 | 0,0 | 7,0 | normal | False | normal | none |
| SYS1 | 55 | 2017-03-28 | nach der Rückkehr | 428,3 | 431,9 | -0,0 | -0,0 | 0,6 | 56,2 | 0,0 | 7,0 | normal | False | normal | none |
| SYS1 | 56 | 2017-03-29 | nach der Rückkehr | 556,7 | 373,1 | 0,4 | 1,4 | 0,7 | 55,4 | 0,0 | 7,0 | normal | False | normal | none |
| SYS1 | 57 | 2017-03-30 | nach der Rückkehr | 351,5 | 380,8 | -0,2 | -0,2 | 0,5 | 47,9 | 0,0 | 7,0 | normal | False | normal | none |
| SYS1 | 58 | 2017-03-31 | nach der Rückkehr | 305,3 | 315,0 | -0,5 | -0,1 | 0,4 | 43,1 | 0,0 | 7,0 | normal | False | normal | none |
| SYS1 | 59 | 2017-04-01 | nach der Rückkehr | 368,9 | 304,5 | -0,1 | 0,5 | 0,6 | 40,4 | 0,0 | 7,0 | normal | False | normal | none |
| SYS1 | 60 | 2017-04-02 | nach der Rückkehr | 482,2 | 318,3 | 0,5 | 1,2 | 0,9 | 40,1 | 0,0 | 7,0 | normal | False | normal | none |
| SYS1 | 61 | 2017-04-03 | nach der Rückkehr | 454,6 | 426,0 | 0,4 | 0,2 | 0,8 | 35,4 | 0,0 | 7,0 | normal | False | normal | none |
| SYS1 | 62 | 2017-04-04 | nach der Rückkehr | 441,4 | 429,8 | 0,9 | 0,1 | 0,8 | 29,4 | 0,0 | 7,0 | normal | False | normal | none |
| SYS1 | 63 | 2017-04-05 | nach der Rückkehr | 443,5 | 425,5 | 0,2 | 0,2 | 0,6 | 29,5 | 0,0 | 7,0 | normal | False | normal | none |
| SYS1 | 64 | 2017-04-06 | nach der Rückkehr | 505,4 | 380,8 | 0,2 | 1,2 | 0,8 | 29,8 | 0,0 | 7,0 | normal | False | normal | none |
| SYS1 | 65 | 2017-04-07 | nach der Rückkehr | 348,4 | 345,0 | -0,0 | 0,0 | 0,9 | 26,8 | 0,0 | 7,0 | normal | False | normal | none |
| SYS1 | 66 | 2017-04-08 | nach der Rückkehr | 376,7 | 362,9 | 0,6 | 0,1 | 0,9 | 22,2 | 0,0 | 7,0 | normal | False | normal | none |
| SYS1 | 67 | 2017-04-09 | nach der Rückkehr | 449,6 | 370,3 | 0,8 | 0,9 | 0,8 | 18,2 | 0,0 | 7,0 | normal | False | normal | none |
| SYS1 | 68 | 2017-04-10 | nach der Rückkehr | 269,3 | 456,0 | -1,5 | -2,2 | 0,5 | 13,9 | 0,0 | 6,0 | normal | False | normal | none |
| SYS1 | 69 | 2017-04-11 | nach der Rückkehr | 234,5 | 436,3 | 0,1 | -2,4 | 0,2 | 8,6 | 0,0 | 5,0 | unusual | False | low | none |
| SYS1 | 70 | 2017-04-12 | nach der Rückkehr | 171,2 | 440,8 | -2,2 | -3,2 | -0,2 | 3,0 | 0,0 | 4,0 | unusual | False | low | none |
| SYS1 | 71 | 2017-04-13 | nach der Rückkehr | 155,8 | 401,6 | -2,5 | -3,0 | -0,8 | -1,7 | 0,0 | 3,0 | unusual | False | low | none |
| SYS1 | 72 | 2017-04-14 | nach der Rückkehr | 309,9 | 366,6 | 0,1 | -0,7 | -0,9 | -1,5 | 0,0 | 2,0 | normal | False | normal | none |
| SYS1 | 73 | 2017-04-15 | nach der Rückkehr | 410,9 | 372,8 | 0,1 | 0,5 | -0,9 | -2,4 | 0,0 | 1,0 | normal | False | normal | none |
| SYS1 | 74 | 2017-04-16 | nach der Rückkehr | 378,3 | 402,8 | 0,5 | -0,3 | -1,1 | -4,3 | 1,0 | 0,0 | normal | False | normal | none |
| SYS1 | 75 | 2017-04-17 | nach der Rückkehr | 428,4 | 456,0 | 0,2 | -0,4 | -0,9 | -6,5 | 1,0 | 0,0 | normal | False | normal | none |
| SYS1 | 76 | 2017-04-18 | nach der Rückkehr | 367,0 | 436,3 | -1,5 | -0,9 | -0,8 | -10,1 | 1,0 | 0,0 | normal | False | normal | none |
| SYS1 | 77 | 2017-04-19 | nach der Rückkehr | 509,2 | 440,8 | 0,7 | 0,9 | -0,3 | -11,1 | 1,0 | 0,0 | normal | False | normal | none |
| SYS1 | 78 | 2017-04-20 | nach der Rückkehr | 411,8 | 401,6 | -1,4 | 0,1 | 0,2 | -12,3 | 1,0 | 0,0 | normal | False | normal | none |
| SYS1 | 79 | 2017-04-21 | nach der Rückkehr | 458,2 | 366,6 | 0,0 | 1,3 | 0,5 | -10,9 | 1,0 | 0,0 | normal | False | normal | none |
| SYS1 | 80 | 2017-04-22 | nach der Rückkehr | 536,1 | 377,9 | 1,1 | 2,3 | 0,8 | -6,4 | 1,0 | 0,0 | normal | False | normal | none |
| SYS2 | 0 | 2017-02-01 | Urlaub | 279,6 | 432,0 | -1,9 | -2,3 | 0,2 | 17,7 | 1,0 | 7,0 | unusual | False | low | none |
| SYS2 | 1 | 2017-02-02 | Urlaub | 232,2 | 422,4 | -2,6 | -3,0 | -0,4 | 14,7 | 0,0 | 7,0 | unusual | False | low | none |
| SYS2 | 2 | 2017-02-03 | Urlaub | 210,6 | 418,6 | -2,8 | -3,1 | -0,8 | 11,6 | 0,0 | 6,0 | unusual | False | low | none |
| SYS2 | 3 | 2017-02-04 | Urlaub | 252,2 | 443,0 | -2,1 | -2,4 | -0,9 | 9,9 | 0,0 | 5,0 | unusual | False | low | none |
| SYS2 | 4 | 2017-02-05 | Urlaub | 235,8 | 463,1 | -2,2 | -2,6 | -1,4 | 7,6 | 1,0 | 4,0 | unusual | False | low | none |
| SYS2 | 5 | 2017-02-06 | Urlaub | 258,8 | 429,3 | -2,0 | -1,8 | -2,1 | 5,7 | 2,0 | 3,0 | normal | False | normal | none |
| SYS2 | 6 | 2017-02-07 | Urlaub | 276,7 | 417,3 | -1,5 | -1,5 | -2,6 | 6,8 | 3,0 | 2,0 | normal | False | normal | none |
| SYS2 | 7 | 2017-02-08 | Urlaub | 256,2 | 416,5 | -2,0 | -2,1 | -2,7 | 5,1 | 4,0 | 1,0 | normal | False | normal | none |
| SYS2 | 8 | 2017-02-09 | Urlaub | 281,1 | 415,4 | -1,6 | -1,7 | -2,6 | 2,3 | 5,0 | 0,0 | normal | False | normal | none |
| SYS2 | 9 | 2017-02-10 | Urlaub | 237,3 | 418,6 | -1,2 | -1,9 | -2,5 | -0,9 | 6,0 | 0,0 | normal | False | normal | none |
| SYS2 | 10 | 2017-02-11 | Urlaub | 122,0 | 407,4 | -2,2 | -2,5 | -2,7 | -4,4 | 7,0 | 0,0 | unusual | False | low | none |
| SYS2 | 11 | 2017-02-12 | Urlaub | 115,4 | 457,3 | -2,2 | -3,0 | -2,9 | -9,4 | 7,0 | 0,0 | unusual | False | low | none |
| SYS2 | 12 | 2017-02-13 | Urlaub | 128,2 | 429,3 | -1,9 | -2,4 | -3,0 | -14,2 | 7,0 | 0,0 | unusual | False | low | none |
| SYS2 | 13 | 2017-02-14 | Urlaub | 121,2 | 383,5 | -1,9 | -2,1 | -3,2 | -18,6 | 7,0 | 1,0 | normal | False | normal | none |
| SYS2 | 14 | 2017-02-15 | Urlaub | 135,8 | 402,7 | -1,5 | -2,0 | -3,2 | -20,7 | 7,0 | 2,0 | normal | False | normal | none |
| SYS2 | 15 | 2017-02-16 | Urlaub | 130,3 | 415,4 | -1,5 | -2,1 | -3,4 | -21,9 | 7,0 | 3,0 | normal | False | normal | none |
| SYS2 | 16 | 2017-02-17 | Urlaub | 201,2 | 384,0 | -1,0 | -1,4 | -3,3 | -24,8 | 7,0 | 4,0 | normal | False | normal | none |
| SYS2 | 17 | 2017-02-18 | Urlaub | 210,0 | 399,8 | -0,9 | -1,4 | -3,0 | -26,7 | 7,0 | 5,0 | normal | False | normal | none |
| SYS2 | 18 | 2017-02-19 | Urlaub | 223,0 | 457,3 | -1,0 | -1,5 | -2,7 | -31,7 | 7,0 | 6,0 | normal | True | new_pattern | advance_history_start |
| SYS2 | 19 | 2017-02-20 | Urlaub | 219,1 | - | 0,7 | - | - | - | - | - | normal | False | normal | none |
| SYS2 | 20 | 2017-02-21 | Urlaub | 217,6 | - | 0,6 | - | - | - | - | - | normal | False | normal | none |
| SYS2 | 21 | 2017-02-22 | nach der Rückkehr | 446,6 | - | 6,4 | - | - | - | - | - | unusual | False | peak | none |
| SYS2 | 22 | 2017-02-23 | nach der Rückkehr | 406,5 | - | 3,4 | - | - | - | - | - | unusual | False | peak | none |
| SYS2 | 23 | 2017-02-24 | nach der Rückkehr | 487,5 | - | 7,2 | - | - | - | - | - | unusual | False | peak | none |
| SYS2 | 24 | 2017-02-25 | nach der Rückkehr | 379,1 | - | 2,4 | - | - | - | - | - | unusual | False | peak | none |
| SYS2 | 25 | 2017-02-26 | nach der Rückkehr | 393,1 | - | 2,2 | - | - | - | - | - | normal | False | normal | none |
| SYS2 | 26 | 2017-02-27 | nach der Rückkehr | 503,4 | - | 2,9 | - | 25,5 | - | - | - | unusual | False | peak | none |
| SYS2 | 27 | 2017-02-28 | nach der Rückkehr | 463,3 | - | 1,5 | - | 19,6 | - | - | - | normal | False | normal | none |
| SYS2 | 28 | 2017-03-01 | nach der Rückkehr | 412,8 | - | 1,5 | - | 7,9 | - | - | - | normal | False | normal | none |
| SYS2 | 29 | 2017-03-02 | nach der Rückkehr | 508,2 | - | 1,8 | - | 5,3 | - | - | - | normal | False | normal | none |
| SYS2 | 30 | 2017-03-03 | nach der Rückkehr | 403,3 | - | 1,1 | - | 3,5 | - | - | - | normal | False | normal | none |
| SYS2 | 31 | 2017-03-04 | nach der Rückkehr | 392,2 | - | 0,1 | - | 2,8 | - | 6,0 | - | normal | False | normal | none |
| SYS2 | 32 | 2017-03-05 | nach der Rückkehr | 347,5 | - | 0,2 | - | 2,3 | - | 7,0 | - | normal | False | normal | none |
| SYS2 | 33 | 2017-03-06 | nach der Rückkehr | 509,6 | - | 0,5 | - | 1,8 | - | 7,0 | - | normal | False | normal | none |
| SYS2 | 34 | 2017-03-07 | nach der Rückkehr | 571,8 | - | 0,8 | - | 1,6 | - | 7,0 | - | normal | False | normal | none |
| SYS2 | 35 | 2017-03-08 | nach der Rückkehr | 333,4 | - | -0,3 | - | 1,3 | - | 7,0 | - | normal | False | normal | none |
| SYS2 | 36 | 2017-03-09 | nach der Rückkehr | 364,9 | - | -0,2 | - | 1,0 | - | 6,0 | - | normal | False | normal | none |
| SYS2 | 37 | 2017-03-10 | nach der Rückkehr | 407,0 | - | 0,7 | - | 0,9 | - | 5,0 | - | normal | False | normal | none |
| SYS2 | 38 | 2017-03-11 | nach der Rückkehr | 426,8 | - | 0,5 | - | 0,8 | - | 4,0 | - | normal | False | normal | none |
| SYS2 | 39 | 2017-03-12 | nach der Rückkehr | 438,3 | - | -0,1 | - | 0,9 | - | 3,0 | - | normal | False | normal | none |
| SYS2 | 40 | 2017-03-13 | nach der Rückkehr | 394,7 | 361,2 | 0,1 | 0,2 | 0,7 | - | 2,0 | - | normal | False | normal | none |
| SYS2 | 41 | 2017-03-14 | nach der Rückkehr | 431,2 | 340,5 | 0,2 | 0,7 | 0,4 | - | 1,0 | - | normal | False | normal | none |
| SYS2 | 42 | 2017-03-15 | nach der Rückkehr | 438,2 | 373,1 | 0,6 | 0,6 | 0,6 | - | 0,0 | - | normal | False | normal | none |
| SYS2 | 43 | 2017-03-16 | nach der Rückkehr | 396,8 | 385,7 | 0,5 | 0,1 | 0,6 | - | 0,0 | - | normal | False | normal | none |
| SYS2 | 44 | 2017-03-17 | nach der Rückkehr | 245,2 | 405,2 | -1,5 | -2,0 | 0,3 | - | 0,0 | - | normal | False | normal | none |
| SYS2 | 45 | 2017-03-18 | nach der Rückkehr | 356,9 | 385,6 | -0,1 | -0,3 | 0,2 | - | 0,0 | - | normal | False | normal | none |
| SYS2 | 46 | 2017-03-19 | nach der Rückkehr | 412,5 | 370,3 | -0,4 | 0,5 | 0,1 | - | 0,0 | - | normal | False | normal | none |
| SYS2 | 47 | 2017-03-20 | nach der Rückkehr | 457,3 | 394,7 | 0,3 | 0,9 | 0,2 | - | 0,0 | - | normal | False | normal | none |
| SYS2 | 48 | 2017-03-21 | nach der Rückkehr | 513,6 | 431,2 | 0,9 | 1,2 | 0,3 | - | 0,0 | - | normal | False | normal | none |
| SYS2 | 49 | 2017-03-22 | nach der Rückkehr | 544,8 | 412,8 | 0,3 | 2,0 | 0,5 | - | 0,0 | - | normal | False | normal | none |
| SYS2 | 50 | 2017-03-23 | nach der Rückkehr | 482,3 | 396,8 | 0,5 | 1,2 | 0,6 | - | 0,0 | - | normal | False | normal | none |
| SYS2 | 51 | 2017-03-24 | nach der Rückkehr | 384,7 | 403,3 | 1,1 | -0,3 | 0,8 | - | 0,0 | - | normal | False | normal | none |
| SYS2 | 52 | 2017-03-25 | nach der Rückkehr | 181,9 | 379,1 | -2,3 | -2,8 | 0,6 | - | 0,0 | - | unusual | False | low | none |
| SYS2 | 53 | 2017-03-26 | nach der Rückkehr | 289,2 | 393,1 | -0,0 | -1,2 | 0,4 | 56,9 | 0,0 | - | normal | False | normal | none |
| SYS2 | 54 | 2017-03-27 | nach der Rückkehr | 524,6 | 426,0 | 1,5 | 1,0 | 0,5 | 48,3 | 0,0 | - | normal | False | normal | none |
| SYS2 | 55 | 2017-03-28 | nach der Rückkehr | 428,3 | 447,3 | -0,2 | -0,2 | 0,3 | 42,0 | 0,0 | - | normal | False | normal | none |
| SYS2 | 56 | 2017-03-29 | nach der Rückkehr | 556,7 | 425,5 | 0,4 | 1,5 | 0,3 | 40,4 | 0,0 | - | normal | False | normal | none |
| SYS2 | 57 | 2017-03-30 | nach der Rückkehr | 351,5 | 401,6 | -0,5 | -0,5 | 0,1 | 33,3 | 0,0 | - | normal | False | normal | none |
| SYS2 | 58 | 2017-03-31 | nach der Rückkehr | 305,3 | 394,0 | -0,9 | -1,0 | -0,1 | 30,1 | 0,0 | 6,0 | normal | False | normal | none |
| SYS2 | 59 | 2017-04-01 | nach der Rückkehr | 368,9 | 368,0 | -0,3 | 0,0 | 0,2 | 28,3 | 0,0 | 7,0 | normal | False | normal | none |
| SYS2 | 60 | 2017-04-02 | nach der Rückkehr | 482,2 | 370,3 | 0,5 | 1,3 | 0,6 | 29,3 | 0,0 | 7,0 | normal | False | normal | none |
| SYS2 | 61 | 2017-04-03 | nach der Rückkehr | 454,6 | 457,3 | 0,4 | -0,0 | 0,5 | 25,3 | 0,0 | 7,0 | normal | False | normal | none |
| SYS2 | 62 | 2017-04-04 | nach der Rückkehr | 441,4 | 431,2 | 1,2 | 0,1 | 0,5 | 20,0 | 0,0 | 7,0 | normal | False | normal | none |
| SYS2 | 63 | 2017-04-05 | nach der Rückkehr | 443,5 | 438,2 | 0,1 | 0,1 | 0,3 | 21,3 | 0,0 | 7,0 | normal | False | normal | none |
| SYS2 | 64 | 2017-04-06 | nach der Rückkehr | 505,4 | 396,8 | 0,2 | 1,4 | 0,6 | 22,4 | 0,0 | 7,0 | normal | False | normal | none |
| SYS2 | 65 | 2017-04-07 | nach der Rückkehr | 348,4 | 384,7 | -0,2 | -0,5 | 0,6 | 20,9 | 0,0 | 7,0 | normal | False | normal | none |
| SYS2 | 66 | 2017-04-08 | nach der Rückkehr | 376,7 | 368,9 | 0,6 | 0,1 | 0,7 | 19,3 | 0,0 | 7,0 | normal | False | normal | none |
| SYS2 | 67 | 2017-04-09 | nach der Rückkehr | 449,6 | 393,1 | 0,8 | 0,8 | 0,6 | 18,2 | 0,0 | 7,0 | normal | False | normal | none |
| SYS2 | 68 | 2017-04-10 | nach der Rückkehr | 269,3 | 456,0 | -1,8 | -2,4 | 0,2 | 13,9 | 0,0 | 6,0 | unusual | False | low | none |
| SYS2 | 69 | 2017-04-11 | nach der Rückkehr | 234,5 | 436,3 | 0,0 | -2,5 | -0,2 | 8,6 | 0,0 | 5,0 | unusual | False | low | none |
| SYS2 | 70 | 2017-04-12 | nach der Rückkehr | 171,2 | 440,8 | -2,3 | -3,3 | -0,8 | 3,0 | 0,0 | 4,0 | unusual | False | low | none |
| SYS2 | 71 | 2017-04-13 | nach der Rückkehr | 155,8 | 401,6 | -2,6 | -3,0 | -1,5 | -1,7 | 1,0 | 3,0 | unusual | False | low | none |
| SYS2 | 72 | 2017-04-14 | nach der Rückkehr | 309,9 | 366,6 | 0,1 | -0,7 | -1,6 | -1,5 | 2,0 | 2,0 | normal | False | normal | none |
| SYS2 | 73 | 2017-04-15 | nach der Rückkehr | 410,9 | 372,8 | 0,1 | 0,5 | -1,5 | -2,4 | 3,0 | 1,0 | normal | False | normal | none |
| SYS2 | 74 | 2017-04-16 | nach der Rückkehr | 378,3 | 402,8 | 0,5 | -0,3 | -1,7 | -4,3 | 4,0 | 0,0 | normal | False | normal | none |
| SYS2 | 75 | 2017-04-17 | nach der Rückkehr | 428,4 | 456,0 | 0,2 | -0,4 | -1,4 | -6,5 | 5,0 | 0,0 | normal | False | normal | none |
| SYS2 | 76 | 2017-04-18 | nach der Rückkehr | 367,0 | 436,3 | -1,5 | -0,9 | -1,1 | -10,1 | 6,0 | 0,0 | normal | False | normal | none |
| SYS2 | 77 | 2017-04-19 | nach der Rückkehr | 509,2 | 440,8 | 0,7 | 0,9 | -0,4 | -11,1 | 6,0 | 0,0 | normal | False | normal | none |
| SYS2 | 78 | 2017-04-20 | nach der Rückkehr | 411,8 | 401,6 | -1,4 | 0,1 | 0,2 | -12,3 | 5,0 | 0,0 | normal | False | normal | none |
| SYS2 | 79 | 2017-04-21 | nach der Rückkehr | 458,2 | 366,6 | 0,0 | 1,3 | 0,5 | -10,9 | 4,0 | 0,0 | normal | False | normal | none |
| SYS2 | 80 | 2017-04-22 | nach der Rückkehr | 536,1 | 377,9 | 1,1 | 2,3 | 0,8 | -6,4 | 3,0 | 0,0 | normal | False | normal | none |
