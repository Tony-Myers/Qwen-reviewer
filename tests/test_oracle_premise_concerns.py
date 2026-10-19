import unittest

from app import review_pipeline as rp


class OraclePremiseConcernTests(unittest.TestCase):

    def setUp(self):
        self.records = [
            {
                "premise_id": "P1",
                "status": "ANSWERED",
                "source_answer": (
                    "Clusters are randomised to one of four study conditions."
                ),
                "residual_question": "",
            },
            {
                "premise_id": "P2",
                "status": "ANSWERED",
                "source_answer": (
                    "A maximum of 20 clusters is planned, with five clusters "
                    "per study condition."
                ),
                "residual_question": "",
            },
            {
                "premise_id": "P3",
                "status": "PARTIAL",
                "source_answer": (
                    "The protocol states that the planned cluster sample "
                    "provides equal allocation and a sufficiently large sample."
                ),
                "residual_question": (
                    "The justification does not establish operating "
                    "characteristics for the planned confirmatory analysis "
                    "accounting for clustering and expected cluster size."
                ),
            },
        ]

    def test_schema_is_strict_and_bounded(self):
        schema = rp.oracle_premise_concern_output_schema()
        self.assertEqual(set(schema["required"]), {"concerns"})
        self.assertFalse(schema["additionalProperties"])
        self.assertEqual(
            schema["properties"]["concerns"]["maxItems"],
            4,
        )

    def test_prompt_freezes_answered_premises(self):
        prompt = rp.build_oracle_premise_concern_prompt(self.records)
        self.assertIn("P1 and P2 are ANSWERED", prompt)
        self.assertIn("randomisation unit", prompt)
        self.assertIn("number of clusters", prompt)
        self.assertIn('"P3"', prompt)

    def test_valid_concern_uses_partial_premise(self):
        result = rp.build_oracle_premise_concerns(
            self.records,
            {
                "concerns": [{
                    "concern": (
                        "The allocation is specified, but the protocol does "
                        "not establish the operating characteristics of the "
                        "planned confirmatory analysis."
                    ),
                    "premise_ids": ["P3"],
                    "residual_dependency": (
                        "Operating-characteristic justification remains partial."
                    ),
                    "methodological_consequence": (
                        "Adequacy of the planned analysis cannot "
                        "be evaluated from the stated justification."
                    ),
                }]
            },
        )
        self.assertEqual(result["eligible_premise_ids"], ["P3"])
        self.assertEqual(result["concerns"][0]["premise_ids"], ["P3"])

    def test_answered_premise_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Resolved premises"):
            rp.build_oracle_premise_concerns(
                self.records,
                {
                    "concerns": [{
                        "concern": "Cluster allocation is unclear.",
                        "premise_ids": ["P1"],
                        "residual_dependency": "Allocation remains unclear.",
                        "methodological_consequence": "This affects inference.",
                    }]
                },
            )

    def test_answered_premise_cannot_hide_with_partial(self):
        with self.assertRaisesRegex(ValueError, "Resolved premises"):
            rp.build_oracle_premise_concerns(
                self.records,
                {
                    "concerns": [{
                        "concern": "A compound concern.",
                        "premise_ids": ["P1", "P3"],
                        "residual_dependency": "A residual remains.",
                        "methodological_consequence": "It matters.",
                    }]
                },
            )

    def test_unknown_premise_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Unknown oracle"):
            rp.build_oracle_premise_concerns(
                self.records,
                {
                    "concerns": [{
                        "concern": "Unknown concern.",
                        "premise_ids": ["P99"],
                        "residual_dependency": "Unknown.",
                        "methodological_consequence": "Unknown.",
                    }]
                },
            )

    def test_generation_uses_assessor(self):
        calls = []

        def assessor(*, prompt, schema):
            calls.append((prompt, schema))
            return {
                "concerns": [{
                    "concern": (
                        "The stated cluster allocation is clear, but its "
                        "operating-characteristic justification remains "
                        "under-specified."
                    ),
                    "premise_ids": ["P3"],
                    "residual_dependency": (
                        "The operating-characteristic justification is partial."
                    ),
                    "methodological_consequence": (
                        "The adequacy of the confirmatory interaction decision "
                        "cannot be evaluated from the stated justification."
                    ),
                }]
            }

        result = rp.generate_oracle_premise_concerns(
            self.records,
            assessor,
        )

        self.assertEqual(len(calls), 1)
        self.assertEqual(result["concerns"][0]["premise_ids"], ["P3"])


if __name__ == "__main__":
    unittest.main()
