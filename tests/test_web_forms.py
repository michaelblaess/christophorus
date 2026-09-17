"""Das Bearbeitungsformular der Web-Oberflaeche: Pruefung und Uebersetzung in eine Fahrt."""

from __future__ import annotations

import pytest

from christo.models.trip import Trip, set_business_categories, set_informational_categories
from christo.web.forms import form_from_trip, read_form, trip_from_form

KATEGORIEN = {"business", "private", "fuel", "fuel_private", "service", "delivery", "return"}


@pytest.fixture(autouse=True)
def _kategorien() -> None:
    set_business_categories({"business", "fuel", "service"})
    set_informational_categories({"delivery", "return"})


def _eingabe(**abweichungen: str) -> dict[str, str]:
    daten = {
        "datum": "16.05.2026",
        "abfahrt": "08:00",
        "ankunft": "18:00",
        "ziel": "Kunde Nord, Musterstadt",
        "zweck": "Messeaufbau",
        "kategorie": "business",
        "km_anfang": "17.977",
        "km_geschaeftlich": "84",
        "km_privat": "0",
        "hin_und_zurueck": "",
        "tankliter": "",
        "volltank": "",
    }
    daten.update(abweichungen)
    return daten


def test_valid_input_becomes_a_trip() -> None:
    form = read_form(_eingabe(), KATEGORIEN)
    assert form.valid, form.errors
    fahrt = trip_from_form(form, trip_id=7)
    assert (fahrt.id, fahrt.date, fahrt.km_start, fahrt.km_end) == (7, "2026-05-16", 17977, 18061)
    assert (fahrt.km_business, fahrt.km_private, fahrt.category) == (84, 0, "business")


def test_km_end_follows_the_columns() -> None:
    fahrt = trip_from_form(read_form(_eingabe(km_geschaeftlich="50", km_privat="34"), KATEGORIEN), 1)
    assert fahrt.km_end == 18061


def test_core_rules_apply() -> None:
    fahrt = trip_from_form(read_form(_eingabe(km_geschaeftlich="0", km_privat="84"), KATEGORIEN), 1)
    assert fahrt.category == "private"


@pytest.mark.parametrize(
    ("abweichung", "feld"),
    [
        ({"datum": ""}, "datum"),
        ({"datum": "16.5.2026"}, "datum"),
        ({"datum": "31.02.2026"}, "datum"),
        ({"abfahrt": "8 Uhr"}, "abfahrt"),
        ({"ankunft": "07:00"}, "ankunft"),
        ({"kategorie": "gibt-es-nicht"}, "kategorie"),
        ({"km_geschaeftlich": "achtzig"}, "km_geschaeftlich"),
        ({"km_geschaeftlich": "0", "km_privat": "0"}, "km_geschaeftlich"),
        ({"tankliter": "voll", "kategorie": "fuel"}, "tankliter"),
    ],
)
def test_invalid_input_names_the_field(abweichung: dict[str, str], feld: str) -> None:
    form = read_form(_eingabe(**abweichung), KATEGORIEN)
    assert feld in form.errors, form.errors
    assert form.errors[feld]
    with pytest.raises(ValueError):
        trip_from_form(form, 1)


def test_informational_trip_needs_no_km() -> None:
    form = read_form(_eingabe(kategorie="delivery", km_geschaeftlich="0", km_privat="0"), KATEGORIEN)
    assert form.valid, form.errors
    fahrt = trip_from_form(form, 1)
    assert (fahrt.km_end, fahrt.destination) == (0, "")


def test_fuel_fields_only_for_fuel() -> None:
    fahrt = trip_from_form(read_form(_eingabe(tankliter="42,5"), KATEGORIEN), 1)
    assert fahrt.fuel_liters == 0.0
    getankt = trip_from_form(read_form(_eingabe(kategorie="fuel", tankliter="42,5", volltank="1"), KATEGORIEN), 1)
    assert (getankt.fuel_liters, getankt.fuel_full_tank) == (42.5, True)


def test_form_from_trip_shows_german_formats() -> None:
    form = form_from_trip(Trip(id=1, date="2026-05-16", km_start=17977, km_business=84, fuel_liters=42.5))
    assert form.values["datum"] == "16.05.2026"
    assert form.values["km_anfang"] == "17.977"
    assert form.values["tankliter"] == "42,5"
