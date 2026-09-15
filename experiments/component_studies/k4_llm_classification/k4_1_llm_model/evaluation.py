# conda activate forecasting-env
# python -m experiments.component_studies.k4_llm_classification.k4_1_llm_model.evaluation

import argparse

import pandas as pd

from experiments.component_studies.k4_llm_classification.k4_1_llm_model.llm_model_config import K4_OUTPUT_ROOT
from src.pipeline.io import df_to_csv, find_run_directory


def load_results(run_number: int | None = None) -> pd.DataFrame:
    found = find_run_directory(K4_OUTPUT_ROOT, prefix="k4", number=run_number)

    if found is None:
        raise FileNotFoundError(f"No K4.1 run found in {K4_OUTPUT_ROOT} (requested number: {run_number}).")

    _, run_dir = found
    return pd.read_csv(run_dir / "results.csv")


def summarize_models(results: pd.DataFrame) -> pd.DataFrame:
    summary = results.groupby(["model_id", "model"], as_index=False).agg(
        n_attempts=("case_id", "count"),
        valid_rate=("valid", "mean"),
        accuracy=("correct", "mean"),
        mean_attempt_count=("attempt_count", "mean"),
        mean_generation_seconds=("generation_seconds", "mean"),
    )

    # stability_rate = Anteil der Fälle mit exakt einer eindeutigen Klassifikation über die Wiederholungen hinweg
    per_case_agreement = results.groupby(["model_id", "case_id"])["classification"].nunique(dropna=False)
    stability_rate = (per_case_agreement == 1).groupby("model_id").mean().rename("stability_rate")

    summary = summary.merge(stability_rate, on="model_id", how="left")

    return summary.sort_values("accuracy", ascending=False)


def summarize_cases(results: pd.DataFrame) -> pd.DataFrame:
    return results.groupby(["model_id", "case_id", "expected_classification"], as_index=False).agg(
        n_repetitions=("repetition", "count"),
        accuracy=("correct", "mean"),
        classifications=("classification", lambda values: ",".join(sorted(v for v in values if pd.notna(v)))),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Aggregate K4.1 model-comparison results.")
    parser.add_argument("--run", type=int, help="k4_<number> run to evaluate. Defaults to the latest one.")

    arguments = parser.parse_args()

    found = find_run_directory(K4_OUTPUT_ROOT, prefix="k4", number=arguments.run)

    if found is None:
        raise FileNotFoundError(f"No K4.1 run found in {K4_OUTPUT_ROOT} (requested number: {arguments.run}).")

    _, run_dir = found
    results = pd.read_csv(run_dir / "results.csv")

    model_comparison = summarize_models(results)
    df_to_csv(model_comparison, run_dir, "model_comparison")
    df_to_csv(summarize_cases(results), run_dir, "case_breakdown")

    print(model_comparison.to_string(index=False))


if __name__ == "__main__":
    main()
