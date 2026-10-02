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
| 2014-02-12 | Wednesday | 10,0 | 8,0 | 26,1 | number: 25 |  |
| 2014-02-13 | Thursday | 9,1 | 9,6 | -4,7 |  |  |
| 2014-02-14 | Friday | 8,5 | 10,1 | -15,5 |  |  |
| 2014-02-15 | Saturday | 9,5 | 8,9 | 6,2 |  | heizung |
| 2014-02-16 | Sunday | 9,1 | 8,1 | 12,1 |  | heizung |
| 2014-02-17 | Monday | 9,0 | 7,2 | 24,8 |  | heizung |
| 2014-02-18 | Tuesday | 9,1 | 9,6 | -6,1 |  |  |
| 2014-02-19 | Wednesday | 8,2 | 8,7 | -5,0 |  | heizung |
| 2014-02-20 | Thursday | 7,9 | 9,2 | -13,8 |  |  |
| 2014-02-21 | Friday | 6,0 | 10,1 | -40,1 |  |  |
| 2014-02-22 | Saturday | 5,6 | 8,8 | -36,3 |  | heizung |
| 2014-02-23 | Sunday | 6,4 | 8,7 | -27,0 |  | heizung |

## Hinweise

- Gemessen wird nur der Text gegen den State. Eine Eintreffquote gegen die Ist-Werte misst die Prognose und nicht das LLM, sie fehlt bewusst.
- Erklärungsbewertung (verständlich, Empfehlung sinnvoll, Prognose sinnvoll genutzt): verblindeter Export in outlook_ratings_template.csv.
- Die Prognose enthält keine Wirkung der Adaption, der Zyklus läuft ohne Aufruf 1.
