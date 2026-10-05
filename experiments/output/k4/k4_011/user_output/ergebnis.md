# K4 Adaptionsstrategien, Lauf k4_011

## Setup

- Cutover: CO1 (2014-07-15), CO2 (2014-10-24), CO3 (2015-03-01), CO4 (2015-06-10), CO5 (2015-10-22)
- Ereignis: Sprung, jede Stunde × 1,2
- Aktion: fest an Tag 6 und 19 nach dem Cutover (Orakel), Historie ab t_c wie die Adaptionsregel
- Auswertung: 23 Prognosetage ab dem Tag der Aktion, Differenz zu keiner Aktion am selben Tag
- Commit: 68202b5 (mit lokalen Änderungen)

## Kennzahlen MAE

| Kennzahl | Wert | Bezug |
|---|---|---|
| Reset, Historie ab t_c, Aktion an Tag 6: Differenz zu keiner Aktion bei Sprung +20 % [W] | 5,1 | 2,8 % des Fehlers ohne Aktion, bei 1/5 Cutover besser |
| Stufen-Regressor, Aktion an Tag 6: Differenz zu keiner Aktion bei Sprung +20 % [W] | -0,8 | -0,4 % des Fehlers ohne Aktion, bei 3/5 Cutover besser |
| Aktion an Tag 19: beste Differenz bei Sprung +20 % [W] | -0,2 | späte Erkennung |

## Differenz der Aktion zu keiner Aktion (MAE), Mittel über 23 Prognosetage ab der Aktion, je Cutover [W], negativ = besser

| Ereignis | Aktion an Tag nach Cutover | Aktion | 2014-07-15 | 2014-10-24 | 2015-03-01 | 2015-06-10 | 2015-10-22 | Mittel | Cutover besser | Mittel in % des Fehlers ohne Aktion |
|---|---:|---|---:|---:|---:|---:|---:|---:|---|---:|
| Sprung +20 % | 6 | Reset, Historie ab t_c | -1,7 | 2,2 | 16,6 | 2,0 | 6,5 | 5,1 | 1/5 | 2,8 |
| Sprung +20 % | 6 | Stufen-Regressor | -5,6 | -0,1 | 1,1 | -1,0 | 1,9 | -0,8 | 3/5 | -0,4 |
| Sprung +20 % | 19 | Reset, Historie ab t_c | -9,1 | 5,6 | 1,8 | -2,3 | 11,1 | 1,4 | 2/5 | 0,8 |
| Sprung +20 % | 19 | Stufen-Regressor | -0,8 | 0,2 | 1,0 | 0,1 | -1,7 | -0,2 | 2/5 | -0,1 |

## Kennzahlen Tagesfehler

| Kennzahl | Wert | Bezug |
|---|---|---|
| Reset, Historie ab t_c, Aktion an Tag 6: Differenz zu keiner Aktion bei Sprung +20 % [W] | -7,8 | -7,3 % des Fehlers ohne Aktion, bei 3/5 Cutover besser |
| Stufen-Regressor, Aktion an Tag 6: Differenz zu keiner Aktion bei Sprung +20 % [W] | -0,2 | -0,2 % des Fehlers ohne Aktion, bei 2/5 Cutover besser |
| Aktion an Tag 19: beste Differenz bei Sprung +20 % [W] | -4,8 | späte Erkennung |

## Differenz der Aktion zu keiner Aktion (Tagesfehler), Mittel über 23 Prognosetage ab der Aktion, je Cutover [W], negativ = besser

| Ereignis | Aktion an Tag nach Cutover | Aktion | 2014-07-15 | 2014-10-24 | 2015-03-01 | 2015-06-10 | 2015-10-22 | Mittel | Cutover besser | Mittel in % des Fehlers ohne Aktion |
|---|---:|---|---:|---:|---:|---:|---:|---:|---|---:|
| Sprung +20 % | 6 | Reset, Historie ab t_c | -4,1 | -36,8 | 15,0 | 8,5 | -21,6 | -7,8 | 3/5 | -7,3 |
| Sprung +20 % | 6 | Stufen-Regressor | -5,9 | -6,8 | 5,1 | 2,9 | 3,5 | -0,2 | 2/5 | -0,2 |
| Sprung +20 % | 19 | Reset, Historie ab t_c | -50,4 | -11,2 | -0,2 | 14,1 | 24,0 | -4,8 | 3/5 | -4,6 |
| Sprung +20 % | 19 | Stufen-Regressor | -12,1 | 11,8 | -1,6 | 0,4 | 7,9 | 1,3 | 2/5 | 1,3 |

## Prognose minus Messung beim Tagesmittel ohne Aktion, Mittel über die Cutover, je Tag seit Cutover [W], negativ = Prognose zu niedrig

| Ereignis | Tag -3 | Tag -2 | Tag -1 | Tag 0 | Tag 1 | Tag 2 | Tag 3 | Tag 4 | Tag 5 | Tag 6 | Tag 7 | Tag 8 | Tag 9 | Tag 10 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| Sprung +20 % | -161,0 | -28,2 | -91,4 | -58,8 | -156,0 | -92,2 | -93,1 | -141,9 | -13,4 | 66,8 | 12,7 | -1,9 | -98,2 | -65,8 |

## Hinweise

- Differenz: Fehler mit Aktion minus Fehler ohne Aktion, tageweise auf denselben Daten, über die Tage ab der Aktion gemittelt
- Cutover besser: Zahl der Cutover, bei denen die Differenz unter null liegt. Die Fenster überlappen, einzelne Cutover sind nicht unabhängig
- Tagesfehler: Betrag der Differenz zwischen prognostiziertem und gemessenem Tagesmittel (Tagesenergie), wie in K1, nur Tage mit lauter bewerteten Stunden. Gegenläufige Stundenfehler gleichen sich dabei aus

![k4_error_curve.png](k4_error_curve.png)
