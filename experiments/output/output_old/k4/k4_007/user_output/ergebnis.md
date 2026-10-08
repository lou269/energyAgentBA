# K4 Adaptionsstrategien, Lauf k4_007

## Setup

- Cutover: 2013-10-15, 2014-02-12, 2014-06-12, 2014-10-10, 2015-02-07
- Ereignisse: Dauerlast +100 W, proportional jede Stunde × 1,3
- Aktion: fest an Tag 6 und 19 nach dem Cutover (Orakel), Historie ab t_c wie die Adaptionsregel
- Auswertung: 30 Prognosetage ab dem Tag der Aktion, Differenz zu keiner Aktion am selben Tag
- Commit: c50d5ab (mit lokalen Änderungen)

## Kennzahlen MAE

| Kennzahl | Wert | Bezug |
|---|---|---|
| Reset, Historie ab t_c, Aktion an Tag 6: Differenz zu keiner Aktion bei Dauerlast +100 W [W] | 0,9 | 0,6 % des Fehlers ohne Aktion, bei 3/5 Cutover besser |
| Stufen-Regressor, Aktion an Tag 6: Differenz zu keiner Aktion bei Dauerlast +100 W [W] | -0,2 | -0,1 % des Fehlers ohne Aktion, bei 3/5 Cutover besser |
| Aktion an Tag 19: beste Differenz bei Dauerlast +100 W [W] | -0,1 | späte Erkennung |

## Differenz der Aktion zu keiner Aktion (MAE), Mittel über 30 Prognosetage ab der Aktion, je Cutover [W], negativ = besser

| Ereignis | Aktion an Tag nach Cutover | Aktion | 2013-10-15 | 2014-02-12 | 2014-06-12 | 2014-10-10 | 2015-02-07 | Mittel | Cutover besser | Mittel in % des Fehlers ohne Aktion |
|---|---:|---|---:|---:|---:|---:|---:|---:|---|---:|
| proportional ×1,3 | 6 | Reset, Historie ab t_c | 0,7 | -2,6 | 7,9 | -2,1 | -4,1 | -0,0 | 3/5 | -0,0 |
| proportional ×1,3 | 6 | Stufen-Regressor | -1,6 | 0,2 | 4,1 | -1,1 | -7,0 | -1,1 | 3/5 | -0,5 |
| proportional ×1,3 | 19 | Reset, Historie ab t_c | 5,4 | 0,9 | 1,2 | 4,1 | -2,9 | 1,7 | 1/5 | 0,8 |
| proportional ×1,3 | 19 | Stufen-Regressor | 0,4 | -3,0 | -0,2 | 0,9 | -0,4 | -0,5 | 3/5 | -0,2 |
| Dauerlast +100 W | 6 | Reset, Historie ab t_c | 1,1 | -0,2 | 7,2 | -1,5 | -2,4 | 0,9 | 3/5 | 0,6 |
| Dauerlast +100 W | 6 | Stufen-Regressor | -1,3 | 0,6 | 4,6 | -0,9 | -4,2 | -0,2 | 3/5 | -0,1 |
| Dauerlast +100 W | 19 | Reset, Historie ab t_c | 4,2 | 0,9 | 0,3 | 2,5 | -2,3 | 1,1 | 1/5 | 0,7 |
| Dauerlast +100 W | 19 | Stufen-Regressor | 0,2 | -1,8 | 0,1 | 0,7 | 0,3 | -0,1 | 1/5 | -0,1 |

## Kennzahlen Tagesfehler

| Kennzahl | Wert | Bezug |
|---|---|---|
| Reset, Historie ab t_c, Aktion an Tag 6: Differenz zu keiner Aktion bei Dauerlast +100 W [W] | 1,0 | 1,4 % des Fehlers ohne Aktion, bei 2/5 Cutover besser |
| Stufen-Regressor, Aktion an Tag 6: Differenz zu keiner Aktion bei Dauerlast +100 W [W] | 0,3 | 0,5 % des Fehlers ohne Aktion, bei 3/5 Cutover besser |
| Aktion an Tag 19: beste Differenz bei Dauerlast +100 W [W] | -1,1 | späte Erkennung |

## Differenz der Aktion zu keiner Aktion (Tagesfehler), Mittel über 30 Prognosetage ab der Aktion, je Cutover [W], negativ = besser

| Ereignis | Aktion an Tag nach Cutover | Aktion | 2013-10-15 | 2014-02-12 | 2014-06-12 | 2014-10-10 | 2015-02-07 | Mittel | Cutover besser | Mittel in % des Fehlers ohne Aktion |
|---|---:|---|---:|---:|---:|---:|---:|---:|---|---:|
| proportional ×1,3 | 6 | Reset, Historie ab t_c | -1,0 | 1,0 | 6,9 | -3,9 | 2,7 | 1,1 | 2/5 | 1,3 |
| proportional ×1,3 | 6 | Stufen-Regressor | -2,2 | 0,5 | 3,4 | -0,5 | -0,5 | 0,1 | 3/5 | 0,2 |
| proportional ×1,3 | 19 | Reset, Historie ab t_c | 3,0 | 0,6 | -4,1 | -4,1 | 2,0 | -0,5 | 2/5 | -0,5 |
| proportional ×1,3 | 19 | Stufen-Regressor | -5,4 | -3,4 | -0,5 | 1,4 | -0,9 | -1,8 | 4/5 | -1,8 |
| Dauerlast +100 W | 6 | Reset, Historie ab t_c | -0,3 | 2,4 | 5,2 | -3,9 | 1,6 | 1,0 | 2/5 | 1,4 |
| Dauerlast +100 W | 6 | Stufen-Regressor | -1,3 | 1,4 | 3,5 | -1,4 | -0,5 | 0,3 | 3/5 | 0,5 |
| Dauerlast +100 W | 19 | Reset, Historie ab t_c | 2,2 | 0,6 | -4,0 | -3,1 | 1,3 | -0,6 | 2/5 | -0,8 |
| Dauerlast +100 W | 19 | Stufen-Regressor | -4,4 | -2,2 | -0,0 | 0,6 | 0,6 | -1,1 | 3/5 | -1,4 |

## Hinweise

- Differenz: Fehler mit Aktion minus Fehler ohne Aktion, tageweise auf denselben Daten, über die Tage ab der Aktion gemittelt
- Cutover besser: Zahl der Cutover, bei denen die Differenz unter null liegt. Die Fenster überlappen, einzelne Cutover sind nicht unabhängig
- Tagesfehler: Betrag der Differenz zwischen prognostiziertem und gemessenem Tagesmittel (Tagesenergie), wie in K1, nur Tage mit lauter bewerteten Stunden. Gegenläufige Stundenfehler gleichen sich dabei aus

![k4_error_curve.png](k4_error_curve.png)
