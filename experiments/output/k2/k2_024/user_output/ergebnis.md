# K2 Schwellen der Anomalieerkennung, Lauf k2_024

## Kurzfassung

- Gewählt: weekday / weekly / long_term % = 2,5 / 0,75 / 12,5 (aktuelle Config 12,5 / 2 / 0,75)
- Echte Trends mit Reset: 5 von 6 erkannt, im Mittel nach 11,2 Tagen. Ziel mindestens 80 %: erreicht. Aktuelle Config: 4 von 6
- Falsche Resets: 1,0 je Jahr (Grenze 1,5: erreicht), aktuelle Config 1,5
- Diagnose mit Eingriffen: Sprung und Rampe 28 Tage erkannt in 16 von 20 Fällen, langsame Rampen feuern in 3 von 10 (Ziel höchstens 20 %: nicht erreicht)

## Setup

- Zeitraum: bewertet 2014-04-02 bis 2016-03-19 (718 Tage), davor die Historie aus train. Kalibriert wird nur auf validation
- Echte Trends: 6 im Zeitraum: Niveau ändert sich um mindestens 20 % gegen die 28 Tage davor, der Übergang ist nach 28 Tagen abgeschlossen und das neue Niveau hält mindestens 10 Tage
- Treffer: ein Reset von 10 Tagen vor bis 38 Tage nach dem Beginn eines echten Trends. Jeder andere Reset ist falsch
- Modus: mit Reset: schlanke Kette (Analyse, Streak, Einordnung nach Regel, Reset) über die ganze Reihe, ohne Prognose und ohne LLM
- Detektor: Referenz Rolling 60 vor dem Beobachtungsfenster, Median/MAD für daily und weekday
- Commit: c286c69

## Ergebnis auf den echten Daten: gewählte Schwellen gegen aktuelle Config

| Einstellung | weekday / weekly / long_term % | echte Trends erkannt | Tage bis Erkennung (Mittel) | Resets gesamt | falsche Resets je Jahr | Grenze |
|---|---|---|---:|---:|---:|---:|
| gewählt | 2,5 / 0,75 / 12,5 | 5/6 | 11,2 | 6 | 1,0 | 1,5 |
| aktuelle Config | 12,5 / 2 / 0,75 | 4/6 | 16,2 | 6 | 1,5 | 1,5 |

## Echte Trends: wann meldet der Detektor (mit Reset)?

| Beginn | Änderung [%] | gewählt: Reset am | gewählt: Tage seit Beginn | aktuelle Config: Reset am | aktuelle Config: Tage seit Beginn |
|---|---:|---|---:|---|---:|
| 23.05.2014 | -48,6 | 18.06.2014 | 26,0 | 18.06.2014 | 26,0 |
| 18.06.2014 | 22,8 | 18.06.2014 | 0,0 | 18.06.2014 | 0,0 |
| 26.08.2014 | 27,3 | 16.09.2014 | 21,0 | 16.09.2014 | 21,0 |
| 25.11.2014 | 23,2 | 13.12.2014 | 18,0 | 13.12.2014 | 18,0 |
| 10.08.2015 | 25,7 | 01.08.2015 | -9,0 | nicht erkannt | - |
| 13.10.2015 | 21,9 | nicht erkannt | - | nicht erkannt | - |

## Diagnose mit Eingriffen: ab welcher Änderung erkennt er? (Cutover-Fenster, mit Reset)

| Szenario | Sollverhalten | gewählt: erkannt bzw. feuert (n von N Fenstern) | gewählt: Tage (Mittel) | aktuelle Config: erkannt bzw. feuert (n von N Fenstern) | aktuelle Config: Tage (Mittel) |
|---|---|---|---:|---|---:|
| Sprung +30 % | erkennen | 4/5 | 13,8 | 4/5 | 13,8 |
| Sprung −30 % | erkennen | 4/5 | 17,5 | 4/5 | 17,0 |
| Rampe über 28 Tage +30 % | erkennen | 3/5 | 26,0 | 3/5 | 26,0 |
| Rampe über 28 Tage −30 % | erkennen | 5/5 | 31,0 | 5/5 | 29,8 |
| Rampe über 56 Tage +30 % | nicht feuern | 1/5 | 44,0 | 2/5 | 47,5 |
| Rampe über 56 Tage −30 % | nicht feuern | 2/5 | 40,0 | 3/5 | 35,0 |
| Einzeltag-Spitze +1000 W über 3 h | Alarm am Ereignistag | 1/5 | 1,0 | 1/5 | 1,0 |
| Einzeltag-Spitze +1000 W über 6 h | Alarm am Ereignistag | 5/5 | 1,0 | 5/5 | 1,0 |

## Raster der Schwellen nach Rang (die besten 10 und die aktuelle Config)

| weekday | weekly | long_term [%] | echte Trends erkannt | Tage bis Erkennung (Mittel) | falsche Resets je Jahr | gewählt | aktuelle Config |
|---|---|---|---|---:|---:|---|---|
| 2,5 | 0,75 | 12,5 | 5/6 | 11,2 | 1,0 | ja |  |
| 2,75 | 0,75 | 12,5 | 5/6 | 11,2 | 1,0 |  |  |
| 2,5 | 1 | 12,5 | 5/6 | 11,8 | 0,5 |  |  |
| 2,75 | 1 | 12,5 | 5/6 | 11,8 | 0,5 |  |  |
| 2,75 | 0,75 | 15 | 5/6 | 13,2 | 0,0 |  |  |
| 2,5 | 0,75 | 15 | 5/6 | 13,2 | 0,5 |  |  |
| 2,75 | 0,5 | 15 | 5/6 | 13,2 | 0,5 |  |  |
| 2,5 | 0,75 | 10 | 5/6 | 13,6 | 1,0 |  |  |
| 2,75 | 0,75 | 10 | 5/6 | 13,6 | 1,0 |  |  |
| 2,75 | 0,5 | 20 | 5/6 | 17,2 | 0,0 |  |  |
| 2 | 0,75 | 12,5 | 4/6 | 16,2 | 1,5 |  | aktuelle Config |

## Hinweise

- Gewählt wird unter der Grenze für falsche Resets je Jahr (1,5) der Punkt mit den meisten erkannten echten Trends, dann dem kürzesten mittleren Verzug. Das Raster steht vollständig in result_streak_sensitivity.csv
- Ein Reset im Trefferfenster eines Trends zählt als Treffer, auch wenn ein Reset zwei nahe Ereignisse trifft. Nach einem Reset fehlen weekday und long_term etwa 28 Tage, das ist im Lauf enthalten
- Diagnose: positive Art = erster Reset in Tag 1 bis 38 nach dem Cutover. Langsame Rampe = erster Reset außerhalb der Trefferfenster echter Trends (soll nie vorkommen). Spitze = Alarm am Ereignistag. Beginne des natürlichen Hintergrunds zählen mit
- Grenzen: wenige echte Trends in einem Haushalt, ein Treffer mehr oder weniger sind mehrere Prozentpunkte. Der Unterschied zwischen benachbarten Rasterpunkten ist nicht belastbar. Mindeständerung, Übergangs- und Haltedauer, Trefferfenster und die Grenze für falsche Resets sind Setzungen
- Die gewählten Schwellen sind in NumericalAnalysisConfig zu übernehmen, gerundet
