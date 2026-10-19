import unittest

from app import review_pipeline as rp


class CandidateSemanticRoleTests(unittest.TestCase):

    def test_schema_has_four_roles(self):
        schema = rp.candidate_semantic_roles_output_schema()
        roles = (
            schema["properties"]["items"]["items"]
            ["properties"]["role"]["enum"]
        )
        self.assertEqual(
            set(roles),
            {
                "SOURCE_TESTABLE_TARGET",
                "METHODOLOGICAL_INTERPRETATION",
                "HYPOTHETICAL_MECHANISM",
                "REMEDY_OR_REQUIREMENT",
            },
        )

    def test_prompt_is_decomposition_only(self):
        prompt = rp.build_candidate_semantic_roles_prompt(
            "C1",
            "The comparison may be limited to two examples.",
        )
        self.assertIn("semantic-role decomposition only", prompt)
        self.assertIn("whether the candidate is correct", prompt)

    def test_prompt_says_candidate_is_not_evidence(self):
        prompt = rp.build_candidate_semantic_roles_prompt(
            "C1",
            "The comparison may be limited to two examples.",
        )
        self.assertIn(
            "Candidate prose is reviewer output, not manuscript evidence",
            prompt,
        )

    def test_prompt_blocks_example_method_substitution(self):
        prompt = rp.build_candidate_semantic_roles_prompt(
            "C1",
            "Was there a comparison, e.g. nested-model test?",
        )
        self.assertIn(
            "example of a possible method",
            prompt,
        )

    def test_builder_preserves_candidate_and_assigns_ids(self):
        result = rp.build_candidate_semantic_roles(
            "C1",
            {
                "items": [
                    {
                        "role": "SOURCE_TESTABLE_TARGET",
                        "text": "The form of comparison reported can be checked.",
                    },
                    {
                        "role": "REMEDY_OR_REQUIREMENT",
                        "text": "A nested-model test is one suggested option.",
                    },
                ],
            },
        )
        self.assertEqual(result["candidate_id"], "C1")
        self.assertEqual(result["items"][0]["item_id"], "C1:semantic-1")
        self.assertEqual(result["items"][1]["item_id"], "C1:semantic-2")

    def test_unknown_role_rejected(self):
        with self.assertRaises(ValueError):
            rp.build_candidate_semantic_roles(
                "C1",
                {
                    "items": [
                        {
                            "role": "FACT",
                            "text": "Invalid role.",
                        },
                    ],
                },
            )

    def test_unexpected_item_field_rejected(self):
        with self.assertRaises(ValueError):
            rp.build_candidate_semantic_roles(
                "C1",
                {
                    "items": [
                        {
                            "role": "SOURCE_TESTABLE_TARGET",
                            "text": "A proposition.",
                            "confidence": 0.9,
                        },
                    ],
                },
            )

    def test_generation_preserves_candidate_id(self):
        def assessor(*, prompt, schema):
            return {
                "items": [
                    {
                        "role": "SOURCE_TESTABLE_TARGET",
                        "text": "The reported comparison form can be checked.",
                    },
                ],
            }

        result = rp.generate_candidate_semantic_roles(
            "C1",
            "What form of comparison is reported?",
            assessor,
        )
        self.assertEqual(result["candidate_id"], "C1")


    def test_prompt_blocks_epistemic_strengthening(self):
        prompt = rp.build_candidate_semantic_roles_prompt(
            "C1",
            "It appears that the comparison may be limited to examples.",
        )
        self.assertIn(
            "Preserve the candidate's epistemic status and scope",
            prompt,
        )
        self.assertIn(
            "Do not strengthen an",
            prompt,
        )

    def test_prompt_preserves_interrogative_status(self):
        prompt = rp.build_candidate_semantic_roles_prompt(
            "C1",
            "Is there a formal comparison or only two examples?",
        )
        self.assertIn(
            "assert X or Y",
            prompt,
        )
        self.assertIn(
            "neutral information that must be established from the source",
            prompt,
        )

    def test_prompt_preserves_local_scope(self):
        prompt = rp.build_candidate_semantic_roles_prompt(
            "C1",
            "No estimand is outlined here.",
        )
        self.assertIn(
            "preserve that local scope",
            prompt,
        )
        self.assertIn(
            "Do not rewrite it as absent",
            prompt,
        )

    def test_prompt_blocks_recommendation_to_fact_conversion(self):
        prompt = rp.build_candidate_semantic_roles_prompt(
            "C1",
            "The mathematical form would need to be inspectable.",
        )
        self.assertIn(
            "do not rewrite",
            prompt,
        )
        self.assertIn(
            "claim that the manuscript actually provides it",
            prompt,
        )


if __name__ == "__main__":
    unittest.main()
