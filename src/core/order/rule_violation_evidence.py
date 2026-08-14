"""Order-semantic rule-violation evidence independent of any producer.

The record in this module identifies which stable Order correctness rule was
observed as violated for which candidate. It does not know which validation
system produced the observation and does not select runtime action, policy,
retry, repair, recovery, or admission fate.
"""

from dataclasses import dataclass

from .correctness_contract import (
    ORDER_CORRECTNESS_CONTRACT_V0,
    OrderCorrectnessRuleId,
)


@dataclass(frozen=True)
class OrderRuleViolationEvidence:
    """Identify one observed stable Order rule violation for one candidate.

    Args:
        contract_id: Canonical Order correctness contract identity.
        contract_version: Canonical Order correctness contract edition.
        rule_id: Stable Order correctness identity reported by a producer.
        candidate_event_id: Identity of the candidate that was evaluated.

    The candidate identity is a same-process correlation coordinate. It is not
    proof of admission or accepted-history membership. This record expresses
    neither completeness nor priority among possible violations.

    Raises:
        TypeError: If version or rule identity has the wrong type.
        ValueError: If contract identity/version is not the supported V0 edition
            or candidate identity is empty.
    """

    contract_id: str
    contract_version: int
    rule_id: OrderCorrectnessRuleId
    candidate_event_id: str

    def __post_init__(self) -> None:
        if self.contract_id != ORDER_CORRECTNESS_CONTRACT_V0.contract_id:
            raise ValueError(
                "contract_id must identify the supported Order V0 contract"
            )
        if type(self.contract_version) is not int:
            raise TypeError("contract_version must be int")
        if (
            self.contract_version
            != ORDER_CORRECTNESS_CONTRACT_V0.contract_version
        ):
            raise ValueError(
                "contract_version must identify the supported Order V0 contract"
            )
        if not isinstance(self.rule_id, OrderCorrectnessRuleId):
            raise TypeError("rule_id must be OrderCorrectnessRuleId")
        _require_non_empty_string(
            self.candidate_event_id,
            "candidate_event_id",
        )


def _require_non_empty_string(value: object, field_name: str) -> None:
    """Reject non-string and whitespace-only identity values."""

    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")


__all__ = ("OrderRuleViolationEvidence",)
