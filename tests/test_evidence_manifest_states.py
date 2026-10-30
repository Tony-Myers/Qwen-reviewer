import unittest
from unittest.mock import patch

import app.review_pipeline as rp
from app.review_pipeline import (
    EvidenceManifest,
    programmatic_post_checks,
    refine_manifest_flags,
    structure_evidence,
)


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



class StandardErrorDetectorTests(unittest.TestCase):
    """The SE flag is set only by the reporting forms documented in
    review_pipeline (_STANDARD_ERROR_RE); the initial scan and refinement use
    the same definition."""

    def both(self, text):
        initial = structure_evidence("x.txt", text, []).has_standard_errors
        refined = refine_manifest_flags(EvidenceManifest(source_name="x.txt"), text).has_standard_errors
        return initial, refined

    def test_negative_controls_do_not_set_the_flag(self):
        negatives = (
            "Sites were located in the SE, near the coast.",
            "Region codes were NE: north east and SE: south east.",
            "Data came from the south-east (SE) of the country.",
            "Training camps were in the NW; SE; and centre.",
            "The squad trained in the SE\nduring winter.",
            "Regions: NE = north-east, SE = south-east.",
            "The SE region of the field was used for testing.",
            "Players were selected from the set of eligible teams.",
        )
        for text in negatives:
            with self.subTest(text=text):
                self.assertEqual(self.both(text), (False, False))

    def test_positive_controls_set_the_flag(self):
        positives = (
            "Robust standard errors were computed.",
            "The estimate was 0.42 (SE = 0.10).",
            "The estimate was 0.42 (S.E. = 0.10).",
            "Slope 0.8, SE: 0.12.",
            "Estimate\tSE\tp-value",
            "SE\t0.12\t0.08",
            "| Estimate | SE | p |",
            "Coefficients are reported as estimate (SE).",
            "Values are mean ± SE.",
        )
        for text in positives:
            with self.subTest(text=text):
                self.assertEqual(self.both(text), (True, True))


class RandomAllocationDetectorTests(unittest.TestCase):
    """The randomisation flag means random allocation/assignment or
    randomised condition order, never random sampling or selection."""

    def both(self, text):
        initial = structure_evidence("x.txt", text, []).has_randomisation
        refined = refine_manifest_flags(EvidenceManifest(source_name="x.txt"), text).has_randomisation
        return initial, refined

    def test_negative_controls_do_not_set_the_flag(self):
        negatives = (
            "The order of test completion was alphabetical by surname.",
            "Randomized sampling was used to select schools from the register.",
            "Schools were chosen by randomised selection from the register.",
            "Participants were randomly selected from the available records.",
            "A random sample of observations was inspected.",
            "Random noise was added to the simulated signal.",
            "A random intercept was fitted for each participant.",
            "This study used a non-randomised pre/post design.",
            "Participants were not randomised to groups.",
            "Groups were compared without randomisation.",
            "A randomisation test compared the two groups.",
            "Participants were randomly recruited from local clubs and divided into groups by age.",
        )
        for text in negatives:
            with self.subTest(text=text):
                self.assertEqual(self.both(text), (False, False))

    def test_positive_controls_set_the_flag(self):
        positives = (
            "Participants were randomly assigned to treatment order.",
            "Participants were randomly allocated to treatment.",
            "Participants were randomised to intervention or control.",
            "This was a randomised controlled trial.",
            "Conditions were completed in a randomised order.",
            "The order of test completion was randomised.",
            "Players were assigned to groups at random.",
            "Condition order was counterbalanced.",
            "Participants were recruited by convenience sampling and then randomly allocated to two groups.",
        )
        for text in positives:
            with self.subTest(text=text):
                self.assertEqual(self.both(text), (True, True))

    def test_sampling_method_does_not_veto_allocation(self):
        text = ("Purposive sampling was used. Participants were invited by email. "
                "Participants were randomly assigned to the two conditions.")
        self.assertEqual(self.both(text), (True, True))


class ManifestOnlyPostCheckTests(unittest.TestCase):
    """A manifest flag (or extraction count) alone yields a verification
    request, never an established correction."""

    CASES = {
        "standard errors": (dict(has_standard_errors=True), "Standard errors are not reported."),
        "p-values": (dict(has_p_values=True), "P-values are not reported."),
        "randomisation": (dict(has_randomisation=True), "Randomisation is unclear."),
        "variance components": (dict(has_variance_components=True), "Variance components are not reported."),
        "model fit": (dict(has_model_fit_stats=True), "Model fit statistics are not reported."),
        "sample": (dict(has_sample_description=True), "Sample size is not reported."),
        "confidence intervals": (dict(has_confidence_intervals=True), "Confidence intervals are not reported."),
        "confidence intervals in a list": (dict(has_confidence_intervals=True),
                                           "Standard errors and confidence intervals are not reported."),
        "model specification": (dict(has_model_spec=True), "Model specification is missing."),
        "equation": (dict(has_equations=True), "Equation is missing."),
        "tables": (dict(n_tables=2, table_labels=["Table 1", "Table 2"]), "Tables are missing."),
    }

    def test_flag_only_signal_requests_verification(self):
        for name, (flags, sentence) in self.CASES.items():
            with self.subTest(case=name):
                manifest = EvidenceManifest(source_name="synthetic.txt", **flags)
                messages = programmatic_post_checks(sentence, manifest)
                self.assertTrue(messages, "expected a verification request")
                for message in messages:
                    self.assertTrue(message.startswith("CHECK:"), message)
                    self.assertNotIn("CORRECTION", message)
                    self.assertIn("Verify", message)
                    self.assertRegex(message, r"(?:not evidence|alone does not show)")

    def test_messages_do_not_assert_that_evidence_was_found(self):
        for name, (flags, sentence) in self.CASES.items():
            manifest = EvidenceManifest(source_name="synthetic.txt", **flags)
            for message in programmatic_post_checks(sentence, manifest):
                with self.subTest(case=name):
                    self.assertNotIn("were found in the extracted evidence", message)
                    self.assertNotIn("Revise this claim", message)

    def test_no_flag_no_message(self):
        for name, (_, sentence) in self.CASES.items():
            with self.subTest(case=name):
                manifest = EvidenceManifest(source_name="synthetic.txt")
                self.assertEqual(programmatic_post_checks(sentence, manifest), [])

    def test_validation_prompt_distinguishes_checks_from_corrections(self):
        captured = {}

        def capture(tokenizer, text):
            captured["prompt"] = text
            return text

        with patch.object(rp, "apply_chat_template_compat", side_effect=capture), \
             patch.object(rp, "make_default_sampler", return_value=None), \
             patch.object(rp, "generate", return_value="report"):
            rp.validate_report_against_evidence(
                None, None, "Standard errors are not reported.",
                [("synthetic.txt", "Synthetic summary.")],
                programmatic_corrections=["CHECK: synthetic check."],
            )
        prompt = captured["prompt"]
        self.assertNotIn("verified automatically", prompt)
        self.assertIn("Items marked CHECK come from document-level detectors", prompt)
        self.assertIn("They are not evidence", prompt)
        self.assertIn("otherwise leave the claim as it is", prompt)
        self.assertIn("- CHECK: synthetic check.", prompt)


if __name__ == "__main__":
    unittest.main()
