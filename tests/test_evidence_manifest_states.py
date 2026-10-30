import unittest

from app.review_pipeline import EvidenceManifest, refine_manifest_flags, structure_evidence


class EvidenceManifestStateTests(unittest.TestCase):
    def refine(self, text):
        manifest = EvidenceManifest(source_name="diagnostic.txt")
        return refine_manifest_flags(manifest, text)

    def test_explicit_confidence_interval_is_detected(self):
        self.assertTrue(self.refine("The estimate was 2.4 (95% CI 1.1 to 3.7).").has_confidence_intervals)

    def test_comparative_lower_is_not_a_confidence_interval(self):
        self.assertFalse(self.refine("Performance was lower after treatment than placebo.").has_confidence_intervals)

    def test_lower_and_upper_bound_terminology_remains_detectable(self):
        self.assertTrue(self.refine("The confidence limits had a lower bound of 1.1 and upper bound of 3.7.").has_confidence_intervals)

    def test_explicit_standard_error_is_detected(self):
        self.assertTrue(self.refine("Coefficients are reported as estimate (SE).").has_standard_errors)

    def test_bare_se_in_prose_is_not_a_standard_error(self):
        self.assertFalse(self.refine("The SE region of the field was used for testing.").has_standard_errors)

    def test_tabular_se_header_is_detected(self):
        self.assertTrue(self.refine("Estimate\tSE\tp-value").has_standard_errors)

    def test_randomly_assigned_is_detected(self):
        self.assertTrue(structure_evidence("x.pdf", "Participants were randomly assigned to treatment order.", []).has_randomisation)

    def test_randomly_allocated_is_detected(self):
        self.assertTrue(structure_evidence("x.pdf", "Participants were randomly allocated to treatment.", []).has_randomisation)

    def test_random_selection_is_not_randomisation(self):
        self.assertFalse(structure_evidence("x.pdf", "Participants were randomly selected from the available records.", []).has_randomisation)

    def test_random_sample_is_not_randomisation(self):
        self.assertFalse(structure_evidence("x.pdf", "A random sample of observations was inspected.", []).has_randomisation)


if __name__ == "__main__":
    unittest.main()
