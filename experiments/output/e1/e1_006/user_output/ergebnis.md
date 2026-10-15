# E1: Erkennung der Verbrauchsänderungen

## Setup

- Lauf: e1_006
- Stichtage: SF6: 02.12.2016, SF7: 13.01.2017, SF8: 20.02.2017
- Szenarien: scaled, scaled_down, ramp_28, ramp_28_down, ramp_56, ramp_56_down, peak
- Systeme: SYS1, die Regel ordnet ein, keine Adaption, kein Sprachmodell
- Commit: f647560

## Kriterien der Teilfrage 1

| Kriterium | Ziel | Ergebnis | erfüllt |
|---|---|---|---|
| Erkennungsrate eingebauter Anomalien | ≥ 90 % | 9 von 13 (69 %) | nein |
| Erkennungsrate langsamer Rampen | 0 % | 3 von 6 (50 %) | nein |

## Erkennung je Szenario über die Stichtage

| Szenario | erwartet | erkannt | Erkennungstag, Mittel (Spanne) | auslösende Skala |
|---|---|---|---|---|
| scaled | erkannt | 1 von 3 | 15,0 (15) | weekly + long_term |
| scaled_down | erkannt | 2 von 3 | 34,5 (31–38) | weekly + long_term |
| ramp_28 | erkannt | 2 von 3 | 33,5 (17–50) | weekly + long_term |
| ramp_28_down | erkannt | 3 von 3 | 43,0 (31–57) | weekly + long_term |
| ramp_56 | nicht erkannt | 2 von 3 | 43,0 (29–57) | weekly + long_term |
| ramp_56_down | nicht erkannt | 1 von 3 | 57,0 (57) | weekly + long_term |
| peak | erkannt | 1 von 1 | - | weekday |

## Hinweise

- Tag = Entscheidungstag seit dem Stichtag, an Tag 1 wird der Stichtag selbst eingeordnet
- erkannt: Lastspitze = Einzelanomalie (Skala daily oder weekday) an Tag 1, Dauerlast und Rampe = anhaltende Veränderung (weekly und long_term an 6 von 7 Tagen). Gezählt wird der erste Tag, an dem der Szenariolauf den Kennwert hat und der Kontrolllauf desselben Stichtags nicht
- auswertbar: zeigt der Kontrolllauf am Einbautag der Lastspitze schon eine Einzelanomalie, geht der Fall nicht in die Zählung ein
- erwartet: die Rampe über 56 Tage soll nicht als anhaltende Veränderung erkannt werden
- Anhaltende Veränderungen werden im Mittel an Tag 35,0 erkannt (Dauerlast und Rampe über 28 Tage)
- Erkennungstag, Mittel (Spanne): nur über die erkannten Fälle, bei der Lastspitze entfällt er, sie zählt nur an Tag 1
- Skalen anhaltend: weekly bzw. long_term liegt an 6 der letzten 7 Tage über der Schwelle, eine anhaltende Veränderung gilt erst, wenn beide gleichzeitig anhalten. Abgerissen zählt, wie oft weekly vor diesem Tag wieder unter 6 von 7 Tagen fiel

## Anhang

### Erkennung je Stichtag und Szenario

| Stichtag | Szenario | erkannt am Tag | auslösende Skala | Tage mit Kennwert im Kontrolllauf | auswertbar |
|---|---|---:|---|---:|---|
| SF6 | scaled | - | - | 0 | ja |
| SF6 | scaled_down | 31 | weekly + long_term | 0 | ja |
| SF6 | ramp_28 | 50 | weekly + long_term | 0 | ja |
| SF6 | ramp_28_down | 31 | weekly + long_term | 0 | ja |
| SF6 | ramp_56 | 57 | weekly + long_term | 0 | ja |
| SF6 | ramp_56_down | - | - | 0 | ja |
| SF6 | peak | - | - | 1 | nein |
| SF7 | scaled | 15 | weekly + long_term | 0 | ja |
| SF7 | scaled_down | 38 | weekly + long_term | 0 | ja |
| SF7 | ramp_28 | 17 | weekly + long_term | 0 | ja |
| SF7 | ramp_28_down | 41 | weekly + long_term | 0 | ja |
| SF7 | ramp_56 | 29 | weekly + long_term | 0 | ja |
| SF7 | ramp_56_down | - | - | 0 | ja |
| SF7 | peak | - | - | 1 | nein |
| SF8 | scaled | - | - | 0 | ja |
| SF8 | scaled_down | - | - | 0 | ja |
| SF8 | ramp_28 | - | - | 0 | ja |
| SF8 | ramp_28_down | 57 | weekly + long_term | 0 | ja |
| SF8 | ramp_56 | - | - | 0 | ja |
| SF8 | ramp_56_down | 57 | weekly + long_term | 0 | ja |
| SF8 | peak | 1 | weekday | 0 | ja |

### Niveauänderungen: erster Tag, an dem die Skalen anhalten

| Stichtag | Szenario | weekly hält an ab Tag | long_term hält an ab Tag | beide halten an ab Tag (Erkennung) | weekly davor abgerissen [mal] |
|---|---|---:|---:|---:|---:|
| SF6 | scaled | 7 | 59 | - | 4 |
| SF6 | scaled_down | 7 | 22 | 31 | 1 |
| SF6 | ramp_28 | 7 | 50 | 50 | 2 |
| SF6 | ramp_28_down | 7 | 28 | 31 | 1 |
| SF6 | ramp_56 | 7 | 57 | 57 | 2 |
| SF6 | ramp_56_down | 7 | 30 | - | 2 |
| SF7 | scaled | 6 | 15 | 15 | 0 |
| SF7 | scaled_down | 35 | 38 | 38 | 0 |
| SF7 | ramp_28 | 7 | 17 | 17 | 0 |
| SF7 | ramp_28_down | 8 | 41 | 41 | 2 |
| SF7 | ramp_56 | 7 | 17 | 29 | 1 |
| SF7 | ramp_56_down | 8 | 18 | - | 3 |
| SF8 | scaled | 1 | 28 | - | 3 |
| SF8 | scaled_down | 1 | 8 | - | 1 |
| SF8 | ramp_28 | 1 | 13 | - | 2 |
| SF8 | ramp_28_down | 1 | 9 | 57 | 1 |
| SF8 | ramp_56 | 1 | 10 | - | 1 |
| SF8 | ramp_56_down | 1 | 9 | 57 | 1 |
