# K2 Schwellen der Anomalieerkennung, Lauf k2_022

## Kurzfassung

- Gewählt: weekday / weekly / long_term % = 2 / 0,75 / 10 (aktuelle Config 12,5 / 2 / 0,75)
- Echte Trends mit Reset: 6 von 6 erkannt, im Mittel nach 20,0 Tagen. Ziel mindestens 80 %: erreicht. Aktuelle Config: 6 von 6
- Falsche Resets: 1,0 je Jahr (Grenze 1,5: erreicht), aktuelle Config 0,5
- Diagnose mit Eingriffen: Sprung und Rampe 28 Tage erkannt in 20 von 20 Fällen, langsame Rampen feuern in 7 von 10 (Ziel höchstens 20 %: nicht erreicht)

## Setup

- Zeitraum: bewertet 2013-06-01 bis 2015-04-29 (698 Tage), davor der Kaltstart. Kalibriert wird nur auf dem Train-Split
- Echte Trends: 6 im Zeitraum: Niveau ändert sich um mindestens 20 % gegen die 28 Tage davor, der Übergang ist nach 28 Tagen abgeschlossen und das neue Niveau hält mindestens 10 Tage
- Treffer: ein Reset von 10 Tagen vor bis 38 Tage nach dem Beginn eines echten Trends. Jeder andere Reset ist falsch
- Modus: mit Reset: schlanke Kette (Analyse, Streak, Einordnung nach Regel, Reset) über die ganze Reihe, ohne Prognose und ohne LLM
- Detektor: Referenz Rolling 60 vor dem Beobachtungsfenster, Median/MAD für daily und weekday
- Commit: c50d5ab (mit lokalen Änderungen)

## Ergebnis auf den echten Daten: gewählte Schwellen gegen aktuelle Config

| Einstellung | weekday / weekly / long_term % | echte Trends erkannt | Tage bis Erkennung (Mittel) | Resets gesamt | falsche Resets je Jahr | Grenze |
|---|---|---|---:|---:|---:|---:|
| gewählt | 2 / 0,75 / 10 | 6/6 | 20,0 | 8 | 1,0 | 1,5 |
| aktuelle Config | 12,5 / 2 / 0,75 | 6/6 | 22,5 | 7 | 0,5 | 1,5 |

## Echte Trends: wann meldet der Detektor (mit Reset)?

| Beginn | Änderung [%] | gewählt: Reset am | gewählt: Tage seit Beginn | aktuelle Config: Reset am | aktuelle Config: Tage seit Beginn |
|---|---:|---|---:|---|---:|
| 29.07.2013 | 27,2 | 31.07.2013 | 2 | 31.08.2013 | 33 |
| 31.10.2013 | 24,6 | 05.12.2013 | 35 | 06.12.2013 | 36 |
| 23.05.2014 | -48,6 | 05.06.2014 | 13 | 18.06.2014 | 26 |
| 18.06.2014 | 22,8 | 19.07.2014 | 31 | 18.06.2014 | 0 |
| 26.08.2014 | 27,3 | 16.09.2014 | 21 | 16.09.2014 | 21 |
| 25.11.2014 | 23,2 | 13.12.2014 | 18 | 14.12.2014 | 19 |

## Diagnose mit Eingriffen: ab welcher Änderung erkennt er? (Cutover-Fenster, mit Reset)

| Szenario | Sollverhalten | gewählt: erkannt bzw. feuert (n von N Fenstern) | gewählt: Tage (Mittel) | aktuelle Config: erkannt bzw. feuert (n von N Fenstern) | aktuelle Config: Tage (Mittel) |
|---|---|---|---:|---|---:|
| Sprung +30 % | erkennen | 5/5 | 13,6 | 5/5 | 16,4 |
| Sprung −30 % | erkennen | 5/5 | 24,0 | 5/5 | 23,6 |
| Rampe über 28 Tage +30 % | erkennen | 5/5 | 19,4 | 5/5 | 16,6 |
| Rampe über 28 Tage −30 % | erkennen | 5/5 | 32,2 | 5/5 | 28,6 |
| Rampe über 56 Tage +30 % | nicht feuern | 4/5 | 35,8 | 3/5 | 31,3 |
| Rampe über 56 Tage −30 % | nicht feuern | 3/5 | 45,0 | 2/5 | 50,0 |
| Einzeltag-Spitze +1000 W über 3 h | Alarm am Ereignistag | 1/5 | 1,0 | 1/5 | 1,0 |
| Einzeltag-Spitze +1000 W über 6 h | Alarm am Ereignistag | 3/5 | 1,0 | 3/5 | 1,0 |

## Raster der Schwellen nach Rang (die besten 10 und die aktuelle Config)

| weekday | weekly | long_term [%] | echte Trends erkannt | Tage bis Erkennung (Mittel) | falsche Resets je Jahr | gewählt | aktuelle Config |
|---|---|---|---|---:|---:|---|---|
| 2 | 0,75 | 10 | 6/6 | 20,0 | 1,0 | ja |  |
| 2,5 | 0,75 | 10 | 6/6 | 20,0 | 1,0 |  |  |
| 2,75 | 0,75 | 10 | 6/6 | 20,0 | 1,0 |  |  |
| 2 | 0,75 | 12,5 | 6/6 | 22,5 | 0,5 |  | aktuelle Config |
| 2,5 | 0,75 | 12,5 | 6/6 | 22,5 | 0,5 |  |  |
| 2,75 | 0,75 | 12,5 | 6/6 | 22,5 | 0,5 |  |  |
| 2 | 1 | 12,5 | 6/6 | 23,3 | 0,5 |  |  |
| 2,5 | 1 | 12,5 | 6/6 | 23,3 | 0,5 |  |  |
| 2,75 | 1 | 12,5 | 6/6 | 23,3 | 0,5 |  |  |
| 2 | 1 | 10 | 5/6 | 19,4 | 1,0 |  |  |

## Hinweise

- Gewählt wird unter der Grenze für falsche Resets je Jahr (1,5) der Punkt mit den meisten erkannten echten Trends, dann dem kürzesten mittleren Verzug. Das Raster steht vollständig in result_streak_sensitivity.csv
- Ein Reset im Trefferfenster eines Trends zählt als Treffer, auch wenn ein Reset zwei nahe Ereignisse trifft. Nach einem Reset fehlen weekday und long_term etwa 30 Tage, das ist im Lauf enthalten
- Diagnose: positive Art = erster Reset in Tag 1 bis 38 nach dem Cutover. Langsame Rampe = erster Reset außerhalb der Trefferfenster echter Trends (soll nie vorkommen). Spitze = Alarm am Ereignistag. Beginne des natürlichen Hintergrunds zählen mit
- Grenzen: wenige echte Trends in einem Haushalt, ein Treffer mehr oder weniger sind mehrere Prozentpunkte. Der Unterschied zwischen benachbarten Rasterpunkten ist nicht belastbar. Mindeständerung, Übergangs- und Haltedauer, Trefferfenster und die Grenze für falsche Resets sind Setzungen
- Die gewählten Schwellen sind in NumericalAnalysisConfig zu übernehmen, gerundet
