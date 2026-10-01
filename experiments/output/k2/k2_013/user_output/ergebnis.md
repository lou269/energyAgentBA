# K2 Schwellen der Anomalieerkennung, Lauf k2_013

## Setup

- Cutover: 2013-10-15, 2014-02-12, 2014-06-12, 2014-10-10, 2015-02-07
- Zeitraum je Cutover: Kaltstart, 60 Tage Überwachung vor dem Cutover, 60 Tage danach
- Ereignisse ab Cutover: Dauerlast +30 W, Dauerlast +50 W, Dauerlast +100 W, Dauerlast +200 W, Einzeltag-Spitze +1000 W über 3 h, Einzeltag-Spitze +1000 W über 6 h, jeweils gepaart mit unverändertem Kontrolllauf
- Modi: ohne Reset = nur Detektor, darauf werden Einzeltag-Schwelle und Streak-Empfindlichkeit bestimmt (nur keine Änderung, Dauerlast +100 W). Mit Reset = Betrieb mit Regel wie SYS2, alle Ereignisse
- Detektor: Referenz Rolling 60 vor dem Beobachtungsfenster, Median/MAD für daily und weekday
- Schwellen im Lauf (Einzeltag / Streak weekday / weekly / long_term %): 3,2 / 2,5 / 0,75 / 20
- Commit: 83d6802 (mit lokalen Änderungen)

## Kennzahlen

| Kennzahl | Wert | Bezug |
|---|---|---|
| Einzeltag-Schwelle für 5 % Alarme in der Kontrolle | 3,2 | gilt im Lauf mit Reset |
| Streak-Schwellen (weekday / weekly / long_term %), Fehlalarm-Budget und früheste Erkennung | 2,5 / 0,75 / 20 | gilt im Lauf mit Reset |
| Detektor: Gate offen ohne Ereignis, mit Reset [%] | 6,0 | Einzeltag-Alarme und Drift zusammen |
| Detektor: falsche Resets im Betrieb je Fenster, alle Ereignisse | 0,0 | nur Resets, die der Kontrolllauf in ±Toleranz nicht hat, bei einer Dauerlast ohne die Erkennung |
| Detektor: Resets im Kontrolllauf ohne Ereignis, je Fenster | 0,6 | Grundrate, zählt nicht als falsch. Ohne Reset (gewählter Punkt) 0,4, Budget 0,5 |
| Detektor: Einzeltag-Spitze +1000 W über 3 h erkannt (Alarm am Ereignistag) | 2/5 | Skala daily, falsche Resets 0,0 je Fenster |
| Detektor: Einzeltag-Spitze +1000 W über 6 h erkannt (Alarm am Ereignistag) | 3/5 | Skala daily, weekday, falsche Resets 0,0 je Fenster |
| Detektor: Dauerlast +100 W erkannt (new_pattern) | 3/3 | im Mittel nach 20,0 Tagen, Skala weekly+long_term, falsche Resets 0,0 je Fenster |
| Detektor: Dauerlast +200 W erkannt (new_pattern) | 3/3 | im Mittel nach 16,3 Tagen, Skala weekly+long_term, falsche Resets 0,0 je Fenster |
| Detektor: Dauerlast +30 W erkannt (new_pattern) | 0/3 | Skala -, falsche Resets 0,2 je Fenster |
| Detektor: Dauerlast +50 W erkannt (new_pattern) | 2/3 | im Mittel nach 22,0 Tagen, Skala weekly+long_term, falsche Resets 0,0 je Fenster |

## Ohne Ereignis: Kontrolllauf über das ganze Fenster, Mittel über Cutover

| Variante | Gate offen mit Reset [%] | davon Einzeltag mit Reset [%] | Resets der Kontrolle je Fenster |
|---|---:|---:|---:|
| Detektor | 6,0 | 5,5 | 0,6 |

## Einzeltag-Schwelle: ein Wert für daily und weekday, Alarmrate der Kontrolle je Cutover, ohne Reset

| Cutover | Schwelle (Score) | Einzeltag-Alarme Kontrolle [%] |
|---|---:|---:|
| 2013-10-15 | 3,2 | 10,7 |
| 2014-02-12 | 3,2 | 3,3 |
| 2014-06-12 | 3,2 | 0,8 |
| 2014-10-10 | 3,2 | 4,1 |
| 2015-02-07 | 3,2 | 6,6 |

## Streak-Schwellen: Raster und gewählter Punkt, ohne Reset, Mittel über Cutover

| Streak weekday | Streak weekly | Streak long_term [%] | falsche new_pattern je Fenster | Stufe erkannt | Erkennungstag im Mittel | gewählt |
|---|---|---|---:|---|---:|---|
| 1,75 | 0,75 | 12,5 | 2,2 | 3/3 | 17,7 |  |
| 1,75 | 0,75 | 15 | 2,0 | 3/3 | 18,3 |  |
| 1,75 | 0,75 | 20 | 0,8 | 3/3 | 19,7 |  |
| 1,75 | 0,75 | 25 | 0,6 | 3/3 | 23,7 |  |
| 1,75 | 1 | 12,5 | 1,8 | 3/3 | 18,7 |  |
| 1,75 | 1 | 15 | 1,6 | 3/3 | 19,0 |  |
| 1,75 | 1 | 20 | 0,8 | 3/3 | 23,3 |  |
| 1,75 | 1 | 25 | 0,6 | 3/3 | 23,7 |  |
| 1,75 | 1,25 | 12,5 | 1,6 | 2/3 | 17,5 |  |
| 1,75 | 1,25 | 15 | 1,4 | 2/3 | 22,5 |  |
| 1,75 | 1,25 | 20 | 0,8 | 2/3 | 28,5 |  |
| 1,75 | 1,25 | 25 | 0,6 | 2/3 | 28,5 |  |
| 1,75 | 1,5 | 12,5 | 0,8 | 1/3 | 23,0 |  |
| 1,75 | 1,5 | 15 | 1,0 | 1/3 | 23,0 |  |
| 1,75 | 1,5 | 20 | 0,6 | 0/3 | - |  |
| 1,75 | 1,5 | 25 | 0,6 | 0/3 | - |  |
| 1,75 | 1,75 | 12,5 | 0,6 | 0/3 | - |  |
| 1,75 | 1,75 | 15 | 0,8 | 0/3 | - |  |
| 1,75 | 1,75 | 20 | 0,4 | 0/3 | - |  |
| 1,75 | 1,75 | 25 | 0,4 | 0/3 | - |  |
| 2 | 0,75 | 12,5 | 2,0 | 3/3 | 17,7 |  |
| 2 | 0,75 | 15 | 1,8 | 3/3 | 18,3 |  |
| 2 | 0,75 | 20 | 0,6 | 3/3 | 19,7 |  |
| 2 | 0,75 | 25 | 0,4 | 3/3 | 23,7 |  |
| 2 | 1 | 12,5 | 1,6 | 3/3 | 18,7 |  |
| 2 | 1 | 15 | 1,4 | 3/3 | 19,0 |  |
| 2 | 1 | 20 | 0,6 | 3/3 | 23,3 |  |
| 2 | 1 | 25 | 0,4 | 3/3 | 23,7 |  |
| 2 | 1,25 | 12,5 | 1,4 | 2/3 | 17,5 |  |
| 2 | 1,25 | 15 | 1,2 | 2/3 | 22,5 |  |
| 2 | 1,25 | 20 | 0,6 | 2/3 | 28,5 |  |
| 2 | 1,25 | 25 | 0,4 | 2/3 | 28,5 |  |
| 2 | 1,5 | 12,5 | 0,6 | 1/3 | 23,0 |  |
| 2 | 1,5 | 15 | 0,8 | 1/3 | 23,0 |  |
| 2 | 1,5 | 20 | 0,4 | 0/3 | - |  |
| 2 | 1,5 | 25 | 0,4 | 0/3 | - |  |
| 2 | 1,75 | 12,5 | 0,6 | 0/3 | - |  |
| 2 | 1,75 | 15 | 0,8 | 0/3 | - |  |
| 2 | 1,75 | 20 | 0,4 | 0/3 | - |  |
| 2 | 1,75 | 25 | 0,4 | 0/3 | - |  |
| 2,5 | 0,75 | 12,5 | 1,8 | 3/3 | 17,7 |  |
| 2,5 | 0,75 | 15 | 1,6 | 3/3 | 18,3 |  |
| 2,5 | 0,75 | 20 | 0,4 | 3/3 | 19,7 | ja |
| 2,5 | 0,75 | 25 | 0,2 | 3/3 | 23,7 |  |
| 2,5 | 1 | 12,5 | 1,4 | 3/3 | 18,7 |  |
| 2,5 | 1 | 15 | 1,2 | 3/3 | 19,0 |  |
| 2,5 | 1 | 20 | 0,4 | 3/3 | 23,3 |  |
| 2,5 | 1 | 25 | 0,2 | 3/3 | 23,7 |  |
| 2,5 | 1,25 | 12,5 | 1,2 | 2/3 | 17,5 |  |
| 2,5 | 1,25 | 15 | 1,0 | 2/3 | 22,5 |  |
| 2,5 | 1,25 | 20 | 0,4 | 2/3 | 28,5 |  |
| 2,5 | 1,25 | 25 | 0,2 | 2/3 | 28,5 |  |
| 2,5 | 1,5 | 12,5 | 0,4 | 1/3 | 23,0 |  |
| 2,5 | 1,5 | 15 | 0,6 | 1/3 | 23,0 |  |
| 2,5 | 1,5 | 20 | 0,2 | 0/3 | - |  |
| 2,5 | 1,5 | 25 | 0,2 | 0/3 | - |  |
| 2,5 | 1,75 | 12,5 | 0,4 | 0/3 | - |  |
| 2,5 | 1,75 | 15 | 0,6 | 0/3 | - |  |
| 2,5 | 1,75 | 20 | 0,2 | 0/3 | - |  |
| 2,5 | 1,75 | 25 | 0,2 | 0/3 | - |  |
| 2,75 | 0,75 | 12,5 | 1,8 | 3/3 | 17,7 |  |
| 2,75 | 0,75 | 15 | 1,6 | 3/3 | 18,3 |  |
| 2,75 | 0,75 | 20 | 0,4 | 3/3 | 19,7 |  |
| 2,75 | 0,75 | 25 | 0,2 | 3/3 | 23,7 |  |
| 2,75 | 1 | 12,5 | 1,4 | 3/3 | 18,7 |  |
| 2,75 | 1 | 15 | 1,2 | 3/3 | 19,0 |  |
| 2,75 | 1 | 20 | 0,4 | 3/3 | 23,3 |  |
| 2,75 | 1 | 25 | 0,2 | 3/3 | 23,7 |  |
| 2,75 | 1,25 | 12,5 | 1,2 | 2/3 | 17,5 |  |
| 2,75 | 1,25 | 15 | 1,0 | 2/3 | 22,5 |  |
| 2,75 | 1,25 | 20 | 0,4 | 2/3 | 28,5 |  |
| 2,75 | 1,25 | 25 | 0,2 | 2/3 | 28,5 |  |
| 2,75 | 1,5 | 12,5 | 0,4 | 1/3 | 23,0 |  |
| 2,75 | 1,5 | 15 | 0,6 | 1/3 | 23,0 |  |
| 2,75 | 1,5 | 20 | 0,2 | 0/3 | - |  |
| 2,75 | 1,5 | 25 | 0,2 | 0/3 | - |  |
| 2,75 | 1,75 | 12,5 | 0,4 | 0/3 | - |  |
| 2,75 | 1,75 | 15 | 0,6 | 0/3 | - |  |
| 2,75 | 1,75 | 20 | 0,2 | 0/3 | - |  |
| 2,75 | 1,75 | 25 | 0,2 | 0/3 | - |  |

## Erkennung je Ereignis im Betrieb mit Reset, Tag seit Cutover je Cutover

| Variante | Ereignis | 2013-10-15 (Dauerlast nicht gezählt) | 2014-02-12 | 2014-06-12 | 2014-10-10 (Dauerlast nicht gezählt) | 2015-02-07 | Mittel erkannter | erkannt | falsche Resets je Fenster | Skala bei Erkennung |
|---|---|---:|---:|---:|---:|---:|---:|---|---:|---|
| Detektor | Dauerlast +30 W | - | - | - | 21 | - | - | 0/3 | 0,2 |  |
| Detektor | Dauerlast +50 W | - | 22 | - | 11 | 22 | 22,0 | 2/3 | 0,0 | weekly+long_term |
| Detektor | Dauerlast +100 W | 15 | 21 | 24 | 9 | 15 | 20,0 | 3/3 | 0,0 | weekly+long_term |
| Detektor | Dauerlast +200 W | 5 | 17 | 21 | 6 | 11 | 16,3 | 3/3 | 0,0 | weekly+long_term |
| Detektor | Einzeltag-Spitze +1000 W über 3 h | 1 | - | - | 1 | - | 1,0 | 2/5 | 0,0 | daily |
| Detektor | Einzeltag-Spitze +1000 W über 6 h | 1 | 1 | - | 1 | - | 1,0 | 3/5 | 0,0 | daily, weekday |

## Hinweise

- Tag seit Cutover = Entscheidungstag: an Tag n meldet das System, eingeordnet ist dabei Tag n-1. Ab Cutover zählt deshalb erst ab Tag 1
- Einzeltag-Schwelle: das 95-%-Quantil des größten Scores von daily und weekday an den Kontrolltagen, ein Wert für beide. Streak-Schwellen: Raster, gewählt wird nach dem Fehlalarm-Budget (max_false_new_pattern) und dann nach früher Erkennung in allen gezählten Fenstern. Beides offline auf den Läufen ohne Reset, Einzeltag-Schwelle und falsche new_pattern über alle Cutover, die Erkennung der Stufe ohne die nicht gezählten
- Stufe erkannt (ohne Reset): erster Tag, an dem bei der Stufe ein new_pattern beginnt und bei der Kontrolle 7 Tage davor und danach keins, also wie im Betrieb mit Reset
- Der Lauf mit Reset nutzt die gewählten Schwellen (Einzeltag und Streak), aus demselben Lauf. In NumericalAnalysisConfig übernehmen, gerundet
- erkannt, im Betrieb mit Reset: dauerhafte Änderung = erster eigener Reset (new_pattern) nach dem Cutover, der Kontrolllauf hat 7 Tage davor und danach keinen. Einzeltag-Spitze = Alarm am Ereignistag, den der Kontrolllauf nicht hat
- nicht gezählt: 2013-10-15, 2014-10-10, Beginn der Heizperiode. Die Kontrolle liegt dort knapp unter der Streak-Bedingung, jede Störung löst new_pattern aus. Mittel, erkannt und Skala der Dauerlasten ohne diese Cutover, die Einzeltag-Spitzen zählen dort mit
- Resets der Kontrolle: Resets des Kontrolllaufs ohne Änderung, im Betrieb mit Reset, Mittel über alle Cutover. Die Grundrate (vor allem Jahreszeit), Vergleichsbasis für die falschen Resets und vergleichbar mit den falschen new_pattern ohne Reset, die ebenfalls an der Kontrolle gezählt werden
- falsche Resets: eigene Resets nach dem Cutover, für die die Kontrolle in ±Toleranz keinen Reset hat. Bei einer Dauerlast ist der erste Reset die Erkennung und zählt nicht, bei einer Spitze zählt jeder
- Skala bei Erkennung: bei new_pattern die Skalen mit Streak, bei der Spitze die Einzeltag-Skala mit dem höchsten Score
