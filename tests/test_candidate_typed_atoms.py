import unittest

from app import review_pipeline as rp


class CandidateTypedAtomTests(unittest.TestCase):

    def test_schema_has_closed_information_need_set(self):
        schema = rp.candidate_typed_atoms_output_schema()
        enum = (
            schema["properties"]["atoms"]["items"]
            ["properties"]["information_need"]["enum"]
        )
        self.assertEqual(
            set(enum),
            rp._TYPED_ATOM_INFORMATION_NEEDS,
        )

    def test_prompt_distinguishes_outcome_from_estimand(self):
        prompt = rp.build_candidate_typed_atoms_prompt(
            "candidate-1",
            "No model, estimand, repeated-measures handling, or hierarchy.",
        )
        self.assertIn(
            "An outcome variable is not itself an estimand",
            prompt,
        )

    def test_prompt_distinguishes_cluster_from_within_participant(self):
        prompt = rp.build_candidate_typed_atoms_prompt(
            "candidate-1",
            "No repeated-measures handling is outlined.",
        )
        self.assertIn(
            "higher-level cluster does not by itself specify how",
            prompt,
        )

    def test_prompt_prevents_factorial_repeated_collapse(self):
        prompt = rp.build_candidate_typed_atoms_prompt(
            "candidate-1",
            "No model or repeated-measures handling is outlined.",
        )
        self.assertIn(
            "Do not collapse factorial-model specification",
            prompt,
        )

    def test_builder_assigns_application_owned_ids(self):
        output = {
            "atoms": [
                {
                    "information_need": "factorial_analysis_model",
                    "question": "What factorial analysis model is specified?",
                },
                {
                    "information_need": "primary_estimand_or_time_contrast",
                    "question": "What primary estimand is specified?",
                },
            ]
        }

        result = rp.build_candidate_typed_atoms("candidate-1", output)

        self.assertEqual(
            result["atoms"][0]["premise_id"],
            "candidate-1:typed-premise-1",
        )
        self.assertEqual(
            result["atoms"][1]["premise_id"],
            "candidate-1:typed-premise-2",
        )

    def test_builder_rejects_unknown_information_need(self):
        output = {
            "atoms": [
                {
                    "information_need": "generic_methodology_problem",
                    "question": "What is specified?",
                }
            ]
        }

        with self.assertRaises(ValueError):
            rp.build_candidate_typed_atoms("candidate-1", output)

    def test_builder_rejects_unexpected_fields(self):
        output = {
            "atoms": [
                {
                    "information_need": "factorial_analysis_model",
                    "question": "What model is specified?",
                    "criticism": "The model is unclear.",
                }
            ]
        }

        with self.assertRaises(ValueError):
            rp.build_candidate_typed_atoms("candidate-1", output)

    def test_generation_uses_assessor(self):
        calls = []

        def assessor(*, prompt, schema):
            calls.append((prompt, schema))
            return {
                "atoms": [
                    {
                        "information_need": "outcome_hierarchy",
                        "question": (
                            "Which outcomes are designated primary and secondary?"
                        ),
                    }
                ]
            }

        result = rp.generate_candidate_typed_atoms(
            "candidate-1",
            "The outcome hierarchy is unclear.",
            assessor,
        )

        self.assertEqual(len(calls), 1)
        self.assertEqual(
            result["atoms"][0]["information_need"],
            "outcome_hierarchy",
        )


if __name__ == "__main__":
    unittest.main()
