from pathlib import Path

from matplotlib.figure import Figure
import matplotlib.pyplot as plt

SYSTEM_COLORS = {
    "SYS1": "#4C78A8",
    "SYS2": "#F58518",
    "SYS3": "#54A24B",
}
# C3 in Grüntönen, je länger das Fenster, desto dunkler
MODEL_COLORS = {
    "B1": "#B0B0B0",
    "B2": "#8C8C8C",
    "B3": "#4C78A8",
    "C1": "#F2CF5B",
    "C2": "#E45756",
    "C3_7": "#54A24B",
    "C3_30": "#3F7A38",
    "C3_60": "#2A5225",
    "S1": "#B279A2",
}
COLDSTART_COLORS = {7: "#54A24B", 14: "#3F7A38", 30: "#2A5225", 60: "#16301A"}
SCALE_COLORS = {
    "daily": "#4C78A8",
    "weekday": "#F58518",
    "weekly": "#B279A2",
    "long_term": "#54A24B",
}

CONTEXT_COLORS = {
    "SYS1": SYSTEM_COLORS["SYS1"],
    "SYS2": SYSTEM_COLORS["SYS2"],
    "SYS3_CTX0": "#E45756",
    "SYS3_CTX1": SYSTEM_COLORS["SYS3"],
    "SYS3_CTX2": "#B279A2",
}
CLASSIFICATION_COLORS = {
    "absence": "#54A24B",
    "new_pattern": "#E45756",
    "low": "#4C78A8",
    "peak": "#F58518",
    "unknown": "#B0B0B0",
}
REFERENCE_WINDOW_COLORS = {
    "REF_STATIC": "#4C78A8",
    "REF_EXPANDING": "#F58518",
    "REF_ROLL60": "#54A24B",
    "REF_ROLL35": "#B279A2",
}
STRATEGY_COLORS = {
    "cut": "#E45756",
    "step_regressor": "#4C78A8",
}


def save_figure(figure: Figure, output_directory: Path, name: str) -> None:
    # PNG für ergebnis.md, SVG für die Arbeit
    figure.savefig(str(output_directory / f"{name}.png"), dpi=300, bbox_inches="tight")
    figure.savefig(str(output_directory / f"{name}.svg"), bbox_inches="tight")
    plt.close(figure)
