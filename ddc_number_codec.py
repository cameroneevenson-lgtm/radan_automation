from __future__ import annotations

import math
from fractions import Fraction


def _exponent_from_prefix(token: str) -> int:
    if len(token) < 3:
        raise ValueError(f"DDC number token is too short: {token!r}")
    head, marker = token[0], token[1]
    if marker == "?":
        return ord(head) - ord("o")
    if marker == "@":
        return ord(head) - ord("0") + 1
    raise ValueError(f"Unsupported DDC number exponent marker in token: {token!r}")


def decode_ddc_number(token: str) -> float:
    """Decode a RADAN DDC compact numeric token.

    Empty tokens are the DDC zero/default representation in geometry slots.
    The non-empty format observed in RADAN 2025 symbols is:

    - 2-character exponent prefix
    - first mantissa digit with sign folded into the character range
    - optional base-64 mantissa continuation digits
    """

    if token == "":
        return 0.0

    return float(decode_ddc_number_fraction(token))


def decode_ddc_number_fraction(token: str) -> Fraction:
    """Decode a RADAN DDC compact numeric token as an exact rational value."""

    if token == "":
        return Fraction(0, 1)

    exponent = _exponent_from_prefix(token)
    mantissa = token[2:]
    first = ord(mantissa[0])
    if 48 <= first <= 63:
        sign = 1
        first_digit = first - 48
    elif 80 <= first <= 95:
        sign = -1
        first_digit = first - 80
    else:
        raise ValueError(f"Unsupported DDC number sign/mantissa digit in token: {token!r}")

    fraction = Fraction(first_digit, 16)
    denominator = 16
    for char in mantissa[1:]:
        digit = ord(char) - 48
        if digit < 0 or digit >= 64:
            raise ValueError(f"Unsupported DDC number continuation digit in token: {token!r}")
        denominator *= 64
        fraction += Fraction(digit, denominator)

    return Fraction(sign, 1) * (Fraction(2, 1) ** exponent) * (1 + fraction)


def _prefix_from_exponent(exponent: int) -> str:
    if exponent <= 0:
        return chr(ord("o") + exponent) + "?"
    return chr(ord("0") + exponent - 1) + "@"


def _fraction_floor_log2(value: Fraction) -> int:
    numerator_bits = value.numerator.bit_length()
    denominator_bits = value.denominator.bit_length()
    exponent = numerator_bits - denominator_bits
    if value < Fraction(2, 1) ** exponent:
        exponent -= 1
    return exponent


def encode_ddc_number_fraction(
    value: Fraction,
    *,
    continuation_digits: int = 8,
    min_continuation_digits: int = 0,
) -> str:
    """Encode an exact rational into the observed DDC compact numeric shape."""

    value = Fraction(value)
    if value == 0:
        return ""

    sign = -1 if value < 0 else 1
    absolute = abs(value)
    exponent = _fraction_floor_log2(absolute)
    prefix = _prefix_from_exponent(exponent)

    normalized = absolute / (Fraction(2, 1) ** exponent)
    fraction = normalized - 1
    scaled = fraction * 16
    first_digit = scaled.numerator // scaled.denominator
    if first_digit >= 16:
        exponent += 1
        prefix = _prefix_from_exponent(exponent)
        first_digit = 0
        remainder = Fraction(0, 1)
    else:
        first_digit = max(0, first_digit)
        remainder = scaled - first_digit
    first_char = chr((80 if sign < 0 else 48) + first_digit)
    min_continuation_digits = max(0, min(int(min_continuation_digits), int(continuation_digits)))
    if remainder == 0 and min_continuation_digits == 0:
        return prefix + first_char

    digits: list[str] = []
    for _ in range(max(0, int(continuation_digits))):
        remainder *= 64
        digit = remainder.numerator // remainder.denominator
        digit = max(0, min(63, digit))
        digits.append(chr(48 + digit))
        remainder -= digit
        if remainder == 0 and len(digits) >= min_continuation_digits:
            break

    while len(digits) < min_continuation_digits:
        digits.append("0")

    while len(digits) > min_continuation_digits and digits[-1] == "0":
        digits.pop()

    return prefix + first_char + "".join(digits)


def encode_ddc_number(value: float, *, continuation_digits: int = 8) -> str:
    """Encode a number using the observed DDC compact numeric shape.

    This is suitable for lab round-trips and simple dyadic values. RADAN may
    choose slightly different final continuation digits for arbitrary decimal
    inputs that decode to the same 6-decimal geometry value.
    """

    value = float(value)
    if value == 0.0:
        return ""

    sign = -1 if value < 0 else 1
    absolute = abs(value)
    exponent = math.floor(math.log(absolute, 2))
    if absolute >= 2.0 ** (exponent + 1):
        exponent += 1
    prefix = _prefix_from_exponent(exponent)

    normalized = absolute / (2.0**exponent)
    fraction = normalized - 1.0
    scaled = fraction * 16.0
    first_digit = int(math.floor(scaled))
    if first_digit >= 16:
        exponent += 1
        prefix = _prefix_from_exponent(exponent)
        first_digit = 0
        remainder = 0.0
    else:
        first_digit = max(0, first_digit)
        remainder = scaled - first_digit
    first_char = chr((80 if sign < 0 else 48) + first_digit)

    digits: list[str] = []
    for _ in range(max(0, int(continuation_digits))):
        remainder *= 64.0
        digit = int(math.floor(remainder))
        digit = max(0, min(63, digit))
        digits.append(chr(48 + digit))
        remainder -= digit

    while digits and digits[-1] == "0":
        digits.pop()

    return prefix + first_char + "".join(digits)
