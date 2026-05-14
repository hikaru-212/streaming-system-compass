from decimal import Decimal

import pytest

from src.core.common.money import (
    MONEY_QUANT,
    MoneyValidationError,
    ensure_positive_money,
    money_to_storage_string,
    normalize_money,
    parse_money,
)


class TestParseMoney:
    def test_parse_money_accepts_decimal(self):
        result = parse_money(Decimal("100.00"))

        assert result == Decimal("100.00")

    def test_parse_money_accepts_int(self):
        result = parse_money(100)

        assert result == Decimal("100")

    def test_parse_money_accepts_string(self):
        result = parse_money("100.00")

        assert result == Decimal("100.00")

    def test_parse_money_accepts_string_with_spaces(self):
        result = parse_money("  100.00  ")

        assert result == Decimal("100.00")

    def test_parse_money_rejects_float(self):
        with pytest.raises(
            MoneyValidationError,
            match="float is not allowed for money input; use Decimal, str, or int",
        ):
            parse_money(100.0)

    @pytest.mark.parametrize("bad_value", ["abc", "12.3.4", "1,000"])
    def test_parse_money_rejects_malformed_string(self, bad_value):
        with pytest.raises(MoneyValidationError, match="invalid money input"):
            parse_money(bad_value)

    def test_parse_money_rejects_nan(self):
        with pytest.raises(
            MoneyValidationError,
            match="NaN is not a valid money value",
        ):
            parse_money("NaN")

    def test_parse_money_rejects_infinity(self):
        with pytest.raises(
            MoneyValidationError,
            match="Infinity is not a valid money value",
        ):
            parse_money("Infinity")

    def test_parse_money_rejects_unsupported_type(self):
        with pytest.raises(
            MoneyValidationError,
            match="unsupported type for money input: list",
        ):
            parse_money(["100.00"])


class TestNormalizeMoney:
    def test_normalize_money_keeps_two_decimal_value(self):
        result = normalize_money("100.00")

        assert result == Decimal("100.00")

    def test_normalize_money_normalizes_integer_to_two_decimals(self):
        result = normalize_money("100")

        assert result == Decimal("100.00")

    def test_normalize_money_normalizes_single_decimal_place(self):
        result = normalize_money("100.0")

        assert result == Decimal("100.00")

    def test_normalize_money_uses_round_half_even_for_half_case(self):
        # 10.005 -> 10.00 under ROUND_HALF_EVEN
        result = normalize_money("10.005")

        assert result == Decimal("10.00")

    def test_normalize_money_uses_round_half_even_for_upper_half_case(self):
        # 10.015 -> 10.02 under ROUND_HALF_EVEN
        result = normalize_money("10.015")

        assert result == Decimal("10.02")

    def test_money_quant_constant_is_two_decimal_places(self):
        assert MONEY_QUANT == Decimal("0.01")


class TestEnsurePositiveMoney:
    def test_ensure_positive_money_accepts_positive_value(self):
        result = ensure_positive_money("100.00")

        assert result == Decimal("100.00")

    @pytest.mark.parametrize("bad_value", ["0", "0.00", "-1", "-1.00", "-100.55"])
    def test_ensure_positive_money_rejects_zero_and_negative_values(self, bad_value):
        with pytest.raises(MoneyValidationError, match="money amount must be positive"):
            ensure_positive_money(bad_value)


class TestMoneyToStorageString:
    def test_money_to_storage_string_returns_canonical_string_for_integer(self):
        result = money_to_storage_string("100")

        assert result == "100.00"

    def test_money_to_storage_string_returns_canonical_string_for_one_decimal_place(self):
        result = money_to_storage_string("100.0")

        assert result == "100.00"

    def test_money_to_storage_string_returns_canonical_string_for_decimal_input(self):
        result = money_to_storage_string(Decimal("100.00"))

        assert result == "100.00"

    def test_money_to_storage_string_stabilizes_equivalent_inputs(self):
        assert money_to_storage_string("100") == "100.00"
        assert money_to_storage_string("100.0") == "100.00"
        assert money_to_storage_string(Decimal("100.00")) == "100.00"

    def test_money_to_storage_string_rounds_using_current_v1_rule(self):
        result = money_to_storage_string("10.015")

        assert result == "10.02"