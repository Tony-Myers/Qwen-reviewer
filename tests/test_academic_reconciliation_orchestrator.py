from dataclasses import dataclass
import inspect

import academic_chat
import academic_claim_coverage
import academic_methodology
import academic_orchestrator
import academic_reconciliation
import academic_technical
import reviewer_notes

try:
    import academic_reconciliation_orchestrator as reconciliation_orchestrator
except ImportError:
    reconciliation_orchestrator = None


fails = []


def check(condition, label, detail=None):
    if condition:
        print(f"PASS: {label}")
    else:
        print(f"FAIL: {label}")
        if detail is not None:
            print(f"      {detail}")
        fails.append(label)


print("\n[academic reconciliation lifecycle contract]")

check(
    reconciliation_orchestrator is not None,
    "reconciliation lifecycle module exists",
)

run_lifecycle = (
    getattr(
        reconciliation_orchestrator,
        "run_academic_reconciliation",
        None,
    )
    if reconciliation_orchestrator is not None
    else None
)

check(
    callable(run_lifecycle),
    "academic reconciliation coordinator exists",
)

if callable(run_lifecycle):
    params = list(inspect.signature(run_lifecycle).parameters)

    check(
        params == [
            "model",
            "tokenizer",
            "question",
            "first_stage_runner",
            "correction_extractor",
            "revision_generator",
            "draft_assessor",
        ],
        "coordinator exposes generation, checking, and revision dependencies",
        params,
    )

    check(
        "max_revisions" not in params,
        "caller cannot request repeated reconciliation",
        params,
    )


print("\n[academic reconciliation lifecycle behaviour]")

if callable(run_lifecycle):

    @dataclass
    class FakeRelease:
        safe_to_present: bool
        status: str

    @dataclass
    class FakeStage:
        answer_draft: str
        release: FakeRelease
        draft: object = None
        local_guidance: object = None
        technical_claims: object = None
        source_claims: object = None
        discovered_claim_assessments: object = None

    @dataclass
    class FakeCorrections:
        empty: bool

        def is_empty(self):
            return self.empty

    model = object()
    tokenizer = object()
    question = "CONFIDENTIAL ORIGINAL QUESTION"

    # ---------------------------------------------------------------
    # 1. Safe first attempt: no reconciliation machinery is invoked.
    # ---------------------------------------------------------------
    calls = []

    safe_initial = FakeStage(
        answer_draft="Safe initial answer.",
        release=FakeRelease(True, "release_allowed"),
    )

    def safe_first_stage(*args, **kwargs):
        calls.append(("first_stage", args, kwargs))
        return safe_initial

    def must_not_extract(*args, **kwargs):
        raise AssertionError("Safe result must not extract corrections.")

    def must_not_revise(*args, **kwargs):
        raise AssertionError("Safe result must not invoke revision.")

    def must_not_assess(*args, **kwargs):
        raise AssertionError("Safe result must not invoke reassessment.")

    safe_result = run_lifecycle(
        model,
        tokenizer,
        question,
        first_stage_runner=safe_first_stage,
        correction_extractor=must_not_extract,
        revision_generator=must_not_revise,
        draft_assessor=must_not_assess,
    )

    check(
        safe_result.initial is safe_initial,
        "safe initial assessment is retained",
    )
    check(
        safe_result.revised is None,
        "safe initial result creates no revised assessment",
    )
    check(
        safe_result.revision_attempted is False,
        "safe initial result records no revision attempt",
    )
    check(
        safe_result.final is safe_initial,
        "safe initial assessment is final",
    )

    # ---------------------------------------------------------------
    # 2. Blocked result with no bounded corrections: fail closed.
    # ---------------------------------------------------------------
    original_draft = object()
    original_guidance = object()
    checked_technical_claims = object()
    checked_source_claims = object()
    checked_discovered_claim_assessments = object()

    blocked_initial = FakeStage(
        answer_draft="Blocked initial answer.",
        release=FakeRelease(False, "blocked_synthetic"),
        draft=original_draft,
        local_guidance=original_guidance,
        technical_claims=checked_technical_claims,
        source_claims=checked_source_claims,
        discovered_claim_assessments=(
            checked_discovered_claim_assessments
        ),
    )

    empty_corrections = FakeCorrections(empty=True)
    empty_calls = []

    def blocked_first_stage(*args, **kwargs):
        empty_calls.append(("first_stage", args, kwargs))
        return blocked_initial

    def extract_empty(
        *,
        technical_claims,
        source_claims,
        discovered_claim_assessments,
    ):
        empty_calls.append(
            (
                "extract",
                technical_claims,
                source_claims,
                discovered_claim_assessments,
            )
        )
        return empty_corrections

    def no_empty_revision(*args, **kwargs):
        raise AssertionError(
            "Empty correction set must not trigger model revision."
        )

    def no_empty_assessment(*args, **kwargs):
        raise AssertionError(
            "No revised draft exists to reassess."
        )

    empty_result = run_lifecycle(
        model,
        tokenizer,
        question,
        first_stage_runner=blocked_first_stage,
        correction_extractor=extract_empty,
        revision_generator=no_empty_revision,
        draft_assessor=no_empty_assessment,
    )

    check(
        empty_result.initial is blocked_initial,
        "blocked initial assessment is retained when corrections are empty",
    )
    check(
        empty_result.revised is None,
        "empty correction set creates no revised assessment",
    )
    check(
        empty_result.revision_attempted is False,
        "empty correction set does not count as a revision attempt",
    )
    check(
        empty_result.final is blocked_initial,
        "blocked initial assessment remains final when no correction exists",
    )

    # ---------------------------------------------------------------
    # 3. Blocked result with corrections: revise exactly once and
    #    independently reassess the new draft.
    # ---------------------------------------------------------------
    bounded_corrections = FakeCorrections(empty=False)
    revised_draft = object()
    revised_stage = FakeStage(
        answer_draft="Corrected answer.",
        release=FakeRelease(True, "release_allowed"),
    )

    lifecycle_calls = []

    def conflict_first_stage(*args, **kwargs):
        lifecycle_calls.append(("first_stage", args, kwargs))
        return blocked_initial

    def extract_bounded(
        *,
        technical_claims,
        source_claims,
        discovered_claim_assessments,
    ):
        lifecycle_calls.append(
            (
                "extract",
                technical_claims,
                source_claims,
                discovered_claim_assessments,
            )
        )
        return bounded_corrections

    def revise_once(
        supplied_model,
        supplied_tokenizer,
        original_draft,
        corrections,
    ):
        lifecycle_calls.append(
            (
                "revise",
                supplied_model,
                supplied_tokenizer,
                original_draft,
                corrections,
            )
        )
        return revised_draft

    def reassess_once(draft, **kwargs):
        lifecycle_calls.append(("assess", draft, kwargs))
        return revised_stage

    revised_result = run_lifecycle(
        model,
        tokenizer,
        question,
        first_stage_runner=conflict_first_stage,
        correction_extractor=extract_bounded,
        revision_generator=revise_once,
        draft_assessor=reassess_once,
    )

    revise_calls = [
        call for call in lifecycle_calls
        if call[0] == "revise"
    ]
    assess_calls = [
        call for call in lifecycle_calls
        if call[0] == "assess"
    ]

    check(
        len(revise_calls) == 1,
        "blocked draft is revised exactly once",
        lifecycle_calls,
    )
    check(
        len(assess_calls) == 1,
        "revised draft is independently reassessed exactly once",
        lifecycle_calls,
    )
    check(
        assess_calls
        and assess_calls[0][1] is revised_draft,
        "reassessment receives the newly generated draft",
        lifecycle_calls,
    )
    check(
        revise_calls
        and revise_calls[0][3] is original_draft,
        "revision receives the exact retained original AcademicDraft",
        lifecycle_calls,
    )
    check(
        lifecycle_calls
        and any(
            call[0] == "extract"
            and call[1] is checked_technical_claims
            and call[2] is checked_source_claims
            and call[3] is checked_discovered_claim_assessments
            for call in lifecycle_calls
        ),
        (
            "correction extraction receives proposition-level and "
            "occurrence-level checked structures"
        ),
        lifecycle_calls,
    )
    check(
        assess_calls
        and assess_calls[0][2].get("local_guidance") is original_guidance,
        "reassessment reuses the exact retained local guidance",
        lifecycle_calls,
    )
    check(
        revised_result.initial is blocked_initial,
        "original blocked assessment remains in audit result",
    )
    check(
        revised_result.revised is revised_stage,
        "fresh revised assessment is retained separately",
    )
    check(
        revised_result.revision_attempted is True,
        "successful revision generation records one attempt",
    )
    check(
        revised_result.final is revised_stage,
        "reassessed revision becomes final result",
    )

    # ---------------------------------------------------------------
    # 4. A still-blocked revision is final; no third attempt exists.
    # ---------------------------------------------------------------
    still_blocked = FakeStage(
        answer_draft="Still blocked.",
        release=FakeRelease(False, "blocked_again"),
    )
    repeated_calls = []

    def still_blocked_first_stage(*args, **kwargs):
        return blocked_initial

    def repeated_extract(
        *,
        technical_claims,
        source_claims,
        discovered_claim_assessments,
    ):
        repeated_calls.append(
            (
                "extract",
                technical_claims,
                source_claims,
                discovered_claim_assessments,
            )
        )
        return bounded_corrections

    def repeated_revision(*args, **kwargs):
        repeated_calls.append(("revise", args, kwargs))
        return revised_draft

    def blocked_reassessment(draft, **kwargs):
        repeated_calls.append(("assess", draft, kwargs))
        return still_blocked

    repeated_result = run_lifecycle(
        model,
        tokenizer,
        question,
        first_stage_runner=still_blocked_first_stage,
        correction_extractor=repeated_extract,
        revision_generator=repeated_revision,
        draft_assessor=blocked_reassessment,
    )

    check(
        len([c for c in repeated_calls if c[0] == "revise"]) == 1,
        "still-blocked revision does not trigger a second revision",
        repeated_calls,
    )
    check(
        len([c for c in repeated_calls if c[0] == "extract"]) == 1,
        "corrections are not recursively extracted from revised result",
        repeated_calls,
    )
    check(
        repeated_result.final is still_blocked,
        "still-blocked reassessment remains final and withheld",
    )



    # ---------------------------------------------------------------
    # 4b. Incomplete checking after revision cannot become release.
    # ---------------------------------------------------------------
    incomplete_reassessment = FakeStage(
        answer_draft="Revised answer with incomplete fresh checking.",
        release=FakeRelease(False, "checking_incomplete"),
    )
    incomplete_calls = []

    def incomplete_first_stage(*args, **kwargs):
        return blocked_initial

    def incomplete_extract(
        *,
        technical_claims,
        source_claims,
        discovered_claim_assessments,
    ):
        incomplete_calls.append(
            (
                "extract",
                technical_claims,
                source_claims,
                discovered_claim_assessments,
            )
        )
        return bounded_corrections

    def incomplete_revision(*args, **kwargs):
        incomplete_calls.append(("revise", args, kwargs))
        return revised_draft

    def incomplete_reassessor(draft, **kwargs):
        incomplete_calls.append(("assess", draft, kwargs))
        return incomplete_reassessment

    incomplete_result = run_lifecycle(
        model,
        tokenizer,
        question,
        first_stage_runner=incomplete_first_stage,
        correction_extractor=incomplete_extract,
        revision_generator=incomplete_revision,
        draft_assessor=incomplete_reassessor,
    )

    check(
        incomplete_result.initial is blocked_initial,
        "initial blocked assessment remains retained after incomplete reassessment",
    )
    check(
        incomplete_result.revision_attempted is True,
        "incomplete fresh checking still records the bounded revision attempt",
    )
    check(
        incomplete_result.revised is incomplete_reassessment,
        "incomplete fresh reassessment is retained separately",
    )
    check(
        incomplete_result.final is incomplete_reassessment,
        "latest reassessment remains final without reverting to stale evidence",
    )
    check(
        incomplete_result.final.release.status == "checking_incomplete",
        "failed fresh coverage cannot masquerade as successful resolution",
    )
    check(
        incomplete_result.final.release.safe_to_present is False,
        "incomplete post-revision checking remains non-releasable",
    )
    check(
        len([c for c in incomplete_calls if c[0] == "revise"]) == 1,
        "incomplete post-revision checking triggers no second revision",
        incomplete_calls,
    )
    check(
        len([c for c in incomplete_calls if c[0] == "assess"]) == 1,
        "revised draft receives exactly one fresh incomplete assessment",
        incomplete_calls,
    )


print("\n[real reassessment composition]")

if callable(run_lifecycle):
    confidential_question = (
        "CONFIDENTIAL ORIGINAL QUESTION: check the MI relative-efficiency "
        "formula."
    )

    mi_parameterisation = (
        "lambda is the fraction of missing information; "
        "M is the number of imputations"
    )

    wrong_claim = academic_chat.TechnicalClaim(
        type="formula",
        concept="multiple imputation relative efficiency",
        statement="RE = 1 + lambda/M",
        parameterisation=mi_parameterisation,
    )

    initial_draft = academic_chat.AcademicDraft(
        answer_draft=(
            "The relative efficiency is RE = 1 + lambda/M."
        ),
        references=[],
        source_claims=[],
        technical_claims=[wrong_claim],
    )

    retained_guidance = academic_orchestrator.LocalGuidanceResult(
        passages=[]
    )

    initial_checked = academic_orchestrator.assess_academic_draft(
        initial_draft,
        local_guidance=retained_guidance,
        technical_verifier=academic_technical.verify_technical_claim,
    )

    check(
        initial_checked.release.safe_to_present is False,
        "real deterministic conflict blocks the initial draft",
    )
    check(
        initial_checked.technical_claims[0].verification.status
        == academic_technical.TECHNICAL_STATUS_CONFLICT,
        "initial attempt retains the real deterministic conflict",
    )

    corrected_claim = academic_chat.TechnicalClaim(
        type="formula",
        concept="multiple imputation relative efficiency",
        statement="RE = 1 / (1 + lambda/M)",
        parameterisation=mi_parameterisation,
    )

    corrected_draft = academic_chat.AcademicDraft(
        answer_draft=(
            "The relative efficiency is RE = 1 / (1 + lambda/M)."
        ),
        references=[],
        source_claims=[],
        technical_claims=[corrected_claim],
    )

    composition_calls = []

    def composition_first_stage(
        supplied_model,
        supplied_tokenizer,
        supplied_question,
    ):
        composition_calls.append(
            (
                "first_stage",
                supplied_model,
                supplied_tokenizer,
                supplied_question,
            )
        )
        return initial_checked

    def composition_revision(
        supplied_model,
        supplied_tokenizer,
        supplied_draft,
        supplied_corrections,
    ):
        composition_calls.append(
            (
                "revision",
                supplied_model,
                supplied_tokenizer,
                supplied_draft,
                supplied_corrections,
            )
        )
        return corrected_draft

    reassessed_claims = []

    def composition_assessor(draft, *, local_guidance):
        composition_calls.append(
            ("reassessment", draft, local_guidance)
        )

        def recording_verifier(claim):
            reassessed_claims.append(claim)
            return academic_technical.verify_technical_claim(claim)

        return academic_orchestrator.assess_academic_draft(
            draft,
            local_guidance=local_guidance,
            technical_verifier=recording_verifier,
        )

    composition_result = run_lifecycle(
        model,
        tokenizer,
        confidential_question,
        first_stage_runner=composition_first_stage,
        correction_extractor=(
            academic_reconciliation.extract_academic_corrections
        ),
        revision_generator=composition_revision,
        draft_assessor=composition_assessor,
    )

    check(
        composition_result.revision_attempted is True,
        "real initial conflict triggers one bounded revision",
    )
    check(
        composition_result.initial is initial_checked,
        "real initial checked result remains separately auditable",
    )
    check(
        composition_result.revised is not None,
        "corrected AcademicDraft receives a fresh real assessment",
    )
    check(
        reassessed_claims == corrected_draft.technical_claims,
        "fresh assessment checks only the revised structured claim",
    )
    check(
        reassessed_claims
        and reassessed_claims[0] is corrected_claim,
        "attempt two does not reuse the initial conflicting claim",
    )
    check(
        composition_result.revised is not None
        and composition_result.revised.technical_claims[0].verification.status
        == academic_technical.TECHNICAL_STATUS_VERIFIED,
        "corrected claim earns a fresh deterministic verification",
    )
    check(
        composition_result.revised is not None
        and composition_result.revised.technical_claims[0]
        is not composition_result.initial.technical_claims[0],
        "attempt two creates a fresh TechnicalClaimResult",
    )
    check(
        composition_result.final.release.safe_to_present is True,
        "fresh reassessment independently permits corrected draft release",
    )
    check(
        composition_result.final.local_guidance is retained_guidance,
        "fresh reassessment reuses exact retained local guidance",
    )

    downstream_calls = [
        call
        for call in composition_calls
        if call[0] != "first_stage"
    ]

    check(
        all(
            confidential_question not in repr(call)
            for call in downstream_calls
        ),
        "original confidential question does not enter reconciliation",
    )
    check(
        len(
            [
                call
                for call in composition_calls
                if call[0] == "revision"
            ]
        ) == 1,
        "real composition performs exactly one revision",
    )
    check(
        len(
            [
                call
                for call in composition_calls
                if call[0] == "reassessment"
            ]
        ) == 1,
        "real composition performs exactly one fresh reassessment",
    )



print("\n[contextual conflict reconciliation composition]")

if callable(run_lifecycle):
    contextual_only_claim = academic_chat.TechnicalClaim(
        type="interpretation",
        concept="covariate adjustment",
        statement="Covariate adjustment improves precision.",
        parameterisation=None,
    )

    contextual_only_source = academic_claim_coverage.ClaimSourceContext(
        source_sentence="Covariate adjustment improves precision.",
        source_sentence_start=0,
        source_sentence_end=40,
        context_excerpt=(
            "Even when the baseline covariate does not predict the outcome, "
            "covariate adjustment improves precision."
        ),
        context_start=0,
        context_end=99,
    )

    contextual_only_discovered = academic_claim_coverage.DiscoveredClaim(
        claim=contextual_only_claim,
        source_anchor="Covariate adjustment improves precision.",
        source_start=0,
        source_end=40,
    )

    contextual_only_passage = reviewer_notes.Passage(
        note="RCT guidance",
        heading="Covariate adjustment",
        text=(
            "Adjustment can improve precision when a baseline covariate "
            "strongly predicts the outcome; when it does not predict the "
            "outcome, there is no precision gain."
        ),
        score=0.73,
    )

    contextual_only_methodology = (
        academic_methodology.ContextualMethodologicalConsistencyResult(
            status=academic_methodology.METHODOLOGICAL_STATUS_CONFLICT,
            claim=contextual_only_claim,
            source_context=contextual_only_source,
            passages=[contextual_only_passage],
            reasons=["Synthetic contextual conflict reason."],
        )
    )

    contextual_only_assessment = (
        academic_orchestrator.DiscoveredClaimAssessment(
            discovered_claim=contextual_only_discovered,
            source_context=contextual_only_source,
            material_restriction=(
                academic_claim_coverage.MaterialRestrictionAssessment(
                    material_restriction_omitted=True,
                )
            ),
            contextual_methodological_consistency=(
                contextual_only_methodology
            ),
        )
    )

    contextual_initial_draft = academic_chat.AcademicDraft(
        answer_draft=(
            "Even when the baseline covariate does not predict the outcome, "
            "covariate adjustment improves precision."
        ),
        references=[],
        source_claims=[],
        technical_claims=[],
    )

    contextual_retained_guidance = academic_orchestrator.LocalGuidanceResult(
        passages=[]
    )

    contextual_initial_checked = academic_orchestrator.assess_academic_draft(
        contextual_initial_draft,
        local_guidance=contextual_retained_guidance,
    )

    contextual_initial_checked.discovered_claim_assessments = [
        contextual_only_assessment
    ]
    contextual_initial_checked.release = (
        academic_orchestrator.assess_academic_release(
            contextual_initial_checked.technical_claims,
            contextual_initial_checked.source_claims,
            contextual_initial_checked.discovered_claim_assessments,
        )
    )

    check(
        contextual_initial_checked.release.status
        == academic_orchestrator.RELEASE_STATUS_METHODOLOGICAL_CONFLICT,
        "a contextual conflict alone is reported with its own release status",
    )
    check(
        contextual_initial_checked.release.safe_to_present is True,
        "a contextual conflict alone no longer withholds the initial draft",
    )

    def contextual_must_not_revise(*args, **kwargs):
        raise AssertionError(
            "A methodological conflict must not trigger a revision.")

    def contextual_must_not_reassess(*args, **kwargs):
        raise AssertionError(
            "A methodological conflict must not trigger a reassessment.")

    contextual_composition_result = run_lifecycle(
        model,
        tokenizer,
        "CONFIDENTIAL CONTEXTUAL QUESTION",
        first_stage_runner=lambda *args: contextual_initial_checked,
        correction_extractor=(
            academic_reconciliation.extract_academic_corrections
        ),
        revision_generator=contextual_must_not_revise,
        draft_assessor=contextual_must_not_reassess,
    )

    check(
        contextual_composition_result.revision_attempted is False
        and contextual_composition_result.revised is None,
        "a sole contextual conflict triggers no revision",
    )
    check(
        contextual_composition_result.final is contextual_initial_checked,
        "the original answer is the one presented",
    )
    check(
        academic_reconciliation.extract_academic_corrections(
            technical_claims=contextual_initial_checked.technical_claims,
            source_claims=contextual_initial_checked.source_claims,
            discovered_claim_assessments=(
                contextual_initial_checked.discovered_claim_assessments
            ),
        ).is_empty(),
        "the contextual conflict is not correction material",
    )


print("\n[reconciliation audit serialization]")


class SerializableStage:
    def __init__(self, label):
        self.label = label

    def to_dict(self):
        return {
            "answer_draft": f"{self.label} answer",
            "release": {
                "status": f"{self.label}_status",
                "safe_to_present": self.label == "revised",
            },
        }


serial_initial = SerializableStage("initial")
serial_revised = SerializableStage("revised")

serial_result = reconciliation_orchestrator.AcademicReconciliationResult(
    initial=serial_initial,
    revised=serial_revised,
    revision_attempted=True,
)

serialized = serial_result.to_dict()

check(
    serialized["answer_draft"] == "revised answer",
    "top-level serialization remains the final independently checked result",
)

check(
    serialized["release"]["status"] == "revised_status",
    "top-level release remains the fresh final release decision",
)

check(
    serialized["reconciliation"]["revision_attempted"] is True,
    "audit records that one bounded revision was attempted",
)

check(
    serialized["reconciliation"]["initial"]["answer_draft"]
    == "initial answer",
    "audit preserves the complete initial checked result",
)

check(
    serialized["reconciliation"]["revised"]["answer_draft"]
    == "revised answer",
    "audit preserves the complete revised checked result separately",
)

no_revision_result = reconciliation_orchestrator.AcademicReconciliationResult(
    initial=serial_initial,
    revised=None,
    revision_attempted=False,
)

no_revision_serialized = no_revision_result.to_dict()

check(
    no_revision_serialized["answer_draft"] == "initial answer",
    "without revision the initial result remains the top-level final result",
)

check(
    no_revision_serialized["reconciliation"]["revision_attempted"] is False,
    "audit records that no revision was attempted",
)

check(
    no_revision_serialized["reconciliation"]["revised"] is None,
    "audit represents absence of a revised assessment explicitly",
)


if fails:
    print(f"\n{len(fails)} test(s) failed.")
    raise SystemExit(1)

print("\nAll academic reconciliation lifecycle checks passed.")
