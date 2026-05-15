"""Tests fuer die km-Kette in Database.

Schwerpunkt: nach JEDER Operation muss die Kette aufsteigend sein
(km_start_n+1 == km_end_n) und mit vehicle.start_km beginnen.
"""

from __future__ import annotations

import pytest

from death_proof.models.trip import Trip
from death_proof.models.vehicle import Vehicle
from death_proof.services.database import Database
from tests.conftest import make_trip


def assert_chain_intact(database: Database, expected_start_km: int) -> None:
    """Garantiert, dass die km-Kette lueckenlos und aufsteigend ist."""
    trips = database.get_all_trips_ordered()
    if not trips:
        return
    assert trips[0].km_start == expected_start_km, (
        f"Erster Trip startet bei {trips[0].km_start} statt {expected_start_km}"
    )
    for trip in trips:
        assert trip.km_end >= trip.km_start, (
            f"Trip {trip.id} hat negative Distanz: km_start={trip.km_start}, km_end={trip.km_end}"
        )
    for prev, curr in zip(trips, trips[1:], strict=False):
        assert curr.km_start == prev.km_end, (
            f"Kettenbruch zwischen Trip {prev.id} (Ende {prev.km_end}) und Trip {curr.id} (Start {curr.km_start})"
        )


# ---------------------------------------------------------------------------
# add_trip
# ---------------------------------------------------------------------------


class TestAddTrip:
    def test_first_trip_starts_at_vehicle_start_km(self, database: Database) -> None:
        database.add_trip(make_trip("2024-03-01", 100))
        trips = database.get_all_trips_ordered()
        assert len(trips) == 1
        assert trips[0].km_start == 10000
        assert trips[0].km_end == 10100

    def test_sequential_trips_chain_correctly(self, database: Database) -> None:
        database.add_trip(make_trip("2024-03-01", 100))
        database.add_trip(make_trip("2024-03-02", 50))
        database.add_trip(make_trip("2024-03-03", 200))
        assert_chain_intact(database, 10000)
        trips = database.get_all_trips_ordered()
        assert trips[-1].km_end == 10350

    def test_insert_in_past_shifts_successors(self, database: Database) -> None:
        """Spaeteren Trip zuerst, dann frueheren — Nachfolger muessen mitgehen."""
        id_b = database.add_trip(make_trip("2024-03-10", 200))
        # Vorher einfuegen
        id_a = database.add_trip(make_trip("2024-03-05", 100))
        assert_chain_intact(database, 10000)
        a = database.get_trip_by_id(id_a)
        b = database.get_trip_by_id(id_b)
        assert a is not None and b is not None
        assert a.km_start == 10000
        assert a.km_end == 10100
        assert b.km_start == 10100
        assert b.km_end == 10300

    def test_zero_distance_trip_does_not_shift_chain(self, database: Database) -> None:
        database.add_trip(make_trip("2024-03-01", 100))
        database.add_trip(make_trip("2024-03-02", 0, business=False))
        database.add_trip(make_trip("2024-03-03", 50))
        assert_chain_intact(database, 10000)
        assert database.get_all_trips_ordered()[-1].km_end == 10150

    def test_multiple_trips_same_day_keep_insertion_order(self, database: Database) -> None:
        id1 = database.add_trip(make_trip("2024-03-01", 30))
        id2 = database.add_trip(make_trip("2024-03-01", 40))
        id3 = database.add_trip(make_trip("2024-03-01", 50))
        assert_chain_intact(database, 10000)
        t1 = database.get_trip_by_id(id1)
        t2 = database.get_trip_by_id(id2)
        t3 = database.get_trip_by_id(id3)
        assert t1 is not None and t2 is not None and t3 is not None
        assert t1.km_start == 10000 and t1.km_end == 10030
        assert t2.km_start == 10030 and t2.km_end == 10070
        assert t3.km_start == 10070 and t3.km_end == 10120

    def test_distance_preserved_from_user_input(self, database: Database) -> None:
        """Distanz aus Trip-Vorlage muss beibehalten werden, auch wenn
        km_start vom Vorgaenger ueberschrieben wird."""
        trip = Trip(
            date="2024-03-01",
            km_start=99999,  # absurd, sollte ignoriert werden
            km_end=99999 + 75,
            km_business=75,
            category="business",
        )
        database.add_trip(trip)
        t = database.get_all_trips_ordered()[0]
        assert t.km_start == 10000
        assert t.km_end == 10075


# ---------------------------------------------------------------------------
# update_trip
# ---------------------------------------------------------------------------


class TestUpdateTrip:
    def test_update_distance_shifts_successors(self, database: Database) -> None:
        id_a = database.add_trip(make_trip("2024-03-01", 100))
        database.add_trip(make_trip("2024-03-02", 50))
        database.add_trip(make_trip("2024-03-03", 200))

        # A von 100 km auf 150 km erweitern (delta +50)
        a = database.get_trip_by_id(id_a)
        assert a is not None
        a.km_end = a.km_start + 150
        a.km_business = 150
        database.update_trip(id_a, a)

        assert_chain_intact(database, 10000)
        # Gesamt: 150 + 50 + 200 = 400
        assert database.get_all_trips_ordered()[-1].km_end == 10400

    def test_update_distance_smaller_pulls_successors_back(self, database: Database) -> None:
        id_a = database.add_trip(make_trip("2024-03-01", 200))
        database.add_trip(make_trip("2024-03-02", 100))

        a = database.get_trip_by_id(id_a)
        assert a is not None
        a.km_end = a.km_start + 50
        a.km_business = 50
        database.update_trip(id_a, a)

        assert_chain_intact(database, 10000)
        assert database.get_all_trips_ordered()[-1].km_end == 10150

    def test_update_date_only_preserves_total_distance(self, database: Database) -> None:
        """Reproduziert den Bug, der zur Limit-Verletzung gefuehrt hat:
        beim Aendern nur des Datums darf der km-Stand nicht explodieren."""
        database.add_trip(make_trip("2024-03-01", 100))
        id_b = database.add_trip(make_trip("2024-03-21", 60))
        database.add_trip(make_trip("2024-03-25", 80))

        # Datum von B auf 12.03. vorziehen, sonst alles gleich
        b = database.get_trip_by_id(id_b)
        assert b is not None
        # Distanz beibehalten
        old_distance = b.km_end - b.km_start
        assert old_distance == 60
        new_b = Trip(
            id=b.id,
            date="2024-03-12",
            time_from=b.time_from,
            time_to=b.time_to,
            destination=b.destination,
            purpose=b.purpose,
            km_start=0,  # wird von DB gesetzt
            km_end=old_distance,  # nur die Distanz zaehlt
            km_business=b.km_business,
            km_private=b.km_private,
            category=b.category,
            round_trip=b.round_trip,
        )
        database.update_trip(id_b, new_b)

        assert_chain_intact(database, 10000)
        # Gesamt-km darf sich nicht aendern
        assert database.get_all_trips_ordered()[-1].km_end == 10240

    def test_update_changes_chain_position_when_date_moved(self, database: Database) -> None:
        id_a = database.add_trip(make_trip("2024-03-01", 100))
        id_b = database.add_trip(make_trip("2024-03-02", 50))
        # B ans Anfang vorziehen
        b = database.get_trip_by_id(id_b)
        assert b is not None
        new_b = Trip(
            id=b.id,
            date="2024-02-15",
            km_start=0,
            km_end=50,
            km_business=50,
            category="business",
        )
        database.update_trip(id_b, new_b)

        assert_chain_intact(database, 10000)
        ordered = database.get_all_trips_ordered()
        assert ordered[0].id == id_b
        assert ordered[1].id == id_a

    def test_update_time_to_only_keeps_chain_stable(self, database: Database) -> None:
        """Regression: Editieren eines Non-km-Feldes (time_to) darf die
        km-Kette nicht verschieben — auch wenn das Trip-Objekt vom UI mit
        einem veralteten/falschen km_start uebergeben wird.
        """
        database.add_trip(make_trip("2024-03-01", 100))
        id_b = database.add_trip(make_trip("2024-03-02", 50))
        database.add_trip(make_trip("2024-03-03", 200))

        b = database.get_trip_by_id(id_b)
        assert b is not None
        # Simuliert den UI-Save: nur time_to wird gesetzt, alles andere
        # bleibt auf den DB-Werten.
        b.time_to = "18:00"
        database.update_trip(id_b, b)

        assert_chain_intact(database, 10000)
        assert database.get_all_trips_ordered()[-1].km_end == 10350

    def test_update_time_from_later_same_day_keeps_chain(self, database: Database) -> None:
        """Regression: Trip auf dem gleichen Tag zeitlich nach hinten
        verschieben darf die Kette nicht verschieben. Der alte Bug war,
        dass get_km_end_before() mit exclude_trip_id den eigenen Trip an
        seiner ALTEN Position als Vorgaenger der NEUEN Position gefunden
        hat — und dann seinen eigenen km_end als predecessor_km geliefert.
        """
        # Szenario aus der echten DB: #136 16:00 service 60km, #127 18:00
        # private 36km auf dem gleichen Tag. User verschiebt #127 auf 20:00
        # um die Zeitueberschneidung aufzuloesen.
        t136 = make_trip("2024-05-28", 60)
        t136.time_from = "16:00"
        t136.time_to = "19:00"
        id_136 = database.add_trip(t136)
        t127 = make_trip("2024-05-28", 36, business=False)
        t127.time_from = "18:00"
        t127.time_to = "21:00"
        id_127 = database.add_trip(t127)
        database.add_trip(make_trip("2024-05-30", 4, business=False))
        database.add_trip(make_trip("2024-05-31", 36, business=False))

        # #127 zeitlich nach 20:00 verschieben, alles andere bleibt gleich
        t127_update = database.get_trip_by_id(id_127)
        assert t127_update is not None
        t127_update.time_from = "20:00"
        database.update_trip(id_127, t127_update)

        assert_chain_intact(database, 10000)
        # #136 unveraendert
        t136_after = database.get_trip_by_id(id_136)
        assert t136_after is not None
        assert t136_after.km_start == 10000
        assert t136_after.km_end == 10060
        # #127 darf nicht seinen eigenen alten km_end als Vorgaenger sehen
        t127_after = database.get_trip_by_id(id_127)
        assert t127_after is not None
        assert t127_after.km_start == 10060
        assert t127_after.km_end == 10096

    def test_update_time_to_preserves_chain_gap(self, database: Database) -> None:
        """Regression: Edits ohne Positions- oder Distanzaenderung duerfen
        einen bestehenden Gap zwischen Vorgaenger und Trip NICHT "heilen",
        weil ein Gap z.B. eine nicht geloggte Privatfahrt repraesentieren
        kann. Wuerde der fast-path den km_start aus dem Vorgaenger ziehen,
        verschoeben sich saemtliche Nachfolger um die Luecke.
        """
        database.add_trip(make_trip("2024-03-01", 100))
        id_b = database.add_trip(make_trip("2024-03-02", 50))
        database.add_trip(make_trip("2024-03-03", 200))

        # Gap kuenstlich einfuegen: B und alle Nachfolger um 30 km nach oben
        # schieben (simuliert eine nicht geloggte Privatfahrt zwischen A und B).
        b = database.get_trip_by_id(id_b)
        assert b is not None
        original_km_start = b.km_start + 30
        original_km_end = b.km_end + 30
        conn = database._get_conn()
        conn.execute("UPDATE trips SET km_start = km_start + 30, km_end = km_end + 30 WHERE date >= '2024-03-02'")
        conn.commit()

        # Jetzt nur time_to editieren — km muessen exakt so bleiben.
        b = database.get_trip_by_id(id_b)
        assert b is not None
        b.time_to = "18:00"
        database.update_trip(id_b, b)

        b_after = database.get_trip_by_id(id_b)
        assert b_after is not None
        assert b_after.km_start == original_km_start
        assert b_after.km_end == original_km_end
        assert database.get_all_trips_ordered()[-1].km_end == 10380

    def test_update_unknown_trip_raises(self, database: Database) -> None:
        with pytest.raises(ValueError):
            database.update_trip(99999, make_trip("2024-03-01", 10))

    def test_update_does_not_reject_over_limit(self, database: Database, vehicle: Vehicle) -> None:
        """Limit-Verletzung wird nicht mehr als Hard-Stop behandelt —
        sie muss vom Plausi-Check gemeldet werden, nicht vom DB-Layer."""
        # Sehr knappes Limit setzen
        vehicle.end_km = 10200
        database.save_vehicle(vehicle)

        database.add_trip(make_trip("2024-03-01", 100))
        # Update auf 500 km — wuerde ueber 10200 hinausgehen, muss aber
        # akzeptiert werden.
        first = database.get_all_trips_ordered()[0]
        first.km_end = first.km_start + 500
        first.km_business = 500
        database.update_trip(first.id, first)
        ordered = database.get_all_trips_ordered()
        assert ordered[-1].km_end == 10500


# ---------------------------------------------------------------------------
# delete_trip
# ---------------------------------------------------------------------------


class TestDeleteTrip:
    def test_delete_pulls_successors_back(self, database: Database) -> None:
        database.add_trip(make_trip("2024-03-01", 100))
        id_b = database.add_trip(make_trip("2024-03-02", 50))
        database.add_trip(make_trip("2024-03-03", 80))

        database.delete_trip(id_b)

        assert_chain_intact(database, 10000)
        ordered = database.get_all_trips_ordered()
        assert len(ordered) == 2
        assert ordered[-1].km_end == 10180

    def test_delete_only_trip_leaves_empty_chain(self, database: Database) -> None:
        id_a = database.add_trip(make_trip("2024-03-01", 100))
        database.delete_trip(id_a)
        assert database.get_all_trips_ordered() == []

    def test_delete_unknown_trip_is_noop(self, database: Database) -> None:
        database.add_trip(make_trip("2024-03-01", 100))
        database.delete_trip(99999)
        assert_chain_intact(database, 10000)


# ---------------------------------------------------------------------------
# get_km_end_before
# ---------------------------------------------------------------------------


class TestGetKmEndBefore:
    def test_returns_vehicle_start_km_when_empty(self, database: Database) -> None:
        assert database.get_km_end_before("2024-03-01") == 10000

    def test_returns_predecessor_km_end(self, database: Database) -> None:
        database.add_trip(make_trip("2024-03-01", 100))
        database.add_trip(make_trip("2024-03-02", 50))
        assert database.get_km_end_before("2024-03-03") == 10150

    def test_excludes_self_for_same_date(self, database: Database) -> None:
        id_a = database.add_trip(make_trip("2024-03-01", 100))
        id_b = database.add_trip(make_trip("2024-03-01", 50))
        # Vorgaenger von B (am gleichen Tag) ist A
        assert database.get_km_end_before("2024-03-01", exclude_trip_id=id_b) == 10100
        # Vorgaenger von A (am gleichen Tag) ist nichts
        assert database.get_km_end_before("2024-03-01", exclude_trip_id=id_a) == 10000


# ---------------------------------------------------------------------------
# Time-basierte Kettenordnung
# ---------------------------------------------------------------------------


def _add_trip_at(
    database: Database,
    date: str,
    time_from: str,
    distance: int,
) -> int:
    """Helper: Trip mit konkreter Uhrzeit anlegen."""
    t = make_trip(date, distance)
    t.time_from = time_from
    t.time_to = time_from  # Inhalt irrelevant fuer Kette, nur time_from zaehlt
    return database.add_trip(t)


class TestTimeFromOrdering:
    """Same-day-Trips werden anhand time_from in die Kette eingefuegt."""

    def test_earlier_time_inserted_later_places_first(self, database: Database) -> None:
        """Zuerst 17:00 eingefuegt, dann 16:00 — 16:00 muss in der Kette zuerst kommen."""
        id_late = _add_trip_at(database, "2024-03-01", "17:00", 36)
        id_early = _add_trip_at(database, "2024-03-01", "16:00", 41)
        assert_chain_intact(database, 10000)
        early = database.get_trip_by_id(id_early)
        late = database.get_trip_by_id(id_late)
        assert early is not None and late is not None
        assert early.km_start == 10000
        assert early.km_end == 10041
        assert late.km_start == 10041
        assert late.km_end == 10077

    def test_three_trips_same_day_ordered_by_time(self, database: Database) -> None:
        _add_trip_at(database, "2024-03-01", "12:00", 20)
        _add_trip_at(database, "2024-03-01", "08:00", 10)
        _add_trip_at(database, "2024-03-01", "18:00", 30)
        assert_chain_intact(database, 10000)
        trips = database.get_all_trips_ordered()
        assert [t.time_from for t in trips] == ["08:00", "12:00", "18:00"]
        assert [t.km_start for t in trips] == [10000, 10010, 10030]
        assert [t.km_end for t in trips] == [10010, 10030, 10060]

    def test_update_time_from_repositions_chain(self, database: Database) -> None:
        """Uhrzeit eines Trips aendern → Kette muss neu ausgerichtet werden."""
        id_a = _add_trip_at(database, "2024-03-01", "09:00", 100)
        id_b = _add_trip_at(database, "2024-03-01", "15:00", 50)
        # A startet bei 10000, B bei 10100 — alles normal
        b_before = database.get_trip_by_id(id_b)
        assert b_before is not None
        assert b_before.km_start == 10100

        # Uhrzeit von A von 09:00 auf 18:00 schieben — A muss NACH B landen
        a = database.get_trip_by_id(id_a)
        assert a is not None
        a.time_from = "18:00"
        database.update_trip(id_a, a)
        assert_chain_intact(database, 10000)

        b_after = database.get_trip_by_id(id_b)
        a_after = database.get_trip_by_id(id_a)
        assert b_after is not None and a_after is not None
        assert b_after.km_start == 10000
        assert b_after.km_end == 10050
        assert a_after.km_start == 10050
        assert a_after.km_end == 10150

    def test_delete_by_time_shifts_correct_successors(self, database: Database) -> None:
        _add_trip_at(database, "2024-03-01", "08:00", 10)
        id_mid = _add_trip_at(database, "2024-03-01", "12:00", 20)
        _add_trip_at(database, "2024-03-01", "18:00", 30)
        database.delete_trip(id_mid)
        assert_chain_intact(database, 10000)
        trips = database.get_all_trips_ordered()
        assert [t.time_from for t in trips] == ["08:00", "18:00"]
        assert trips[-1].km_end == 10040

    def test_rebuild_heals_misordered_same_day_chain(self, database: Database) -> None:
        """Simuliert die Dezember-29-Situation: Trips same-day in falscher
        Zeit-Reihenfolge eingefuegt → rebuild_all_km repariert die Kette.
        """
        # Insert-Reihenfolge: 17:00 zuerst, 16:00 danach
        id_late = _add_trip_at(database, "2024-03-01", "17:00", 36)
        id_early = _add_trip_at(database, "2024-03-01", "16:00", 41)
        # Mit der neuen Logik stimmt die Kette bereits — um die alte Bug-
        # Situation nachzustellen, setzen wir die km_start/km_end bewusst
        # im alten (date, id)-Stil: 16:00-Trip bekommt den hoeheren km_start.
        conn = database._get_conn()  # type: ignore[reportPrivateUsage]
        conn.execute(
            "UPDATE trips SET km_start = ?, km_end = ? WHERE id = ?",
            (10000, 10036, id_late),
        )
        conn.execute(
            "UPDATE trips SET km_start = ?, km_end = ? WHERE id = ?",
            (10036, 10077, id_early),
        )
        conn.commit()

        # rebuild stellt die zeitliche Reihenfolge wieder her
        changed, final_km = database.rebuild_all_km()
        assert changed == 2
        assert final_km == 10077
        assert_chain_intact(database, 10000)
        early = database.get_trip_by_id(id_early)
        late = database.get_trip_by_id(id_late)
        assert early is not None and late is not None
        assert early.km_start == 10000
        assert early.km_end == 10041
        assert late.km_start == 10041
        assert late.km_end == 10077


# ---------------------------------------------------------------------------
# rebuild_all_km
# ---------------------------------------------------------------------------


class TestRebuildAllKm:
    def test_rebuild_fixes_broken_chain(self, database: Database) -> None:
        """Manuelle Sabotage in der DB — rebuild muss die Kette heilen."""
        database.add_trip(make_trip("2024-03-01", 100))
        database.add_trip(make_trip("2024-03-02", 50))
        database.add_trip(make_trip("2024-03-03", 80))

        # Zerschiesse den mittleren Trip per direktem SQL
        ordered = database.get_all_trips_ordered()
        mid = ordered[1]
        # Direkten DB-Zugriff via _get_conn (Test darf das)
        database._get_conn().execute(  # type: ignore[reportPrivateUsage]
            "UPDATE trips SET km_start = ?, km_end = ? WHERE id = ?",
            (99999, 99999 + (mid.km_end - mid.km_start), mid.id),
        )
        database._get_conn().commit()  # type: ignore[reportPrivateUsage]

        changed, final_km = database.rebuild_all_km()
        assert changed == 3
        assert final_km == 10230
        assert_chain_intact(database, 10000)

    def test_rebuild_preserves_distances(self, database: Database) -> None:
        database.add_trip(make_trip("2024-03-01", 100))
        database.add_trip(make_trip("2024-03-02", 50))
        database.rebuild_all_km()
        ordered = database.get_all_trips_ordered()
        assert ordered[0].km_end - ordered[0].km_start == 100
        assert ordered[1].km_end - ordered[1].km_start == 50

    def test_rebuild_raises_when_over_limit(self, database: Database, vehicle: Vehicle) -> None:
        vehicle.end_km = 10100
        database.save_vehicle(vehicle)
        database.add_trip(make_trip("2024-03-01", 50))
        database.add_trip(make_trip("2024-03-02", 200))
        with pytest.raises(ValueError, match="Endkilometerstand"):
            database.rebuild_all_km()

    def test_rebuild_force_ignores_over_limit(self, database: Database, vehicle: Vehicle) -> None:
        """Mit force=True laeuft der Rebuild auch ueber dem Vertragslimit."""
        vehicle.end_km = 10100
        database.save_vehicle(vehicle)
        database.add_trip(make_trip("2024-03-01", 50))
        database.add_trip(make_trip("2024-03-02", 200))
        changed, final_km = database.rebuild_all_km(force=True)
        assert changed == 2
        assert final_km == 10250

    def test_rebuild_uses_column_sum_when_chain_is_zero(self, database: Database) -> None:
        """Trip #104-Fall: km_start==km_end aber km_business=260.

        Rebuild muss 260 km aus den Spalten uebernehmen, nicht bei 0
        bleiben — sonst faellt die Kette auseinander.
        """
        database.add_trip(make_trip("2024-03-01", 100))
        t2 = make_trip("2024-03-02", 260)
        t2_id = database.add_trip(t2)
        # Simuliere Nutzer-Bug: km_end auf km_start setzen, km_business
        # steht aber korrekt in der Spalte.
        database._get_conn().execute(  # type: ignore[reportPrivateUsage]
            "UPDATE trips SET km_end = km_start WHERE id = ?",
            (t2_id,),
        )
        database._get_conn().commit()  # type: ignore[reportPrivateUsage]
        changed, final_km = database.rebuild_all_km()
        assert changed == 2
        assert final_km == 10360  # 10000 + 100 + 260
        ordered = database.get_all_trips_ordered()
        assert ordered[1].km_end - ordered[1].km_start == 260


# ---------------------------------------------------------------------------
# Stress / Mixed Operations
# ---------------------------------------------------------------------------


class TestMixedOperations:
    def test_full_chain_remains_ascending_after_random_ops(self, database: Database) -> None:
        """Verschiedenste Operationen — danach muss die Kette sauber sein."""
        ids = []
        for day, dist in [
            ("2024-03-01", 100),
            ("2024-03-15", 200),
            ("2024-03-05", 80),
            ("2024-03-20", 150),
            ("2024-03-10", 30),
        ]:
            ids.append(database.add_trip(make_trip(day, dist)))
        assert_chain_intact(database, 10000)

        # Update einer Fahrt
        t = database.get_trip_by_id(ids[0])
        assert t is not None
        t.km_end = t.km_start + 250
        t.km_business = 250
        database.update_trip(ids[0], t)
        assert_chain_intact(database, 10000)

        # Loesche zwei Fahrten
        database.delete_trip(ids[2])
        database.delete_trip(ids[4])
        assert_chain_intact(database, 10000)

        # Neue Fahrt einfuegen
        database.add_trip(make_trip("2024-03-08", 60))
        assert_chain_intact(database, 10000)

        # Rebuild als Sicherheitsnetz
        database.rebuild_all_km()
        assert_chain_intact(database, 10000)
