# Proaktiver Zyklus, Morgen-Ausblick, Lauf proactive_cycle_002

## Setup

- Modell: ministral-3:8b, Prompt outlook_v2, temperature 0,0
- Prognose: SYS1 ohne Adaption und ohne Aufruf 1, ohne Kalender
- Tage: 12 ab 2014-02-12 (Train-Split)
- Commit: 1590933 (mit lokalen Änderungen)

## Kernzahlen

| Kennzahl | Wert | Bezug |
|---|---|---|
| Gültige Antworten | 100,0 | % der Tage |
| Regelverstöße | 1 | Tage (Steuerung, State-fremde Zahlen und Daten) |
| Gerätenennungen | 0 | Tage, nur Hinweis |

## Ausblick je Tag

| Tag | Wochentag | Prognose [kWh] | üblich [kWh] | Abweichung [%] | Regelverstöße | Geräte |
|---|---|---:|---:|---:|---|---|
| 2014-02-12 | Mittwoch | 10,0 | 8,0 | 26,1 |  |  |
| 2014-02-13 | Donnerstag | 9,1 | 9,6 | -4,7 |  |  |
| 2014-02-14 | Freitag | 8,5 | 10,1 | -15,5 |  |  |
| 2014-02-15 | Samstag | 9,5 | 8,9 | 6,2 |  |  |
| 2014-02-16 | Sonntag | 9,1 | 8,1 | 12,1 |  |  |
| 2014-02-17 | Montag | 9,0 | 7,2 | 24,8 |  |  |
| 2014-02-18 | Dienstag | 9,1 | 9,6 | -6,1 |  |  |
| 2014-02-19 | Mittwoch | 8,2 | 8,7 | -5,0 |  |  |
| 2014-02-20 | Donnerstag | 7,9 | 9,2 | -13,8 |  |  |
| 2014-02-21 | Freitag | 6,0 | 10,1 | -40,1 |  |  |
| 2014-02-22 | Samstag | 5,6 | 8,8 | -36,3 | number: 4,2 |  |
| 2014-02-23 | Sonntag | 6,4 | 8,7 | -27,0 |  |  |

## Hinweise

- Gemessen wird nur der Text gegen den State. Eine Eintreffquote gegen die Ist-Werte misst die Prognose und nicht das LLM, sie fehlt bewusst.
- Erklärungsbewertung (verständlich, Empfehlung sinnvoll, Prognose sinnvoll genutzt): verblindeter Export in outlook_ratings_template.csv.
- Die Prognose enthält keine Wirkung der Adaption, der Zyklus läuft ohne Aufruf 1.

## Anhang

### Antworten je Tag

**2014-02-12, Mittwoch**: Prognose 10,0 kWh, üblich 8,0 kWh, Abweichung 26,1 %

- Erklärung: Heute wird etwas mehr als sonst an einem Mittwoch verbraucht (voraussichtlich **10,0 kWh**).
- Empfehlung: Falls heute mehr Menschen zu Hause sind oder Gäste da sind, passt das gut. Andernfalls lohnt sich ein Blick auf den Verbrauch am Abend.
- Unsicherheit: Das ist eine Schätzung aus den vergangenen Wochen – an einem einzigen Tag kann der Wert deutlich abweichen.

**2014-02-13, Donnerstag**: Prognose 9,1 kWh, üblich 9,6 kWh, Abweichung -4,7 %

- Erklärung: Heute ist der Stromverbrauch etwas weniger als sonst an einem Donnerstag.
- Empfehlung: Falls heute mehr Menschen zu Hause sind oder Gäste da sind, passt das gut. Ansonsten lohnt sich ein Blick auf den Verbrauch am Abend.
- Unsicherheit: Das ist eine Schätzung aus den vergangenen Wochen – an einem einzigen Tag kann es stärker abweichen.

**2014-02-14, Freitag**: Prognose 8,5 kWh, üblich 10,1 kWh, Abweichung -15,5 %

- Erklärung: Heute ist etwas weniger Strom als sonst an einem Freitag zu erwarten (ca. **8,5 kWh**).
- Empfehlung: Falls heute mehr Menschen im Haushalt sind oder Gäste da sind, könnte der Wert passen – andernfalls lohnt sich ein Blick auf den Abendverbrauch.
- Unsicherheit: Das ist eine Schätzung aus den vergangenen Wochen und kann an einem Tag stärker abweichen.

**2014-02-15, Samstag**: Prognose 9,5 kWh, üblich 8,9 kWh, Abweichung 6,2 %

- Erklärung: Heute ist etwas mehr Strom als sonst am Samstag zu erwarten (voraussichtlich **9,5 kWh**).
- Empfehlung: Falls heute viele Menschen im Haushalt sind oder Gäste da sind, passt das gut. Andernfalls lohnt sich ein Blick auf den Verbrauch am Abend.
- Unsicherheit: Das ist eine Schätzung aus den vergangenen Wochen – an einem einzigen Tag kann der Wert deutlich abweichen.

**2014-02-16, Sonntag**: Prognose 9,1 kWh, üblich 8,1 kWh, Abweichung 12,1 %

- Erklärung: Etwas mehr als sonst an einem Sonntag.
- Empfehlung: Falls heute viele Menschen im Haushalt sind oder Gäste da sind, passt das gut. Andernfalls lohnt sich ein Blick auf den Verbrauch am Abend.
- Unsicherheit: Das ist eine Schätzung aus den vergangenen Wochen und kann an einem einzelnen Tag deutlich abweichen.

**2014-02-17, Montag**: Prognose 9,0 kWh, üblich 7,2 kWh, Abweichung 24,8 %

- Erklärung: Heute ist etwas mehr Strom als sonst an einem Montag zu erwarten (voraussichtlich **9,0 kWh**).
- Empfehlung: Falls heute viele Menschen im Haushalt sind oder Gäste da sind, passt das gut. Andernfalls könnte es sich lohnen, den Verbrauch am Abend einmal anzuschauen.
- Unsicherheit: Das ist eine Schätzung aus den vergangenen Wochen – ein einzelner Tag kann davon deutlich abweichen.

**2014-02-18, Dienstag**: Prognose 9,1 kWh, üblich 9,6 kWh, Abweichung -6,1 %

- Erklärung: Heute Dienstag wird etwas weniger Strom verbraucht als sonst an einem Dienstag.
- Empfehlung: Falls heute mehr Menschen zu Hause sind oder Gäste da sind, passt das gut. Ansonsten lohnt sich ein Blick auf den Verbrauch am Abend.
- Unsicherheit: Das ist eine Schätzung aus den vergangenen Wochen – an einem einzelnen Tag kann der Verbrauch stärker abweichen.

**2014-02-19, Mittwoch**: Prognose 8,2 kWh, üblich 8,7 kWh, Abweichung -5,0 %

- Erklärung: Heute ist der Stromverbrauch etwas niedriger als sonst an einem Mittwoch.
- Empfehlung: Falls heute mehr Menschen zu Hause sind oder Gäste da sind, könnte das passen. Ansonsten lohnt sich ein Blick auf den Verbrauch am Abend.
- Unsicherheit: Das ist eine Schätzung aus den vergangenen Wochen – an einem einzigen Tag kann es stärker abweichen.

**2014-02-20, Donnerstag**: Prognose 7,9 kWh, üblich 9,2 kWh, Abweichung -13,8 %

- Erklärung: Heute ist etwas weniger Strom als sonst an einem Donnerstag verbraucht (voraussichtlich **7,9 kWh**).
- Empfehlung: Falls heute mehr Menschen zu Hause sind oder Gäste da sind, könnte der Verbrauch höher ausfallen. Andernfalls lohnt sich ein Blick auf den Abendverbrauch.
- Unsicherheit: Das ist eine Schätzung aus den vergangenen Wochen – an einem einzigen Tag kann es stärker abweichen.

**2014-02-21, Freitag**: Prognose 6,0 kWh, üblich 10,1 kWh, Abweichung -40,1 %

- Erklärung: Heute wird deutlich weniger Strom verbraucht als sonst an einem Freitag, etwa **6,0 kWh** (normalerweise sind es rund **10,1 kWh**).
- Empfehlung: Wenn heute mehr Menschen zu Hause sind oder Gäste da sind, könnte der Verbrauch höher liegen. Andernfalls lohnt sich ein Blick auf den Abendverbrauch, um das ungewöhnlich niedrige Ergebnis zu überprüfen.
- Unsicherheit: Dies ist eine Schätzung aus den vergangenen Wochen – an einem einzigen Tag kann die Abweichung deutlich größer sein.

**2014-02-22, Samstag**: Prognose 5,6 kWh, üblich 8,8 kWh, Abweichung -36,3 %

- Erklärung: Heute wird deutlich weniger Strom verbraucht als sonst am Samstag, etwa **4,2 kWh** weniger (voraussichtlich **5,6 kWh**).
- Empfehlung: Wenn heute weniger Menschen zu Hause sind oder Gäste fehlen, passt das gut. Andernfalls könnte ein Blick auf den Abendverbrauch sinnvoll sein.
- Unsicherheit: Das ist eine Schätzung aus den vergangenen Wochen – an einem einzelnen Tag kann der Verbrauch stärker abweichen.
- Regelverstöße: number: 4,2

**2014-02-23, Sonntag**: Prognose 6,4 kWh, üblich 8,7 kWh, Abweichung -27,0 %

- Erklärung: Heute wird etwas weniger Strom verbraucht als sonst an einem Sonntag – etwa **6,4 kWh** (normalerweise sind es rund **8,7 kWh**).
- Empfehlung: Falls heute mehr Menschen zu Hause sind oder Gäste da waren, passt das gut. Ansonsten könnte ein Blick auf den Abendverbrauch lohnen.
- Unsicherheit: Das ist eine Schätzung aus den vergangenen Wochen – an einem einzigen Tag kann der Verbrauch stärker abweichen.

