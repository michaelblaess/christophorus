"""Speicherregeln fuer Fahrten im Kern (gemeinsam fuer TUI und Web)."""

from __future__ import annotations

import pytest

from christo.models.trip import Trip, set_business_categories, set_informational_categories
from christo.services.formatting import de_to_iso, format_liters, iso_to_de, parse_liters
from christo.services.trip_rules import km_end_from_columns, normalize_trip


@pytest.fixture(autouse=True)
def _kategorien() -> None:
    set_business_categories({"business", "fuel", "service"})
    set_informational_categories({"delivery", "return"})


def _fahrt(**werte: object) -> Trip:
    basis: dict[str, object] = {
        "date": "2026-05-16",
        "destination": "  Kunde Nord  ",
        "purpose": " Messeaufbau ",
        "km_start": 17977,
        "km_end": 18061,
        "km_business": 84,
        "category": "business",
    }
    basis.update(werte)
    return Trip(**basis)  # type: ignore[arg-type]


def test_business_trip_stays_and_text_is_trimmed() -> None:
    fahrt = normalize_trip(_fahrt())
    assert fahrt.category == "business"
    assert (fahrt.destination, fahrt.purpose) == ("Kunde Nord", "Messeaufbau")


def test_informational_trip_is_zeroed() -> None:
    fahrt = normalize_trip(_fahrt(category="delivery", round_trip=True))
    assert (fahrt.km_start, fahrt.km_end, fahrt.km_business, fahrt.km_private) == (0, 0, 0, 0)
    assert (fahrt.destination, fahrt.purpose, fahrt.round_trip) == ("", "", False)


def test_private_km_move_category_to_private() -> None:
    fahrt = normalize_trip(_fahrt(km_business=0, km_private=84))
    assert fahrt.category == "private"


def test_private_km_on_fuel_become_fuel_private() -> None:
    fahrt = normalize_trip(_fahrt(category="fuel", km_business=0, km_private=3, fuel_liters=40.0))
    assert fahrt.category == "fuel_private"
    assert fahrt.fuel_liters == 40.0


def test_business_km_move_private_category_to_business() -> None:
    assert normalize_trip(_fahrt(category="private")).category == "business"
    assert normalize_trip(_fahrt(category="fuel_private")).category == "fuel"


def test_split_km_keep_category() -> None:
    assert normalize_trip(_fahrt(km_business=50, km_private=34)).category == "business"


def test_fuel_fields_only_on_fuel_trips() -> None:
    fahrt = normalize_trip(_fahrt(fuel_liters=40.0, fuel_full_tank=True))
    assert (fahrt.fuel_liters, fahrt.fuel_full_tank) == (0.0, False)


def test_input_is_not_modified() -> None:
    eingabe = _fahrt(category="delivery")
    normalize_trip(eingabe)
    assert eingabe.km_business == 84


def test_km_end_from_columns() -> None:
    assert km_end_from_columns(17977, 84, 0) == 18061
    assert km_end_from_columns(17977, -5, 10) == 17987


@pytest.mark.parametrize(("iso", "de"), [("2026-05-16", "16.05.2026"), ("", ""), ("kaputt", "kaputt")])
def test_date_round_trip(iso: str, de: str) -> None:
    assert iso_to_de(iso) == de
    assert de_to_iso(de) == iso


def test_liters() -> None:
    assert format_liters(40.0) == "40"
    assert format_liters(40.25) == "40,25"
    assert format_liters(0) == ""
    assert parse_liters("40,25") == 40.25
    assert parse_liters("abc") == 0.0
