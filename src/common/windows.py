from src.config.config_forecasting import SPLITS


def window_names() -> list[str]:
    return list(dict.fromkeys(definition.window for definition in SPLITS.values()))


def window_splits(window: str) -> dict[str, int | None]:
    return {
        split: definition.days
        for split, definition in SPLITS.items()
        if definition.window == window
    }
