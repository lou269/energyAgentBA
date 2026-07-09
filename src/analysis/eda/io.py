from pathlib import Path

import pandas as pd


def df_to_csv(df: pd.DataFrame, output_path: Path, filename: str) -> None:
    """
    Save a DataFrame to a CSV file.

    Parameters
    ----------
    df : pd.DataFrame
        The DataFrame to save.
    output_path : Path
        The directory where the CSV file will be saved.
    filename : str
        The name of the CSV file (without extension).
    """
    output_file = output_path / f"{filename}.csv"
    df.to_csv(output_file, index=False)