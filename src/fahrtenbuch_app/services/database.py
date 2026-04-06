"""SQLite-basierte Datenhaltung fuer ein einzelnes Fahrtenbuch."""

import sqlite3
from pathlib import Path

from fahrtenbuch_app.models.trip import MonthData, Trip
from fahrtenbuch_app.models.vehicle import Vehicle


class Database:
    """Verwaltet eine fahrtenbuch.db SQLite-Datenbank.

    Jedes Fahrtenbuch hat eine eigene Datenbank in seinem Verzeichnis.
    """

    DB_FILENAME = "fahrtenbuch.db"

    def __init__(self, path: Path) -> None:
        self._path = path
        self._db_file = path / self.DB_FILENAME
        self._conn: sqlite3.Connection | None = None

    @property
    def path(self) -> Path:
        """Pfad zum Fahrtenbuch-Verzeichnis."""
        return self._path

    @property
    def db_file(self) -> Path:
        """Pfad zur Datenbankdatei."""
        return self._db_file

    @property
    def is_open(self) -> bool:
        """Prueft ob die Datenbank geoeffnet ist."""
        return self._conn is not None

    def open(self) -> None:
        """Oeffnet die Datenbank und erstellt das Schema falls noetig."""
        self._path.mkdir(parents=True, exist_ok=True)
        belege_dir = self._path / "belege"
        belege_dir.mkdir(parents=True, exist_ok=True)

        self._conn = sqlite3.connect(str(self._db_file))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._init_schema()

    def close(self) -> None:
        """Schliesst die Datenbank."""
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def _get_conn(self) -> sqlite3.Connection:
        """Gibt die aktive Verbindung zurueck oder wirft einen Fehler."""
        if self._conn is None:
            raise RuntimeError("Datenbank ist nicht geoeffnet")
        return self._conn

    def _init_schema(self) -> None:
        """Erstellt die Datenbanktabellen falls sie noch nicht existieren."""
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS vehicle (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                name TEXT NOT NULL DEFAULT '',
                plate TEXT NOT NULL DEFAULT '',
                contract_number TEXT NOT NULL DEFAULT '',
                lease_km_per_month INTEGER NOT NULL DEFAULT 1500,
                start_km INTEGER NOT NULL DEFAULT 0,
                end_km INTEGER NOT NULL DEFAULT 0,
                start_date TEXT NOT NULL DEFAULT '',
                end_date TEXT NOT NULL DEFAULT '',
                lease_months INTEGER NOT NULL DEFAULT 12
            );

            CREATE TABLE IF NOT EXISTS trips (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                time_from TEXT NOT NULL DEFAULT '',
                time_to TEXT NOT NULL DEFAULT '',
                destination TEXT NOT NULL DEFAULT '',
                purpose TEXT NOT NULL DEFAULT '',
                km_start INTEGER NOT NULL DEFAULT 0,
                km_end INTEGER NOT NULL DEFAULT 0,
                km_business INTEGER NOT NULL DEFAULT 0,
                km_private INTEGER NOT NULL DEFAULT 0,
                category TEXT NOT NULL DEFAULT 'business'
                    CHECK (category IN ('business', 'private', 'fuel', 'service'))
            );

            CREATE INDEX IF NOT EXISTS idx_trips_date ON trips (date);

            CREATE TABLE IF NOT EXISTS addresses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL DEFAULT 'customer'
                    CHECK (category IN (
                        'customer', 'gas_station', 'shopping',
                        'steuerberaterin', 'restaurant'
                    )),
                name TEXT NOT NULL DEFAULT '',
                address TEXT NOT NULL DEFAULT '',
                km REAL NOT NULL DEFAULT 0.0
            );

            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS blacklist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                reason TEXT NOT NULL DEFAULT '',
                allow_private INTEGER NOT NULL DEFAULT 0
            );
        """)
        conn.commit()

    # ------------------------------------------------------------------
    # Vehicle
    # ------------------------------------------------------------------

    def get_vehicle(self) -> Vehicle:
        """Laedt das Fahrzeug aus der Datenbank."""
        conn = self._get_conn()
        row = conn.execute("SELECT * FROM vehicle WHERE id = 1").fetchone()
        if row is None:
            return Vehicle()
        return Vehicle(
            name=row["name"],
            plate=row["plate"],
            contract_number=row["contract_number"],
            lease_km_per_month=row["lease_km_per_month"],
            start_km=row["start_km"],
            end_km=row["end_km"],
            start_date=row["start_date"],
            end_date=row["end_date"],
            lease_months=row["lease_months"],
        )

    def save_vehicle(self, vehicle: Vehicle) -> None:
        """Speichert das Fahrzeug in die Datenbank (upsert)."""
        conn = self._get_conn()
        conn.execute(
            """
            INSERT INTO vehicle (id, name, plate, contract_number,
                lease_km_per_month, start_km, end_km,
                start_date, end_date, lease_months)
            VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name = excluded.name,
                plate = excluded.plate,
                contract_number = excluded.contract_number,
                lease_km_per_month = excluded.lease_km_per_month,
                start_km = excluded.start_km,
                end_km = excluded.end_km,
                start_date = excluded.start_date,
                end_date = excluded.end_date,
                lease_months = excluded.lease_months
            """,
            (
                vehicle.name, vehicle.plate, vehicle.contract_number,
                vehicle.lease_km_per_month, vehicle.start_km, vehicle.end_km,
                vehicle.start_date, vehicle.end_date, vehicle.lease_months,
            ),
        )
        conn.commit()

    # ------------------------------------------------------------------
    # Trips
    # ------------------------------------------------------------------

    def add_trip(self, trip: Trip) -> int:
        """Fuegt eine neue Fahrt hinzu und gibt die ID zurueck."""
        conn = self._get_conn()
        cursor = conn.execute(
            """
            INSERT INTO trips (date, time_from, time_to, destination, purpose,
                km_start, km_end, km_business, km_private, category)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                trip.date, trip.time_from, trip.time_to,
                trip.destination, trip.purpose,
                trip.km_start, trip.km_end,
                trip.km_business, trip.km_private, trip.category,
            ),
        )
        conn.commit()
        return cursor.lastrowid or 0

    def update_trip(self, trip_id: int, trip: Trip) -> None:
        """Aktualisiert eine bestehende Fahrt."""
        conn = self._get_conn()
        conn.execute(
            """
            UPDATE trips SET
                date = ?, time_from = ?, time_to = ?,
                destination = ?, purpose = ?,
                km_start = ?, km_end = ?,
                km_business = ?, km_private = ?, category = ?
            WHERE id = ?
            """,
            (
                trip.date, trip.time_from, trip.time_to,
                trip.destination, trip.purpose,
                trip.km_start, trip.km_end,
                trip.km_business, trip.km_private, trip.category,
                trip_id,
            ),
        )
        conn.commit()

    def delete_trip(self, trip_id: int) -> None:
        """Loescht eine Fahrt anhand der ID."""
        conn = self._get_conn()
        conn.execute("DELETE FROM trips WHERE id = ?", (trip_id,))
        conn.commit()

    def get_trips_for_month(self, year: int, month: int) -> list[Trip]:
        """Gibt alle Fahrten eines Monats zurueck, sortiert nach Datum und km_start."""
        conn = self._get_conn()
        month_prefix = f"{year}-{month:02d}"
        rows = conn.execute(
            """
            SELECT * FROM trips
            WHERE date LIKE ? || '%'
            ORDER BY date, km_start
            """,
            (month_prefix,),
        ).fetchall()
        return [self._row_to_trip(row) for row in rows]

    def get_month_data(self, year: int, month: int) -> MonthData:
        """Gibt MonthData fuer einen Monat zurueck."""
        trips = self.get_trips_for_month(year, month)
        return MonthData(year=year, month=month, trips=trips)

    def get_first_trip_date(self) -> tuple[int, int] | None:
        """Gibt (year, month) des ersten Trips zurueck, oder None."""
        conn = self._get_conn()
        row = conn.execute("SELECT MIN(date) FROM trips").fetchone()
        if row and row[0]:
            parts = row[0].split("-")
            if len(parts) >= 2:
                return int(parts[0]), int(parts[1])
        return None

    def get_all_month_data(self, year: int) -> dict[int, MonthData]:
        """Gibt MonthData fuer alle 12 Monate eines Jahres zurueck."""
        result: dict[int, MonthData] = {}
        for month in range(1, 13):
            result[month] = self.get_month_data(year, month)
        return result

    def get_last_km_end(self, year: int, month: int) -> int:
        """Gibt den letzten km_end-Wert fuer einen Monat zurueck."""
        conn = self._get_conn()
        month_prefix = f"{year}-{month:02d}"
        row = conn.execute(
            """
            SELECT km_end FROM trips
            WHERE date LIKE ? || '%'
            ORDER BY date DESC, km_start DESC
            LIMIT 1
            """,
            (month_prefix,),
        ).fetchone()
        return row["km_end"] if row else 0

    @staticmethod
    def _row_to_trip(row: sqlite3.Row) -> Trip:
        """Konvertiert eine Datenbankzeile in ein Trip-Objekt."""
        return Trip(
            id=row["id"],
            date=row["date"],
            time_from=row["time_from"],
            time_to=row["time_to"],
            destination=row["destination"],
            purpose=row["purpose"],
            km_start=row["km_start"],
            km_end=row["km_end"],
            km_business=row["km_business"],
            km_private=row["km_private"],
            category=row["category"],
        )

    # ------------------------------------------------------------------
    # Addresses
    # ------------------------------------------------------------------

    def get_addresses(self, category: str | None = None) -> list[dict[str, object]]:
        """Gibt Adressen zurueck, optional gefiltert nach Kategorie."""
        conn = self._get_conn()
        if category:
            rows = conn.execute(
                "SELECT * FROM addresses WHERE category = ? ORDER BY name",
                (category,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM addresses ORDER BY category, name"
            ).fetchall()
        return [dict(row) for row in rows]

    def add_address(
        self, category: str, name: str, address: str, km: float
    ) -> int:
        """Fuegt eine neue Adresse hinzu und gibt die ID zurueck."""
        conn = self._get_conn()
        cursor = conn.execute(
            """
            INSERT INTO addresses (category, name, address, km)
            VALUES (?, ?, ?, ?)
            """,
            (category, name, address, km),
        )
        conn.commit()
        return cursor.lastrowid or 0

    def update_address(
        self, address_id: int, name: str, address: str, km: float
    ) -> None:
        """Aktualisiert eine bestehende Adresse."""
        conn = self._get_conn()
        conn.execute(
            """
            UPDATE addresses SET name = ?, address = ?, km = ?
            WHERE id = ?
            """,
            (name, address, km, address_id),
        )
        conn.commit()

    def delete_address(self, address_id: int) -> None:
        """Loescht eine Adresse anhand der ID."""
        conn = self._get_conn()
        conn.execute("DELETE FROM addresses WHERE id = ?", (address_id,))
        conn.commit()

    # ------------------------------------------------------------------
    # Settings (Key-Value)
    # ------------------------------------------------------------------

    def get_setting(self, key: str, default: str = "") -> str:
        """Liest einen Einstellungswert aus der Datenbank."""
        conn = self._get_conn()
        row = conn.execute(
            "SELECT value FROM settings WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row else default

    def set_setting(self, key: str, value: str) -> None:
        """Setzt einen Einstellungswert in der Datenbank (upsert)."""
        conn = self._get_conn()
        conn.execute(
            """
            INSERT INTO settings (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (key, value),
        )
        conn.commit()

    # ------------------------------------------------------------------
    # Blacklist
    # ------------------------------------------------------------------

    def get_blacklist(self) -> list[dict[str, object]]:
        """Gibt alle Blacklist-Eintraege zurueck."""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM blacklist ORDER BY date"
        ).fetchall()
        return [dict(row) for row in rows]

    def add_blacklist_entry(
        self, date: str, reason: str, allow_private: bool = False
    ) -> int:
        """Fuegt einen Blacklist-Eintrag hinzu und gibt die ID zurueck."""
        conn = self._get_conn()
        cursor = conn.execute(
            """
            INSERT INTO blacklist (date, reason, allow_private)
            VALUES (?, ?, ?)
            """,
            (date, reason, 1 if allow_private else 0),
        )
        conn.commit()
        return cursor.lastrowid or 0

    def delete_blacklist_entry(self, entry_id: int) -> None:
        """Loescht einen Blacklist-Eintrag."""
        conn = self._get_conn()
        conn.execute("DELETE FROM blacklist WHERE id = ?", (entry_id,))
        conn.commit()
