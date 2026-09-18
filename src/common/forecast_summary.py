from collections.abc import Sequence


def mean_and_peak(predictions: Sequence[float]) -> tuple[float, float]:
    return sum(predictions) / len(predictions), max(predictions)


def mean_interval_width(interval_widths: Sequence[float]) -> float | None:
    if not interval_widths:
        return None

    return sum(interval_widths) / len(interval_widths)
