# K2 Schwellen der Anomalieerkennung, Lauf k2_017

## Setup

- Cutover: 2013-10-15, 2014-02-12, 2014-06-12, 2014-10-10, 2015-02-07
- Zeitraum je Cutover: Kaltstart, 60 Tage Überwachung vor dem Cutover, 60 Tage danach
- Ereignisse ab Cutover: proportional ×1,3, proportional ×0,7, Rampe über 28 Tage auf ×1,3, Rampe über 28 Tage auf ×0,7, Rampe über 56 Tage auf ×1,3, Rampe über 56 Tage auf ×0,7, Einzeltag-Spitze +1000 W über 3 h, Einzeltag-Spitze +1000 W über 6 h, jeweils neben dem unveränderten Kontrolllauf
- Soll: neues Muster, wenn sich das Niveau in 28 Tagen um mindestens 20 % ändert (proportional ×1,3, proportional ×0,7, Rampe über 28 Tage auf ×1,3, Rampe über 28 Tage auf ×0,7), nicht bei langsamerer Änderung (Rampe über 56 Tage auf ×1,3, Rampe über 56 Tage auf ×0,7)
- Modi: ohne Reset = nur Detektor, darauf werden Einzeltag-Schwelle und Streak-Empfindlichkeit bestimmt (Kontrolle und proportional ×1,3, proportional ×0,7, Rampe über 28 Tage auf ×1,3, Rampe über 28 Tage auf ×0,7, Rampe über 56 Tage auf ×1,3, Rampe über 56 Tage auf ×0,7). Mit Reset = Betrieb mit Regel wie SYS2, alle Ereignisse
- Detektor: Referenz Rolling 60 vor dem Beobachtungsfenster, Median/MAD für daily und weekday
- Schwellen im Lauf (Einzeltag / Streak weekday / weekly / long_term %): 3,2 / 1,25 / 1 / 25
- Commit: 1590933 (mit lokalen Änderungen)

## Kennzahlen

| Kennzahl | Wert | Bezug |
|---|---|---|
| Einzeltag-Schwelle für 5 % Alarme in der Kontrolle | 3,2 | gilt im Lauf mit Reset |
| Streak-Schwellen (weekday / weekly / long_term %), Fehlalarm-Budget und früheste Erkennung | 1,25 / 1 / 25 | gilt im Lauf mit Reset |
| Detektor: Gate offen ohne Ereignis, mit Reset [%] | 8,3 | Einzeltag-Alarme und Drift zusammen |
| Detektor: falsche Resets im Betrieb je Fenster, alle Ereignisse | 0,3 | jeder Reset ab Tag 1 außer dem Treffer, bei langsamen Rampen und Spitzen jeder. Nicht gezählt im Trefferfenster eines echten Trends |
| Detektor: Resets im Kontrolllauf ohne Ereignis, je Fenster | 1,0 | Grundrate, zählt nicht als falsch. Ohne Reset (gewählter Punkt) 0,4, Budget 0,5 |
| Detektor: Einzeltag-Spitze +1000 W über 3 h erkannt (Alarm am Ereignistag) | 2/5 | Skala daily, falsche Resets 0,4 je Fenster |
| Detektor: Einzeltag-Spitze +1000 W über 6 h erkannt (Alarm am Ereignistag) | 3/5 | Skala daily, weekday, falsche Resets 0,4 je Fenster |
| Detektor: Rampe über 28 Tage auf ×1,3 erkannt (new_pattern) | 3/5 | im Mittel nach 21,0 Tagen, Skala weekly+long_term, falsche Resets 0,2 je Fenster |
| Detektor: Rampe über 28 Tage auf ×0,7 erkannt (new_pattern) | 2/5 | im Mittel nach 23,0 Tagen, Skala weekday+weekly, falsche Resets 0,4 je Fenster |
| Detektor: Rampe über 56 Tage auf ×1,3 feuert (new_pattern) | 2/5 | im Mittel nach 37,0 Tagen, Skala weekday+weekly, weekly+long_term, falsche Resets 0,4 je Fenster |
| Detektor: Rampe über 56 Tage auf ×0,7 feuert (new_pattern) | 1/5 | im Mittel nach 58,0 Tagen, Skala weekday+weekly, falsche Resets 0,2 je Fenster |
| Detektor: proportional ×1,3 erkannt (new_pattern) | 4/5 | im Mittel nach 10,5 Tagen, Skala weekday+weekly, weekly+long_term, falsche Resets 0,2 je Fenster |
| Detektor: proportional ×0,7 erkannt (new_pattern) | 3/5 | im Mittel nach 19,7 Tagen, Skala weekday+weekly, weekly+long_term, falsche Resets 0,6 je Fenster |

## Ohne Ereignis: Kontrolllauf über das ganze Fenster, Mittel über Cutover

| Variante | Gate offen mit Reset [%] | davon Einzeltag mit Reset [%] | Resets der Kontrolle je Fenster |
|---|---:|---:|---:|
| Detektor | 8,3 | 7,1 | 1,0 |

## Einzeltag-Schwelle: ein Wert für daily und weekday, Alarmrate der Kontrolle je Cutover, ohne Reset

| Cutover | Schwelle (Score) | Einzeltag-Alarme Kontrolle [%] |
|---|---:|---:|
| 2013-10-15 | 3,2 | 10,7 |
| 2014-02-12 | 3,2 | 3,3 |
| 2014-06-12 | 3,2 | 0,8 |
| 2014-10-10 | 3,2 | 4,1 |
| 2015-02-07 | 3,2 | 6,6 |

## Streak-Schwellen: Raster und gewählter Punkt, ohne Reset, Mittel über Cutover

| Streak weekday | Streak weekly | Streak long_term [%] | falsche new_pattern je Fenster | Eingriffe erkannt | Erkennungstag im Mittel | feuert bei langsamer Rampe | gewählt |
|---|---|---|---:|---|---:|---|---|
| 1,25 | 0,75 | 12,5 | 1,1 | 13/20 | 15,7 | 8/10 |  |
| 1,25 | 0,75 | 15 | 1,1 | 13/20 | 13,5 | 7/10 |  |
| 1,25 | 0,75 | 20 | 0,7 | 14/20 | 15,5 | 6/10 |  |
| 1,25 | 0,75 | 25 | 0,5 | 11/20 | 17,1 | 3/10 |  |
| 1,25 | 1 | 12,5 | 1,0 | 13/20 | 16,1 | 6/10 |  |
| 1,25 | 1 | 15 | 1,1 | 13/20 | 13,8 | 6/10 |  |
| 1,25 | 1 | 20 | 0,7 | 14/20 | 15,9 | 4/10 |  |
| 1,25 | 1 | 25 | 0,4 | 11/20 | 17,3 | 3/10 | ja |
| 1,25 | 1,25 | 12,5 | 0,9 | 10/20 | 16,1 | 5/10 |  |
| 1,25 | 1,25 | 15 | 0,9 | 10/20 | 13,1 | 6/10 |  |
| 1,25 | 1,25 | 20 | 0,6 | 10/20 | 15,8 | 4/10 |  |
| 1,25 | 1,25 | 25 | 0,3 | 8/20 | 16,4 | 3/10 |  |
| 1,25 | 1,5 | 12,5 | 0,7 | 7/20 | 14,6 | 5/10 |  |
| 1,25 | 1,5 | 15 | 0,6 | 8/20 | 12,0 | 6/10 |  |
| 1,25 | 1,5 | 20 | 0,4 | 8/20 | 14,0 | 4/10 |  |
| 1,25 | 1,5 | 25 | 0,3 | 6/20 | 14,0 | 3/10 |  |
| 1,5 | 0,75 | 12,5 | 1,0 | 11/20 | 14,9 | 8/10 |  |
| 1,5 | 0,75 | 15 | 1,0 | 11/20 | 11,9 | 7/10 |  |
| 1,5 | 0,75 | 20 | 0,6 | 11/20 | 13,5 | 6/10 |  |
| 1,5 | 0,75 | 25 | 0,5 | 8/20 | 15,0 | 3/10 |  |
| 1,5 | 1 | 12,5 | 0,9 | 11/20 | 15,2 | 6/10 |  |
| 1,5 | 1 | 15 | 1,0 | 11/20 | 12,2 | 6/10 |  |
| 1,5 | 1 | 20 | 0,6 | 11/20 | 13,8 | 4/10 |  |
| 1,5 | 1 | 25 | 0,3 | 8/20 | 15,0 | 3/10 |  |
| 1,5 | 1,25 | 12,5 | 0,8 | 8/20 | 14,8 | 5/10 |  |
| 1,5 | 1,25 | 15 | 0,9 | 8/20 | 10,6 | 6/10 |  |
| 1,5 | 1,25 | 20 | 0,5 | 7/20 | 12,4 | 4/10 |  |
| 1,5 | 1,25 | 25 | 0,3 | 5/20 | 12,0 | 3/10 |  |
| 1,5 | 1,5 | 12,5 | 0,6 | 6/20 | 14,0 | 5/10 |  |
| 1,5 | 1,5 | 15 | 0,6 | 6/20 | 8,3 | 6/10 |  |
| 1,5 | 1,5 | 20 | 0,3 | 6/20 | 11,0 | 4/10 |  |
| 1,5 | 1,5 | 25 | 0,2 | 4/20 | 9,5 | 3/10 |  |
| 1,75 | 0,75 | 12,5 | 0,9 | 11/20 | 15,3 | 8/10 |  |
| 1,75 | 0,75 | 15 | 1,0 | 11/20 | 12,5 | 7/10 |  |
| 1,75 | 0,75 | 20 | 0,5 | 10/20 | 13,4 | 6/10 |  |
| 1,75 | 0,75 | 25 | 0,4 | 7/20 | 15,3 | 3/10 |  |
| 1,75 | 1 | 12,5 | 0,9 | 11/20 | 15,5 | 6/10 |  |
| 1,75 | 1 | 15 | 0,9 | 11/20 | 12,8 | 6/10 |  |
| 1,75 | 1 | 20 | 0,5 | 10/20 | 13,7 | 4/10 |  |
| 1,75 | 1 | 25 | 0,3 | 7/20 | 15,3 | 3/10 |  |
| 1,75 | 1,25 | 12,5 | 0,8 | 8/20 | 15,2 | 5/10 |  |
| 1,75 | 1,25 | 15 | 0,9 | 8/20 | 11,5 | 6/10 |  |
| 1,75 | 1,25 | 20 | 0,5 | 6/20 | 12,0 | 4/10 |  |
| 1,75 | 1,25 | 25 | 0,3 | 4/20 | 11,8 | 3/10 |  |
| 1,75 | 1,5 | 12,5 | 0,6 | 6/20 | 14,7 | 5/10 |  |
| 1,75 | 1,5 | 15 | 0,6 | 5/20 | 6,2 | 6/10 |  |
| 1,75 | 1,5 | 20 | 0,3 | 5/20 | 10,2 | 4/10 |  |
| 1,75 | 1,5 | 25 | 0,2 | 3/20 | 8,3 | 3/10 |  |
| 2 | 0,75 | 12,5 | 0,9 | 11/20 | 15,3 | 8/10 |  |
| 2 | 0,75 | 15 | 0,9 | 11/20 | 12,5 | 7/10 |  |
| 2 | 0,75 | 20 | 0,5 | 10/20 | 13,4 | 6/10 |  |
| 2 | 0,75 | 25 | 0,3 | 7/20 | 15,3 | 2/10 |  |
| 2 | 1 | 12,5 | 0,8 | 11/20 | 15,5 | 6/10 |  |
| 2 | 1 | 15 | 0,9 | 11/20 | 12,8 | 6/10 |  |
| 2 | 1 | 20 | 0,5 | 10/20 | 13,7 | 4/10 |  |
| 2 | 1 | 25 | 0,2 | 7/20 | 15,3 | 2/10 |  |
| 2 | 1,25 | 12,5 | 0,7 | 8/20 | 15,2 | 5/10 |  |
| 2 | 1,25 | 15 | 0,8 | 8/20 | 11,5 | 6/10 |  |
| 2 | 1,25 | 20 | 0,4 | 6/20 | 12,0 | 4/10 |  |
| 2 | 1,25 | 25 | 0,2 | 4/20 | 11,8 | 2/10 |  |
| 2 | 1,5 | 12,5 | 0,5 | 6/20 | 14,7 | 5/10 |  |
| 2 | 1,5 | 15 | 0,5 | 5/20 | 6,2 | 6/10 |  |
| 2 | 1,5 | 20 | 0,3 | 5/20 | 10,2 | 4/10 |  |
| 2 | 1,5 | 25 | 0,1 | 3/20 | 8,3 | 2/10 |  |
| 2,5 | 0,75 | 12,5 | 0,9 | 11/20 | 15,8 | 8/10 |  |
| 2,5 | 0,75 | 15 | 0,9 | 11/20 | 13,3 | 7/10 |  |
| 2,5 | 0,75 | 20 | 0,5 | 10/20 | 14,4 | 6/10 |  |
| 2,5 | 0,75 | 25 | 0,3 | 6/20 | 17,0 | 2/10 |  |
| 2,5 | 1 | 12,5 | 0,8 | 11/20 | 16,1 | 6/10 |  |
| 2,5 | 1 | 15 | 0,9 | 11/20 | 13,5 | 6/10 |  |
| 2,5 | 1 | 20 | 0,5 | 10/20 | 14,7 | 4/10 |  |
| 2,5 | 1 | 25 | 0,2 | 6/20 | 17,0 | 2/10 |  |
| 2,5 | 1,25 | 12,5 | 0,7 | 8/20 | 16,0 | 5/10 |  |
| 2,5 | 1,25 | 15 | 0,8 | 8/20 | 12,5 | 6/10 |  |
| 2,5 | 1,25 | 20 | 0,4 | 6/20 | 13,7 | 4/10 |  |
| 2,5 | 1,25 | 25 | 0,2 | 3/20 | 14,0 | 2/10 |  |
| 2,5 | 1,5 | 12,5 | 0,5 | 6/20 | 15,7 | 5/10 |  |
| 2,5 | 1,5 | 15 | 0,5 | 5/20 | 7,8 | 6/10 |  |
| 2,5 | 1,5 | 20 | 0,3 | 5/20 | 12,2 | 4/10 |  |
| 2,5 | 1,5 | 25 | 0,1 | 2/20 | 10,0 | 2/10 |  |
| 2,75 | 0,75 | 12,5 | 0,9 | 11/20 | 15,8 | 8/10 |  |
| 2,75 | 0,75 | 15 | 0,9 | 11/20 | 13,3 | 7/10 |  |
| 2,75 | 0,75 | 20 | 0,5 | 10/20 | 14,4 | 6/10 |  |
| 2,75 | 0,75 | 25 | 0,3 | 6/20 | 17,0 | 2/10 |  |
| 2,75 | 1 | 12,5 | 0,8 | 11/20 | 16,1 | 6/10 |  |
| 2,75 | 1 | 15 | 0,9 | 11/20 | 13,5 | 6/10 |  |
| 2,75 | 1 | 20 | 0,5 | 10/20 | 14,7 | 4/10 |  |
| 2,75 | 1 | 25 | 0,2 | 6/20 | 17,0 | 2/10 |  |
| 2,75 | 1,25 | 12,5 | 0,7 | 8/20 | 16,0 | 5/10 |  |
| 2,75 | 1,25 | 15 | 0,8 | 8/20 | 12,5 | 6/10 |  |
| 2,75 | 1,25 | 20 | 0,4 | 6/20 | 13,7 | 4/10 |  |
| 2,75 | 1,25 | 25 | 0,2 | 3/20 | 14,0 | 2/10 |  |
| 2,75 | 1,5 | 12,5 | 0,5 | 6/20 | 15,7 | 5/10 |  |
| 2,75 | 1,5 | 15 | 0,5 | 5/20 | 7,8 | 6/10 |  |
| 2,75 | 1,5 | 20 | 0,3 | 5/20 | 12,2 | 4/10 |  |
| 2,75 | 1,5 | 25 | 0,1 | 2/20 | 10,0 | 2/10 |  |

## Erkennung je Ereignis im Betrieb mit Reset, Tag seit Cutover je Cutover

| Variante | Ereignis | 2013-10-15 | 2014-02-12 | 2014-06-12 | 2014-10-10 | 2015-02-07 | Mittel erkannter | erkannt | falsche Resets je Fenster | Skala bei Erkennung |
|---|---|---:|---:|---:|---:|---:|---:|---|---:|---|
| Detektor | proportional ×1,3 | 5 | - | 18 | 5 | 14 | 10,5 | 4/5 | 0,2 | weekday+weekly, weekly+long_term |
| Detektor | Rampe über 28 Tage auf ×1,3 | - | 23 | 18 | - | 22 | 21,0 | 3/5 | 0,2 | weekly+long_term |
| Detektor | Rampe über 56 Tage auf ×1,3 | - | - | 18 | 56 | - | 37,0 | 2/5 | 0,4 | weekday+weekly, weekly+long_term |
| Detektor | proportional ×0,7 | 19 | 16 | - | 24 | - | 19,7 | 3/5 | 0,6 | weekday+weekly, weekly+long_term |
| Detektor | Rampe über 28 Tage auf ×0,7 | 22 | - | - | 24 | - | 23,0 | 2/5 | 0,4 | weekday+weekly |
| Detektor | Rampe über 56 Tage auf ×0,7 | - | - | 58 | - | - | 58,0 | 1/5 | 0,2 | weekday+weekly |
| Detektor | Einzeltag-Spitze +1000 W über 3 h | 1 | - | - | 1 | - | 1,0 | 2/5 | 0,4 | daily |
| Detektor | Einzeltag-Spitze +1000 W über 6 h | 1 | 1 | - | 1 | - | 1,0 | 3/5 | 0,4 | daily, weekday |

## Hinweise

- Tag seit Cutover = Entscheidungstag: an Tag n meldet das System, eingeordnet ist dabei Tag n-1. Ab Cutover zählt deshalb erst ab Tag 1
- Einzeltag-Schwelle: das 95-%-Quantil des größten Scores von daily und weekday an den Kontrolltagen, ein Wert für beide. Streak-Schwellen: Raster, gewählt wird nach dem Fehlalarm-Budget (max_false_new_pattern), dann nach den meisten erkannten Eingriffen, dann nach wenig Feuern bei langsamen Rampen und früher Erkennung. Beides offline auf den Läufen ohne Reset
- Eingriff erkannt (ohne Reset): erster Beginn eines new_pattern (erster Tag einer Drift) zwischen Tag 1 und Tag 28 nach dem Cutover. Jeder andere Beginn ab Tag 1 ist falsch, außer er liegt im Trefferfenster eines echten Trends. Die Eingriffsreihe ist vor dem Cutover gleich der Kontrolle, dort zählt nur die Kontrolle
- langsame Rampe: jeder Beginn nach dem Cutover ist falsch (außer im Trefferfenster eines echten Trends), die Änderung bleibt in 28 Tagen unter 20 %
- falsche new_pattern je Fenster: Beginne aller Reihen des Fensters (Kontrolle und Eingriffe) außerhalb des Trefferfensters eines echten Trends (10 Tage vor bis 28 Tage nach dessen Beginn), gemittelt je Reihe. Auch ein Beginn in einem echten Einbruch zählt als falsch
- echte Trends: Abweichung des 5-Tage-Mittels vom Median der 28 Tage davor, ab 20 %, aus der Reihe ohne Detektor. Hält sie mindestens 10 Tage, ist es ein Trend, sonst ein Einbruch. Die Glättung verbreitert kurze Einbrüche um 1 bis 2 Tage, ein Einbruch nahe der Grenze kann deshalb als Trend gelten. Die Liste steht im Lauf unter raw/k2_events.csv
- Der Lauf mit Reset nutzt die gewählten Schwellen (Einzeltag und Streak), aus demselben Lauf. In NumericalAnalysisConfig übernehmen, gerundet
- erkannt, im Betrieb mit Reset: erster Reset (new_pattern) zwischen Tag 1 und Tag 28 nach dem Cutover. Einzeltag-Spitze = Alarm am Ereignistag, den der Kontrolllauf nicht hat. Langsame Rampen: ein Reset heißt feuert
- Resets der Kontrolle: Resets des Kontrolllaufs ohne Änderung, im Betrieb mit Reset, Mittel über alle Cutover. Die Grundrate (vor allem Jahreszeit), Vergleichsbasis für die falschen Resets
- falsche Resets: jeder Reset ab Tag 1 außer dem Treffer, außer im Trefferfenster eines echten Trends. Bei einer Spitze und einer langsamen Rampe zählt jeder
- Skala bei Erkennung: bei new_pattern die Skalen mit Streak, bei der Spitze die Einzeltag-Skala mit dem höchsten Score
