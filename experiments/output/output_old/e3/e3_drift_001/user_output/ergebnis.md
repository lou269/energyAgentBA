# E3 Stufe gegen langsame Rampe, Lauf e3_drift_001

## Setup

- Cutover: 2013-10-15, 2014-01-15, 2014-04-15, 2014-07-15
- Ereignisse: keine Änderung, proportional ×1,3, Rampe über 28 Tage auf ×1,3, Rampe über 56 Tage auf ×1,3
- System: SYS2 Regel, Einordnung und Reset wie im Betrieb, ohne LLM
- Commit: 3bef76f (mit lokalen Änderungen)

## Kennzahlen

| Kennzahl | Wert | Bezug |
|---|---|---|
| proportional ×1,3: als new_pattern gemeldet | 3/4 | im Mittel an Tag 8 |
| Rampe über 28 Tage auf ×1,3: als new_pattern gemeldet | 4/4 | im Mittel an Tag 26 |
| Rampe über 56 Tage auf ×1,3: als new_pattern gemeldet | 2/4 | im Mittel an Tag 28 |
| proportional ×1,3: Tage mit offenem Gate | 2,0 | Mittel über Cutover, mehr als im Kontrolllauf |
| Rampe über 28 Tage auf ×1,3: Tage mit offenem Gate | 2,8 | Mittel über Cutover, mehr als im Kontrolllauf |
| Rampe über 56 Tage auf ×1,3: Tage mit offenem Gate | 1,5 | Mittel über Cutover, mehr als im Kontrolllauf |

## Erster Tag mit new_pattern, den der Kontrolllauf nicht hat, je Cutover

| Ereignis | 2013-10-15 | 2014-01-15 | 2014-04-15 | 2014-07-15 | Mittel | erkannt |
|---|---:|---:|---:|---:|---:|---|
| proportional ×1,3 | 6 | - | 11 | 8 | 8,3 | 3/4 |
| Rampe über 28 Tage auf ×1,3 | 5 | 29 | 32 | 36 | 25,5 | 4/4 |
| Rampe über 56 Tage auf ×1,3 | 5 | - | - | 51 | 28,0 | 2/4 |

## Tage mit offenem Gate ohne Gegenstück im Kontrolllauf, je Cutover

| Ereignis | 2013-10-15 | 2014-01-15 | 2014-04-15 | 2014-07-15 | Mittel |
|---|---:|---:|---:|---:|---:|
| proportional ×1,3 | 4 | 0 | 3 | 1 | 2,0 |
| Rampe über 28 Tage auf ×1,3 | 4 | 3 | 2 | 2 | 2,8 |
| Rampe über 56 Tage auf ×1,3 | 2 | 1 | 0 | 3 | 1,5 |

## Hinweise

- Tag = Entscheidungstag seit Cutover, an Tag 1 wird der Cutover-Tag eingeordnet
- kein Tag = die Veränderung wurde still aufgenommen
- offenes Gate = Tag, an dem SYS3 das LLM fragen würde, die States dieser Tage liegen in raw/
