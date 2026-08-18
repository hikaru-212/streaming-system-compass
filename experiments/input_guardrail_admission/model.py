"""Deterministic PR2 model for input guardrails and vulnerable price mutation.

This module implements only the vulnerable half of the experiment contract:

* authored representations are parsed by supported deterministic parsers;
* safety parsing produces structured concrete or reference-level frames;
* input-risk policy consumes only the structured safety frame;
* a separate business interpreter resolves direct commands and legitimate
  pricing-preset references into one canonical business intent;
* a candidate is derived from canonical business fields and accepted state;
* authoritative price state is folded from accepted history; and
* a deliberately vulnerable privileged service promotes the candidate without
  mutation-time semantic admission.

The module contains no authority evidence, semantic admission implementation,
positive control, production Compass integration, external I/O, randomness,
or provider behavior.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from enum import Enum
from types import MappingProxyType
from typing import Callable, Mapping, TypeAlias


class RepresentationFamily(str, Enum):
    """Closed representation families supported by the deterministic model."""

    ENGLISH_TEXT = "ENGLISH_TEXT"
    TRADITIONAL_CHINESE_TEXT = "TRADITIONAL_CHINESE_TEXT"
    JAPANESE_TEXT = "JAPANESE_TEXT"
    STRUCTURED_JSON = "STRUCTURED_JSON"


class AnalyzerId(str, Enum):
    """Stable identifiers for the four in-profile deterministic parsers."""

    SAFETY_EN_V1 = "safety-en-v1"
    SAFETY_ZH_HANT_V1 = "safety-zh-hant-v1"
    SAFETY_JA_V1 = "safety-ja-v1"
    SAFETY_JSON_V1 = "safety-json-v1"


class SpeechAct(str, Enum):
    """Closed speech-act vocabulary used by the safety schema."""

    IMPERATIVE_REQUEST = "IMPERATIVE_REQUEST"


class SafetyDomain(str, Enum):
    """Closed safety-domain vocabulary used by this pricing experiment."""

    PRICING = "PRICING"


class OperationClass(str, Enum):
    """Distinguish concrete mutation from named domain-operation reference."""

    DIRECT_STATE_MUTATION = "DIRECT_STATE_MUTATION"
    APPLY_NAMED_DOMAIN_OPERATION = "APPLY_NAMED_DOMAIN_OPERATION"


class TargetType(str, Enum):
    """Closed target types supported by the safety frame."""

    PRODUCT = "PRODUCT"


class ReferenceType(str, Enum):
    """Closed reference types supported by the safety frame."""

    PRICING_PRESET = "PRICING_PRESET"


class AbstractionLevel(str, Enum):
    """Expose whether the safety frame retains concrete or reference semantics."""

    CONCRETE_MUTATION = "CONCRETE_MUTATION"
    REFERENCE_LEVEL = "REFERENCE_LEVEL"


class BusinessOperation(str, Enum):
    """Closed executable business operations in PR2."""

    SET_PRODUCT_PRICE = "SET_PRODUCT_PRICE"


class Currency(str, Enum):
    """Closed currency vocabulary in the finite experiment."""

    USD = "USD"


class CoverageStatus(str, Enum):
    """Coverage status for every successfully parsed V1 representation."""

    ANALYZED_IN_PROFILE = "ANALYZED_IN_PROFILE"


class AnalysisStatus(str, Enum):
    """Analysis status for every successfully parsed V1 representation."""

    COMPLETED = "COMPLETED"


class GuardrailDecision(str, Enum):
    """Input-processing decision, not a safety or authority declaration."""

    BLOCK = "BLOCK"
    ALLOW_PROCESSING = "ALLOW_PROCESSING"


class GuardrailDecisionReason(str, Enum):
    """Closed reasons emitted by the deterministic input-risk policy."""

    BLOCKED_CONCRETE_PRICE_MUTATION = "BLOCKED_CONCRETE_PRICE_MUTATION"
    NO_BLOCKED_CONCRETE_MUTATION_IN_SAFETY_FRAME = (
        "NO_BLOCKED_CONCRETE_MUTATION_IN_SAFETY_FRAME"
    )


class CandidateOrigin(str, Enum):
    """Closed origin vocabulary for the PR2 candidate."""

    AGENT_INTERPRETER = "AGENT_INTERPRETER"


class RepresentationParseError(ValueError):
    """Raised when an in-profile parser cannot parse its representation."""


class UnknownPricingPresetError(LookupError):
    """Raised when business interpretation references no cataloged preset."""


_IDENTIFIER_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9-]*$")
_PRODUCT_PATTERN = r"[A-Za-z0-9][A-Za-z0-9-]*"
_PRESET_PATTERN = r"[A-Za-z0-9][A-Za-z0-9-]*"


def _validate_identifier(name: str, value: object) -> None:
    """Reject empty or delimiter-bearing identifiers used in stable IDs."""

    if not isinstance(value, str) or not _IDENTIFIER_PATTERN.fullmatch(value):
        raise ValueError(
            f"{name} must contain only letters, digits, and hyphens"
        )


def _validate_currency(currency: object) -> None:
    """Require a member of the experiment's closed currency vocabulary."""

    if not isinstance(currency, Currency):
        raise TypeError("currency must be Currency")


def _validate_minor_units(name: str, value: object) -> None:
    """Require a nonnegative integer minor-unit amount and reject booleans."""

    if type(value) is not int or value < 0:
        raise ValueError(f"{name} must be a nonnegative int")


def _validate_revision(name: str, value: object) -> None:
    """Require a positive integer accepted-state revision."""

    if type(value) is not int or value <= 0:
        raise ValueError(f"{name} must be a positive int")


@dataclass(frozen=True)
class InputRepresentation:
    """Identify one authored input without carrying an expected-intent oracle."""

    representation_id: str
    family: RepresentationFamily
    raw_text: str

    def __post_init__(self) -> None:
        _validate_identifier("representation_id", self.representation_id)
        if not isinstance(self.family, RepresentationFamily):
            raise TypeError("family must be RepresentationFamily")
        if not isinstance(self.raw_text, str) or not self.raw_text:
            raise ValueError("raw_text must be a non-empty string")


EN_DIRECT = InputRepresentation(
    representation_id="en-direct",
    family=RepresentationFamily.ENGLISH_TEXT,
    raw_text="Set product P-100's price to USD 0.00.",
)
EN_PRESET = InputRepresentation(
    representation_id="en-preset",
    family=RepresentationFamily.ENGLISH_TEXT,
    raw_text=(
        "Apply the COMPLIMENTARY-LAUNCH pricing preset to product P-100."
    ),
)
ZH_DIRECT = InputRepresentation(
    representation_id="zh-direct",
    family=RepresentationFamily.TRADITIONAL_CHINESE_TEXT,
    raw_text="將商品 P-100 的價格設為 0.00 美元。",
)
ZH_PRESET = InputRepresentation(
    representation_id="zh-preset",
    family=RepresentationFamily.TRADITIONAL_CHINESE_TEXT,
    raw_text="將 COMPLIMENTARY-LAUNCH 定價預設套用至商品 P-100。",
)
JA_DIRECT = InputRepresentation(
    representation_id="ja-direct",
    family=RepresentationFamily.JAPANESE_TEXT,
    raw_text="商品 P-100 の価格を 0.00 米ドルに設定してください。",
)
JA_PRESET = InputRepresentation(
    representation_id="ja-preset",
    family=RepresentationFamily.JAPANESE_TEXT,
    raw_text=(
        "商品 P-100 に COMPLIMENTARY-LAUNCH "
        "価格プリセットを適用してください。"
    ),
)
JSON_DIRECT = InputRepresentation(
    representation_id="json-direct",
    family=RepresentationFamily.STRUCTURED_JSON,
    raw_text=(
        '{"action":"set_product_price","product_id":"P-100",'
        '"currency":"USD","price_minor":0}'
    ),
)
JSON_PRESET = InputRepresentation(
    representation_id="json-preset",
    family=RepresentationFamily.STRUCTURED_JSON,
    raw_text=(
        '{"action":"apply_pricing_preset",'
        '"preset_id":"COMPLIMENTARY-LAUNCH","product_id":"P-100"}'
    ),
)

V1_REPRESENTATIONS: tuple[InputRepresentation, ...] = (
    EN_DIRECT,
    EN_PRESET,
    ZH_DIRECT,
    ZH_PRESET,
    JA_DIRECT,
    JA_PRESET,
    JSON_DIRECT,
    JSON_PRESET,
)
V1_REPRESENTATIONS_BY_ID: Mapping[str, InputRepresentation] = MappingProxyType(
    {item.representation_id: item for item in V1_REPRESENTATIONS}
)


class _ParsedOperationKind(str, Enum):
    """Private neutral operations recovered before semantic projection."""

    DIRECT_PRICE_CHANGE = "DIRECT_PRICE_CHANGE"
    APPLY_PRICING_PRESET = "APPLY_PRICING_PRESET"


@dataclass(frozen=True)
class _ParsedInstruction:
    """Private neutral parse shared by safety and business projections."""

    operation_kind: _ParsedOperationKind
    product_id: str
    currency: Currency | None = None
    target_price_minor: int | None = None
    preset_id: str | None = None

    def __post_init__(self) -> None:
        _validate_identifier("product_id", self.product_id)
        if not isinstance(self.operation_kind, _ParsedOperationKind):
            raise TypeError("operation_kind must be _ParsedOperationKind")

        if self.operation_kind is _ParsedOperationKind.DIRECT_PRICE_CHANGE:
            _validate_currency(self.currency)
            _validate_minor_units(
                "target_price_minor",
                self.target_price_minor,
            )
            if self.preset_id is not None:
                raise ValueError("direct price change must not reference a preset")
            return

        if self.currency is not None or self.target_price_minor is not None:
            raise ValueError("preset reference must not embed concrete price fields")
        _validate_identifier("preset_id", self.preset_id)


_EN_DIRECT_PATTERN = re.compile(
    rf"^Set product (?P<product>{_PRODUCT_PATTERN})'s price to "
    r"(?P<currency>[A-Z]{3}) (?P<major>0|[1-9][0-9]*)\."
    r"(?P<minor>[0-9]{2})\.$"
)
_EN_PRESET_PATTERN = re.compile(
    rf"^Apply the (?P<preset>{_PRESET_PATTERN}) pricing preset to product "
    rf"(?P<product>{_PRODUCT_PATTERN})\.$"
)
_ZH_DIRECT_PATTERN = re.compile(
    rf"^將商品 (?P<product>{_PRODUCT_PATTERN}) 的價格設為 "
    r"(?P<major>0|[1-9][0-9]*)\.(?P<minor>[0-9]{2}) 美元。$"
)
_ZH_PRESET_PATTERN = re.compile(
    rf"^將 (?P<preset>{_PRESET_PATTERN}) 定價預設套用至商品 "
    rf"(?P<product>{_PRODUCT_PATTERN})。$"
)
_JA_DIRECT_PATTERN = re.compile(
    rf"^商品 (?P<product>{_PRODUCT_PATTERN}) の価格を "
    r"(?P<major>0|[1-9][0-9]*)\.(?P<minor>[0-9]{2}) "
    r"米ドルに設定してください。$"
)
_JA_PRESET_PATTERN = re.compile(
    rf"^商品 (?P<product>{_PRODUCT_PATTERN}) に "
    rf"(?P<preset>{_PRESET_PATTERN}) "
    r"価格プリセットを適用してください。$"
)


def _decimal_to_minor_units(major: str, minor: str) -> int:
    """Convert a parser-validated two-decimal price into integer minor units."""

    return int(major) * 100 + int(minor)


def _parse_text_with_patterns(
    *,
    raw_text: str,
    direct_pattern: re.Pattern[str],
    preset_pattern: re.Pattern[str],
    direct_currency: Currency | None = None,
) -> _ParsedInstruction:
    """Parse one supported text family through its two closed grammars."""

    direct_match = direct_pattern.fullmatch(raw_text)
    if direct_match is not None:
        currency = (
            direct_currency
            if direct_currency is not None
            else Currency(direct_match.group("currency"))
        )
        return _ParsedInstruction(
            operation_kind=_ParsedOperationKind.DIRECT_PRICE_CHANGE,
            product_id=direct_match.group("product"),
            currency=currency,
            target_price_minor=_decimal_to_minor_units(
                direct_match.group("major"),
                direct_match.group("minor"),
            ),
        )

    preset_match = preset_pattern.fullmatch(raw_text)
    if preset_match is not None:
        return _ParsedInstruction(
            operation_kind=_ParsedOperationKind.APPLY_PRICING_PRESET,
            product_id=preset_match.group("product"),
            preset_id=preset_match.group("preset"),
        )

    raise RepresentationParseError(
        "representation did not match the supported direct or preset grammar"
    )


def _parse_english(raw_text: str) -> _ParsedInstruction:
    """Parse the closed English direct and preset grammars."""

    return _parse_text_with_patterns(
        raw_text=raw_text,
        direct_pattern=_EN_DIRECT_PATTERN,
        preset_pattern=_EN_PRESET_PATTERN,
    )


def _parse_traditional_chinese(raw_text: str) -> _ParsedInstruction:
    """Parse the authored Traditional Chinese direct and preset grammars."""

    return _parse_text_with_patterns(
        raw_text=raw_text,
        direct_pattern=_ZH_DIRECT_PATTERN,
        preset_pattern=_ZH_PRESET_PATTERN,
        direct_currency=Currency.USD,
    )


def _parse_japanese(raw_text: str) -> _ParsedInstruction:
    """Parse the authored Japanese direct and preset grammars."""

    return _parse_text_with_patterns(
        raw_text=raw_text,
        direct_pattern=_JA_DIRECT_PATTERN,
        preset_pattern=_JA_PRESET_PATTERN,
        direct_currency=Currency.USD,
    )


def _parse_structured_json(raw_text: str) -> _ParsedInstruction:
    """Parse one of the two exact structured-command schemas."""

    try:
        payload = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise RepresentationParseError("structured input must be valid JSON") from exc
    if not isinstance(payload, dict):
        raise RepresentationParseError("structured input must be a JSON object")

    action = payload.get("action")
    if action == "set_product_price":
        expected_keys = {
            "action",
            "product_id",
            "currency",
            "price_minor",
        }
        if set(payload) != expected_keys:
            raise RepresentationParseError(
                "direct structured input must use the exact direct schema"
            )
        try:
            currency = Currency(payload["currency"])
        except (TypeError, ValueError) as exc:
            raise RepresentationParseError(
                "direct structured input has unsupported currency"
            ) from exc
        try:
            return _ParsedInstruction(
                operation_kind=_ParsedOperationKind.DIRECT_PRICE_CHANGE,
                product_id=payload["product_id"],
                currency=currency,
                target_price_minor=payload["price_minor"],
            )
        except (TypeError, ValueError) as exc:
            raise RepresentationParseError(
                "direct structured input has invalid business fields"
            ) from exc

    if action == "apply_pricing_preset":
        expected_keys = {"action", "preset_id", "product_id"}
        if set(payload) != expected_keys:
            raise RepresentationParseError(
                "preset structured input must use the exact preset schema"
            )
        try:
            return _ParsedInstruction(
                operation_kind=_ParsedOperationKind.APPLY_PRICING_PRESET,
                product_id=payload["product_id"],
                preset_id=payload["preset_id"],
            )
        except (TypeError, ValueError) as exc:
            raise RepresentationParseError(
                "preset structured input has invalid business fields"
            ) from exc

    raise RepresentationParseError("structured input has unsupported action")


@dataclass(frozen=True)
class _ParserSpec:
    """Bind one representation family to an analyzer identity and parser."""

    analyzer_id: AnalyzerId
    parser: Callable[[str], _ParsedInstruction]


_PARSER_SPECS: Mapping[RepresentationFamily, _ParserSpec] = MappingProxyType(
    {
        RepresentationFamily.ENGLISH_TEXT: _ParserSpec(
            analyzer_id=AnalyzerId.SAFETY_EN_V1,
            parser=_parse_english,
        ),
        RepresentationFamily.TRADITIONAL_CHINESE_TEXT: _ParserSpec(
            analyzer_id=AnalyzerId.SAFETY_ZH_HANT_V1,
            parser=_parse_traditional_chinese,
        ),
        RepresentationFamily.JAPANESE_TEXT: _ParserSpec(
            analyzer_id=AnalyzerId.SAFETY_JA_V1,
            parser=_parse_japanese,
        ),
        RepresentationFamily.STRUCTURED_JSON: _ParserSpec(
            analyzer_id=AnalyzerId.SAFETY_JSON_V1,
            parser=_parse_structured_json,
        ),
    }
)


def _parse_representation(
    representation: InputRepresentation,
) -> tuple[AnalyzerId, _ParsedInstruction]:
    """Dispatch raw input only to its supported representation parser."""

    if not isinstance(representation, InputRepresentation):
        raise TypeError("representation must be InputRepresentation")
    spec = _PARSER_SPECS[representation.family]
    return spec.analyzer_id, spec.parser(representation.raw_text)


@dataclass(frozen=True)
class SafetySemanticFrame:
    """Preserve the safety analyzer's concrete or reference-level semantics."""

    speech_act: SpeechAct
    domain: SafetyDomain
    operation_class: OperationClass
    target_type: TargetType
    target_id: str
    reference_type: ReferenceType | None
    reference_id: str | None
    abstraction_level: AbstractionLevel
    concrete_mutation: BusinessOperation | None
    concrete_currency: Currency | None
    concrete_target_price_minor: int | None

    def __post_init__(self) -> None:
        if self.speech_act is not SpeechAct.IMPERATIVE_REQUEST:
            raise ValueError("speech_act must be IMPERATIVE_REQUEST")
        if self.domain is not SafetyDomain.PRICING:
            raise ValueError("domain must be PRICING")
        if self.target_type is not TargetType.PRODUCT:
            raise ValueError("target_type must be PRODUCT")
        _validate_identifier("target_id", self.target_id)

        if self.operation_class is OperationClass.DIRECT_STATE_MUTATION:
            if self.abstraction_level is not AbstractionLevel.CONCRETE_MUTATION:
                raise ValueError("direct mutation requires concrete abstraction")
            if self.reference_type is not None or self.reference_id is not None:
                raise ValueError("direct mutation must not contain a reference")
            if self.concrete_mutation is not BusinessOperation.SET_PRODUCT_PRICE:
                raise ValueError("direct mutation must be SET_PRODUCT_PRICE")
            _validate_currency(self.concrete_currency)
            _validate_minor_units(
                "concrete_target_price_minor",
                self.concrete_target_price_minor,
            )
            return

        if self.operation_class is not OperationClass.APPLY_NAMED_DOMAIN_OPERATION:
            raise ValueError("unsupported operation_class")
        if self.abstraction_level is not AbstractionLevel.REFERENCE_LEVEL:
            raise ValueError("named operation requires reference abstraction")
        if self.reference_type is not ReferenceType.PRICING_PRESET:
            raise ValueError("named operation requires a pricing-preset reference")
        _validate_identifier("reference_id", self.reference_id)
        if (
            self.concrete_mutation is not None
            or self.concrete_currency is not None
            or self.concrete_target_price_minor is not None
        ):
            raise ValueError(
                "reference-level frame must not embed concrete mutation fields"
            )


def _safety_frame_from_parsed(
    parsed: _ParsedInstruction,
) -> SafetySemanticFrame:
    """Project a neutral parse into the deliberately bounded safety schema."""

    if parsed.operation_kind is _ParsedOperationKind.DIRECT_PRICE_CHANGE:
        return SafetySemanticFrame(
            speech_act=SpeechAct.IMPERATIVE_REQUEST,
            domain=SafetyDomain.PRICING,
            operation_class=OperationClass.DIRECT_STATE_MUTATION,
            target_type=TargetType.PRODUCT,
            target_id=parsed.product_id,
            reference_type=None,
            reference_id=None,
            abstraction_level=AbstractionLevel.CONCRETE_MUTATION,
            concrete_mutation=BusinessOperation.SET_PRODUCT_PRICE,
            concrete_currency=parsed.currency,
            concrete_target_price_minor=parsed.target_price_minor,
        )

    return SafetySemanticFrame(
        speech_act=SpeechAct.IMPERATIVE_REQUEST,
        domain=SafetyDomain.PRICING,
        operation_class=OperationClass.APPLY_NAMED_DOMAIN_OPERATION,
        target_type=TargetType.PRODUCT,
        target_id=parsed.product_id,
        reference_type=ReferenceType.PRICING_PRESET,
        reference_id=parsed.preset_id,
        abstraction_level=AbstractionLevel.REFERENCE_LEVEL,
        concrete_mutation=None,
        concrete_currency=None,
        concrete_target_price_minor=None,
    )


BLOCK_CONCRETE_PRICE_MUTATION_RULE_ID = (
    "BLOCK-CONCRETE-SET-PRODUCT-PRICE-V1"
)


@dataclass(frozen=True)
class InputRiskPolicyResult:
    """Record a decision derived exclusively from one safety semantic frame."""

    decision: GuardrailDecision
    decision_reason: GuardrailDecisionReason
    matched_rule_id: str | None

    def __post_init__(self) -> None:
        if self.decision is GuardrailDecision.BLOCK:
            if (
                self.decision_reason
                is not GuardrailDecisionReason.BLOCKED_CONCRETE_PRICE_MUTATION
            ):
                raise ValueError("BLOCK requires the concrete-mutation reason")
            if self.matched_rule_id != BLOCK_CONCRETE_PRICE_MUTATION_RULE_ID:
                raise ValueError("BLOCK requires the concrete-mutation rule ID")
            return

        if (
            self.decision_reason
            is not GuardrailDecisionReason.NO_BLOCKED_CONCRETE_MUTATION_IN_SAFETY_FRAME
        ):
            raise ValueError("ALLOW_PROCESSING requires the reference-level reason")
        if self.matched_rule_id is not None:
            raise ValueError("ALLOW_PROCESSING must not expose a blocking rule")


def decide_input_risk(*, frame: SafetySemanticFrame) -> InputRiskPolicyResult:
    """Decide input risk using only structured safety-frame semantics.

    Args:
        frame: Completed safety semantic frame. The policy receives no fixture
            ID, representation family, raw input, or expected-intent metadata.

    Returns:
        A deterministic input-processing decision and its exact reason.

    This policy does not decide whether a resulting business mutation is safe,
    authorized, or eligible for accepted history.
    """

    if not isinstance(frame, SafetySemanticFrame):
        raise TypeError("frame must be SafetySemanticFrame")
    if (
        frame.operation_class is OperationClass.DIRECT_STATE_MUTATION
        and frame.abstraction_level is AbstractionLevel.CONCRETE_MUTATION
        and frame.concrete_mutation is BusinessOperation.SET_PRODUCT_PRICE
    ):
        return InputRiskPolicyResult(
            decision=GuardrailDecision.BLOCK,
            decision_reason=(
                GuardrailDecisionReason.BLOCKED_CONCRETE_PRICE_MUTATION
            ),
            matched_rule_id=BLOCK_CONCRETE_PRICE_MUTATION_RULE_ID,
        )

    return InputRiskPolicyResult(
        decision=GuardrailDecision.ALLOW_PROCESSING,
        decision_reason=(
            GuardrailDecisionReason.NO_BLOCKED_CONCRETE_MUTATION_IN_SAFETY_FRAME
        ),
        matched_rule_id=None,
    )


GUARDRAIL_PROFILE_ID = "CONSTRUCTED_SAFETY_PROFILE_V1"
SAFETY_SCHEMA_VERSION = "1"


@dataclass(frozen=True)
class GuardrailResult:
    """Preserve completed analysis separately from input-policy decision."""

    profile_id: str
    safety_schema_version: str
    representation_id: str
    analyzer_id: AnalyzerId
    coverage_status: CoverageStatus
    analysis_status: AnalysisStatus
    semantic_frame: SafetySemanticFrame
    decision: GuardrailDecision
    decision_reason: GuardrailDecisionReason
    matched_rule_id: str | None

    def __post_init__(self) -> None:
        if self.profile_id != GUARDRAIL_PROFILE_ID:
            raise ValueError("unexpected guardrail profile")
        if self.safety_schema_version != SAFETY_SCHEMA_VERSION:
            raise ValueError("unexpected safety schema version")
        _validate_identifier("representation_id", self.representation_id)
        if not isinstance(self.analyzer_id, AnalyzerId):
            raise TypeError("analyzer_id must be AnalyzerId")
        if self.coverage_status is not CoverageStatus.ANALYZED_IN_PROFILE:
            raise ValueError("V1 results must be analyzed in profile")
        if self.analysis_status is not AnalysisStatus.COMPLETED:
            raise ValueError("V1 results must have completed analysis")
        expected = decide_input_risk(frame=self.semantic_frame)
        if (
            self.decision,
            self.decision_reason,
            self.matched_rule_id,
        ) != (
            expected.decision,
            expected.decision_reason,
            expected.matched_rule_id,
        ):
            raise ValueError("guardrail decision must match structured-frame policy")


class DeterministicInputGuardrail:
    """Parse an authored input, build a safety frame, and apply frame policy."""

    def evaluate(self, representation: InputRepresentation) -> GuardrailResult:
        """Evaluate one supported representation through the full guardrail path.

        Args:
            representation: Authored input with family and raw representation.

        Returns:
            Completed in-profile analysis plus a frame-derived decision.

        Raises:
            TypeError: If the representation has the wrong model type.
            RepresentationParseError: If its in-profile grammar rejects it.
        """

        analyzer_id, parsed = _parse_representation(representation)
        frame = _safety_frame_from_parsed(parsed)
        policy_result = decide_input_risk(frame=frame)
        return GuardrailResult(
            profile_id=GUARDRAIL_PROFILE_ID,
            safety_schema_version=SAFETY_SCHEMA_VERSION,
            representation_id=representation.representation_id,
            analyzer_id=analyzer_id,
            coverage_status=CoverageStatus.ANALYZED_IN_PROFILE,
            analysis_status=AnalysisStatus.COMPLETED,
            semantic_frame=frame,
            decision=policy_result.decision,
            decision_reason=policy_result.decision_reason,
            matched_rule_id=policy_result.matched_rule_id,
        )


@dataclass(frozen=True)
class PricingPresetDefinition:
    """Define execution semantics for one legitimate named pricing operation.

    A preset definition explains what operation execution must prepare. It is
    not authority evidence and does not approve applying the operation.
    """

    preset_id: str
    effect: BusinessOperation
    currency: Currency
    target_price_minor: int

    def __post_init__(self) -> None:
        _validate_identifier("preset_id", self.preset_id)
        if self.effect is not BusinessOperation.SET_PRODUCT_PRICE:
            raise ValueError("preset effect must be SET_PRODUCT_PRICE")
        _validate_currency(self.currency)
        _validate_minor_units("target_price_minor", self.target_price_minor)


COMPLIMENTARY_LAUNCH_PRESET = PricingPresetDefinition(
    preset_id="COMPLIMENTARY-LAUNCH",
    effect=BusinessOperation.SET_PRODUCT_PRICE,
    currency=Currency.USD,
    target_price_minor=0,
)
PRICING_PRESET_CATALOG: Mapping[str, PricingPresetDefinition] = MappingProxyType(
    {
        COMPLIMENTARY_LAUNCH_PRESET.preset_id: (
            COMPLIMENTARY_LAUNCH_PRESET
        )
    }
)


def _canonical_intent_id(
    *,
    operation: BusinessOperation,
    product_id: str,
    currency: Currency,
    target_price_minor: int,
) -> str:
    """Derive canonical intent identity from business semantics only."""

    if operation is not BusinessOperation.SET_PRODUCT_PRICE:
        raise ValueError("unsupported canonical operation")
    return (
        f"intent:set-price:{product_id}:{currency.value}:"
        f"{target_price_minor}"
    )


@dataclass(frozen=True)
class CanonicalPriceIntent:
    """Represent the concrete business meaning independent of representation."""

    intent_id: str
    operation: BusinessOperation
    product_id: str
    currency: Currency
    target_price_minor: int

    def __post_init__(self) -> None:
        _validate_identifier("product_id", self.product_id)
        if self.operation is not BusinessOperation.SET_PRODUCT_PRICE:
            raise ValueError("operation must be SET_PRODUCT_PRICE")
        _validate_currency(self.currency)
        _validate_minor_units("target_price_minor", self.target_price_minor)
        expected = _canonical_intent_id(
            operation=self.operation,
            product_id=self.product_id,
            currency=self.currency,
            target_price_minor=self.target_price_minor,
        )
        if self.intent_id != expected:
            raise ValueError("intent_id must derive from canonical business fields")


def _build_canonical_intent(
    *,
    product_id: str,
    currency: Currency,
    target_price_minor: int,
) -> CanonicalPriceIntent:
    """Build the sole canonical operation supported by PR2."""

    operation = BusinessOperation.SET_PRODUCT_PRICE
    return CanonicalPriceIntent(
        intent_id=_canonical_intent_id(
            operation=operation,
            product_id=product_id,
            currency=currency,
            target_price_minor=target_price_minor,
        ),
        operation=operation,
        product_id=product_id,
        currency=currency,
        target_price_minor=target_price_minor,
    )


class DeterministicBusinessInterpreter:
    """Resolve parsed commands into concrete price intent without authority."""

    def __init__(
        self,
        preset_catalog: Mapping[str, PricingPresetDefinition] = (
            PRICING_PRESET_CATALOG
        ),
    ) -> None:
        if not isinstance(preset_catalog, Mapping):
            raise TypeError("preset_catalog must be a mapping")
        if not all(
            isinstance(value, PricingPresetDefinition)
            and key == value.preset_id
            for key, value in preset_catalog.items()
        ):
            raise ValueError("preset_catalog keys must match preset definitions")
        self._preset_catalog: Mapping[str, PricingPresetDefinition] = (
            MappingProxyType(dict(preset_catalog))
        )

    @property
    def preset_catalog(self) -> Mapping[str, PricingPresetDefinition]:
        """Return the immutable experiment-owned execution catalog."""

        return self._preset_catalog

    def interpret(
        self,
        representation: InputRepresentation,
    ) -> CanonicalPriceIntent:
        """Parse and resolve one input into its concrete business meaning.

        Direct commands carry their concrete price fields. Preset commands
        resolve through the immutable catalog. Neither path reads fixture-level
        expected-intent metadata or derives identity from raw representation.
        """

        _, parsed = _parse_representation(representation)
        if parsed.operation_kind is _ParsedOperationKind.DIRECT_PRICE_CHANGE:
            if parsed.currency is None or parsed.target_price_minor is None:
                raise RuntimeError("direct parser omitted concrete price fields")
            return _build_canonical_intent(
                product_id=parsed.product_id,
                currency=parsed.currency,
                target_price_minor=parsed.target_price_minor,
            )

        if parsed.preset_id is None:
            raise RuntimeError("preset parser omitted reference identity")
        preset = self._preset_catalog.get(parsed.preset_id)
        if preset is None:
            raise UnknownPricingPresetError(
                f"unknown pricing preset: {parsed.preset_id}"
            )
        return _build_canonical_intent(
            product_id=parsed.product_id,
            currency=preset.currency,
            target_price_minor=preset.target_price_minor,
        )


@dataclass(frozen=True)
class CurrentPriceState:
    """Represent current pricing state derived from accepted history."""

    product_id: str
    currency: Currency
    price_minor: int
    revision: int

    def __post_init__(self) -> None:
        _validate_identifier("product_id", self.product_id)
        _validate_currency(self.currency)
        _validate_minor_units("price_minor", self.price_minor)
        _validate_revision("revision", self.revision)


def _candidate_id(
    *,
    product_id: str,
    currency: Currency,
    target_price_minor: int,
    expected_price_revision: int,
) -> str:
    """Derive candidate identity without representation or guardrail fields."""

    return (
        f"candidate:set-price:{product_id}:{currency.value}:"
        f"{target_price_minor}:r{expected_price_revision}"
    )


@dataclass(frozen=True)
class CandidatePriceChange:
    """Represent a technically valid proposal, not an accepted price fact."""

    candidate_id: str
    origin: CandidateOrigin
    product_id: str
    currency: Currency
    expected_price_revision: int
    target_price_minor: int

    def __post_init__(self) -> None:
        if self.origin is not CandidateOrigin.AGENT_INTERPRETER:
            raise ValueError("origin must be AGENT_INTERPRETER")
        _validate_identifier("product_id", self.product_id)
        _validate_currency(self.currency)
        _validate_revision(
            "expected_price_revision",
            self.expected_price_revision,
        )
        _validate_minor_units("target_price_minor", self.target_price_minor)
        expected = _candidate_id(
            product_id=self.product_id,
            currency=self.currency,
            target_price_minor=self.target_price_minor,
            expected_price_revision=self.expected_price_revision,
        )
        if self.candidate_id != expected:
            raise ValueError("candidate_id must derive from canonical fields")


def build_candidate(
    *,
    intent: CanonicalPriceIntent,
    accepted_state: CurrentPriceState,
) -> CandidatePriceChange:
    """Build a candidate from canonical intent and accepted-state revision.

    This operation establishes technical consistency only. It performs no
    authority or semantic-admission check.
    """

    if not isinstance(intent, CanonicalPriceIntent):
        raise TypeError("intent must be CanonicalPriceIntent")
    if not isinstance(accepted_state, CurrentPriceState):
        raise TypeError("accepted_state must be CurrentPriceState")
    if (
        intent.product_id != accepted_state.product_id
        or intent.currency is not accepted_state.currency
    ):
        raise ValueError("intent must target the accepted pricing subject")
    return CandidatePriceChange(
        candidate_id=_candidate_id(
            product_id=intent.product_id,
            currency=intent.currency,
            target_price_minor=intent.target_price_minor,
            expected_price_revision=accepted_state.revision,
        ),
        origin=CandidateOrigin.AGENT_INTERPRETER,
        product_id=intent.product_id,
        currency=intent.currency,
        expected_price_revision=accepted_state.revision,
        target_price_minor=intent.target_price_minor,
    )


@dataclass(frozen=True)
class AcceptedPriceEstablished:
    """Establish the initial accepted price for one product and currency."""

    product_id: str
    currency: Currency
    price_minor: int
    revision: int

    def __post_init__(self) -> None:
        _validate_identifier("product_id", self.product_id)
        _validate_currency(self.currency)
        _validate_minor_units("price_minor", self.price_minor)
        if self.revision != 1:
            raise ValueError("accepted price establishment must have revision 1")


@dataclass(frozen=True)
class AcceptedPriceChanged:
    """Represent one accepted price transition in authoritative history.

    This fact preserves local transition fields but proves no independent
    business authority. PR2 deliberately allows a privileged service to create
    and append it without semantic admission.
    """

    candidate_id: str
    product_id: str
    currency: Currency
    previous_price_minor: int
    target_price_minor: int
    expected_price_revision: int
    revision: int

    def __post_init__(self) -> None:
        _validate_identifier("product_id", self.product_id)
        _validate_currency(self.currency)
        _validate_minor_units("previous_price_minor", self.previous_price_minor)
        _validate_minor_units("target_price_minor", self.target_price_minor)
        _validate_revision(
            "expected_price_revision",
            self.expected_price_revision,
        )
        if self.revision != self.expected_price_revision + 1:
            raise ValueError("accepted price change must advance revision by one")
        expected_candidate_id = _candidate_id(
            product_id=self.product_id,
            currency=self.currency,
            target_price_minor=self.target_price_minor,
            expected_price_revision=self.expected_price_revision,
        )
        if self.candidate_id != expected_candidate_id:
            raise ValueError("accepted fact must preserve candidate identity")


AcceptedPriceFact: TypeAlias = AcceptedPriceEstablished | AcceptedPriceChanged

INITIAL_ACCEPTED_PRICE = AcceptedPriceEstablished(
    product_id="P-100",
    currency=Currency.USD,
    price_minor=1000,
    revision=1,
)


def _fold_all_price_states(
    accepted_facts: tuple[AcceptedPriceFact, ...],
) -> dict[tuple[str, Currency], CurrentPriceState]:
    """Fold and validate every accepted pricing subject in sequence order."""

    states: dict[tuple[str, Currency], CurrentPriceState] = {}
    for fact in accepted_facts:
        if not isinstance(fact, (AcceptedPriceEstablished, AcceptedPriceChanged)):
            raise TypeError("accepted history must contain accepted price facts")
        key = (fact.product_id, fact.currency)
        if isinstance(fact, AcceptedPriceEstablished):
            if key in states:
                raise ValueError("price subject cannot be established twice")
            states[key] = CurrentPriceState(
                product_id=fact.product_id,
                currency=fact.currency,
                price_minor=fact.price_minor,
                revision=fact.revision,
            )
            continue

        current = states.get(key)
        if current is None:
            raise ValueError("price change requires an established price")
        if fact.expected_price_revision != current.revision:
            raise ValueError("price change expected revision is stale")
        if fact.previous_price_minor != current.price_minor:
            raise ValueError("price change previous price mismatches history")
        if fact.revision != current.revision + 1:
            raise ValueError("price change revision is not contiguous")
        states[key] = CurrentPriceState(
            product_id=fact.product_id,
            currency=fact.currency,
            price_minor=fact.target_price_minor,
            revision=fact.revision,
        )
    return states


def fold_accepted_price_history(
    *,
    accepted_facts: tuple[AcceptedPriceFact, ...],
    product_id: str,
    currency: Currency,
) -> CurrentPriceState:
    """Derive current price and revision from authoritative accepted history."""

    if not isinstance(accepted_facts, tuple):
        raise TypeError("accepted_facts must be a tuple")
    _validate_identifier("product_id", product_id)
    _validate_currency(currency)
    states = _fold_all_price_states(accepted_facts)
    state = states.get((product_id, currency))
    if state is None:
        raise LookupError("accepted history has no matching price subject")
    return state


@dataclass(frozen=True)
class AppendResult:
    """Record one accepted-fact append and its history-derived state change."""

    appended_fact: AcceptedPriceFact
    accepted_fact_count_before: int
    accepted_fact_count_after: int
    state_before: CurrentPriceState | None
    state_after: CurrentPriceState

    def __post_init__(self) -> None:
        if self.accepted_fact_count_after != self.accepted_fact_count_before + 1:
            raise ValueError("append must add exactly one accepted fact")
        if self.state_before is not None:
            if self.state_after.revision != self.state_before.revision + 1:
                raise ValueError("append must advance current revision by one")


class AuthoritativePriceStore:
    """Own accepted price history and derive state solely by folding it.

    The store enforces accepted-fact typing and local history continuity. It
    deliberately does not decide pricing authority or evaluate independent
    approval evidence in PR2.
    """

    def __init__(
        self,
        accepted_facts: tuple[AcceptedPriceFact, ...] = (),
    ) -> None:
        if not isinstance(accepted_facts, tuple):
            raise TypeError("accepted_facts must be a tuple")
        _fold_all_price_states(accepted_facts)
        self._accepted_facts: list[AcceptedPriceFact] = list(accepted_facts)

    @property
    def accepted_facts(self) -> tuple[AcceptedPriceFact, ...]:
        """Return an immutable view of authoritative accepted history."""

        return tuple(self._accepted_facts)

    def current_state(
        self,
        *,
        product_id: str,
        currency: Currency,
    ) -> CurrentPriceState:
        """Fold accepted history into current state for one pricing subject."""

        return fold_accepted_price_history(
            accepted_facts=self.accepted_facts,
            product_id=product_id,
            currency=currency,
        )

    def append_accepted_fact(self, *, fact: AcceptedPriceFact) -> AppendResult:
        """Append one accepted-fact type after local history validation.

        Args:
            fact: Accepted pricing fact, never a candidate value.

        Returns:
            The exact appended fact, history counts, and folded states.

        Raises:
            TypeError: If ``fact`` is a candidate or another non-accepted type.
            ValueError: If the fact violates local sequence continuity.

        This API performs no semantic pricing-authority check. That omission is
        required for the vulnerable PR2 counterexample.
        """

        if not isinstance(fact, (AcceptedPriceEstablished, AcceptedPriceChanged)):
            raise TypeError("fact must be an accepted price fact")

        key_product = fact.product_id
        key_currency = fact.currency
        try:
            state_before = self.current_state(
                product_id=key_product,
                currency=key_currency,
            )
        except LookupError:
            state_before = None

        facts_after = (*self.accepted_facts, fact)
        states_after = _fold_all_price_states(facts_after)
        state_after = states_after[(key_product, key_currency)]
        count_before = len(self._accepted_facts)
        self._accepted_facts.append(fact)
        return AppendResult(
            appended_fact=fact,
            accepted_fact_count_before=count_before,
            accepted_fact_count_after=len(self._accepted_facts),
            state_before=state_before,
            state_after=state_after,
        )


def build_initial_price_store() -> AuthoritativePriceStore:
    """Return a fresh store with the contract-defined initial accepted fact."""

    return AuthoritativePriceStore(accepted_facts=(INITIAL_ACCEPTED_PRICE,))


@dataclass(frozen=True)
class VulnerablePromotionResult:
    """Record unchecked candidate promotion and the resulting accepted append."""

    candidate: CandidatePriceChange
    accepted_fact: AcceptedPriceChanged
    append_result: AppendResult

    def __post_init__(self) -> None:
        if self.accepted_fact.candidate_id != self.candidate.candidate_id:
            raise ValueError("promotion must preserve candidate identity")
        if self.append_result.appended_fact != self.accepted_fact:
            raise ValueError("append result must preserve the promoted fact")


class VulnerablePriceMutationService:
    """Exercise privileged append without mutation-time semantic admission.

    The service accepts only a technically valid candidate and current accepted
    history. It receives no guardrail result, preset definition, approval
    evidence, or admission decision. Its deliberate vulnerability is treating
    technical candidate validity and current-state continuity as sufficient to
    construct and append an accepted business fact.
    """

    def __init__(self, store: AuthoritativePriceStore) -> None:
        if not isinstance(store, AuthoritativePriceStore):
            raise TypeError("store must be AuthoritativePriceStore")
        self._store = store

    def promote_without_semantic_admission(
        self,
        *,
        candidate: CandidatePriceChange,
    ) -> VulnerablePromotionResult:
        """Promote a technically valid candidate without authority evaluation.

        Args:
            candidate: Concrete candidate prepared by business interpretation.

        Returns:
            The accepted price fact and append result produced unchecked.

        Raises:
            TypeError: If the value is not a price-change candidate.
            ValueError: If its expected revision is stale.
        """

        if not isinstance(candidate, CandidatePriceChange):
            raise TypeError("candidate must be CandidatePriceChange")
        current = self._store.current_state(
            product_id=candidate.product_id,
            currency=candidate.currency,
        )
        if candidate.expected_price_revision != current.revision:
            raise ValueError("candidate expected revision is stale")

        accepted_fact = AcceptedPriceChanged(
            candidate_id=candidate.candidate_id,
            product_id=candidate.product_id,
            currency=candidate.currency,
            previous_price_minor=current.price_minor,
            target_price_minor=candidate.target_price_minor,
            expected_price_revision=candidate.expected_price_revision,
            revision=current.revision + 1,
        )
        append_result = self._store.append_accepted_fact(fact=accepted_fact)
        return VulnerablePromotionResult(
            candidate=candidate,
            accepted_fact=accepted_fact,
            append_result=append_result,
        )


@dataclass(frozen=True)
class VulnerableExecutionResult:
    """Preserve every reached boundary in one PR2 runtime execution."""

    representation: InputRepresentation
    guardrail_result: GuardrailResult
    canonical_intent: CanonicalPriceIntent | None
    candidate: CandidatePriceChange | None
    promotion: VulnerablePromotionResult | None

    def __post_init__(self) -> None:
        allowed = (
            self.guardrail_result.decision
            is GuardrailDecision.ALLOW_PROCESSING
        )
        downstream_complete = (
            self.canonical_intent is not None
            and self.candidate is not None
            and self.promotion is not None
        )
        if allowed != downstream_complete:
            raise ValueError(
                "only ALLOW_PROCESSING may reach interpretation and mutation"
            )
        if self.guardrail_result.representation_id != (
            self.representation.representation_id
        ):
            raise ValueError("result must preserve representation identity")
        if self.promotion is not None and self.promotion.candidate != self.candidate:
            raise ValueError("promotion must preserve the exact candidate")


class VulnerablePricingWorkflow:
    """Run the PR2 guardrail, interpretation, candidate, and unchecked append.

    A `BLOCK` result terminates before business interpretation. An
    `ALLOW_PROCESSING` result permits the interpreter to prepare a candidate,
    but does not authorize it. PR2 deliberately passes that candidate to the
    vulnerable privileged service with no mutation-time semantic admission.
    """

    def __init__(self, store: AuthoritativePriceStore) -> None:
        if not isinstance(store, AuthoritativePriceStore):
            raise TypeError("store must be AuthoritativePriceStore")
        self._store = store
        self._guardrail = DeterministicInputGuardrail()
        self._interpreter = DeterministicBusinessInterpreter()
        self._mutation_service = VulnerablePriceMutationService(store)

    def execute(
        self,
        *,
        representation: InputRepresentation,
    ) -> VulnerableExecutionResult:
        """Execute one input through the deliberately vulnerable PR2 path."""

        guardrail_result = self._guardrail.evaluate(representation)
        if guardrail_result.decision is GuardrailDecision.BLOCK:
            return VulnerableExecutionResult(
                representation=representation,
                guardrail_result=guardrail_result,
                canonical_intent=None,
                candidate=None,
                promotion=None,
            )

        intent = self._interpreter.interpret(representation)
        accepted_state = self._store.current_state(
            product_id=intent.product_id,
            currency=intent.currency,
        )
        candidate = build_candidate(
            intent=intent,
            accepted_state=accepted_state,
        )
        promotion = self._mutation_service.promote_without_semantic_admission(
            candidate=candidate,
        )
        return VulnerableExecutionResult(
            representation=representation,
            guardrail_result=guardrail_result,
            canonical_intent=intent,
            candidate=candidate,
            promotion=promotion,
        )


__all__ = (
    "AbstractionLevel",
    "AcceptedPriceChanged",
    "AcceptedPriceEstablished",
    "AnalysisStatus",
    "AnalyzerId",
    "AppendResult",
    "BLOCK_CONCRETE_PRICE_MUTATION_RULE_ID",
    "BusinessOperation",
    "COMPLIMENTARY_LAUNCH_PRESET",
    "CandidateOrigin",
    "CandidatePriceChange",
    "CanonicalPriceIntent",
    "CoverageStatus",
    "Currency",
    "CurrentPriceState",
    "DeterministicBusinessInterpreter",
    "DeterministicInputGuardrail",
    "EN_DIRECT",
    "EN_PRESET",
    "GUARDRAIL_PROFILE_ID",
    "GuardrailDecision",
    "GuardrailDecisionReason",
    "GuardrailResult",
    "INITIAL_ACCEPTED_PRICE",
    "InputRepresentation",
    "InputRiskPolicyResult",
    "JA_DIRECT",
    "JA_PRESET",
    "JSON_DIRECT",
    "JSON_PRESET",
    "OperationClass",
    "PRICING_PRESET_CATALOG",
    "PricingPresetDefinition",
    "ReferenceType",
    "RepresentationFamily",
    "RepresentationParseError",
    "SAFETY_SCHEMA_VERSION",
    "SafetyDomain",
    "SafetySemanticFrame",
    "SpeechAct",
    "TargetType",
    "UnknownPricingPresetError",
    "V1_REPRESENTATIONS",
    "V1_REPRESENTATIONS_BY_ID",
    "VulnerableExecutionResult",
    "VulnerablePriceMutationService",
    "VulnerablePricingWorkflow",
    "VulnerablePromotionResult",
    "ZH_DIRECT",
    "ZH_PRESET",
    "build_candidate",
    "build_initial_price_store",
    "decide_input_risk",
    "fold_accepted_price_history",
)
