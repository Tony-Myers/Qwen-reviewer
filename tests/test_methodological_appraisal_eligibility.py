import unittest

from app import review_pipeline as rp


def semantic(items):
    return {
        "assessment_type": "candidate_semantic_roles",
        "candidate_id": "paper.pdf:chunk-1:candidate-1",
        "items": [
            {
                "item_id": (
                    f"paper.pdf:chunk-1:candidate-1:semantic-{i}"
                ),
                "role": role,
                "text": text,
            }
            for i, (role, text) in enumerate(items, start=1)
        ],
    }


def resolution(pid, status, answer="", residual=""):
    return {
        "premise_id": pid,
        "status": status,
        "source_answer": answer,
        "residual_question": residual,
    }


class MethodologicalAppraisalEligibilityTests(unittest.TestCase):

    def test_interpretation_authorises_appraisal(self):
        result = rp.determine_methodological_appraisal_eligibility(
            semantic([
                ("SOURCE_TESTABLE_TARGET", "What is reported?"),
                (
                    "METHODOLOGICAL_INTERPRETATION",
                    "The reported approach may affect inference.",
                ),
            ]),
            [
                resolution(
                    "P1",
                    "ANSWERED",
                    "The approach is reported.",
                )
            ],
        )
        self.assertEqual(
            result["state"],
            "ELIGIBLE_INTERPRETATION",
        )
        self.assertEqual(len(result["authority_ids"]), 1)

    def test_conflict_authorises_without_interpretation(self):
        result = rp.determine_methodological_appraisal_eligibility(
            semantic([
                (
                    "SOURCE_TESTABLE_TARGET",
                    "What coefficient is reported?",
                ),
                (
                    "REMEDY_OR_REQUIREMENT",
                    "Correct the inconsistent value.",
                ),
            ]),
            [
                resolution(
                    "P1",
                    "CONFLICTING",
                    "Narrative and equation report different values.",
                    "The values conflict.",
                )
            ],
        )
        self.assertEqual(
            result["state"],
            "ELIGIBLE_SOURCE_CONFLICT",
        )
        self.assertEqual(result["authority_ids"], ["P1"])

    def test_answered_plus_remedy_does_not_authorise(self):
        result = rp.determine_methodological_appraisal_eligibility(
            semantic([
                (
                    "SOURCE_TESTABLE_TARGET",
                    "How are the models compared?",
                ),
                (
                    "REMEDY_OR_REQUIREMENT",
                    "Use a formal statistical comparison.",
                ),
            ]),
            [
                resolution(
                    "P1",
                    "ANSWERED",
                    "Two illustrative individuals are compared.",
                )
            ],
        )
        self.assertEqual(
            result["state"],
            "NO_APPRAISAL_PROPOSITION",
        )
        self.assertEqual(result["authority_ids"], [])

    def test_not_located_plus_remedy_does_not_authorise(self):
        result = rp.determine_methodological_appraisal_eligibility(
            semantic([
                (
                    "SOURCE_TESTABLE_TARGET",
                    "Was the instrument frozen?",
                ),
                (
                    "REMEDY_OR_REQUIREMENT",
                    "Freeze the instrument before analysis.",
                ),
            ]),
            [
                resolution("P1", "NOT_LOCATED")
            ],
        )
        self.assertEqual(
            result["state"],
            "NO_APPRAISAL_PROPOSITION",
        )

    def test_hypothetical_mechanism_does_not_authorise(self):
        result = rp.determine_methodological_appraisal_eligibility(
            semantic([
                (
                    "SOURCE_TESTABLE_TARGET",
                    "What is the timing?",
                ),
                (
                    "HYPOTHETICAL_MECHANISM",
                    "Early data could influence item selection.",
                ),
            ]),
            [
                resolution(
                    "P1",
                    "ANSWERED",
                    "Psychometric work precedes the trial.",
                )
            ],
        )
        self.assertEqual(
            result["state"],
            "NO_APPRAISAL_PROPOSITION",
        )

    def test_empty_resolutions_withholds(self):
        result = rp.determine_methodological_appraisal_eligibility(
            semantic([
                (
                    "METHODOLOGICAL_INTERPRETATION",
                    "The method may be inadequate.",
                )
            ]),
            [],
        )
        self.assertEqual(
            result["state"],
            "NO_SOURCE_RESOLUTION",
        )

    def test_rejects_wrong_semantic_assessment_type(self):
        value = semantic([
            ("SOURCE_TESTABLE_TARGET", "Question.")
        ])
        value["assessment_type"] = "wrong"

        with self.assertRaises(ValueError):
            rp.determine_methodological_appraisal_eligibility(
                value,
                [resolution("P1", "ANSWERED", "Answer.")],
            )


if __name__ == "__main__":
    unittest.main()
