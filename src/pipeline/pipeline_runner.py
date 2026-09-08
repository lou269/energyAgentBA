# python -m src.pipeline.pipeline_runner

from __future__ import annotations

import subprocess

#from src.config.pipeline_config import PIPELINE_STAGES
from src.pipeline.pipeline_config_testing import PIPELINE_STAGES

def run_stage(module: str, environment: str, args: tuple[str, ...] = ()) -> None:
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
            *args,
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
            args=stage.args,
        )

    print("\nPipeline completed successfully.")


if __name__ == "__main__":
    main()