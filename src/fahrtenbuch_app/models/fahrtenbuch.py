"""Fahrtenbuch-Modell — repraesentiert ein geoeffnetes Fahrtenbuch."""

from pathlib import Path

from fahrtenbuch_app.models.vehicle import Vehicle
from fahrtenbuch_app.services.database import Database


class Fahrtenbuch:
    """Repraesentiert ein einzelnes Fahrtenbuch (Verzeichnis mit SQLite-DB).

    Jedes Fahrtenbuch ist ein Verzeichnis mit einer fahrtenbuch.db und
    einem belege/-Unterverzeichnis fuer Belegbilder.
    """

    def __init__(self, path: Path) -> None:
        self._path = path
        self._database = Database(path)
        self._vehicle: Vehicle | None = None

    @property
    def path(self) -> Path:
        """Pfad zum Fahrtenbuch-Verzeichnis."""
        return self._path

    @property
    def name(self) -> str:
        """Name des Fahrtenbuchs (Verzeichnisname)."""
        return self._path.name

    @property
    def database(self) -> Database:
        """Die SQLite-Datenbank dieses Fahrtenbuchs."""
        return self._database

    @property
    def vehicle(self) -> Vehicle | None:
        """Das Fahrzeug dieses Fahrtenbuchs."""
        return self._vehicle

    @property
    def is_open(self) -> bool:
        """Prueft ob das Fahrtenbuch geoeffnet ist."""
        return self._database.is_open

    @staticmethod
    def create(path: Path, vehicle: Vehicle) -> "Fahrtenbuch":
        """Erstellt ein neues Fahrtenbuch an dem angegebenen Pfad.

        Erstellt das Verzeichnis, die Datenbank und speichert das Fahrzeug.
        """
        fb = Fahrtenbuch(path)
        fb._database.open()
        fb._database.save_vehicle(vehicle)
        fb._vehicle = vehicle
        return fb

    @staticmethod
    def open(path: Path) -> "Fahrtenbuch":
        """Oeffnet ein bestehendes Fahrtenbuch.

        Laedt das Fahrzeug aus der Datenbank.
        """
        fb = Fahrtenbuch(path)
        fb._database.open()
        fb._vehicle = fb._database.get_vehicle()
        return fb

    def close(self) -> None:
        """Schliesst das Fahrtenbuch und die Datenbank."""
        self._database.close()
        self._vehicle = None
