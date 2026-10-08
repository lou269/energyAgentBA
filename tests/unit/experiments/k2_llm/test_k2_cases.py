# python -m pytest tests/unit/experiments/k2_llm/test_k2_cases.py -v

from experiments.k2_llm.k2_cases import EXPECTED_EVIDENCE_PATHS, llm_relevant_cases
from src.evaluation.consistency import missing_evidence_paths
from src.llm.validation import collect_scalar_evidence_paths
from src.structured_state.structured_state_schema import validate_structured_state


def test_cases_and_evidence() -> None:
    for case in llm_relevant_cases():
        validate_structured_state(case.state)
        expected = EXPECTED_EVIDENCE_PATHS[case.case_id]

        # die Fälle dürfen nur Pfade erwarten, die es im State gibt und die der Beleg-Prüfung genügen
        assert expected <= set(collect_scalar_evidence_paths(case.state))
        assert (
            missing_evidence_paths(case.expected_classification, expected, case.state)
            == ()
        )
