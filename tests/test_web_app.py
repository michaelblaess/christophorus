"""Die Routen der Web-Oberflaeche, gegen eine echte Arbeitskopie."""

from __future__ import annotations

import json
import re
from collections.abc import Iterator
from pathlib import Path

import pytest

pytest.importorskip("fasthtml")

from starlette.testclient import TestClient  # noqa: E402

from christo.models.vehicle import Vehicle  # noqa: E402
from christo.services.database import Database  # noqa: E402
from christo.services.fahrtenbuch import Fahrtenbuch  # noqa: E402
from christo.web.app import create_app  # noqa: E402
from christo.web.workspace import prepare  # noqa: E402
from tests.conftest import make_trip  # noqa: E402

VERWEIS = re.compile(r'<(?:link|script)\b[^>]*?(?:href|src)="([^"]+)"')
GEAENDERT = "datenGeaendert"


@pytest.fixture
def client(tmp_path: Path, vehicle: Vehicle) -> Iterator[TestClient]:
    quelle = tmp_path / "Kompaktkombi"
    quelle.mkdir()
    fb = Fahrtenbuch.create(quelle, vehicle)
    fb.database.add_trip(make_trip("2024-05-02", 50, destination="Kunde Nord", purpose="Projektbesprechung"))
    fb.database.add_trip(make_trip("2024-05-11", 20, business=False, destination="Badesee", purpose="Ausflug"))
    fb.database.add_trip(make_trip("2024-06-04", 30, destination="Werkstatt", purpose="Inspektion"))
    fb.database.add_blacklist_entry("2024-05-20", "Urlaub")
    fb.close()
    kopie = prepare(quelle)
    with TestClient(create_app(kopie)) as client:
        client.quelle = quelle  # type: ignore[attr-defined]
        client.kopie = kopie.path  # type: ignore[attr-defined]
        yield client


def _db(client: TestClient) -> Database:
    db = Database(client.kopie)  # type: ignore[attr-defined]
    db.open()
    return db


def _fahrten(client: TestClient, jahr: int = 2024, monat: int = 5) -> list[dict[str, object]]:
    antwort = client.get(f"/api/fahrten?jahr={jahr}&monat={monat}")
    assert antwort.status_code == 200
    daten = json.loads(antwort.text)
    assert isinstance(daten, list)
    return daten


def _erste_id(client: TestClient) -> int:
    return int(str(_fahrten(client)[0]["id"]))


# --- Geruest ---------------------------------------------------------------------------


def test_start_redirects_to_a_month(client: TestClient) -> None:
    antwort = client.get("/", follow_redirects=False)
    assert antwort.status_code == 303
    assert antwort.headers["location"].startswith("/fahrten?jahr=")


def test_month_page_shows_vehicle_and_copy_note(client: TestClient) -> None:
    html = client.get("/fahrten?jahr=2024&monat=5").text
    assert "Mai 2024" in html
    assert "Kompaktkombi" in html
    assert "Kopie vom" in html


@pytest.mark.parametrize(
    "adresse",
    [
        "/fahrten?jahr=2024&monat=5",
        "/fahrten/jahr?jahr=2024",
        "/kalender?jahr=2024&monat=5",
        "/jahr?jahr=2024",
        "/blacklist",
        "/belege",
        "/arbeitszeit?jahr=2024",
        "/einstellungen",
    ],
)
def test_every_page_answers_and_links_only_local_assets(client: TestClient, adresse: str) -> None:
    antwort = client.get(adresse)
    assert antwort.status_code == 200, adresse
    # rel=canonical von FastHTML zeigt absolut auf den Testserver, das laedt nichts
    verweise = [v for v in VERWEIS.findall(antwort.text) if "testserver" not in v]
    assert verweise
    for verweis in verweise:
        assert verweis.startswith("/"), f"externer Verweis: {verweis}"
        assert client.get(verweis).status_code == 200, verweis


def test_every_tab_is_reachable_from_every_page(client: TestClient) -> None:
    html = client.get("/fahrten?jahr=2024&monat=5").text
    for titel in ("Liste (Jahr)", "Kalender", "Jahr", "Blacklist", "Belege", "Arbeitszeit"):
        assert titel in html
    assert 'class="reiter gesperrt"' not in html


# --- Monats- und Jahresliste -----------------------------------------------------------


def test_month_data_is_json_for_the_table(client: TestClient) -> None:
    daten = _fahrten(client)
    assert [zeile["ziel"] for zeile in daten] == ["Kunde Nord", "Badesee"]
    assert daten[0]["datum"] == "02.05.2024"
    assert daten[0]["privatfahrt"] is False
    assert daten[1]["privatfahrt"] is True


def test_year_data_covers_every_month_and_names_it(client: TestClient) -> None:
    antwort = client.get("/api/fahrten?jahr=2024")
    daten = json.loads(antwort.text)
    assert [zeile["ziel"] for zeile in daten] == ["Kunde Nord", "Badesee", "Werkstatt"]
    assert daten[-1]["monat"] == "Juni 2024"


def test_overview_reports_the_month(client: TestClient) -> None:
    html = client.get("/uebersicht?jahr=2024&monat=5").text
    assert "km gesamt: 70" in html
    assert "Plausibilitätsprüfung" in html


def test_overview_for_the_year_adds_the_other_months(client: TestClient) -> None:
    html = client.get("/uebersicht?jahr=2024&art=jahr").text
    assert "km gesamt: 100" in html


# --- Bearbeiten ------------------------------------------------------------------------


def test_edit_dialog_is_prefilled(client: TestClient) -> None:
    html = client.get(f"/fahrten/{_erste_id(client)}/bearbeiten").text
    assert 'value="02.05.2024"' in html
    assert "Kunde Nord" in html


def test_saving_writes_into_the_copy_only(client: TestClient) -> None:
    fahrt_id = _erste_id(client)
    antwort = client.post(
        f"/fahrten/{fahrt_id}",
        data={
            "datum": "02.05.2024",
            "abfahrt": "07:15",
            "ankunft": "10:40",
            "ziel": "Kunde Süd, Beispielhausen",
            "zweck": "Schulung",
            "kategorie": "business",
            "km_anfang": "0",
            "km_geschaeftlich": "60",
            "km_privat": "0",
        },
    )
    assert antwort.status_code == 200
    assert antwort.headers.get("HX-Trigger") == GEAENDERT

    kopie = _db(client)
    gespeichert = kopie.get_trip_by_id(fahrt_id)
    kopie.close()
    assert gespeichert is not None
    assert (gespeichert.destination, gespeichert.km_business) == ("Kunde Süd, Beispielhausen", 60)

    quelle = Database(client.quelle)  # type: ignore[attr-defined]
    quelle.open()
    im_original = quelle.get_trip_by_id(fahrt_id)
    quelle.close()
    assert im_original is not None
    assert im_original.destination == "Kunde Nord"


def test_invalid_input_returns_the_dialog_with_the_error(client: TestClient) -> None:
    fahrt_id = _erste_id(client)
    antwort = client.post(f"/fahrten/{fahrt_id}", data={"datum": "", "kategorie": "business"})
    assert antwort.status_code == 200
    assert "HX-Trigger" not in antwort.headers
    assert "Bitte ein Datum eintragen." in antwort.text

    kopie = _db(client)
    unveraendert = kopie.get_trip_by_id(fahrt_id)
    kopie.close()
    assert unveraendert is not None and unveraendert.destination == "Kunde Nord"


def test_unknown_trip_gives_an_empty_dialog(client: TestClient) -> None:
    assert '<div id="dialog"></div>' in client.get("/fahrten/9999/bearbeiten").text


# --- Anlegen und Loeschen --------------------------------------------------------------


def test_new_trip_dialog_starts_at_the_last_km(client: TestClient) -> None:
    html = client.get("/fahrten/neu?jahr=2024&monat=7").text
    assert "Neue Fahrt" in html
    assert 'value="01.07.2024"' in html
    # Im Juli steht noch nichts, also zaehlt das Ende der letzten Fahrt davor (Juni: 10.100)
    assert 'value="10.100"' in html
    assert "/fahrten/neu?jahr=2024&amp;monat=7" in html


def test_new_trip_dialog_takes_the_day_from_the_calendar(client: TestClient) -> None:
    assert 'value="17.05.2024"' in client.get("/fahrten/neu?datum=2024-05-17").text


def test_creating_a_trip_adds_it_to_the_month(client: TestClient) -> None:
    antwort = client.post(
        "/fahrten/neu?jahr=2024&monat=5",
        data={
            "datum": "17.05.2024",
            "ziel": "Messe",
            "zweck": "Messeaufbau",
            "kategorie": "business",
            "km_anfang": "10.070",
            "km_geschaeftlich": "84",
            "km_privat": "0",
        },
    )
    assert antwort.status_code == 200
    assert antwort.headers.get("HX-Trigger") == GEAENDERT
    assert [z["zweck"] for z in _fahrten(client)] == ["Projektbesprechung", "Ausflug", "Messeaufbau"]


def test_creating_a_trip_with_errors_keeps_the_dialog(client: TestClient) -> None:
    vorher = len(_fahrten(client))
    antwort = client.post("/fahrten/neu?jahr=2024&monat=5", data={"datum": "32.05.2024", "kategorie": "business"})
    assert "HX-Trigger" not in antwort.headers
    assert "Dieses Datum gibt es nicht." in antwort.text
    assert len(_fahrten(client)) == vorher


def test_delete_asks_first_and_then_removes(client: TestClient) -> None:
    fahrt_id = _erste_id(client)
    frage = client.get(f"/fahrten/{fahrt_id}/loeschen")
    assert "Endgültig löschen" in frage.text
    assert "02.05.2024" in frage.text
    # Die Rueckfrage allein loescht nichts
    assert len(_fahrten(client)) == 2

    antwort = client.post(f"/fahrten/{fahrt_id}/loeschen")
    assert antwort.headers.get("HX-Trigger") == GEAENDERT
    assert [z["ziel"] for z in _fahrten(client)] == ["Badesee"]


def test_delete_warns_about_attached_documents(client: TestClient, tmp_path: Path) -> None:
    fahrt_id = _erste_id(client)
    db = _db(client)
    db.add_document(path="quittung.pdf", description="Tankbeleg", trip_id=fahrt_id)
    db.close()
    assert "Beleg" in client.get(f"/fahrten/{fahrt_id}/loeschen").text


# --- Kalender und Jahr -----------------------------------------------------------------


def test_calendar_shows_trips_holidays_and_blocked_days(client: TestClient) -> None:
    html = client.get("/kalender?jahr=2024&monat=5").text
    assert "Projektbesprechung" in html
    assert "Christi Himmelfahrt" in html  # 09.05.2024
    assert "gesperrt: Urlaub" in html
    assert "/fahrten/neu?datum=2024-05-17" in html


def test_year_view_shows_twelve_tiles_and_the_sum(client: TestClient) -> None:
    html = client.get("/jahr?jahr=2024").text
    for name in ("Januar", "Mai", "Juni", "Dezember"):
        assert name in html
    assert "km gesamt: 100" in html
    assert "/fahrten?jahr=2024&amp;monat=5" in html


# --- Blacklist -------------------------------------------------------------------------


def test_blacklist_lists_the_blocked_days(client: TestClient) -> None:
    daten = json.loads(client.get("/api/blacklist").text)
    assert [(z["datum"], z["grund"]) for z in daten] == [("20.05.2024", "Urlaub")]


def test_blacklist_entry_can_be_created_changed_and_deleted(client: TestClient) -> None:
    angelegt = client.post("/blacklist/neu", data={"datum": "03.06.2024", "grund": "Krank"})
    assert angelegt.headers.get("HX-Trigger") == GEAENDERT
    eintraege = json.loads(client.get("/api/blacklist").text)
    assert [z["grund"] for z in eintraege] == ["Urlaub", "Krank"]

    neue_id = int(str(eintraege[1]["id"]))
    assert "Krank" in client.get(f"/blacklist/{neue_id}/bearbeiten").text
    client.post(f"/blacklist/{neue_id}", data={"datum": "03.06.2024", "grund": "Krankenschein"})
    assert json.loads(client.get("/api/blacklist").text)[1]["grund"] == "Krankenschein"

    geloescht = client.post(f"/blacklist/{neue_id}/loeschen")
    assert geloescht.headers.get("HX-Trigger") == GEAENDERT
    assert len(json.loads(client.get("/api/blacklist").text)) == 1


def test_blacklist_entry_without_reason_is_rejected(client: TestClient) -> None:
    antwort = client.post("/blacklist/neu", data={"datum": "03.06.2024", "grund": ""})
    assert "HX-Trigger" not in antwort.headers
    assert "Bitte einen Grund eintragen" in antwort.text
    assert len(json.loads(client.get("/api/blacklist").text)) == 1


# --- Belege ----------------------------------------------------------------------------


def test_documents_list_marks_missing_files(client: TestClient) -> None:
    fahrt_id = _erste_id(client)
    db = _db(client)
    db.add_document(path="belege/quittung.txt", description="Tankbeleg", trip_id=fahrt_id)
    db.close()
    (client.quelle / "belege").mkdir(exist_ok=True)  # type: ignore[attr-defined]

    zeilen = json.loads(client.get("/api/belege").text)
    assert zeilen[0]["datei"] == "quittung.txt"
    assert zeilen[0]["vorhanden"] is False
    assert "1 Datei fehlt" in client.get("/belege").text

    (client.quelle / "belege" / "quittung.txt").write_text("Beleg", encoding="utf-8")  # type: ignore[attr-defined]
    assert json.loads(client.get("/api/belege").text)[0]["vorhanden"] is True


def test_document_is_served_from_the_original_folder(client: TestClient) -> None:
    fahrt_id = _erste_id(client)
    db = _db(client)
    doc_id = db.add_document(path="belege/quittung.txt", trip_id=fahrt_id)
    db.close()
    (client.quelle / "belege").mkdir(exist_ok=True)  # type: ignore[attr-defined]
    (client.quelle / "belege" / "quittung.txt").write_text("Beleg", encoding="utf-8")  # type: ignore[attr-defined]

    antwort = client.get(f"/belege/{doc_id}/datei")
    assert antwort.status_code == 200
    assert antwort.text == "Beleg"
    assert client.get("/belege/9999/datei").status_code == 404


# --- Arbeitszeit -----------------------------------------------------------------------


def test_worktimes_are_saved_and_cleared(client: TestClient) -> None:
    html = client.get("/arbeitszeit?jahr=2024").text
    assert "Arbeitszeit 2024" in html
    assert 'name="monat_5"' in html

    antwort = client.post("/arbeitszeit?jahr=2024", data={"monat_5": "142,5", "monat_6": ""})
    assert antwort.status_code == 200
    assert "Gespeichert." in antwort.text
    db = _db(client)
    assert {int(w["month"]): float(w["hours"]) for w in db.get_worktimes(2024)} == {5: 142.5}

    client.post("/arbeitszeit?jahr=2024", data={"monat_5": ""})
    assert db.get_worktimes(2024) == []
    db.close()


# --- Export ----------------------------------------------------------------------------


def test_export_delivers_a_file_per_format(client: TestClient) -> None:
    for wahl, endung in (("xlsx", ".xlsx"), ("json", ".json"), ("md", ".md")):
        antwort = client.get(f"/export?jahr=2024&monat=5&format={wahl}")
        assert antwort.status_code == 200, wahl
        assert antwort.content
        assert endung in antwort.headers["content-disposition"]
    inhalt = client.get("/export?jahr=2024&monat=5&format=json").json()
    assert json.dumps(inhalt, ensure_ascii=False).count("Kunde Nord") == 1


def test_year_export_covers_every_month(client: TestClient) -> None:
    antwort = client.get("/export?jahr=2024&format=md")
    assert "Werkstatt" in antwort.text
    assert "Kunde Nord" in antwort.text


def test_export_of_an_empty_month_says_so(client: TestClient) -> None:
    antwort = client.get("/export?jahr=2024&monat=2&format=md")
    assert antwort.status_code == 404
    assert "keine Fahrten" in antwort.text


# --- Einstellungen ---------------------------------------------------------------------


def test_settings_show_the_vehicle_and_save_it(client: TestClient) -> None:
    html = client.get("/einstellungen").text
    assert 'value="Testwagen"' in html
    assert 'value="01.01.2024"' in html

    antwort = client.post(
        "/einstellungen/fahrzeug",
        data={
            "name": "Kombi neu",
            "plate": "B-TT 2",
            "contract_number": "X",
            "start_date": "01.01.2024",
            "end_date": "31.12.2026",
            "lease_months": "36",
            "lease_km_per_month": "2.000",
            "start_km": "10000",
            "end_km": "30000",
            "tank_capacity_l": "55",
            "consumption_l_100km": "6,4",
        },
    )
    assert "Gespeichert." in antwort.text
    db = _db(client)
    fahrzeug = db.get_vehicle()
    db.close()
    assert (fahrzeug.name, fahrzeug.lease_km_per_month, fahrzeug.end_date) == ("Kombi neu", 2000, "2026-12-31")
    assert fahrzeug.consumption_l_100km == 6.4
    assert "Kombi neu" in client.get("/fahrten?jahr=2024&monat=5").text


def test_vehicle_form_reports_an_impossible_contract(client: TestClient) -> None:
    antwort = client.post(
        "/einstellungen/fahrzeug",
        data={"name": "Testwagen", "start_date": "01.01.2026", "end_date": "01.01.2025"},
    )
    assert "Das Vertragsende liegt vor dem Beginn." in antwort.text
    db = _db(client)
    assert db.get_vehicle().name == "Testwagen"
    db.close()


def test_check_settings_are_saved(client: TestClient) -> None:
    antwort = client.post(
        "/einstellungen/pruefung",
        data={"federal_state": "SN", "home_address": "Musterweg 1", "check_ghost_trips": "1"},
    )
    assert "Gespeichert." in antwort.text
    db = _db(client)
    assert db.get_setting("federal_state") == "SN"
    assert db.get_setting("home_address") == "Musterweg 1"
    assert db.get_setting("check_ghost_trips") == "1"
    assert db.get_setting("export_include_prev_december") == "0"
    db.close()


def test_categories_can_be_relabelled(client: TestClient) -> None:
    db = _db(client)
    kategorie = next(k for k in db.get_categories() if k["name"] == "business")
    db.close()
    kid = int(str(kategorie["id"]))
    antwort = client.post(
        "/einstellungen/kategorien",
        data={f"beschriftung_{kid}": "Dienstfahrt", f"geschaeftlich_{kid}": "1", f"farbe_{kid}": "#112233"},
    )
    assert "Kategorien gespeichert." in antwort.text
    db = _db(client)
    neu = next(k for k in db.get_categories() if k["name"] == "business")
    db.close()
    assert neu["display_name"] == "Dienstfahrt"
    assert "Dienstfahrt" in client.get(f"/fahrten/{_erste_id(client)}/bearbeiten").text


def test_a_used_category_cannot_be_deleted(client: TestClient) -> None:
    html = client.get("/einstellungen").text
    db = _db(client)
    business = next(k for k in db.get_categories() if k["name"] == "business")
    unbenutzt = next(k for k in db.get_categories() if k["name"] not in {"business", "private"})
    db.close()
    assert f'name="loeschen" value="{business["id"]}"' not in html
    assert f'name="loeschen" value="{unbenutzt["id"]}"' in html

    antwort = client.post("/einstellungen/kategorien", data={"loeschen": str(unbenutzt["id"])})
    assert "Kategorie gelöscht." in antwort.text
    db = _db(client)
    assert unbenutzt["name"] not in {k["name"] for k in db.get_categories()}
    db.close()


def test_switches_show_the_defaults_the_checks_really_use(client: TestClient) -> None:
    html = client.get("/einstellungen").text

    def kasten(name: str) -> str:
        treffer = re.search(rf"<input[^>]*name=\"{name}\"[^>]*>", html)
        assert treffer, name
        return treffer.group(0)

    # Die Pruefung liest fuel_winter_tolerance mit Standard "1" - die Maske muss das zeigen,
    # sonst schaltet das erste Speichern die Toleranz unbemerkt ab.
    assert "checked" in kasten("fuel_winter_tolerance")
    assert "checked" not in kasten("check_ghost_trips")
    assert "checked" not in kasten("export_include_prev_december")


def test_saving_the_checks_keeps_a_ticked_switch(client: TestClient) -> None:
    client.post("/einstellungen/pruefung", data={"federal_state": "BB", "fuel_winter_tolerance": "1"})
    db = _db(client)
    assert db.get_setting("fuel_winter_tolerance") == "1"
    db.close()
    assert "checked" in re.search(  # type: ignore[union-attr]
        r"<input[^>]*name=\"fuel_winter_tolerance\"[^>]*>", client.get("/einstellungen").text
    ).group(0)


def test_worktimes_average_counts_only_filled_months(client: TestClient) -> None:
    client.post("/arbeitszeit?jahr=2024", data={"monat_1": "100", "monat_2": "200"})
    html = client.get("/arbeitszeit?jahr=2024").text
    assert "2 erfasst" in html
    assert "Ø 150,00" in html


def test_extra_fields_carry_their_own_heading(client: TestClient) -> None:
    # Ohne <summary> zeigt der Browser sein eigenes Wort "Details" statt der Beschriftung
    html = client.get(f"/fahrten/{_erste_id(client)}/bearbeiten").text
    assert "<summary" in html
    assert "Tanken und Hin- und Rückfahrt" in html
