from __future__ import annotations

import pandas as pd


def build_no_calendar_context() -> dict:
    """
    Simuliert einen Zustand ohne verfügbaren Kalenderkontext.
    """
    return {
        "calendar_available": False,
        "currently_absent": None,
        "events": [],
    }


def build_normal_calendar_context() -> dict:
    """
    Simuliert einen verfügbaren Kalender ohne relevantes Ereignis.
    """
    return {
        "calendar_available": True,
        "currently_absent": False,
        "events": [],
    }


def build_vacation_calendar_context(
    cutoff: pd.Timestamp,
) -> dict:
    """
    Simuliert einen Urlaub, der zum Forecast-Cutoff bereits läuft.
    """
    cutoff = pd.Timestamp(cutoff)

    vacation_start = (
        cutoff - pd.Timedelta(days=2)
    )

    vacation_end = (
        cutoff + pd.Timedelta(days=5)
    )

    return {
        "calendar_available": True,
        "currently_absent": True,
        "events": [
            {
                "type": "absence",
                "label": "vacation",
                "start": vacation_start.isoformat(),
                "end": vacation_end.isoformat(),
            }
        ],
    }