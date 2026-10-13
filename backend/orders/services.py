"""FRD-driven milestone helpers for the Order (shipment) lifecycle."""
from .models import HAPPY_PATH_ORDER


def next_happy_status(current):
    if current not in HAPPY_PATH_ORDER:
        return None
    idx = HAPPY_PATH_ORDER.index(current)
    if idx + 1 < len(HAPPY_PATH_ORDER):
        return HAPPY_PATH_ORDER[idx + 1]
    return None
