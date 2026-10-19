import unittest

from app import review_pipeline as rp


class CandidatePropositionVerificationTests(unittest.TestCase):

    def setUp(self):
        self.propositions = {
            "assessment_type": "whole_file_methodological_propositions",
            "propositions": [
                {
                    "proposition_id": "method-proposition-1",
                    "proposition": (
                        "The primary endpoint time point is not specified."
                    ),
                    "candidate_ids": [
                        "paper:chunk-1:candidate-1",
                        "paper:chunk-2:candidate-1",
                    ],
                    "state": "supported_under_specification",
                    "counterevidence_check": (
                        "Whole-file positive evidence was actively checked."
                    ),
                    "reason": "The observations were combined.",
                },
                {
                    "proposition_id": "method-proposition-2",
                    "proposition": (
                        "The number of clusters per condition is not defined."
                    ),
                    "candidate_ids": [
                        "paper:chunk-3:candidate-1",
                    ],
                    "state": "unresolved_question",
                    "counterevidence_check": (
                        "Whole-file positive evidence was actively checked."
                    ),
                    "reason": "The candidate raised this question.",
                },
            ],
            "resolved_candidate_groups": [],
            "represented_candidate_ids": [
                "paper:chunk-1:candidate-1",
                "paper:chunk-2:candidate-1",
                "paper:chunk-3:candidate-1",
            ],
            "resolved_candidate_ids": [],
        }

    def test_schema_is_strict_and_bounded(self):
        schema = rp.candidate_proposition_verification_output_schema()

        self.assertEqual(set(schema["required"]), {"verifications"})
        self.assertFalse(schema["additionalProperties"])

        items = schema["properties"]["verifications"]
        self.assertEqual(
            items["maxItems"],
            rp._CANDIDATE_PROPOSITION_MAX_ITEMS,
        )

        item = items["items"]
        self.assertFalse(item["additionalProperties"])
        self.assertEqual(
            set(item["required"]),
            {
                "proposition_id",
                "verdict",
                "verified_proposition",
                "verified_state",
                "counterevidence_check",
                "reason",
            },
        )

    def test_prompt_preserves_proposition_ids(self):
        prompt = rp.build_candidate_proposition_verification_prompt(
            self.propositions,
            manuscript_text=(
                "Six clusters are allocated to each condition."
            ),
        )

        self.assertIn("method-proposition-1", prompt)
        self.assertIn("method-proposition-2", prompt)
        self.assertIn(
            "Check every factual premise",
            prompt,
        )
        self.assertIn(
            "do not generate additional propositions",
            prompt.lower(),
        )
        self.assertIn("counterevidence_check", prompt)
        self.assertIn(
            "perform the counterevidence check BEFORE choosing a",
            prompt,
        )
        self.assertIn(
            "Information does not need to be repeated in",
            prompt,
        )
        self.assertIn("keep is prohibited", prompt)

    def test_keep_requires_unchanged_text_and_state(self):
        output = {
            "verifications": [
                {
                    "proposition_id": "method-proposition-1",
                    "verdict": "keep",
                    "verified_proposition": (
                        "The primary endpoint time point is not specified."
                    ),
                    "verified_state": "supported_under_specification",
                    "counterevidence_check": (
                        "Whole-file positive evidence was actively checked."
                    ),
                    "reason": "The manuscript does not identify the endpoint.",
                },
                {
                    "proposition_id": "method-proposition-2",
                    "verdict": "discard",
                    "verified_proposition": "",
                    "verified_state": "unresolved_question",
                    "counterevidence_check": (
                        "Whole-file positive evidence was actively checked."
                    ),
                    "reason": (
                        "The manuscript explicitly states six clusters "
                        "per condition."
                    ),
                },
            ]
        }

        result = rp.build_candidate_proposition_verification(
            self.propositions,
            output,
        )

        self.assertEqual(len(result["verifications"]), 2)
        self.assertEqual(
            result["verifications"][0]["verdict"],
            "keep",
        )

    def test_revise_can_change_text_and_state(self):
        output = {
            "verifications": [
                {
                    "proposition_id": "method-proposition-1",
                    "verdict": "revise",
                    "verified_proposition": (
                        "It remains unclear which follow-up time point "
                        "enters the confirmatory analysis."
                    ),
                    "verified_state": "unresolved_question",
                    "counterevidence_check": (
                        "Whole-file positive evidence was actively checked."
                    ),
                    "reason": (
                        "Repeated follow-ups are specified, but the "
                        "confirmatory endpoint remains unclear."
                    ),
                },
                {
                    "proposition_id": "method-proposition-2",
                    "verdict": "discard",
                    "verified_proposition": "",
                    "verified_state": "unresolved_question",
                    "counterevidence_check": (
                        "Whole-file positive evidence was actively checked."
                    ),
                    "reason": "The cluster allocation is explicitly stated.",
                },
            ]
        }

        result = rp.build_candidate_proposition_verification(
            self.propositions,
            output,
        )

        first = result["verifications"][0]
        self.assertEqual(first["verdict"], "revise")
        self.assertEqual(first["verified_state"], "unresolved_question")

    def test_unknown_proposition_id_is_rejected(self):
        output = {
            "verifications": [
                {
                    "proposition_id": "invented-id",
                    "verdict": "discard",
                    "verified_proposition": "",
                    "verified_state": "unresolved_question",
                    "counterevidence_check": (
                        "Whole-file positive evidence was actively checked."
                    ),
                    "reason": "Not supported.",
                }
            ]
        }

        with self.assertRaisesRegex(ValueError, "unknown proposition ID"):
            rp.build_candidate_proposition_verification(
                self.propositions,
                output,
            )

    def test_missing_proposition_is_rejected(self):
        output = {
            "verifications": [
                {
                    "proposition_id": "method-proposition-1",
                    "verdict": "keep",
                    "verified_proposition": (
                        "The primary endpoint time point is not specified."
                    ),
                    "verified_state": "supported_under_specification",
                    "counterevidence_check": (
                        "Whole-file positive evidence was actively checked."
                    ),
                    "reason": "Supported.",
                }
            ]
        }

        with self.assertRaisesRegex(
            ValueError,
            "exactly one result for every proposition ID",
        ):
            rp.build_candidate_proposition_verification(
                self.propositions,
                output,
            )

    def test_generation_uses_structured_assessor(self):
        captured = {}

        def assessor(*, prompt, schema):
            captured["prompt"] = prompt
            captured["schema"] = schema
            return {
                "verifications": [
                    {
                        "proposition_id": "method-proposition-1",
                        "verdict": "keep",
                        "verified_proposition": (
                            "The primary endpoint time point is not specified."
                        ),
                        "verified_state": "supported_under_specification",
                        "counterevidence_check": (
                        "Whole-file positive evidence was actively checked."
                    ),
                    "reason": "Supported by the whole manuscript.",
                    },
                    {
                        "proposition_id": "method-proposition-2",
                        "verdict": "discard",
                        "verified_proposition": "",
                        "verified_state": "unresolved_question",
                        "counterevidence_check": (
                        "Whole-file positive evidence was actively checked."
                    ),
                    "reason": (
                            "The whole manuscript explicitly gives the "
                            "cluster allocation."
                        ),
                    },
                ]
            }

        result = rp.verify_candidate_propositions(
            self.propositions,
            manuscript_text="Whole manuscript evidence.",
            assessor=assessor,
        )

        self.assertIn("Propositions:", captured["prompt"])
        self.assertEqual(
            captured["schema"],
            rp.candidate_proposition_verification_output_schema(),
        )
        self.assertEqual(len(result["verifications"]), 2)


if __name__ == "__main__":
    unittest.main()
