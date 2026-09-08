from __future__ import annotations

from collections.abc import Mapping
from numbers import Real
from typing import TypeGuard


def validate_fields(
    value: Mapping[str, object],
    expected: frozenset[str],
    name: str,
) -> None:
    missing = expected.difference(value)
    unexpected = set(value).difference(expected)

    if missing:
        raise ValueError(f"{name} is missing required fields: " + ", ".join(sorted(missing)))

    if unexpected:
        raise ValueError(f"{name} contains unexpected fields: " + ", ".join(sorted(str(field) for field in unexpected)))


def is_real_number(value: object) -> TypeGuard[Real]:
    return not isinstance(value, bool) and isinstance(value, Real)
