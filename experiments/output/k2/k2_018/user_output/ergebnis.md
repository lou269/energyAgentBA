# K2 Schwellen der Anomalieerkennung, Lauf k2_018

## Kurzfassung

- Gewählt: weekday / weekly / long_term % = 1,25 / 1 / 25 (aktuelle Config 2,5 / 0,75 / 20), Einzeltag-Schwelle 3,2
- Erkennung ohne Reset: 11 von 20 Änderungen von mindestens 20 % in 28 Tagen erkannt, im Mittel nach 17,3 Tagen. Ziel mindestens 80 %: nicht erreicht
- Langsame Rampen: feuert bei 3 von 10. Ziel höchstens 20 %: nicht erreicht
- Falsche Beginne in der Kontrolle je Fenster: 0,4 ohne Reset (Grenze 0,5: erreicht), 0,8 im Betrieb mit Reset (nicht erreicht)

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
| weekday (Streak, Score) | 2,5 | 1,25 |
| weekly (Streak, Score) | 0,75 | 1 |
| long_term (Streak, %) | 20 | 25 |

## Ohne Reset (Grundlage der Wahl): Erkennung und Feuern bei langsamer Änderung

| Szenario | Sollverhalten | erkannt bzw. feuert (n von N Fenstern) | Tage bis Erkennung (Mittel) |
|---|---|---|---:|
| Sprung +30 % | erkennen | 4/5 | 11,8 |
| Sprung −30 % | erkennen | 3/5 | 17,3 |
| Rampe über 28 Tage +30 % | erkennen | 2/5 | 22,5 |
| Rampe über 28 Tage −30 % | erkennen | 2/5 | 23,0 |
| Rampe über 56 Tage +30 % | nicht feuern | 2/5 | - |
| Rampe über 56 Tage −30 % | nicht feuern | 1/5 | - |

## Im Betrieb mit Reset (Abnahme): Wird die Änderung erkannt? Tag seit Cutover

| Szenario | 2013-10-15 | 2014-02-12 | 2014-06-12 | 2014-10-10 | 2015-02-07 | Tage bis Erkennung (Mittel) | erkannt (n von N Fenstern) | Skala bei Erkennung |
|---|---:|---:|---:|---:|---:|---:|---|---|
| Sprung +30 % | 5 | - | 18 | 5 | 14 | 10,5 | 4/5 | weekday+weekly, weekly+long_term |
| Sprung −30 % | 19 | 16 | - | 24 | - | 19,7 | 3/5 | weekday+weekly, weekly+long_term |
| Rampe über 28 Tage +30 % | - | 23 | 18 | - | 22 | 21,0 | 3/5 | weekly+long_term |
| Rampe über 28 Tage −30 % | 22 | - | - | 24 | - | 23,0 | 2/5 | weekday+weekly |
| Einzeltag-Spitze +1000 W über 3 h | 1 | - | - | 1 | - | 1,0 | 2/5 | daily |
| Einzeltag-Spitze +1000 W über 6 h | 1 | 1 | - | 1 | - | 1,0 | 3/5 | daily, weekday |

## Im Betrieb mit Reset (Abnahme): Feuert er bei langsamer Änderung? Jedes Feuern ist falsch, Tag seit Cutover

| Szenario | 2013-10-15 | 2014-02-12 | 2014-06-12 | 2014-10-10 | 2015-02-07 | Tage bis zum Feuern (Mittel) | feuert (n von N Fenstern) | Skala beim Feuern |
|---|---:|---:|---:|---:|---:|---:|---|---|
| Rampe über 56 Tage +30 % | - | - | 18 | 56 | - | 37,0 | 2/5 | weekday+weekly, weekly+long_term |
| Rampe über 56 Tage −30 % | - | - | 58 | - | - | 58,0 | 1/5 | weekday+weekly |

## Meldungen ohne Ereignis (Kontrolle), ohne Reset gegen im Betrieb

| Kennzahl | ohne Reset | mit Reset | Grenze bzw. Ziel |
|---|---:|---:|---:|
| falsche Beginne bzw. Resets je Fenster | 0,4 | 0,8 | 0,5 |
| Einzeltag-Alarme [%] | 5,1 | 7,1 | 5,0 |
| Gate offen [%] | - | 8,3 | - |

## Raster der Schwellen nach Rang (die besten 10 und die aktuelle Config)

| weekday | weekly | long_term [%] | falsche Beginne je Fenster | Änderungen erkannt | Tage bis Erkennung (Mittel) | feuert bei langsamer Rampe | gewählt | aktuelle Config |
|---|---|---|---:|---|---:|---|---|---|
| 1,25 | 1 | 25 | 0,4 | 11/20 | 17,3 | 3/10 | ja |  |
| 2 | 1 | 20 | 0,2 | 10/20 | 13,7 | 4/10 |  |  |
| 1,75 | 1 | 20 | 0,4 | 10/20 | 13,7 | 4/10 |  |  |
| 2,5 | 1 | 20 | 0,2 | 10/20 | 14,7 | 4/10 |  |  |
| 2,75 | 1 | 20 | 0,2 | 10/20 | 14,7 | 4/10 |  |  |
| 2 | 0,75 | 20 | 0,2 | 10/20 | 13,4 | 6/10 |  |  |
| 1,75 | 0,75 | 20 | 0,4 | 10/20 | 13,4 | 6/10 |  |  |
| 2,5 | 0,75 | 20 | 0,2 | 10/20 | 14,4 | 6/10 |  | Config |
| 2,75 | 0,75 | 20 | 0,2 | 10/20 | 14,4 | 6/10 |  |  |
| 1,5 | 0,75 | 25 | 0,4 | 8/20 | 15,0 | 3/10 |  |  |

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
