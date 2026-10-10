# E4 Kaltstart, Lauf e4_002

## Setup

- Starttermine: Standard-Cutover CO2 (2015-02-12), CO3 (2015-05-24), CO5 (2016-01-12) (validation)
- Kaltstart: 7, 60 Tage, jeweils alle Tage am ersten Entscheidungstag, der erste eingeordnete Tag zählt mit
- Auswertung: 56 Tage ab Start in Wochen zu 7 Tagen, je Starttermin dieselben Kalendertage für alle Kaltstart-Längen
- Prognose (E4a): C3_60 täglich nachtrainiert, C1 nur auf den Starttagen, Baseline B2, Seed 42
- Kreislauf (E4b): SYS3 LLM, ministral-3:8b, Prompt v30, Temperatur 0, Adaption an
- Injektionen: Spitze +670 W über 6 h, ganzer Tag +190 W, je Lauf eine, an Tag 3, 10, 18, 26, 35, 43, 51, eingeordnet am Tag danach
- Commit: f3418db

## Antwort auf TF4: funktioniert mit 7 Tagen: ja (Prognose, keine Fehlfunktion, Erkennung)

| Bedingung | Prüfung | erfüllt | Wert |
|---|---|---|---:|
| Prognose | Wochen, in denen der Tagesfehler belastbar über dem des langen Kaltstarts liegt | ja | 0,0 |
| Prognose | Tagesfehler gegenüber der Baseline in Woche 1 [W], höchstens 0 | ja | -5,6 |
| keine Fehlfunktion | Resets nur beim kurzen Kaltstart, solange nicht alle Skalen einen Score haben | ja | 0,0 |
| Erkennung | Injektionen ab dem Tag mit weekday, die nur der lange Kaltstart erkennt | ja | 0,0 |

## Kennzahlen insgesamt: 7 gegenüber 60 Tagen Kaltstart, alle Termine

| Kennzahl | C3_60, Kaltstart 7 Tage | C3_60, Kaltstart 60 Tage (Referenz) |
|---|---|---|
| Prognosefehler gesamt [W] | 76,8 | 75,8 |
| Prognosefehler gegenüber C1 [W], negativ = besser | -117,5 | -11,5 |
| Prognosefehler gegenüber B2 [W], negativ = besser | -7,9 | -8,9 |
| Falschmeldungen: Tage, an denen nur der kurze Kaltstart meldet | 6 von 168 | - |
| Verpasste Meldungen: Tage, an denen nur der lange Kaltstart meldet | 1 von 168 | - |
| Anomalie erkannt: eingebaute Injektionen mit der erwarteten Klasse | 17 von 42 | 24 von 42 |
| Falsche new_pattern: Läufe mit Reset nur beim kurzen Kaltstart | 0 von 45 | - |

## Einpegeln: 7 gegenüber 60 Tagen Kaltstart je Woche nach Start

| Woche | Prognose C3_60: 7 minus 60 Tage [W] | belastbar | Falschmeldungen (nur bei 7 Tagen gemeldet) | Verpasste Meldungen (nur bei 60 Tagen gemeldet) | Anomalie erkannt, 7 Tage | Anomalie erkannt, 60 Tage | falsche new_pattern (nur bei 7 Tagen) |
|---|---|---|---:|---:|---|---|---:|
| 1 | -6,6 | nein | 1 | 0 | 1 von 6 | 2 von 6 | 0 |
| 2 | -1,8 | nein | 0 | 0 | 1 von 6 | 6 von 6 | 0 |
| 3 | 11,5 | nein | 0 | 0 | 1 von 6 | 3 von 6 | 0 |
| 4 | -0,7 | nein | 1 | 0 | 4 von 6 | 4 von 6 | 0 |
| 5 | 2,5 | nein | 2 | 0 | - | - | 0 |
| 6 | 1,2 | nein | 0 | 0 | 2 von 6 | 2 von 6 | 0 |
| 7 | 1,8 | nein | 2 | 0 | 6 von 6 | 5 von 6 | 0 |
| 8 | 0,3 | nein | 0 | 1 | 2 von 6 | 2 von 6 | 0 |
| gesamt | 1,0 | nein | 6 | 1 | 17 von 42 | 24 von 42 | 0 |

## Einschwingwoche: erste Woche, ab der es keine Abweichung mehr gibt

| Größe | eingeschwungen ab Woche |
|---|---|
| Prognose | 1 |
| Meldungen | nicht eingeschwungen |
| Erkennung | 4 |

## Hinweise

- Tag 0 = erster prognostizierter Tag, eingeordnet wird an ihm der letzte Tag der Start-Historie. Ein Injektionstag k wird am Tag k + 1 eingeordnet
- Als Meldung zählen die Klassen peak, new_pattern, measurement_error, low und unknown nicht. Falsch und verpasst sind Abweichungen vom langen Kaltstart am selben Tag im sauberen Lauf. Es sind echte Daten, eine Meldung nur beim kurzen Kaltstart kann also auch berechtigt sein
- Anomalie erkannt: am Tag nach dem Injektionstag ist die Klasse die erwartete, Wahrheit ist die eingebaute Injektion. Der lange Kaltstart erkennt selbst nur einen Teil
- Falsche new_pattern: Läufe, sauber und mit Injektion, in denen der kurze Kaltstart zurücksetzt und der lange am selben Tag nicht
- Einschwingwoche: Prognose nach der 2-Standardfehler-Regel, Meldungen und Resets nach jeder Abweichung, Erkennung nach jeder Injektion, die nur der lange Kaltstart erkennt. Erkennung ist nur bis zur letzten Injektionswoche belegt
- MAPE C3_60 mit 7 Tagen: 56,6 % (Proposal-Kriterium 10 %, hier kein Maßstab)
- Kontrolle Prognose im Kreislauf gegen Walk-Forward bis zum ersten Reset, soll 0 sein: größte Abweichung 7 Tage 0,0 W, 60 Tage 0,0 W
- belastbar: Betrag der Differenz größer als 2 Standardfehler der gepaarten Differenzen, grobe Faustregel
- Einschränkungen: ein Haushalt, wenige Termine, aufeinanderfolgende Tage sind nicht unabhängig (Standardfehler eher zu klein), LLM mit Temperatur 0 als deterministisch angenommen (Ollama auf GPU nicht garantiert bitgenau)

![e4_forecast.png](e4_forecast.png)

## Anhang

### Prognose je Woche nach Start: Tagesfehler C3_60 minus Vergleichsmodell [W], negativ = C3_60 besser

| Woche | 7 Tage: C3_60 minus C1 | 60 Tage: C3_60 minus C1 | 7 Tage: C3_60 minus B2 | 60 Tage: C3_60 minus B2 | C3_60: 7 Tage minus 60 Tage |
|---:|---:|---:|---:|---:|---:|
| 1 | -12,1 | -18,6 | -5,6 | 1,0 | -6,6 |
| 2 | -50,8 | 5,9 | -4,2 | -2,4 | -1,8 |
| 3 | -68,8 | -2,1 | -21,1 | -32,6 | 11,5 |
| 4 | -135,9 | -9,5 | -22,8 | -22,1 | -0,7 |
| 5 | -159,1 | -4,9 | -15,7 | -18,3 | 2,5 |
| 6 | -110,2 | -5,1 | -13,6 | -14,9 | 1,2 |
| 7 | -184,4 | -13,0 | -14,3 | -16,1 | 1,8 |
| 8 | -219,0 | -44,9 | 34,5 | 34,1 | 0,3 |

### Eingebaute Tage: ✓ = Klasse am Tag nach dem Injektionstag ist die erwartete, – = nicht

| Szenario | Injektionstag | 2015-02-12, 7 Tage | 2015-02-12, 60 Tage | 2015-05-24, 7 Tage | 2015-05-24, 60 Tage | 2016-01-12, 7 Tage | 2016-01-12, 60 Tage |
|---|---:|---|---|---|---|---|---|
| ganzer Tag +190 W | 3 | – | ✓ | – | – | – | – |
| ganzer Tag +190 W | 10 | – | ✓ | – | ✓ | – | ✓ |
| ganzer Tag +190 W | 18 | – | ✓ | – | ✓ | – | – |
| ganzer Tag +190 W | 26 | ✓ | ✓ | ✓ | ✓ | – | – |
| ganzer Tag +190 W | 35 | – | – | ✓ | ✓ | – | – |
| ganzer Tag +190 W | 43 | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| ganzer Tag +190 W | 51 | – | – | ✓ | ✓ | – | – |
| Spitze +670 W über 6 h | 3 | ✓ | ✓ | – | – | – | – |
| Spitze +670 W über 6 h | 10 | ✓ | ✓ | – | ✓ | – | ✓ |
| Spitze +670 W über 6 h | 18 | ✓ | ✓ | – | – | – | – |
| Spitze +670 W über 6 h | 26 | ✓ | ✓ | ✓ | ✓ | – | – |
| Spitze +670 W über 6 h | 35 | – | – | ✓ | ✓ | – | – |
| Spitze +670 W über 6 h | 43 | ✓ | – | ✓ | ✓ | ✓ | ✓ |
| Spitze +670 W über 6 h | 51 | – | – | ✓ | ✓ | – | – |
