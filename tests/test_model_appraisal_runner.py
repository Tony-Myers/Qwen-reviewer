import json
import unittest
from unittest.mock import Mock, patch

from app.model_appraisal import (
    ModelAppraisalEvidenceItem,
    ModelAppraisalResult,
    ModelAppraisalTarget,
    ModelAppraisalVerdict,
    build_model_appraisal_evidence_package,
)
from app.model_appraisal_runner import (
    ModelAppraisalConfiguration,
    ModelAppraisalExperimentalRecord,
    ModelAppraisalInvocationInput,
    build_model_appraisal_invocation,
    build_model_appraisal_user_prompt,
    run_model_appraisal,
)


class ModelAppraisalRunnerRecordTests(unittest.TestCase):

    def setUp(self):
        self.target = ModelAppraisalTarget(
            target_id="target-1",
            proposition="The proposition is established.",
            evidence_package_id="package-1",
            package_snapshot_id="snapshot-1",
            permitted_evidence_ids=("evidence-1",),
        )

        self.configuration = ModelAppraisalConfiguration(
            thinking=True,
            reasoning_effort="medium",
            temperature=1.0,
            top_p=0.95,
            top_k=20,
            presence_penalty=0.0,
            answer_max_tokens=900,
            thinking_token_allowance=8000,
        )

        self.result = ModelAppraisalResult(
            target_id="target-1",
            evidence_package_id="package-1",
            package_snapshot_id="snapshot-1",
            model_verdict=ModelAppraisalVerdict.SUPPORTED,
            relied_on_evidence_ids=("evidence-1",),
            bounded_rationale="The supplied evidence supports the proposition.",
            model_unresolved_premises=(),
        )

    def record(self, **changes):
        values = {
            "invocation": ModelAppraisalInvocationInput(
                target=self.target,
                evidence_text="evidence-1: reported value = 10.",
            ),
            "configuration": self.configuration,
            "requested_model": "requested.gguf",
            "served_model": "served.gguf",
            "raw_response": '{"model_verdict":"SUPPORTED"}',
            "result": self.result,
            "validation_error": None,
            "execution_error": None,
            "elapsed_seconds": 1.25,
            "reasoning_stats": {
                "generations": 1,
                "with_reasoning": 1,
                "chars": 500,
                "template_kwargs_dropped": False,
                "retries": 0,
                "fallbacks": 0,
            },
            "diagnostic_reasoning": "Bounded diagnostic reasoning.",
        }
        values.update(changes)
        return ModelAppraisalExperimentalRecord(**values)


    def test_invocation_preserves_exact_evidence_text(self):
        evidence = "evidence-1: exact text\\nsecond line"
        invocation = ModelAppraisalInvocationInput(
            target=self.target,
            evidence_text=evidence,
        )
        self.assertEqual(invocation.evidence_text, evidence)

    def test_user_prompt_binds_target_package_and_evidence(self):
        invocation = ModelAppraisalInvocationInput(
            target=self.target,
            evidence_text="evidence-1: reported value = 10.",
        )
        prompt = build_model_appraisal_user_prompt(invocation)
        self.assertIn("Target ID: target-1", prompt)
        self.assertIn("Evidence package ID: package-1", prompt)
        self.assertIn("Package snapshot ID: snapshot-1", prompt)
        self.assertIn("Proposition: The proposition is established.", prompt)
        self.assertIn("evidence-1", prompt)
        self.assertIn("evidence-1: reported value = 10.", prompt)

    def test_valid_result_record(self):
        record = self.record()
        self.assertIs(record.result, self.result)
        self.assertIsNone(record.validation_error)
        self.assertIsNone(record.execution_error)

    def test_validation_failure_preserves_raw_response(self):
        record = self.record(
            raw_response="```json\n{}\n```",
            result=None,
            validation_error="Model appraisal response is not valid JSON.",
        )
        self.assertIsNone(record.result)
        self.assertIn("```json", record.raw_response)

    def test_execution_failure_is_distinct(self):
        record = self.record(
            raw_response="",
            result=None,
            execution_error="BackendError: backend unavailable",
        )
        self.assertIsNone(record.result)
        self.assertIsNone(record.validation_error)

    def test_no_outcome_is_rejected(self):
        with self.assertRaises(ValueError):
            self.record(
                result=None,
                validation_error=None,
                execution_error=None,
            )

    def test_multiple_outcomes_are_rejected(self):
        with self.assertRaises(ValueError):
            self.record(
                validation_error="invalid",
                execution_error="failed",
            )

    def test_validation_failure_requires_raw_response(self):
        with self.assertRaises(ValueError):
            self.record(
                raw_response="",
                result=None,
                validation_error="invalid",
            )

    def test_negative_elapsed_time_is_rejected(self):
        with self.assertRaises(ValueError):
            self.record(elapsed_seconds=-0.1)



class ModelAppraisalInvocationTests(unittest.TestCase):

    def setUp(self):
        self.package = build_model_appraisal_evidence_package(
            "package-run",
            (
                ModelAppraisalEvidenceItem(
                    "evidence-a",
                    "Model A = 10.",
                ),
                ModelAppraisalEvidenceItem(
                    "evidence-b",
                    "Model B = 12.",
                ),
            ),
        )
        self.target = ModelAppraisalTarget(
            target_id="target-run",
            proposition="The reported value is lower.",
            evidence_package_id=self.package.evidence_package_id,
            package_snapshot_id=self.package.package_snapshot_id,
            permitted_evidence_ids=("evidence-a", "evidence-b"),
        )
        self.tokenizer = Mock()
        self.tokenizer.apply_chat_template.return_value = "PROMPT"

    def valid_response(self):
        return json.dumps({
            "target_id": "target-run",
            "evidence_package_id": "package-run",
            "package_snapshot_id": self.package.package_snapshot_id,
            "model_verdict": "SUPPORTED",
            "relied_on_evidence_ids": ["evidence-a", "evidence-b"],
            "bounded_rationale": "The reported value for Model A is lower.",
            "model_unresolved_premises": [],
        })

    def patches(self, generated):
        if isinstance(generated, BaseException):
            generate_patch = patch(
                "app.llm_backend.generate",
                side_effect=generated,
            )
        else:
            generate_patch = patch(
                "app.llm_backend.generate",
                return_value=generated,
            )

        return (
            patch("app.llm_backend.reasoning_effort", return_value="medium"),
            patch(
                "app.llm_backend.thinking_token_allowance",
                return_value=8000,
            ),
            generate_patch,
            patch(
                "app.llm_backend.reasoning_stats",
                return_value={
                    "generations": 1,
                    "with_reasoning": 1,
                    "chars": 123,
                    "template_kwargs_dropped": False,
                    "retries": 0,
                    "fallbacks": 0,
                },
            ),
            patch(
                "app.llm_backend.last_reasoning",
                return_value="diagnostic reasoning",
            ),
            patch(
                "app.llm_backend.served_model_name",
                return_value="served-flash.gguf",
            ),
        )

    def test_success_uses_validated_medium_thinking_configuration(self):
        patches = self.patches(self.valid_response())

        with (
            patches[0],
            patches[1],
            patches[2] as generate,
            patches[3],
            patches[4],
            patches[5],
            patch("app.llm_backend.make_sampler") as make_sampler,
        ):
            sampler = object()
            make_sampler.return_value = sampler

            record = run_model_appraisal(
                object(),
                self.tokenizer,
                self.package,
                self.target,
                requested_model="requested-flash.gguf",
            )

        self.assertEqual(
            record.result.model_verdict,
            ModelAppraisalVerdict.SUPPORTED,
        )
        self.assertIsNone(record.validation_error)
        self.assertIsNone(record.execution_error)
        self.assertEqual(record.served_model, "served-flash.gguf")

        config = record.configuration
        self.assertTrue(config.thinking)
        self.assertEqual(config.reasoning_effort, "medium")
        self.assertEqual(config.temperature, 1.0)
        self.assertEqual(config.top_p, 0.95)
        self.assertEqual(config.top_k, 20)
        self.assertEqual(config.presence_penalty, 0.0)
        self.assertEqual(config.answer_max_tokens, 900)
        self.assertEqual(config.thinking_token_allowance, 8000)

        make_sampler.assert_called_once_with(
            1.0,
            top_p=0.95,
            top_k=20,
            presence_penalty=0.0,
        )

        kwargs = generate.call_args.kwargs
        self.assertEqual(kwargs["max_tokens"], 8900)
        self.assertIs(kwargs["sampler"], sampler)
        self.assertFalse(kwargs["recover_truncation"])

        template_kwargs = self.tokenizer.apply_chat_template.call_args.kwargs
        self.assertTrue(template_kwargs["enable_thinking"])

    def test_invalid_json_is_validation_failure_not_not_established(self):
        patches = self.patches("```json\n{}\n```")

        with (
            patches[0],
            patches[1],
            patches[2],
            patches[3],
            patches[4],
            patches[5],
            patch("app.llm_backend.make_sampler"),
        ):
            record = run_model_appraisal(
                object(),
                self.tokenizer,
                self.package,
                self.target,
                requested_model="requested-flash.gguf",
            )

        self.assertIsNone(record.result)
        self.assertIsNotNone(record.validation_error)
        self.assertIsNone(record.execution_error)
        self.assertEqual(record.raw_response, "```json\n{}\n```")

    def test_backend_failure_is_execution_failure(self):
        from app.llm_backend import BackendError

        patches = self.patches(BackendError("backend unavailable"))

        with (
            patches[0],
            patches[1],
            patches[2],
            patches[3],
            patches[4],
            patches[5],
            patch("app.llm_backend.make_sampler"),
        ):
            record = run_model_appraisal(
                object(),
                self.tokenizer,
                self.package,
                self.target,
                requested_model="requested-flash.gguf",
            )

        self.assertIsNone(record.result)
        self.assertIsNone(record.validation_error)
        self.assertIn("BackendError", record.execution_error)

    def test_cancellation_propagates(self):
        from app.llm_backend import InferenceCancelledError

        patches = self.patches(InferenceCancelledError("cancelled"))

        with (
            patches[0],
            patches[1],
            patches[2],
            patches[3],
            patches[4],
            patches[5],
            patch("app.llm_backend.make_sampler"),
        ):
            with self.assertRaises(InferenceCancelledError):
                run_model_appraisal(
                    object(),
                    self.tokenizer,
                    self.package,
                    self.target,
                    requested_model="requested-flash.gguf",
                )

    def test_non_medium_reasoning_effort_fails_before_generation(self):
        with (
            patch("app.llm_backend.reasoning_effort", return_value="high"),
            patch("app.llm_backend.generate") as generate,
        ):
            with self.assertRaises(RuntimeError):
                run_model_appraisal(
                    object(),
                    self.tokenizer,
                    self.package,
                    self.target,
                    requested_model="requested-flash.gguf",
                )

        generate.assert_not_called()


class ReasoningIsolationTests(unittest.TestCase):

    def test_isolated_reasoning_stats_restore_enclosing_state(self):
        from app import llm_backend

        llm_backend.reset_reasoning_stats()
        llm_backend._note_reasoning_chars(17, "outer reasoning")
        before = llm_backend.reasoning_stats().copy()
        before_reasoning = llm_backend.last_reasoning()

        with llm_backend.isolated_reasoning_stats():
            self.assertEqual(llm_backend.reasoning_stats()["chars"], 0)
            self.assertEqual(llm_backend.last_reasoning(), "")
            llm_backend._note_reasoning_chars(9, "inner reasoning")
            self.assertEqual(llm_backend.reasoning_stats()["chars"], 9)
            self.assertEqual(llm_backend.last_reasoning(), "inner reasoning")

        self.assertEqual(llm_backend.reasoning_stats(), before)
        self.assertEqual(llm_backend.last_reasoning(), before_reasoning)

    def test_isolated_reasoning_stats_restore_after_exception(self):
        from app import llm_backend

        llm_backend.reset_reasoning_stats()
        llm_backend._note_reasoning_chars(13, "outer reasoning")
        before = llm_backend.reasoning_stats().copy()
        before_reasoning = llm_backend.last_reasoning()

        with self.assertRaises(RuntimeError):
            with llm_backend.isolated_reasoning_stats():
                llm_backend._note_reasoning_chars(5, "inner reasoning")
                raise RuntimeError("test failure")

        self.assertEqual(llm_backend.reasoning_stats(), before)
        self.assertEqual(llm_backend.last_reasoning(), before_reasoning)


class ModelAppraisalPackageBindingTests(unittest.TestCase):

    def setUp(self):
        self.package = build_model_appraisal_evidence_package(
            "package-binding",
            (
                ModelAppraisalEvidenceItem(
                    "evidence-a",
                    "Evidence A exact text.",
                ),
                ModelAppraisalEvidenceItem(
                    "evidence-b",
                    "Evidence B exact text.",
                ),
                ModelAppraisalEvidenceItem(
                    "evidence-c",
                    "Evidence C must remain hidden.",
                ),
                ModelAppraisalEvidenceItem(
                    "evidence-d",
                    "Evidence D exact text.",
                ),
            ),
        )

    def target(self, **changes):
        values = {
            "target_id": "target-binding",
            "proposition": "The bounded proposition.",
            "evidence_package_id": self.package.evidence_package_id,
            "package_snapshot_id": self.package.package_snapshot_id,
            "permitted_evidence_ids": ("evidence-b", "evidence-d"),
        }
        values.update(changes)
        return ModelAppraisalTarget(**values)

    def test_only_permitted_evidence_is_model_visible(self):
        invocation = build_model_appraisal_invocation(
            self.package,
            self.target(),
        )

        self.assertIn(
            "[EVIDENCE ID: evidence-b]\nEvidence B exact text.",
            invocation.evidence_text,
        )
        self.assertIn(
            "[EVIDENCE ID: evidence-d]\nEvidence D exact text.",
            invocation.evidence_text,
        )
        self.assertNotIn("evidence-a", invocation.evidence_text)
        self.assertNotIn("Evidence A exact text.", invocation.evidence_text)
        self.assertNotIn("evidence-c", invocation.evidence_text)
        self.assertNotIn(
            "Evidence C must remain hidden.",
            invocation.evidence_text,
        )

    def test_visible_evidence_preserves_package_order(self):
        target = self.target(
            permitted_evidence_ids=("evidence-d", "evidence-b"),
        )
        invocation = build_model_appraisal_invocation(
            self.package,
            target,
        )

        self.assertLess(
            invocation.evidence_text.index("evidence-b"),
            invocation.evidence_text.index("evidence-d"),
        )

    def test_reference_closed_permitted_subset_is_accepted(self):
        package = build_model_appraisal_evidence_package(
            "package-reference-closure",
            (
                ModelAppraisalEvidenceItem(
                    "evidence-a",
                    "Evidence A.",
                ),
                ModelAppraisalEvidenceItem(
                    "evidence-b",
                    "Evidence B.",
                ),
                ModelAppraisalEvidenceItem(
                    evidence_id="evidence-derived",
                    text="Derived evidence depending on A and B.",
                    referenced_evidence_ids=("evidence-a", "evidence-b"),
                ),
            ),
        )
        target = ModelAppraisalTarget(
            target_id="target-reference-closure",
            proposition="The bounded proposition.",
            evidence_package_id=package.evidence_package_id,
            package_snapshot_id=package.package_snapshot_id,
            permitted_evidence_ids=(
                "evidence-derived",
                "evidence-b",
                "evidence-a",
            ),
        )

        invocation = build_model_appraisal_invocation(
            package,
            target,
        )

        self.assertLess(
            invocation.evidence_text.index("evidence-a"),
            invocation.evidence_text.index("evidence-b"),
        )
        self.assertLess(
            invocation.evidence_text.index("evidence-b"),
            invocation.evidence_text.index("evidence-derived"),
        )

    def test_permitted_evidence_subset_must_be_reference_closed(self):
        package = build_model_appraisal_evidence_package(
            "package-reference-closure",
            (
                ModelAppraisalEvidenceItem(
                    "evidence-a",
                    "Evidence A.",
                ),
                ModelAppraisalEvidenceItem(
                    "evidence-b",
                    "Evidence B.",
                ),
                ModelAppraisalEvidenceItem(
                    evidence_id="evidence-derived",
                    text="Derived evidence depending on A and B.",
                    referenced_evidence_ids=("evidence-a", "evidence-b"),
                ),
            ),
        )
        target = ModelAppraisalTarget(
            target_id="target-reference-closure",
            proposition="The bounded proposition.",
            evidence_package_id=package.evidence_package_id,
            package_snapshot_id=package.package_snapshot_id,
            permitted_evidence_ids=(
                "evidence-a",
                "evidence-derived",
            ),
        )

        with self.assertRaises(ValueError):
            build_model_appraisal_invocation(
                package,
                target,
            )

    def test_package_id_mismatch_is_rejected(self):
        target = self.target(
            evidence_package_id="different-package",
        )
        with self.assertRaises(ValueError):
            build_model_appraisal_invocation(
                self.package,
                target,
            )

    def test_stale_snapshot_is_rejected(self):
        target = self.target(
            package_snapshot_id="sha256:stale",
        )
        with self.assertRaises(ValueError):
            build_model_appraisal_invocation(
                self.package,
                target,
            )

    def test_missing_permitted_evidence_is_rejected(self):
        target = self.target(
            permitted_evidence_ids=("evidence-b", "evidence-missing"),
        )
        with self.assertRaises(ValueError):
            build_model_appraisal_invocation(
                self.package,
                target,
            )

    def test_empty_permitted_subset_cannot_be_invoked(self):
        target = self.target(
            permitted_evidence_ids=(),
        )
        with self.assertRaises(ValueError):
            build_model_appraisal_invocation(
                self.package,
                target,
            )

if __name__ == "__main__":
    unittest.main()
