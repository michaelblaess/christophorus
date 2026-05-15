"""Tests fuer die informationellen Kategorien (Anlieferung/Rueckgabe).

Deckt drei Schichten ab:
- Seed + Flag: die DB-Migration legt die Kategorien mit is_informational=1 an
- km-Kette: informationelle Trips tragen keine km, werden beim
  Vorgaenger-Lookup uebersprungen und verschieben keine Nachfolger
- Plausi-Checks: informationelle Trips werden von allen Checks ignoriert
"""

from __future__ import annotations

from death_proof.models.trip import Trip, get_informational_categories
from death_proof.services.database import Database
from death_proof.services.plausibility import (
    check_chain_ascending,
    check_distance_matches_columns,
    check_empty_trips,
    run_all_checks,
)
from tests.conftest import make_trip


def _make_info_trip(date_iso: str, category: str) -> Trip:
    """Erzeugt einen informationellen Trip (keine km, kein Ziel)."""
    return Trip(
        date=date_iso,
        destination="",
        purpose="",
        km_start=0,
        km_end=0,
        km_business=0,
        km_private=0,
        category=category,
    )


class TestSeedInformationalCategories:
    def test_default_categories_seeded(self, database: Database) -> None:
        names = database.get_informational_category_names()
        assert "delivery" in names
        assert "return" in names

    def test_flag_not_set_on_business(self, database: Database) -> None:
        names = database.get_informational_category_names()
        assert "business" not in names
        assert "fuel" not in names
        assert "service" not in names

    def test_default_matches_module_set(self, database: Database) -> None:
        # Fallback-Default im trip-Modell darf nicht divergieren
        assert get_informational_categories() == {"delivery", "return"}


class TestAddTripInformational:
    def test_add_stores_zero_km(self, database: Database) -> None:
        trip_id = database.add_trip(_make_info_trip("2024-12-20", "delivery"))
        stored = database.get_trip_by_id(trip_id)
        assert stored is not None
        assert stored.km_start == 0
        assert stored.km_end == 0
        assert stored.km_business == 0
        assert stored.km_private == 0

    def test_informational_does_not_shift_successors(self, database: Database) -> None:
        # Erst ein normaler Trip, der die km-Kette startet
        first_id = database.add_trip(make_trip("2024-12-21", 100))
        before = database.get_trip_by_id(first_id)
        assert before is not None
        before_start = before.km_start
        before_end = before.km_end

        # Informationeller Trip vor dem ersten Trip — darf ihn nicht verschieben
        database.add_trip(_make_info_trip("2024-12-20", "delivery"))

        after = database.get_trip_by_id(first_id)
        assert after is not None
        assert after.km_start == before_start
        assert after.km_end == before_end

    def test_predecessor_lookup_skips_informational(self, database: Database) -> None:
        # Vehicle.start_km = 10000 aus der Fixture
        database.add_trip(_make_info_trip("2024-12-18", "return"))
        database.add_trip(_make_info_trip("2024-12-20", "delivery"))

        # Erster echter Trip muss bei vehicle.start_km anfangen — nicht bei 0
        first_real = database.add_trip(make_trip("2024-12-21", 50))
        stored = database.get_trip_by_id(first_real)
        assert stored is not None
        assert stored.km_start == 10000
        assert stored.km_end == 10050


class TestUpdateTripInformationalTransition:
    def test_business_to_informational_undoes_cascade(self, database: Database) -> None:
        trip_a = database.add_trip(make_trip("2024-06-01", 100))
        trip_b = database.add_trip(make_trip("2024-06-02", 40))

        # Trip A nachtraeglich auf informational umstellen — der 100er
        # Offset muss aus der Kette verschwinden.
        old_a = database.get_trip_by_id(trip_a)
        assert old_a is not None
        flipped = Trip(
            id=trip_a,
            date=old_a.date,
            destination="",
            purpose="",
            km_start=0,
            km_end=0,
            km_business=0,
            km_private=0,
            category="delivery",
        )
        database.update_trip(trip_a, flipped)

        # B startet jetzt beim vehicle.start_km und hat Distanz 40
        after_b = database.get_trip_by_id(trip_b)
        assert after_b is not None
        assert after_b.km_start == 10000
        assert after_b.km_end == 10040

        # A selbst ist auf 0/0 normalisiert
        after_a = database.get_trip_by_id(trip_a)
        assert after_a is not None
        assert after_a.km_start == 0
        assert after_a.km_end == 0


class TestDeleteTripInformational:
    def test_delete_informational_leaves_chain_untouched(self, database: Database) -> None:
        info_id = database.add_trip(_make_info_trip("2024-12-20", "delivery"))
        real_id = database.add_trip(make_trip("2024-12-21", 75))

        before = database.get_trip_by_id(real_id)
        assert before is not None
        before_start = before.km_start
        before_end = before.km_end

        database.delete_trip(info_id)

        after = database.get_trip_by_id(real_id)
        assert after is not None
        assert after.km_start == before_start
        assert after.km_end == before_end


class TestPlausiSkipsInformational:
    def test_chain_ascending_ignores_info_trip(self, database: Database) -> None:
        database.add_trip(_make_info_trip("2024-12-18", "return"))
        database.add_trip(_make_info_trip("2024-12-20", "delivery"))
        database.add_trip(make_trip("2024-12-21", 50))
        assert check_chain_ascending(database) == []

    def test_distance_match_ignores_info_trip(self, database: Database) -> None:
        # Informational trip hat 0/0 — ohne Skip wuerde er als distance=0
        # columns=0 sauber laufen, wir wollen aber sicher sein, dass er
        # gar nicht erst betrachtet wird.
        database.add_trip(_make_info_trip("2024-12-20", "delivery"))
        database.add_trip(make_trip("2024-12-21", 50))
        assert check_distance_matches_columns(database) == []

    def test_empty_trip_check_ignores_info(self, database: Database) -> None:
        database.add_trip(_make_info_trip("2024-12-20", "delivery"))
        assert check_empty_trips(database) == []

    def test_run_all_checks_ignores_info(self, database: Database) -> None:
        database.add_trip(_make_info_trip("2024-12-18", "return"))
        database.add_trip(_make_info_trip("2024-12-20", "delivery"))
        database.add_trip(make_trip("2024-12-21", 50))
        report = run_all_checks(database)
        # Es duerfen keine Plausi-Issues aus den informationellen Trips
        # entstehen (Quote-Warning weil zu wenig Business-km ist erlaubt,
        # wir pruefen hier nur, dass kein Issue auf sie VERWEIST).
        for issue in report.issues:
            assert issue.trip_id not in {1, 2} or issue.trip_id is None
