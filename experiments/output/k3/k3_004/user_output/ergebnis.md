# K3: Adaptionsstrategien

## Setup

- Lauf: k3_004
- Stichtage: SF1: 31.07.2014, SF2: 12.02.2015, SF3: 24.05.2015, SF4: 26.09.2015, SF5: 12.01.2016
- Szenarien: scaled
- Aktionstage: fest an Tag 8 und 19 nach dem Stichtag (Orakel, ohne Einordnung), Historie ab t_c wie die Adaptionsregel
- Auswertung: 53 Prognosetage ab dem Tag der Aktion
- Commit: 83412b7

## Differenz des Tagesfehlers zu keiner Aktion [W], negativ = besser

| Szenario | Aktionstag | Aktion | SF1 | SF2 | SF3 | SF4 | SF5 | Mittel | Stichtage besser | Mittel [%] |
|---|---:|---|---:|---:|---:|---:|---:|---:|---|---:|
| scaled | 8 | Zurücksetzen | −4,4 | 1,8 | −1,4 | 8,3 | 2,3 | 1,3 | 2/5 | 1,5 |
| scaled | 8 | Stufenregressor | −0,7 | −0,7 | 3,1 | −0,8 | −1,4 | −0,1 | 4/5 | −0,1 |
| scaled | 19 | Zurücksetzen | −2,9 | 5,0 | −3,3 | 16,0 | 3,3 | 3,6 | 2/5 | 4,0 |
| scaled | 19 | Stufenregressor | −3,2 | −0,4 | −4,9 | 1,5 | 0,2 | −1,4 | 3/5 | −1,5 |

## Hinweise

- Differenz: Tagesfehler mit Aktion minus Tagesfehler ohne Aktion, tageweise auf denselben Daten, über die Tage ab der Aktion gemittelt
- Stichtage besser: Zahl der Stichtage, bei denen die Differenz unter null liegt. Die Fenster überlappen, einzelne Stichtage sind nicht unabhängig
- Tagesfehler: Betrag der Differenz zwischen prognostiziertem und gemessenem Tagesmittel, wie in K4, nur Tage mit lauter bewerteten Stunden
