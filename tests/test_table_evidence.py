import unittest

from app.table_evidence import (
    AcquisitionMethod,
    AcquisitionState,
    RecordRelationshipEvidence,
    TableRecordFamily,
    TableRecordFamilyKind,
    parallel_schema_families,
    record_relationship_evidence,
    repeated_row_families,
    schema_extension_families,
    table_record_from_quantities,
    attach_page_vision_observation,
    table_evidence_from_selected,
    table_pages_from_evidence,
)


class TableEvidenceTests(unittest.TestCase):

    def test_selected_table_preserves_text_provenance(self):
        selected = [{
            "source": "pdfplumber_text",
            "page": 65,
            "table_index": 23,
            "label": "Table S8",
            "rows": [
                ["Model", "DIC", "SD"],
                ["RE Model", "551.563", "2.13"],
            ],
        }]

        evidence = table_evidence_from_selected("benchmark.pdf", selected)

        self.assertEqual(len(evidence), 1)
        table = evidence[0]
        self.assertEqual(table.source_name, "benchmark.pdf")
        self.assertEqual(table.label, "Table S8")
        self.assertEqual(table.pages, [65])
        self.assertEqual(len(table.text_observations), 1)

        observation = table.text_observations[0]
        self.assertEqual(observation.acquisition_method, AcquisitionMethod.TEXT)
        self.assertEqual(observation.extraction_source, "pdfplumber_text")
        self.assertEqual(observation.extraction_index, 23)
        self.assertIn("551.563", observation.content)
        self.assertIn("2.13", observation.content)

    def test_extraction_index_does_not_define_table_identity(self):
        base = {
            "source": "pdfplumber_text",
            "page": 65,
            "label": "Table S8",
            "rows": [["Model", "DIC"], ["RE", "551.563"]],
        }

        first = table_evidence_from_selected(
            "benchmark.pdf",
            [{**base, "table_index": 3}],
        )[0]
        second = table_evidence_from_selected(
            "benchmark.pdf",
            [{**base, "table_index": 99}],
        )[0]

        self.assertEqual(first.evidence_id, second.evidence_id)
        self.assertNotEqual(
            first.text_observations[0].extraction_index,
            second.text_observations[0].extraction_index,
        )

    def test_source_file_is_part_of_identity(self):
        table = {
            "source": "pdfplumber_text",
            "page": 4,
            "table_index": 1,
            "label": "Table 1",
            "rows": [["A", "B"], ["1", "2"]],
        }

        primary = table_evidence_from_selected("primary.pdf", [table])[0]
        supplement = table_evidence_from_selected("supplement.pdf", [table])[0]

        self.assertNotEqual(primary.evidence_id, supplement.evidence_id)

    def test_unlabelled_tables_on_same_page_are_not_silently_merged(self):
        selected = [
            {
                "source": "pdfplumber_text",
                "page": 12,
                "table_index": 1,
                "label": None,
                "rows": [["A", "B"], ["1", "2"]],
            },
            {
                "source": "pdfplumber_text",
                "page": 12,
                "table_index": 2,
                "label": None,
                "rows": [["C", "D"], ["3", "4"]],
            },
        ]

        evidence = table_evidence_from_selected("paper.pdf", selected)

        self.assertEqual(len(evidence), 2)
        self.assertNotEqual(evidence[0].evidence_id, evidence[1].evidence_id)

    def test_multiple_tables_can_share_one_page_evidence(self):
        selected = [
            {
                "source": "pdfplumber_text",
                "page": 12,
                "table_index": 1,
                "label": "Table 2",
                "rows": [["A", "B"], ["1", "2"]],
            },
            {
                "source": "pdfplumber_text",
                "page": 12,
                "table_index": 2,
                "label": "Table 3",
                "rows": [["C", "D"], ["3", "4"]],
            },
        ]

        tables = table_evidence_from_selected("paper.pdf", selected)
        pages = table_pages_from_evidence("paper.pdf", tables)

        self.assertEqual(len(pages), 1)
        self.assertEqual(pages[0].page, 12)
        self.assertEqual(len(pages[0].table_evidence_ids), 2)

    def test_page_vision_is_not_automatically_attached_to_individual_table(self):
        selected = [
            {
                "source": "pdfplumber_text",
                "page": 12,
                "table_index": 1,
                "label": "Table 2",
                "rows": [["A", "B"], ["1", "2"]],
            },
            {
                "source": "pdfplumber_text",
                "page": 12,
                "table_index": 2,
                "label": "Table 3",
                "rows": [["C", "D"], ["3", "4"]],
            },
        ]

        tables = table_evidence_from_selected("paper.pdf", selected)
        page = table_pages_from_evidence("paper.pdf", tables)[0]

        attach_page_vision_observation(
            page,
            "Table 2 ...\nTable 3 ...",
        )

        self.assertIsNotNone(page.vision_observation)
        self.assertEqual(
            page.vision_observation.acquisition_method,
            AcquisitionMethod.VISION,
        )
        self.assertEqual(
            page.vision_observation.acquisition_state,
            AcquisitionState.VISION_TRANSCRIBED,
        )
        self.assertTrue(all(not t.vision_observations for t in tables))


if __name__ == "__main__":
    unittest.main()


class TableVisionAcquisitionTests(unittest.TestCase):

    def page(self, number=12, ids=None):
        from app.table_evidence import TablePageEvidence
        return TablePageEvidence(
            source_name="paper.pdf",
            page=number,
            table_evidence_ids=ids or ["table-a"],
        )

    def test_acquires_one_visual_observation_per_table_page(self):
        from app.table_evidence import acquire_page_vision

        pages = [
            self.page(3, ["table-a", "table-b"]),
            self.page(7, ["table-c"]),
        ]
        calls = []

        def render(path, page, dpi):
            calls.append(("render", page, dpi))
            return f"png-{page}".encode()

        def transcribe(png, prompt):
            page = int(png.decode().split("-")[1])
            calls.append(("transcribe", page, prompt))
            return f"Header | Value\nrow | {page}"

        result = acquire_page_vision(
            pages,
            "paper.pdf",
            render_page=render,
            transcribe=transcribe,
            prompt="TRANSCRIBE TABLES",
            dpi=200,
        )

        self.assertEqual(len(result), 2)
        self.assertEqual(
            [r.vision_observation.acquisition_state for r in result],
            [
                AcquisitionState.VISION_TRANSCRIBED,
                AcquisitionState.VISION_TRANSCRIBED,
            ],
        )
        self.assertEqual(result[0].table_evidence_ids, ["table-a", "table-b"])
        self.assertEqual(result[1].table_evidence_ids, ["table-c"])
        self.assertEqual(
            calls,
            [
                ("render", 3, 200),
                ("transcribe", 3, "TRANSCRIBE TABLES"),
                ("render", 7, 200),
                ("transcribe", 7, "TRANSCRIBE TABLES"),
            ],
        )

    def test_visual_observation_remains_page_level_with_multiple_tables(self):
        from app.table_evidence import acquire_page_vision

        page = self.page(12, ["table-2", "table-3"])

        result = acquire_page_vision(
            [page],
            "paper.pdf",
            render_page=lambda path, number, dpi: b"png",
            transcribe=lambda png, prompt: (
                "Table 2 | value\nA | 1\nTable 3 | value\nB | 2"
            ),
            prompt="TRANSCRIBE",
        )

        self.assertEqual(
            result[0].table_evidence_ids,
            ["table-2", "table-3"],
        )
        self.assertEqual(
            result[0].vision_observation.acquisition_method,
            AcquisitionMethod.VISION,
        )
        self.assertIn("Table 2", result[0].vision_observation.content)
        self.assertIn("Table 3", result[0].vision_observation.content)

    def test_render_failure_is_an_explicit_observation(self):
        from app.table_evidence import acquire_page_vision

        result = acquire_page_vision(
            [self.page(8)],
            "paper.pdf",
            render_page=lambda path, number, dpi: b"",
            transcribe=lambda png, prompt: self.fail(
                "transcriber must not run after render failure"
            ),
            prompt="TRANSCRIBE",
        )

        observation = result[0].vision_observation
        self.assertEqual(
            observation.acquisition_state,
            AcquisitionState.RENDER_FAILED,
        )
        self.assertEqual(observation.content, "")

    def test_renderer_exception_is_contained(self):
        from app.table_evidence import acquire_page_vision

        def fail_render(path, number, dpi):
            raise RuntimeError("renderer unavailable")

        result = acquire_page_vision(
            [self.page(9)],
            "paper.pdf",
            render_page=fail_render,
            transcribe=lambda png, prompt: "must not run",
            prompt="TRANSCRIBE",
        )

        self.assertEqual(
            result[0].vision_observation.acquisition_state,
            AcquisitionState.RENDER_FAILED,
        )

    def test_empty_transcription_is_an_explicit_observation(self):
        from app.table_evidence import acquire_page_vision

        result = acquire_page_vision(
            [self.page(5)],
            "paper.pdf",
            render_page=lambda path, number, dpi: b"png",
            transcribe=lambda png, prompt: "",
            prompt="TRANSCRIBE",
        )

        self.assertEqual(
            result[0].vision_observation.acquisition_state,
            AcquisitionState.VISION_EMPTY,
        )

    def test_transcriber_exception_is_recorded_as_failure(self):
        from app.table_evidence import acquire_page_vision

        def fail_transcription(png, prompt):
            raise RuntimeError("vision backend unavailable")

        result = acquire_page_vision(
            [self.page(6)],
            "paper.pdf",
            render_page=lambda path, number, dpi: b"png",
            transcribe=fail_transcription,
            prompt="TRANSCRIBE",
        )

        self.assertEqual(
            result[0].vision_observation.acquisition_state,
            AcquisitionState.VISION_FAILED,
        )

    def test_exact_no_table_response_has_distinct_state(self):
        from app.table_evidence import acquire_page_vision

        result = acquire_page_vision(
            [self.page(10)],
            "paper.pdf",
            render_page=lambda path, number, dpi: b"png",
            transcribe=lambda png, prompt: "No table on this page.",
            prompt="TRANSCRIBE",
        )

        self.assertEqual(
            result[0].vision_observation.acquisition_state,
            AcquisitionState.VISION_REPORTED_NO_TABLE,
        )

    def test_uncertain_no_table_language_is_not_silently_discarded(self):
        from app.table_evidence import acquire_page_vision

        result = acquire_page_vision(
            [self.page(11)],
            "paper.pdf",
            render_page=lambda path, number, dpi: b"png",
            transcribe=lambda png, prompt: (
                "I cannot clearly determine whether a table is present."
            ),
            prompt="TRANSCRIBE",
        )

        self.assertEqual(
            result[0].vision_observation.acquisition_state,
            AcquisitionState.VISION_TRANSCRIBED,
        )
        self.assertTrue(result[0].vision_observation.content)

    def test_acquisition_does_not_mutate_input_page(self):
        from app.table_evidence import acquire_page_vision

        original = self.page(14, ["table-x"])

        result = acquire_page_vision(
            [original],
            "paper.pdf",
            render_page=lambda path, number, dpi: b"png",
            transcribe=lambda png, prompt: "A | B\n1 | 2",
            prompt="TRANSCRIBE",
        )

        self.assertIsNone(original.vision_observation)
        self.assertIsNotNone(result[0].vision_observation)
        self.assertEqual(original.table_evidence_ids, ["table-x"])


class StructuredTableObservationTests(unittest.TestCase):

    def observation(self, content):
        from app.table_evidence import TableObservation
        return TableObservation(
            acquisition_method=AcquisitionMethod.VISION,
            content=content,
            page=7,
            extraction_source="vision",
            acquisition_state=AcquisitionState.VISION_TRANSCRIBED,
        )

    def parse(self, content):
        from app.table_evidence import parse_structured_table_observation
        return parse_structured_table_observation(self.observation(content))

    def assert_parse_error(self, content):
        from app.table_evidence import (
            StructuredTableParseError,
            parse_structured_table_observation,
        )
        with self.assertRaises(StructuredTableParseError):
            parse_structured_table_observation(self.observation(content))

    def valid_payload(self):
        return """{
          "caption": "Table 2. Example results",
          "columns": [
            {"index": 0, "header": "Analysis"},
            {"index": 1, "header": "Estimate"},
            {"index": 2, "header": "Uncertainty"}
          ],
          "sections": [{
            "label": "Outcome A",
            "rows": [{
              "label": "Model 1",
              "cells": [
                {"column_index": 1, "value": "10.08"},
                {"column_index": 2, "value": "(8.07, 12.71)"}
              ]
            }]
          }]
        }"""

    def test_valid_structure_preserves_identity_and_values(self):
        result = self.parse(self.valid_payload())
        self.assertEqual(result.caption, "Table 2. Example results")
        self.assertEqual(
            [c.header for c in result.columns],
            ["Analysis", "Estimate", "Uncertainty"],
        )
        self.assertEqual(result.sections[0].label, "Outcome A")
        self.assertEqual(result.sections[0].rows[0].label, "Model 1")
        self.assertEqual(
            [c.value for c in result.sections[0].rows[0].cells],
            ["10.08", "(8.07, 12.71)"],
        )

    def test_original_observation_is_retained_verbatim(self):
        content = self.valid_payload()
        observation = self.observation(content)
        from app.table_evidence import parse_structured_table_observation
        result = parse_structured_table_observation(observation)
        self.assertIs(result.source_observation, observation)
        self.assertEqual(result.source_observation.content, content)

    def test_markdown_json_fence_is_accepted(self):
        result = self.parse("```json\n" + self.valid_payload() + "\n```")
        self.assertEqual(result.caption, "Table 2. Example results")

    def test_invalid_json_fails_closed(self):
        self.assert_parse_error('{"columns": [')

    def test_non_object_root_fails_closed(self):
        self.assert_parse_error("[]")

    def test_missing_columns_fails_closed(self):
        self.assert_parse_error('{"sections": []}')

    def test_duplicate_column_indices_fail_closed(self):
        self.assert_parse_error("""{
          "columns": [
            {"index": 0, "header": "A"},
            {"index": 0, "header": "B"}
          ],
          "sections": []
        }""")

    def test_boolean_column_index_fails_closed(self):
        self.assert_parse_error("""{
          "columns": [{"index": true, "header": "A"}],
          "sections": []
        }""")

    def test_unknown_cell_column_fails_closed(self):
        self.assert_parse_error("""{
          "columns": [
            {"index": 0, "header": "Row"},
            {"index": 1, "header": "Value"}
          ],
          "sections": [{
            "label": null,
            "rows": [{
              "label": "A",
              "cells": [{"column_index": 2, "value": "4.2"}]
            }]
          }]
        }""")

    def test_duplicate_cell_column_fails_closed(self):
        self.assert_parse_error("""{
          "columns": [
            {"index": 0, "header": "Row"},
            {"index": 1, "header": "Value"}
          ],
          "sections": [{
            "label": null,
            "rows": [{
              "label": "A",
              "cells": [
                {"column_index": 1, "value": "4.2"},
                {"column_index": 1, "value": "4.3"}
              ]
            }]
          }]
        }""")

    def test_missing_cells_are_not_invented(self):
        result = self.parse("""{
          "caption": null,
          "columns": [
            {"index": 0, "header": "Row"},
            {"index": 1, "header": "A"},
            {"index": 2, "header": "B"}
          ],
          "sections": [{
            "label": null,
            "rows": [{
              "label": "Result",
              "cells": [{"column_index": 1, "value": "5"}]
            }]
          }]
        }""")
        cells = result.sections[0].rows[0].cells
        self.assertEqual(len(cells), 1)
        self.assertEqual(cells[0].column_index, 1)

    def test_negative_value_is_preserved(self):
        value = "-10.28 (-31.49, -2.50)"
        result = self.parse(f"""{{
          "caption": null,
          "columns": [
            {{"index": 0, "header": "Row"}},
            {{"index": 1, "header": "Parameter"}}
          ],
          "sections": [{{
            "label": null,
            "rows": [{{
              "label": "Analysis A",
              "cells": [{{"column_index": 1, "value": "{value}"}}]
            }}]
          }}]
        }}""")
        self.assertEqual(result.sections[0].rows[0].cells[0].value, value)

    def test_combined_quantity_remains_one_string(self):
        value = "2.13 (1.79, 2.54)"
        result = self.parse(f"""{{
          "caption": null,
          "columns": [
            {{"index": 0, "header": "Row"}},
            {{"index": 1, "header": "Reported quantity"}}
          ],
          "sections": [{{
            "label": null,
            "rows": [{{
              "label": "A",
              "cells": [{{"column_index": 1, "value": "{value}"}}]
            }}]
          }}]
        }}""")
        self.assertEqual(result.sections[0].rows[0].cells[0].value, value)

    def test_non_numeric_table_is_valid(self):
        result = self.parse("""{
          "caption": "Descriptive table",
          "columns": [
            {"index": 0, "header": "Category"},
            {"index": 1, "header": "Description"}
          ],
          "sections": [{
            "label": null,
            "rows": [{
              "label": "Group A",
              "cells": [{"column_index": 1, "value": "Moderate"}]
            }]
          }]
        }""")
        self.assertEqual(
            result.sections[0].rows[0].cells[0].value,
            "Moderate",
        )


class TableCellEvidenceTests(unittest.TestCase):

    def structured(self):
        from app.table_evidence import (
            AcquisitionMethod,
            AcquisitionState,
            TableObservation,
            parse_structured_table_observation,
        )

        observation = TableObservation(
            acquisition_method=AcquisitionMethod.VISION,
            content="""{
              "caption": "Table S9. Example",
              "columns": [
                {"index": 0, "header": "Covariate Analysis"},
                {"index": 1, "header": "DIC"},
                {"index": 5, "header": "SD"}
              ],
              "sections": [{
                "label": "Cognitive flexibility",
                "rows": [{
                  "label": "Age",
                  "cells": [
                    {"column_index": 1, "value": "245.273"},
                    {"column_index": 5, "value": "-10.28 (-31.49, -2.50)"}
                  ]
                }]
              }]
            }""",
            page=66,
            extraction_source="vision",
            acquisition_state=AcquisitionState.VISION_TRANSCRIBED,
        )
        return parse_structured_table_observation(observation)

    def cells(self, table_evidence_id=None):
        from app.table_evidence import cell_evidence_from_structured_observation
        return cell_evidence_from_structured_observation(
            "manuscript.pdf",
            self.structured(),
            table_evidence_id=table_evidence_id,
        )

    def test_one_evidence_object_per_observed_cell(self):
        cells = self.cells()
        self.assertEqual(len(cells), 2)

    def test_structural_path_is_preserved(self):
        cell = self.cells()[0]
        self.assertEqual(cell.source_name, "manuscript.pdf")
        self.assertEqual(cell.page, 66)
        self.assertEqual(cell.caption, "Table S9. Example")
        self.assertEqual(cell.section_label, "Cognitive flexibility")
        self.assertEqual(cell.row_label, "Age")
        self.assertEqual(cell.column_index, 1)
        self.assertEqual(cell.column_header, "DIC")
        self.assertEqual(cell.observed_value, "245.273")

    def test_observed_value_is_not_parsed_or_corrected(self):
        cell = self.cells()[1]
        self.assertEqual(cell.column_header, "SD")
        self.assertEqual(
            cell.observed_value,
            "-10.28 (-31.49, -2.50)",
        )
        self.assertIsInstance(cell.observed_value, str)

    def test_acquisition_provenance_is_preserved(self):
        from app.table_evidence import AcquisitionMethod
        cell = self.cells()[0]
        self.assertIs(cell.acquisition_method, AcquisitionMethod.VISION)
        self.assertEqual(cell.extraction_source, "vision")

    def test_table_identity_is_not_inferred(self):
        for cell in self.cells():
            self.assertIsNone(cell.table_evidence_id)

    def test_explicit_table_identity_can_be_preserved(self):
        cells = self.cells("table-explicit")
        self.assertTrue(
            all(cell.table_evidence_id == "table-explicit" for cell in cells)
        )

    def test_sparse_column_indices_are_preserved(self):
        cells = self.cells()
        self.assertEqual(
            [(cell.column_index, cell.column_header) for cell in cells],
            [(1, "DIC"), (5, "SD")],
        )


class ParsedQuantityTests(unittest.TestCase):

    def parse(self, value):
        from app.table_evidence import parse_quantity_syntax
        return parse_quantity_syntax(value)

    def test_plain_number(self):
        result = self.parse("245.273")
        self.assertIsNotNone(result)
        self.assertEqual(result.raw_value, "245.273")
        self.assertEqual(result.central_value, 245.273)
        self.assertIsNone(result.lower_value)
        self.assertIsNone(result.upper_value)

    def test_negative_number(self):
        result = self.parse("-61.40")
        self.assertIsNotNone(result)
        self.assertEqual(result.central_value, -61.40)

    def test_number_with_interval(self):
        result = self.parse("-10.28 (-31.49, -2.50)")
        self.assertIsNotNone(result)
        self.assertEqual(result.central_value, -10.28)
        self.assertEqual(result.lower_value, -31.49)
        self.assertEqual(result.upper_value, -2.50)

    def test_positive_interval(self):
        result = self.parse("2.13 (1.79, 2.54)")
        self.assertIsNotNone(result)
        self.assertEqual(result.central_value, 2.13)
        self.assertEqual(result.lower_value, 1.79)
        self.assertEqual(result.upper_value, 2.54)

    def test_whitespace_does_not_change_numeric_parse(self):
        result = self.parse("  6.88 ( 5.13, 9.15 )  ")
        self.assertIsNotNone(result)
        self.assertEqual(result.central_value, 6.88)
        self.assertEqual(result.lower_value, 5.13)
        self.assertEqual(result.upper_value, 9.15)

    def test_raw_value_is_preserved_verbatim(self):
        raw = "  2.13 (1.79, 2.54) "
        result = self.parse(raw)
        self.assertIsNotNone(result)
        self.assertEqual(result.raw_value, raw)

    def test_missing_marker_is_not_parsed(self):
        self.assertIsNone(self.parse("NA"))
        self.assertIsNone(self.parse("-"))

    def test_percentage_is_not_parsed(self):
        self.assertIsNone(self.parse("95%"))

    def test_plus_minus_is_not_parsed(self):
        self.assertIsNone(self.parse("67.3±5.2"))

    def test_inequality_is_not_parsed(self):
        self.assertIsNone(self.parse("<50"))

    def test_split_interval_is_not_repaired(self):
        self.assertIsNone(self.parse("(1.79,"))
        self.assertIsNone(self.parse("2.54)"))

    def test_mixed_corrupted_cell_is_not_repaired(self):
        self.assertIsNone(self.parse("108.953 – 10.08"))

    def test_descriptive_text_is_not_parsed(self):
        self.assertIsNone(self.parse("Moderate"))
        self.assertIsNone(self.parse("RE Model"))


class NamedQuantityTests(unittest.TestCase):

    def make_cell(
        self,
        *,
        section="Cognitive flexibility",
        row="Age",
        column="SD",
        value="-10.28 (-31.49, -2.50)",
        table_id=None,
    ):
        from app.table_evidence import AcquisitionMethod, TableCellEvidence

        return TableCellEvidence(
            source_name="paper.pdf",
            page=66,
            table_evidence_id=table_id,
            caption="Table S9. Dose-response network meta-regression",
            section_index=0,
            section_label=section,
            row_index=0,
            row_label_header=None,
            row_label=row,
            column_index=5,
            column_header=column,
            observed_value=value,
            acquisition_method=AcquisitionMethod.VISION,
            extraction_source="vision",
        )

    def test_literal_structure_is_preserved(self):
        from app.table_evidence import named_quantity_from_cell

        result = named_quantity_from_cell(self.make_cell())

        self.assertIsNotNone(result)
        self.assertEqual(result.section_label, "Cognitive flexibility")
        self.assertEqual(result.row_label, "Age")
        self.assertEqual(result.quantity_label, "SD")

    def test_numeric_syntax_is_preserved(self):
        from app.table_evidence import named_quantity_from_cell

        result = named_quantity_from_cell(self.make_cell())

        self.assertEqual(result.raw_value, "-10.28 (-31.49, -2.50)")
        self.assertEqual(result.central_value, -10.28)
        self.assertEqual(result.lower_value, -31.49)
        self.assertEqual(result.upper_value, -2.50)

    def test_provenance_is_preserved(self):
        from app.table_evidence import AcquisitionMethod, named_quantity_from_cell

        result = named_quantity_from_cell(
            self.make_cell(table_id="table-s9")
        )

        self.assertEqual(result.source_name, "paper.pdf")
        self.assertEqual(result.page, 66)
        self.assertEqual(result.table_evidence_id, "table-s9")
        self.assertEqual(
            result.caption,
            "Table S9. Dose-response network meta-regression",
        )
        self.assertEqual(result.acquisition_method, AcquisitionMethod.VISION)
        self.assertEqual(result.extraction_source, "vision")

    def test_descriptive_cell_does_not_become_named_quantity(self):
        from app.table_evidence import named_quantity_from_cell

        result = named_quantity_from_cell(
            self.make_cell(
                section="Cognitive flexibility",
                row="Brisk walking",
                column="Intensity",
                value="Moderate",
            )
        )

        self.assertIsNone(result)

    def test_missing_marker_does_not_become_named_quantity(self):
        from app.table_evidence import named_quantity_from_cell

        self.assertIsNone(
            named_quantity_from_cell(self.make_cell(value="-"))
        )

    def test_quantity_label_is_not_normalised(self):
        from app.table_evidence import named_quantity_from_cell

        result = named_quantity_from_cell(
            self.make_cell(
                section="All studies (150 data points)",
                row="RE Model",
                column="SD (95% CrI)",
                value="2.13 (1.79, 2.54)",
            )
        )

        self.assertEqual(result.quantity_label, "SD (95% CrI)")

    def test_no_semantic_role_fields_are_added(self):
        from app.table_evidence import named_quantity_from_cell

        result = named_quantity_from_cell(self.make_cell())

        self.assertFalse(hasattr(result, "outcome"))
        self.assertFalse(hasattr(result, "analysis"))
        self.assertFalse(hasattr(result, "model"))
        self.assertFalse(hasattr(result, "parameter"))
        self.assertFalse(hasattr(result, "interval_type"))
        self.assertFalse(hasattr(result, "comparability"))

    def test_same_literal_labels_do_not_imply_comparability(self):
        from app.table_evidence import named_quantity_from_cell

        s7 = named_quantity_from_cell(
            self.make_cell(
                section="Cognitive flexibility",
                row="Restricted cubic spline",
                column="DIC",
                value="478.2",
                table_id="table-s7",
            )
        )
        s9 = named_quantity_from_cell(
            self.make_cell(
                section="Cognitive flexibility",
                row="Unadjusted",
                column="DIC",
                value="217.901",
                table_id="table-s9",
            )
        )

        self.assertEqual(s7.section_label, s9.section_label)
        self.assertEqual(s7.quantity_label, s9.quantity_label)
        self.assertNotEqual(s7.table_evidence_id, s9.table_evidence_id)
        self.assertFalse(hasattr(s7, "comparable"))
        self.assertFalse(hasattr(s9, "comparable"))


class TableRecordTestHelpers:

    def make_quantity(
        self,
        *,
        page=65,
        table_id="table-s8",
        section="Cognitive flexibility",
        row="RE Model",
        label="DIC",
        value="217.901",
        source_name="paper.pdf",
    ):
        from app.table_evidence import (
            AcquisitionMethod,
            TableCellEvidence,
            named_quantity_from_cell,
        )

        cell = TableCellEvidence(
            source_name=source_name,
            page=page,
            table_evidence_id=table_id,
            caption=f"Table on page {page}",
            section_index=0,
            section_label=section,
            row_index=0,
            row_label_header=None,
            row_label=row,
            column_index=1,
            column_header=label,
            observed_value=value,
            acquisition_method=AcquisitionMethod.VISION,
            extraction_source="vision",
        )
        result = named_quantity_from_cell(cell)
        self.assertIsNotNone(result)
        return result

class TableRecordTests(TableRecordTestHelpers, unittest.TestCase):

    def test_record_preserves_structural_row_and_quantities(self):
        from app.table_evidence import table_record_from_quantities

        dic = self.make_quantity(label="DIC", value="217.901")
        pd = self.make_quantity(label="pD", value="108.948")

        record = table_record_from_quantities([dic, pd])

        self.assertIsNotNone(record)
        self.assertEqual(record.source_name, "paper.pdf")
        self.assertEqual(record.page, 65)
        self.assertEqual(record.table_evidence_id, "table-s8")
        self.assertEqual(record.section_label, "Cognitive flexibility")
        self.assertEqual(record.row_label, "RE Model")
        self.assertEqual(record.quantities, (dic, pd))

    def test_record_preserves_structural_positions(self):
        from dataclasses import replace
        from app.table_evidence import table_record_from_quantities

        first = self.make_quantity(label="DIC", value="217.901")
        second = self.make_quantity(label="pD", value="108.948")

        first = replace(first, section_index=2, row_index=7)
        second = replace(second, section_index=2, row_index=7)

        record = table_record_from_quantities([first, second])

        self.assertIsNotNone(record)
        self.assertEqual(record.section_index, 2)
        self.assertEqual(record.row_index, 7)

    def test_empty_quantity_collection_does_not_form_record(self):
        from app.table_evidence import table_record_from_quantities

        self.assertIsNone(table_record_from_quantities([]))

    def test_mixed_rows_are_rejected(self):
        from app.table_evidence import table_record_from_quantities

        left = self.make_quantity(row="RE Model", label="DIC")
        right = self.make_quantity(row="RE UME", label="pD", value="109.062")

        with self.assertRaises(ValueError):
            table_record_from_quantities([left, right])

    def test_mixed_provenance_is_rejected(self):
        from app.table_evidence import table_record_from_quantities

        left = self.make_quantity(
            page=65,
            table_id="table-s8",
            label="DIC",
        )
        right = self.make_quantity(
            page=66,
            table_id="table-s9",
            label="pD",
            value="108.948",
        )

        with self.assertRaises(ValueError):
            table_record_from_quantities([left, right])

    def test_record_adds_no_semantic_role_or_comparability(self):
        from app.table_evidence import table_record_from_quantities

        record = table_record_from_quantities([
            self.make_quantity(label="DIC"),
            self.make_quantity(label="pD", value="108.948"),
        ])

        self.assertFalse(hasattr(record, "analysis"))
        self.assertFalse(hasattr(record, "model"))
        self.assertFalse(hasattr(record, "outcome"))
        self.assertFalse(hasattr(record, "comparable"))


class RecordCorrespondenceTests(TableRecordTestHelpers, unittest.TestCase):

    def make_record(
        self,
        *,
        page,
        table_id,
        section,
        row,
        values,
    ):
        from app.table_evidence import table_record_from_quantities

        quantities = [
            self.make_quantity(
                page=page,
                table_id=table_id,
                section=section,
                row=row,
                label=label,
                value=value,
            )
            for label, value in values
        ]
        return table_record_from_quantities(quantities)

    def test_three_exact_fields_establish_correspondence_evidence(self):
        from app.table_evidence import record_correspondence

        left = self.make_record(
            page=65,
            table_id="table-s8",
            section="Cognitive flexibility",
            row="RE Model",
            values=[
                ("DIC", "217.901"),
                ("pD", "108.948"),
                ("Residual Deviance", "108.953"),
            ],
        )
        right = self.make_record(
            page=66,
            table_id="table-s9",
            section="Cognitive flexibility",
            row="Unadjusted",
            values=[
                ("DIC", "217.901"),
                ("pD", "108.948"),
                ("Residual Deviance", "108.953"),
            ],
        )

        result = record_correspondence(left, right)

        self.assertIsNotNone(result)
        self.assertEqual(
            result.exact_labels,
            ("dic", "pd", "residual deviance"),
        )
        self.assertEqual(result.different_labels, ())

    def test_single_exact_field_is_insufficient(self):
        from app.table_evidence import record_correspondence

        left = self.make_record(
            page=64,
            table_id="table-s7",
            section="Cognitive flexibility",
            row="Spline",
            values=[
                ("DIC", "217.901"),
                ("pD", "104.8"),
            ],
        )
        right = self.make_record(
            page=66,
            table_id="table-s9",
            section="Cognitive flexibility",
            row="Unadjusted",
            values=[
                ("DIC", "217.901"),
                ("pD", "108.948"),
            ],
        )

        self.assertIsNone(record_correspondence(left, right))

    def test_differing_shared_fields_are_retained(self):
        from app.table_evidence import record_correspondence

        left = self.make_record(
            page=65,
            table_id="table-s8",
            section="Cognitive flexibility",
            row="RE Model",
            values=[
                ("DIC", "217.901"),
                ("pD", "108.948"),
                ("Residual Deviance", "108.953"),
                ("Mean", "1.0"),
            ],
        )
        right = self.make_record(
            page=66,
            table_id="table-s9",
            section="Cognitive flexibility",
            row="Unadjusted",
            values=[
                ("DIC", "217.901"),
                ("pD", "108.948"),
                ("Residual Deviance", "108.953"),
                ("Mean", "2.0"),
            ],
        )

        result = record_correspondence(left, right)

        self.assertIsNotNone(result)
        self.assertEqual(result.different_labels, ("mean",))
        self.assertIn("mean", result.shared_labels)

    def test_case_and_whitespace_only_are_normalised(self):
        from app.table_evidence import record_correspondence

        left = self.make_record(
            page=65,
            table_id="table-s8",
            section="Cognitive flexibility",
            row="RE Model",
            values=[
                ("Residual Deviance", "108.953"),
                ("DIC", "217.901"),
            ],
        )
        right = self.make_record(
            page=66,
            table_id="table-s9",
            section="Cognitive flexibility",
            row="Unadjusted",
            values=[
                (" residual   deviance ", "108.953"),
                ("dic", "217.901"),
            ],
        )

        result = record_correspondence(left, right)

        self.assertIsNotNone(result)
        self.assertEqual(result.exact_labels, ("dic", "residual deviance"))

    def test_sd_and_sd_with_interval_label_are_not_equated(self):
        from app.table_evidence import record_correspondence

        left = self.make_record(
            page=65,
            table_id="table-s8",
            section="Cognitive flexibility",
            row="RE Model",
            values=[
                ("DIC", "217.901"),
                ("SD (95%CrI)", "10.08 (8.07, 12.71)"),
            ],
        )
        right = self.make_record(
            page=66,
            table_id="table-s9",
            section="Cognitive flexibility",
            row="Unadjusted",
            values=[
                ("DIC", "217.901"),
                ("SD", "10.08 (8.07, 12.71)"),
            ],
        )

        self.assertIsNone(record_correspondence(left, right))

    def test_duplicate_normalised_quantity_labels_are_rejected(self):
        from app.table_evidence import record_correspondence

        left = self.make_record(
            page=65,
            table_id="table-s8",
            section="Cognitive flexibility",
            row="RE Model",
            values=[
                ("DIC", "217.901"),
                (" dic ", "217.901"),
            ],
        )
        right = self.make_record(
            page=66,
            table_id="table-s9",
            section="Cognitive flexibility",
            row="Unadjusted",
            values=[
                ("DIC", "217.901"),
                ("pD", "108.948"),
            ],
        )

        with self.assertRaises(ValueError):
            record_correspondence(left, right)

    def test_threshold_cannot_be_weakened_to_one_field(self):
        from app.table_evidence import record_correspondence

        left = self.make_record(
            page=65,
            table_id="table-s8",
            section="Cognitive flexibility",
            row="RE Model",
            values=[("DIC", "217.901")],
        )
        right = self.make_record(
            page=66,
            table_id="table-s9",
            section="Cognitive flexibility",
            row="Unadjusted",
            values=[("DIC", "217.901")],
        )

        with self.assertRaises(ValueError):
            record_correspondence(
                left,
                right,
                minimum_exact_fields=1,
            )

    def test_correspondence_adds_no_semantic_claims(self):
        from app.table_evidence import record_correspondence

        left = self.make_record(
            page=65,
            table_id="table-s8",
            section="Cognitive flexibility",
            row="RE Model",
            values=[
                ("DIC", "217.901"),
                ("pD", "108.948"),
            ],
        )
        right = self.make_record(
            page=66,
            table_id="table-s9",
            section="Cognitive flexibility",
            row="Unadjusted",
            values=[
                ("DIC", "217.901"),
                ("pD", "108.948"),
            ],
        )

        result = record_correspondence(left, right)

        self.assertIsNotNone(result)
        self.assertFalse(hasattr(result, "same_analysis"))
        self.assertFalse(hasattr(result, "equivalent"))
        self.assertFalse(hasattr(result, "comparable"))
        self.assertFalse(hasattr(result, "methodologically_valid"))


class TableRecordFamilyTests(TableRecordTestHelpers, unittest.TestCase):

    def make_record(
        self,
        *,
        section_label,
        row_label,
        labels,
        page=10,
        table_id=None,
        source_name="paper.pdf",
    ):
        quantities = [
            self.make_quantity(
                page=page,
                table_id=table_id if table_id is not None else f"table-{page}",
                section=section_label,
                row=row_label,
                label=label,
                value=str(index + 1),
                source_name=source_name,
            )
            for index, label in enumerate(labels)
        ]
        return table_record_from_quantities(quantities)

    def test_parallel_schema_groups_same_section_and_schema(self):
        first = self.make_record(
            section_label="Outcome A",
            row_label="Form one",
            labels=["DIC", "pD"],
        )
        second = self.make_record(
            section_label="Outcome A",
            row_label="Form two",
            labels=["DIC", "pD"],
        )

        families = parallel_schema_families([first, second])

        self.assertEqual(len(families), 1)
        family = families[0]
        self.assertEqual(
            family.kind,
            TableRecordFamilyKind.PARALLEL_SCHEMA,
        )
        self.assertEqual(family.members, (first, second))
        self.assertIsNone(family.base_record)
        self.assertEqual(family.added_quantity_labels, ())

    def test_parallel_schema_does_not_merge_different_sections(self):
        first = self.make_record(
            section_label="Outcome A",
            row_label="Form one",
            labels=["DIC"],
        )
        second = self.make_record(
            section_label="Outcome B",
            row_label="Form two",
            labels=["DIC"],
        )

        self.assertEqual(
            parallel_schema_families([first, second]),
            [],
        )

    def test_parallel_schema_does_not_merge_different_pages(self):
        first = self.make_record(
            section_label="Outcome",
            row_label="Form one",
            labels=["DIC"],
            page=10,
        )
        second = self.make_record(
            section_label="Outcome",
            row_label="Form two",
            labels=["DIC"],
            page=11,
        )

        self.assertEqual(
            parallel_schema_families([first, second]),
            [],
        )

    def test_repeated_row_groups_across_sections(self):
        first = self.make_record(
            section_label="Full data",
            row_label="Same row",
            labels=["DIC", "pD"],
        )
        second = self.make_record(
            section_label="Restricted data",
            row_label="Same row",
            labels=["DIC", "pD"],
        )

        families = repeated_row_families([first, second])

        self.assertEqual(len(families), 1)
        family = families[0]
        self.assertEqual(
            family.kind,
            TableRecordFamilyKind.REPEATED_ROW,
        )
        self.assertEqual(family.members, (first, second))
        self.assertIsNone(family.base_record)

    def test_repeated_row_requires_distinct_sections(self):
        first = self.make_record(
            section_label="Same section",
            row_label="Repeated",
            labels=["DIC"],
        )
        second = self.make_record(
            section_label="Same section",
            row_label="Repeated",
            labels=["DIC"],
        )

        self.assertEqual(
            repeated_row_families([first, second]),
            [],
        )

    def test_repeated_row_requires_same_schema(self):
        first = self.make_record(
            section_label="First",
            row_label="Repeated",
            labels=["DIC"],
        )
        second = self.make_record(
            section_label="Second",
            row_label="Repeated",
            labels=["DIC", "pD"],
        )

        self.assertEqual(
            repeated_row_families([first, second]),
            [],
        )

    def test_schema_extension_preserves_base_and_extensions(self):
        base = self.make_record(
            section_label="Outcome",
            row_label="Reference",
            labels=["DIC", "pD"],
        )
        first = self.make_record(
            section_label="Outcome",
            row_label="Alternative one",
            labels=["DIC", "pD", "Beta"],
        )
        second = self.make_record(
            section_label="Outcome",
            row_label="Alternative two",
            labels=["DIC", "pD", "Beta"],
        )

        families = schema_extension_families(
            [base, first, second]
        )

        self.assertEqual(len(families), 1)
        family = families[0]

        self.assertEqual(
            family.kind,
            TableRecordFamilyKind.SCHEMA_EXTENSION,
        )
        self.assertEqual(family.base_record, base)
        self.assertEqual(family.members, (first, second))
        self.assertEqual(
            family.added_quantity_labels,
            ("beta",),
        )

    def test_schema_extension_records_union_of_added_labels(self):
        base = self.make_record(
            section_label="Outcome",
            row_label="Reference",
            labels=["DIC"],
        )
        first = self.make_record(
            section_label="Outcome",
            row_label="First extension",
            labels=["DIC", "Beta"],
        )
        second = self.make_record(
            section_label="Outcome",
            row_label="Second extension",
            labels=["DIC", "SD"],
        )

        families = schema_extension_families(
            [base, first, second]
        )

        base_families = [
            family
            for family in families
            if family.base_record == base
        ]

        self.assertEqual(len(base_families), 1)
        self.assertEqual(
            base_families[0].added_quantity_labels,
            ("beta", "sd"),
        )

    def test_schema_extension_requires_same_section(self):
        base = self.make_record(
            section_label="Outcome A",
            row_label="Reference",
            labels=["DIC"],
        )
        extended = self.make_record(
            section_label="Outcome B",
            row_label="Alternative",
            labels=["DIC", "Beta"],
        )

        self.assertEqual(
            schema_extension_families([base, extended]),
            [],
        )

    def test_schema_extension_requires_proper_subset(self):
        first = self.make_record(
            section_label="Outcome",
            row_label="First",
            labels=["DIC", "pD"],
        )
        second = self.make_record(
            section_label="Outcome",
            row_label="Second",
            labels=["DIC", "pD"],
        )

        self.assertEqual(
            schema_extension_families([first, second]),
            [],
        )

    def test_parallel_schema_does_not_cross_source_files(self):
        primary = self.make_record(
            section_label="Outcome",
            row_label="First",
            labels=["DIC", "pD"],
            page=10,
            source_name="primary.pdf",
        )
        supplement = self.make_record(
            section_label="Outcome",
            row_label="Second",
            labels=["DIC", "pD"],
            page=10,
            source_name="supplement.pdf",
        )

        self.assertEqual(
            parallel_schema_families([primary, supplement]),
            [],
        )

    def test_parallel_schema_does_not_cross_known_tables(self):
        first = self.make_record(
            section_label="Outcome",
            row_label="First",
            labels=["DIC", "pD"],
            page=10,
            table_id="table-a",
        )
        second = self.make_record(
            section_label="Outcome",
            row_label="Second",
            labels=["DIC", "pD"],
            page=10,
            table_id="table-b",
        )

        self.assertEqual(
            parallel_schema_families([first, second]),
            [],
        )

    def test_repeated_row_does_not_cross_source_files(self):
        primary = self.make_record(
            section_label="First section",
            row_label="Repeated",
            labels=["DIC"],
            page=10,
            source_name="primary.pdf",
        )
        supplement = self.make_record(
            section_label="Second section",
            row_label="Repeated",
            labels=["DIC"],
            page=10,
            source_name="supplement.pdf",
        )

        self.assertEqual(
            repeated_row_families([primary, supplement]),
            [],
        )

    def test_schema_extension_does_not_cross_source_files(self):
        primary = self.make_record(
            section_label="Outcome",
            row_label="Base",
            labels=["DIC"],
            page=10,
            source_name="primary.pdf",
        )
        supplement = self.make_record(
            section_label="Outcome",
            row_label="Extended",
            labels=["DIC", "beta"],
            page=10,
            source_name="supplement.pdf",
        )

        self.assertEqual(
            schema_extension_families([primary, supplement]),
            [],
        )

    def test_schema_extension_does_not_cross_known_tables(self):
        first = self.make_record(
            section_label="Outcome",
            row_label="Base",
            labels=["DIC"],
            page=10,
            table_id="table-a",
        )
        second = self.make_record(
            section_label="Outcome",
            row_label="Extended",
            labels=["DIC", "beta"],
            page=10,
            table_id="table-b",
        )

        self.assertEqual(
            schema_extension_families([first, second]),
            [],
        )

    def test_unresolved_table_identity_can_group_within_same_source_page(self):
        first = self.make_record(
            section_label="Outcome",
            row_label="First",
            labels=["DIC", "pD"],
            page=10,
            table_id=None,
        )
        second = self.make_record(
            section_label="Outcome",
            row_label="Second",
            labels=["DIC", "pD"],
            page=10,
            table_id=None,
        )

        # Remove the helper's default known table identity so this exercises
        # genuinely unresolved page-level visual evidence.
        from dataclasses import replace

        first = replace(
            first,
            table_evidence_id=None,
            quantities=tuple(
                replace(q, table_evidence_id=None)
                for q in first.quantities
            ),
        )
        second = replace(
            second,
            table_evidence_id=None,
            quantities=tuple(
                replace(q, table_evidence_id=None)
                for q in second.quantities
            ),
        )

        families = parallel_schema_families([first, second])

        self.assertEqual(len(families), 1)
        self.assertEqual(families[0].members, (first, second))

    def test_record_relationship_evidence_preserves_structural_facts(self):
        left = self.make_record(
            section_label="Cognitive flexibility",
            row_label="Unadjusted",
            labels=["DIC", "pD", "Residual Deviance", "SD"],
            page=66,
            table_id="table-s9",
        )
        right = self.make_record(
            section_label="Cognitive flexibility",
            row_label="Age",
            labels=[
                "DIC",
                "pD",
                "Residual Deviance",
                "Shared beta",
                "SD",
            ],
            page=66,
            table_id="table-s9",
        )

        evidence = record_relationship_evidence(left, right)

        self.assertTrue(evidence.same_source)
        self.assertTrue(evidence.same_page)
        self.assertTrue(evidence.same_known_table)
        self.assertTrue(evidence.same_section_label)
        self.assertFalse(evidence.same_row_label)
        self.assertEqual(
            evidence.shared_quantity_labels,
            ("dic", "pd", "residual deviance", "sd"),
        )
        self.assertEqual(evidence.left_only_quantity_labels, ())
        self.assertEqual(
            evidence.right_only_quantity_labels,
            ("shared beta",),
        )

    def test_record_relationship_unknown_pages_do_not_establish_same_page(self):
        from dataclasses import replace

        left = self.make_record(
            section_label="Outcome",
            row_label="First",
            labels=["DIC"],
            page=10,
        )
        right = self.make_record(
            section_label="Outcome",
            row_label="Second",
            labels=["DIC"],
            page=10,
        )

        left = replace(
            left,
            page=None,
            quantities=tuple(
                replace(quantity, page=None)
                for quantity in left.quantities
            ),
        )
        right = replace(
            right,
            page=None,
            quantities=tuple(
                replace(quantity, page=None)
                for quantity in right.quantities
            ),
        )

        evidence = record_relationship_evidence(left, right)

        self.assertTrue(evidence.same_source)
        self.assertFalse(evidence.same_page)

    def test_record_relationship_does_not_promote_page_to_table_identity(self):
        from dataclasses import replace

        left = self.make_record(
            section_label="Outcome",
            row_label="First",
            labels=["DIC"],
            page=10,
            table_id=None,
        )
        right = self.make_record(
            section_label="Outcome",
            row_label="Second",
            labels=["DIC"],
            page=10,
            table_id=None,
        )

        left = replace(
            left,
            table_evidence_id=None,
            quantities=tuple(
                replace(quantity, table_evidence_id=None)
                for quantity in left.quantities
            ),
        )
        right = replace(
            right,
            table_evidence_id=None,
            quantities=tuple(
                replace(quantity, table_evidence_id=None)
                for quantity in right.quantities
            ),
        )

        evidence = record_relationship_evidence(left, right)

        self.assertTrue(evidence.same_source)
        self.assertTrue(evidence.same_page)
        self.assertFalse(evidence.same_known_table)

    def test_record_relationship_known_table_requires_same_source(self):
        left = self.make_record(
            section_label="Outcome",
            row_label="First",
            labels=["DIC"],
            page=10,
            table_id="table-a",
            source_name="primary.pdf",
        )
        right = self.make_record(
            section_label="Outcome",
            row_label="Second",
            labels=["DIC"],
            page=10,
            table_id="table-a",
            source_name="supplement.pdf",
        )

        evidence = record_relationship_evidence(left, right)

        self.assertFalse(evidence.same_source)
        self.assertFalse(evidence.same_page)
        self.assertFalse(evidence.same_known_table)

    def test_record_relationship_layer_has_no_semantic_judgement_fields(self):
        fields = set(RecordRelationshipEvidence.__dataclass_fields__)

        forbidden = {
            "analysis",
            "model",
            "outcome",
            "dataset",
            "baseline",
            "moderator",
            "sensitivity",
            "comparable",
            "better_fit",
            "methodologically_valid",
            "confidence",
            "relationship_class",
        }

        self.assertTrue(forbidden.isdisjoint(fields))

    def test_family_layer_has_no_semantic_judgement_fields(self):
        fields = set(TableRecordFamily.__dataclass_fields__)

        forbidden = {
            "analysis",
            "model",
            "baseline",
            "moderator",
            "sensitivity",
            "outcome",
            "comparable",
            "better_fit",
            "methodologically_valid",
        }

        self.assertTrue(forbidden.isdisjoint(fields))


class RowLabelHeaderEvidenceTests(unittest.TestCase):

    def make_structured(self, *, row_label, cells):
        from app.table_evidence import (
            AcquisitionMethod,
            AcquisitionState,
            StructuredTableCell,
            StructuredTableColumn,
            StructuredTableObservation,
            StructuredTableRow,
            StructuredTableSection,
            TableObservation,
        )

        observation = TableObservation(
            acquisition_method=AcquisitionMethod.VISION,
            content="{}",
            page=66,
            extraction_source="vision",
            acquisition_state=AcquisitionState.VISION_TRANSCRIBED,
        )

        return StructuredTableObservation(
            source_observation=observation,
            caption="Test table",
            columns=(
                StructuredTableColumn(index=0, header="Covariate Analysis"),
                StructuredTableColumn(index=1, header="DIC"),
                StructuredTableColumn(index=2, header="Other"),
            ),
            sections=(
                StructuredTableSection(
                    label="Cognitive flexibility",
                    rows=(
                        StructuredTableRow(
                            label=row_label,
                            cells=tuple(
                                StructuredTableCell(
                                    column_index=index,
                                    value=value,
                                )
                                for index, value in cells
                            ),
                        ),
                    ),
                ),
            ),
        )

    def test_unique_exact_row_label_cell_preserves_header(self):
        from app.table_evidence import (
            cell_evidence_from_structured_observation,
        )

        structured = self.make_structured(
            row_label="Age",
            cells=((0, "Age"), (1, "245.273"), (2, "other")),
        )

        cells = cell_evidence_from_structured_observation(
            "paper.pdf",
            structured,
            table_evidence_id="table-s9",
        )

        self.assertTrue(cells)
        self.assertTrue(
            all(
                cell.row_label_header == "Covariate Analysis"
                for cell in cells
            )
        )

    def test_no_matching_row_label_cell_leaves_header_unresolved(self):
        from app.table_evidence import (
            cell_evidence_from_structured_observation,
        )

        structured = self.make_structured(
            row_label="Age",
            cells=((0, "Adjusted"), (1, "245.273")),
        )

        cells = cell_evidence_from_structured_observation(
            "paper.pdf",
            structured,
        )

        self.assertTrue(cells)
        self.assertTrue(
            all(cell.row_label_header is None for cell in cells)
        )

    def test_multiple_matching_row_label_cells_leave_header_unresolved(self):
        from app.table_evidence import (
            cell_evidence_from_structured_observation,
        )

        structured = self.make_structured(
            row_label="Age",
            cells=((0, "Age"), (1, "245.273"), (2, "Age")),
        )

        cells = cell_evidence_from_structured_observation(
            "paper.pdf",
            structured,
        )

        self.assertTrue(cells)
        self.assertTrue(
            all(cell.row_label_header is None for cell in cells)
        )
