from dataclasses import dataclass
from pathlib import Path

RUN_PREFIX = "cc"
# vom Runner geschrieben
RESULTS_FILE = "cc_windows"


@dataclass(frozen=True)
class CcConfig:
    # Unterordner von experiment_output_dir
    output_subdir: Path = Path("cutover_choice")
    # Abstand der Kandidaten-Cutover
    step_days: int = 1
