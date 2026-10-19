import unittest

from app import review_pipeline as rp


class OraclePremiseSuiteTests(unittest.TestCase):

    def test_five_resolution_states_are_accepted(self):
        for state in (
            "ANSWERED",
            "PARTIAL",
            "CONFLICTING",
            "NOT_LOCATED",
            "INSUFFICIENT_ACCESS",
        ):
            residual = (
                "A consequential residual remains."
                if state in {"PARTIAL", "CONFLICTING"}
                else ""
            )
            records = [{
                "premise_id": "P1",
                "status": state,
                "source_answer": "Source answer.",
                "residual_question": residual,
            }]
            validated = rp.validate_oracle_premise_records(records)
            self.assertEqual(validated[0]["status"], state)

    def test_invalid_resolution_state_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Invalid oracle"):
            rp.validate_oracle_premise_records([{
                "premise_id": "P1",
                "status": "MISSING",
                "source_answer": "",
                "residual_question": "",
            }])

    def test_answered_cannot_retain_residual(self):
        with self.assertRaisesRegex(ValueError, "ANSWERED"):
            rp.validate_oracle_premise_records([{
                "premise_id": "P1",
                "status": "ANSWERED",
                "source_answer": "The manuscript specifies it.",
                "residual_question": "But perhaps it does not.",
            }])

    def test_partial_requires_residual(self):
        with self.assertRaisesRegex(ValueError, "require"):
            rp.validate_oracle_premise_records([{
                "premise_id": "P1",
                "status": "PARTIAL",
                "source_answer": "Partly answered.",
                "residual_question": "",
            }])

    def test_not_located_does_not_become_omission(self):
        records = [{
            "premise_id": "P1",
            "status": "NOT_LOCATED",
            "source_answer": "",
            "residual_question": "",
        }]
        result = rp.build_oracle_premise_concerns(
            records,
            {"concerns": []},
        )
        self.assertEqual(result["eligible_premise_ids"], [])

    def test_insufficient_access_does_not_become_omission(self):
        records = [{
            "premise_id": "P1",
            "status": "INSUFFICIENT_ACCESS",
            "source_answer": "Relevant source section was unavailable.",
            "residual_question": "",
        }]
        result = rp.build_oracle_premise_concerns(
            records,
            {"concerns": []},
        )
        self.assertEqual(result["eligible_premise_ids"], [])

    def test_duplicate_premise_id_is_rejected(self):
        record = {
            "premise_id": "P1",
            "status": "ANSWERED",
            "source_answer": "Resolved.",
            "residual_question": "",
        }
        with self.assertRaisesRegex(ValueError, "Duplicate"):
            rp.validate_oracle_premise_records([record, dict(record)])

    def test_conflicting_premise_is_concern_eligible(self):
        records = [{
            "premise_id": "P1",
            "status": "CONFLICTING",
            "source_answer": (
                "The stated quantities are internally inconsistent."
            ),
            "residual_question": (
                "The planning statements require reconciliation."
            ),
        }]
        result = rp.build_oracle_premise_concerns(
            records,
            {
                "concerns": [{
                    "concern": "The planning statements require reconciliation.",
                    "premise_ids": ["P1"],
                    "residual_dependency": (
                        "The stated quantities conflict."
                    ),
                    "methodological_consequence": (
                        "The intended sample cannot be determined."
                    ),
                }]
            },
        )
        self.assertEqual(result["eligible_premise_ids"], ["P1"])


if __name__ == "__main__":
    unittest.main()
