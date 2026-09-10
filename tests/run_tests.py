# python tests/run_tests.py
#
# Führt jede Test-Gruppe in der conda-Env aus, unter der ihre src/-Module auch laufen

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class TestGroup:
    environment: str
    paths: tuple[str, ...]


TEST_GROUPS = [
    TestGroup(
        environment="nilmtk-env",
        paths=(
            "tests/unit/ingestion",
            "tests/unit/analysis",
            "tests/unit/data_preparation",
        ),
    ),
    TestGroup(
        environment="forecasting-env",
        paths=(
            "tests/unit/preprocessing",
            "tests/unit/numerical_analysis",
            "tests/unit/forecasting",
            "tests/unit/context",
            "tests/unit/structured_state",
            "tests/unit/llm",
            "tests/unit/adaption",
            "tests/unit/pipeline",
            "tests/unit/evaluation",
            "tests/unit/user_profile",
            "tests/unit/config",
        ),
    ),
]


def run_group(group: TestGroup) -> int:
    print(f"\n=== {group.environment} ===")

    result = subprocess.run(
        [
            "conda", "run", "--no-capture-output", "-n", group.environment,
            "python", "-m", "pytest", *group.paths,
        ],
        cwd=PROJECT_ROOT,
    )

    return result.returncode


def main() -> None:
    exit_code = 0

    for group in TEST_GROUPS:
        exit_code = run_group(group) or exit_code

    sys.exit(exit_code)


if __name__ == "__main__":
    main()