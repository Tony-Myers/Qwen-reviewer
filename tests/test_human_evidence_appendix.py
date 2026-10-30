import unittest

from app.human_evidence_appendix import extract_final_findings


SAMPLE_REPORT = """# Reviewer critical-appraisal aid

## Major strengths

- Strength: The outcome is clearly defined.

## Directly supported concerns

- Concern: The analysis does not account for treatment order.
  Evidence: "The model included treatment as a fixed effect."
  Why it matters: Period or sequence effects may affect interpretation.

- Concern: Missing observations are not clearly accounted for.
  Evidence: The manuscript reports 84 enrolled participants but 76 analysed.
  Why it matters: Missing-data handling affects interpretation.

## Verification prompts

- Check: whether allocation concealment was implemented.
  Reason: The available description does not establish this.

- Check: whether the analysis population was prespecified.
  Reason: This remains unclear.
"""


class FinalFindingIdentityTests(unittest.TestCase):

    def test_concerns_receive_stable_ids_in_report_order(self):
        findings = extract_final_findings(SAMPLE_REPORT)

        concerns = [f for f in findings if f["review_status"] == "concern"]

        self.assertEqual([f["finding_id"] for f in concerns], ["C1", "C2"])
        self.assertEqual(
            concerns[0]["text"],
            "The analysis does not account for treatment order.",
        )
        self.assertEqual(
            concerns[1]["text"],
            "Missing observations are not clearly accounted for.",
        )

    def test_questions_receive_stable_ids_in_report_order(self):
        findings = extract_final_findings(SAMPLE_REPORT)

        questions = [
            f for f in findings
            if f["review_status"] == "verification_question"
        ]

        self.assertEqual([f["finding_id"] for f in questions], ["Q1", "Q2"])
        self.assertEqual(
            questions[0]["text"],
            "whether allocation concealment was implemented.",
        )
        self.assertEqual(
            questions[1]["text"],
            "whether the analysis population was prespecified.",
        )

    def test_ids_are_unique(self):
        findings = extract_final_findings(SAMPLE_REPORT)

        ids = [f["finding_id"] for f in findings]

        self.assertEqual(len(ids), len(set(ids)))

    def test_identity_extraction_does_not_rewrite_finding_text(self):
        report = """## Directly supported concerns

- Concern: Preserve THIS punctuation: n = 42; p = .031 (two-sided).

## Verification prompts

- Check: whether "primary outcome" means the registered endpoint?
"""

        findings = extract_final_findings(report)

        self.assertEqual(
            findings[0]["text"],
            "Preserve THIS punctuation: n = 42; p = .031 (two-sided).",
        )
        self.assertEqual(
            findings[1]["text"],
            'whether "primary outcome" means the registered endpoint?',
        )

    def test_no_upstream_lineage_is_invented(self):
        findings = extract_final_findings(SAMPLE_REPORT)

        for finding in findings:
            self.assertIsNone(finding["upstream_lineage"])

    def test_non_finding_sections_are_ignored(self):
        findings = extract_final_findings(SAMPLE_REPORT)

        self.assertEqual(len(findings), 4)
        self.assertFalse(
            any(f["text"] == "The outcome is clearly defined." for f in findings)
        )

    def test_empty_report_returns_empty_list(self):
        self.assertEqual(extract_final_findings(""), [])


if __name__ == "__main__":
    unittest.main()


class EvidenceCardTests(unittest.TestCase):

    def test_unverified_report_evidence_is_not_promoted_to_direct_support(self):
        from app.human_evidence_appendix import build_evidence_cards

        report = """## Directly supported concerns

- Concern: Treatment order is not accounted for.
  Evidence: "The model included treatment as a fixed effect."
  Why it matters: Period or sequence effects may affect interpretation.
"""

        cards = build_evidence_cards(report)

        self.assertEqual(len(cards), 1)
        card = cards[0]

        self.assertEqual(card["finding_id"], "C1")
        self.assertEqual(card["review_status"], "concern")
        self.assertEqual(
            card["reported_evidence"],
            '"The model included treatment as a fixed effect."',
        )
        self.assertEqual(
            card["interpretation"],
            "Period or sequence effects may affect interpretation.",
        )

        self.assertEqual(
            card["evidence_relationship"],
            "source_relationship_not_established",
        )
        self.assertIsNone(card["source_location"])
        self.assertIsNone(card["verified_source_evidence"])
        self.assertTrue(card["human_verification_required"])

    def test_verified_source_relationship_can_be_supplied_by_application_state(self):
        from app.human_evidence_appendix import build_evidence_cards

        report = """## Directly supported concerns

- Concern: The study is non-randomised.
  Evidence: "This synthetic study used a non-randomised pre/post design."
  Why it matters: Group differences should not be interpreted as if allocation were random.
"""

        verified = {
            "C1": {
                "evidence_relationship": "direct_manuscript_support",
                "source_location": "Methods, p. 8",
                "verified_source_evidence":
                    "This synthetic study used a non-randomised pre/post design.",
                "evidence_type": "quotation",
                "exact_quotation_verified": True,
            }
        }

        cards = build_evidence_cards(report, verified_relationships=verified)
        card = cards[0]

        self.assertEqual(
            card["evidence_relationship"],
            "direct_manuscript_support",
        )
        self.assertEqual(card["source_location"], "Methods, p. 8")
        self.assertEqual(
            card["verified_source_evidence"],
            "This synthetic study used a non-randomised pre/post design.",
        )
        self.assertEqual(card["evidence_type"], "quotation")
        self.assertTrue(card["exact_quotation_verified"])
        self.assertFalse(card["human_verification_required"])

    def test_table_evidence_can_be_represented_without_becoming_proof(self):
        from app.human_evidence_appendix import build_evidence_cards

        report = """## Directly supported concerns

- Concern: Groups differed at baseline.
  Evidence: Baseline scores differed between groups.
  Why it matters: Baseline heterogeneity should be considered when interpreting group comparisons.
"""

        verified = {
            "C1": {
                "evidence_relationship": "direct_table_evidence",
                "source_location": "Table 1, p. 3",
                "verified_source_evidence":
                    "Score: 10.00 (1.00), 12.00 (2.00), 14.00 (3.00), p=.010",
                "evidence_type": "table",
                "table_evidence_used": True,
            }
        }

        card = build_evidence_cards(
            report,
            verified_relationships=verified,
        )[0]

        self.assertEqual(card["evidence_relationship"], "direct_table_evidence")
        self.assertEqual(card["evidence_type"], "table")
        self.assertTrue(card["table_evidence_used"])

        self.assertEqual(
            card["interpretation"],
            "Baseline heterogeneity should be considered when interpreting group comparisons.",
        )

    def test_verification_question_remains_unresolved_by_default(self):
        from app.human_evidence_appendix import build_evidence_cards

        report = """## Verification prompts

- Check: whether allocation concealment was implemented.
  Reason: The available description does not establish this.
"""

        card = build_evidence_cards(report)[0]

        self.assertEqual(card["finding_id"], "Q1")
        self.assertEqual(card["review_status"], "verification_question")
        self.assertEqual(
            card["evidence_relationship"],
            "source_relationship_not_established",
        )
        self.assertEqual(
            card["interpretation"],
            "The available description does not establish this.",
        )
        self.assertTrue(card["human_verification_required"])

    def test_absence_of_support_is_not_contradiction(self):
        from app.human_evidence_appendix import build_evidence_cards

        report = """## Directly supported concerns

- Concern: Missing observations are not clearly accounted for.
  Evidence: The manuscript reports different enrolled and analysed totals.
  Why it matters: Missing-data handling affects interpretation.
"""

        card = build_evidence_cards(report)[0]

        self.assertNotEqual(
            card["evidence_relationship"],
            "conflicting_manuscript_evidence",
        )
        self.assertEqual(
            card["evidence_relationship"],
            "source_relationship_not_established",
        )

    def test_conflicting_evidence_requires_explicit_application_state(self):
        from app.human_evidence_appendix import build_evidence_cards

        report = """## Directly supported concerns

- Concern: Missing observations are not described.
  Evidence: No explanation is given.
  Why it matters: Attrition may affect interpretation.
"""

        verified = {
            "C1": {
                "evidence_relationship": "conflicting_manuscript_evidence",
                "source_location": "Methods, p. 5",
                "verified_source_evidence":
                    "Missing observations were handled using multiple imputation.",
                "evidence_type": "quotation",
                "exact_quotation_verified": True,
                "human_verification_required": True,
            }
        }

        card = build_evidence_cards(
            report,
            verified_relationships=verified,
        )[0]

        self.assertEqual(
            card["evidence_relationship"],
            "conflicting_manuscript_evidence",
        )
        self.assertTrue(card["human_verification_required"])

    def test_manifest_boolean_cannot_be_supplied_as_evidence_relationship(self):
        from app.human_evidence_appendix import build_evidence_cards

        report = """## Directly supported concerns

- Concern: Confidence intervals are appropriately reported.
  Evidence: Confidence intervals were found.
  Why it matters: Precision can be evaluated.
"""

        invalid = {
            "C1": {
                "evidence_relationship": "has_confidence_intervals",
                "verified_source_evidence": True,
            }
        }

        with self.assertRaises(ValueError):
            build_evidence_cards(report, verified_relationships=invalid)

    def test_unknown_finding_id_in_verification_state_is_rejected(self):
        from app.human_evidence_appendix import build_evidence_cards

        report = """## Directly supported concerns

- Concern: One concern.
  Evidence: One evidence statement.
  Why it matters: One interpretation.
"""

        invalid = {
            "C99": {
                "evidence_relationship": "direct_manuscript_support",
                "source_location": "p. 1",
                "verified_source_evidence": "text",
            }
        }

        with self.assertRaises(ValueError):
            build_evidence_cards(report, verified_relationships=invalid)


if __name__ == "__main__":
    unittest.main()


class HumanEvidenceRenderingTests(unittest.TestCase):

    def test_unverified_card_is_explicitly_unresolved(self):
        from app.human_evidence_appendix import (
            build_evidence_cards,
            render_human_evidence_appendix,
        )

        report = """## Directly supported concerns

- Concern: Treatment order is not accounted for.
  Evidence: "The model included treatment as a fixed effect."
  Why it matters: Period or sequence effects may affect interpretation.
"""

        rendered = render_human_evidence_appendix(
            build_evidence_cards(report)
        )

        self.assertIn("## C1 — Concern", rendered)
        self.assertIn(
            "**Source relationship:** Not established — human verification required",
            rendered,
        )
        self.assertIn(
            '**Evidence reported in the review:** "The model included treatment as a fixed effect."',
            rendered,
        )
        self.assertIn(
            "**Reviewer interpretation:** Period or sequence effects may affect interpretation.",
            rendered,
        )
        self.assertNotIn("**Verified manuscript evidence:**", rendered)

    def test_verified_card_shows_source_and_verified_evidence_separately(self):
        from app.human_evidence_appendix import (
            build_evidence_cards,
            render_human_evidence_appendix,
        )

        report = """## Directly supported concerns

- Concern: The study is non-randomised.
  Evidence: "This synthetic study used a non-randomised pre/post design."
  Why it matters: Group differences should not be interpreted as if allocation were random.
"""

        verified = {
            "C1": {
                "evidence_relationship": "direct_manuscript_support",
                "source_location": "Methods, p. 8",
                "verified_source_evidence":
                    "This synthetic study used a non-randomised pre/post design.",
                "evidence_type": "quotation",
                "source_passage_located": True,
                "exact_quotation_verified": True,
            }
        }

        rendered = render_human_evidence_appendix(
            build_evidence_cards(
                report,
                verified_relationships=verified,
            )
        )

        self.assertIn(
            "**Source relationship:** Direct manuscript support",
            rendered,
        )
        self.assertIn("**Source:** Methods, p. 8", rendered)
        self.assertIn(
            "**Verified manuscript evidence:** This synthetic study used a non-randomised pre/post design.",
            rendered,
        )
        self.assertIn("**Evidence type:** Quotation", rendered)
        self.assertIn("**Exact quotation verified:** Yes", rendered)

    def test_table_card_has_human_readable_table_relationship(self):
        from app.human_evidence_appendix import (
            build_evidence_cards,
            render_human_evidence_appendix,
        )

        report = """## Directly supported concerns

- Concern: Groups differed at baseline.
  Evidence: Baseline scores differed between groups.
  Why it matters: Baseline heterogeneity should be considered.
"""

        verified = {
            "C1": {
                "evidence_relationship": "direct_table_evidence",
                "source_location": "Table 1, p. 3",
                "verified_source_evidence":
                    "Score: 10.00 (1.00), 12.00 (2.00), 14.00 (3.00), p=.010",
                "evidence_type": "table",
                "table_evidence_used": True,
            }
        }

        rendered = render_human_evidence_appendix(
            build_evidence_cards(
                report,
                verified_relationships=verified,
            )
        )

        self.assertIn(
            "**Source relationship:** Direct table evidence",
            rendered,
        )
        self.assertIn("**Source:** Table 1, p. 3", rendered)
        self.assertIn("**Evidence type:** Table", rendered)
        self.assertIn("**Table evidence used:** Yes", rendered)

    def test_verification_question_is_labelled_question(self):
        from app.human_evidence_appendix import (
            build_evidence_cards,
            render_human_evidence_appendix,
        )

        report = """## Verification prompts

- Check: whether allocation concealment was implemented.
  Reason: The available description does not establish this.
"""

        rendered = render_human_evidence_appendix(
            build_evidence_cards(report)
        )

        self.assertIn("## Q1 — Verification question", rendered)
        self.assertIn(
            "**Human action:** Check this point against the manuscript before using it.",
            rendered,
        )

    def test_renderer_does_not_expose_manifest_boolean_language(self):
        from app.human_evidence_appendix import (
            build_evidence_cards,
            render_human_evidence_appendix,
        )

        report = """## Directly supported concerns

- Concern: Precision reporting should be checked.
  Evidence: Confidence intervals may be relevant.
  Why it matters: Precision affects interpretation.
"""

        rendered = render_human_evidence_appendix(
            build_evidence_cards(report)
        )

        forbidden = (
            "Confidence intervals reported: True",
            "Standard errors reported: True",
            "Randomisation described: True",
            "P-values reported: True",
            "Model fit statistics reported: True",
        )

        for text in forbidden:
            self.assertNotIn(text, rendered)

    def test_renderer_does_not_use_evidence_match_confidence_language(self):
        from app.human_evidence_appendix import (
            build_evidence_cards,
            render_human_evidence_appendix,
        )

        report = """## Directly supported concerns

- Concern: One concern.
  Evidence: One reported evidence statement.
  Why it matters: One interpretation.
"""

        rendered = render_human_evidence_appendix(
            build_evidence_cards(report)
        )

        self.assertNotIn("Evidence match:", rendered)
        self.assertNotIn("Evidence match: High", rendered)
        self.assertNotIn("Evidence match: Moderate", rendered)
        self.assertNotIn("Evidence match: Low", rendered)

    def test_renderer_contains_explanatory_boundary_note(self):
        from app.human_evidence_appendix import (
            build_evidence_cards,
            render_human_evidence_appendix,
        )

        report = """## Directly supported concerns

- Concern: One concern.
  Evidence: One evidence statement.
  Why it matters: One interpretation.
"""

        rendered = render_human_evidence_appendix(
            build_evidence_cards(report)
        )

        self.assertIn("# Human Evidence Appendix", rendered)
        self.assertIn(
            "Evidence reported in the review is not treated as verified manuscript evidence unless the application has established the source relationship.",
            rendered,
        )

    def test_empty_cards_render_clear_empty_appendix(self):
        from app.human_evidence_appendix import render_human_evidence_appendix

        rendered = render_human_evidence_appendix([])

        self.assertIn("# Human Evidence Appendix", rendered)
        self.assertIn(
            "No substantive concerns or verification questions were identified for evidence-card rendering.",
            rendered,
        )


if __name__ == "__main__":
    unittest.main()


class HumanEvidenceTableRenderingTests(unittest.TestCase):

    def test_structured_table_evidence_renders_as_markdown_table(self):
        from app.human_evidence_appendix import (
            build_evidence_cards,
            render_human_evidence_appendix,
        )

        report = """## Directly supported concerns

- Concern: Groups differed at baseline.
  Evidence: Baseline scores differed between groups.
  Why it matters: Baseline heterogeneity should be considered.
"""

        verified = {
            "C1": {
                "evidence_relationship": "direct_table_evidence",
                "source_location": "Table 1, p. 3",
                "verified_source_evidence":
                    "Score: 10.00 (1.00), 12.00 (2.00), 14.00 (3.00), p=.010",
                "evidence_type": "table",
                "table_evidence_used": True,
                "structured_table": {
                    "columns": [
                        "Measure",
                        "Strategic",
                        "Self-paced",
                        "Control",
                        "p",
                    ],
                    "rows": [
                        [
                            "Score",
                            "10.00 (1.00)",
                            "12.00 (2.00)",
                            "14.00 (3.00)",
                            ".010",
                        ]
                    ],
                },
            }
        }

        rendered = render_human_evidence_appendix(
            build_evidence_cards(
                report,
                verified_relationships=verified,
            )
        )

        self.assertIn(
            "| Measure | Strategic | Self-paced | Control | p |",
            rendered,
        )
        self.assertIn(
            "| --- | --- | --- | --- | --- |",
            rendered,
        )
        self.assertIn(
            "| Score | 10.00 (1.00) | 12.00 (2.00) | 14.00 (3.00) | .010 |",
            rendered,
        )

    def test_structured_table_preserves_headers_and_cells_verbatim(self):
        from app.human_evidence_appendix import (
            build_evidence_cards,
            render_human_evidence_appendix,
        )

        report = """## Directly supported concerns

- Concern: A table value should be checked.
  Evidence: The relevant values occur in Table 2.
  Why it matters: The values affect interpretation.
"""

        verified = {
            "C1": {
                "evidence_relationship": "direct_table_evidence",
                "source_location": "Table 2, p. 6",
                "evidence_type": "table",
                "table_evidence_used": True,
                "structured_table": {
                    "columns": ["Outcome", "Group A", "Group B", "95% CI"],
                    "rows": [
                        ["Outcome", "50.0 ± 5.0", "48.0 ± 5.0", "0.5 to 3.5"]
                    ],
                },
            }
        }

        rendered = render_human_evidence_appendix(
            build_evidence_cards(
                report,
                verified_relationships=verified,
            )
        )

        self.assertIn("Outcome", rendered)
        self.assertIn("50.0 ± 5.0", rendered)
        self.assertIn("48.0 ± 5.0", rendered)
        self.assertIn("0.5 to 3.5", rendered)

    def test_unstructured_table_evidence_falls_back_to_verified_text(self):
        from app.human_evidence_appendix import (
            build_evidence_cards,
            render_human_evidence_appendix,
        )

        report = """## Directly supported concerns

- Concern: Groups differed at baseline.
  Evidence: Baseline scores differed between groups.
  Why it matters: Baseline heterogeneity should be considered.
"""

        verified_text = (
            "Score: 10.00 (1.00), 12.00 (2.00), "
            "14.00 (3.00), p=.010"
        )

        verified = {
            "C1": {
                "evidence_relationship": "direct_table_evidence",
                "source_location": "Table 1, p. 3",
                "verified_source_evidence": verified_text,
                "evidence_type": "table",
                "table_evidence_used": True,
            }
        }

        rendered = render_human_evidence_appendix(
            build_evidence_cards(
                report,
                verified_relationships=verified,
            )
        )

        self.assertIn(
            f"**Verified manuscript evidence:** {verified_text}",
            rendered,
        )
        self.assertNotIn(
            "| Measure | Strategic | Self-paced | Control | p |",
            rendered,
        )

    def test_reported_evidence_string_is_not_reconstructed_as_table(self):
        from app.human_evidence_appendix import (
            build_evidence_cards,
            render_human_evidence_appendix,
        )

        report = """## Directly supported concerns

- Concern: Groups differed at baseline.
  Evidence: Score: 10.00 (1.00), 12.00 (2.00), 14.00 (3.00), p=.010
  Why it matters: Baseline heterogeneity should be considered.
"""

        rendered = render_human_evidence_appendix(
            build_evidence_cards(report)
        )

        self.assertIn(
            "**Evidence reported in the review:** Score: 10.00 (1.00), 12.00 (2.00), 14.00 (3.00), p=.010",
            rendered,
        )
        self.assertNotIn("| Score |", rendered)
        self.assertNotIn("| Measure |", rendered)

    def test_malformed_structured_table_is_rejected(self):
        from app.human_evidence_appendix import build_evidence_cards

        report = """## Directly supported concerns

- Concern: Groups differed at baseline.
  Evidence: Baseline scores differed between groups.
  Why it matters: Baseline heterogeneity should be considered.
"""

        invalid = {
            "C1": {
                "evidence_relationship": "direct_table_evidence",
                "source_location": "Table 1, p. 3",
                "evidence_type": "table",
                "structured_table": {
                    "columns": ["Measure", "Group A", "Group B"],
                    "rows": [
                        ["Score", "10.0"]
                    ],
                },
            }
        }

        with self.assertRaises(ValueError):
            build_evidence_cards(
                report,
                verified_relationships=invalid,
            )

    def test_markdown_control_characters_are_escaped_not_interpreted(self):
        from app.human_evidence_appendix import (
            build_evidence_cards,
            render_human_evidence_appendix,
        )

        report = """## Directly supported concerns

- Concern: Table content should remain structurally faithful.
  Evidence: The source table contains a labelled category.
  Why it matters: Rendering should not change cell boundaries.
"""

        verified = {
            "C1": {
                "evidence_relationship": "direct_table_evidence",
                "source_location": "Table 3, p. 9",
                "evidence_type": "table",
                "table_evidence_used": True,
                "structured_table": {
                    "columns": ["Measure", "Category | subgroup"],
                    "rows": [
                        ["Score", "High | very high"]
                    ],
                },
            }
        }

        rendered = render_human_evidence_appendix(
            build_evidence_cards(
                report,
                verified_relationships=verified,
            )
        )

        self.assertIn(
            "| Measure | Category \\| subgroup |",
            rendered,
        )
        self.assertIn(
            "| Score | High \\| very high |",
            rendered,
        )


if __name__ == "__main__":
    unittest.main()


from app.human_evidence_appendix import build_evidence_cards


class HistoricalInlineReportParsingTests(unittest.TestCase):
    def test_inline_concern_fields_are_separated(self):
        report = """# Directly supported concerns

- Concern: Groups differed at baseline. Evidence: Table 1 shows different baseline values. Why it matters: The imbalance may affect interpretation.
"""

        cards = build_evidence_cards(report)

        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0]["finding_id"], "C1")
        self.assertEqual(
            cards[0]["finding"],
            "Groups differed at baseline.",
        )
        self.assertEqual(
            cards[0]["reported_evidence"],
            "Table 1 shows different baseline values.",
        )
        self.assertEqual(
            cards[0]["interpretation"],
            "The imbalance may affect interpretation.",
        )

    def test_inline_verification_reason_is_separated(self):
        report = """# Verification prompts

- Check: whether allocation was randomised. Reason: The extracted methods describe self-selection.
"""

        cards = build_evidence_cards(report)

        self.assertEqual(len(cards), 1)
        self.assertEqual(cards[0]["finding_id"], "Q1")
        self.assertEqual(
            cards[0]["finding"],
            "whether allocation was randomised.",
        )
        self.assertIsNone(cards[0]["reported_evidence"])
        self.assertEqual(
            cards[0]["interpretation"],
            "The extracted methods describe self-selection.",
        )

    def test_inline_concern_preserves_internal_evidence_word(self):
        report = """# Directly supported concerns

- Concern: The evidence base is narrow. Evidence: Only one source is described. Why it matters: Generalisation is limited.
"""

        cards = build_evidence_cards(report)

        self.assertEqual(
            cards[0]["finding"],
            "The evidence base is narrow.",
        )
        self.assertEqual(
            cards[0]["reported_evidence"],
            "Only one source is described.",
        )

    def test_inline_not_verbatim_note_remains_with_reported_evidence(self):
        report = """# Directly supported concerns

- Concern: Sample sizes differ. Evidence: Table values imply different totals. Why it matters: The operative sample is unclear. *[not verbatim - see Citation check]*
"""

        cards = build_evidence_cards(report)

        self.assertEqual(
            cards[0]["finding"],
            "Sample sizes differ.",
        )
        self.assertEqual(
            cards[0]["reported_evidence"],
            "Table values imply different totals.",
        )
        self.assertEqual(
            cards[0]["interpretation"],
            "The operative sample is unclear. *[not verbatim - see Citation check]*",
        )

    def test_multiline_existing_format_still_parses(self):
        report = """# Directly supported concerns

- Concern: Groups differed at baseline.
  Evidence: Table 1 shows different baseline values.
  Why it matters: The imbalance may affect interpretation.
"""

        cards = build_evidence_cards(report)

        self.assertEqual(
            cards[0]["finding"],
            "Groups differed at baseline.",
        )
        self.assertEqual(
            cards[0]["reported_evidence"],
            "Table 1 shows different baseline values.",
        )
        self.assertEqual(
            cards[0]["interpretation"],
            "The imbalance may affect interpretation.",
        )


class VerifiedSourceSpanTests(unittest.TestCase):

    SOURCE = """[Page 3]
Results text before the table.
[TABLE_START]
Source: pdfplumber_text
Page: 3
Label: Table 1
Score 10.00 12.00 14.00 p=.010
[TABLE_END]

[Page 8]
Methods
This synthetic study used a non-randomised pre/post design.
"""

    def _span(self, text):
        start = self.SOURCE.index(text)
        return {
            "source_start_char": start,
            "source_end_char": start + len(text),
            "text": text,
        }

    def test_exact_prose_span_derives_page_location(self):
        from app.human_evidence_appendix import (
            build_verified_source_evidence,
        )

        text = (
            "This synthetic study used a non-randomised "
            "pre/post design."
        )

        result = build_verified_source_evidence(
            self.SOURCE,
            [self._span(text)],
        )

        self.assertEqual(result["source_locations"], ["p. 8"])
        self.assertEqual(result["source_location"], "p. 8")
        self.assertEqual(result["verified_source_evidence"], text)
        self.assertTrue(result["source_passage_located"])

    def test_exact_table_span_derives_table_and_page(self):
        from app.human_evidence_appendix import (
            build_verified_source_evidence,
        )

        text = "Score 10.00 12.00 14.00 p=.010"

        result = build_verified_source_evidence(
            self.SOURCE,
            [self._span(text)],
        )

        self.assertEqual(
            result["source_locations"],
            ["Table 1, p. 3"],
        )
        self.assertEqual(
            result["source_location"],
            "Table 1, p. 3",
        )
        self.assertTrue(result["table_evidence_used"])

    def test_multiple_spans_preserve_distinct_locations(self):
        from app.human_evidence_appendix import (
            build_verified_source_evidence,
        )

        table_text = "Score 10.00 12.00 14.00 p=.010"
        methods_text = (
            "This synthetic study used a non-randomised "
            "pre/post design."
        )

        result = build_verified_source_evidence(
            self.SOURCE,
            [
                self._span(table_text),
                self._span(methods_text),
            ],
        )

        self.assertEqual(
            result["source_locations"],
            ["Table 1, p. 3", "p. 8"],
        )
        self.assertEqual(
            result["source_location"],
            "Table 1, p. 3; p. 8",
        )
        self.assertEqual(
            result["verified_source_evidence"],
            [table_text, methods_text],
        )

    def test_duplicate_locations_are_collapsed_without_losing_spans(self):
        from app.human_evidence_appendix import (
            build_verified_source_evidence,
        )

        first = "Results text before the table."
        second = "Methods"

        result = build_verified_source_evidence(
            self.SOURCE,
            [
                self._span(first),
                self._span(second),
            ],
        )

        self.assertEqual(
            result["source_locations"],
            ["p. 3", "p. 8"],
        )
        self.assertEqual(
            result["verified_source_evidence"],
            [first, second],
        )

    def test_stale_or_incorrect_span_is_rejected_not_relocated(self):
        from app.human_evidence_appendix import (
            build_verified_source_evidence,
        )

        text = (
            "This synthetic study used a non-randomised "
            "pre/post design."
        )
        span = self._span(text)
        span["source_start_char"] -= 1
        span["source_end_char"] -= 1

        with self.assertRaises(ValueError):
            build_verified_source_evidence(
                self.SOURCE,
                [span],
            )

    def test_span_without_page_structure_remains_location_unresolved(self):
        from app.human_evidence_appendix import (
            build_verified_source_evidence,
        )

        source = "Exact manuscript statement without structural markers."
        span = {
            "source_start_char": 0,
            "source_end_char": len(source),
            "text": source,
        }

        result = build_verified_source_evidence(source, [span])

        self.assertEqual(result["source_locations"], [])
        self.assertIsNone(result["source_location"])
        self.assertEqual(result["verified_source_evidence"], source)
        self.assertTrue(result["source_passage_located"])

    def test_structural_metadata_does_not_establish_semantic_relationship(self):
        from app.human_evidence_appendix import (
            build_verified_source_evidence,
        )

        text = "Score 10.00 12.00 14.00 p=.010"

        result = build_verified_source_evidence(
            self.SOURCE,
            [self._span(text)],
        )

        self.assertNotIn("evidence_relationship", result)
        self.assertNotIn("direct_table_evidence", result.values())


class MultipleSourceRenderingTests(unittest.TestCase):

    def test_multiple_verified_passages_render_separately(self):
        from app.human_evidence_appendix import (
            build_evidence_cards,
            render_human_evidence_appendix,
        )

        report = """## Directly supported concerns

- Concern: Evidence comes from more than one manuscript location.
  Evidence: The review combines two source observations.
  Why it matters: Both locations are needed to assess the point.
"""

        verified = {
            "C1": {
                "evidence_relationship": "multiple_source_support",
                "source_location": "pp. 3, 5",
                "verified_source_evidence": [
                    "First exact source passage.",
                    "Second exact source passage.",
                ],
                "source_passage_located": True,
            }
        }

        rendered = render_human_evidence_appendix(
            build_evidence_cards(
                report,
                verified_relationships=verified,
            )
        )

        self.assertIn("**Source:** pp. 3, 5", rendered)
        self.assertIn(
            "**Verified manuscript evidence:**",
            rendered,
        )
        self.assertIn(
            "- First exact source passage.",
            rendered,
        )
        self.assertIn(
            "- Second exact source passage.",
            rendered,
        )
        self.assertNotIn(
            "['First exact source passage.'",
            rendered,
        )


class VerifiedSourceToHumanCardTests(unittest.TestCase):

    def test_verified_spans_flow_into_human_readable_card(self):
        from app.human_evidence_appendix import (
            build_evidence_cards,
            build_verified_source_evidence,
            render_human_evidence_appendix,
        )

        source = """[Page 3]
[TABLE_START]
Source: pdfplumber_text
Page: 3
Label: Table 1
Score 10.00 12.00 14.00 p=.010
[TABLE_END]

[Page 8]
This synthetic study used a non-randomised pre/post design.
"""

        table_text = "Score 10.00 12.00 14.00 p=.010"
        design_text = (
            "This synthetic study used a non-randomised "
            "pre/post design."
        )

        table_start = source.index(table_text)
        design_start = source.index(design_text)

        provenance = build_verified_source_evidence(
            source,
            [
                {
                    "source_start_char": table_start,
                    "source_end_char": table_start + len(table_text),
                    "text": table_text,
                },
                {
                    "source_start_char": design_start,
                    "source_end_char": design_start + len(design_text),
                    "text": design_text,
                },
            ],
        )

        report = """## Directly supported concerns

- Concern: Interpretation should account for the observational group structure.
  Evidence: Baseline group differences and non-randomised allocation are relevant.
  Why it matters: Group comparisons should not be interpreted as randomised contrasts.
"""

        verified = {
            "C1": {
                **provenance,
                "evidence_relationship": "multiple_source_support",
                "evidence_type": "quotation",
            }
        }

        rendered = render_human_evidence_appendix(
            build_evidence_cards(
                report,
                verified_relationships=verified,
            )
        )

        self.assertIn(
            "**Source:** Table 1, p. 3; p. 8",
            rendered,
        )
        self.assertIn(
            "- Score 10.00 12.00 14.00 p=.010",
            rendered,
        )
        self.assertIn(
            "- This synthetic study used a non-randomised pre/post design.",
            rendered,
        )
        self.assertIn(
            "**Source relationship:** Multiple-source support",
            rendered,
        )
        self.assertIn(
            "**Table evidence used:** Yes",
            rendered,
        )
        self.assertNotIn("Evidence match:", rendered)
