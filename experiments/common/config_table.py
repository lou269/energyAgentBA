# conda activate forecasting-env
# python -m experiments.common.config_table

import dataclasses
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from experiments.common.standard_config import StandardScenarioConfig
from experiments.cutover_choice.cc_config import CcConfig
from experiments.e1_seasonality.e1_config import E1Config
from experiments.e2_absence.e2_config import E2Config
from experiments.e3_system_compare.e3_config import E3Config
from experiments.e4_cold_start.e4_config import E4Config
from experiments.k1_detection.k1_config import K1Config
from experiments.k2_llm.k2_config import K2Config
from experiments.k3_adaptation.k3_config import K3Config
from experiments.k4_forecast_model.k4_config import K4Config
from src.config.config_forecasting import (
    SPLITS,
    SYS_VARIANTS,
    ComparisonConfig,
    CycleConfig,
    ForecastingConfig,
    NumericalAnalysisConfig,
    PreprocessingConfig,
    TextCheckConfig,
)
from src.config.config_nilmtk import DataPreparationConfig, DiagnosticsConfig

from src.config.project_config import ProjectConfig

config_table_file: Path = ProjectConfig().project_root / "docs" / "config_tabellen.tex"

LATEX_ESCAPES = str.maketrans(
    {
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
        "\\": r"\textbackslash{}",
    }
)


def escape(text: str) -> str:
    return text.translate(LATEX_ESCAPES)


def name_cell(name: str) -> str:
    return escape(name).replace(".", ".\\allowbreak{}")


def is_hidden(value: Any) -> bool:
    return isinstance(value, Path) or (
        isinstance(value, str) and value.startswith("http")
    )


def format_value(value: Any) -> str:
    if value is None or (isinstance(value, (tuple, list)) and not value):
        return "--"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return str(value).replace(".", "{,}")
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        return escape(value)
    if dataclasses.is_dataclass(value):
        return (
            "("
            + ", ".join(
                f"{escape(field.name)} {format_value(getattr(value, field.name))}"
                for field in dataclasses.fields(value)
            )
            + ")"
        )
    if isinstance(value, Mapping):
        parts = []
        for key, item in value.items():
            text = format_value(item)
            parts.append(
                f"{format_value(key)}: [{text}]"
                if isinstance(item, Mapping)
                else f"{format_value(key)}: {text}"
            )
        return "; ".join(parts)
    return ", ".join(
        (
            f"({format_value(item)})"
            if isinstance(item, (tuple, list))
            else format_value(item)
        )
        for item in value
    )


def flatten(config: Any, prefix: str = "") -> dict[str, Any]:
    rows: dict[str, Any] = {}
    for field in dataclasses.fields(config):
        value = getattr(config, field.name)
        if is_hidden(value):
            continue
        if dataclasses.is_dataclass(value):
            rows.update(flatten(value, f"{prefix}{field.name}."))
        else:
            rows[f"{prefix}{field.name}"] = value
    return rows


def build_table(title: str, rows: Mapping[str, Any]) -> str:
    lines = [rf"\begin{{konfig}}{{{title}}}"]
    for name, value in rows.items():
        lines.append(rf"{name_cell(name)} & {format_value(value)} \\")
    lines.append(r"\end{konfig}")
    return "\n".join(lines)


def build_variant_table(title: str, variants: Mapping[str, Any]) -> str:
    flat = {label: flatten(config) for label, config in variants.items()}
    own_fields = {field.name for field in dataclasses.fields(CycleConfig)}
    names = [name for label in flat for name in flat[label]]
    names = [
        name
        for name in dict.fromkeys(names)
        if all(name in flat[label] for label in flat)
        and name in own_fields
        or len({str(flat[label][name]) for label in flat if name in flat[label]}) > 1
    ]
    label = title.lower().replace("_", "")
    caption = (
        rf"Systemvarianten (\texttt{{{escape(title)}}}), "
        r"Schalter der \texttt{CycleConfig} und Unterschiede"
    )
    header = " & ".join(["Parameter", *(escape(variant) for variant in flat)])
    lines = [
        rf"\begin{{konfigvar}}{{{caption}}}{{tab:cfg-{label}}}{{{len(flat)}}}{{{header}}}"
    ]
    for name in names:
        cells = [format_value(flat[label].get(name)) for label in flat]
        lines.append(" & ".join([name_cell(name), *cells]) + r" \\")
    lines.append(r"\end{konfigvar}")
    return "\n".join(lines)


def build_all_tables() -> str:
    configs = [
        ProjectConfig(),
        PreprocessingConfig(),
        NumericalAnalysisConfig(),
        ForecastingConfig(),
        SYS_VARIANTS["SYS3"].llm_config,
        TextCheckConfig(),
        ComparisonConfig(),
        DiagnosticsConfig(),
        DataPreparationConfig(),
        StandardScenarioConfig(),
        CcConfig(),
        E1Config(),
        E2Config(),
        E3Config(),
        E4Config(),
        K1Config(),
        K2Config(),
        K3Config(),
        K4Config(),
    ]
    tables = [build_table(type(config).__name__, flatten(config)) for config in configs]
    tables.insert(1, build_table("SplitDefinition", dict(SPLITS)))
    tables.append(build_variant_table("SYS_VARIANTS", SYS_VARIANTS))

    return "\n\n".join(tables) + "\n"


def main() -> None:
    config_table_file.parent.mkdir(parents=True, exist_ok=True)
    config_table_file.write_text(build_all_tables(), encoding="utf-8")


if __name__ == "__main__":
    main()
