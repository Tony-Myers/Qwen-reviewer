import unittest

from app import review_pipeline as rp


def eligibility(state, authority_ids):
    return {
        "assessment_type": "methodological_appraisal_eligibility",
        "candidate_id": "paper.pdf:chunk-1:candidate-1",
        "state": state,
        "authority_ids": authority_ids,
    }


class MethodologicalAppraisalGateTests(unittest.TestCase):

    def test_interpretation_proceeds(self):
        result = rp.methodological_appraisal_gate_decision(
            eligibility(
                "ELIGIBLE_INTERPRETATION",
                ["candidate:semantic-2"],
            )
        )
        self.assertEqual(
            result["decision"],
            "PROCEED_TO_APPRAISAL",
        )

    def test_source_conflict_proceeds(self):
        result = rp.methodological_appraisal_gate_decision(
            eligibility(
                "ELIGIBLE_SOURCE_CONFLICT",
                ["P1"],
            )
        )
        self.assertEqual(
            result["decision"],
            "PROCEED_TO_APPRAISAL",
        )

    def test_no_proposition_is_withheld(self):
        result = rp.methodological_appraisal_gate_decision(
            eligibility(
                "NO_APPRAISAL_PROPOSITION",
                [],
            )
        )
        self.assertEqual(
            result["decision"],
            "WITHHELD_NO_APPRAISAL_PROPOSITION",
        )

    def test_no_source_resolution_is_withheld(self):
        result = rp.methodological_appraisal_gate_decision(
            eligibility(
                "NO_SOURCE_RESOLUTION",
                [],
            )
        )
        self.assertEqual(
            result["decision"],
            "WITHHELD_NO_SOURCE_RESOLUTION",
        )

    def test_eligible_state_requires_authority(self):
        with self.assertRaises(ValueError):
            rp.methodological_appraisal_gate_decision(
                eligibility(
                    "ELIGIBLE_INTERPRETATION",
                    [],
                )
            )

    def test_withheld_state_rejects_authority(self):
        with self.assertRaises(ValueError):
            rp.methodological_appraisal_gate_decision(
                eligibility(
                    "NO_APPRAISAL_PROPOSITION",
                    ["candidate:semantic-2"],
                )
            )


if __name__ == "__main__":
    unittest.main()
