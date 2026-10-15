# K2: Sprachmodell

## Setup

- Lauf: k2_003 und k2_seq_003
- Stichtage: SF2: 12.02.2015
- Szenarien: Kontrolllauf, scaled_strong, peak_strong
- Systeme: SYS3 mit Adaption, jedes Modell als eigener Kreislauf
- Sprachmodell: Prompt v30, temperature 0,0, höchstens 2 Versuche je Aufruf, ohne Kalender
- Modelle: MDL0 qwen3:4b, MDL1 qwen3:8b, MDL2 qwen3.5:9b, MDL3 gemma4:e4b, MDL4 gemma4:e4b-mlx, MDL5 ministral-3:8b
- Ebene 1: 10 synthetische Fälle, je Modell 1 Aufruf je Fall, Regel (BASELINE) läuft mit
- Ebene 2: 40 Tage vor und 60 Tage nach dem Stichtag
- Produktivmodell: ministral-3:8b
- Textprüfung: 15 Steuerungswörter, Zahlentoleranz 0,5, gerundet auf 10 erlaubt, Fensterzahlen aus dem Prompt 7, 28
- Commit: a46b8ad (Ebene 1), 9c0e1d6 (Ebene 2)

## Ebene 1: Modellvergleich auf den Einzelfällen

| ID | Modell | richtig | Macro-F1 | ungültig | Ø Versuche | Grounding | Ø Zeit [s] | p95 Zeit [s] |
|---|---|---|---:|---:|---:|---:|---:|---:|
| MDL2 | qwen3.5:9b | 10/10 | 1,0 | 0 | 1,0 | 0,8 | 9,8 | 17,3 |
| MDL5 | ministral-3:8b | 10/10 | 1,0 | 0 | 1,0 | 0,9 | 10,5 | 18,7 |
| BASELINE | Regel | 9/10 | 0,8 | 0 | 1,0 | - | 0,0 | 0,0 |
| MDL0 | qwen3:4b | 9/10 | 0,8 | 0 | 1,0 | 0,8 | 5,3 | 9,4 |
| MDL1 | qwen3:8b | 9/10 | 0,8 | 0 | 1,0 | 0,9 | 10,5 | 17,8 |
| MDL3 | gemma4:e4b | 0/10 | 0,0 | 10 | 2,0 | - | 0,0 | 0,0 |
| MDL4 | gemma4:e4b-mlx | 0/10 | 0,0 | 10 | 2,0 | - | 0,0 | 0,0 |

## Ebene 1: Antwort je Fall (✓ = richtig, sonst die Antwort, - = ungültig)

| Fall | erwartet | qwen3.5:9b | ministral-3:8b | Regel | qwen3:4b | qwen3:8b | gemma4:e4b | gemma4:e4b-mlx |
|---|---|---|---|---|---|---|---|---|
| absence_drift_down | absence | ✓ | ✓ | new_pattern | new_pattern | new_pattern | - | - |
| low_single_scale | low | ✓ | ✓ | ✓ | ✓ | ✓ | - | - |
| measurement_error_missing_day | measurement_error | ✓ | ✓ | ✓ | ✓ | ✓ | - | - |
| new_pattern | new_pattern | ✓ | ✓ | ✓ | ✓ | ✓ | - | - |
| new_pattern_at_min_scales_boundary | new_pattern | ✓ | ✓ | ✓ | ✓ | ✓ | - | - |
| new_pattern_drift_down | new_pattern | ✓ | ✓ | ✓ | ✓ | ✓ | - | - |
| normal_single_sustained_scale | normal | ✓ | ✓ | ✓ | ✓ | ✓ | - | - |
| normal_weekly_after_reset | normal | ✓ | ✓ | ✓ | ✓ | ✓ | - | - |
| peak | peak | ✓ | ✓ | ✓ | ✓ | ✓ | - | - |
| peak_single_sustained_scale | peak | ✓ | ✓ | ✓ | ✓ | ✓ | - | - |

## Ebene 2: je Modell über alle Szenarien

| Modell | Szenarien erkannt | Abweichungstage | Vorfilter offen | Ausfalltage | Meldungen Kontrolllauf | unknown Kontrolllauf | Zurücksetzen Kontrolllauf |
|---|---|---:|---:|---:|---:|---:|---:|
| qwen3.5:9b | 2/2 | 15 | 74 | 0 | 11 | 0 | 5 |
| ministral-3:8b | 1/2 | 4 | 105 | 0 | 3 | 0 | 1 |
| Regel | 1/2 | 0 | 110 | 0 | 0 | 0 | 0 |
| qwen3:4b | 1/2 | 6 | 110 | 0 | 0 | 0 | 0 |
| qwen3:8b | 1/2 | 13 | 110 | 0 | 0 | 0 | 0 |
| gemma4:e4b | 1/2 | 5 | 110 | 0 | 0 | 0 | 0 |
| gemma4:e4b-mlx | 1/2 | 13 | 115 | 0 | 1 | 0 | 1 |

## Textprüfung je Modell, Antworten mit Verstoß oder fehlendem Beleg

| Modell | E1 Antworten | E1 Verstoß | E1 Beleg fehlt | E2 Antworten | E2 Verstoß | E2 Beleg fehlt |
|---|---:|---:|---:|---:|---:|---:|
| qwen3.5:9b | 10 | 0 | 1 | 74 | 0 | 0 |
| ministral-3:8b | 10 | 1 | 1 | 105 | 0 | 0 |
| qwen3:4b | 10 | 0 | 4 | 110 | 4 | 43 |
| qwen3:8b | 10 | 0 | 0 | 110 | 2 | 0 |
| gemma4:e4b | 0 | 0 | 0 | 110 | 2 | 0 |
| gemma4:e4b-mlx | 0 | 0 | 0 | 115 | 3 | 4 |

## Hinweise

- Ebene 1 prüft, ob ein Modell die Regeln aus dem Prompt nachvollzieht. Der Prompt wurde auf denselben Fällen verbessert, die Quoten begründen deshalb nur die Modellwahl und belegen nicht das Ziel von 80 % richtiger Klassen (dafür E2)
- wenige Fälle: ein Fall sind mehrere Prozentpunkte, eine Klasse hängt teils an einem einzigen Fall
- Macro-F1: Mittel der F1-Werte über die Klassen, die als erwartete Klasse vorkommen
- Grounding: Anteil der für den Fall erwarteten Felder, die das Modell als Beleg zitiert. Die Regel zitiert keine
- Ebene 2, erkannt: erwartete Klasse an einem Tag, an dem nur das Szenario den Vorfilter öffnet (gepaart mit dem Kontrolllauf desselben Modells)
- Ebene 2, Abweichungstage: gleiche Art und gleicher analysierter Tag, Regel gegen Modell. Nach einem Zurücksetzen an verschiedenen Tagen laufen die Reihen auseinander, spätere Abweichungen können daraus folgen
- Zeit: gemessen auf dem Rechner des Laufs, nur zum Vergleich der Modelle untereinander
- Textprüfung: Verstoß heißt, ein Steuerungswort oder eine Zahl, ein Datum oder eine Uhrzeit steht im Text, aber nicht im State des Falls. Zahlwörter („sechs Wochen“) findet sie nicht. Die Fensterlängen 7 und 28 aus der Skalenbeschreibung im Prompt gelten als erlaubt
- Beleg fehlt: der Prompt verlangt je Klasse bestimmte Pfade (new_pattern: sustained_drift, Streaks, peak und low: level, direction, absence: level, Kalendereintrag, measurement_error: Flag). Geprüft wird gegen die eigene Klasse des Modells, nicht gegen die erwartete. Ebene 1 wird nur für Läufe geprüft, die den State der Fälle in der Antwortdatei speichern, ältere Läufe haben in der Tabelle 0 Antworten
- Antworttexte, Abweichungstage, Erkennung je Szenario und Auffälligkeiten der Textprüfung stehen als CSV im Ordner des Laufs (answers_single, answers_sequence nur vom Produktivmodell, result_text_findings, sequence_events)
