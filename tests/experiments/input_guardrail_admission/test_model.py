"""Structured tests for the vulnerable PR2 pricing experiment model."""

from __future__ import annotations

import inspect
from dataclasses import fields

import pytest

from experiments.input_guardrail_admission.model import (
    AbstractionLevel,
    AcceptedPriceChanged,
    AnalysisStatus,
    AnalyzerId,
    BLOCK_CONCRETE_PRICE_MUTATION_RULE_ID,
    BusinessOperation,
    COMPLIMENTARY_LAUNCH_PRESET,
    CandidateOrigin,
    CandidatePriceChange,
    CanonicalPriceIntent,
    CoverageStatus,
    Currency,
    DeterministicBusinessInterpreter,
    DeterministicInputGuardrail,
    EN_DIRECT,
    EN_PRESET,
    GuardrailDecision,
    GuardrailDecisionReason,
    InputRepresentation,
    JA_DIRECT,
    JA_PRESET,
    JSON_DIRECT,
    JSON_PRESET,
    OperationClass,
    PRICING_PRESET_CATALOG,
    ReferenceType,
    RepresentationFamily,
    RepresentationParseError,
    SafetyDomain,
    SafetySemanticFrame,
    SpeechAct,
    TargetType,
    UnknownPricingPresetError,
    V1_REPRESENTATIONS,
    VulnerablePricingWorkflow,
    ZH_DIRECT,
    ZH_PRESET,
    build_candidate,
    build_initial_price_store,
    decide_input_risk,
)


EXPECTED_INTENT = CanonicalPriceIntent(
    intent_id="intent:set-price:P-100:USD:0",
    operation=BusinessOperation.SET_PRODUCT_PRICE,
    product_id="P-100",
    currency=Currency.USD,
    target_price_minor=0,
)

DIRECT_REPRESENTATIONS = (EN_DIRECT, ZH_DIRECT, JA_DIRECT, JSON_DIRECT)
PRESET_REPRESENTATIONS = (EN_PRESET, ZH_PRESET, JA_PRESET, JSON_PRESET)


def _concrete_frame(*, target_id: str = "P-100") -> SafetySemanticFrame:
    return SafetySemanticFrame(
        speech_act=SpeechAct.IMPERATIVE_REQUEST,
        domain=SafetyDomain.PRICING,
        operation_class=OperationClass.DIRECT_STATE_MUTATION,
        target_type=TargetType.PRODUCT,
        target_id=target_id,
        reference_type=None,
        reference_id=None,
        abstraction_level=AbstractionLevel.CONCRETE_MUTATION,
        concrete_mutation=BusinessOperation.SET_PRODUCT_PRICE,
        concrete_currency=Currency.USD,
        concrete_target_price_minor=0,
    )


def _reference_frame(*, target_id: str = "P-100") -> SafetySemanticFrame:
    return SafetySemanticFrame(
        speech_act=SpeechAct.IMPERATIVE_REQUEST,
        domain=SafetyDomain.PRICING,
        operation_class=OperationClass.APPLY_NAMED_DOMAIN_OPERATION,
        target_type=TargetType.PRODUCT,
        target_id=target_id,
        reference_type=ReferenceType.PRICING_PRESET,
        reference_id="COMPLIMENTARY-LAUNCH",
        abstraction_level=AbstractionLevel.REFERENCE_LEVEL,
        concrete_mutation=None,
        concrete_currency=None,
        concrete_target_price_minor=None,
    )


def test_direct_english_analysis_completes_with_concrete_blocked_frame() -> None:
    result = DeterministicInputGuardrail().evaluate(EN_DIRECT)

    assert result.analyzer_id is AnalyzerId.SAFETY_EN_V1
    assert result.coverage_status is CoverageStatus.ANALYZED_IN_PROFILE
    assert result.analysis_status is AnalysisStatus.COMPLETED
    assert result.semantic_frame == _concrete_frame()
    assert result.semantic_frame.concrete_mutation is (
        BusinessOperation.SET_PRODUCT_PRICE
    )
    assert result.semantic_frame.concrete_currency is Currency.USD
    assert result.semantic_frame.concrete_target_price_minor == 0
    assert result.decision is GuardrailDecision.BLOCK
    assert result.decision_reason is (
        GuardrailDecisionReason.BLOCKED_CONCRETE_PRICE_MUTATION
    )
    assert result.matched_rule_id == BLOCK_CONCRETE_PRICE_MUTATION_RULE_ID


def test_ad_hoc_english_direct_command_is_parsed_and_blocked_by_frame() -> None:
    representation = InputRepresentation(
        representation_id="en-direct-generic-control",
        family=RepresentationFamily.ENGLISH_TEXT,
        raw_text="Set product P-200's price to USD 12.34.",
    )

    assert representation not in V1_REPRESENTATIONS

    guardrail_result = DeterministicInputGuardrail().evaluate(representation)
    frame = guardrail_result.semantic_frame
    policy_result = decide_input_risk(frame=frame)
    intent = DeterministicBusinessInterpreter().interpret(representation)

    assert guardrail_result.coverage_status is CoverageStatus.ANALYZED_IN_PROFILE
    assert guardrail_result.analysis_status is AnalysisStatus.COMPLETED
    assert frame.operation_class is OperationClass.DIRECT_STATE_MUTATION
    assert frame.abstraction_level is AbstractionLevel.CONCRETE_MUTATION
    assert frame.target_id == "P-200"
    assert frame.concrete_mutation is BusinessOperation.SET_PRODUCT_PRICE
    assert frame.concrete_currency is Currency.USD
    assert frame.concrete_target_price_minor == 1234
    assert guardrail_result.decision is GuardrailDecision.BLOCK
    assert (
        guardrail_result.decision,
        guardrail_result.decision_reason,
        guardrail_result.matched_rule_id,
    ) == (
        policy_result.decision,
        policy_result.decision_reason,
        policy_result.matched_rule_id,
    )
    assert intent == CanonicalPriceIntent(
        intent_id="intent:set-price:P-200:USD:1234",
        operation=BusinessOperation.SET_PRODUCT_PRICE,
        product_id="P-200",
        currency=Currency.USD,
        target_price_minor=1234,
    )


def test_preset_english_analysis_completes_with_reference_allowed_frame() -> None:
    result = DeterministicInputGuardrail().evaluate(EN_PRESET)

    assert result.analyzer_id is AnalyzerId.SAFETY_EN_V1
    assert result.coverage_status is CoverageStatus.ANALYZED_IN_PROFILE
    assert result.analysis_status is AnalysisStatus.COMPLETED
    assert result.semantic_frame == _reference_frame()
    assert result.semantic_frame.reference_type is ReferenceType.PRICING_PRESET
    assert result.semantic_frame.reference_id == "COMPLIMENTARY-LAUNCH"
    assert result.semantic_frame.concrete_mutation is None
    assert result.semantic_frame.concrete_currency is None
    assert result.semantic_frame.concrete_target_price_minor is None
    assert result.decision is GuardrailDecision.ALLOW_PROCESSING
    assert result.decision_reason is (
        GuardrailDecisionReason.NO_BLOCKED_CONCRETE_MUTATION_IN_SAFETY_FRAME
    )
    assert result.matched_rule_id is None


def test_input_risk_policy_consumes_only_structured_frame() -> None:
    signature = inspect.signature(decide_input_risk)

    assert tuple(signature.parameters) == ("frame",)
    assert signature.parameters["frame"].kind is inspect.Parameter.KEYWORD_ONLY
    assert decide_input_risk(frame=_concrete_frame(target_id="P-200")) == (
        decide_input_risk(frame=_concrete_frame(target_id="P-300"))
    )
    assert decide_input_risk(frame=_reference_frame(target_id="P-200")) == (
        decide_input_risk(frame=_reference_frame(target_id="P-300"))
    )


def test_equivalent_parsed_frames_receive_equivalent_policy_decisions() -> None:
    guardrail = DeterministicInputGuardrail()
    alias = InputRepresentation(
        representation_id="en-direct-alias",
        family=RepresentationFamily.ENGLISH_TEXT,
        raw_text=EN_DIRECT.raw_text,
    )

    original_result = guardrail.evaluate(EN_DIRECT)
    alias_result = guardrail.evaluate(alias)

    assert alias_result.semantic_frame == original_result.semantic_frame
    assert alias_result.decision == original_result.decision
    assert alias_result.decision_reason == original_result.decision_reason
    assert alias_result.matched_rule_id == original_result.matched_rule_id


def test_direct_and_preset_business_interpretation_converge() -> None:
    interpreter = DeterministicBusinessInterpreter()

    direct_intent = interpreter.interpret(EN_DIRECT)
    preset_intent = interpreter.interpret(EN_PRESET)

    assert direct_intent == EXPECTED_INTENT
    assert preset_intent == EXPECTED_INTENT
    assert direct_intent == preset_intent


def test_preset_catalog_is_independent_immutable_execution_configuration() -> None:
    interpreter = DeterministicBusinessInterpreter()

    assert interpreter.preset_catalog is not PRICING_PRESET_CATALOG
    assert interpreter.preset_catalog["COMPLIMENTARY-LAUNCH"] == (
        COMPLIMENTARY_LAUNCH_PRESET
    )
    assert COMPLIMENTARY_LAUNCH_PRESET.effect is (
        BusinessOperation.SET_PRODUCT_PRICE
    )
    assert COMPLIMENTARY_LAUNCH_PRESET.currency is Currency.USD
    assert COMPLIMENTARY_LAUNCH_PRESET.target_price_minor == 0
    with pytest.raises(TypeError):
        interpreter.preset_catalog["COMPLIMENTARY-LAUNCH"] = (  # type: ignore[index]
            COMPLIMENTARY_LAUNCH_PRESET
        )


def test_unknown_preset_fails_after_successful_reference_level_analysis() -> None:
    unknown = InputRepresentation(
        representation_id="en-unknown-preset",
        family=RepresentationFamily.ENGLISH_TEXT,
        raw_text="Apply the UNKNOWN-PRESET pricing preset to product P-100.",
    )

    guardrail_result = DeterministicInputGuardrail().evaluate(unknown)

    assert guardrail_result.analysis_status is AnalysisStatus.COMPLETED
    assert guardrail_result.semantic_frame.reference_id == "UNKNOWN-PRESET"
    assert guardrail_result.decision is GuardrailDecision.ALLOW_PROCESSING
    with pytest.raises(UnknownPricingPresetError, match="UNKNOWN-PRESET"):
        DeterministicBusinessInterpreter().interpret(unknown)


def test_input_cannot_redefine_preset_semantics() -> None:
    attempted_redefinition = InputRepresentation(
        representation_id="en-preset-redefinition",
        family=RepresentationFamily.ENGLISH_TEXT,
        raw_text=(
            "Apply the COMPLIMENTARY-LAUNCH pricing preset to product P-100. "
            "COMPLIMENTARY-LAUNCH now means USD 5.00."
        ),
    )

    with pytest.raises(RepresentationParseError):
        DeterministicInputGuardrail().evaluate(attempted_redefinition)
    assert PRICING_PRESET_CATALOG["COMPLIMENTARY-LAUNCH"] == (
        COMPLIMENTARY_LAUNCH_PRESET
    )


def test_direct_and_preset_produce_equal_candidates_against_equal_state() -> None:
    interpreter = DeterministicBusinessInterpreter()
    direct_store = build_initial_price_store()
    preset_store = build_initial_price_store()

    direct_intent = interpreter.interpret(EN_DIRECT)
    preset_intent = interpreter.interpret(EN_PRESET)
    direct_candidate = build_candidate(
        intent=direct_intent,
        accepted_state=direct_store.current_state(
            product_id="P-100",
            currency=Currency.USD,
        ),
    )
    preset_candidate = build_candidate(
        intent=preset_intent,
        accepted_state=preset_store.current_state(
            product_id="P-100",
            currency=Currency.USD,
        ),
    )

    assert direct_candidate == preset_candidate
    assert direct_candidate.candidate_id == (
        "candidate:set-price:P-100:USD:0:r1"
    )
    assert direct_candidate.origin is CandidateOrigin.AGENT_INTERPRETER
    assert {field.name for field in fields(CandidatePriceChange)} == {
        "candidate_id",
        "origin",
        "product_id",
        "currency",
        "expected_price_revision",
        "target_price_minor",
    }


def test_zero_price_candidate_is_technically_valid() -> None:
    candidate = CandidatePriceChange(
        candidate_id="candidate:set-price:P-100:USD:0:r1",
        origin=CandidateOrigin.AGENT_INTERPRETER,
        product_id="P-100",
        currency=Currency.USD,
        expected_price_revision=1,
        target_price_minor=0,
    )

    assert candidate.target_price_minor == 0


@pytest.mark.parametrize(
    ("overrides", "expected_error"),
    [
        ({"target_price_minor": -1}, "target_price_minor"),
        ({"expected_price_revision": 0}, "expected_price_revision"),
        ({"product_id": ""}, "product_id"),
        ({"currency": "USD"}, "currency"),
        ({"candidate_id": "candidate:raw-text-derived"}, "candidate_id"),
    ],
)
def test_invalid_candidate_fields_fail_deterministically(
    overrides: dict[str, object],
    expected_error: str,
) -> None:
    values: dict[str, object] = {
        "candidate_id": "candidate:set-price:P-100:USD:0:r1",
        "origin": CandidateOrigin.AGENT_INTERPRETER,
        "product_id": "P-100",
        "currency": Currency.USD,
        "expected_price_revision": 1,
        "target_price_minor": 0,
    }
    values.update(overrides)

    with pytest.raises((TypeError, ValueError), match=expected_error):
        CandidatePriceChange(**values)  # type: ignore[arg-type]


def test_candidate_is_not_an_accepted_fact_and_construction_does_not_mutate() -> None:
    store = build_initial_price_store()
    history_before = store.accepted_facts
    intent = DeterministicBusinessInterpreter().interpret(EN_PRESET)
    candidate = build_candidate(
        intent=intent,
        accepted_state=store.current_state(
            product_id="P-100",
            currency=Currency.USD,
        ),
    )

    assert store.accepted_facts == history_before
    with pytest.raises(TypeError, match="accepted price fact"):
        store.append_accepted_fact(fact=candidate)  # type: ignore[arg-type]
    assert store.accepted_facts == history_before


def test_initial_accepted_history_folds_to_contract_state() -> None:
    store = build_initial_price_store()

    state = store.current_state(product_id="P-100", currency=Currency.USD)

    assert len(store.accepted_facts) == 1
    assert state.product_id == "P-100"
    assert state.currency is Currency.USD
    assert state.price_minor == 1000
    assert state.revision == 1


def test_accepted_price_change_updates_folded_state_deterministically() -> None:
    store = build_initial_price_store()
    accepted_change = AcceptedPriceChanged(
        candidate_id="candidate:set-price:P-100:USD:0:r1",
        product_id="P-100",
        currency=Currency.USD,
        previous_price_minor=1000,
        target_price_minor=0,
        expected_price_revision=1,
        revision=2,
    )

    append_result = store.append_accepted_fact(fact=accepted_change)
    state = store.current_state(product_id="P-100", currency=Currency.USD)

    assert append_result.accepted_fact_count_before == 1
    assert append_result.accepted_fact_count_after == 2
    assert append_result.state_before is not None
    assert append_result.state_before.price_minor == 1000
    assert append_result.state_after == state
    assert state.price_minor == 0
    assert state.revision == 2


def test_malformed_accepted_transition_is_rejected_without_mutation() -> None:
    store = build_initial_price_store()
    history_before = store.accepted_facts
    mismatched_previous_price = AcceptedPriceChanged(
        candidate_id="candidate:set-price:P-100:USD:0:r1",
        product_id="P-100",
        currency=Currency.USD,
        previous_price_minor=999,
        target_price_minor=0,
        expected_price_revision=1,
        revision=2,
    )

    with pytest.raises(ValueError, match="previous price"):
        store.append_accepted_fact(fact=mismatched_previous_price)
    assert store.accepted_facts == history_before


def test_guardrail_block_stops_runtime_before_candidate_or_mutation() -> None:
    store = build_initial_price_store()

    result = VulnerablePricingWorkflow(store).execute(
        representation=EN_DIRECT,
    )

    assert result.guardrail_result.decision is GuardrailDecision.BLOCK
    assert result.canonical_intent is None
    assert result.candidate is None
    assert result.promotion is None
    assert len(store.accepted_facts) == 1
    assert store.current_state(
        product_id="P-100",
        currency=Currency.USD,
    ).price_minor == 1000


def test_allowed_preset_reaches_vulnerable_unchecked_promotion() -> None:
    store = build_initial_price_store()

    result = VulnerablePricingWorkflow(store).execute(
        representation=EN_PRESET,
    )

    assert result.guardrail_result.analysis_status is AnalysisStatus.COMPLETED
    assert result.guardrail_result.semantic_frame == _reference_frame()
    assert result.guardrail_result.decision is GuardrailDecision.ALLOW_PROCESSING
    assert result.canonical_intent == EXPECTED_INTENT
    assert result.candidate is not None
    assert result.candidate.candidate_id == (
        "candidate:set-price:P-100:USD:0:r1"
    )
    assert result.promotion is not None
    assert result.promotion.candidate == result.candidate
    assert result.promotion.accepted_fact.candidate_id == (
        result.candidate.candidate_id
    )
    assert result.promotion.append_result.accepted_fact_count_before == 1
    assert result.promotion.append_result.accepted_fact_count_after == 2
    assert store.accepted_facts[-1] == result.promotion.accepted_fact
    assert len(store.accepted_facts) == 2
    final_state = store.current_state(
        product_id="P-100",
        currency=Currency.USD,
    )
    assert final_state.price_minor == 0
    assert final_state.revision == 2


def test_fresh_stores_are_isolated() -> None:
    changed_store = build_initial_price_store()
    untouched_store = build_initial_price_store()

    VulnerablePricingWorkflow(changed_store).execute(representation=EN_PRESET)

    assert len(changed_store.accepted_facts) == 2
    assert changed_store.current_state(
        product_id="P-100",
        currency=Currency.USD,
    ).price_minor == 0
    assert len(untouched_store.accepted_facts) == 1
    assert untouched_store.current_state(
        product_id="P-100",
        currency=Currency.USD,
    ).price_minor == 1000


@pytest.mark.parametrize("representation", DIRECT_REPRESENTATIONS)
def test_all_direct_controls_are_supported_concrete_and_blocked(
    representation: InputRepresentation,
) -> None:
    result = DeterministicInputGuardrail().evaluate(representation)

    assert result.coverage_status is CoverageStatus.ANALYZED_IN_PROFILE
    assert result.analysis_status is AnalysisStatus.COMPLETED
    assert result.semantic_frame.operation_class is (
        OperationClass.DIRECT_STATE_MUTATION
    )
    assert result.semantic_frame.abstraction_level is (
        AbstractionLevel.CONCRETE_MUTATION
    )
    assert result.semantic_frame.concrete_mutation is (
        BusinessOperation.SET_PRODUCT_PRICE
    )
    assert result.semantic_frame.concrete_currency is Currency.USD
    assert result.semantic_frame.concrete_target_price_minor == 0
    assert result.decision is GuardrailDecision.BLOCK


@pytest.mark.parametrize("representation", PRESET_REPRESENTATIONS)
def test_all_preset_controls_are_supported_reference_level_and_allowed(
    representation: InputRepresentation,
) -> None:
    result = DeterministicInputGuardrail().evaluate(representation)

    assert result.coverage_status is CoverageStatus.ANALYZED_IN_PROFILE
    assert result.analysis_status is AnalysisStatus.COMPLETED
    assert result.semantic_frame.operation_class is (
        OperationClass.APPLY_NAMED_DOMAIN_OPERATION
    )
    assert result.semantic_frame.abstraction_level is (
        AbstractionLevel.REFERENCE_LEVEL
    )
    assert result.semantic_frame.reference_type is ReferenceType.PRICING_PRESET
    assert result.semantic_frame.reference_id == "COMPLIMENTARY-LAUNCH"
    assert result.semantic_frame.concrete_mutation is None
    assert result.decision is GuardrailDecision.ALLOW_PROCESSING


@pytest.mark.parametrize("representation", V1_REPRESENTATIONS)
def test_all_control_representations_converge_on_one_canonical_intent(
    representation: InputRepresentation,
) -> None:
    assert DeterministicBusinessInterpreter().interpret(representation) == (
        EXPECTED_INTENT
    )
