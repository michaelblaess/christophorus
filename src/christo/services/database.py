"""SQLite-basierte Datenhaltung fuer ein einzelnes Fahrtenbuch."""

import contextlib
import getpass
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from christo.models.trip import MonthData, Trip
from christo.models.vehicle import Vehicle

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
    """Verwaltet eine christo.db SQLite-Datenbank.

    Jedes Fahrtenbuch hat eine eigene Datenbank in seinem Verzeichnis.
    """

    DB_FILENAME = "christo.db"
    # Fruehere Dateinamen, juengster zuerst ("Death Proof", davor "fahrtenbuch").
    # Werden beim Oeffnen transparent auf DB_FILENAME migriert
    # (siehe _migrate_legacy_db).
    LEGACY_DB_FILENAMES: tuple[str, ...] = ("death-proof.db", "fahrtenbuch.db")

    def __init__(self, path: Path) -> None:
        self._path = path
        self._db_file = path / self.DB_FILENAME
        self._conn: sqlite3.Connection | None = None

    @staticmethod
    def has_logbook(path: Path) -> bool:
        """Prueft ob im Verzeichnis ein Fahrtenbuch liegt.

        Erkennt die aktuelle christo.db und alle frueheren Dateinamen, damit
        bestehende Fahrtenbuecher vor der Migration als gueltig erkannt werden.
        """
        names = (Database.DB_FILENAME, *Database.LEGACY_DB_FILENAMES)
        return any((path / name).exists() for name in names)

    def _migrate_legacy_db(self) -> None:
        """Benennt die juengste alte Datenbank einmalig auf christo.db um.

        Migriert nur, wenn noch keine christo.db existiert. Vorhandene
        Backup-Dateien (*.db.backup_*) bleiben unangetastet.
        """
        if self._db_file.exists():
            return
        for name in self.LEGACY_DB_FILENAMES:
            legacy = self._path / name
            if legacy.exists():
                legacy.rename(self._db_file)
                return

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

        # Legacy-DB (fahrtenbuch.db) vor dem Verbinden migrieren.
        self._migrate_legacy_db()

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
                color TEXT NOT NULL DEFAULT 'green',
                is_informational INTEGER NOT NULL DEFAULT 0
            );
        """)
        conn.commit()
        self._migrate_trips_check_constraint()
        self._migrate_trips_add_round_trip()
        self._migrate_blacklist_remove_allow_private()
        self._migrate_addresses_remove_category_check()
        self._seed_default_categories()
        self._migrate_add_fuel_private_category()
        self._migrate_add_informational_flag()
        self._migrate_add_informational_categories()
        self._migrate_add_fuel_columns()
        self._migrate_add_vehicle_tank_columns()
        self._migrate_add_audit_columns()
        self._migrate_add_category_code()

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

    def _add_missing_columns(self, table: str, columns: tuple[str, ...]) -> None:
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

    def _migrate_add_category_code(self) -> None:
        """Fuegt die Spalte 'code' in categories ein und setzt Defaults."""
        conn = self._get_conn()
        rows = conn.execute("PRAGMA table_info(categories)").fetchall()
        existing = {str(row[1]) for row in rows}
        if "code" in existing:
            return
        conn.execute("ALTER TABLE categories ADD COLUMN code TEXT")
        code_map = {
            "business": "G",
            "private": "P",
            "fuel": "T",
            "fuel_private": "T",
        }
        for name, code in code_map.items():
            conn.execute(
                "UPDATE categories SET code = ? WHERE name = ?",
                (code, name),
            )
        conn.commit()

    def _migrate_trips_check_constraint(self) -> None:
        """Entfernt die CHECK-Constraint auf trips.category falls vorhanden.

        SQLite erlaubt kein ALTER TABLE DROP CONSTRAINT, daher wird die
        Tabelle neu erstellt falls die alte Constraint noch existiert.
        """
        conn = self._get_conn()
        row = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='trips'").fetchone()
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
        row = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='trips'").fetchone()
        if row is None:
            return
        create_sql = row[0] or ""
        if "round_trip" in create_sql.lower():
            return
        conn.execute("ALTER TABLE trips ADD COLUMN round_trip INTEGER NOT NULL DEFAULT 0")
        conn.commit()

    def _migrate_blacklist_remove_allow_private(self) -> None:
        """Entfernt die allow_private-Spalte aus der blacklist-Tabelle falls vorhanden."""
        conn = self._get_conn()
        row = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='blacklist'").fetchone()
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

    def _migrate_add_informational_flag(self) -> None:
        """Fuegt die is_informational-Spalte in bestehende DBs ein.

        Informational-Kategorien (z.B. Fahrzeug-Anlieferung) tragen keine
        km bei und werden von Plausi-Checks und km-Summen uebersprungen.
        """
        conn = self._get_conn()
        rows = conn.execute("PRAGMA table_info(categories)").fetchall()
        existing = {str(row[1]) for row in rows}
        if "is_informational" not in existing:
            conn.execute("ALTER TABLE categories ADD COLUMN is_informational INTEGER NOT NULL DEFAULT 0")
            conn.commit()

    def _migrate_add_fuel_columns(self) -> None:
        """Fuegt fuel_liters und fuel_full_tank zur trips-Tabelle hinzu.

        fuel_liters: getankte Menge in Litern (REAL, Default 0).
        fuel_full_tank: 1 wenn vollgetankt, 0 sonst (INTEGER, Default 0).
        Beide nur fuer Trips der Kategorien fuel/fuel_private relevant.
        """
        conn = self._get_conn()
        rows = conn.execute("PRAGMA table_info(trips)").fetchall()
        existing = {str(row[1]) for row in rows}
        if "fuel_liters" not in existing:
            conn.execute("ALTER TABLE trips ADD COLUMN fuel_liters REAL NOT NULL DEFAULT 0")
        if "fuel_full_tank" not in existing:
            conn.execute("ALTER TABLE trips ADD COLUMN fuel_full_tank INTEGER NOT NULL DEFAULT 0")
        conn.commit()

    def _migrate_add_vehicle_tank_columns(self) -> None:
        """Fuegt tank_capacity_l und consumption_l_100km zur vehicle-Tabelle.

        Basis fuer die Tank-Plausibilitaets-Checks: Wie gross ist der Tank
        und welchen Durchschnittsverbrauch nehmen wir als Referenz an.
        """
        conn = self._get_conn()
        rows = conn.execute("PRAGMA table_info(vehicle)").fetchall()
        existing = {str(row[1]) for row in rows}
        if "tank_capacity_l" not in existing:
            conn.execute("ALTER TABLE vehicle ADD COLUMN tank_capacity_l REAL NOT NULL DEFAULT 0")
        if "consumption_l_100km" not in existing:
            conn.execute("ALTER TABLE vehicle ADD COLUMN consumption_l_100km REAL NOT NULL DEFAULT 0")
        conn.commit()

    def _migrate_add_informational_categories(self) -> None:
        """Fuegt die Kategorien 'delivery' und 'return' ein, falls fehlend."""
        conn = self._get_conn()
        existing = {
            row["name"]
            for row in conn.execute(
                "SELECT name FROM categories WHERE name IN (?, ?)",
                ("delivery", "return"),
            ).fetchall()
        }
        to_insert = [
            ("delivery", "Anlieferung", 0, "white", 1),
            ("return", "Rueckgabe / Abholung", 0, "white", 1),
        ]
        for row in to_insert:
            if row[0] in existing:
                continue
            conn.execute(
                """
                INSERT INTO categories (
                    name, display_name, counts_as_business, color,
                    is_informational
                )
                VALUES (?, ?, ?, ?, ?)
                """,
                row,
            )
        conn.commit()

    # ------------------------------------------------------------------
    # Categories
    # ------------------------------------------------------------------

    def get_categories(self) -> list[dict[str, Any]]:
        """Gibt alle Kategorien zurueck."""
        conn = self._get_conn()
        rows = conn.execute("SELECT * FROM categories ORDER BY id").fetchall()
        return [dict(row) for row in rows]

    def get_business_category_names(self) -> set[str]:
        """Gibt die Namen aller Kategorien zurueck, die als geschaeftlich zaehlen."""
        conn = self._get_conn()
        rows = conn.execute("SELECT name FROM categories WHERE counts_as_business = 1").fetchall()
        return {row["name"] for row in rows}

    def get_informational_category_names(self) -> set[str]:
        """Gibt die Namen aller informationellen Kategorien zurueck.

        Diese Trips (Anlieferung, Rueckgabe) tragen keine km und werden von
        Plausi-Checks und km-Kette-Pflegen uebersprungen.
        """
        conn = self._get_conn()
        rows = conn.execute("SELECT name FROM categories WHERE is_informational = 1").fetchall()
        return {row["name"] for row in rows}

    def get_category_colors(self) -> dict[str, str]:
        """Gibt ein Mapping von Kategorie-Name zu Farbe zurueck."""
        conn = self._get_conn()
        rows = conn.execute("SELECT name, color FROM categories ORDER BY id").fetchall()
        return {row["name"]: row["color"] for row in rows}

    def get_category_codes(self) -> dict[str, str]:
        """Gibt ein Mapping von Kategorie-Name zu Code (G/P/T/...) zurueck."""
        conn = self._get_conn()
        rows = conn.execute("SELECT name, code FROM categories WHERE code IS NOT NULL ORDER BY id").fetchall()
        return {row["name"]: row["code"] for row in rows}

    def get_category_options(self) -> list[tuple[str, str]]:
        """Gibt Kategorien als (display_name, name)-Tupel fuer Select-Widgets zurueck."""
        conn = self._get_conn()
        rows = conn.execute("SELECT name, display_name FROM categories ORDER BY id").fetchall()
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
                name,
                display_name,
                1 if counts_as_business else 0,
                color,
                now,
                user,
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
                name,
                display_name,
                1 if counts_as_business else 0,
                color,
                _audit_now(),
                _audit_user(),
                category_id,
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
            tank_capacity_l=float(row["tank_capacity_l"] or 0),
            consumption_l_100km=float(row["consumption_l_100km"] or 0),
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
                tank_capacity_l, consumption_l_100km,
                created_at, created_by, changed_at, changed_by)
            VALUES (1, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, NULL)
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
                tank_capacity_l = excluded.tank_capacity_l,
                consumption_l_100km = excluded.consumption_l_100km,
                changed_at = excluded.created_at,
                changed_by = excluded.created_by
            """,
            (
                vehicle.name,
                vehicle.plate,
                vehicle.contract_number,
                vehicle.lease_km_per_month,
                vehicle.start_km,
                vehicle.end_km,
                vehicle.start_date,
                vehicle.end_date,
                vehicle.lease_months,
                vehicle.tank_capacity_l,
                vehicle.consumption_l_100km,
                now,
                user,
            ),
        )
        conn.commit()

    # ------------------------------------------------------------------
    # Trips
    # ------------------------------------------------------------------

    # Informationelle Trips (Anlieferung/Rueckgabe) nehmen nicht an der
    # km-Kette teil. Die SQL-Filter schliessen sie ueber die categories-Tabelle
    # aus, damit weder Vorgaenger-Lookup noch Shift-Cascades sie anfassen.
    _SQL_EXCLUDE_INFORMATIONAL = "category NOT IN (SELECT name FROM categories WHERE is_informational = 1)"

    def get_km_end_before(
        self,
        date_iso: str,
        time_from: str = "",
        exclude_trip_id: int | None = None,
    ) -> int:
        """Gibt km_end des chronologischen Vorgaengers zurueck.

        Die Kette wird nach (date, time_from, id) sortiert. Ein Trip auf dem
        gleichen Tag mit frueherer Uhrzeit ist Vorgaenger; Trips ohne Uhrzeit
        (time_from == "") sortieren zuerst.

        Vorgaenger eines NEUEN Trips (exclude_trip_id is None): letzter Trip
        mit (date, time_from) < (neues_date, neues_time_from). Same-day-Trips
        mit gleicher time_from gelten als Vorgaenger (neuer Trip bekommt die
        hoechste id und kommt zuletzt).

        Vorgaenger eines BESTEHENDEN Trips (exclude_trip_id gesetzt): letzter
        Trip mit (date, time_from, id) < (exclude_trip_date, exclude_time_from,
        exclude_trip_id).

        Informationelle Trips (Anlieferung/Rueckgabe) werden uebersprungen,
        da sie keine km tragen.

        Fallback wenn nichts gefunden: vehicle.start_km.
        """
        conn = self._get_conn()
        excl = self._SQL_EXCLUDE_INFORMATIONAL
        if exclude_trip_id is not None:
            # exclude_trip_id muss den Trip komplett rausfiltern — sonst
            # kann der Trip an seiner ALTEN Position (die noch im DB steht,
            # bevor der Slow-Path ihn verschiebt) faelschlich als Vorgaenger
            # seines NEUEN Platzes matchen und seinen eigenen km_end als
            # predecessor_km zurueckliefern.
            row = conn.execute(
                f"""
                SELECT km_end FROM trips
                WHERE (
                    (date < ?)
                    OR (date = ? AND time_from < ?)
                    OR (date = ? AND time_from = ? AND id < ?)
                )
                  AND id != ?
                  AND {excl}
                ORDER BY date DESC, time_from DESC, id DESC
                LIMIT 1
                """,
                (
                    date_iso,
                    date_iso,
                    time_from,
                    date_iso,
                    time_from,
                    exclude_trip_id,
                    exclude_trip_id,
                ),
            ).fetchone()
        else:
            row = conn.execute(
                f"""
                SELECT km_end FROM trips
                WHERE (
                    (date < ?)
                    OR (date = ? AND time_from <= ?)
                )
                  AND {excl}
                ORDER BY date DESC, time_from DESC, id DESC
                LIMIT 1
                """,
                (date_iso, date_iso, time_from),
            ).fetchone()
        if row is not None:
            return int(row["km_end"])
        vehicle = self.get_vehicle()
        return vehicle.start_km

    def _shift_trips_after(
        self,
        date_iso: str,
        time_from: str,
        delta: int,
        exclude_trip_id: int | None = None,
    ) -> None:
        """Verschiebt km_start/km_end aller Trips nach (date, time_from, id).

        Die Kette wird nach (date, time_from, id) sortiert. Verschoben werden
        alle Trips, die nach dem Referenzpunkt kommen — also echte Nachfolger
        in der Chain-Ordnung.

        Bei gleichem Datum+Uhrzeit werden nur Trips mit id > exclude_trip_id
        verschoben, so dass der gerade eingefuegte Trip nicht sich selbst
        anfasst.
        """
        if delta == 0:
            return
        conn = self._get_conn()
        excl = self._SQL_EXCLUDE_INFORMATIONAL
        if exclude_trip_id is not None:
            conn.execute(
                f"""
                UPDATE trips
                SET km_start = km_start + ?, km_end = km_end + ?
                WHERE (
                    (date > ?)
                    OR (date = ? AND time_from > ?)
                    OR (date = ? AND time_from = ? AND id > ?)
                )
                  AND {excl}
                """,
                (
                    delta,
                    delta,
                    date_iso,
                    date_iso,
                    time_from,
                    date_iso,
                    time_from,
                    exclude_trip_id,
                ),
            )
        else:
            conn.execute(
                f"""
                UPDATE trips
                SET km_start = km_start + ?, km_end = km_end + ?
                WHERE (
                    (date > ?)
                    OR (date = ? AND time_from > ?)
                )
                  AND {excl}
                """,
                (delta, delta, date_iso, date_iso, time_from),
            )

    def _is_informational_category(self, category: str) -> bool:
        """Prueft ob die Kategorie rein informationell ist (keine km)."""
        return category in self.get_informational_category_names()

    def add_trip(self, trip: Trip) -> int:
        """Fuegt eine neue Fahrt hinzu und baut die km-Kette auf.

        km_start wird aus dem chronologischen Vorgaenger bestimmt (ignoriert den
        vom User eingetragenen Wert). km_end wird so gesetzt, dass die vom User
        eingegebene Distanz (km_end - km_start) erhalten bleibt. Alle nachfolgenden
        Trips werden um diese Distanz verschoben. Bei Ueberschreitung der
        Fahrzeug-Endkilometer wird die Transaktion zurueckgerollt.

        Informationelle Trips (Anlieferung/Rueckgabe) werden mit km_start = 0
        und km_end = 0 gespeichert und loesen keinen Shift aus.
        """
        is_info = self._is_informational_category(trip.category)
        distance = 0 if is_info else max(0, trip.km_end - trip.km_start)
        conn = self._get_conn()
        try:
            conn.execute("BEGIN")
            if is_info:
                new_km_start = 0
                new_km_end = 0
                km_business = 0
                km_private = 0
            else:
                predecessor_km = self.get_km_end_before(trip.date, trip.time_from)
                new_km_start = predecessor_km
                new_km_end = new_km_start + distance
                km_business = trip.km_business
                km_private = trip.km_private

            is_fuel_cat = trip.category in ("fuel", "fuel_private")
            fuel_liters = float(trip.fuel_liters) if is_fuel_cat else 0.0
            fuel_full_tank = 1 if (is_fuel_cat and trip.fuel_full_tank) else 0
            cursor = conn.execute(
                """
                INSERT INTO trips (date, time_from, time_to, destination, purpose,
                    km_start, km_end, km_business, km_private, category, round_trip,
                    fuel_liters, fuel_full_tank,
                    created_at, created_by)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    trip.date,
                    trip.time_from,
                    trip.time_to,
                    trip.destination,
                    trip.purpose,
                    new_km_start,
                    new_km_end,
                    km_business,
                    km_private,
                    trip.category,
                    1 if trip.round_trip else 0,
                    fuel_liters,
                    fuel_full_tank,
                    _audit_now(),
                    _audit_user(),
                ),
            )
            new_id = cursor.lastrowid or 0
            # Alle Nachfolger um die Distanz dieser Fahrt nach oben verschieben
            # (entfaellt bei informationellen Trips — distance == 0)
            self._shift_trips_after(trip.date, trip.time_from, distance, exclude_trip_id=new_id)
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

        old_is_info = self._is_informational_category(old.category)
        new_is_info = self._is_informational_category(trip.category)

        old_distance = 0 if old_is_info else max(0, old.km_end - old.km_start)
        new_distance = 0 if new_is_info else max(0, trip.km_end - trip.km_start)

        # Felder fuer INSERT/UPDATE anhand des Informational-Zustands normalisieren
        if new_is_info:
            new_km_business = 0
            new_km_private = 0
            new_destination = ""
            new_purpose = ""
            new_round_trip = 0
        else:
            new_km_business = trip.km_business
            new_km_private = trip.km_private
            new_destination = trip.destination
            new_purpose = trip.purpose
            new_round_trip = 1 if trip.round_trip else 0

        # Tankfelder nur bei fuel/fuel_private speichern
        is_fuel_cat = trip.category in ("fuel", "fuel_private")
        new_fuel_liters = float(trip.fuel_liters) if is_fuel_cat else 0.0
        new_fuel_full_tank = 1 if (is_fuel_cat and trip.fuel_full_tank) else 0

        # Eine reine Distanz-Aenderung (Datum + Uhrzeit + Typ gleich) darf den
        # bestehenden km_start behalten — die Chain-Position bleibt identisch.
        # Jede andere Aenderung (Datum, Uhrzeit, Typ) kann die Chain-Position
        # verschieben und muss ueber den "full re-place"-Pfad laufen.
        position_unchanged = trip.date == old.date and trip.time_from == old.time_from and old_is_info == new_is_info
        try:
            conn.execute("BEGIN")
            if position_unchanged:
                if new_is_info:
                    upd_km_start = 0
                    upd_km_end = 0
                    delta = new_distance - old_distance
                else:
                    # Position und Info-Status unveraendert: km_start des Trips
                    # bleibt, wie er ist. Nur wenn sich die Distanz aendert,
                    # verschieben wir die Nachfolger um das Delta. Ein eventueller
                    # Gap zum Vorgaenger (z.B. nicht geloggte Privatfahrt) bleibt
                    # dabei bewusst erhalten — automatisches "Heilen" wuerde
                    # legitime Luecken schliessen und die ganze Kette verschieben.
                    upd_km_start = old.km_start
                    upd_km_end = upd_km_start + new_distance
                    delta = new_distance - old_distance
                conn.execute(
                    """
                    UPDATE trips SET
                        date = ?, time_from = ?, time_to = ?,
                        destination = ?, purpose = ?,
                        km_start = ?, km_end = ?,
                        km_business = ?, km_private = ?, category = ?,
                        round_trip = ?,
                        fuel_liters = ?, fuel_full_tank = ?,
                        changed_at = ?, changed_by = ?
                    WHERE id = ?
                    """,
                    (
                        trip.date,
                        trip.time_from,
                        trip.time_to,
                        new_destination,
                        new_purpose,
                        upd_km_start,
                        upd_km_end,
                        new_km_business,
                        new_km_private,
                        trip.category,
                        new_round_trip,
                        new_fuel_liters,
                        new_fuel_full_tank,
                        _audit_now(),
                        _audit_user(),
                        trip_id,
                    ),
                )
                self._shift_trips_after(trip.date, trip.time_from, delta, exclude_trip_id=trip_id)
            else:
                # Position in der Kette kann sich aendern: alte Nachfolger
                # zurueckrollen, Trip an neuer Stelle einsetzen, neue Nachfolger
                # verschieben.
                self._shift_trips_after(old.date, old.time_from, -old_distance, exclude_trip_id=trip_id)
                if new_is_info:
                    new_km_start = 0
                    new_km_end = 0
                else:
                    predecessor_km = self.get_km_end_before(trip.date, trip.time_from, exclude_trip_id=trip_id)
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
                        fuel_liters = ?, fuel_full_tank = ?,
                        changed_at = ?, changed_by = ?
                    WHERE id = ?
                    """,
                    (
                        trip.date,
                        trip.time_from,
                        trip.time_to,
                        new_destination,
                        new_purpose,
                        new_km_start,
                        new_km_end,
                        new_km_business,
                        new_km_private,
                        trip.category,
                        new_round_trip,
                        new_fuel_liters,
                        new_fuel_full_tank,
                        _audit_now(),
                        _audit_user(),
                        trip_id,
                    ),
                )
                self._shift_trips_after(trip.date, trip.time_from, new_distance, exclude_trip_id=trip_id)
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
        old_distance = 0 if self._is_informational_category(old.category) else max(0, old.km_end - old.km_start)
        try:
            conn.execute("BEGIN")
            conn.execute("DELETE FROM trips WHERE id = ?", (trip_id,))
            self._shift_trips_after(old.date, old.time_from, -old_distance, exclude_trip_id=trip_id)
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    def rebuild_all_km(self, force: bool = False) -> tuple[int, int]:
        """Baut die km-Kette aller Fahrten chronologisch neu auf.

        Als Distanz pro Trip wird `max(km_end - km_start, km_business +
        km_private)` genommen — so werden auch Zeilen repariert bei denen
        der User die km-Spalten eingetragen hat aber km_start/km_end nicht
        (typischer Bug: Rueckfahrt mit business=260, aber km_start==km_end).

        km_start wird auf den akkumulierten Stand gesetzt, beginnend mit
        vehicle.start_km. Rueckgabe: (Anzahl veraenderte Trips, finaler
        km-Stand).

        Wenn force=False und vehicle.end_km ueberschritten wuerde, wirft
        die Methode ValueError ohne Aenderungen zu schreiben. Mit force=
        True laeuft der Rebuild trotzdem durch — die Vertragspruefung
        uebernimmt dann separat der Plausi-Check.
        """
        conn = self._get_conn()
        vehicle = self.get_vehicle()
        cursor_state = vehicle.start_km
        info_cats = self.get_informational_category_names()
        rows = conn.execute(
            "SELECT id, km_start, km_end, km_business, km_private, category FROM trips ORDER BY date, time_from, id"
        ).fetchall()

        changes: list[tuple[int, int, int]] = []  # (id, new_start, new_end)
        for row in rows:
            if str(row["category"]) in info_cats:
                # Informationelle Trips bleiben bei 0/0 und zaehlen nicht mit
                changes.append((int(row["id"]), 0, 0))
                continue
            distance_chain = max(0, int(row["km_end"]) - int(row["km_start"]))
            distance_cols = max(0, int(row["km_business"] or 0) + int(row["km_private"] or 0))
            distance = max(distance_chain, distance_cols)
            new_start = cursor_state
            new_end = new_start + distance
            changes.append((int(row["id"]), new_start, new_end))
            cursor_state = new_end

        if not force and vehicle.end_km > 0 and cursor_state > vehicle.end_km:
            raise ValueError(
                f"Rebuild wuerde Endkilometerstand ueberschreiten: {cursor_state} km > {vehicle.end_km} km"
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

    def get_audit_info(self, table: str, row_id: int, id_column: str = "id") -> dict[str, str]:
        """Liest die Audit-Spalten einer Zeile und gibt sie als Dict zurueck.

        Fehlende/NULL-Werte kommen als leerer String zurueck. Der table- und
        id_column-Parameter wird direkt in SQL eingesetzt, daher duerfen hier
        nur intern bekannte Tabellennamen reingereicht werden — keine
        User-Eingaben.
        """
        conn = self._get_conn()
        row = conn.execute(
            f"SELECT created_at, created_by, changed_at, changed_by FROM {table} WHERE {id_column} = ?",
            (row_id,),
        ).fetchone()
        if row is None:
            return {
                "created_at": "",
                "created_by": "",
                "changed_at": "",
                "changed_by": "",
            }
        return {
            "created_at": str(row["created_at"] or ""),
            "created_by": str(row["created_by"] or ""),
            "changed_at": str(row["changed_at"] or ""),
            "changed_by": str(row["changed_by"] or ""),
        }

    def get_trips_for_month(self, year: int, month: int) -> list[Trip]:
        """Gibt alle Fahrten eines Monats zurueck, sortiert nach Datum und Startzeit."""
        conn = self._get_conn()
        month_prefix = f"{year}-{month:02d}"
        rows = conn.execute(
            """
            SELECT * FROM trips
            WHERE date LIKE ? || '%'
            ORDER BY date, time_from, id
            """,
            (month_prefix,),
        ).fetchall()
        return [self._row_to_trip(row) for row in rows]

    def get_month_data(self, year: int, month: int) -> MonthData:
        """Gibt MonthData fuer einen Monat zurueck."""
        trips = self.get_trips_for_month(year, month)
        return MonthData(year=year, month=month, trips=trips)

    def get_trips_for_year(self, year: int) -> list[Trip]:
        """Gibt alle Fahrten eines Jahres zurueck, sortiert nach Datum und Startzeit."""
        conn = self._get_conn()
        year_prefix = f"{year}-"
        rows = conn.execute(
            """
            SELECT * FROM trips
            WHERE date LIKE ? || '%'
            ORDER BY date, time_from, id
            """,
            (year_prefix,),
        ).fetchall()
        return [self._row_to_trip(row) for row in rows]

    def get_year_data(self, year: int) -> MonthData:
        """Gibt MonthData mit allen Fahrten eines Jahres zurueck (month=0 als Marker)."""
        trips = self.get_trips_for_year(year)
        return MonthData(year=year, month=0, trips=trips)

    def get_all_trips_ordered(self) -> list[Trip]:
        """Gibt alle Trips der Datenbank zurueck, sortiert nach
        (date, time_from, id).

        Diese Reihenfolge entspricht der kanonischen km-Kette und wird von
        Plausibilitaets-Checks und Tests verwendet.
        """
        conn = self._get_conn()
        rows = conn.execute("SELECT * FROM trips ORDER BY date, time_from, id").fetchall()
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
        keys = row.keys() if hasattr(row, "keys") else []
        fuel_liters = float(row["fuel_liters"] or 0) if "fuel_liters" in keys else 0.0
        fuel_full_tank = bool(row["fuel_full_tank"]) if "fuel_full_tank" in keys else False
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
            fuel_liters=fuel_liters,
            fuel_full_tank=fuel_full_tank,
        )

    # ------------------------------------------------------------------
    # Addresses
    # ------------------------------------------------------------------

    def get_addresses(self, category: str | None = None) -> list[dict[str, Any]]:
        """Gibt Adressen zurueck, optional gefiltert nach Kategorie."""
        conn = self._get_conn()
        if category:
            rows = conn.execute(
                "SELECT * FROM addresses WHERE category = ? ORDER BY name",
                (category,),
            ).fetchall()
        else:
            rows = conn.execute("SELECT * FROM addresses ORDER BY category, name").fetchall()
        return [dict(row) for row in rows]

    def add_address(self, category: str, name: str, address: str, km: float) -> int:
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

    def update_address(self, address_id: int, name: str, address: str, km: float) -> None:
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
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
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

    def get_blacklist(self) -> list[dict[str, Any]]:
        """Gibt alle Blacklist-Eintraege zurueck."""
        conn = self._get_conn()
        rows = conn.execute("SELECT * FROM blacklist ORDER BY date").fetchall()
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
        row = conn.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='addresses'").fetchone()
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
    ) -> list[dict[str, Any]]:
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

    def get_all_documents(self) -> list[dict[str, Any]]:
        """Gibt alle Dokumente zurueck, mit Trip/Blacklist-Referenz."""
        conn = self._get_conn()
        rows = conn.execute("""
            SELECT d.id, d.trip_id, d.blacklist_id, d.path, d.description,
                   d.created_at,
                   t.date AS trip_date, t.time_from AS trip_time_from,
                   t.purpose AS trip_purpose, t.category AS trip_category,
                   t.fuel_liters AS trip_fuel_liters,
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

    def get_worktimes(self, year: int) -> list[dict[str, Any]]:
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

    def clone_settings_from(self, source_path: Path) -> None:
        """Uebernimmt fahrer-bezogene Daten aus einem anderen Fahrtenbuch.

        Kopiert settings, addresses, categories, blacklist und worktimes aus
        der Quell-Datenbank in die aktuell geoeffnete. vehicle, trips und
        documents bleiben unveraendert (typischerweise leer beim Klonen).
        Session-spezifische Settings (last_viewed_year/month) werden
        ausgelassen, damit der Start-Zustand des neuen Fahrtenbuchs sauber
        ist.

        Das Ziel muss vorher geoeffnet sein (Schema ist dann vorhanden).
        Die Quelle wird kurz geoeffnet und wieder geschlossen, damit ihre
        Migration laeuft und das Schema kompatibel ist.
        """
        conn = self._get_conn()
        if not Database.has_logbook(source_path):
            raise FileNotFoundError(f"Quell-Datenbank nicht gefunden: {source_path / self.DB_FILENAME}")

        # Quelle kurz oeffnen, damit Migrationen laufen (inkl. Legacy-DB-
        # Umbenennung). Danach ist das Schema garantiert identisch zum Ziel,
        # sodass SELECT * sicher ist und die Datei unter DB_FILENAME liegt.
        src_fb = Database(source_path)
        src_fb.open()
        src_fb.close()

        source_db_file = source_path / self.DB_FILENAME

        # ATTACH erlaubt keinen ?-Parameter fuer den Pfad, daher SQL-Literal
        # mit doppeltem Einzel-Quote als Escape.
        escaped_path = str(source_db_file).replace("'", "''")
        conn.execute(f"ATTACH DATABASE '{escaped_path}' AS src")
        try:
            conn.execute("BEGIN")

            # settings hat keinen AUTOINCREMENT-Key und wird per WHERE
            # gefiltert — hier reicht der explizite Column-Copy.
            self._copy_table(
                conn,
                "settings",
                where="key NOT IN ('last_viewed_year', 'last_viewed_month')",
            )

            # categories wird in _init_schema mit Defaults befuellt — die
            # raeumen wir weg, damit die Quell-Kategorien (ggf. angepasst)
            # 1:1 uebernommen werden.
            self._copy_table(conn, "categories")
            self._copy_table(conn, "addresses")
            self._copy_table(conn, "blacklist")
            self._copy_table(conn, "worktimes")

            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            with contextlib.suppress(sqlite3.Error):
                conn.execute("DETACH DATABASE src")

    def _copy_table(
        self,
        conn: sqlite3.Connection,
        table: str,
        where: str | None = None,
    ) -> None:
        """Kopiert Zeilen aus src.<table> in die Ziel-<table>.

        Ermittelt die in beiden Schemas vorhandenen Spalten und listet sie
        explizit im INSERT auf. Das ist noetig, weil migrierte DBs
        (ALTER TABLE ADD COLUMN) Spalten am Ende der Tabelle haben, waehrend
        frisch angelegte DBs sie in der Reihenfolge aus _init_schema haben.
        'SELECT *' macht positionales Column-Mapping und crasht dann z.B.
        mit NOT NULL constraint failed, weil ein TEXT-Wert in eine INTEGER-
        Spalte geschoben wird.
        """
        src_cols = {str(row[1]) for row in conn.execute(f"PRAGMA src.table_info({table})")}
        dst_cols = [str(row[1]) for row in conn.execute(f"PRAGMA table_info({table})")]
        common = [c for c in dst_cols if c in src_cols]
        if not common:
            return
        col_list = ", ".join(f'"{c}"' for c in common)
        where_sql = f" WHERE {where}" if where else ""
        conn.execute(f"DELETE FROM {table}")
        conn.execute(f"INSERT INTO {table} ({col_list}) SELECT {col_list} FROM src.{table}{where_sql}")

    def backup_to_file(self, timestamp: datetime | None = None) -> Path:
        """Erstellt eine Sicherungskopie der DB-Datei mit Timestamp.

        Verwendet sqlite3.Connection.backup() — die offizielle SQLite-API
        fuer Hot-Backups. Safe auch bei aktiven Transaktionen und beliebigem
        journal_mode. Ziel: <db_file>.backup_YYYYMMDD_HHMMSS im gleichen
        Verzeichnis. Gibt den Pfad der Backup-Datei zurueck.
        """
        conn = self._get_conn()
        ts = (timestamp or datetime.now()).strftime("%Y%m%d_%H%M%S")
        backup_file = self._db_file.with_name(f"{self._db_file.name}.backup_{ts}")
        target = sqlite3.connect(str(backup_file))
        try:
            conn.backup(target)
        finally:
            target.close()
        return backup_file
