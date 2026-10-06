# conda activate forecasting-env
# python -m experiments.common.data_overview

# Kennzahlen der echten Daten für die Beschreibung der Datenbasis, schreibt experiments/output/data_overview.md

from dataclasses import dataclass, field

import pandas as pd

from experiments.common.evaluation import local_dates, summarize_scenario_real_data
from experiments.common.report import markdown_table
from experiments.common.scenarios import load_target
from experiments.common.standard_config import (
    LOCAL_TIMEZONE,
    PROJECT_CONFIG,
    STANDARD_CONFIG,
)
from src.common.channel_tables import load_channel_tables
from src.pipeline.io import read_split_bounds, write_text_atomic

OVERVIEW_FILE = "data_overview.md"


@dataclass(frozen=True)
class DataOverviewConfig:
    # Abschnitte, über die das Fenster gelesen wird (validation liegt im Fenster development)
    window_labels: dict[str, str] = field(
        default_factory=lambda: {"validation": "development", "test": "test"}
    )
    daily_quantiles: tuple[float, float] = (0.05, 0.95)
    # Quantil echter Tage, an dem level und peak im Katalog liegen, Abweichung gegen den Median der Tage davor wie in 5.2
    catalog_quantile: float = 0.99
    reference_days: int = 28
    # Monat vor und nach dem echten Herbstanstieg je Abschnitt
    autumn_months: dict[str, tuple[str, str]] = field(
        default_factory=lambda: {
            "validation": ("2014-08", "2014-10"),
            "test": ("2016-08", "2016-10"),
        }
    )


def summarize_houses() -> pd.DataFrame:
    quality = load_channel_tables(PROJECT_CONFIG)[1]
    mains = quality.loc[quality["is_mains"]]

    return pd.DataFrame(
        {
            "Haus": mains["house"],
            "Tage": mains["duration_days"],
            "Abdeckung in %": 100 * mains["sampling_share"],
        }
    )


def summarize_window(split: str, label: str, config: DataOverviewConfig) -> dict:
    series, imputed, implausible = load_target(split)
    daily = series.groupby(local_dates(series.index)).mean()
    missing_days = series.isna().groupby(local_dates(series.index)).any()
    hourly_profile = series.groupby(
        pd.DatetimeIndex(series.index).tz_convert(LOCAL_TIMEZONE).hour
    ).mean()
    weekdays = pd.DatetimeIndex(daily.index).dayofweek
    workdays = daily[weekdays < 5].mean()
    weekend = daily[weekdays >= 5].mean()
    low, high = config.daily_quantiles
    real_data = summarize_scenario_real_data(
        series,
        reference_days=config.reference_days,
        peak_hours=STANDARD_CONFIG.peak_hours,
        quantile=config.catalog_quantile,
        autumn_months=config.autumn_months[split],
    )
    # daneben die Stärke im Katalog
    quantile = f"{config.catalog_quantile:.0%}-Quantil"
    level_label = (
        f"Tagesmittel über Median der Vortage, {quantile} in W "
        f"(level +{STANDARD_CONFIG.level_extra_w:.0f})"
    )
    peak_label = (
        f"stärkster {STANDARD_CONFIG.peak_hours}-h-Block über Median derselben Stunde, "
        f"{quantile} in W (peak +{STANDARD_CONFIG.peak_extra_w:.0f})"
    )

    return {
        "Fenster": label,
        "Tage": len(daily),
        "Stunden": len(series),
        "fehlende Stunden": int(series.isna().sum()),
        "Tage mit Lücke": int(missing_days.sum()),
        "aufgefüllte Stunden": int(imputed.sum()),
        "markierte Stunden": int(implausible.sum()),
        "Stundenmittel in W": series.mean(),
        "Streuung in W": series.std(),
        "Variationskoeffizient in %": 100 * series.std() / series.mean(),
        "Tagesmittel in W": daily.mean(),
        f"Tagesmittel {low:.0%}-Quantil in W": daily.quantile(low),
        f"Tagesmittel {high:.0%}-Quantil in W": daily.quantile(high),
        "ruhigste Stunde (Uhr)": hourly_profile.idxmin(),
        "Last in der ruhigsten Stunde in W": hourly_profile.min(),
        "lauteste Stunde (Uhr)": hourly_profile.idxmax(),
        "Last in der lautesten Stunde in W": hourly_profile.max(),
        "Werktag in W": workdays,
        "Wochenende in W": weekend,
        "Wochenende gegen Werktag in %": 100 * (weekend / workdays - 1),
        "Tage mit Median der Vortage": int(real_data["evaluable_days"]),
        level_label: real_data["level_w"],
        peak_label: real_data["peak_w"],
        "Herbstanstieg Aug bis Okt in %": real_data["autumn_rise_pct"],
        **{
            f"Monatsmittel {month:02d} in W": value
            for month, value in daily.groupby(pd.DatetimeIndex(daily.index).month)
            .mean()
            .items()
        },
    }


def main() -> None:
    config = DataOverviewConfig()
    # object, damit Zählungen in der Tabelle keine Nachkommastelle bekommen
    windows = pd.DataFrame(
        [
            summarize_window(split, label, config)
            for split, label in config.window_labels.items()
        ],
        dtype=object,
    ).set_index("Fenster")
    development_end = read_split_bounds(PROJECT_CONFIG, "validation")[1]
    test_start = read_split_bounds(PROJECT_CONFIG, "test")[0]

    lines = [
        "# Kennzahlen der Datenbasis",
        "",
        "## Hauptzähler je Haus",
        "",
        markdown_table(summarize_houses(), 1),
        "",
        f"Datenlücke zwischen den Fenstern: {(test_start - development_end).days} Tage",
        "",
        "## Fenster",
        "",
        markdown_table(windows.T.reset_index(names="Kennzahl"), 1),
    ]
    target = PROJECT_CONFIG.experiment_output_dir / OVERVIEW_FILE
    write_text_atomic("\n".join(lines) + "\n", target)
    print(f"Written to {target}")


if __name__ == "__main__":
    main()
