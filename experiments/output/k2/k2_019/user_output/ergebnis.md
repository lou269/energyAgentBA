# K2 Schwellen der Anomalieerkennung, Lauf k2_019

## Kurzfassung

- Gewählt: weekday / weekly / long_term % = 2,5 / 1 / 20 (aktuelle Config 2,5 / 0,75 / 20), Einzeltag-Schwelle 3,2
- Erkennung ohne Reset: 10 von 20 Änderungen von mindestens 20 % in 28 Tagen erkannt, im Mittel nach 13,4 Tagen. Ziel mindestens 80 %: nicht erreicht
- Langsame Rampen: feuert bei 4 von 10. Ziel höchstens 20 %: nicht erreicht
- Falsche Beginne in der Kontrolle je Fenster: 0,4 ohne Reset (Grenze 0,5: erreicht), 0,6 im Betrieb mit Reset (nicht erreicht)

## Setup

- Cutover: 2013-10-15, 2014-02-12, 2014-06-12, 2014-10-10, 2015-02-07
- Zeitraum je Cutover: Kaltstart, 60 Tage Überwachung vor dem Cutover, 60 Tage danach
- Soll: neues Muster, wenn sich das Niveau in 28 Tagen um mindestens 20 % ändert und mindestens 10 Tage hält. Langsamere Änderungen sollen still bleiben
- Modi: ohne Reset = nur der Detektor, darauf werden die Schwellen gewählt. Mit Reset = Betrieb mit Regel wie SYS2 und den gewählten Schwellen, Abnahme
- Detektor: Referenz Rolling 60 vor dem Beobachtungsfenster, Median/MAD für daily und weekday
- Commit: 1590933 (mit lokalen Änderungen)

## Szenarien und Sollverhalten

| Szenario | Sollverhalten |
|---|---|
| Sprung +30 % | erkennen |
| Sprung −30 % | erkennen |
| Rampe über 28 Tage +30 % | erkennen |
| Rampe über 28 Tage −30 % | erkennen |
| Rampe über 56 Tage +30 % | nicht feuern |
| Rampe über 56 Tage −30 % | nicht feuern |
| Einzeltag-Spitze +1000 W über 3 h | Alarm am Ereignistag |
| Einzeltag-Spitze +1000 W über 6 h | Alarm am Ereignistag |

## Gewählte Schwellen

| Parameter | aktuelle Config | gewählt |
|---|---|---|
| Einzeltag-Schwelle (Score) | 3,2 | 3,2 |
| weekday (Streak, Score) | 2,5 | 2,5 |
| weekly (Streak, Score) | 0,75 | 1 |
| long_term (Streak, %) | 20 | 20 |

## Ohne Reset (Grundlage der Wahl): Erkennung und Feuern bei langsamer Änderung

| Szenario | Sollverhalten | erkannt bzw. feuert (n von N Fenstern) | Tage bis Erkennung (Mittel) |
|---|---|---|---:|
| Sprung +30 % | erkennen | 4/5 | 13,8 |
| Sprung −30 % | erkennen | 1/5 | 6,0 |
| Rampe über 28 Tage +30 % | erkennen | 4/5 | 16,5 |
| Rampe über 28 Tage −30 % | erkennen | 1/5 | 7,0 |
| Rampe über 56 Tage +30 % | nicht feuern | 2/5 | - |
| Rampe über 56 Tage −30 % | nicht feuern | 2/5 | - |

## Im Betrieb mit Reset (Abnahme): Wird die Änderung erkannt? Tag seit Cutover

| Szenario | 2013-10-15 | 2014-02-12 | 2014-06-12 | 2014-10-10 | 2015-02-07 | Tage bis Erkennung (Mittel) | erkannt (n von N Fenstern) | Skala bei Erkennung |
|---|---:|---:|---:|---:|---:|---:|---|---|
| Sprung +30 % | 14 | 21 | - | 8 | 13 | 14,0 | 4/5 | weekly+long_term |
| Sprung −30 % | - | - | 6 | - | - | 6,0 | 1/5 | weekly+long_term |
| Rampe über 28 Tage +30 % | - | 21 | 7 | 17 | 21 | 16,5 | 4/5 | weekly+long_term |
| Rampe über 28 Tage −30 % | - | - | 7 | - | - | 7,0 | 1/5 | weekly+long_term |
| Einzeltag-Spitze +1000 W über 3 h | 1 | - | - | 1 | - | 1,0 | 2/5 | daily |
| Einzeltag-Spitze +1000 W über 6 h | 1 | 1 | - | 1 | - | 1,0 | 3/5 | daily, weekday |

## Im Betrieb mit Reset (Abnahme): Feuert er bei langsamer Änderung? Jedes Feuern ist falsch, Tag seit Cutover

| Szenario | 2013-10-15 | 2014-02-12 | 2014-06-12 | 2014-10-10 | 2015-02-07 | Tage bis zum Feuern (Mittel) | feuert (n von N Fenstern) | Skala beim Feuern |
|---|---:|---:|---:|---:|---:|---:|---|---|
| Rampe über 56 Tage +30 % | - | - | 7 | 58 | - | 32,5 | 2/5 | weekly+long_term |
| Rampe über 56 Tage −30 % | - | - | 7 | - | 59 | 33,0 | 2/5 | weekday+weekly+long_term, weekly+long_term |

## Meldungen ohne Ereignis (Kontrolle), ohne Reset gegen im Betrieb

| Kennzahl | ohne Reset | mit Reset | Grenze bzw. Ziel |
|---|---:|---:|---:|
| falsche Beginne bzw. Resets je Fenster | 0,4 | 0,6 | 0,5 |
| Einzeltag-Alarme [%] | 5,1 | 5,8 | 5,0 |
| Gate offen [%] | - | 6,6 | - |

## Raster der Schwellen nach Rang (die besten 10 und die aktuelle Config)

| weekday | weekly | long_term [%] | falsche Beginne je Fenster | Änderungen erkannt | Tage bis Erkennung (Mittel) | feuert bei langsamer Rampe | gewählt | aktuelle Config |
|---|---|---|---:|---|---:|---|---|---|
| 2,5 | 1 | 20 | 0,4 | 10/20 | 13,4 | 4/10 | ja |  |
| 2,75 | 1 | 20 | 0,4 | 10/20 | 13,4 | 4/10 |  |  |
| 2,5 | 1,25 | 20 | 0,4 | 9/20 | 12,9 | 4/10 |  |  |
| 2,75 | 1,25 | 20 | 0,4 | 9/20 | 12,9 | 4/10 |  |  |
| 2 | 1 | 25 | 0,4 | 8/20 | 15,9 | 4/10 |  |  |
| 2 | 0,75 | 25 | 0,4 | 8/20 | 15,9 | 5/10 |  |  |
| 2,5 | 1 | 25 | 0,2 | 7/20 | 17,7 | 3/10 |  |  |
| 2,75 | 1 | 25 | 0,2 | 7/20 | 17,7 | 3/10 |  |  |
| 2 | 1,25 | 25 | 0,4 | 7/20 | 16,3 | 4/10 |  |  |
| 2,5 | 0,75 | 25 | 0,2 | 7/20 | 17,7 | 4/10 |  |  |
| 2,5 | 0,75 | 20 | 0,6 | 10/20 | 13,1 | 6/10 |  | Config |

## Hinweise

- Tag seit Cutover = Entscheidungstag: an Tag n meldet das System, eingeordnet ist dabei Tag n-1. Ab Cutover zählt deshalb erst ab Tag 1
- Erkannt: erster Beginn einer Drift (Streak auf mindestens zwei Skalen) zwischen Tag 1 und Tag 28 nach dem Cutover. Im Betrieb mit Reset der erste Reset in dieser Zeit. Einzeltag-Spitze: Alarm am Ereignistag, den die Kontrolle nicht hat
- Feuert: ein Beginn bei einer langsamen Rampe, außerhalb des Trefferfensters eines echten Trends (10 Tage vor bis 28 Tage nach dessen Beginn). Beginne des natürlichen Hintergrunds zählen mit
- Falsche Beginne: nur in der Kontrolle gezählt, außerhalb des Trefferfensters eines echten Trends (auch in einem echten Einbruch). Bei den Eingriffsreihen ist nicht zu trennen, was der Eingriff und was der Hintergrund ausgelöst hat
- Echte Trends: Abweichung des 5-Tage-Mittels vom Median der 28 Tage davor, ab 20 %, hält sie 10 Tage, ist es ein Trend, sonst ein Einbruch. Die Glättung verbreitert kurze Einbrüche um 1 bis 2 Tage. Die Liste steht unter raw/k2_events.csv
- Einzeltag-Schwelle: das 95-%-Quantil des größten Scores von daily und weekday an den Kontrolltagen
- Auswahl der Streak-Schwellen: erst die Grenze für falsche Beginne, dann die meisten erkannten Änderungen, dann wenig Feuern bei langsamen Rampen, dann früher Tag. Das Raster steht vollständig in result_streak_sensitivity.csv
- Grenzen: fünf Cutover-Fenster, die Arten eines Fensters teilen denselben natürlichen Hintergrund. n von 5 stützt sich auf höchstens fünf voneinander abhängige Fenster, Unterschiede von ein bis zwei Fällen zwischen Rasterpunkten sind nicht belastbar
- Die gewählten Schwellen sind in NumericalAnalysisConfig zu übernehmen, gerundet
