# E3 Saisonaler Drift, Lauf e3_001

## Setup

- Cutover und Ereignisse: CO3 (2015-03-01): keine Änderung, Rampe über 28 Tage −20 %, Rampe über 56 Tage −20 %; CO4 (2015-06-10): keine Änderung, Rampe über 28 Tage +20 %, Rampe über 56 Tage +20 %, Rampe über 28 Tage −20 %, Rampe über 56 Tage −20 %; CO5 (2015-10-22): keine Änderung, Rampe über 28 Tage +20 %, Rampe über 56 Tage +20 %
- Systeme: SYS2 Regel, SYS3 LLM, je im vollen Kreislauf, SYS1 ohne Adaption nur als Bezug für den MAE
- LLM: ministral-3:8b, Prompt v29
- Commit: 3424ee4

## Erkennung, Gate und Reset je System, Cutover und Ereignis

| System | Cutover | Ereignis | erwartet | erstes new_pattern (Tag) | Tage Gate offen | erster Reset (Tag) | MAE ab Reset minus SYS1 [W] |
|---|---|---|---|---:|---:|---:|---|
| SYS2 Regel | 2015-03-01 | keine Änderung | normal | - | - | - | - |
| SYS2 Regel | 2015-03-01 | Rampe über 28 Tage −20 % | new_pattern | 36 | 19 | 36 | 2,2 |
| SYS2 Regel | 2015-03-01 | Rampe über 56 Tage −20 % | normal | 39 | 5 | 39 | 6,5 |
| SYS2 Regel | 2015-06-10 | keine Änderung | normal | - | - | 54 | 10,3 |
| SYS2 Regel | 2015-06-10 | Rampe über 28 Tage +20 % | new_pattern | 34 | 9 | 34 | 0,4 |
| SYS2 Regel | 2015-06-10 | Rampe über 56 Tage +20 % | normal | - | 8 | - | - |
| SYS2 Regel | 2015-06-10 | Rampe über 28 Tage −20 % | new_pattern | 48 | 6 | 48 | 0,8 |
| SYS2 Regel | 2015-06-10 | Rampe über 56 Tage −20 % | normal | 50 | 6 | 50 | 7,3 |
| SYS2 Regel | 2015-10-22 | keine Änderung | normal | - | - | - | - |
| SYS2 Regel | 2015-10-22 | Rampe über 28 Tage +20 % | new_pattern | 45 | 6 | 45 | 10,9 |
| SYS2 Regel | 2015-10-22 | Rampe über 56 Tage +20 % | normal | 46 | 7 | 46 | 10,3 |
| SYS3 LLM | 2015-03-01 | keine Änderung | normal | - | - | 40 | -1,3 |
| SYS3 LLM | 2015-03-01 | Rampe über 28 Tage −20 % | new_pattern | 33 | 19 | 33 | -2,2 |
| SYS3 LLM | 2015-03-01 | Rampe über 56 Tage −20 % | normal | 35 | 13 | 35 | 3,0 |
| SYS3 LLM | 2015-06-10 | keine Änderung | normal | - | - | 52 | 26,8 |
| SYS3 LLM | 2015-06-10 | Rampe über 28 Tage +20 % | new_pattern | 32 | 8 | 32 | 1,7 |
| SYS3 LLM | 2015-06-10 | Rampe über 56 Tage +20 % | normal | 51 | 8 | 51 | 17,8 |
| SYS3 LLM | 2015-06-10 | Rampe über 28 Tage −20 % | new_pattern | 47 | 6 | 47 | 1,1 |
| SYS3 LLM | 2015-06-10 | Rampe über 56 Tage −20 % | normal | 48 | 3 | 48 | 1,2 |
| SYS3 LLM | 2015-10-22 | keine Änderung | normal | - | - | - | - |
| SYS3 LLM | 2015-10-22 | Rampe über 28 Tage +20 % | new_pattern | 29 | 2 | 29 | 4,5 |
| SYS3 LLM | 2015-10-22 | Rampe über 56 Tage +20 % | normal | 46 | 7 | 46 | 10,3 |

## Hinweise

- Tag = Entscheidungstag seit Cutover, an Tag 1 wird der Cutover-Tag eingeordnet
- erwartet: Rampe über 28 Tage ist ein neues Muster, Rampe über 56 Tage nicht, dort ist still aufnehmen richtig und ein Reset ein Fehler
- erstes new_pattern und Gate: gepaart wird je System gegen dessen eigenen Kontrolllauf, leer = still aufgenommen
- offenes Gate = Tag, an dem SYS3 das LLM fragt, States und Antworten liegen in raw/
- MAE: SYS1 ordnet wie die Regel ein, setzt aber nie zurück. Vor den gewählten Cutovern setzt die Regel nicht zurück, bis zum ersten Reset laufen beide also gleich. Negativ = der Reset senkt den Fehler, leer = kein Reset
- keine Änderung: jeder Reset dort ist ein falscher
