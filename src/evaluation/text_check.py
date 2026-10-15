import re
from collections.abc import Collection, Mapping
from dataclasses import dataclass

import pandas as pd

ISO_TIMESTAMP = re.compile(r"\d{4}-\d{2}-\d{2}(?:T[\d:.+\-Z]+)?")
MONTHS = (
    "Januar|Februar|März|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember"
)
DATE_IN_TEXT = re.compile(r"\b(\d{1,2})\.(\d{1,2})\.(\d{4})?")
DAY_AND_MONTH_IN_TEXT = re.compile(
    rf"\b(\d{{1,2}})\.(?:[^\d]{{1,20}}?(\d{{1,2}})\.)?\s+(?:{MONTHS})"
)
TIME_IN_TEXT = re.compile(r"\b(\d{1,2}):(\d{2})\b")
NUMBER_IN_TEXT = re.compile(r"\d+(?:[.,]\d+)?")


@dataclass(frozen=True)
class TextViolation:
    kind: str
    found: str


def collect_state_values(state: Mapping[str, object]) -> tuple[set[float], set[int]]:
    quantities: set[float] = set()
    date_parts: set[int] = set()
    _collect(state, quantities, date_parts)

    return quantities, date_parts


def find_violations(
    text: str,
    *,
    quantities: Collection[float],
    date_parts: Collection[int],
    control_words: Collection[str],
    number_tolerance: float,
    rounding_step: float,
    prompt_numbers: Collection[float] = (),
) -> tuple[TextViolation, ...]:
    lowered = text.lower()
    violations = [
        TextViolation("control", word)
        for word in control_words
        if re.search(rf"\b{re.escape(word)}", lowered)
    ]

    for pattern in (DATE_IN_TEXT, DAY_AND_MONTH_IN_TEXT, TIME_IN_TEXT):
        for match in pattern.finditer(text):
            for part in match.groups():
                if part is not None and int(part) not in date_parts:
                    violations.append(TextViolation("number", match.group(0)))
                    break
        text = pattern.sub(" ", text)

    known_values = [*quantities, *prompt_numbers]
    for match in NUMBER_IN_TEXT.findall(text):
        value = float(match.replace(",", "."))
        # „etwa 70 %“ bei 71 %: eine auf rounding_step gerundete Zahl darf bis zur halben Stufe abweichen
        tolerance = (
            rounding_step / 2 if value % rounding_step == 0 else number_tolerance
        )
        if not any(abs(value - known) <= tolerance for known in known_values):
            violations.append(TextViolation("number", match))

    return tuple(violations)


def _collect(value: object, quantities: set[float], date_parts: set[int]) -> None:
    if isinstance(value, Mapping):
        for nested in value.values():
            _collect(nested, quantities, date_parts)
    elif isinstance(value, list):
        # Anzahl der Einträge ist eine erlaubte Zahl, etwa „zwei Skalen“
        quantities.add(float(len(value)))
        for nested in value:
            _collect(nested, quantities, date_parts)
    elif isinstance(value, bool):
        return
    elif isinstance(value, (int, float)):
        quantities.add(abs(float(value)))
    elif isinstance(value, str) and ISO_TIMESTAMP.fullmatch(value):
        stamp = pd.Timestamp(value)
        date_parts.update(
            {stamp.year, stamp.month, stamp.day, stamp.hour, stamp.minute}
        )
