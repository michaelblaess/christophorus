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


@pytest.fixture
def client(tmp_path: Path, vehicle: Vehicle) -> Iterator[TestClient]:
    quelle = tmp_path / "Kompaktkombi"
    quelle.mkdir()
    fb = Fahrtenbuch.create(quelle, vehicle)
    fb.database.add_trip(make_trip("2024-05-02", 50, destination="Kunde Nord", purpose="Projektbesprechung"))
    fb.database.add_trip(make_trip("2024-05-11", 20, business=False, destination="Badesee", purpose="Ausflug"))
    fb.close()
    kopie = prepare(quelle)
    with TestClient(create_app(kopie)) as client:
        client.quelle = quelle  # type: ignore[attr-defined]
        client.kopie = kopie.path  # type: ignore[attr-defined]
        yield client


def _fahrten(client: TestClient) -> list[dict[str, object]]:
    antwort = client.get("/api/fahrten?jahr=2024&monat=5")
    assert antwort.status_code == 200
    daten = json.loads(antwort.text)
    assert isinstance(daten, list)
    return daten


def test_start_redirects_to_a_month(client: TestClient) -> None:
    antwort = client.get("/", follow_redirects=False)
    assert antwort.status_code == 303
    assert antwort.headers["location"].startswith("/fahrten?jahr=")


def test_month_page_shows_vehicle_and_copy_note(client: TestClient) -> None:
    html = client.get("/fahrten?jahr=2024&monat=5").text
    assert "Mai 2024" in html
    assert "Kompaktkombi" in html
    assert "Kopie vom" in html


def test_every_asset_is_local_and_resolves(client: TestClient) -> None:
    html = client.get("/fahrten?jahr=2024&monat=5").text
    # rel=canonical von FastHTML zeigt absolut auf den Testserver, das laedt nichts
    verweise = [v for v in VERWEIS.findall(html) if "testserver" not in v]
    assert verweise
    for verweis in verweise:
        assert verweis.startswith("/"), f"externer Verweis: {verweis}"
        assert client.get(verweis).status_code == 200, verweis


def test_month_data_is_json_for_the_table(client: TestClient) -> None:
    daten = _fahrten(client)
    assert [zeile["ziel"] for zeile in daten] == ["Kunde Nord", "Badesee"]
    assert daten[0]["datum"] == "02.05.2024"
    assert daten[0]["privatfahrt"] is False
    assert daten[1]["privatfahrt"] is True


def test_edit_dialog_is_prefilled(client: TestClient) -> None:
    fahrt_id = _fahrten(client)[0]["id"]
    html = client.get(f"/fahrten/{fahrt_id}/bearbeiten").text
    assert 'value="02.05.2024"' in html
    assert "Kunde Nord" in html


def test_saving_writes_into_the_copy_only(client: TestClient) -> None:
    fahrt_id = int(str(_fahrten(client)[0]["id"]))
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
    assert antwort.headers.get("HX-Trigger") == "fahrtGespeichert"

    kopie = Database(client.kopie)  # type: ignore[attr-defined]
    kopie.open()
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
    fahrt_id = int(str(_fahrten(client)[0]["id"]))
    antwort = client.post(f"/fahrten/{fahrt_id}", data={"datum": "", "kategorie": "business"})
    assert antwort.status_code == 200
    assert "HX-Trigger" not in antwort.headers
    assert "Bitte ein Datum eintragen." in antwort.text

    kopie = Database(client.kopie)  # type: ignore[attr-defined]
    kopie.open()
    unveraendert = kopie.get_trip_by_id(fahrt_id)
    kopie.close()
    assert unveraendert is not None and unveraendert.destination == "Kunde Nord"


def test_overview_reports_the_month(client: TestClient) -> None:
    html = client.get("/uebersicht?jahr=2024&monat=5").text
    assert "km gesamt: 70" in html
    assert "Plausibilitätsprüfung" in html


def test_unknown_trip_gives_an_empty_dialog(client: TestClient) -> None:
    assert '<div id="dialog"></div>' in client.get("/fahrten/9999/bearbeiten").text
