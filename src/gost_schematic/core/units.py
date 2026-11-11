"""Engine uses integral micrometres; user-facing lengths are in millimetres."""
from decimal import Decimal, InvalidOperation


def mm(value: str | int | float | Decimal) -> int:
    """Convert millimetres to an EXACT integral number of micrometres."""
    if isinstance(value, bool):
        raise ValueError("A boolean is not a length")
    try:
        millimetres = Decimal(str(value))
    except InvalidOperation as error:
        raise ValueError(f"Invalid millimetre value: {value!r}") from error
    if not millimetres.is_finite():
        raise ValueError("Length must be finite")
    micrometres = millimetres * 1000
    if micrometres != micrometres.to_integral_value():
        raise ValueError("Length cannot be represented as integral micrometres")
    return int(micrometres)


def format_mm(micrometres: int) -> str:
    """Stable human-readable decimal millimetres without float rounding."""
    if type(micrometres) is not int:
        raise TypeError("Internal length must be an integer")
    return format(Decimal(micrometres) / 1000, "f")
