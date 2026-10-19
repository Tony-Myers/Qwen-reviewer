import unittest

from app import review_pipeline as rp


class CandidatePropositionTests(unittest.TestCase):

    def setUp(self):
        self.candidates = [
            {
                "candidate_id": "paper:chunk-1:candidate-1",
                "source_name": "paper",
                "chunk_id": 1,
                "section": "missing or unclear",
                "text": "The primary endpoint time point is unclear.",
                "status": "candidate",
            },
            {
                "candidate_id": "paper:chunk-2:candidate-1",
                "source_name": "paper",
                "chunk_id": 2,
                "section": "statistical / methodological concerns",
                "text": "Repeated follow-up measurements are planned.",
                "status": "candidate",
            },
        ]

    def test_schema_is_bounded_and_strict(self):
        schema = rp.candidate_proposition_output_schema()

        self.assertEqual(
            set(schema["required"]),
            {"propositions", "resolved_candidate_groups"},
        )
        self.assertFalse(schema["additionalProperties"])

        propositions = schema["properties"]["propositions"]
        self.assertEqual(
            propositions["maxItems"],
            rp._CANDIDATE_PROPOSITION_MAX_ITEMS,
        )

        item = propositions["items"]
        self.assertFalse(item["additionalProperties"])
        self.assertEqual(
            set(item["required"]),
            {
                "proposition",
                "candidate_ids",
                "state",
                "counterevidence_check",
                "reason",
            },
        )

        resolutions = schema["properties"]["resolved_candidate_groups"]
        self.assertEqual(
            resolutions["maxItems"],
            rp._CANDIDATE_PROPOSITION_MAX_ITEMS,
        )

        resolution_item = resolutions["items"]
        self.assertFalse(resolution_item["additionalProperties"])
        self.assertEqual(
            set(resolution_item["required"]),
            {"candidate_ids", "resolution"},
        )

    def test_prompt_preserves_candidate_ids_and_allows_combination(self):
        prompt = rp.build_candidate_proposition_prompt(
            self.candidates,
            manuscript_text="Whole manuscript evidence.",
            manifest_summary="Prospective protocol.",
            method_expectations="Consider longitudinal specification.",
        )

        for candidate in self.candidates:
            self.assertIn(candidate["candidate_id"], prompt)
            self.assertIn(candidate["text"], prompt)

        self.assertIn(
            "You may combine multiple candidate observations",
            prompt,
        )
        self.assertIn(
            "resolved_candidate_groups",
            prompt,
        )
        self.assertIn(
            "positive whole-file evidence",
            prompt,
        )
        self.assertIn("counterevidence_check", prompt)
        self.assertIn(
            "BEFORE writing the final proposition",
            prompt,
        )
        self.assertIn(
            "post-falsification formulation",
            prompt,
        )
        self.assertIn(
            "Information does not need to be repeated",
            prompt,
        )
        self.assertIn(
            "Absence of a familiar named safeguard",
            prompt,
        )
        self.assertIn(
            "Do not invent manuscript facts",
            prompt,
        )
        self.assertIn(
            "Do not rank propositions as high, medium, or low",
            prompt,
        )

    def test_valid_output_gets_application_owned_ids(self):
        output = {
            "propositions": [
                {
                    "proposition": (
                        "The confirmatory time structure remains "
                        "under-specified."
                    ),
                    "candidate_ids": [
                        "paper:chunk-1:candidate-1",
                        "paper:chunk-2:candidate-1",
                    ],
                    "state": "supported_under_specification",
                    "counterevidence_check": (
                        "The strongest relevant positive whole-file evidence "
                        "was considered before final formulation."
                    ),
                    "reason": (
                        "The two observations jointly identify an unresolved "
                        "decision about the planned repeated measurements."
                    ),
                }
            ],
            "resolved_candidate_groups": [],
        }

        result = rp.build_candidate_propositions(
            self.candidates,
            output,
        )

        self.assertEqual(
            result["assessment_type"],
            "whole_file_methodological_propositions",
        )
        self.assertEqual(
            result["propositions"][0]["proposition_id"],
            "method-proposition-1",
        )
        self.assertEqual(
            result["propositions"][0]["candidate_ids"],
            [
                "paper:chunk-1:candidate-1",
                "paper:chunk-2:candidate-1",
            ],
        )
        self.assertEqual(result["resolved_candidate_groups"], [])
        self.assertEqual(result["resolved_candidate_ids"], [])

    def test_valid_resolved_candidate_group_is_retained(self):
        candidate_id = "paper:chunk-1:candidate-1"
        output = {
            "propositions": [],
            "resolved_candidate_groups": [
                {
                    "candidate_ids": [candidate_id],
                    "resolution": (
                        "The whole-file analysis table explicitly identifies "
                        "the primary endpoint time point."
                    ),
                }
            ],
        }

        result = rp.build_candidate_propositions(
            self.candidates,
            output,
        )

        self.assertEqual(result["propositions"], [])
        self.assertEqual(
            result["resolved_candidate_groups"],
            [
                {
                    "candidate_ids": [candidate_id],
                    "resolution": (
                        "The whole-file analysis table explicitly identifies "
                        "the primary endpoint time point."
                    ),
                }
            ],
        )
        self.assertEqual(
            result["resolved_candidate_ids"],
            [candidate_id],
        )

    def test_unknown_candidate_id_is_rejected(self):
        output = {
            "propositions": [
                {
                    "proposition": "A proposition.",
                    "candidate_ids": ["invented-id"],
                    "state": "unresolved_question",
                    "counterevidence_check": (
                        "The strongest relevant positive whole-file evidence "
                        "was considered before final formulation."
                    ),
                    "reason": "A reason.",
                }
            ],
            "resolved_candidate_groups": [],
        }

        with self.assertRaisesRegex(
            ValueError,
            "unknown candidate IDs",
        ):
            rp.build_candidate_propositions(
                self.candidates,
                output,
            )

    def test_unknown_resolved_candidate_id_is_rejected(self):
        output = {
            "propositions": [],
            "resolved_candidate_groups": [
                {
                    "candidate_ids": ["invented-id"],
                    "resolution": "The premise is resolved elsewhere.",
                }
            ],
        }

        with self.assertRaisesRegex(
            ValueError,
            "unknown candidate IDs",
        ):
            rp.build_candidate_propositions(
                self.candidates,
                output,
            )

    def test_duplicate_candidate_id_within_proposition_is_rejected(self):
        candidate_id = "paper:chunk-1:candidate-1"
        output = {
            "propositions": [
                {
                    "proposition": "A proposition.",
                    "candidate_ids": [candidate_id, candidate_id],
                    "state": "unresolved_question",
                    "counterevidence_check": (
                        "The strongest relevant positive whole-file evidence "
                        "was considered before final formulation."
                    ),
                    "reason": "A reason.",
                }
            ],
            "resolved_candidate_groups": [],
        }

        with self.assertRaisesRegex(
            ValueError,
            "duplicate candidate IDs",
        ):
            rp.build_candidate_propositions(
                self.candidates,
                output,
            )

    def test_duplicate_candidate_id_within_resolution_is_rejected(self):
        candidate_id = "paper:chunk-1:candidate-1"
        output = {
            "propositions": [],
            "resolved_candidate_groups": [
                {
                    "candidate_ids": [candidate_id, candidate_id],
                    "resolution": "The premise is resolved elsewhere.",
                }
            ],
        }

        with self.assertRaisesRegex(
            ValueError,
            "duplicate candidate IDs",
        ):
            rp.build_candidate_propositions(
                self.candidates,
                output,
            )

    def test_candidate_cannot_be_proposition_and_resolved(self):
        candidate_id = "paper:chunk-1:candidate-1"
        output = {
            "propositions": [
                {
                    "proposition": "A surviving proposition.",
                    "candidate_ids": [candidate_id],
                    "state": "unresolved_question",
                    "counterevidence_check": (
                        "The strongest relevant positive whole-file evidence "
                        "was considered before final formulation."
                    ),
                    "reason": "The issue remains unresolved.",
                }
            ],
            "resolved_candidate_groups": [
                {
                    "candidate_ids": [candidate_id],
                    "resolution": "The same premise is resolved elsewhere.",
                }
            ],
        }

        with self.assertRaisesRegex(
            ValueError,
            "both represented in propositions and marked resolved",
        ):
            rp.build_candidate_propositions(
                self.candidates,
                output,
            )

    def test_invalid_state_is_rejected(self):
        output = {
            "propositions": [
                {
                    "proposition": "A proposition.",
                    "candidate_ids": [
                        "paper:chunk-1:candidate-1",
                    ],
                    "state": "high_priority_concern",
                    "counterevidence_check": (
                        "Positive whole-file evidence was considered."
                    ),
                    "reason": "A reason.",
                }
            ],
            "resolved_candidate_groups": [],
        }

        with self.assertRaisesRegex(
            ValueError,
            "Invalid candidate proposition state",
        ):
            rp.build_candidate_propositions(
                self.candidates,
                output,
            )

    def test_generation_uses_structured_assessor(self):
        captured = {}

        def assessor(*, prompt, schema):
            captured["prompt"] = prompt
            captured["schema"] = schema
            return {
                "propositions": [
                    {
                        "proposition": (
                            "The endpoint/time structure requires resolution."
                        ),
                        "candidate_ids": [
                            "paper:chunk-1:candidate-1",
                            "paper:chunk-2:candidate-1",
                        ],
                        "state": "unresolved_question",
                        "counterevidence_check": (
                            "The strongest relevant positive whole-file "
                            "evidence was considered before formulation."
                        ),
                        "reason": (
                            "The candidate observations become consequential "
                            "when considered together."
                        ),
                    }
                ],
                "resolved_candidate_groups": [],
            }

        result = rp.generate_candidate_propositions(
            self.candidates,
            manuscript_text="Whole manuscript evidence.",
            assessor=assessor,
        )

        self.assertIn("Candidate ledger:", captured["prompt"])
        self.assertIn(
            "resolved_candidate_groups",
            captured["prompt"],
        )
        self.assertEqual(
            captured["schema"],
            rp.candidate_proposition_output_schema(),
        )
        self.assertEqual(len(result["propositions"]), 1)
        self.assertEqual(result["resolved_candidate_groups"], [])


if __name__ == "__main__":
    unittest.main()
