from __future__ import annotations

import math


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

    exponent = _exponent_from_prefix(token)
    mantissa = token[2:]
    first = ord(mantissa[0])
    if 48 <= first <= 63:
        sign = 1.0
        first_digit = first - 48
    elif 80 <= first <= 95:
        sign = -1.0
        first_digit = first - 80
    else:
        raise ValueError(f"Unsupported DDC number sign/mantissa digit in token: {token!r}")

    fraction = first_digit / 16.0
    denominator = 16.0
    for char in mantissa[1:]:
        digit = ord(char) - 48
        if digit < 0 or digit >= 64:
            raise ValueError(f"Unsupported DDC number continuation digit in token: {token!r}")
        denominator *= 64.0
        fraction += digit / denominator

    return sign * (2.0**exponent) * (1.0 + fraction)


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
    if math.isclose(absolute, 2.0 ** (exponent + 1), rel_tol=0.0, abs_tol=1e-9):
        exponent += 1
    if exponent <= 0:
        prefix = chr(ord("o") + exponent) + "?"
    else:
        prefix = chr(ord("0") + exponent - 1) + "@"

    normalized = absolute / (2.0**exponent)
    fraction = normalized - 1.0
    scaled = fraction * 16.0
    first_digit = int(math.floor(scaled + 1e-12))
    if first_digit >= 16:
        exponent += 1
        if exponent <= 0:
            prefix = chr(ord("o") + exponent) + "?"
        else:
            prefix = chr(ord("0") + exponent - 1) + "@"
        first_digit = 0
        remainder = 0.0
    else:
        first_digit = max(0, first_digit)
        remainder = scaled - first_digit
    first_char = chr((80 if sign < 0 else 48) + first_digit)

    digits: list[str] = []
    for _ in range(max(0, int(continuation_digits))):
        remainder *= 64.0
        digit = int(math.floor(remainder + 1e-12))
        digit = max(0, min(63, digit))
        digits.append(chr(48 + digit))
        remainder -= digit

    while digits and digits[-1] == "0":
        digits.pop()

    return prefix + first_char + "".join(digits)
