# E2 Abwesenheit, Lauf e2_005

## Setup

- Urlaub event-2014-08: 2014-08-03 bis vor 2014-08-17, Beginn = Tag 0, analysierte Tage 2014-07-03 bis 2014-09-15, Eintrag „Urlaub bei Oma“, Gegenfall „Oma kommt zu Besuch“
- Urlaub event-2015-10: 2015-10-04 bis vor 2015-10-25, Beginn = Tag 0, analysierte Tage 2015-09-03 bis 2015-11-23, Eintrag „Reise nach Tokio mit Moni“, ohne Gegenfall
- Kanäle: je Urlaub im Fenster aus Mains herausgerechnet, Coverage ab 90 %
- Systeme ctx0: SYS1, SYS2, SYS3_CTX0
- Systeme ctx1: SYS3_CTX1
- Systeme ctx1_visit: SYS3_CTX1_VISIT
- Systeme ctx2: SYS3_CTX2
- Commit: 106c124

## event-2014-08: Kennzahlen

| Kennzahl | Wert | Bezug |
|---|---|---|
| SYS1: erster Treffer absence [Urlaubstag] | - | 0 von 9 Urlaubstagen mit offenem Gate, 0 × absence ohne Beleg |
| SYS2: erster Treffer absence [Urlaubstag] | - | 0 von 9 Urlaubstagen mit offenem Gate, 0 × absence ohne Beleg |
| SYS3_CTX0: erster Treffer absence [Urlaubstag] | - | 0 von 2 Urlaubstagen mit offenem Gate, 0 × absence ohne Beleg |
| SYS3_CTX1: erster Treffer absence [Urlaubstag] | 5 | 1 von 1 Urlaubstagen mit offenem Gate, 0 × absence ohne Beleg |
| SYS3_CTX1_VISIT: erster Treffer absence [Urlaubstag] | - | 0 von 2 Urlaubstagen mit offenem Gate, 0 × absence ohne Beleg |
| SYS3_CTX2: erster Treffer absence [Urlaubstag] | - | 0 von 2 Urlaubstagen mit offenem Gate, 0 × absence ohne Beleg |
| Absenkung durch das Herausrechnen im Mittel [W] | 94,9 | je Tag im Urlaubsfenster |

## event-2014-08: Einordnung je Phase

| System | Phase | Tage | Gate offen | davon Einzeltag | davon Drift | davon nur eine Skala | new_pattern | low | peak | absence | Resets | Meldungen | Ausfalltage | MAE [W] |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| SYS1 | vor dem Urlaub | 31 | 11 | 0 | 0 | 10 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 123,9 |
| SYS1 | Urlaub | 14 | 9 | 0 | 0 | 9 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 45,5 |
| SYS1 | nach der Rückkehr | 30 | 21 | 0 | 2 | 19 | 2 | 0 | 0 | 0 | 0 | 2 | 0 | 144,4 |
| SYS2 | vor dem Urlaub | 31 | 11 | 0 | 0 | 10 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 123,9 |
| SYS2 | Urlaub | 14 | 9 | 0 | 0 | 9 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 45,5 |
| SYS2 | nach der Rückkehr | 30 | 15 | 3 | 1 | 11 | 1 | 0 | 3 | 0 | 1 | 4 | 0 | 143,8 |
| SYS3_CTX0 | vor dem Urlaub | 31 | 11 | 0 | 0 | 10 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 123,9 |
| SYS3_CTX0 | Urlaub | 14 | 2 | 1 | 0 | 1 | 1 | 0 | 1 | 0 | 1 | 2 | 0 | 46,5 |
| SYS3_CTX0 | nach der Rückkehr | 30 | 21 | 9 | 0 | 12 | 1 | 0 | 9 | 0 | 1 | 10 | 0 | 144,0 |
| SYS3_CTX1 | vor dem Urlaub | 31 | 11 | 0 | 0 | 10 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 123,9 |
| SYS3_CTX1 | Urlaub | 14 | 1 | 0 | 0 | 1 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 52,5 |
| SYS3_CTX1 | nach der Rückkehr | 30 | 2 | 0 | 0 | 2 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 141,9 |
| SYS3_CTX1_VISIT | vor dem Urlaub | 31 | 11 | 0 | 0 | 10 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 123,9 |
| SYS3_CTX1_VISIT | Urlaub | 14 | 2 | 1 | 0 | 1 | 1 | 0 | 1 | 0 | 1 | 2 | 0 | 46,5 |
| SYS3_CTX1_VISIT | nach der Rückkehr | 30 | 10 | 6 | 0 | 4 | 1 | 0 | 5 | 0 | 1 | 6 | 0 | 148,4 |
| SYS3_CTX2 | vor dem Urlaub | 31 | 11 | 0 | 0 | 10 | 0 | 0 | 0 | 0 | 0 | 1 | 0 | 123,9 |
| SYS3_CTX2 | Urlaub | 14 | 2 | 1 | 0 | 1 | 1 | 0 | 1 | 0 | 1 | 2 | 0 | 46,5 |
| SYS3_CTX2 | nach der Rückkehr | 30 | 10 | 4 | 0 | 6 | 1 | 0 | 4 | 0 | 1 | 5 | 0 | 148,0 |

## event-2014-08: Einordnung im Urlaub

| System | Urlaubstage | Treffer | erster Treffer [Urlaubstag] | absence ohne Beleg |
|---|---:|---|---:|---:|
| SYS1 | 14 | 0 von 9 | - | 0 |
| SYS2 | 14 | 0 von 9 | - | 0 |
| SYS3_CTX0 | 14 | 0 von 2 | - | 0 |
| SYS3_CTX1 | 14 | 1 von 1 | 5 | 0 |
| SYS3_CTX1_VISIT | 14 | 0 von 2 | - | 0 |
| SYS3_CTX2 | 14 | 0 von 2 | - | 0 |

## event-2014-08: Kalender im State

| System | Phase | eingeordnete Tage | davon Kalender im State |
|---|---|---:|---:|
| SYS1 | vor dem Urlaub | 11 | 0 |
| SYS1 | Urlaub | 9 | 0 |
| SYS1 | nach der Rückkehr | 21 | 0 |
| SYS2 | vor dem Urlaub | 11 | 0 |
| SYS2 | Urlaub | 9 | 0 |
| SYS2 | nach der Rückkehr | 15 | 0 |
| SYS3_CTX0 | vor dem Urlaub | 11 | 0 |
| SYS3_CTX0 | Urlaub | 2 | 0 |
| SYS3_CTX0 | nach der Rückkehr | 21 | 0 |
| SYS3_CTX1 | vor dem Urlaub | 11 | 11 |
| SYS3_CTX1 | Urlaub | 1 | 1 |
| SYS3_CTX1 | nach der Rückkehr | 2 | 2 |
| SYS3_CTX1_VISIT | vor dem Urlaub | 11 | 11 |
| SYS3_CTX1_VISIT | Urlaub | 2 | 2 |
| SYS3_CTX1_VISIT | nach der Rückkehr | 10 | 10 |
| SYS3_CTX2 | vor dem Urlaub | 11 | 0 |
| SYS3_CTX2 | Urlaub | 2 | 0 |
| SYS3_CTX2 | nach der Rückkehr | 10 | 0 |

## event-2014-08: Kalenderabruf per Tool, an Tagen mit Einordnung

| System | nützlich | überflüssig | verpasst | zu Recht nicht abgerufen |
|---|---:|---:|---:|---:|
| SYS3_CTX2 | 0 | 0 | 2 | 21 |

## event-2014-08: Prognose je Phase

| System | Phase | MAE [W] | Differenz zu SYS1 [W] | Standardfehler [W] | Anteil Tage besser | gepaarte Tage |
|---|---|---:|---:|---:|---:|---:|
| SYS1 | vor dem Urlaub | 123,9 | - | - | - | - |
| SYS1 | Urlaub | 45,5 | - | - | - | - |
| SYS1 | nach der Rückkehr | 144,4 | - | - | - | - |
| SYS2 | vor dem Urlaub | 123,9 | 0,0 | 0,0 | 0,0 | 30,0 |
| SYS2 | Urlaub | 45,5 | 0,0 | 0,0 | 0,0 | 14,0 |
| SYS2 | nach der Rückkehr | 143,8 | -0,5 | 6,6 | 0,5 | 30,0 |
| SYS3_CTX0 | vor dem Urlaub | 123,9 | 0,0 | 0,0 | 0,0 | 30,0 |
| SYS3_CTX0 | Urlaub | 46,5 | 1,0 | 3,2 | 0,2 | 14,0 |
| SYS3_CTX0 | nach der Rückkehr | 144,0 | -0,4 | 2,5 | 0,4 | 30,0 |
| SYS3_CTX1 | vor dem Urlaub | 123,9 | 0,0 | 0,0 | 0,0 | 30,0 |
| SYS3_CTX1 | Urlaub | 52,5 | 6,9 | 6,9 | 0,0 | 14,0 |
| SYS3_CTX1 | nach der Rückkehr | 141,9 | -2,5 | 1,8 | 0,4 | 30,0 |
| SYS3_CTX1_VISIT | vor dem Urlaub | 123,9 | 0,0 | 0,0 | 0,0 | 30,0 |
| SYS3_CTX1_VISIT | Urlaub | 46,5 | 1,0 | 3,2 | 0,2 | 14,0 |
| SYS3_CTX1_VISIT | nach der Rückkehr | 148,4 | 4,0 | 10,3 | 0,6 | 30,0 |
| SYS3_CTX2 | vor dem Urlaub | 123,9 | 0,0 | 0,0 | 0,0 | 30,0 |
| SYS3_CTX2 | Urlaub | 46,5 | 1,0 | 3,2 | 0,2 | 14,0 |
| SYS3_CTX2 | nach der Rückkehr | 148,0 | 3,6 | 8,2 | 0,6 | 30,0 |

## event-2015-10: Kennzahlen

| Kennzahl | Wert | Bezug |
|---|---|---|
| SYS1: erster Treffer absence [Urlaubstag] | - | 0 von 12 Urlaubstagen mit offenem Gate, 0 × absence ohne Beleg |
| SYS2: erster Treffer absence [Urlaubstag] | - | 0 von 7 Urlaubstagen mit offenem Gate, 0 × absence ohne Beleg |
| SYS3_CTX0: erster Treffer absence [Urlaubstag] | - | 0 von 5 Urlaubstagen mit offenem Gate, 0 × absence ohne Beleg |
| SYS3_CTX1: erster Treffer absence [Urlaubstag] | 9 | 1 von 1 Urlaubstagen mit offenem Gate, 0 × absence ohne Beleg |
| SYS3_CTX2: erster Treffer absence [Urlaubstag] | - | 0 von 4 Urlaubstagen mit offenem Gate, 0 × absence ohne Beleg |
| Absenkung durch das Herausrechnen im Mittel [W] | 154,2 | je Tag im Urlaubsfenster |

## event-2015-10: Einordnung je Phase

| System | Phase | Tage | Gate offen | davon Einzeltag | davon Drift | davon nur eine Skala | new_pattern | low | peak | absence | Resets | Meldungen | Ausfalltage | MAE [W] |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| SYS1 | vor dem Urlaub | 31 | 14 | 0 | 0 | 14 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 130,9 |
| SYS1 | Urlaub | 21 | 12 | 0 | 8 | 4 | 8 | 0 | 0 | 0 | 0 | 8 | 0 | 74,7 |
| SYS1 | nach der Rückkehr | 30 | 29 | 1 | 6 | 22 | 6 | 0 | 1 | 0 | 0 | 7 | 0 | 179,5 |
| SYS2 | vor dem Urlaub | 31 | 14 | 0 | 0 | 14 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 130,9 |
| SYS2 | Urlaub | 21 | 7 | 2 | 1 | 4 | 1 | 0 | 2 | 0 | 1 | 3 | 0 | 75,9 |
| SYS2 | nach der Rückkehr | 30 | 28 | 12 | 0 | 16 | 0 | 2 | 10 | 0 | 0 | 10 | 0 | 181,1 |
| SYS3_CTX0 | vor dem Urlaub | 31 | 14 | 0 | 0 | 14 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 130,9 |
| SYS3_CTX0 | Urlaub | 21 | 5 | 3 | 0 | 2 | 1 | 0 | 3 | 0 | 1 | 4 | 0 | 75,4 |
| SYS3_CTX0 | nach der Rückkehr | 30 | 5 | 3 | 0 | 2 | 2 | 0 | 2 | 0 | 2 | 4 | 0 | 182,2 |
| SYS3_CTX1 | vor dem Urlaub | 31 | 14 | 0 | 0 | 14 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 130,9 |
| SYS3_CTX1 | Urlaub | 21 | 1 | 0 | 0 | 1 | 0 | 0 | 0 | 1 | 0 | 0 | 0 | 74,2 |
| SYS3_CTX1 | nach der Rückkehr | 30 | 5 | 3 | 0 | 2 | 1 | 2 | 1 | 0 | 1 | 2 | 0 | 185,9 |
| SYS3_CTX2 | vor dem Urlaub | 31 | 14 | 0 | 0 | 14 | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 130,9 |
| SYS3_CTX2 | Urlaub | 21 | 4 | 3 | 0 | 1 | 1 | 0 | 3 | 0 | 1 | 4 | 0 | 73,4 |
| SYS3_CTX2 | nach der Rückkehr | 30 | 5 | 4 | 0 | 1 | 2 | 1 | 2 | 0 | 2 | 4 | 0 | 184,0 |

## event-2015-10: Einordnung im Urlaub

| System | Urlaubstage | Treffer | erster Treffer [Urlaubstag] | absence ohne Beleg |
|---|---:|---|---:|---:|
| SYS1 | 21 | 0 von 12 | - | 0 |
| SYS2 | 21 | 0 von 7 | - | 0 |
| SYS3_CTX0 | 21 | 0 von 5 | - | 0 |
| SYS3_CTX1 | 21 | 1 von 1 | 9 | 0 |
| SYS3_CTX2 | 21 | 0 von 4 | - | 0 |

## event-2015-10: Kalender im State

| System | Phase | eingeordnete Tage | davon Kalender im State |
|---|---|---:|---:|
| SYS1 | vor dem Urlaub | 14 | 0 |
| SYS1 | Urlaub | 12 | 0 |
| SYS1 | nach der Rückkehr | 29 | 0 |
| SYS2 | vor dem Urlaub | 14 | 0 |
| SYS2 | Urlaub | 7 | 0 |
| SYS2 | nach der Rückkehr | 28 | 0 |
| SYS3_CTX0 | vor dem Urlaub | 14 | 0 |
| SYS3_CTX0 | Urlaub | 5 | 0 |
| SYS3_CTX0 | nach der Rückkehr | 5 | 0 |
| SYS3_CTX1 | vor dem Urlaub | 14 | 14 |
| SYS3_CTX1 | Urlaub | 1 | 1 |
| SYS3_CTX1 | nach der Rückkehr | 5 | 5 |
| SYS3_CTX2 | vor dem Urlaub | 14 | 0 |
| SYS3_CTX2 | Urlaub | 4 | 0 |
| SYS3_CTX2 | nach der Rückkehr | 5 | 0 |

## event-2015-10: Kalenderabruf per Tool, an Tagen mit Einordnung

| System | nützlich | überflüssig | verpasst | zu Recht nicht abgerufen |
|---|---:|---:|---:|---:|
| SYS3_CTX2 | 0 | 0 | 4 | 19 |

## event-2015-10: Prognose je Phase

| System | Phase | MAE [W] | Differenz zu SYS1 [W] | Standardfehler [W] | Anteil Tage besser | gepaarte Tage |
|---|---|---:|---:|---:|---:|---:|
| SYS1 | vor dem Urlaub | 130,9 | - | - | - | - |
| SYS1 | Urlaub | 74,7 | - | - | - | - |
| SYS1 | nach der Rückkehr | 179,5 | - | - | - | - |
| SYS2 | vor dem Urlaub | 130,9 | 0,0 | 0,0 | 0,0 | 31,0 |
| SYS2 | Urlaub | 75,9 | 1,1 | 1,1 | 0,1 | 21,0 |
| SYS2 | nach der Rückkehr | 181,1 | 1,6 | 2,6 | 0,2 | 30,0 |
| SYS3_CTX0 | vor dem Urlaub | 130,9 | 0,0 | 0,0 | 0,0 | 31,0 |
| SYS3_CTX0 | Urlaub | 75,4 | 0,6 | 4,0 | 0,3 | 21,0 |
| SYS3_CTX0 | nach der Rückkehr | 182,2 | 2,7 | 5,1 | 0,4 | 30,0 |
| SYS3_CTX1 | vor dem Urlaub | 130,9 | 0,0 | 0,0 | 0,0 | 31,0 |
| SYS3_CTX1 | Urlaub | 74,2 | -0,5 | 0,5 | 0,0 | 21,0 |
| SYS3_CTX1 | nach der Rückkehr | 185,9 | 6,4 | 3,9 | 0,3 | 30,0 |
| SYS3_CTX2 | vor dem Urlaub | 130,9 | 0,0 | 0,0 | 0,0 | 31,0 |
| SYS3_CTX2 | Urlaub | 73,4 | -1,3 | 4,2 | 0,3 | 21,0 |
| SYS3_CTX2 | nach der Rückkehr | 184,0 | 4,5 | 4,7 | 0,5 | 30,0 |

## Hinweise

- Urlaubstag = analysierter Tag seit Beginn der Abwesenheit, 0 = erster Urlaubstag
- Treffer = absence mit passendem Kalendereintrag. absence ohne Beleg (ohne Kalender, Kalender nicht abgerufen oder nach der Rückkehr) zählt als Fehlklassifikation, über alle Phasen
- Treffer: von den Urlaubstagen mit offenem Gate, an den übrigen wird nicht eingeordnet. Wenige Tage, deshalb als Anzahl
- Einordnung je Phase: absence ist keine Meldung, im Urlaub ist jede Meldung ein Fehlalarm. Ausfalltage = LLM ohne gültige Antwort
- Gate offen: Einzeltag, Drift (weekly und long_term halten an) oder nur eine anhaltende Skala
- Differenz zu SYS1: gepaart am selben Tag, negativ = besser
- ctx0 ohne, ctx1 mit Kalender im State, ctx2 Kalender per Tool. SYS1 und SYS2 lesen keinen Kalender und laufen nur in ctx0
- Kalendereinträge als Freitext aus calendar_events.json, im Gegenfall ctx1_visit steht zu denselben Zeiten nur ein Eintrag, der keine Abwesenheit meint. Dort ist jedes absence falsch und zählt als absence ohne Beleg
- Kalender im State: bei ctx2 hat das LLM an diesen Tagen nachgeschaut, jeder ctx2-Tag mit LLM kostet einen zusätzlichen Aufruf für die Tool-Entscheidung
- Kalenderabruf: nützlich = abgerufen an einem Urlaubstag (ein Eintrag deckt den Tag), überflüssig = abgerufen ohne deckenden Eintrag, verpasst = nicht abgerufen an einem Urlaubstag. Vergleich: ctx1 schaut immer nach

![e2_timeline_event-2014-08.png](e2_timeline_event-2014-08.png)

![e2_timeline_event-2015-10.png](e2_timeline_event-2015-10.png)

## Anhang

### event-2014-08: Absenkung je Tag im Urlaubsfenster

| Datum | Mains [W] | ohne Kanäle [W] | Absenkung [W] |
|---|---:|---:|---:|
| 2014-08-03 | 160,9 | 139,0 | 21,9 |
| 2014-08-04 | 151,5 | 132,6 | 18,9 |
| 2014-08-05 | 156,3 | 135,7 | 20,7 |
| 2014-08-06 | 155,3 | 132,8 | 22,4 |
| 2014-08-07 | 169,7 | 147,7 | 22,1 |
| 2014-08-08 | 163,6 | 138,9 | 24,7 |
| 2014-08-09 | 362,2 | 180,8 | 181,4 |
| 2014-08-10 | 270,1 | 176,7 | 93,5 |
| 2014-08-11 | 306,0 | 159,9 | 146,1 |
| 2014-08-12 | 277,7 | 160,6 | 117,1 |
| 2014-08-13 | 303,7 | 187,5 | 116,2 |
| 2014-08-14 | 362,9 | 184,9 | 178,0 |
| 2014-08-15 | 386,2 | 217,5 | 168,7 |
| 2014-08-16 | 387,4 | 190,0 | 197,4 |

### event-2015-10: Absenkung je Tag im Urlaubsfenster

| Datum | Mains [W] | ohne Kanäle [W] | Absenkung [W] |
|---|---:|---:|---:|
| 2015-10-04 | 498,4 | 202,0 | 296,4 |
| 2015-10-05 | 374,1 | 215,1 | 159,0 |
| 2015-10-06 | 335,2 | 223,4 | 111,8 |
| 2015-10-07 | 416,2 | 243,9 | 172,4 |
| 2015-10-08 | 362,5 | 200,0 | 162,5 |
| 2015-10-09 | 331,9 | 188,9 | 143,0 |
| 2015-10-10 | 163,3 | 133,0 | 30,3 |
| 2015-10-11 | 170,8 | 135,2 | 35,6 |
| 2015-10-12 | 371,4 | 184,7 | 186,7 |
| 2015-10-13 | 272,3 | 185,1 | 87,2 |
| 2015-10-14 | 368,0 | 209,6 | 158,4 |
| 2015-10-15 | 510,5 | 299,6 | 210,9 |
| 2015-10-16 | 330,9 | 188,6 | 142,4 |
| 2015-10-17 | 364,2 | 177,7 | 186,5 |
| 2015-10-18 | 332,1 | 201,8 | 130,3 |
| 2015-10-19 | 363,0 | 198,7 | 164,3 |
| 2015-10-20 | 386,2 | 227,9 | 158,4 |
| 2015-10-21 | 466,8 | 255,3 | 211,5 |
| 2015-10-22 | 347,7 | 207,6 | 140,0 |
| 2015-10-23 | 492,6 | 214,5 | 278,1 |
| 2015-10-24 | 329,9 | 256,7 | 73,2 |
