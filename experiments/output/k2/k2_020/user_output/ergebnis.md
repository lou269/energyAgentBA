# K2 Schwellen der Anomalieerkennung, Lauf k2_020

## Kurzfassung

- Gewählt: weekday / weekly / long_term % = 1,75 / 0,75 / 20 (aktuelle Config 2,5 / 0,75 / 20)
- Echte Trends mit Reset: 3 von 6 erkannt, im Mittel nach 10,0 Tagen. Ziel mindestens 80 %: nicht erreicht. Aktuelle Config: 2 von 6
- Falsche Resets: 1,0 je Jahr (Grenze 1,5: erreicht), aktuelle Config 1,0
- Diagnose mit Eingriffen: Sprung und Rampe 28 Tage erkannt in 9 von 20 Fällen, langsame Rampen feuern in 2 von 10 (Ziel höchstens 20 %: erreicht)

## Setup

- Zeitraum: bewertet 2013-06-01 bis 2015-04-29 (698 Tage), davor der Kaltstart. Kalibriert wird nur auf dem Train-Split
- Echte Trends: 6 im Zeitraum: Niveau ändert sich um mindestens 20 % gegen die 28 Tage davor, der Übergang ist nach 28 Tagen abgeschlossen und das neue Niveau hält mindestens 10 Tage
- Treffer: ein Reset von 10 Tagen vor bis 28 Tage nach dem Beginn eines echten Trends. Jeder andere Reset ist falsch
- Modus: mit Reset: schlanke Kette (Analyse, Streak, Einordnung nach Regel, Reset) über die ganze Reihe, ohne Prognose und ohne LLM
- Detektor: Referenz Rolling 60 vor dem Beobachtungsfenster, Median/MAD für daily und weekday
- Commit: 1590933 (mit lokalen Änderungen)

## Ergebnis auf den echten Daten: gewählte Schwellen gegen aktuelle Config

| Einstellung | weekday / weekly / long_term % | echte Trends erkannt | Tage bis Erkennung (Mittel) | Resets gesamt | falsche Resets je Jahr | Grenze |
|---|---|---|---:|---:|---:|---:|
| gewählt | 1,75 / 0,75 / 20 | 3/6 | 10,0 | 5 | 1,0 | 1,5 |
| aktuelle Config | 2,5 / 0,75 / 20 | 2/6 | 13,0 | 3 | 1,0 | 1,5 |

## Echte Trends: wann meldet der Detektor (mit Reset)?

| Beginn | Änderung [%] | gewählt: Reset am | gewählt: Tage seit Beginn | aktuelle Config: Reset am | aktuelle Config: Tage seit Beginn |
|---|---:|---|---:|---|---:|
| 29.07.2013 | 27,2 | nicht erkannt | - | nicht erkannt | - |
| 31.10.2013 | 24,6 | nicht erkannt | - | nicht erkannt | - |
| 23.05.2014 | -48,6 | 30.05.2014 | 7,0 | 18.06.2014 | 26,0 |
| 18.06.2014 | 22,8 | 30.06.2014 | 12,0 | 18.06.2014 | 0,0 |
| 26.08.2014 | 27,3 | 06.09.2014 | 11,0 | nicht erkannt | - |
| 25.11.2014 | 23,2 | nicht erkannt | - | nicht erkannt | - |

## Diagnose mit Eingriffen: ab welcher Änderung erkennt er? (Cutover-Fenster, mit Reset)

| Szenario | Sollverhalten | gewählt: erkannt bzw. feuert (n von N Fenstern) | gewählt: Tage (Mittel) | aktuelle Config: erkannt bzw. feuert (n von N Fenstern) | aktuelle Config: Tage (Mittel) |
|---|---|---|---:|---|---:|
| Sprung +30 % | erkennen | 5/5 | 13,4 | 4/5 | 14,8 |
| Sprung −30 % | erkennen | 0/5 | - | 1/5 | 7,0 |
| Rampe über 28 Tage +30 % | erkennen | 4/5 | 21,0 | 4/5 | 18,0 |
| Rampe über 28 Tage −30 % | erkennen | 0/5 | - | 1/5 | 7,0 |
| Rampe über 56 Tage +30 % | nicht feuern | 1/5 | 22,0 | 3/5 | 36,3 |
| Rampe über 56 Tage −30 % | nicht feuern | 1/5 | 60,0 | 1/5 | 60,0 |
| Einzeltag-Spitze +1000 W über 3 h | Alarm am Ereignistag | 2/5 | 1,0 | 2/5 | 1,0 |
| Einzeltag-Spitze +1000 W über 6 h | Alarm am Ereignistag | 3/5 | 1,0 | 3/5 | 1,0 |

## Raster der Schwellen nach Rang (die besten 10 und die aktuelle Config)

| weekday | weekly | long_term [%] | echte Trends erkannt | Tage bis Erkennung (Mittel) | falsche Resets je Jahr | gewählt | aktuelle Config |
|---|---|---|---|---:|---:|---|---|
| 1,75 | 0,75 | 20 | 3/6 | 10,0 | 1,0 | ja |  |
| 1,75 | 0,75 | 25 | 3/6 | 10,0 | 1,0 |  |  |
| 2 | 1 | 15 | 3/6 | 16,3 | 1,0 |  |  |
| 2,5 | 1 | 15 | 3/6 | 16,3 | 1,0 |  |  |
| 2,75 | 1 | 15 | 3/6 | 16,3 | 1,0 |  |  |
| 2 | 1,25 | 15 | 3/6 | 17,3 | 1,0 |  |  |
| 2,5 | 1,25 | 15 | 3/6 | 17,3 | 1,0 |  |  |
| 2,75 | 1,25 | 15 | 3/6 | 17,3 | 1,0 |  |  |
| 1,75 | 1 | 20 | 2/6 | 10,0 | 1,0 |  |  |
| 1,75 | 1 | 25 | 2/6 | 10,0 | 1,0 |  |  |
| 2,5 | 0,75 | 20 | 2/6 | 13,0 | 1,0 |  | Config |

## Hinweise

- Gewählt wird unter der Grenze für falsche Resets je Jahr (1,5) der Punkt mit den meisten erkannten echten Trends, dann dem kürzesten mittleren Verzug. Das Raster steht vollständig in result_streak_sensitivity.csv
- Ein Reset im Trefferfenster eines Trends zählt als Treffer, auch wenn ein Reset zwei nahe Ereignisse trifft. Nach einem Reset fehlen weekday und long_term etwa 30 Tage, das ist im Lauf enthalten
- Diagnose: positive Art = erster Reset in Tag 1 bis 28 nach dem Cutover. Langsame Rampe = erster Reset außerhalb der Trefferfenster echter Trends (soll nie vorkommen). Spitze = Alarm am Ereignistag. Beginne des natürlichen Hintergrunds zählen mit
- Grenzen: wenige echte Trends in einem Haushalt, ein Treffer mehr oder weniger sind mehrere Prozentpunkte. Der Unterschied zwischen benachbarten Rasterpunkten ist nicht belastbar. Mindeständerung, Übergangs- und Haltedauer, Trefferfenster und die Grenze für falsche Resets sind Setzungen
- Die gewählten Schwellen sind in NumericalAnalysisConfig zu übernehmen, gerundet
