# Proaktiver Zyklus, Morgen-Ausblick, Lauf proactive_cycle_001

## Setup

- Modell: ministral-3:8b, Prompt outlook_v1, temperature 0,0
- Prognose: SYS1 ohne Adaption und ohne Aufruf 1, ohne Kalender
- Tage: 12 ab 2014-02-12 (Train-Split)
- Commit: 67b1e7c (mit lokalen Änderungen)

## Kernzahlen

| Kennzahl | Wert | Bezug |
|---|---|---|
| Gültige Antworten | 100,0 | % der Tage |
| Regelverstöße | 1 | Tage (Steuerung, State-fremde Zahlen und Daten) |
| Gerätenennungen | 6 | Tage, nur Hinweis |

## Ausblick je Tag

| Tag | Wochentag | Prognose [kWh] | üblich [kWh] | Abweichung [%] | Regelverstöße | Geräte |
|---|---|---:|---:|---:|---|---|
| 2014-02-12 | Mittwoch | 10,0 | 8,0 | 26,1 | number: 25 |  |
| 2014-02-13 | Donnerstag | 9,1 | 9,6 | -4,7 |  |  |
| 2014-02-14 | Freitag | 8,5 | 10,1 | -15,5 |  |  |
| 2014-02-15 | Samstag | 9,5 | 8,9 | 6,2 |  | heizung |
| 2014-02-16 | Sonntag | 9,1 | 8,1 | 12,1 |  | heizung |
| 2014-02-17 | Montag | 9,0 | 7,2 | 24,8 |  | heizung |
| 2014-02-18 | Dienstag | 9,1 | 9,6 | -6,1 |  |  |
| 2014-02-19 | Mittwoch | 8,2 | 8,7 | -5,0 |  | heizung |
| 2014-02-20 | Donnerstag | 7,9 | 9,2 | -13,8 |  |  |
| 2014-02-21 | Freitag | 6,0 | 10,1 | -40,1 |  |  |
| 2014-02-22 | Samstag | 5,6 | 8,8 | -36,3 |  | heizung |
| 2014-02-23 | Sonntag | 6,4 | 8,7 | -27,0 |  | heizung |

## Hinweise

- Gemessen wird nur der Text gegen den State. Eine Eintreffquote gegen die Ist-Werte misst die Prognose und nicht das LLM, sie fehlt bewusst.
- Erklärungsbewertung (verständlich, Empfehlung sinnvoll, Prognose sinnvoll genutzt): verblindeter Export in outlook_ratings_template.csv.
- Die Prognose enthält keine Wirkung der Adaption, der Zyklus läuft ohne Aufruf 1.

## Anhang

### Antworten je Tag

**2014-02-12, Mittwoch**: Prognose 10,0 kWh, üblich 8,0 kWh, Abweichung 26,1 %

- Erklärung: Heute ist mit etwa **25 % mehr Strom** als an einem durchschnittlichen Mittwoch zu rechnen – das entspricht rund **10 Kilowattstunden**.
- Empfehlung: Möglicherweise verbrauchen heute mehr Personen Strom, z. B. durch längeres Arbeiten oder Lernen im Haushalt. Auch Gäste oder ungewöhnlich kaltes Wetter könnten eine Rolle spielen.
- Unsicherheit: Der Wert ist eine Schätzung für den heutigen Tag und die genaue Ursache bleibt unklar.
- Regelverstöße: number: 25

**2014-02-13, Donnerstag**: Prognose 9,1 kWh, üblich 9,6 kWh, Abweichung -4,7 %

- Erklärung: Heute ist mit etwa **5 % weniger** Strom als sonst an einem Donnerstag zu rechnen – das entspricht rund **9,1 Kilowattstunden**.
- Empfehlung: Vielleicht war gestern etwas weniger Heizbedarf oder jemand hat länger im Homeoffice gearbeitet. Sie könnten überlegen, ob heute ungewöhnlich viele Menschen zu Hause sind oder ob die Kälte nachgelassen hat.
- Unsicherheit: Der Wert ist eine Schätzung für den ganzen Tag und kann je nach Verhalten abweichen.

**2014-02-14, Freitag**: Prognose 8,5 kWh, üblich 10,1 kWh, Abweichung -15,5 %

- Erklärung: Heute ist mit etwa **15 % weniger Strom** als sonst an einem Freitag zu rechnen – das entspricht rund **8,5 Kilowattstunden**. Das könnte auf einen etwas ruhigeren Tag hindeuten.
- Empfehlung: Vielleicht sind heute weniger Menschen im Haushalt oder es gibt weniger Aktivitäten wie Kochen oder Heizen. Denken Sie daran, ob jemand länger unterwegs ist oder ob die Außentemperaturen ungewöhnlich mild waren – das könnte den Unterschied ausmachen.
- Unsicherheit: Der Wert ist eine Schätzung für den Tag und die genaue Ursache bleibt unklar.

**2014-02-15, Samstag**: Prognose 9,5 kWh, üblich 8,9 kWh, Abweichung 6,2 %

- Erklärung: Heute ist mit etwa **6 % mehr** Strom als sonst an einem Samstag zu rechnen – das entspricht rund **9,5 Kilowattstunden**.
- Empfehlung: Möglicherweise war gestern ein kühlerer Tag oder es gab längeres Lichtnutzung am Abend. Vielleicht waren auch Gäste da oder die Heizung lief länger als sonst.
- Unsicherheit: Der Wert ist eine Schätzung für den heutigen Tag, und der genaue Grund bleibt unklar.
- Geräte genannt: heizung

**2014-02-16, Sonntag**: Prognose 9,1 kWh, üblich 8,1 kWh, Abweichung 12,1 %

- Erklärung: Heute wird etwas mehr Strom als sonst an einem Sonntag verbraucht, etwa 12 % mehr.
- Empfehlung: Vielleicht waren heute Gäste da oder Sie haben länger zu Hause verbracht – das könnte den höheren Verbrauch erklären. Auch kälteres Wetter im Februar kann den Bedarf erhöhen, besonders wenn Heizung oder Warmwasser häufiger genutzt wurden.
- Unsicherheit: Der Wert ist eine Schätzung für den heutigen Tag und die genaue Ursache bleibt unklar.
- Geräte genannt: heizung

**2014-02-17, Montag**: Prognose 9,0 kWh, üblich 7,2 kWh, Abweichung 24,8 %

- Erklärung: Heute ist mit etwa **25 % mehr Strom** als an einem durchschnittlichen Montag zu rechnen – das entspricht rund **9 Kilowattstunden**. Das sind etwa so viel wie ein ganzer Tag mit zusätzlicher Heizung oder längeren Gerätezeiten, zum Beispiel durch Gäste oder längeres Arbeiten im Homeoffice.
- Empfehlung: Überlegen Sie, ob heute ungewöhnlich viele Menschen zu Hause sind oder ob jemand länger als sonst arbeitet. Auch kälteres Wetter oder längere Beleuchtungszeiten könnten den Unterschied machen. Vielleicht war gestern weniger Strom verbraucht worden und der Verbrauch gleicht sich heute aus?
- Unsicherheit: Der Wert ist eine Schätzung für den heutigen Tag, und die genaue Ursache bleibt unklar.
- Geräte genannt: heizung

**2014-02-18, Dienstag**: Prognose 9,1 kWh, üblich 9,6 kWh, Abweichung -6,1 %

- Erklärung: Heute ist mit etwa **6 % weniger** Strom als sonst an einem Dienstag zu rechnen – das entspricht rund **9,1 Kilowattstunden**.
- Empfehlung: Vielleicht war gestern etwas weniger Heizbedarf oder jemand hat länger im Homeoffice gearbeitet. Sie könnten überlegen, ob heute ungewöhnlich viele Menschen zu Hause sind oder ob die Kälte nachgelassen hat.
- Unsicherheit: Der Wert ist eine Schätzung für den ganzen Tag und kann abweichen.

**2014-02-19, Mittwoch**: Prognose 8,2 kWh, üblich 8,7 kWh, Abweichung -5,0 %

- Erklärung: Heute Mittwoch wird etwas weniger Strom verbraucht als sonst an einem Mittwoch – etwa fünf Prozent weniger.
- Empfehlung: Vielleicht sind heute weniger Menschen zu Hause oder es ist wärmer als üblich. Sie könnten überlegen, ob jemand im Urlaub ist oder die Heizung anders eingestellt wurde.
- Unsicherheit: Der Wert ist eine Schätzung für den heutigen Tag und die genaue Ursache bleibt unklar.
- Geräte genannt: heizung

**2014-02-20, Donnerstag**: Prognose 7,9 kWh, üblich 9,2 kWh, Abweichung -13,8 %

- Erklärung: Heute ist mit etwa **14 % weniger** Stromverbrauch als an einem typischen Donnerstag zu rechnen – das entspricht rund **7,9 kWh**. Das liegt im Bereich einer etwas ruhigeren Woche.
- Empfehlung: Möglicherweise sind heute weniger Menschen zu Hause oder es wurde weniger geheizt. Vielleicht war die Nacht milder oder jemand hat länger gearbeitet als sonst. Sie könnten überlegen, ob sich der Alltag heute anders gestaltet hat – etwa durch Abwesenheit oder kürzere Aufenthalte im Haus.
- Unsicherheit: Der Wert ist eine Schätzung für den Tag und die genaue Ursache bleibt unklar.

**2014-02-21, Freitag**: Prognose 6,0 kWh, üblich 10,1 kWh, Abweichung -40,1 %

- Erklärung: Heute ist mit etwa **6 kWh** deutlich weniger Strom als sonst an einem Freitag zu erwarten – das sind rund **40 % weniger**.
- Empfehlung: Vielleicht war der Wochenendeffekt stärker als üblich: Vielleicht waren mehr Menschen unterwegs oder es gab weniger Heizbedarf durch milderes Wetter. Sie könnten überlegen, ob heute ungewöhnlich viele Personen im Haushalt waren oder ob die Außentemperaturen höher lagen als sonst.
- Unsicherheit: Die Schätzung für heute ist ein Wert aus der Vergangenheit und kann abweichen; der genaue Grund bleibt unklar.

**2014-02-22, Samstag**: Prognose 5,6 kWh, üblich 8,8 kWh, Abweichung -36,3 %

- Erklärung: Heute ist mit etwa **36 % weniger Strom** als an einem typischen Samstag zu rechnen – das entspricht rund **5,6 kWh**. Das sind deutlich weniger als sonst.
- Empfehlung: Vielleicht waren gestern oder heute weniger Menschen im Haushalt unterwegs? Oder war die Heizung besonders sparsam eingestellt? Ein Blick auf den Tag könnte helfen, ob etwas ungewöhnlich war – etwa Gäste oder längere Abwesenheit.
- Unsicherheit: Die Schätzung basiert auf vergangenen Daten und kann abweichen; der genaue Grund bleibt unklar.
- Geräte genannt: heizung

**2014-02-23, Sonntag**: Prognose 6,4 kWh, üblich 8,7 kWh, Abweichung -27,0 %

- Erklärung: Heute ist mit etwa **27 % weniger** Stromverbrauch als an einem durchschnittlichen Sonntag gerechnet – das entspricht rund **6,4 kWh**. Das sind deutlich weniger als sonst.
- Empfehlung: Vielleicht waren heute weniger Menschen zu Hause oder es war wärmer als üblich. Sie könnten überlegen, ob jemand länger weg war oder ob die Heizung oder Beleuchtung besonders sparsam lief.
- Unsicherheit: Der Wert ist eine Schätzung für den heutigen Tag und die genaue Ursache bleibt unklar.
- Geräte genannt: heizung

