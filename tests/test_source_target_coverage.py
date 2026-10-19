import unittest

from app import review_pipeline as rp


def record(**overrides):
    value = {
        "premise_id": "candidate:semantic-1",
        "information_need": "Whether the requested specification is reported.",
        "target_authorised": True,
        "source_resolution_status": "NOT_LOCATED",
        "whole_primary_file_accessible": True,
        "search_scope": "whole_primary_file",
        "search_completed": True,
        "answer_found_elsewhere": False,
    }
    value.update(overrides)
    return value


class SourceTargetCoverageTests(unittest.TestCase):

    def test_complete_whole_file_search_can_establish_unresolved(self):
        result = rp.validate_source_target_coverage_record(record())
        self.assertEqual(
            result["state"],
            "MANUSCRIPT_UNRESOLVED",
        )

    def test_answer_elsewhere_resolves(self):
        result = rp.validate_source_target_coverage_record(
            record(answer_found_elsewhere=True)
        )
        self.assertEqual(
            result["state"],
            "RESOLVED_ELSEWHERE",
        )

    def test_unauthorised_target_cannot_escalate(self):
        result = rp.validate_source_target_coverage_record(
            record(target_authorised=False)
        )
        self.assertEqual(
            result["state"],
            "TARGET_NOT_AUTHORISED",
        )

    def test_local_evidence_is_insufficient(self):
        result = rp.validate_source_target_coverage_record(
            record(
                search_scope="local_evidence_only",
                search_completed=True,
            )
        )
        self.assertEqual(
            result["state"],
            "COVERAGE_INSUFFICIENT",
        )

    def test_targeted_search_does_not_yet_certify_absence(self):
        result = rp.validate_source_target_coverage_record(
            record(
                search_scope="targeted_primary_file",
                search_completed=True,
            )
        )
        self.assertEqual(
            result["state"],
            "COVERAGE_INSUFFICIENT",
        )

    def test_incomplete_whole_file_search_is_insufficient(self):
        result = rp.validate_source_target_coverage_record(
            record(search_completed=False)
        )
        self.assertEqual(
            result["state"],
            "COVERAGE_INSUFFICIENT",
        )

    def test_inaccessible_primary_file_is_insufficient(self):
        result = rp.validate_source_target_coverage_record(
            record(whole_primary_file_accessible=False)
        )
        self.assertEqual(
            result["state"],
            "COVERAGE_INSUFFICIENT",
        )

    def test_partial_source_resolution_is_accepted(self):
        result = rp.validate_source_target_coverage_record(
            record(source_resolution_status="PARTIAL")
        )
        self.assertEqual(
            result["state"],
            "MANUSCRIPT_UNRESOLVED",
        )

    def test_answered_source_resolution_is_rejected(self):
        with self.assertRaises(ValueError):
            rp.validate_source_target_coverage_record(
                record(source_resolution_status="ANSWERED")
            )

    def test_rejects_unknown_search_scope(self):
        with self.assertRaises(ValueError):
            rp.validate_source_target_coverage_record(
                record(search_scope="distributed_excerpts")
            )


if __name__ == "__main__":
    unittest.main()
