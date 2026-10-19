import unittest

from app import review_pipeline as rp


class CoverageEscalationTests(unittest.TestCase):

    def base_record(self):
        return {
            "premise_id": "P1",
            "information_need": "primary_estimand_or_time_contrast",
            "candidate_grounded": True,
            "source_resolution_status": "NOT_LOCATED",
            "whole_primary_file_accessible": True,
            "search_scope": "whole_primary_file",
            "relevant_regions_searched": True,
            "answer_found_elsewhere": False,
        }

    def test_full_coverage_can_mark_manuscript_unresolved(self):
        result = rp.validate_coverage_escalation_record(
            self.base_record()
        )
        self.assertEqual(
            result["state"],
            "MANUSCRIPT_UNRESOLVED",
        )

    def test_model_added_safeguard_cannot_escalate(self):
        record = self.base_record()
        record["candidate_grounded"] = False

        result = rp.validate_coverage_escalation_record(record)

        self.assertEqual(
            result["state"],
            "NOT_CANDIDATE_GROUNDED",
        )

    def test_answer_elsewhere_resolves_premise(self):
        record = self.base_record()
        record["answer_found_elsewhere"] = True

        result = rp.validate_coverage_escalation_record(record)

        self.assertEqual(
            result["state"],
            "RESOLVED_ELSEWHERE",
        )

    def test_local_evidence_is_insufficient_coverage(self):
        record = self.base_record()
        record["search_scope"] = "local_evidence_only"
        record["relevant_regions_searched"] = False

        result = rp.validate_coverage_escalation_record(record)

        self.assertEqual(
            result["state"],
            "COVERAGE_INSUFFICIENT",
        )

    def test_inaccessible_primary_file_is_insufficient(self):
        record = self.base_record()
        record["whole_primary_file_accessible"] = False

        result = rp.validate_coverage_escalation_record(record)

        self.assertEqual(
            result["state"],
            "COVERAGE_INSUFFICIENT",
        )

    def test_partial_is_valid_input(self):
        record = self.base_record()
        record["source_resolution_status"] = "PARTIAL"

        result = rp.validate_coverage_escalation_record(record)

        self.assertEqual(
            result["state"],
            "MANUSCRIPT_UNRESOLVED",
        )

    def test_answered_cannot_enter_coverage_escalation(self):
        record = self.base_record()
        record["source_resolution_status"] = "ANSWERED"

        with self.assertRaises(ValueError):
            rp.validate_coverage_escalation_record(record)

    def test_unexpected_field_rejected(self):
        record = self.base_record()
        record["extra"] = True

        with self.assertRaises(ValueError):
            rp.validate_coverage_escalation_record(record)


if __name__ == "__main__":
    unittest.main()
