# K2 Schwellen der Anomalieerkennung, Lauf k2_016

## Setup

- Cutover: 2013-10-15, 2014-02-12, 2014-06-12, 2014-10-10, 2015-02-07
- Zeitraum je Cutover: Kaltstart, 60 Tage Überwachung vor dem Cutover, 60 Tage danach
- Ereignisse ab Cutover: Dauerlast +30 W, Dauerlast +50 W, Dauerlast +100 W, Dauerlast +200 W, Dauerlast −100 W, Einzeltag-Spitze +1000 W über 3 h, Einzeltag-Spitze +1000 W über 6 h, jeweils gepaart mit unverändertem Kontrolllauf
- Modi: ohne Reset = nur Detektor, darauf werden Einzeltag-Schwelle und Streak-Empfindlichkeit bestimmt (nur keine Änderung, Dauerlast +100 W, Dauerlast −100 W). Mit Reset = Betrieb mit Regel wie SYS2, alle Ereignisse
- Detektor: Referenz Rolling 60 vor dem Beobachtungsfenster, Median/MAD für daily und weekday
- Schwellen im Lauf (Einzeltag / Streak weekday / weekly / long_term %): 3,2 / 2,5 / 0,75 / 20
- Commit: 1590933 (mit lokalen Änderungen)

## Kennzahlen

| Kennzahl | Wert | Bezug |
|---|---|---|
| Einzeltag-Schwelle für 5 % Alarme in der Kontrolle | 3,2 | gilt im Lauf mit Reset |
| Streak-Schwellen (weekday / weekly / long_term %), Fehlalarm-Budget und früheste Erkennung | 2,5 / 0,75 / 20 | gilt im Lauf mit Reset |
| Detektor: Gate offen ohne Ereignis, mit Reset [%] | 6,3 | Einzeltag-Alarme und Drift zusammen |
| Detektor: falsche Resets im Betrieb je Fenster, alle Ereignisse | 0,0 | nur Resets, die der Kontrolllauf in ±Toleranz nicht hat, bei einer Dauerlast ohne die Erkennung |
| Detektor: Resets im Kontrolllauf ohne Ereignis, je Fenster | 0,6 | Grundrate, zählt nicht als falsch. Ohne Reset (gewählter Punkt) 0,4, Budget 0,8 |
| Detektor: Einzeltag-Spitze +1000 W über 3 h erkannt (Alarm am Ereignistag) | 2/5 | Skala daily, falsche Resets 0,0 je Fenster |
| Detektor: Einzeltag-Spitze +1000 W über 6 h erkannt (Alarm am Ereignistag) | 3/5 | Skala daily, weekday, falsche Resets 0,0 je Fenster |
| Detektor: Dauerlast +100 W erkannt (new_pattern) | 3/3 | im Mittel nach 20,0 Tagen, Skala weekly+long_term, falsche Resets 0,0 je Fenster |
| Detektor: Dauerlast −100 W erkannt (new_pattern) | 2/3 | im Mittel nach 34,0 Tagen, Skala weekly+long_term, falsche Resets 0,0 je Fenster |
| Detektor: Dauerlast +200 W erkannt (new_pattern) | 3/3 | im Mittel nach 16,3 Tagen, Skala weekly+long_term, falsche Resets 0,0 je Fenster |
| Detektor: Dauerlast +30 W erkannt (new_pattern) | 0/3 | Skala -, falsche Resets 0,2 je Fenster |
| Detektor: Dauerlast +50 W erkannt (new_pattern) | 2/3 | im Mittel nach 22,0 Tagen, Skala weekly+long_term, falsche Resets 0,0 je Fenster |

## Ohne Ereignis: Kontrolllauf über das ganze Fenster, Mittel über Cutover

| Variante | Gate offen mit Reset [%] | davon Einzeltag mit Reset [%] | Resets der Kontrolle je Fenster |
|---|---:|---:|---:|
| Detektor | 6,3 | 5,5 | 0,6 |

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
| 1,25 | 0,75 | 12,5 | 2,6 | 5/6 | 23,6 |  |
| 1,25 | 0,75 | 15 | 2,4 | 5/6 | 24,4 |  |
| 1,25 | 0,75 | 20 | 1,2 | 5/6 | 25,4 |  |
| 1,25 | 0,75 | 25 | 1,0 | 4/6 | 19,5 |  |
| 1,25 | 1 | 12,5 | 2,0 | 5/6 | 23,6 |  |
| 1,25 | 1 | 15 | 1,8 | 5/6 | 23,8 |  |
| 1,25 | 1 | 20 | 1,0 | 5/6 | 26,4 |  |
| 1,25 | 1 | 25 | 0,8 | 4/6 | 19,5 |  |
| 1,25 | 1,25 | 12,5 | 1,8 | 4/6 | 24,5 |  |
| 1,25 | 1,25 | 15 | 1,6 | 4/6 | 27,0 |  |
| 1,25 | 1,25 | 20 | 1,0 | 4/6 | 30,0 |  |
| 1,25 | 1,25 | 25 | 0,8 | 3/6 | 21,3 |  |
| 1,25 | 1,5 | 12,5 | 1,0 | 2/6 | 14,5 |  |
| 1,25 | 1,5 | 15 | 1,2 | 2/6 | 14,5 |  |
| 1,25 | 1,5 | 20 | 0,8 | 1/6 | 7,0 |  |
| 1,25 | 1,5 | 25 | 0,8 | 1/6 | 7,0 |  |
| 1,5 | 0,75 | 12,5 | 2,4 | 6/6 | 29,3 |  |
| 1,5 | 0,75 | 15 | 2,2 | 6/6 | 30,0 |  |
| 1,5 | 0,75 | 20 | 1,0 | 6/6 | 30,8 |  |
| 1,5 | 0,75 | 25 | 0,8 | 4/6 | 19,8 |  |
| 1,5 | 1 | 12,5 | 2,0 | 5/6 | 23,6 |  |
| 1,5 | 1 | 15 | 1,8 | 5/6 | 23,8 |  |
| 1,5 | 1 | 20 | 1,0 | 5/6 | 26,4 |  |
| 1,5 | 1 | 25 | 0,8 | 4/6 | 19,8 |  |
| 1,5 | 1,25 | 12,5 | 1,6 | 4/6 | 24,5 |  |
| 1,5 | 1,25 | 15 | 1,4 | 4/6 | 27,0 |  |
| 1,5 | 1,25 | 20 | 0,8 | 4/6 | 30,0 |  |
| 1,5 | 1,25 | 25 | 0,6 | 3/6 | 21,7 |  |
| 1,5 | 1,5 | 12,5 | 0,8 | 2/6 | 15,0 |  |
| 1,5 | 1,5 | 15 | 1,0 | 2/6 | 15,0 |  |
| 1,5 | 1,5 | 20 | 0,6 | 1/6 | 7,0 |  |
| 1,5 | 1,5 | 25 | 0,6 | 1/6 | 8,0 |  |
| 1,75 | 0,75 | 12,5 | 2,2 | 5/6 | 23,6 |  |
| 1,75 | 0,75 | 15 | 2,0 | 5/6 | 24,4 |  |
| 1,75 | 0,75 | 20 | 0,8 | 5/6 | 25,4 |  |
| 1,75 | 0,75 | 25 | 0,6 | 4/6 | 19,8 |  |
| 1,75 | 1 | 12,5 | 1,8 | 5/6 | 23,6 |  |
| 1,75 | 1 | 15 | 1,6 | 5/6 | 23,8 |  |
| 1,75 | 1 | 20 | 0,8 | 5/6 | 26,4 |  |
| 1,75 | 1 | 25 | 0,6 | 4/6 | 19,8 |  |
| 1,75 | 1,25 | 12,5 | 1,6 | 4/6 | 24,5 |  |
| 1,75 | 1,25 | 15 | 1,4 | 4/6 | 27,0 |  |
| 1,75 | 1,25 | 20 | 0,8 | 4/6 | 30,0 |  |
| 1,75 | 1,25 | 25 | 0,6 | 3/6 | 21,7 |  |
| 1,75 | 1,5 | 12,5 | 0,8 | 2/6 | 15,0 |  |
| 1,75 | 1,5 | 15 | 1,0 | 2/6 | 15,0 |  |
| 1,75 | 1,5 | 20 | 0,6 | 1/6 | 7,0 |  |
| 1,75 | 1,5 | 25 | 0,6 | 1/6 | 8,0 |  |
| 2 | 0,75 | 12,5 | 2,0 | 5/6 | 23,6 |  |
| 2 | 0,75 | 15 | 1,8 | 5/6 | 24,4 |  |
| 2 | 0,75 | 20 | 0,6 | 5/6 | 25,4 |  |
| 2 | 0,75 | 25 | 0,4 | 4/6 | 19,8 |  |
| 2 | 1 | 12,5 | 1,6 | 5/6 | 23,6 |  |
| 2 | 1 | 15 | 1,4 | 5/6 | 23,8 |  |
| 2 | 1 | 20 | 0,6 | 5/6 | 26,4 |  |
| 2 | 1 | 25 | 0,4 | 4/6 | 19,8 |  |
| 2 | 1,25 | 12,5 | 1,4 | 4/6 | 24,5 |  |
| 2 | 1,25 | 15 | 1,2 | 4/6 | 27,0 |  |
| 2 | 1,25 | 20 | 0,6 | 4/6 | 30,0 |  |
| 2 | 1,25 | 25 | 0,4 | 3/6 | 21,7 |  |
| 2 | 1,5 | 12,5 | 0,6 | 2/6 | 15,0 |  |
| 2 | 1,5 | 15 | 0,8 | 2/6 | 15,0 |  |
| 2 | 1,5 | 20 | 0,4 | 1/6 | 7,0 |  |
| 2 | 1,5 | 25 | 0,4 | 1/6 | 8,0 |  |
| 2,5 | 0,75 | 12,5 | 1,8 | 5/6 | 23,6 |  |
| 2,5 | 0,75 | 15 | 1,6 | 5/6 | 24,4 |  |
| 2,5 | 0,75 | 20 | 0,4 | 5/6 | 25,4 | ja |
| 2,5 | 0,75 | 25 | 0,2 | 4/6 | 19,8 |  |
| 2,5 | 1 | 12,5 | 1,4 | 5/6 | 23,6 |  |
| 2,5 | 1 | 15 | 1,2 | 5/6 | 23,8 |  |
| 2,5 | 1 | 20 | 0,4 | 5/6 | 26,4 |  |
| 2,5 | 1 | 25 | 0,2 | 4/6 | 19,8 |  |
| 2,5 | 1,25 | 12,5 | 1,2 | 4/6 | 24,5 |  |
| 2,5 | 1,25 | 15 | 1,0 | 4/6 | 27,0 |  |
| 2,5 | 1,25 | 20 | 0,4 | 4/6 | 30,0 |  |
| 2,5 | 1,25 | 25 | 0,2 | 3/6 | 21,7 |  |
| 2,5 | 1,5 | 12,5 | 0,4 | 2/6 | 15,0 |  |
| 2,5 | 1,5 | 15 | 0,6 | 2/6 | 15,0 |  |
| 2,5 | 1,5 | 20 | 0,2 | 1/6 | 7,0 |  |
| 2,5 | 1,5 | 25 | 0,2 | 1/6 | 8,0 |  |
| 2,75 | 0,75 | 12,5 | 1,8 | 5/6 | 23,6 |  |
| 2,75 | 0,75 | 15 | 1,6 | 5/6 | 24,4 |  |
| 2,75 | 0,75 | 20 | 0,4 | 5/6 | 25,4 |  |
| 2,75 | 0,75 | 25 | 0,2 | 4/6 | 19,8 |  |
| 2,75 | 1 | 12,5 | 1,4 | 5/6 | 23,6 |  |
| 2,75 | 1 | 15 | 1,2 | 5/6 | 23,8 |  |
| 2,75 | 1 | 20 | 0,4 | 5/6 | 26,4 |  |
| 2,75 | 1 | 25 | 0,2 | 4/6 | 19,8 |  |
| 2,75 | 1,25 | 12,5 | 1,2 | 4/6 | 24,5 |  |
| 2,75 | 1,25 | 15 | 1,0 | 4/6 | 27,0 |  |
| 2,75 | 1,25 | 20 | 0,4 | 4/6 | 30,0 |  |
| 2,75 | 1,25 | 25 | 0,2 | 3/6 | 21,7 |  |
| 2,75 | 1,5 | 12,5 | 0,4 | 2/6 | 15,0 |  |
| 2,75 | 1,5 | 15 | 0,6 | 2/6 | 15,0 |  |
| 2,75 | 1,5 | 20 | 0,2 | 1/6 | 7,0 |  |
| 2,75 | 1,5 | 25 | 0,2 | 1/6 | 8,0 |  |

## Erkennung je Ereignis im Betrieb mit Reset, Tag seit Cutover je Cutover

| Variante | Ereignis | 2013-10-15 (Dauerlast nicht gezählt) | 2014-02-12 | 2014-06-12 | 2014-10-10 (Dauerlast nicht gezählt) | 2015-02-07 | Mittel erkannter | erkannt | falsche Resets je Fenster | Skala bei Erkennung |
|---|---|---:|---:|---:|---:|---:|---:|---|---:|---|
| Detektor | Dauerlast +30 W | - | - | - | 21 | - | - | 0/3 | 0,2 |  |
| Detektor | Dauerlast +50 W | - | 22 | - | 11 | 22 | 22,0 | 2/3 | 0,0 | weekly+long_term |
| Detektor | Dauerlast +100 W | 15 | 21 | 24 | 9 | 15 | 20,0 | 3/3 | 0,0 | weekly+long_term |
| Detektor | Dauerlast +200 W | 5 | 17 | 21 | 6 | 11 | 16,3 | 3/3 | 0,0 | weekly+long_term |
| Detektor | Dauerlast −100 W | 27 | 34 | - | 31 | 34 | 34,0 | 2/3 | 0,0 | weekly+long_term |
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
