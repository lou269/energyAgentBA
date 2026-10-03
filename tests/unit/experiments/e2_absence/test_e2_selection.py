# python -m pytest tests/unit/experiments/e2_absence/test_e2_selection.py -v

import pandas as pd

from experiments.e2_absence.e2_selection import channels_meeting_thresholds


def test_channels_meeting_thresholds_ignores_activity_share() -> None:
    # Spülmaschinen-Fall: niedrige activity_share, aber hohe coverage_share(-> soll trotzdem ausgesucht werden)
    ranking = pd.DataFrame(
        [
            {"meter_key": "H1_M6", "coverage_share": 1.0, "activity_share": 0.036},
            {"meter_key": "H1_M9", "coverage_share": 0.5, "activity_share": 0.3},
        ]
    )

    selected = channels_meeting_thresholds(ranking, min_coverage_share=0.9)

    assert selected.tolist() == [True, False]
