# conda activate forecasting-env
# python -m experiments.component_studies.k5_adaptation_strategies.k5_masking_analysis [run_directory]

import sys

import pandas as pd

from experiments.component_studies.k5_adaptation_strategies.k5_config import (
    K5_KIND_LABELS,
    K5_MASKED_CLASSIFICATIONS,
    K5_MASKING_EARLY_DAYS,
    K5_MASKING_PHASE_LABELS,
)
from experiments.component_studies.k5_adaptation_strategies.k5_masking_evaluation import (
    pair_masking,
    summarize_masking,
)
from experiments.shared_analysis import ALL_DAYS, SPREAD_LABELS, spread_over_repeats
from src.common.result_report import (
    format_commit,
    format_number,
    key_figures_table,
    write_result_report,
)
from src.config.project_config import ProjectConfig
from src.pipeline.io import (
    RAW_SUBDIR,
    read_raw_json,
    resolve_run_directory,
    user_output_directory,
)

HEADERS = {
    "kind": "Ereignis",
    "phase": "Zeitraum",
    "days": "Tage",
    "masked_days": "ausgeblendet",
    **SPREAD_LABELS,
}


def build_masking_table(summary: pd.DataFrame) -> pd.DataFrame:
    keys = ["kind", "phase"]
    table = spread_over_repeats(summary, keys, "mae_delta_w", count_same_direction=True)
    counts = summary.groupby(keys, as_index=False, sort=False).agg(
        days=("days", "sum"), masked_days=("masked_days", "sum")
    )

    return counts.merge(table, on=keys).sort_values("kind", kind="stable")


def _labeled(table: pd.DataFrame) -> pd.DataFrame:
    labeled = table.assign(
        kind=table["kind"].map(K5_KIND_LABELS),
        phase=table["phase"].map(K5_MASKING_PHASE_LABELS),
    )

    return labeled.rename(columns=HEADERS)


def build_key_figures(
    summary: pd.DataFrame, table: pd.DataFrame, decimals: int
) -> pd.DataFrame:
    overall = table.loc[table["phase"].eq(ALL_DAYS)]
    mae_replay = (
        summary.loc[summary["phase"].eq(ALL_DAYS)]
        .groupby("kind")["mae_replay_w"]
        .mean()
    )

    return key_figures_table(
        [
            (
                f"Ausblenden, Szenario {K5_KIND_LABELS[row['kind']]}: MAE-Differenz [W]",
                row["mean"],
                f"bei {format_number(mae_replay[row['kind']], decimals)} W ohne Ausblenden, "
                f"{row['masked_days']} von {row['days']} Tagen ausgeblendet, gleiche Richtung {row['same_direction']}",
            )
            for row in overall.to_dict("records")
        ]
    )


def main() -> None:
    project_config = ProjectConfig()
    decimals = project_config.result_decimals

    run_directory = resolve_run_directory(
        project_config.k5_output_dir,
        "k5_mask",
        sys.argv[1] if len(sys.argv) > 1 else None,
    )
    run_config = read_raw_json(run_directory, "run_config")

    results = pd.read_csv(
        run_directory / RAW_SUBDIR / "k5_mask_results.csv", dtype={"cutover_date": str}
    )
    decisions = pd.read_csv(
        run_directory / RAW_SUBDIR / "k5_mask_decisions.csv",
        dtype={"cutover_date": str},
    )

    paired = pair_masking(results, decisions, K5_MASKED_CLASSIFICATIONS)
    summary = summarize_masking(paired, K5_MASKING_EARLY_DAYS)
    table = build_masking_table(summary)

    output_directory = user_output_directory(run_directory)
    write_result_report(
        output_directory,
        title=f"K5 Teil 2, {'/'.join(K5_MASKED_CLASSIFICATIONS)} für Prophet ausblenden, Lauf {run_directory.name}",
        setup={
            "Cutover": ", ".join(run_config["k3_config"]["cutover_dates"]),
            "Entscheidungen": "SYS2, danach zweimal nachgespielt: nur Resets (replay) und zusätzlich ausgeblendet (mask)",
            "Commit": format_commit(run_config["code_version"]),
        },
        tables={
            "key_figures": ("Kennzahlen", build_key_figures(summary, table, decimals)),
            "result_masking": (
                "MAE mask minus replay je Cutover [W], negativ = besser",
                _labeled(table),
            ),
        },
        notes=[
            f"replay trifft SYS2 an {format_number(paired['replay_matches_sys2'].mean() * 100, decimals)} % der Tage"
        ],
        images=[],
        decimals=decimals,
    )

    print(f"Result written to {output_directory / 'ergebnis.md'}")


if __name__ == "__main__":
    main()
