"""Regeln, die beim Speichern einer Fahrt gelten - unabhaengig von der Oberflaeche.

Stammen aus `TripScreen.action_save` (Stand v1.3.1) und gelten fuer TUI und Web gleich.
"""

from dataclasses import replace

from christo.models.trip import Trip, get_business_categories, get_informational_categories

FUEL_CATEGORIES = ("fuel", "fuel_private")


def normalize_trip(trip: Trip) -> Trip:
    """Bringt eine eingegebene Fahrt in die gespeicherte Form.

    - Informationelle Kategorien (Anlieferung, Rueckgabe) tragen keine km, kein Ziel,
      keinen Zweck und keine Hin- und Rueckfahrt.
    - Stehen die km in genau einer Spalte, die nicht zur Kategorie passt, gleicht sich die
      Kategorie an, nicht die km. Sonst liesse sich "km auf privat umbuchen" nie speichern.
    - Tankfelder zaehlen nur bei Tankfahrten.

    Args:
        trip: Die Fahrt, wie sie eingegeben wurde.

    Returns:
        Eine neue Fahrt, die Eingabe bleibt unveraendert.
    """
    category = trip.category
    if category in get_informational_categories():
        normalized = replace(
            trip,
            km_start=0,
            km_end=0,
            km_business=0,
            km_private=0,
            destination="",
            purpose="",
            round_trip=False,
        )
    else:
        if trip.km_private > 0 and trip.km_business == 0 and category in get_business_categories():
            category = "fuel_private" if category == "fuel" else "private"
        elif trip.km_business > 0 and trip.km_private == 0 and category not in get_business_categories():
            category = "fuel" if category == "fuel_private" else "business"
        normalized = replace(
            trip,
            category=category,
            destination=trip.destination.strip(),
            purpose=trip.purpose.strip(),
        )

    if normalized.category not in FUEL_CATEGORIES:
        normalized = replace(normalized, fuel_liters=0.0, fuel_full_tank=False)
    return normalized


def km_end_from_columns(km_start: int, km_business: int, km_private: int) -> int:
    """Endstand aus Startstand und den beiden km-Spalten, wie die TUI-Maske ihn fortschreibt."""
    return km_start + max(0, km_business) + max(0, km_private)
