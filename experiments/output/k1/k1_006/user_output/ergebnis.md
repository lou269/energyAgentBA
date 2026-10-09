# K1 Schwellen der Erkennung, Lauf k1_006

## Kurzfassung

- Gewählt: weekly / long_term % = 1,02 / 14,20 bei Anteil 0,20 (aktuelle Config 1,02 / 14,20)
- Einzeltag-Schwelle = 2,3 bei 4,9 % Alarmtagen (Ziel 5 %, aktuelle Config 2,3)
- 4 Resets auf validation, 2,03 je Jahr (Grenze höchstens 4)

## Setup

- Zeitraum: 2014-04-02 bis 2016-03-19 (718 Tage, validation), durchgehend mit Reset, Historie davor aus train
- Regel: weekly und long_term halten ohne Reset an gleich vielen Tagen an (6 von 7 Tagen über der Schwelle). Gewählt wird der größte Anteil mit höchstens 4 Resets
- Einzeltag-Schwelle: ein Wert für daily und weekday: der größte Score des Tages schlägt an dem Anteil der 718 Tage an, der am nächsten bei 5 % liegt. Scores aus dem durchgehenden Lauf mit Reset und den gewählten Niveau-Schwellen
- Kette: Analyse, Streak, Einordnung nach Regel und Reset wie im Zyklus, ohne Prognose und ohne LLM
- Diagnose: Katalog-Arten an 11 Cutovern im Abstand von 60 Tagen, je 40 Tage davor und 60 danach. Nicht Teil der Wahl
- Commit: 9ef1fd9 (mit lokalen Änderungen)

## Schwellen je Anteil anhaltender Tage und Resets im durchgehenden Lauf

| Anteil der Tage, an denen eine Skala anhält (ohne Reset) | Schwelle weekly | Schwelle long_term [%] | Resets auf validation | Resets je Jahr | gewählt |
|---:|---:|---:|---:|---:|---|
| 0,0 | 2,5 | 25,5 | 0 | 0,0 |  |
| 0,0 | 2,3 | 23,2 | 0 | 0,0 |  |
| 0,0 | 2,1 | 22,4 | 0 | 0,0 |  |
| 0,1 | 1,9 | 21,8 | 1 | 0,5 |  |
| 0,1 | 1,7 | 21,2 | 1 | 0,5 |  |
| 0,1 | 1,6 | 20,1 | 1 | 0,5 |  |
| 0,1 | 1,5 | 19,2 | 1 | 0,5 |  |
| 0,1 | 1,4 | 18,4 | 1 | 0,5 |  |
| 0,1 | 1,4 | 17,3 | 2 | 1,0 |  |
| 0,1 | 1,4 | 17,3 | 3 | 1,5 |  |
| 0,1 | 1,3 | 16,7 | 3 | 1,5 |  |
| 0,1 | 1,2 | 16,1 | 3 | 1,5 |  |
| 0,1 | 1,2 | 15,8 | 3 | 1,5 |  |
| 0,1 | 1,2 | 15,3 | 4 | 2,0 |  |
| 0,2 | 1,1 | 15,1 | 4 | 2,0 |  |
| 0,2 | 1,1 | 14,9 | 4 | 2,0 |  |
| 0,2 | 1,0 | 14,7 | 4 | 2,0 |  |
| 0,2 | 1,0 | 14,5 | 4 | 2,0 |  |
| 0,2 | 1,0 | 14,2 | 4 | 2,0 | ja |
| 0,2 | 1,0 | 13,7 | 5 | 2,5 |  |
| 0,2 | 1,0 | 13,0 | 5 | 2,5 |  |
| 0,2 | 0,9 | 12,9 | 5 | 2,5 |  |
| 0,2 | 0,9 | 12,5 | 5 | 2,5 |  |
| 0,2 | 0,9 | 12,0 | 6 | 3,1 |  |
| 0,3 | 0,8 | 11,7 | 6 | 3,1 |  |
| 0,3 | 0,8 | 11,3 | 6 | 3,1 |  |
| 0,3 | 0,8 | 11,1 | 6 | 3,1 |  |
| 0,3 | 0,7 | 10,9 | 6 | 3,1 |  |
| 0,3 | 0,7 | 10,6 | 6 | 3,1 |  |

## Resets mit den gewählten Schwellen

| Reset am |
|---|
| 19.06.2014 |
| 13.10.2014 |
| 13.12.2014 |
| 02.08.2015 |

## Einzeltag-Schwelle und Anteil der Tage mit Alarm im durchgehenden Lauf

| Einzeltag-Schwelle (Score) | Tage mit Alarm [%] | gewählt |
|---:|---:|---|
| 2,0 | 7,7 |  |
| 2,1 | 6,7 |  |
| 2,2 | 5,4 |  |
| 2,3 | 4,9 | ja |
| 2,4 | 4,3 |  |
| 2,5 | 3,5 |  |
| 2,6 | 3,2 |  |
| 2,7 | 3,1 |  |
| 2,8 | 2,9 |  |
| 2,9 | 2,9 |  |
| 3,0 | 2,7 |  |
| 3,1 | 2,7 |  |
| 3,2 | 2,5 |  |
| 3,3 | 2,1 |  |
| 3,4 | 2,0 |  |
| 3,5 | 1,5 |  |
| 3,6 | 1,4 |  |
| 3,7 | 1,4 |  |
| 3,8 | 1,4 |  |
| 3,9 | 1,4 |  |
| 4,0 | 1,4 |  |
| 4,1 | 1,4 |  |
| 4,2 | 1,3 |  |
| 4,3 | 1,3 |  |
| 4,4 | 1,3 |  |
| 4,5 | 1,3 |  |
| 4,6 | 1,3 |  |
| 4,7 | 1,1 |  |
| 4,8 | 1,1 |  |
| 4,9 | 1,1 |  |
| 5,0 | 1,1 |  |

## Was der Detektor mit eingebauten Ereignissen macht, an 11 Zeitpunkten in validation (Ansicht, nicht zur Wahl). Reset wegen des Ereignisses: so oft setzt das System zurück, und zwar früher als zur selben Zeit ohne Ereignis. Tage bis zum Reset: Median ab dem Ereignistag. Ereignistag gemeldet: der Tag selbst ist auffällig, nur für Spitze und ganzen Tag gedacht

| eingebautes Ereignis | soll | neue Schwellen: Reset wegen des Ereignisses | neue Schwellen: Tage bis zum Reset | neue Schwellen: Ereignistag gemeldet | bisherige Schwellen: Reset wegen des Ereignisses | bisherige Schwellen: Tage bis zum Reset | bisherige Schwellen: Ereignistag gemeldet |
|---|---|---|---:|---|---|---:|---|
| keine Änderung | still bleiben | 0/11 | - | 0/11 | 0/11 | - | 0/11 |
| Sprung +20 % | erkennen (Reset) | 6/11 | 18,5 | 3/11 | 6/11 | 18,5 | 3/11 |
| Rampe über 28 Tage +20 % | erkennen (Reset) | 7/11 | 32,0 | 0/11 | 7/11 | 32,0 | 0/11 |
| Rampe über 28 Tage −20 % | erkennen (Reset) | 7/11 | 31,0 | 0/11 | 7/11 | 31,0 | 0/11 |
| Rampe über 56 Tage +20 % | still bleiben | 5/11 | 34,0 | 0/11 | 5/11 | 34,0 | 0/11 |
| Rampe über 56 Tage −20 % | still bleiben | 5/11 | 35,0 | 0/11 | 5/11 | 35,0 | 0/11 |
| Spitze +670 W über 6 h | Alarm am Ereignistag | 2/11 | 19,0 | 8/11 | 2/11 | 19,0 | 8/11 |
| ganzer Tag +190 W | Alarm am Ereignistag | 2/11 | 19,0 | 8/11 | 2/11 | 19,0 | 8/11 |

## Hinweise

- Gezählt wird jeder Reset im durchgehenden Lauf, auch an echten Wechseln (Urlaub, Saison). Die Grenze ist eine Setzung über die Blindzeit nach einem Reset
- Der Anteil anhaltender Tage legt nur das Verhältnis der beiden Schwellen fest. Er wird ohne Reset auf 718 Tagen bestimmt, gezählt wird mit Reset
- Diagnose: Die Zeitpunkte liegen in den Kalibrierdaten, die Zahlen sind eine Ansicht, kein Beleg. Bei 11 Zeitpunkten verschiebt schon ein einzelner Fall die Anteile deutlich
- Die gewählten Schwellen (weekly_streak_threshold, long_term_streak_threshold_pct, unusual_threshold) sind in NumericalAnalysisConfig zu übernehmen, gerundet
