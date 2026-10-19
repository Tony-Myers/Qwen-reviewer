import unittest

from app import review_pipeline as rp


class SemanticTargetResolutionTests(unittest.TestCase):

    def test_selects_only_source_testable_targets(self):
        semantic = {
            "assessment_type": "candidate_semantic_roles",
            "candidate_id": "C1",
            "items": [
                {
                    "item_id": "C1:semantic-1",
                    "role": "SOURCE_TESTABLE_TARGET",
                    "text": "The timing relationship between phases.",
                },
                {
                    "item_id": "C1:semantic-2",
                    "role": "HYPOTHETICAL_MECHANISM",
                    "text": "Timing could create circularity.",
                },
                {
                    "item_id": "C1:semantic-3",
                    "role": "REMEDY_OR_REQUIREMENT",
                    "text": "The instrument should be frozen.",
                },
                {
                    "item_id": "C1:semantic-4",
                    "role": "METHODOLOGICAL_INTERPRETATION",
                    "text": "This may threaten validity.",
                },
            ],
        }

        targets = rp.select_source_testable_targets(semantic)

        self.assertEqual(len(targets), 1)
        self.assertEqual(
            targets[0]["item_id"],
            "C1:semantic-1",
        )
        self.assertEqual(
            targets[0]["text"],
            "The timing relationship between phases.",
        )

    def test_rejects_wrong_assessment_type(self):
        with self.assertRaises(ValueError):
            rp.select_source_testable_targets({
                "assessment_type": "wrong",
                "candidate_id": "C1",
                "items": [],
            })

    def test_rejects_malformed_item(self):
        with self.assertRaises(ValueError):
            rp.select_source_testable_targets({
                "assessment_type": "candidate_semantic_roles",
                "candidate_id": "C1",
                "items": [{
                    "item_id": "C1:semantic-1",
                    "role": "SOURCE_TESTABLE_TARGET",
                }],
            })

    def test_empty_target_set_is_allowed(self):
        semantic = {
            "assessment_type": "candidate_semantic_roles",
            "candidate_id": "C1",
            "items": [{
                "item_id": "C1:semantic-1",
                "role": "REMEDY_OR_REQUIREMENT",
                "text": "Authors should report X.",
            }],
        }

        self.assertEqual(
            rp.select_source_testable_targets(semantic),
            [],
        )

    def test_preserves_target_identity_and_text(self):
        semantic = {
            "assessment_type": "candidate_semantic_roles",
            "candidate_id": "C1",
            "items": [{
                "item_id": "C1:semantic-7",
                "role": "SOURCE_TESTABLE_TARGET",
                "text": "  The form of comparison actually reported.  ",
            }],
        }

        targets = rp.select_source_testable_targets(semantic)

        self.assertEqual(targets, [{
            "item_id": "C1:semantic-7",
            "text": "The form of comparison actually reported.",
        }])


if __name__ == "__main__":
    unittest.main()
