# conda activate forecasting-env
# python -m experiments.proactive_cycle.pc_report [run_directory]

import pandas as pd

from experiments.common.report import (
    answer_bullets,
    format_commit,
    format_number,
    key_figures_table,
    relabel,
    write_result_report,
)
from experiments.common.standard_config import PROJECT_CONFIG, STANDARD_CONFIG
from experiments.proactive_cycle.pc_config import (
    OUTLOOK_FILE,
    RATING_TEMPLATE_FILE,
    RUN_PREFIX,
)
from experiments.proactive_cycle.pc_evaluation import (
    ProactiveCycleSummary,
    build_rating_export,
    summarize_outlook,
)
from src.config.config_forecasting import TextCheckConfig
from src.pipeline.io import (
    RAW_SUBDIR,
    df_to_csv,
    read_jsonl,
    read_raw_json,
    run_directory_from_argv,
    user_output_directory,
)

DAY_HEADERS = {
    "day": "Tag",
    "weekday": "Wochentag",
    "forecast_kwh": "Prognose [kWh]",
    "usual_kwh": "üblich [kWh]",
    "deviation_pct": "Abweichung [%]",
    "violations": "Regelverstöße",
}

WEEKDAY_LABELS = {
    "Monday": "Montag",
    "Tuesday": "Dienstag",
    "Wednesday": "Mittwoch",
    "Thursday": "Donnerstag",
    "Friday": "Freitag",
    "Saturday": "Samstag",
    "Sunday": "Sonntag",
}


RATING_CRITERIA = ["verständlich", "Empfehlung sinnvoll", "Prognose sinnvoll genutzt"]


def build_setup(run_config: dict, summary: ProactiveCycleSummary) -> dict[str, str]:
    config = run_config["proactive_cycle_config"]
    llm_config = config["llm_config"]

    return {
        "Modell": f"{llm_config['model']}, Prompt {llm_config['prompt_version']}, temperature {format_number(llm_config['temperature'], 1)}",
        "Prognose": f"{config['cycle_system']} ohne Adaption und ohne Aufruf 1, ohne Kalender",
        "Tage": f"{summary.day_count} ab {config['cutover_date']} ({run_config['standard_config']['split']})",
        "Commit": format_commit(run_config["code_version"]),
    }


def build_key_figures(summary: ProactiveCycleSummary) -> pd.DataFrame:
    return key_figures_table(
        [
            ("Gültige Antworten", summary.validity_percent, "% der Tage"),
            (
                "Regelverstöße",
                summary.violation_count,
                "Tage (Steuerung, State-fremde Zahlen und Daten)",
            ),
        ]
    )


def answer_lines(days: pd.DataFrame, decimals: int) -> list[str]:
    lines: list[str] = []
    for _, row in days.iterrows():
        comparison = (
            "kein üblicher Wert verfügbar"
            if pd.isna(row["usual_kwh"])
            else f"üblich {format_number(row['usual_kwh'], decimals)} kWh, "
            f"Abweichung {format_number(row['deviation_pct'], decimals)} %"
        )
        lines += [
            f"**{row['day']}, {WEEKDAY_LABELS[row['weekday']]}**: Prognose "
            f"{format_number(row['forecast_kwh'], decimals)} kWh, {comparison}",
            "",
        ]
        if row["valid"]:
            lines += answer_bullets(
                row["explanation"], row["user_recommendation"], row["uncertainty"]
            )
            if row["violations"]:
                lines.append(f"- Regelverstöße: {row['violations']}")
        else:
            lines.append(f"- ungültig ({row['error']})")
        lines.append("")

    return lines


def main() -> None:
    run_directory = run_directory_from_argv(
        PROJECT_CONFIG.proactive_cycle_output_dir, RUN_PREFIX
    )
    run_config = read_raw_json(run_directory, "run_config")
    text_check_config = TextCheckConfig()

    summary = summarize_outlook(
        read_jsonl(run_directory / RAW_SUBDIR / OUTLOOK_FILE),
        control_words=text_check_config.control_words,
        number_tolerance=text_check_config.number_tolerance,
        rounding_step=text_check_config.rounding_step,
    )
    output_directory = user_output_directory(run_directory)

    rating = build_rating_export(
        summary.days, seed=run_config["proactive_cycle_config"]["rating_seed"]
    )
    for name in RATING_CRITERIA:
        rating[name] = ""
    df_to_csv(rating, output_directory, RATING_TEMPLATE_FILE)

    write_result_report(
        output_directory,
        title=f"Proaktiver Zyklus, Morgen-Ausblick, Lauf {run_directory.name}",
        setup=build_setup(run_config, summary),
        tables={
            "key_figures": ("Kernzahlen", build_key_figures(summary)),
            "outlook_days": (
                "Ausblick je Tag",
                relabel(
                    summary.days[list(DAY_HEADERS)],
                    DAY_HEADERS,
                    value_labels={"weekday": WEEKDAY_LABELS},
                ),
            ),
        },
        notes=[
            "Gemessen wird nur der Text gegen den State. Eine Eintreffquote gegen die Ist-Werte misst die Prognose und nicht das LLM, sie fehlt bewusst.",
            f"Erklärungsbewertung (verständlich, Empfehlung sinnvoll, Prognose sinnvoll genutzt): verblindeter Export in {RATING_TEMPLATE_FILE}.csv.",
            "Die Prognose enthält keine Wirkung der Adaption, der Zyklus läuft ohne Aufruf 1.",
        ],
        images=[],
        decimals=STANDARD_CONFIG.decimals,
        appendix_text=[
            ("Antworten je Tag", answer_lines(summary.days, STANDARD_CONFIG.decimals))
        ],
    )

    print(f"Result written to {output_directory / 'ergebnis.md'}")


if __name__ == "__main__":
    main()
