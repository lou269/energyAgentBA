# energyAgentBA

Code zur Bachelorarbeit "Ein adaptiver Multi-Scale-Ansatz zur Prognose von Energieverbrauch auf Basis von Zeitreihen" (TU Berlin, DAI-Lab).

Ein Agent prognostiziert den Stromverbrauch eines Haushalts, erkennt Auffälligkeiten auf mehreren Zeitskalen (Tag, Woche, 30-Tage-Niveau), lässt sie von einem Sprachmodell einordnen und erklären und passt auf Basis dieser Einordnung seine eigene Trainingshistorie an. Gerechnet wird auf dem UK-DALE-Datensatz (Haus 1, Hauptzähler). Es gibt keine Hardware-Anbindung, der Agent wird auf historischen Daten Tag für Tag abgespielt.

## Aufbau

```
src/            der Agent und die Datenpipeline
experiments/    Experimente (E1–E4) und Komponentenstudien (K1–K4)
tests/          Unit- und Integrationstests
docs/           Diagramme (PlantUML) und Plot-Skripte
data/           UK-DALE-Rohdaten und HDF5 (nicht im Repo)
output/         Zwischenergebnisse der Datenpipeline (bereinigte Stundenreihen, Splits)
```

### `src/`

| Ordner | Aufgabe |
|---|---|
| `ingestion` | UK-DALE herunterladen und nach HDF5 konvertieren |
| `diagnostics` | Qualität der Messkanäle prüfen |
| `data_preparation` | Kandidaten auswählen, Kanäle aggregieren |
| `preprocessing` | Lücken behandeln, Plausibilität und Tagesqualität prüfen, Train/Test-Split |
| `numerical_analysis` | Anomalie-Scores (Z-Score) auf mehreren Skalen |
| `forecasting` | Prophet-Modell, Baselines, Walk-forward-Auswertung |
| `context` | Kalenderkontext (z. B. Abwesenheit) |
| `structured_state` | JSON-Zustand als Schnittstelle zum Sprachmodell |
| `llm` | Prompts, Aufruf über Ollama, Gate, Validierung, regelbasierter Vergleich |
| `adaption` | Policy, die aus der Klasse eine Aktion auf die Trainingshistorie macht |
| `pipeline` | Tageszyklus (`daily_cycle.py`) und Vergleichslauf (`comparison_harness.py`) |
| `evaluation` | Konsistenz- und Textprüfungen |
| `common` | geteilte Hilfsfunktionen |
| `config` | alle Parameter (`project_config.py`, `config_forecasting.py`, `config_nilmtk.py`) |

Alle Pfade stehen in `src/config/project_config.py`, alle Parameter in den Configs.

### `experiments/`

| Ordner | Inhalt |
|---|---|
| `e1_seasonality` | E1 Erkennung: werden Anomalien erkannt, auf welcher Skala |
| `e2_absence` | E2 Einordnung: richtige Klasse mit und ohne Kalenderkontext |
| `e3_system_compare` | E3 Anpassung: Vergleich der Systeme `SYS1`, `SYS2`, `SYS3` |
| `e4_cold_start` | E4 Kaltstart: Verhalten mit kurzer Historie, Prognose gegen statisches Modell |
| `k1_detection` | K1 Kalibrierung der Skalen-Schwellen |
| `k2_llm` | K2 Modellwahl und Prompt für die Einordnung |
| `k3_adaptation` | K3 Adaptionsstrategien |
| `k4_forecast_model` | K4 Prognosemodell (Retraining, Saisonalität) |
| `cutover_choice` | Termine der Standard-Cutover |
| `proactive_cycle` | Prototyp für einen Morgen-Ausblick, nicht Teil der Auswertung |
| `common` | geteilte Szenarien, Harness, Auswertung und Berichte |

Systemvarianten: `SYS1` ordnet per Regel ein und handelt nie, `SYS2` ordnet per Regel ein und handelt, `SYS3` ist der Agent mit Sprachmodell.

Jede Studie besteht aus `<id>_config.py`, `<id>_runner.py` (rechnet und schreibt `raw/`), `<id>_evaluation.py` und `<id>_report.py` (liest `raw/`, schreibt `ergebnis.md`).

## Installation

Es gibt zwei conda-Umgebungen, weil NILMTK nur mit Python 3.8 läuft.

```bash
conda env create -f environment-nilmtk.yml
```

```bash
conda env create -f environment-forecasting.yml
```

| Umgebung | Python | Wofür |
|---|---|---|
| `nilmtk-env` | 3.8 | `ingestion`, `diagnostics`, `data_preparation` und `e2_select_channels` |
| `forecasting-env` | 3.14 | alles ab `preprocessing`, alle Experimente, Tests |

Für die Läufe mit Sprachmodell wird [Ollama](https://ollama.com) gebraucht, das verwendete Modell steht in `src/config/config_forecasting.py`:

```bash
ollama pull ministral-3:8b
```

## Datenpipeline

Reihenfolge, jeweils aus dem Projektordner `energyAgentBA/` heraus. Die Rohdaten in `data/` sind nicht im Repo, die Ergebnisse der Pipeline in `output/` liegen dagegen bei.

```bash
conda activate nilmtk-env
python -m src.ingestion.ingestion_runner
python -m src.diagnostics.diagnostic_runner
python -m src.data_preparation.data_preparation_runner
```

```bash
conda activate forecasting-env
python -m src.preprocessing.preprocessing_runner
```

Die Ingestion lädt UK-DALE (April 2017, DOI `10.5286/UKERC.EDC.000004`) von CEDA und konvertiert nach `data/processed/ukdale.h5`. Mit `--overwrite` wird erneut geladen.

## Experimente ausführen

Die Kommandos stehen auch jeweils in der Kopfzeile des Runners. Läufe mit Sprachmodell brauchen eine laufende Ollama-Instanz (`open -a Ollama`).

```bash
conda activate forecasting-env
python -m experiments.e1_seasonality.e1_runner
python -m experiments.e1_seasonality.e1_report [run_directory]
```

E2 braucht vorher einmal die Kanalauswahl in `nilmtk-env`:

```bash
conda activate nilmtk-env
python -m experiments.e2_absence.e2_select_channels
```

```bash
conda activate forecasting-env
python -m experiments.e2_absence.e2_runner [full | precheck]
python -m experiments.e2_absence.e2_report [run_directory]
```

E3 und E4 laufen entsprechend:

```bash
python -m experiments.e3_system_compare.e3_runner
python -m experiments.e3_system_compare.e3_report [run_directory]
python -m experiments.e4_cold_start.e4_runner
python -m experiments.e4_cold_start.e4_report
```

Komponentenstudien:

```bash
python -m experiments.k1_detection.k1_runner
python -m experiments.k2_llm.k2_runner
python -m experiments.k3_adaptation.k3_runner [strategies | masking]
python -m experiments.k4_forecast_model.k4_runner [retraining | seasonality]
```

Ergebnisse landen in `experiments/output/<studie>/<studie>_NNN/` (Rohdaten in `raw/`, Bericht `ergebnis.md`, Tabellen und Plots in `user_output/`). Ohne Argument nimmt der Report den neuesten Lauf. Die Läufe mit Sprachmodell dauern lange, `caffeinate -i` davor verhindert den Ruhezustand.

Plots für die Arbeit erzeugen die Skripte in `docs/plots/` aus den Ergebnisordnern.

## Tests

```bash
python tests/run_tests.py
```

Das Skript führt jede Testgruppe in der passenden conda-Umgebung aus (Ingestion, Diagnostics, Data-Preparation in `nilmtk-env`, der Rest in `forecasting-env`). Einzelne Gruppen gehen auch direkt:

```bash
conda activate forecasting-env
python -m pytest tests/unit/llm
```

`tests/integration` enthält zwei Integrationstests: den Goldstandard-Lauf und den Kausalitätstest (keine Zukunftswerte im Zyklus).

## Hinweise

- Die Ergebnisse sind eine Einzelfallstudie.
- Läufe mit Sprachmodell lassen sich nicht garantiert bit-genau wiederholen. Die gespeicherten Läufe in `experiments/output/` liegen dem Repo bei.
