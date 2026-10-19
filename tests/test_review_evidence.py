import unittest

from app.table_evidence import AcquisitionMethod, NamedQuantity
from app.review_evidence import (
    ComparabilityState,
    ComparisonRelationship,
    AcceptedRelationshipEvidence,
    EvidenceRelationship,
    EvidenceValue,
    IdentityState,
    RelationshipEvidenceItem,
    RelationshipEvidenceKind,
    RelationshipState,
    accept_relationship_evidence,
    compare_evidence_values,
    evidence_value_from_named_quantity,
)


class ReviewEvidenceTests(unittest.TestCase):

    def test_s8_sd_sensitivity_is_sd_to_sd_not_effect(self):
        full = EvidenceValue(
            evidence_id="s8-all-re-sd",
            source_name="benchmark.pdf",
            source_chunk_id=28,
            page=65,
            table_id="S8",
            outcome=None,
            analysis="all studies",
            model="RE",
            parameter="SD",
            estimate=2.13,
            interval_lower=1.79,
            interval_upper=2.54,
            interval_type="95% CrI",
        )

        sensitivity = EvidenceValue(
            evidence_id="s8-exclude-residual-re-sd",
            source_name="benchmark.pdf",
            source_chunk_id=28,
            page=65,
            table_id="S8",
            outcome=None,
            analysis="exclude high residual deviance",
            model="RE",
            parameter="SD",
            estimate=1.09,
            interval_lower=0.90,
            interval_upper=1.31,
            interval_type="95% CrI",
        )

        comparison = compare_evidence_values(full, sensitivity)

        self.assertEqual(
            comparison.comparability_state,
            ComparabilityState.COMPARISON_OPPORTUNITY,
        )
        self.assertEqual(
            comparison.relationship,
            ComparisonRelationship.SAME_PARAMETER_ACROSS_ANALYSES,
        )
        self.assertEqual(comparison.parameter, "SD")
        self.assertAlmostEqual(
            comparison.deterministic_difference,
            -1.04,
        )

        self.assertNotIn(
            comparison.parameter.casefold(),
            {"effect", "beta", "slope"},
        )

    def test_s8_s9_dic_is_same_metric_same_outcome(self):
        unadjusted = EvidenceValue(
            evidence_id="cf-unadjusted-dic",
            source_name="benchmark.pdf",
            source_chunk_id=28,
            page=65,
            table_id="S8",
            outcome="cognitive flexibility",
            analysis="unadjusted",
            model="RE",
            parameter="DIC",
            estimate=217.901,
        )

        age = EvidenceValue(
            evidence_id="cf-age-dic",
            source_name="benchmark.pdf",
            source_chunk_id=28,
            page=66,
            table_id="S9",
            outcome="cognitive flexibility",
            analysis="age adjusted",
            model="meta-regression",
            parameter="DIC",
            estimate=245.273,
        )

        comparison = compare_evidence_values(unadjusted, age)

        self.assertEqual(
            comparison.comparability_state,
            ComparabilityState.COMPARISON_OPPORTUNITY,
        )
        self.assertEqual(
            comparison.relationship,
            ComparisonRelationship.SAME_FIT_METRIC_ACROSS_ANALYSES,
        )
        self.assertEqual(comparison.parameter, "DIC")
        self.assertEqual(
            comparison.outcome,
            "cognitive flexibility",
        )
        self.assertAlmostEqual(
            comparison.deterministic_difference,
            27.372,
        )

        self.assertNotIn("worse", comparison.reason.casefold())
        self.assertNotIn("inferior", comparison.reason.casefold())
        self.assertNotIn("better", comparison.reason.casefold())
        self.assertIn(
            "not methodological comparability",
            comparison.reason.casefold(),
        )

    def test_different_parameters_are_not_compared(self):
        dic = EvidenceValue(
            evidence_id="dic",
            source_name="paper.pdf",
            source_chunk_id=1,
            page=1,
            table_id="1",
            outcome="outcome",
            analysis="model a",
            model="RE",
            parameter="DIC",
            estimate=100.0,
        )

        sd = EvidenceValue(
            evidence_id="sd",
            source_name="paper.pdf",
            source_chunk_id=1,
            page=1,
            table_id="1",
            outcome="outcome",
            analysis="model b",
            model="RE",
            parameter="SD",
            estimate=2.0,
        )

        comparison = compare_evidence_values(dic, sd)

        self.assertEqual(
            comparison.comparability_state,
            ComparabilityState.NOT_COMPARABLE,
        )
        self.assertIsNone(comparison.deterministic_difference)
        self.assertIsNone(comparison.relationship)

    def test_different_outcomes_are_not_compared(self):
        left = EvidenceValue(
            evidence_id="cf-dic",
            source_name="paper.pdf",
            source_chunk_id=1,
            page=1,
            table_id="S9",
            outcome="cognitive flexibility",
            analysis="unadjusted",
            model="RE",
            parameter="DIC",
            estimate=217.901,
        )

        right = EvidenceValue(
            evidence_id="wm-dic",
            source_name="paper.pdf",
            source_chunk_id=1,
            page=1,
            table_id="S9",
            outcome="working memory",
            analysis="age adjusted",
            model="meta-regression",
            parameter="DIC",
            estimate=251.804,
        )

        comparison = compare_evidence_values(left, right)

        self.assertEqual(
            comparison.comparability_state,
            ComparabilityState.NOT_COMPARABLE,
        )
        self.assertIsNone(comparison.deterministic_difference)

    def test_ambiguous_identity_withholds_comparison(self):
        left = EvidenceValue(
            evidence_id="ambiguous-cell",
            source_name="paper.pdf",
            source_chunk_id=2,
            page=66,
            table_id="S9",
            outcome="cognitive flexibility",
            analysis="age adjusted",
            model="meta-regression",
            parameter="SD",
            estimate=-10.28,
            identity_state=IdentityState.AMBIGUOUS,
        )

        right = EvidenceValue(
            evidence_id="identified-sd",
            source_name="paper.pdf",
            source_chunk_id=2,
            page=66,
            table_id="S9",
            outcome="cognitive flexibility",
            analysis="unadjusted",
            model="RE",
            parameter="SD",
            estimate=10.08,
        )

        comparison = compare_evidence_values(left, right)

        self.assertEqual(
            comparison.comparability_state,
            ComparabilityState.UNRESOLVED,
        )
        self.assertIsNone(comparison.deterministic_difference)
        self.assertIsNone(comparison.relationship)


    def test_unknown_analyses_use_weaker_reported_parameter_relationship(self):
        left = EvidenceValue(
            evidence_id="left-mean",
            source_name="left.pdf",
            source_chunk_id=1,
            page=1,
            table_id="1",
            outcome=None,
            analysis=None,
            model=None,
            parameter="Mean",
            estimate=10.0,
        )
        right = EvidenceValue(
            evidence_id="right-mean",
            source_name="right.pdf",
            source_chunk_id=1,
            page=1,
            table_id="1",
            outcome=None,
            analysis=None,
            model=None,
            parameter="Mean",
            estimate=12.0,
        )

        comparison = compare_evidence_values(left, right)

        self.assertEqual(
            comparison.comparability_state,
            ComparabilityState.COMPARISON_OPPORTUNITY,
        )
        self.assertEqual(
            comparison.relationship,
            ComparisonRelationship.SAME_REPORTED_PARAMETER,
        )
        self.assertAlmostEqual(
            comparison.deterministic_difference,
            2.0,
        )
        self.assertIsNone(comparison.left_analysis)
        self.assertIsNone(comparison.right_analysis)
        self.assertNotIn(
            "compatible outcome identities",
            comparison.reason.casefold(),
        )
        self.assertIn(
            "no conflicting identified outcome identities",
            comparison.reason.casefold(),
        )

    def test_numeric_correspondence_cannot_establish_same_model(self):
        evidence = (
            RelationshipEvidenceItem(
                relationship=EvidenceRelationship.MODEL_SPECIFICATION,
                kind=RelationshipEvidenceKind.NUMERIC_CORRESPONDENCE,
                description=(
                    "Table S8 CF RE and Table S9 CF Unadjusted report identical "
                    "DIC, pD, residual deviance, and SD values."
                ),
                provenance="Tables S8-S9",
            ),
        )

        result = accept_relationship_evidence(
            EvidenceRelationship.MODEL_SPECIFICATION,
            evidence,
        )

        self.assertIsInstance(result, AcceptedRelationshipEvidence)
        self.assertEqual(result.state, RelationshipState.NOT_ESTABLISHED)

    def test_numeric_correspondence_cannot_establish_same_observations(self):
        evidence = (
            RelationshipEvidenceItem(
                relationship=EvidenceRelationship.ANALYSED_OBSERVATIONS,
                kind=RelationshipEvidenceKind.NUMERIC_CORRESPONDENCE,
                description=(
                    "Table S8 CF RE and Table S9 CF Unadjusted report identical "
                    "DIC, pD, and residual deviance values."
                ),
                provenance="Tables S8-S9",
            ),
        )

        result = accept_relationship_evidence(
            EvidenceRelationship.ANALYSED_OBSERVATIONS,
            evidence,
        )

        self.assertEqual(result.state, RelationshipState.NOT_ESTABLISHED)

    def test_explicit_different_counts_establish_different_observations(self):
        evidence = (
            RelationshipEvidenceItem(
                relationship=EvidenceRelationship.ANALYSED_OBSERVATIONS,
                kind=RelationshipEvidenceKind.EXPLICIT_DIFFERENCE,
                description=(
                    "Table S8 reports 150 data points for All studies and "
                    "94 for Exclude missing education."
                ),
                provenance="Table S8",
            ),
        )

        result = accept_relationship_evidence(
            EvidenceRelationship.ANALYSED_OBSERVATIONS,
            evidence,
        )

        self.assertEqual(
            result.state,
            RelationshipState.ESTABLISHED_DIFFERENT,
        )

    def test_explicit_covariate_distinction_establishes_different_specification(self):
        evidence = (
            RelationshipEvidenceItem(
                relationship=EvidenceRelationship.MODEL_SPECIFICATION,
                kind=RelationshipEvidenceKind.EXPLICIT_DIFFERENCE,
                description=(
                    "Table S9 explicitly distinguishes Unadjusted from the "
                    "Age covariate analysis."
                ),
                provenance="Table S9",
            ),
        )

        result = accept_relationship_evidence(
            EvidenceRelationship.MODEL_SPECIFICATION,
            evidence,
        )

        self.assertEqual(
            result.state,
            RelationshipState.ESTABLISHED_DIFFERENT,
        )

    def test_explicit_identity_can_establish_same_relationship(self):
        evidence = (
            RelationshipEvidenceItem(
                relationship=EvidenceRelationship.ANALYSED_OBSERVATIONS,
                kind=RelationshipEvidenceKind.EXPLICIT_IDENTITY,
                description=(
                    "The manuscript explicitly states that the two reported "
                    "results use the same analysed observations."
                ),
                provenance="manuscript text",
            ),
        )

        result = accept_relationship_evidence(
            EvidenceRelationship.ANALYSED_OBSERVATIONS,
            evidence,
        )

        self.assertEqual(result.state, RelationshipState.ESTABLISHED_SAME)

    def test_explicit_evidence_cannot_establish_different_relationship(self):
        evidence = (
            RelationshipEvidenceItem(
                relationship=EvidenceRelationship.ANALYSED_OBSERVATIONS,
                kind=RelationshipEvidenceKind.EXPLICIT_DIFFERENCE,
                description=(
                    "Table S8 reports 150 data points for All studies and "
                    "94 for Exclude missing education."
                ),
                provenance="Table S8",
            ),
        )

        result = accept_relationship_evidence(
            EvidenceRelationship.MODEL_SPECIFICATION,
            evidence,
        )

        self.assertEqual(result.state, RelationshipState.NOT_ESTABLISHED)
        self.assertEqual(result.evidence, ())


    def test_accepted_relationship_retains_only_applicable_evidence(self):
        observation_evidence = RelationshipEvidenceItem(
            relationship=EvidenceRelationship.ANALYSED_OBSERVATIONS,
            kind=RelationshipEvidenceKind.EXPLICIT_DIFFERENCE,
            description="The analyses use different observation counts.",
            provenance="Table S8",
        )
        specification_evidence = RelationshipEvidenceItem(
            relationship=EvidenceRelationship.MODEL_SPECIFICATION,
            kind=RelationshipEvidenceKind.EXPLICIT_DIFFERENCE,
            description="Unadjusted and Age are different covariate analyses.",
            provenance="Table S9",
        )

        result = accept_relationship_evidence(
            EvidenceRelationship.MODEL_SPECIFICATION,
            (observation_evidence, specification_evidence),
        )

        self.assertEqual(
            result.state,
            RelationshipState.ESTABLISHED_DIFFERENT,
        )
        self.assertEqual(
            result.evidence,
            (specification_evidence,),
        )



    def test_conflicting_explicit_evidence_fails_closed(self):
        evidence = (
            RelationshipEvidenceItem(
                relationship=EvidenceRelationship.ANALYSED_OBSERVATIONS,
                kind=RelationshipEvidenceKind.EXPLICIT_IDENTITY,
                description="The manuscript states that the observations are the same.",
                provenance="source A",
            ),
            RelationshipEvidenceItem(
                relationship=EvidenceRelationship.ANALYSED_OBSERVATIONS,
                kind=RelationshipEvidenceKind.EXPLICIT_DIFFERENCE,
                description="The manuscript reports different observation sets.",
                provenance="source B",
            ),
        )

        result = accept_relationship_evidence(
            EvidenceRelationship.ANALYSED_OBSERVATIONS,
            evidence,
        )

        self.assertEqual(result.state, RelationshipState.NOT_ESTABLISHED)
        self.assertIn("conflict", result.reason.casefold())




class AnalysedObservationCountEvidenceTests(unittest.TestCase):

    def make_record(
        self,
        *,
        section_label,
        row_label="RE Model",
        table_id="table-s8",
        source_name="paper.pdf",
    ):
        from app.table_evidence import (
            AcquisitionMethod,
            TableCellEvidence,
            named_quantity_from_cell,
            table_record_from_quantities,
        )

        cell = TableCellEvidence(
            source_name=source_name,
            page=65,
            table_evidence_id=table_id,
            caption="Table S8",
            section_index=0,
            section_label=section_label,
            row_index=1,
            row_label=row_label,
            row_label_header="Model",
            column_index=1,
            column_header="DIC",
            observed_value="551.563",
            acquisition_method=AcquisitionMethod.VISION,
            extraction_source="vision",
        )

        quantity = named_quantity_from_cell(cell)
        self.assertIsNotNone(quantity)

        record = table_record_from_quantities([quantity])
        self.assertIsNotNone(record)
        return record

    def test_different_explicit_counts_create_difference_evidence(self):
        from app.review_evidence import (
            explicit_analysed_observation_count_difference,
        )

        full = self.make_record(
            section_label="All studies (150 data points)"
        )
        restricted = self.make_record(
            section_label=(
                "Exclude studies that do not indicate years of education "
                "(94 data points)"
            )
        )

        item = explicit_analysed_observation_count_difference(full, restricted)

        self.assertIsNotNone(item)
        self.assertEqual(
            item.relationship,
            EvidenceRelationship.ANALYSED_OBSERVATIONS,
        )
        self.assertEqual(
            item.kind,
            RelationshipEvidenceKind.EXPLICIT_DIFFERENCE,
        )
        self.assertIn("150 data points", item.description)
        self.assertIn("94 data points", item.description)
        self.assertIn("acquisition_method=vision", item.provenance)

    def test_difference_evidence_is_accepted_as_different(self):
        from app.review_evidence import (
            explicit_analysed_observation_count_difference,
        )

        full = self.make_record(
            section_label="All studies (150 data points)"
        )
        restricted = self.make_record(
            section_label="Restricted analysis (94 data points)"
        )

        item = explicit_analysed_observation_count_difference(full, restricted)
        self.assertIsNotNone(item)

        accepted = accept_relationship_evidence(
            EvidenceRelationship.ANALYSED_OBSERVATIONS,
            (item,),
        )

        self.assertEqual(
            accepted.state,
            RelationshipState.ESTABLISHED_DIFFERENT,
        )

    def test_equal_counts_do_not_create_identity_evidence(self):
        from app.review_evidence import (
            explicit_analysed_observation_count_difference,
        )

        left = self.make_record(
            section_label="First analysis (150 data points)"
        )
        right = self.make_record(
            section_label="Second analysis (150 data points)"
        )

        item = explicit_analysed_observation_count_difference(left, right)

        self.assertIsNone(item)

        accepted = accept_relationship_evidence(
            EvidenceRelationship.ANALYSED_OBSERVATIONS,
            (),
        )
        self.assertEqual(
            accepted.state,
            RelationshipState.NOT_ESTABLISHED,
        )

    def test_other_numbers_do_not_replace_explicit_data_point_count(self):
        from app.review_evidence import (
            explicit_analysed_observation_count_difference,
        )

        full = self.make_record(
            section_label="All studies (150 data points)"
        )
        restricted = self.make_record(
            section_label="Exclude small sample sizes (<50, 105 data points)"
        )

        item = explicit_analysed_observation_count_difference(full, restricted)

        self.assertIsNotNone(item)
        self.assertIn("150 data points", item.description)
        self.assertIn("105 data points", item.description)
        self.assertNotIn("versus 50 data points", item.description)

    def test_missing_count_creates_no_evidence(self):
        from app.review_evidence import (
            explicit_analysed_observation_count_difference,
        )

        left = self.make_record(
            section_label="All studies (150 data points)"
        )
        right = self.make_record(
            section_label="Sensitivity analysis"
        )

        self.assertIsNone(
            explicit_analysed_observation_count_difference(left, right)
        )

    def test_different_known_tables_create_no_evidence(self):
        from app.review_evidence import (
            explicit_analysed_observation_count_difference,
        )

        left = self.make_record(
            section_label="All studies (150 data points)",
            table_id="table-s8",
        )
        right = self.make_record(
            section_label="Restricted (94 data points)",
            table_id="table-other",
        )

        self.assertIsNone(
            explicit_analysed_observation_count_difference(left, right)
        )

    def test_different_rows_create_no_evidence(self):
        from app.review_evidence import (
            explicit_analysed_observation_count_difference,
        )

        left = self.make_record(
            section_label="All studies (150 data points)",
            row_label="RE Model",
        )
        right = self.make_record(
            section_label="Restricted (94 data points)",
            row_label="FE Model",
        )

        self.assertIsNone(
            explicit_analysed_observation_count_difference(left, right)
        )

    def test_real_s8_section_labels_preserve_count_semantics(self):
        from app.review_evidence import (
            explicit_analysed_observation_count_difference,
        )

        full = self.make_record(
            section_label="All studies (150 data points)"
        )
        small = self.make_record(
            section_label=(
                "Exclude small sample sizes (<50, 105 data points)"
            )
        )
        education = self.make_record(
            section_label=(
                "Exclude studies that do not indicate years of education "
                "(94 data points)"
            )
        )
        equal_count = self.make_record(
            section_label="Synthetic negative control (150 data points)"
        )

        small_item = explicit_analysed_observation_count_difference(
            full, small
        )
        education_item = explicit_analysed_observation_count_difference(
            full, education
        )
        equal_item = explicit_analysed_observation_count_difference(
            full, equal_count
        )

        self.assertIsNotNone(small_item)
        self.assertIn(
            "150 data points versus 105 data points",
            small_item.description,
        )
        self.assertNotIn(
            "versus 50 data points",
            small_item.description,
        )

        self.assertIsNotNone(education_item)
        self.assertIn(
            "150 data points versus 94 data points",
            education_item.description,
        )

        small_accepted = accept_relationship_evidence(
            EvidenceRelationship.ANALYSED_OBSERVATIONS,
            (small_item,),
        )
        education_accepted = accept_relationship_evidence(
            EvidenceRelationship.ANALYSED_OBSERVATIONS,
            (education_item,),
        )
        equal_accepted = accept_relationship_evidence(
            EvidenceRelationship.ANALYSED_OBSERVATIONS,
            (),
        )

        self.assertEqual(
            small_accepted.state,
            RelationshipState.ESTABLISHED_DIFFERENT,
        )
        self.assertEqual(
            education_accepted.state,
            RelationshipState.ESTABLISHED_DIFFERENT,
        )
        self.assertIsNone(equal_item)
        self.assertEqual(
            equal_accepted.state,
            RelationshipState.NOT_ESTABLISHED,
        )

    def test_multiple_explicit_counts_fail_closed(self):
        from app.review_evidence import (
            explicit_analysed_observation_count_difference,
        )

        left = self.make_record(
            section_label="All studies (150 data points)"
        )
        right = self.make_record(
            section_label="Primary 94 data points; secondary 80 data points"
        )

        self.assertIsNone(
            explicit_analysed_observation_count_difference(left, right)
        )


class CovariateAnalysisSpecificationEvidenceTests(unittest.TestCase):

    def make_record(
        self,
        *,
        row_label,
        header="Covariate Analysis",
        section="Cognitive flexibility",
        section_index=0,
        table_id="table-s9",
        source="paper.pdf",
    ):
        from app.table_evidence import TableRecord

        return TableRecord(
            source_name=source,
            page=66,
            table_evidence_id=table_id,
            caption="Table S9. Dose-response network meta-regression",
            section_index=section_index,
            section_label=section,
            row_index=0,
            row_label=row_label,
            row_label_header=header,
            quantities=(),
        )

    def difference(self, left, right):
        from app.review_evidence import (
            explicit_covariate_analysis_specification_difference,
        )
        return explicit_covariate_analysis_specification_difference(left, right)

    def test_unadjusted_and_age_create_explicit_difference(self):
        item = self.difference(
            self.make_record(row_label="Unadjusted"),
            self.make_record(row_label="Age"),
        )

        self.assertIsNotNone(item)
        self.assertEqual(
            item.relationship,
            EvidenceRelationship.MODEL_SPECIFICATION,
        )
        self.assertEqual(
            item.kind,
            RelationshipEvidenceKind.EXPLICIT_DIFFERENCE,
        )
        self.assertIn("'Unadjusted' versus 'Age'", item.description)

        accepted = accept_relationship_evidence(
            EvidenceRelationship.MODEL_SPECIFICATION,
            (item,),
        )
        self.assertEqual(
            accepted.state,
            RelationshipState.ESTABLISHED_DIFFERENT,
        )

    def test_equal_row_labels_create_no_identity_evidence(self):
        item = self.difference(
            self.make_record(row_label="Age"),
            self.make_record(row_label="Age"),
        )
        self.assertIsNone(item)

    def test_unrecognised_header_creates_no_evidence(self):
        item = self.difference(
            self.make_record(
                row_label="Unadjusted",
                header="Participant characteristic",
            ),
            self.make_record(
                row_label="Age",
                header="Participant characteristic",
            ),
        )
        self.assertIsNone(item)

    def test_model_header_is_not_generalised(self):
        item = self.difference(
            self.make_record(row_label="FE Model", header="Model"),
            self.make_record(row_label="RE Model", header="Model"),
        )
        self.assertIsNone(item)

    def test_missing_header_creates_no_evidence(self):
        item = self.difference(
            self.make_record(row_label="Unadjusted", header=None),
            self.make_record(row_label="Age", header=None),
        )
        self.assertIsNone(item)

    def test_different_sections_create_no_evidence(self):
        item = self.difference(
            self.make_record(
                row_label="Unadjusted",
                section="Cognitive flexibility",
            ),
            self.make_record(
                row_label="Age",
                section="Working memory",
            ),
        )
        self.assertIsNone(item)

    def test_repeated_section_label_at_different_position_creates_no_evidence(self):
        item = self.difference(
            self.make_record(
                row_label="Unadjusted",
                section="Cognitive flexibility",
                section_index=0,
            ),
            self.make_record(
                row_label="Age",
                section="Cognitive flexibility",
                section_index=1,
            ),
        )
        self.assertIsNone(item)

    def test_different_known_tables_create_no_evidence(self):
        item = self.difference(
            self.make_record(row_label="Unadjusted", table_id="table-s9"),
            self.make_record(row_label="Age", table_id="table-other"),
        )
        self.assertIsNone(item)

    def test_different_sources_create_no_evidence(self):
        item = self.difference(
            self.make_record(row_label="Unadjusted", source="main.pdf"),
            self.make_record(row_label="Age", source="supplement.pdf"),
        )
        self.assertIsNone(item)

class ReportedEvidenceValueTests(unittest.TestCase):

    def make_quantity(
        self,
        *,
        row_index=1,
        row_label="Age",
        row_label_header="Covariate Analysis",
        quantity_label="DIC",
        raw_value="245.273",
        central_value=245.273,
        lower_value=None,
        upper_value=None,
    ):
        return NamedQuantity(
            source_name="benchmark.pdf",
            page=66,
            table_evidence_id="table-s9",
            caption=(
                "Table S9. Dose-response network meta-regression "
                "of exercise effects"
            ),
            section_index=0,
            section_label="Cognitive flexibility",
            row_index=row_index,
            row_label=row_label,
            row_label_header=row_label_header,
            quantity_label=quantity_label,
            raw_value=raw_value,
            central_value=central_value,
            lower_value=lower_value,
            upper_value=upper_value,
            acquisition_method=AcquisitionMethod.VISION,
            extraction_source="structured_vision",
        )

    def test_named_dic_quantity_preserves_reported_identity(self):
        value = evidence_value_from_named_quantity(
            self.make_quantity()
        )

        self.assertEqual(value.parameter, "DIC")
        self.assertEqual(value.analysis, "Age")
        self.assertIsNone(value.outcome)
        self.assertIsNone(value.model)
        self.assertEqual(value.estimate, 245.273)
        self.assertEqual(
            value.identity_state,
            IdentityState.IDENTIFIED,
        )

    def test_negative_sd_is_reported_identity_not_validation(self):
        value = evidence_value_from_named_quantity(
            self.make_quantity(
                quantity_label="SD",
                raw_value="-10.28 (-31.49, -2.50)",
                central_value=-10.28,
                lower_value=-31.49,
                upper_value=-2.50,
            )
        )

        self.assertEqual(value.parameter, "SD")
        self.assertEqual(value.estimate, -10.28)
        self.assertEqual(value.interval_lower, -31.49)
        self.assertEqual(value.interval_upper, -2.50)
        self.assertIsNone(value.interval_type)
        self.assertEqual(
            value.identity_state,
            IdentityState.IDENTIFIED,
        )

    def test_arbitrary_row_dimension_is_not_analysis(self):
        value = evidence_value_from_named_quantity(
            self.make_quantity(
                row_label="Treatment",
                row_label_header="Group",
                quantity_label="Mean",
                raw_value="12.3",
                central_value=12.3,
            )
        )

        self.assertEqual(value.parameter, "Mean")
        self.assertIsNone(value.analysis)

    def test_s9_dic_values_form_comparison_opportunity(self):
        unadjusted = evidence_value_from_named_quantity(
            self.make_quantity(
                row_index=0,
                row_label="Unadjusted",
                raw_value="217.901",
                central_value=217.901,
            )
        )
        age = evidence_value_from_named_quantity(
            self.make_quantity()
        )

        comparison = compare_evidence_values(
            unadjusted,
            age,
        )

        self.assertEqual(
            comparison.comparability_state,
            ComparabilityState.COMPARISON_OPPORTUNITY,
        )
        self.assertEqual(
            comparison.relationship,
            ComparisonRelationship.SAME_FIT_METRIC_ACROSS_ANALYSES,
        )
        self.assertEqual(comparison.parameter, "DIC")
        self.assertIsNone(comparison.outcome)
        self.assertEqual(
            comparison.left_analysis,
            "Unadjusted",
        )
        self.assertEqual(
            comparison.right_analysis,
            "Age",
        )
        self.assertAlmostEqual(
            comparison.deterministic_difference,
            27.372,
        )
        self.assertIn(
            "not methodological comparability",
            comparison.reason.casefold(),
        )


if __name__ == "__main__":
    unittest.main()
