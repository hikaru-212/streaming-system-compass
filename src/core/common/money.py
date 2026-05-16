"""
Money utilities for exact decimal handling in the current v1 domain.

Purpose:
- prevent float-based money ambiguity
- enforce canonical money normalization
- provide stable durable/string forms for payloads and semantic fingerprints

This module is introduced as part of Stage 3.5A after ADR 0006.

Boundary:
- this module is responsible only for exact money parsing, normalization,
  validation, and durable string conversion
- it does not define business policy
- it does not define trust verdicts
- it does not define governance actions
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_HALF_EVEN
from typing import Union

MoneyInput = Union[str, int, Decimal]

# Current v1 money precision baseline: 2 decimal places.
MONEY_QUANT = Decimal("0.01")

class MoneyValidationError(ValueError):
    """Raised when a money input cannot be accepted as valid domain value."""


def parse_money(value: MoneyInput) -> Decimal:
    """
    Parse external/domain input into Decimal without allowing float-based ambiguity.

    Accepted:
    - str
    - int
    - Decimal

    Rejected:
    - float
    - NaN
    - Infinity
    - malformed numeric strings
    """
    if isinstance(value, float):
        raise MoneyValidationError(
            "float is not allowed for money input; use Decimal, str, or int"
        )
    
    
    if isinstance(value, Decimal):
        result = value
    elif isinstance(value, int):
        result = Decimal(value)
    elif isinstance(value, str):
        try:
            result = Decimal(value.strip())
        except (InvalidOperation, ValueError) as exc:
            raise MoneyValidationError(f"invalid money input: {value!r}") from exc
    else:
        raise MoneyValidationError(
            f"unsupported type for money input: {type(value).__name__}"
        )

    
    if result.is_nan():
        raise MoneyValidationError("NaN is not a valid money value")
    
    if result.is_infinite():
        raise MoneyValidationError("Infinity is not a valid money value")
    
    return result


def normalize_money(value: MoneyInput) -> Decimal:
    """
    Convert input into canonical Decimal form for current v1 domain semantics.

    Current baseline:
    - 2 decimal places
    - banker's rounding (ROUND_HALF_EVEN)
    """
    amount = parse_money(value)
    return amount.quantize(MONEY_QUANT, rounding=ROUND_HALF_EVEN)


def ensure_positive_money(value: MoneyInput) -> Decimal:
    """
    Parse + normalize + enforce positive-money rule.
    """
    amount = normalize_money(value)

    if amount <= Decimal("0.00"):
        raise MoneyValidationError("money amount must be positive")
    
    return amount


def money_to_storage_string(value: MoneyInput) -> str:
    """
    Convert money into stable durable/string form.

    Use this for:
    - JSON payloads
    - semantic fingerprint basis
    """
    return format(normalize_money(value), "f")