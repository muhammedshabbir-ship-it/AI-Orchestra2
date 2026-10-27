"""Money helpers. All amounts are stored as integer cents (AUD) to avoid float errors."""
import re
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP


def to_cents(value) -> int:
    """Convert '1,234.56' / 1234.56 / Decimal to integer cents. Raises ValueError if invalid."""
    try:
        d = Decimal(re.sub(r"(?i)aud|a\$|[\$,\s_]", "", str(value)))
    except (InvalidOperation, AttributeError):
        raise ValueError(f"Invalid amount: {value!r}")
    if not d.is_finite():
        raise ValueError("Invalid amount")
    return int((d * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def fmt(cents: int, cur: str = "AUD") -> str:
    sign = "-" if cents < 0 else ""
    c = abs(int(cents))
    return f"{sign}{cur} {c // 100:,}.{c % 100:02d}"
