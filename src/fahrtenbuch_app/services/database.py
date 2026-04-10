"""SQLite-basierte Datenhaltung fuer ein einzelnes Fahrtenbuch."""

import getpass
import sqlite3
from datetime import datetime
from pathlib import Path

from fahrtenbuch_app.models.trip import MonthData, Trip
from fahrtenbuch_app.models.vehicle import Vehicle


# Tabellen, die Audit-Spalten bekommen (siehe _migrate_add_audit_columns).
# documents hat bereits created_at — deshalb separate Liste.
_AUDIT_TABLES_FULL: tuple[str, ...] = (
    "vehicle",
    "trips",
    "addresses",
    "settings",
    "blacklist",
    "worktimes",
    "categories",
)
_AUDIT_TABLES_WITHOUT_CREATED_AT: tuple[str, ...] = ("documents",)
_AUDIT_COLUMNS_FULL: tuple[str, ...] = (
    "created_at",
    "created_by",
    "changed_at",
    "changed_by",
)
_AUDIT_COLUMNS_NO_CREATED_AT: tuple[str, ...] = (
    "created_by",
    "changed_at",
    "changed_by",
)


def _audit_now() -> str:
    """Aktueller Zeitstempel im ISO-Format fuer Audit-Felder."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _audit_user() -> str:
    """Name des aktuellen OS-Users fuer Audit-Felder."""
    try:
        return getpass.getuser()
    except Exception:
        return ""


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

        self._conn = sqlite3.connect(str(self._db_file), timeout=10.0)
        self._conn.row_factory = sqlite3.Row
        # 10 Sekunden auf Locks warten, bevor "database is locked" kommt.
        # Hilft gegen kurzzeitig offene Reader (DB Browser o.ae.).
        self._conn.execute("PRAGMA busy_timeout=10000")
        self._conn.execute("PRAGMA foreign_keys=ON")
        # Schema muss vor dem Lesen des journal_mode-Settings existieren,
        # sonst gibt es die settings-Tabelle beim Erstkontakt noch nicht.
        self._init_schema()
        self._apply_journal_mode_setting()

    def _apply_journal_mode_setting(self) -> None:
        """Liest das gewuenschte journal_mode-Setting und setzt es ggf. um.

        Erlaubte Werte: DELETE (Default, Dropbox-sicher), WAL, TRUNCATE,
        PERSIST, MEMORY, OFF. Wird nur umgestellt, wenn der aktuelle Modus
        vom Wunsch abweicht — das vermeidet unnoetige Schreib-Locks beim
        Oeffnen.
        """
        if self._conn is None:
            return
        allowed = {"DELETE", "WAL", "TRUNCATE", "PERSIST", "MEMORY", "OFF"}
        wanted = self.get_setting("db_journal_mode", "DELETE").upper()
        if wanted not in allowed:
            wanted = "DELETE"
        current_row = self._conn.execute("PRAGMA journal_mode").fetchone()
        current = str(current_row[0]).upper() if current_row else ""
        if current != wanted:
            self._conn.execute(f"PRAGMA journal_mode={wanted}")

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
                category TEXT NOT NULL DEFAULT 'business',
                round_trip INTEGER NOT NULL DEFAULT 0
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
                reason TEXT NOT NULL DEFAULT ''
            );

            CREATE TABLE IF NOT EXISTS documents (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trip_id INTEGER REFERENCES trips(id) ON DELETE CASCADE,
                blacklist_id INTEGER REFERENCES blacklist(id) ON DELETE CASCADE,
                path TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
            );

            CREATE TABLE IF NOT EXISTS worktimes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                year INTEGER NOT NULL,
                month INTEGER NOT NULL,
                hours REAL NOT NULL DEFAULT 0.0,
                UNIQUE(year, month)
            );

            CREATE TABLE IF NOT EXISTS categories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                display_name TEXT NOT NULL,
                counts_as_business INTEGER NOT NULL DEFAULT 1,
                color TEXT NOT NULL DEFAULT 'green'
            );
        """)
        conn.commit()
        self._migrate_trips_check_constraint()
        self._migrate_trips_add_round_trip()
        self._migrate_blacklist_remove_allow_private()
        self._migrate_addresses_remove_category_check()
        self._seed_default_categories()
        self._migrate_add_fuel_private_category()
        self._migrate_add_audit_columns()

    def _migrate_add_audit_columns(self) -> None:
        """Fuegt created_at/created_by/changed_at/changed_by als NULL-Spalten
        in alle Tabellen ein. Dokumente behalten ihre bestehende created_at
        Spalte und bekommen nur die restlichen drei dazu.
        """
        conn = self._get_conn()
        for table in _AUDIT_TABLES_FULL:
            self._add_missing_columns(table, _AUDIT_COLUMNS_FULL)
        for table in _AUDIT_TABLES_WITHOUT_CREATED_AT:
            self._add_missing_columns(table, _AUDIT_COLUMNS_NO_CREATED_AT)
        conn.commit()

    def _add_missing_columns(
        self, table: str, columns: tuple[str, ...]
    ) -> None:
        """Fuegt die angegebenen Audit-Spalten als TEXT NULL hinzu, sofern
        sie noch nicht existieren. Idempotent — ueberspringt vorhandene.
        """
        conn = self._get_conn()
        # Existierende Spalten einsammeln
        rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
        existing = {str(row[1]) for row in rows}
        for col in columns:
            if col in existing:
                continue
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {col} TEXT")

    def _migrate_trips_check_constraint(self) -> None:
        """Entfernt die CHECK-Constraint auf trips.category falls vorhanden.

        SQLite erlaubt kein ALTER TABLE DROP CONSTRAINT, daher wird die
        Tabelle neu erstellt falls die alte Constraint noch existiert.
        """
        conn = self._get_conn()
        row = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='trips'"
        ).fetchone()
        if row is None:
            return

        create_sql = row[0] or ""
        if "CHECK" not in create_sql.upper():
            return

        conn.executescript("""
            ALTER TABLE trips RENAME TO trips_old;

            CREATE TABLE trips (
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
            );

            INSERT INTO trips SELECT * FROM trips_old;
            DROP TABLE trips_old;

            CREATE INDEX IF NOT EXISTS idx_trips_date ON trips (date);
        """)
        conn.commit()

    def _migrate_trips_add_round_trip(self) -> None:
        """Fuegt die round_trip-Spalte zur trips-Tabelle hinzu falls noch nicht vorhanden."""
        conn = self._get_conn()
        row = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='trips'"
        ).fetchone()
        if row is None:
            return
        create_sql = row[0] or ""
        if "round_trip" in create_sql.lower():
            return
        conn.execute(
            "ALTER TABLE trips ADD COLUMN round_trip INTEGER NOT NULL DEFAULT 0"
        )
        conn.commit()

    def _migrate_blacklist_remove_allow_private(self) -> None:
        """Entfernt die allow_private-Spalte aus der blacklist-Tabelle falls vorhanden."""
        conn = self._get_conn()
        row = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='blacklist'"
        ).fetchone()
        if row is None:
            return
        create_sql = row[0] or ""
        if "allow_private" not in create_sql.lower():
            return
        conn.executescript("""
            ALTER TABLE blacklist RENAME TO blacklist_old;
            CREATE TABLE blacklist (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                date TEXT NOT NULL,
                reason TEXT NOT NULL DEFAULT ''
            );
            INSERT INTO blacklist (id, date, reason)
                SELECT id, date, reason FROM blacklist_old;
            DROP TABLE blacklist_old;
        """)
        conn.commit()

    def _seed_default_categories(self) -> None:
        """Fuegt die Standard-Kategorien ein, falls die Tabelle leer ist."""
        conn = self._get_conn()
        count = conn.execute("SELECT COUNT(*) FROM categories").fetchone()[0]
        if count > 0:
            return

        defaults = [
            ("business", "Geschaeftlich", 1, "green"),
            ("private", "Privat", 0, "blue"),
            ("fuel", "Tanken", 1, "yellow"),
            ("fuel_private", "Tanken nach Privatfahrt", 0, "cyan"),
            ("service", "Service (TUeV, Reifen, ...)", 1, "magenta"),
        ]
        conn.executemany(
            """
            INSERT INTO categories (name, display_name, counts_as_business, color)
            VALUES (?, ?, ?, ?)
            """,
            defaults,
        )
        conn.commit()

    def _migrate_add_fuel_private_category(self) -> None:
        """Fuegt die Kategorie 'fuel_private' in bestehende DBs ein, falls fehlend."""
        conn = self._get_conn()
        row = conn.execute(
            "SELECT COUNT(*) FROM categories WHERE name = ?",
            ("fuel_private",),
        ).fetchone()
        if row and row[0] > 0:
            return
        conn.execute(
            """
            INSERT INTO categories (name, display_name, counts_as_business, color)
            VALUES (?, ?, ?, ?)
            """,
            ("fuel_private", "Tanken nach Privatfahrt", 0, "cyan"),
        )
        conn.commit()

    # ------------------------------------------------------------------
    # Categories
    # ------------------------------------------------------------------

    def get_categories(self) -> list[dict[str, object]]:
        """Gibt alle Kategorien zurueck."""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM categories ORDER BY id"
        ).fetchall()
        return [dict(row) for row in rows]

    def get_business_category_names(self) -> set[str]:
        """Gibt die Namen aller Kategorien zurueck, die als geschaeftlich zaehlen."""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT name FROM categories WHERE counts_as_business = 1"
        ).fetchall()
        return {row["name"] for row in rows}

    def get_category_colors(self) -> dict[str, str]:
        """Gibt ein Mapping von Kategorie-Name zu Farbe zurueck."""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT name, color FROM categories ORDER BY id"
        ).fetchall()
        return {row["name"]: row["color"] for row in rows}

    def get_category_options(self) -> list[tuple[str, str]]:
        """Gibt Kategorien als (display_name, name)-Tupel fuer Select-Widgets zurueck."""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT name, display_name FROM categories ORDER BY id"
        ).fetchall()
        return [(row["display_name"], row["name"]) for row in rows]

    def add_category(
        self,
        name: str,
        display_name: str,
        counts_as_business: bool,
        color: str,
    ) -> int:
        """Fuegt eine neue Kategorie hinzu und gibt die ID zurueck."""
        conn = self._get_conn()
        now = _audit_now()
        user = _audit_user()
        cursor = conn.execute(
            """
            INSERT INTO categories (
                name, display_name, counts_as_business, color,
                created_at, created_by
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                name, display_name, 1 if counts_as_business else 0, color,
                now, user,
            ),
        )
        conn.commit()
        return cursor.lastrowid or 0

    def update_category(
        self,
        category_id: int,
        name: str,
        display_name: str,
        counts_as_business: bool,
        color: str,
    ) -> None:
        """Aktualisiert eine bestehende Kategorie."""
        conn = self._get_conn()
        conn.execute(
            """
            UPDATE categories SET
                name = ?, display_name = ?,
                counts_as_business = ?, color = ?,
                changed_at = ?, changed_by = ?
            WHERE id = ?
            """,
            (
                name, display_name, 1 if counts_as_business else 0, color,
                _audit_now(), _audit_user(), category_id,
            ),
        )
        conn.commit()

    def delete_category(self, category_id: int) -> None:
        """Loescht eine Kategorie anhand der ID."""
        conn = self._get_conn()
        conn.execute("DELETE FROM categories WHERE id = ?", (category_id,))
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
        now = _audit_now()
        user = _audit_user()
        conn.execute(
            """
            INSERT INTO vehicle (id, name, plate, contract_number,
                lease_km_per_month, start_km, end_km,
                start_date, end_date, lease_months,
                created_at, created_by, changed_at, changed_by)
            VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL)
            ON CONFLICT(id) DO UPDATE SET
                name = excluded.name,
                plate = excluded.plate,
                contract_number = excluded.contract_number,
                lease_km_per_month = excluded.lease_km_per_month,
                start_km = excluded.start_km,
                end_km = excluded.end_km,
                start_date = excluded.start_date,
                end_date = excluded.end_date,
                lease_months = excluded.lease_months,
                changed_at = excluded.created_at,
                changed_by = excluded.created_by
            """,
            (
                vehicle.name, vehicle.plate, vehicle.contract_number,
                vehicle.lease_km_per_month, vehicle.start_km, vehicle.end_km,
                vehicle.start_date, vehicle.end_date, vehicle.lease_months,
                now, user,
            ),
        )
        conn.commit()

    # ------------------------------------------------------------------
    # Trips
    # ------------------------------------------------------------------

    def get_km_end_before(
        self, date_iso: str, exclude_trip_id: int | None = None
    ) -> int:
        """Gibt km_end des chronologischen Vorgaengers zurueck.

        Vorgaenger eines NEUEN Trips (exclude_trip_id is None): letzter Trip
        mit date <= date_iso. Der neue Trip wird beim Insert die hoechste id
        bekommen und damit innerhalb des Tages ans Ende sortiert — alle
        bestehenden same-day-Trips sind also seine Vorgaenger.

        Vorgaenger eines BESTEHENDEN Trips (exclude_trip_id gesetzt): letzter
        Trip mit date < exclude_trip_date oder (date = exclude_trip_date und
        id < exclude_trip_id). Sortierung in der Kette ist (date, id).

        Fallback wenn nichts gefunden: vehicle.start_km.
        """
        conn = self._get_conn()
        if exclude_trip_id is not None:
            row = conn.execute(
                """
                SELECT km_end FROM trips
                WHERE (date < ?)
                   OR (date = ? AND id < ?)
                ORDER BY date DESC, id DESC
                LIMIT 1
                """,
                (date_iso, date_iso, exclude_trip_id),
            ).fetchone()
        else:
            row = conn.execute(
                """
                SELECT km_end FROM trips
                WHERE date <= ?
                ORDER BY date DESC, id DESC
                LIMIT 1
                """,
                (date_iso,),
            ).fetchone()
        if row is not None:
            return int(row["km_end"])
        vehicle = self.get_vehicle()
        return vehicle.start_km

    def _shift_trips_after(
        self, date_iso: str, delta: int, exclude_trip_id: int | None = None
    ) -> None:
        """Verschiebt km_start/km_end aller Trips nach date_iso um delta.

        Bei gleichem Datum werden nur Trips mit id > exclude_trip_id verschoben,
        so dass der gerade eingefuegte Trip nicht sich selbst anfasst.
        """
        if delta == 0:
            return
        conn = self._get_conn()
        if exclude_trip_id is not None:
            conn.execute(
                """
                UPDATE trips
                SET km_start = km_start + ?, km_end = km_end + ?
                WHERE (date > ?)
                   OR (date = ? AND id > ?)
                """,
                (delta, delta, date_iso, date_iso, exclude_trip_id),
            )
        else:
            conn.execute(
                """
                UPDATE trips
                SET km_start = km_start + ?, km_end = km_end + ?
                WHERE date > ?
                """,
                (delta, delta, date_iso),
            )

    def add_trip(self, trip: Trip) -> int:
        """Fuegt eine neue Fahrt hinzu und baut die km-Kette auf.

        km_start wird aus dem chronologischen Vorgaenger bestimmt (ignoriert den
        vom User eingetragenen Wert). km_end wird so gesetzt, dass die vom User
        eingegebene Distanz (km_end - km_start) erhalten bleibt. Alle nachfolgenden
        Trips werden um diese Distanz verschoben. Bei Ueberschreitung der
        Fahrzeug-Endkilometer wird die Transaktion zurueckgerollt.
        """
        distance = max(0, trip.km_end - trip.km_start)
        conn = self._get_conn()
        try:
            conn.execute("BEGIN")
            predecessor_km = self.get_km_end_before(trip.date)
            new_km_start = predecessor_km
            new_km_end = new_km_start + distance

            cursor = conn.execute(
                """
                INSERT INTO trips (date, time_from, time_to, destination, purpose,
                    km_start, km_end, km_business, km_private, category, round_trip,
                    created_at, created_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    trip.date, trip.time_from, trip.time_to,
                    trip.destination, trip.purpose,
                    new_km_start, new_km_end,
                    trip.km_business, trip.km_private, trip.category,
                    1 if trip.round_trip else 0,
                    _audit_now(), _audit_user(),
                ),
            )
            new_id = cursor.lastrowid or 0
            # Alle Nachfolger um die Distanz dieser Fahrt nach oben verschieben
            self._shift_trips_after(trip.date, distance, exclude_trip_id=new_id)
            conn.commit()
            return new_id
        except Exception:
            conn.rollback()
            raise

    def update_trip(self, trip_id: int, trip: Trip) -> None:
        """Aktualisiert eine bestehende Fahrt und pflegt die km-Kette.

        Bei Datumsaenderung werden die alten Nachfolger zurueckgerollt, der Trip
        an neuer Position plaziert und die neuen Nachfolger um die Distanz
        verschoben. Bei geaenderter Distanz werden die Nachfolger um das Delta
        verschoben. Bei Ueberschreitung der Fahrzeug-Endkilometer erfolgt
        Rollback.
        """
        conn = self._get_conn()
        old = self.get_trip_by_id(trip_id)
        if old is None:
            raise ValueError(f"Trip {trip_id} nicht gefunden")

        old_distance = max(0, old.km_end - old.km_start)
        new_distance = max(0, trip.km_end - trip.km_start)

        try:
            conn.execute("BEGIN")
            if trip.date == old.date:
                # Datum unveraendert: km_start bleibt wie gehabt,
                # km_end nach neuer Distanz, Nachfolger um delta shiften.
                delta = new_distance - old_distance
                conn.execute(
                    """
                    UPDATE trips SET
                        date = ?, time_from = ?, time_to = ?,
                        destination = ?, purpose = ?,
                        km_start = ?, km_end = ?,
                        km_business = ?, km_private = ?, category = ?,
                        round_trip = ?,
                        changed_at = ?, changed_by = ?
                    WHERE id = ?
                    """,
                    (
                        trip.date, trip.time_from, trip.time_to,
                        trip.destination, trip.purpose,
                        old.km_start, old.km_start + new_distance,
                        trip.km_business, trip.km_private, trip.category,
                        1 if trip.round_trip else 0,
                        _audit_now(), _audit_user(),
                        trip_id,
                    ),
                )
                self._shift_trips_after(trip.date, delta, exclude_trip_id=trip_id)
            else:
                # Datum geaendert: zuerst alte Nachfolger rueckabwickeln
                self._shift_trips_after(
                    old.date, -old_distance, exclude_trip_id=trip_id
                )
                # Neue km_start aus neuem Vorgaenger
                predecessor_km = self.get_km_end_before(
                    trip.date, exclude_trip_id=trip_id
                )
                new_km_start = predecessor_km
                new_km_end = new_km_start + new_distance
                conn.execute(
                    """
                    UPDATE trips SET
                        date = ?, time_from = ?, time_to = ?,
                        destination = ?, purpose = ?,
                        km_start = ?, km_end = ?,
                        km_business = ?, km_private = ?, category = ?,
                        round_trip = ?,
                        changed_at = ?, changed_by = ?
                    WHERE id = ?
                    """,
                    (
                        trip.date, trip.time_from, trip.time_to,
                        trip.destination, trip.purpose,
                        new_km_start, new_km_end,
                        trip.km_business, trip.km_private, trip.category,
                        1 if trip.round_trip else 0,
                        _audit_now(), _audit_user(),
                        trip_id,
                    ),
                )
                self._shift_trips_after(
                    trip.date, new_distance, exclude_trip_id=trip_id
                )
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    def delete_trip(self, trip_id: int) -> None:
        """Loescht eine Fahrt und rollt die Nachfolger zurueck."""
        conn = self._get_conn()
        old = self.get_trip_by_id(trip_id)
        if old is None:
            return
        old_distance = max(0, old.km_end - old.km_start)
        try:
            conn.execute("BEGIN")
            conn.execute("DELETE FROM trips WHERE id = ?", (trip_id,))
            self._shift_trips_after(old.date, -old_distance, exclude_trip_id=trip_id)
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    def rebuild_all_km(self) -> tuple[int, int]:
        """Baut die km-Kette aller Fahrten chronologisch neu auf.

        Die Distanz jedes Trips (km_end - km_start) bleibt erhalten. km_start
        wird auf den akkumulierten Stand gesetzt, beginnend mit vehicle.start_km.
        Rueckgabe: (Anzahl veraenderte Trips, finaler km-Stand).
        Wirft ValueError, wenn vehicle.end_km ueberschritten wuerde.
        """
        conn = self._get_conn()
        vehicle = self.get_vehicle()
        cursor_state = vehicle.start_km
        rows = conn.execute(
            "SELECT id, km_start, km_end FROM trips ORDER BY date, id"
        ).fetchall()

        changes: list[tuple[int, int, int]] = []  # (id, new_start, new_end)
        for row in rows:
            distance = max(0, int(row["km_end"]) - int(row["km_start"]))
            new_start = cursor_state
            new_end = new_start + distance
            changes.append((int(row["id"]), new_start, new_end))
            cursor_state = new_end

        if vehicle.end_km > 0 and cursor_state > vehicle.end_km:
            raise ValueError(
                f"Rebuild wuerde Endkilometerstand ueberschreiten: "
                f"{cursor_state} km > {vehicle.end_km} km"
            )

        changed_count = 0
        now = _audit_now()
        user = _audit_user()
        try:
            conn.execute("BEGIN")
            for trip_id, new_start, new_end in changes:
                conn.execute(
                    """
                    UPDATE trips SET
                        km_start = ?, km_end = ?,
                        changed_at = ?, changed_by = ?
                    WHERE id = ?
                    """,
                    (new_start, new_end, now, user, trip_id),
                )
                changed_count += 1
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        return changed_count, cursor_state

    def get_trip_by_id(self, trip_id: int) -> Trip | None:
        """Gibt eine einzelne Fahrt anhand der ID zurueck."""
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM trips WHERE id = ?",
            (trip_id,),
        ).fetchone()
        return self._row_to_trip(row) if row else None

    def get_audit_info(
        self, table: str, row_id: int, id_column: str = "id"
    ) -> dict[str, str]:
        """Liest die Audit-Spalten einer Zeile und gibt sie als Dict zurueck.

        Fehlende/NULL-Werte kommen als leerer String zurueck. Der table- und
        id_column-Parameter wird direkt in SQL eingesetzt, daher duerfen hier
        nur intern bekannte Tabellennamen reingereicht werden — keine
        User-Eingaben.
        """
        conn = self._get_conn()
        row = conn.execute(
            f"SELECT created_at, created_by, changed_at, changed_by "
            f"FROM {table} WHERE {id_column} = ?",
            (row_id,),
        ).fetchone()
        if row is None:
            return {
                "created_at": "", "created_by": "",
                "changed_at": "", "changed_by": "",
            }
        return {
            "created_at": str(row["created_at"] or ""),
            "created_by": str(row["created_by"] or ""),
            "changed_at": str(row["changed_at"] or ""),
            "changed_by": str(row["changed_by"] or ""),
        }

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

    def get_trips_for_year(self, year: int) -> list[Trip]:
        """Gibt alle Fahrten eines Jahres zurueck, sortiert nach Datum und km_start."""
        conn = self._get_conn()
        year_prefix = f"{year}-"
        rows = conn.execute(
            """
            SELECT * FROM trips
            WHERE date LIKE ? || '%'
            ORDER BY date, km_start
            """,
            (year_prefix,),
        ).fetchall()
        return [self._row_to_trip(row) for row in rows]

    def get_year_data(self, year: int) -> MonthData:
        """Gibt MonthData mit allen Fahrten eines Jahres zurueck (month=0 als Marker)."""
        trips = self.get_trips_for_year(year)
        return MonthData(year=year, month=0, trips=trips)

    def get_all_trips_ordered(self) -> list[Trip]:
        """Gibt alle Trips der Datenbank zurueck, sortiert nach (date, id).

        Diese Reihenfolge entspricht der kanonischen km-Kette und wird von
        Plausibilitaets-Checks und Tests verwendet.
        """
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM trips ORDER BY date, id"
        ).fetchall()
        return [self._row_to_trip(row) for row in rows]

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
            round_trip=bool(row["round_trip"]),
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
            INSERT INTO addresses (
                category, name, address, km, created_at, created_by
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (category, name, address, km, _audit_now(), _audit_user()),
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
            UPDATE addresses SET
                name = ?, address = ?, km = ?,
                changed_at = ?, changed_by = ?
            WHERE id = ?
            """,
            (name, address, km, _audit_now(), _audit_user(), address_id),
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
        now = _audit_now()
        user = _audit_user()
        conn.execute(
            """
            INSERT INTO settings (key, value, created_at, created_by)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                changed_at = excluded.created_at,
                changed_by = excluded.created_by
            """,
            (key, value, now, user),
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

    def add_blacklist_entry(self, date: str, reason: str) -> int:
        """Fuegt einen Blacklist-Eintrag hinzu und gibt die ID zurueck."""
        conn = self._get_conn()
        cursor = conn.execute(
            """
            INSERT INTO blacklist (date, reason, created_at, created_by)
            VALUES (?, ?, ?, ?)
            """,
            (date, reason, _audit_now(), _audit_user()),
        )
        conn.commit()
        return cursor.lastrowid or 0

    def update_blacklist_entry(self, entry_id: int, date: str, reason: str) -> None:
        """Aktualisiert Datum und Grund eines Blacklist-Eintrags."""
        conn = self._get_conn()
        conn.execute(
            """
            UPDATE blacklist SET
                date = ?, reason = ?,
                changed_at = ?, changed_by = ?
            WHERE id = ?
            """,
            (date, reason, _audit_now(), _audit_user(), entry_id),
        )
        conn.commit()

    def delete_blacklist_entry(self, entry_id: int) -> None:
        """Loescht einen Blacklist-Eintrag."""
        conn = self._get_conn()
        conn.execute("DELETE FROM blacklist WHERE id = ?", (entry_id,))
        conn.commit()

    def _migrate_addresses_remove_category_check(self) -> None:
        """Entfernt die CHECK-Constraint auf addresses.category (fehlte 'other')."""
        conn = self._get_conn()
        row = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='addresses'"
        ).fetchone()
        if row is None:
            return
        create_sql = row[0] or ""
        if "CHECK" not in create_sql.upper():
            return
        conn.executescript("""
            ALTER TABLE addresses RENAME TO addresses_old;
            CREATE TABLE addresses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                category TEXT NOT NULL DEFAULT 'customer',
                name TEXT NOT NULL DEFAULT '',
                address TEXT NOT NULL DEFAULT '',
                km REAL NOT NULL DEFAULT 0.0
            );
            INSERT INTO addresses SELECT * FROM addresses_old;
            DROP TABLE addresses_old;
        """)
        conn.commit()

    # ------------------------------------------------------------------
    # Documents
    # ------------------------------------------------------------------

    def get_documents(
        self,
        trip_id: int | None = None,
        blacklist_id: int | None = None,
    ) -> list[dict[str, object]]:
        """Gibt alle Dokumente fuer einen Trip oder Blacklist-Eintrag zurueck."""
        conn = self._get_conn()
        if trip_id is not None:
            rows = conn.execute(
                "SELECT * FROM documents WHERE trip_id = ? ORDER BY created_at",
                (trip_id,),
            ).fetchall()
        elif blacklist_id is not None:
            rows = conn.execute(
                "SELECT * FROM documents WHERE blacklist_id = ? ORDER BY created_at",
                (blacklist_id,),
            ).fetchall()
        else:
            rows = []
        return [dict(row) for row in rows]

    def add_document(
        self,
        path: str,
        description: str = "",
        trip_id: int | None = None,
        blacklist_id: int | None = None,
    ) -> int:
        """Fuegt ein Dokument hinzu und gibt die ID zurueck."""
        conn = self._get_conn()
        # documents.created_at existiert bereits mit DEFAULT datetime('now',...)
        # — wir setzen hier nur created_by mit dem Windows-User.
        cursor = conn.execute(
            """
            INSERT INTO documents (
                trip_id, blacklist_id, path, description, created_by
            )
            VALUES (?, ?, ?, ?, ?)
            """,
            (trip_id, blacklist_id, path, description, _audit_user()),
        )
        conn.commit()
        return cursor.lastrowid or 0

    def delete_document(self, doc_id: int) -> None:
        """Loescht ein Dokument."""
        conn = self._get_conn()
        conn.execute("DELETE FROM documents WHERE id = ?", (doc_id,))
        conn.commit()

    def get_all_documents(self) -> list[dict[str, object]]:
        """Gibt alle Dokumente zurueck, mit Trip/Blacklist-Referenz."""
        conn = self._get_conn()
        rows = conn.execute("""
            SELECT d.id, d.trip_id, d.blacklist_id, d.path, d.description,
                   d.created_at,
                   t.date AS trip_date, t.purpose AS trip_purpose,
                   b.date AS bl_date, b.reason AS bl_reason
            FROM documents d
            LEFT JOIN trips t ON d.trip_id = t.id
            LEFT JOIN blacklist b ON d.blacklist_id = b.id
            ORDER BY d.created_at DESC
        """).fetchall()
        return [dict(row) for row in rows]

    # ------------------------------------------------------------------
    # Worktimes (Arbeitsstunden pro Monat)
    # ------------------------------------------------------------------

    def get_worktimes(self, year: int) -> list[dict[str, object]]:
        """Gibt alle Arbeitsstunden eines Jahres zurueck."""
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM worktimes WHERE year = ? ORDER BY month",
            (year,),
        ).fetchall()
        return [dict(row) for row in rows]

    def save_worktime(self, year: int, month: int, hours: float) -> None:
        """Speichert Arbeitsstunden fuer einen Monat (upsert)."""
        conn = self._get_conn()
        now = _audit_now()
        user = _audit_user()
        conn.execute(
            """
            INSERT INTO worktimes (
                year, month, hours, created_at, created_by
            )
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(year, month) DO UPDATE SET
                hours = excluded.hours,
                changed_at = excluded.created_at,
                changed_by = excluded.created_by
            """,
            (year, month, hours, now, user),
        )
        conn.commit()

    def delete_worktime(self, year: int, month: int) -> None:
        """Loescht Arbeitsstunden fuer einen Monat."""
        conn = self._get_conn()
        conn.execute(
            "DELETE FROM worktimes WHERE year = ? AND month = ?",
            (year, month),
        )
        conn.commit()
