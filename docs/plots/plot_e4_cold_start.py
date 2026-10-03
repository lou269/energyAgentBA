from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.lines import Line2D

from docs.plots.plot_style import COLDSTART_COLORS, SCALE_COLORS, save_figure
from experiments.e4_cold_start.e4_evaluation import ALL_SCALES, SystemSummary
from src.structured_state.structured_state_schema import SCALE_NAMES

INJECTION_COLORS = {
    "same": "#54A24B",
    "other_class": "#F58518",
    "missed": "#E45756",
}
INJECTION_LABELS = {
    "same": "wie beim langen Kaltstart",
    "other_class": "andere Klasse",
    "missed": "verpasst",
}
SETTLING_LINES = {
    "notification_settling_day": ("Meldungen", ":"),
    "detection_settling_day": ("Erkennung", "--"),
    "classification_settling_day": ("Einordnung", "-."),
}


def build_e4_forecast_plot(
    gap_curve: pd.DataFrame,
    settling: pd.DataFrame,
    output_directory: Path,
    *,
    adaptive_model_id: str,
    static_model_id: str,
    smoothing_days: int,
) -> None:
    figure, axis = plt.subplots(figsize=(9, 4.5))

    for model_id, linestyle in ((adaptive_model_id, "-"), (static_model_id, "--")):
        model_curve = gap_curve.loc[gap_curve["model_id"].eq(model_id)]
        for coldstart_days in sorted(model_curve["coldstart_days"].unique()):
            line = model_curve.loc[model_curve["coldstart_days"].eq(coldstart_days)]
            axis.plot(
                line["day_since_start"],
                line["mae_gap_w_smoothed"],
                color=COLDSTART_COLORS[coldstart_days],
                linestyle=linestyle,
                linewidth=2 if model_id == adaptive_model_id else 1.2,
                label=f"{model_id}, Kaltstart {coldstart_days} Tage",
            )

    shortest = gap_curve["coldstart_days"].min()
    settling_day = settling.loc[
        settling["model_id"].eq(adaptive_model_id)
        & settling["coldstart_days"].eq(shortest),
        "settling_day",
    ].iloc[0]
    if pd.notna(settling_day):
        axis.axvline(settling_day, linestyle=":", linewidth=1)
        axis.annotate(
            f"eingeschwungen, {adaptive_model_id} {shortest} Tage",
            (settling_day, axis.get_ylim()[1]),
            xytext=(4, -12),
            textcoords="offset points",
            fontsize=8,
        )

    axis.axhline(0, linewidth=0.8)
    axis.set_title(
        f"MAE-Abstand zum längsten Kaltstart (Mittel über Starttermine, {smoothing_days} Tage geglättet)",
        loc="left",
    )
    axis.set_xlabel("Tage seit Start")
    axis.set_ylabel("MAE-Abstand (W)")
    axis.grid(axis="y", alpha=0.25)
    axis.legend(fontsize=8, ncols=2)

    save_figure(figure, output_directory, "e4_forecast_gap")


def build_e4_system_plot(
    system: SystemSummary,
    criteria: pd.DataFrame,
    output_directory: Path,
    *,
    shortest: int,
    longest: int,
    evaluation_days: int,
    scenario_labels: dict[str, str],
) -> None:
    figure, (scale_axis, gate_axis, injection_axis) = plt.subplots(
        3,
        1,
        figsize=(10, 7),
        sharex=True,
        gridspec_kw={"height_ratios": [1.2, 1, 0.8]},
    )

    first_days = (
        system.scale_days.loc[system.scale_days["coldstart_days"].eq(shortest)]
        .set_index("scale")["latest_day"]
        .to_dict()
    )
    for row, scale in enumerate(SCALE_NAMES):
        scale_axis.barh(
            row,
            evaluation_days - first_days[scale],
            left=first_days[scale],
            color=SCALE_COLORS[scale],
            height=0.6,
        )
    scale_axis.set_yticks(range(len(SCALE_NAMES)), SCALE_NAMES)
    scale_axis.invert_yaxis()
    scale_axis.set_title(
        f"Skalen mit Score bei {shortest} Tagen Kaltstart (ab dem spätesten Termin)",
        loc="left",
    )

    gate_axis.bar(
        system.gate_by_day["day_since_start"],
        system.gate_by_day["only_shortest"],
        color="#E45756",
        label=f"Gate offen nur bei {shortest} Tagen",
    )
    gate_axis.bar(
        system.gate_by_day["day_since_start"],
        -system.gate_by_day["only_longest"],
        color="#4C78A8",
        label=f"Gate offen nur bei {longest} Tagen",
    )
    resets = system.resets.loc[system.resets["coldstart_days"].eq(shortest)]
    gate_axis.scatter(
        resets["day_since_start"],
        [0] * len(resets),
        marker="x",
        s=80,
        zorder=4,
        label="Reset vor allen Skalen",
    )
    gate_axis.axhline(0, linewidth=0.8)
    gate_axis.set_ylabel("Termine")
    gate_axis.set_title("Saubere Tage mit abweichendem Gate", loc="left")
    gate_axis.legend(fontsize=8, loc="upper right")

    kinds = list(system.injection_by_day["scenario"].unique())
    for row, kind in enumerate(kinds):
        injections = system.injection_by_day.loc[
            system.injection_by_day["scenario"].eq(kind)
        ]
        status = injections["missed"].gt(0).map({True: "missed", False: "same"})
        status = status.where(
            ~(status.eq("same") & injections["class_deviation"].gt(0)), "other_class"
        )
        injection_axis.scatter(
            injections["injection_day"],
            [row] * len(injections),
            color=status.map(INJECTION_COLORS),
            s=70,
            zorder=3,
        )
    injection_axis.set_yticks(
        range(len(kinds)), [scenario_labels[kind] for kind in kinds]
    )
    injection_axis.set_ylim(-0.6, len(kinds) - 0.4)
    injection_axis.set_title(
        f"Eingebaute Tage bei {shortest} Tagen, gegenüber {longest} Tagen", loc="left"
    )
    injection_axis.legend(
        handles=[
            Line2D(
                [],
                [],
                marker="o",
                linestyle="",
                color=color,
                label=INJECTION_LABELS[key],
            )
            for key, color in INJECTION_COLORS.items()
        ],
        fontsize=8,
        loc="upper right",
    )

    settling = criteria.set_index("check")["value"]
    all_scales_day = first_days[ALL_SCALES]
    for axis in (scale_axis, gate_axis, injection_axis):
        axis.axvline(all_scales_day, linewidth=1, label="alle Skalen da")
        for check, (label, linestyle) in SETTLING_LINES.items():
            if pd.notna(settling[check]):
                axis.axvline(
                    settling[check],
                    color="#8C8C8C",
                    linestyle=linestyle,
                    linewidth=1,
                    label=f"eingeschwungen: {label}",
                )
        axis.grid(axis="x", alpha=0.25)

    injection_axis.set_xlim(-0.5, evaluation_days - 0.5)
    injection_axis.set_xlabel("Tage seit Start")
    # unten sind nur die senkrechten Linien Line2D, sie stehen für alle drei Achsen
    figure.legend(
        handles=injection_axis.get_lines(),
        fontsize=8,
        loc="lower center",
        ncols=4,
        bbox_to_anchor=(0.5, -0.03),
    )

    save_figure(figure, output_directory, "e4_system")
