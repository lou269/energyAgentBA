# K3 Teil 2: Spitzen-Tage ausblenden

## Setup

- Lauf: k3_mask_004
- Stichtage: SF1: 31.07.2014, SF2: 12.02.2015, SF3: 24.05.2015, SF4: 26.09.2015, SF5: 12.01.2016
- Szenarien: peak an Tag 0, 8, 17 nach dem Stichtag (Orakel, ohne Einordnung)
- Vergleich: Ereignistage für Prophet ausgeblendet (mask) gegen nicht ausgeblendet (none), 60 Tage Trainingsfenster
- Commit: 83412b7 (mit lokalen Änderungen)

## Differenz des Tagesfehlers mask minus none [W], negativ = Ausblenden besser

| Szenario | Tage | ohne Ausblenden [W] | SF1 | SF2 | SF3 | SF4 | SF5 | Mittel | Stichtage besser |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---|
| peak | 300 | 76,8 | 1,0 | −1,1 | 3,1 | −0,9 | 0,7 | 0,6 | 2/5 |

## Hinweise

- mask minus none: beide gegen dieselbe Reihe mit Spitzen bewertet, ausgeblendet ist nur das Training
- Tagesfehler wie in Teil 1: Tage mit unvollständig bewerteten Stunden zählen dort nicht mit
