# python -m src.pipeline.runner

from __future__ import annotations

import subprocess

from src.pipeline.pipeline_config import PIPELINE_STAGES


def run_stage(module: str, environment: str) -> None:
    subprocess.run(
        [
            "conda",
            "run",
            "--no-capture-output",
            "-n",
            environment,
            "python",
            "-m",
            module,
        ],
        check=True,
    )


def main() -> None:
    for stage in PIPELINE_STAGES:
        print(
            f"\n=== {stage.name} "
            f"[{stage.environment}] ==="
        )

        run_stage(
            module=stage.module,
            environment=stage.environment,
        )

    print("\nPipeline completed successfully.")


if __name__ == "__main__":
    main()