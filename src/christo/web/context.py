"""Der gemeinsame Zustand der Weboberflaeche: Datenbank, Fahrzeug, Kategorien, Befunde.

Alle Ansichten bekommen diesen Kontext statt einer eigenen Datenbankverbindung. Er haelt
je Thread eine Verbindung, weil Starlette synchrone Routen aus einem Threadpool bedient und
eine SQLite-Verbindung genau einem Thread gehoert.
"""

from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import date

from christo.models.trip import set_business_categories, set_informational_categories
from christo.models.vehicle import Vehicle
from christo.services.database import Database
from christo.services.holiday_service import HolidayService
from christo.services.plausibility import (
    CAT_GHOST_BUSINESS_TRIP,
    PlausibilityIssue,
    run_all_checks,
)
from christo.web.workspace import Workspace


@dataclass
class Monat:
    """Der angezeigte Monat."""

    jahr: int
    monat: int

    @property
    def titel(self) -> str:
        from christo.i18n import month_name

        return f"{month_name(self.monat)} {self.jahr}"

    def verschoben(self, schritte: int) -> Monat:
        gesamt = self.jahr * 12 + (self.monat - 1) + schritte
        return Monat(jahr=gesamt // 12, monat=gesamt % 12 + 1)


class Context:
    """Zugriff auf die Arbeitskopie fuer alle Ansichten und Routen."""

    def __init__(self, workspace: Workspace) -> None:
        self.workspace = workspace
        self._lokal = threading.local()
        self.uebernehme_kategorien()

    # --- Datenbank ----------------------------------------------------------------------

    def db(self) -> Database:
        """Die Verbindung dieses Threads, bei Bedarf frisch geoeffnet."""
        vorhanden: Database | None = getattr(self._lokal, "db", None)
        if vorhanden is None or not vorhanden.is_open:
            vorhanden = Database(self.workspace.path)
            vorhanden.open()
            self._lokal.db = vorhanden
        return vorhanden

    def uebernehme_kategorien(self) -> None:
        """Setzt die Kategorien aus der Datenbank ins Modell, wie es die TUI beim Start tut."""
        db = self.db()
        set_business_categories(db.get_business_category_names())
        set_informational_categories(db.get_informational_category_names())

    # --- Stammdaten ---------------------------------------------------------------------

    @property
    def vehicle(self) -> Vehicle:
        """Das Fahrzeug, bei jedem Zugriff frisch - die Einstellungen koennen es aendern."""
        return self.db().get_vehicle()

    def kategorien(self) -> list[tuple[str, str]]:
        """Alle Kategorien als (Beschriftung, Name)."""
        return self.db().get_category_options()

    def kategoriename(self, code: str) -> str:
        """Die Beschriftung zu einem Kategorienamen, sonst der Name selbst."""
        return next((label for label, name in self.kategorien() if name == code), code)

    def standardmonat(self) -> Monat:
        """Zuletzt in der TUI angesehener Monat, sonst der erste mit Fahrten, sonst heute."""
        db = self.db()
        jahr = db.get_setting("last_viewed_year", "")
        monat = db.get_setting("last_viewed_month", "")
        if jahr.isdigit() and monat.isdigit() and 1 <= int(monat) <= 12:
            return Monat(jahr=int(jahr), monat=int(monat))
        erster = db.get_first_trip_date()
        if erster:
            return Monat(jahr=erster[0], monat=erster[1])
        heute = date.today()
        return Monat(jahr=heute.year, monat=heute.month)

    # --- Pruefung -----------------------------------------------------------------------

    def issues(self, jahr: int) -> list[PlausibilityIssue]:
        """Die Plausibilitaetsbefunde eines Jahres, mit den Einstellungen der Datenbank."""
        db = self.db()
        feiertage = HolidayService(db.get_setting("federal_state", "BB")).get_holidays_in_year(jahr)
        skip: set[str] = set()
        if db.get_setting("check_ghost_trips", "0") != "1":
            skip.add(CAT_GHOST_BUSINESS_TRIP)
        return run_all_checks(db, holidays_by_date=feiertage, skip_checks=skip).issues

    def befunde_je_monat(self, jahr: int) -> dict[int, int]:
        """Anzahl der Befunde je Monat, fuer die Jahresuebersicht."""
        zaehler: dict[int, int] = {}
        for issue in self.issues(jahr):
            if issue.month_key:
                zaehler[issue.month_key[1]] = zaehler.get(issue.month_key[1], 0) + 1
        return zaehler
