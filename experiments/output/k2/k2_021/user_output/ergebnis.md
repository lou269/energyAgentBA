# K2 Schwellen der Anomalieerkennung, Lauf k2_021

## Kurzfassung

- Gewählt: weekday / weekly / long_term % = 2 / 0,75 / 12,5 (aktuelle Config 2,5 / 0,75 / 20)
- Echte Trends mit Reset: 6 von 6 erkannt, im Mittel nach 22,5 Tagen. Ziel mindestens 80 %: erreicht. Aktuelle Config: 3 von 6
- Falsche Resets: 0,5 je Jahr (Grenze 1,5: erreicht), aktuelle Config 0,0
- Diagnose mit Eingriffen: Sprung und Rampe 28 Tage erkannt in 20 von 20 Fällen, langsame Rampen feuern in 5 von 10 (Ziel höchstens 20 %: nicht erreicht)

## Setup

- Zeitraum: bewertet 2013-06-01 bis 2015-04-29 (698 Tage), davor der Kaltstart. Kalibriert wird nur auf dem Train-Split
- Echte Trends: 6 im Zeitraum: Niveau ändert sich um mindestens 20 % gegen die 28 Tage davor, der Übergang ist nach 28 Tagen abgeschlossen und das neue Niveau hält mindestens 10 Tage
- Treffer: ein Reset von 10 Tagen vor bis 38 Tage nach dem Beginn eines echten Trends. Jeder andere Reset ist falsch
- Modus: mit Reset: schlanke Kette (Analyse, Streak, Einordnung nach Regel, Reset) über die ganze Reihe, ohne Prognose und ohne LLM
- Detektor: Referenz Rolling 60 vor dem Beobachtungsfenster, Median/MAD für daily und weekday
- Commit: 1590933 (mit lokalen Änderungen)

## Ergebnis auf den echten Daten: gewählte Schwellen gegen aktuelle Config

| Einstellung | weekday / weekly / long_term % | echte Trends erkannt | Tage bis Erkennung (Mittel) | Resets gesamt | falsche Resets je Jahr | Grenze |
|---|---|---|---:|---:|---:|---:|
| gewählt | 2 / 0,75 / 12,5 | 6/6 | 22,5 | 7 | 0,5 | 1,5 |
| aktuelle Config | 2,5 / 0,75 / 20 | 3/6 | 18,3 | 3 | 0,0 | 1,5 |

## Echte Trends: wann meldet der Detektor (mit Reset)?

| Beginn | Änderung [%] | gewählt: Reset am | gewählt: Tage seit Beginn | aktuelle Config: Reset am | aktuelle Config: Tage seit Beginn |
|---|---:|---|---:|---|---:|
| 29.07.2013 | 27,2 | 31.08.2013 | 33 | nicht erkannt | - |
| 31.10.2013 | 24,6 | 06.12.2013 | 36 | nicht erkannt | - |
| 23.05.2014 | -48,6 | 18.06.2014 | 26 | 18.06.2014 | 26,0 |
| 18.06.2014 | 22,8 | 18.06.2014 | 0 | 18.06.2014 | 0,0 |
| 26.08.2014 | 27,3 | 16.09.2014 | 21 | nicht erkannt | - |
| 25.11.2014 | 23,2 | 14.12.2014 | 19 | 24.12.2014 | 29,0 |

## Diagnose mit Eingriffen: ab welcher Änderung erkennt er? (Cutover-Fenster, mit Reset)

| Szenario | Sollverhalten | gewählt: erkannt bzw. feuert (n von N Fenstern) | gewählt: Tage (Mittel) | aktuelle Config: erkannt bzw. feuert (n von N Fenstern) | aktuelle Config: Tage (Mittel) |
|---|---|---|---:|---|---:|
| Sprung +30 % | erkennen | 5/5 | 16,4 | 5/5 | 18,6 |
| Sprung −30 % | erkennen | 5/5 | 23,6 | 4/5 | 25,0 |
| Rampe über 28 Tage +30 % | erkennen | 5/5 | 16,6 | 4/5 | 18,0 |
| Rampe über 28 Tage −30 % | erkennen | 5/5 | 28,6 | 2/5 | 22,5 |
| Rampe über 56 Tage +30 % | nicht feuern | 3/5 | 31,3 | 1/5 | 22,0 |
| Rampe über 56 Tage −30 % | nicht feuern | 2/5 | 50,0 | 1/5 | 60,0 |
| Einzeltag-Spitze +1000 W über 3 h | Alarm am Ereignistag | 1/5 | 1,0 | 2/5 | 1,0 |
| Einzeltag-Spitze +1000 W über 6 h | Alarm am Ereignistag | 3/5 | 1,0 | 3/5 | 1,0 |

## Raster der Schwellen nach Rang (die besten 10 und die aktuelle Config)

| weekday | weekly | long_term [%] | echte Trends erkannt | Tage bis Erkennung (Mittel) | falsche Resets je Jahr | gewählt | aktuelle Config |
|---|---|---|---|---:|---:|---|---|
| 2 | 0,75 | 12,5 | 6/6 | 22,5 | 0,5 | ja |  |
| 2,5 | 0,75 | 12,5 | 6/6 | 22,5 | 0,5 |  |  |
| 2,75 | 0,75 | 12,5 | 6/6 | 22,5 | 0,5 |  |  |
| 2 | 1 | 12,5 | 6/6 | 23,3 | 0,5 |  |  |
| 2,5 | 1 | 12,5 | 6/6 | 23,3 | 0,5 |  |  |
| 2,75 | 1 | 12,5 | 6/6 | 23,3 | 0,5 |  |  |
| 2 | 0,75 | 15 | 5/6 | 22,8 | 1,0 |  |  |
| 2,5 | 0,75 | 15 | 5/6 | 22,8 | 1,0 |  |  |
| 2,75 | 0,75 | 15 | 5/6 | 22,8 | 1,0 |  |  |
| 2 | 1,25 | 12,5 | 5/6 | 23,8 | 1,0 |  |  |
| 2,5 | 0,75 | 20 | 3/6 | 18,3 | 0,0 |  | Config |

## Hinweise

- Gewählt wird unter der Grenze für falsche Resets je Jahr (1,5) der Punkt mit den meisten erkannten echten Trends, dann dem kürzesten mittleren Verzug. Das Raster steht vollständig in result_streak_sensitivity.csv
- Ein Reset im Trefferfenster eines Trends zählt als Treffer, auch wenn ein Reset zwei nahe Ereignisse trifft. Nach einem Reset fehlen weekday und long_term etwa 30 Tage, das ist im Lauf enthalten
- Diagnose: positive Art = erster Reset in Tag 1 bis 38 nach dem Cutover. Langsame Rampe = erster Reset außerhalb der Trefferfenster echter Trends (soll nie vorkommen). Spitze = Alarm am Ereignistag. Beginne des natürlichen Hintergrunds zählen mit
- Grenzen: wenige echte Trends in einem Haushalt, ein Treffer mehr oder weniger sind mehrere Prozentpunkte. Der Unterschied zwischen benachbarten Rasterpunkten ist nicht belastbar. Mindeständerung, Übergangs- und Haltedauer, Trefferfenster und die Grenze für falsche Resets sind Setzungen
- Die gewählten Schwellen sind in NumericalAnalysisConfig zu übernehmen, gerundet
