"""Fahrt anlegen oder bearbeiten."""

import os
from pathlib import Path

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    Checkbox,
    Input,
    Label,
    Select,
    Static,
    TextArea,
)

from fahrtenbuch_app.models.settings import AddressEntry
from fahrtenbuch_app.models.trip import (
    Trip,
    get_business_categories,
    get_informational_categories,
)
from fahrtenbuch_app.services.database import Database
from fahrtenbuch_app.services.formatting import format_km, parse_km


def _iso_to_de(iso: str) -> str:
    """Konvertiert ISO-Datum (YYYY-MM-DD) zu deutschem Format (DD.MM.YYYY)."""
    try:
        parts = iso.split("-")
        if len(parts) == 3 and len(parts[2]) > 0:
            return f"{parts[2]}.{parts[1]}.{parts[0]}"
    except (ValueError, IndexError):
        pass
    return iso


def _de_to_iso(de: str) -> str:
    """Konvertiert deutsches Datum (DD.MM.YYYY) zu ISO-Format (YYYY-MM-DD)."""
    try:
        parts = de.split(".")
        if len(parts) == 3:
            return f"{parts[2]}-{parts[1]}-{parts[0]}"
    except (ValueError, IndexError):
        pass
    return de


def _format_liters(value: float) -> str:
    """Formatiert Liter mit deutschem Komma. 0 / leer → '' ."""
    if value is None or value <= 0:
        return ""
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.2f}".rstrip("0").rstrip(".").replace(".", ",")


def _parse_liters(raw: str) -> float:
    """Parst Liter aus UI-Eingabe (deutsches Komma). Fehler → 0.0."""
    s = (raw or "").strip().replace(",", ".")
    if not s:
        return 0.0
    try:
        return float(s)
    except ValueError:
        return 0.0


DELETE_REQUESTED = object()  # Sentinel: vom Dialog an den Caller, 'Loeschen'


class TripScreen(ModalScreen[Trip | None]):
    """Dialog zum Anlegen oder Bearbeiten einer Fahrt."""

    DEFAULT_CSS = """
    TripScreen {
        align: center middle;
    }
    TripScreen > VerticalScroll {
        width: 80;
        height: auto;
        max-height: 40;
        background: $surface;
        border: thick $accent;
        padding: 1 2;
    }
    TripScreen .form-row {
        height: auto;
        margin-bottom: 1;
    }
    TripScreen Label {
        width: 18;
        padding: 0 1;
    }
    TripScreen Input {
        width: 1fr;
        background: $surface;
        color: $foreground;
    }
    TripScreen Input:focus {
        background: $surface;
        color: $foreground;
        border: tall $accent;
    }
    TripScreen Select {
        width: 1fr;
    }
    TripScreen #input-destination {
        width: 1fr;
        height: 4;
    }
    TripScreen #btn-date-picker {
        width: 5;
        min-width: 5;
        margin-left: 1;
    }
    TripScreen .button-row {
        height: auto;
        margin-top: 1;
        align: center middle;
    }
    TripScreen Button {
        margin: 0 1;
    }
    TripScreen #title {
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
    }
    TripScreen #docs-title {
        text-style: bold;
        color: $accent;
        margin-top: 1;
        margin-bottom: 0;
    }
    TripScreen #audit-info {
        height: auto;
        margin-top: 1;
        padding: 0 1;
        color: $text-muted;
        text-style: italic;
        border-top: solid $surface-lighten-1;
    }
    TripScreen #docs-list {
        height: auto;
        margin-bottom: 1;
    }
    TripScreen .doc-row {
        height: 1;
        color: $text-muted;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Abbrechen"),
        Binding("ctrl+s", "save", "Speichern"),
    ]

    def __init__(
        self,
        database: Database,
        trip: Trip | None = None,
        last_km_end: int = 0,
        default_date: str = "",
        **kwargs: object,
    ) -> None:
        super().__init__(**kwargs)
        self._database = database
        self._trip = trip
        self._last_km_end = last_km_end
        self._default_date = default_date
        self._is_edit = trip is not None and trip.id > 0
        self._addresses: list[AddressEntry] = []
        self._selected_entry_km: float = 0.0
        # code → display_name fuer Kategorie-Lookup (z.B. "fuel"→"Tanken"),
        # wird in compose() aus der DB befuellt.
        self._category_labels: dict[str, str] = {}
        # Zuletzt aktive Kategorie, damit wir beim Wechsel erkennen koennen,
        # ob der Reisezweck der alten Kategorie-Anzeige entsprach.
        self._current_category: str = ""
        # Re-Entry-Schutz fuer die km-Auto-Berechnung: wenn wir selbst ein
        # Input-Feld programmatisch aendern, soll der Handler nicht noch mal
        # zurueckspringen.
        self._km_updating: bool = False

    def compose(self) -> ComposeResult:
        """Erstellt das Formular."""
        trip = self._trip or Trip()
        title = "Fahrt bearbeiten" if self._is_edit else "Neue Fahrt"

        self._load_addresses()
        dest_options = self._build_destination_options()
        category_options = self._database.get_category_options()
        if not category_options:
            category_options = [
                ("Geschaeftlich", "business"),
                ("Privat", "private"),
                ("Tanken", "fuel"),
                ("Service (TUeV, Reifen, ...)", "service"),
            ]
        # Lookup code → display_name fuer spaeteren Abgleich beim Kategoriewechsel
        self._category_labels = {code: label for label, code in category_options}
        self._current_category = trip.category if self._is_edit else "business"

        default_date_iso = trip.date if self._is_edit else self._default_date
        default_date_de = _iso_to_de(default_date_iso) if default_date_iso else ""

        # km_start IMMER aus dem chronologischen Vorgaenger bestimmen
        # (statt wie frueher vom User eintragbar). Beim Edit den eigenen Trip
        # ausschliessen, damit wir nicht auf uns selbst schauen. time_from
        # ist wichtig, sonst wird die Position innerhalb des Tages ignoriert
        # und get_km_end_before liefert faelschlich den km_end des Vortags.
        if default_date_iso:
            exclude_id = trip.id if self._is_edit else None
            default_time_from = trip.time_from if self._is_edit else ""
            default_km_start = self._database.get_km_end_before(
                default_date_iso,
                time_from=default_time_from,
                exclude_trip_id=exclude_id,
            )
        else:
            default_km_start = self._last_km_end

        with VerticalScroll():
            yield Static(title, id="title")

            with Horizontal(classes="form-row"):
                yield Label("Datum:")
                yield Input(
                    value=default_date_de,
                    placeholder="TT.MM.JJJJ",
                    id="input-date",
                )
                yield Button("...", id="btn-date-picker")

            with Horizontal(classes="form-row"):
                yield Label("Fahrzeit von:")
                yield Input(
                    value=trip.time_from,
                    placeholder="08:00",
                    id="input-time-from",
                )

            with Horizontal(classes="form-row"):
                yield Label("Fahrzeit bis:")
                yield Input(
                    value=trip.time_to,
                    placeholder="11:00",
                    id="input-time-to",
                )

            with Horizontal(classes="form-row"):
                yield Label("Kategorie:")
                yield Select(
                    options=category_options,
                    value=trip.category if self._is_edit else "business",
                    id="select-category",
                )

            with Horizontal(classes="form-row"):
                yield Label("Ziel (Auswahl):")
                select = Select[str](
                    options=dest_options if dest_options else [("(keine Adressen)", "__none__")],
                    prompt="Ziel auswaehlen...",
                    id="select-destination",
                    allow_blank=True,
                )
                yield select

            with Horizontal(classes="form-row"):
                yield Label("Ziel (Adresse):")
                yield TextArea(
                    trip.destination,
                    id="input-destination",
                )

            with Horizontal(classes="form-row"):
                yield Label("Strecke:")
                yield Select[str](
                    options=[
                        ("Einfach (nur Hinfahrt)", "oneway"),
                        ("Hin- und Rueckfahrt", "roundtrip"),
                    ],
                    value="roundtrip" if (self._is_edit and trip.round_trip) else "oneway",
                    id="select-round-trip",
                )

            with Horizontal(classes="form-row"):
                yield Label("Reisezweck:")
                yield Input(
                    value=trip.purpose,
                    placeholder="z.B. Abstimmung Projekt",
                    id="input-purpose",
                )

            with Horizontal(classes="form-row"):
                yield Label("km Anfang:")
                yield Input(
                    value=format_km(default_km_start) if default_km_start > 0 else "",
                    placeholder="Kilometerstand",
                    id="input-km-start",
                    disabled=True,
                )

            with Horizontal(classes="form-row"):
                yield Label("km Ende:")
                yield Input(
                    value=format_km(trip.km_end) if self._is_edit and trip.km_end > 0 else "",
                    placeholder="Kilometerstand",
                    id="input-km-end",
                )

            with Horizontal(classes="form-row"):
                yield Label("km geschaeftl.:")
                yield Input(
                    value=format_km(trip.km_business) if self._is_edit and trip.km_business > 0 else "",
                    placeholder="0",
                    id="input-km-business",
                )

            with Horizontal(classes="form-row"):
                yield Label("km privat:")
                yield Input(
                    value=format_km(trip.km_private) if self._is_edit and trip.km_private > 0 else "",
                    placeholder="0",
                    id="input-km-private",
                )

            with Horizontal(classes="form-row", id="row-fuel-liters"):
                yield Label("Getankt (Liter):")
                yield Input(
                    value=_format_liters(trip.fuel_liters) if self._is_edit else "",
                    placeholder="z.B. 46,5",
                    id="input-fuel-liters",
                )

            with Horizontal(classes="form-row", id="row-fuel-full-tank"):
                yield Label("Volltanken:")
                yield Checkbox(
                    value=trip.fuel_full_tank if self._is_edit else True,
                    id="check-fuel-full-tank",
                )

            # Audit-Info (nur im Bearbeitungsmodus)
            if self._is_edit and self._trip is not None and self._trip.id > 0:
                yield Static(
                    self._format_audit_text(self._trip.id),
                    id="audit-info",
                )

            # Belege-Sektion (nur im Bearbeitungsmodus)
            if self._is_edit and self._trip is not None:
                yield Static("Belege", id="docs-title")
                yield Vertical(id="docs-list")
                with Horizontal(classes="form-row"):
                    yield Label("")
                    yield Button(
                        "+ Beleg hinzufuegen",
                        variant="success",
                        id="btn-add-doc",
                    )

            with Horizontal(classes="button-row"):
                yield Button("Speichern (Ctrl+S)", variant="primary", id="btn-save")
                yield Button("Abbrechen (Esc)", variant="default", id="btn-cancel")
                if self._is_edit and self._trip is not None and self._trip.id > 0:
                    yield Button("Loeschen", variant="error", id="btn-delete")

    def _format_audit_text(self, trip_id: int) -> str:
        """Formatiert die Audit-Informationen (created/changed) fuer die
        Anzeige im Dialog. Fehlende Werte werden mit Bindestrich dargestellt.
        Das Datum wird im deutschen Format ausgegeben.
        """
        info = self._database.get_audit_info("trips", trip_id)

        def fmt_when(iso: str) -> str:
            if not iso:
                return "\u2014"
            # Erwartet "YYYY-MM-DD HH:MM:SS", tolerant gegen Varianten
            date_part, _, time_part = iso.partition(" ")
            try:
                parts = date_part.split("-")
                de = f"{parts[2]}.{parts[1]}.{parts[0]}"
            except IndexError:
                return iso
            return f"{de} {time_part}".rstrip()

        def fmt_who(user: str) -> str:
            return user if user else "\u2014"

        created = (
            f"Erstellt: {fmt_when(info['created_at'])} "
            f"von {fmt_who(info['created_by'])}"
        )
        changed = (
            f"Geaendert: {fmt_when(info['changed_at'])} "
            f"von {fmt_who(info['changed_by'])}"
        )
        return f"{created}\n{changed}"

    def _load_addresses(self) -> None:
        """Laedt alle Adressen aus der Datenbank."""
        self._addresses = []
        try:
            rows = self._database.get_addresses()
            for row in rows:
                self._addresses.append(AddressEntry(
                    id=int(row.get("id", 0)),
                    category=str(row.get("category", "")),
                    name=str(row.get("name", "")),
                    address=str(row.get("address", "")),
                    km=float(row.get("km", 0.0)),
                ))
        except Exception:
            pass

    def on_input_changed(self, event: Input.Changed) -> None:
        """Reagiert auf Feldaenderungen:
        - Datum aendert km_start (Vorgaenger), Distanz bleibt erhalten.
        - km_business / km_private addieren auf km_end = km_start + Summe.
        """
        if self._km_updating:
            return
        if event.input.id in ("input-km-business", "input-km-private"):
            self._update_km_end_from_columns()
            return
        if event.input.id != "input-date":
            return
        iso = _de_to_iso(event.value.strip())
        if not iso:
            return
        exclude_id = self._trip.id if (self._is_edit and self._trip) else None
        try:
            time_from_input = self.query_one("#input-time-from", Input)
            current_time_from = time_from_input.value.strip()
        except Exception:
            current_time_from = ""
        try:
            predecessor_km = self._database.get_km_end_before(
                iso,
                time_from=current_time_from,
                exclude_trip_id=exclude_id,
            )
        except Exception:
            return

        km_start_input = self.query_one("#input-km-start", Input)
        km_end_input = self.query_one("#input-km-end", Input)

        # Distanz aus den aktuellen Feldwerten merken, damit sie nach dem
        # Verschieben von km_start konstant bleibt.
        old_km_start = parse_km(km_start_input.value)
        old_km_end = parse_km(km_end_input.value)
        old_distance = max(0, old_km_end - old_km_start)

        km_start_input.value = format_km(predecessor_km) if predecessor_km > 0 else ""
        if old_distance > 0 and predecessor_km >= 0:
            km_end_input.value = format_km(predecessor_km + old_distance)

        # Adress-basierte Neuberechnung nur, wenn ein Adress-Eintrag aktiv ist.
        self._recalculate_km()

    def on_select_changed(self, event: Select.Changed) -> None:
        """Fuellt Adresse und km wenn ein Ziel ausgewaehlt wird."""
        if event.select.id == "select-round-trip":
            self._recalculate_km()
            return
        if event.select.id == "select-category":
            # Kategorie-Wechsel: km zwischen business und private umbuchen,
            # damit die Spalten direkt passen.
            if event.value != Select.BLANK:
                new_cat = str(event.value)
                self._sync_purpose_to_category(new_cat)
                self._apply_informational_state(new_cat)
                self._apply_fuel_visibility(new_cat)
                if new_cat not in get_informational_categories():
                    self._rebalance_km_for_category(new_cat)
                self._current_category = new_cat
            return
        if event.select.id != "select-destination":
            return
        if event.value == Select.BLANK:
            return

        key = str(event.value)

        # Explizites Leer-Machen: Ziel-Textfeld raeumen und raus.
        if key == "__clear__":
            self._selected_entry_km = 0.0
            dest_area = self.query_one("#input-destination", TextArea)
            dest_area.load_text("")
            self._recalculate_km()
            return

        # Zuhause als Ziel: Adresse aus Settings laden, km unveraendert lassen
        # (Distanz zum Heimatort haengt vom Startpunkt ab).
        if key == "__home__":
            home_address = self._database.get_setting("home_address", "").strip()
            self._selected_entry_km = 0.0
            dest_area = self.query_one("#input-destination", TextArea)
            dest_area.load_text(f"Zuhause\n{home_address}" if home_address else "Zuhause")
            return

        entry = self._find_address_entry(key)
        if entry is None:
            return

        self._selected_entry_km = entry.km

        dest_area = self.query_one("#input-destination", TextArea)
        dest_area.load_text(f"{entry.name}\n{entry.address}")

        category_select = self.query_one("#select-category", Select)

        # Kategorie automatisch setzen basierend auf Adress-Kategorie
        if entry.category == "customer":
            category_select.value = "business"
            purpose_input = self.query_one("#input-purpose", Input)
            if not purpose_input.value:
                purpose_input.value = "Abstimmung Projekt"
        elif entry.category == "gas_station":
            category_select.value = "fuel"
        elif entry.category == "steuerberaterin":
            category_select.value = "business"
            purpose_input = self.query_one("#input-purpose", Input)
            if not purpose_input.value:
                purpose_input.value = "Steuerberaterin"
        elif entry.category == "shopping":
            category_select.value = "private"
        elif entry.category == "restaurant":
            category_select.value = "business"
            purpose_input = self.query_one("#input-purpose", Input)
            if not purpose_input.value:
                purpose_input.value = "Geschaeftsessen"

        self._recalculate_km()

    def _is_round_trip(self) -> bool:
        """Prueft ob Hin- und Rueckfahrt ausgewaehlt ist."""
        rt_select = self.query_one("#select-round-trip", Select)
        return str(rt_select.value) == "roundtrip"

    def _update_km_end_from_columns(self) -> None:
        """Setzt km_end = km_start + km_business + km_private.

        Wird aufgerufen, wenn der User km_business oder km_private direkt
        eingibt, damit der Endkilometerstand automatisch mitwaechst und die
        Cascade beim Speichern die richtige Distanz sieht.
        """
        try:
            km_start_input = self.query_one("#input-km-start", Input)
            km_end_input = self.query_one("#input-km-end", Input)
            biz_input = self.query_one("#input-km-business", Input)
            priv_input = self.query_one("#input-km-private", Input)
        except Exception:
            return
        if km_end_input.disabled:
            return
        km_start = parse_km(km_start_input.value)
        km_business = parse_km(biz_input.value)
        km_private = parse_km(priv_input.value)
        total = km_business + km_private
        if total <= 0:
            return
        new_end = km_start + total
        new_value = format_km(new_end)
        if km_end_input.value == new_value:
            return
        self._km_updating = True
        try:
            km_end_input.value = new_value
        finally:
            self._km_updating = False

    def _recalculate_km(self) -> None:
        """Berechnet km-Werte basierend auf Strecke und Adress-Entfernung."""
        if self._selected_entry_km <= 0:
            return

        km_start_input = self.query_one("#input-km-start", Input)
        km_end_input = self.query_one("#input-km-end", Input)
        biz_input = self.query_one("#input-km-business", Input)
        priv_input = self.query_one("#input-km-private", Input)
        category_select = self.query_one("#select-category", Select)

        km_start = parse_km(km_start_input.value)

        multiplier = 2 if self._is_round_trip() else 1
        driven_km = int(self._selected_entry_km) * multiplier

        if km_start > 0:
            km_end_input.value = format_km(km_start + driven_km)

        current_category = str(category_select.value)
        if current_category in get_business_categories():
            if km_start > 0:
                biz_input.value = format_km(driven_km)
                priv_input.value = "0"
        else:
            # Alle Nicht-Business-Kategorien (private, fuel_private, ...) → km_private
            if km_start > 0:
                biz_input.value = "0"
                priv_input.value = format_km(driven_km)

    def _sync_purpose_to_category(self, new_category: str) -> None:
        """Aktualisiert den Reisezweck, wenn er dem Display-Namen der alten
        Kategorie entsprach.

        So wird 'Tanken' (von import_trips/fuel) beim Wechsel auf fuel_private
        automatisch zu 'Tanken nach Privatfahrt', waehrend selbst eingetragene
        Reisezwecke (z.B. 'Kundentermin XYZ') unveraendert bleiben.
        """
        if not self._current_category or self._current_category == new_category:
            return
        old_label = self._category_labels.get(self._current_category, "")
        new_label = self._category_labels.get(new_category, "")
        if not old_label or not new_label:
            return
        try:
            purpose_input = self.query_one("#input-purpose", Input)
        except Exception:
            return
        if purpose_input.value.strip() == old_label:
            purpose_input.value = new_label

    def _apply_informational_state(self, category: str) -> None:
        """Deaktiviert km-/Ziel-/Zweck-Felder fuer informationelle Kategorien
        (Anlieferung, Rueckgabe) und nullt die Werte. Nicht-informationelle
        Kategorien aktivieren die Felder wieder.
        """
        is_info = category in get_informational_categories()

        try:
            km_start_input = self.query_one("#input-km-start", Input)
            km_end = self.query_one("#input-km-end", Input)
            biz = self.query_one("#input-km-business", Input)
            priv = self.query_one("#input-km-private", Input)
            dest_select = self.query_one("#select-destination", Select)
            dest_area = self.query_one("#input-destination", TextArea)
            purpose = self.query_one("#input-purpose", Input)
            round_trip = self.query_one("#select-round-trip", Select)
        except Exception:
            return

        if is_info:
            # Informationelle Trips haben keine km-Werte
            km_start_input.value = ""
            km_end.value = ""
            biz.value = ""
            priv.value = ""
            dest_area.load_text("")
            purpose.value = ""
        else:
            # Beim Wechsel zurueck zu einer Normal-Kategorie km_start aus dem
            # Vorgaenger nachladen, falls es noch leer ist.
            if not km_start_input.value.strip():
                date_de = self.query_one("#input-date", Input).value.strip()
                iso = _de_to_iso(date_de) if date_de else ""
                if iso:
                    exclude_id = (
                        self._trip.id if (self._is_edit and self._trip) else None
                    )
                    try:
                        tf_input = self.query_one("#input-time-from", Input)
                        current_tf = tf_input.value.strip()
                    except Exception:
                        current_tf = ""
                    try:
                        pred = self._database.get_km_end_before(
                            iso,
                            time_from=current_tf,
                            exclude_trip_id=exclude_id,
                        )
                    except Exception:
                        pred = 0
                    if pred > 0:
                        km_start_input.value = format_km(pred)

        km_start_input.disabled = True  # bleibt in beiden Faellen read-only
        km_end.disabled = is_info
        biz.disabled = is_info
        priv.disabled = is_info
        dest_select.disabled = is_info
        dest_area.disabled = is_info
        purpose.disabled = is_info
        round_trip.disabled = is_info

    def _apply_fuel_visibility(self, category: str) -> None:
        """Blendet die Tankfelder nur bei fuel/fuel_private ein.

        Der Wert im Liter-Input bleibt beim Verstecken stehen — wenn der
        User die Kategorie zurueck auf fuel* dreht, soll der vorher
        eingetragene Wert noch da sein. action_save liest den Liter-Input
        ohnehin nur, wenn die finale Kategorie fuel* ist, also koennen
        "eingeschleppte" Restwerte gar nicht in eine falsche Kategorie
        gelangen.
        """
        is_fuel_cat = category in ("fuel", "fuel_private")
        try:
            row_liters = self.query_one("#row-fuel-liters", Horizontal)
            row_full = self.query_one("#row-fuel-full-tank", Horizontal)
        except Exception:
            return
        row_liters.display = is_fuel_cat
        row_full.display = is_fuel_cat

    def _rebalance_km_for_category(self, new_category: str) -> None:
        """Verschiebt km zwischen business und private, wenn die Kategorie
        gewechselt wird. Die Gesamt-km (km_business + km_private) bleiben
        erhalten, nur die Zuordnung aendert sich.
        """
        try:
            biz_input = self.query_one("#input-km-business", Input)
            priv_input = self.query_one("#input-km-private", Input)
        except Exception:
            return

        km_business = parse_km(biz_input.value)
        km_private = parse_km(priv_input.value)
        total = km_business + km_private
        if total <= 0:
            return

        if new_category in get_business_categories():
            biz_input.value = format_km(total)
            priv_input.value = "0"
        else:
            # Alle Nicht-Business-Kategorien (private, fuel_private, ...) → km_private
            biz_input.value = "0"
            priv_input.value = format_km(total)

    def _build_destination_options(self) -> list[tuple[str, str]]:
        """Baut die Auswahlliste fuer Ziele aus den DB-Adressen.

        Erster Eintrag ist immer "(leer)" um das Ziel-Feld per Auswahl
        leeren zu koennen — haendisches Loeschen im TextArea ist
        umstaendlicher.
        """
        options: list[tuple[str, str]] = []

        category_labels = {
            "customer": "Kunde",
            "gas_station": "Tankstelle",
            "shopping": "Einkaufen",
            "steuerberaterin": "Steuerberaterin",
            "restaurant": "Restaurant",
            "other": "Sonstige",
        }

        for addr in self._addresses:
            cat_label = category_labels.get(addr.category, addr.category)
            label = f"{cat_label}: {addr.name} ({addr.km:.0f} km)"
            options.append((label, f"addr_{addr.id}"))

        options.sort(key=lambda o: o[0].casefold())
        options.insert(0, ("(leer)", "__clear__"))

        home_address = self._database.get_setting("home_address", "").strip()
        if home_address:
            options.insert(1, (f"Zuhause: {home_address}", "__home__"))

        return options

    def _find_address_entry(self, key: str) -> AddressEntry | None:
        """Findet einen AddressEntry anhand des Select-Keys."""
        if not key.startswith("addr_"):
            return None

        try:
            addr_id = int(key.split("_", 1)[1])
        except (ValueError, IndexError):
            return None

        for addr in self._addresses:
            if addr.id == addr_id:
                return addr
        return None

    def on_mount(self) -> None:
        """Laedt Belege nach dem Mounten und setzt informational-Zustand."""
        if self._is_edit and self._trip is not None:
            self._refresh_docs()

        # Initialen informational-Zustand anhand der aktuellen Kategorie setzen
        try:
            category_select = self.query_one("#select-category", Select)
            current = str(category_select.value) if category_select.value != Select.BLANK else ""
        except Exception:
            current = ""
        if current:
            self._apply_informational_state(current)
            self._apply_fuel_visibility(current)
            self._current_category = current

    def _refresh_docs(self) -> None:
        """Aktualisiert die Belegliste."""
        if self._trip is None:
            return
        docs_list = self.query_one("#docs-list", Vertical)
        for child in list(docs_list.children):
            child.remove()

        docs = self._database.get_documents(trip_id=self._trip.id)
        for doc in docs:
            doc_id = int(doc.get("id", 0))
            path = str(doc.get("path", ""))
            name = Path(path).name or path
            desc = str(doc.get("description", ""))
            label_text = f"{name}  {desc}" if desc else name
            # Eckige Klammern im sichtbaren Text escapen, damit sie nicht als Markup interpretiert werden
            safe_label = label_text.replace("[", r"\[")
            markup = (
                f"[@click=screen.open_doc({doc_id})]{safe_label}[/]  "
                f"[@click=screen.delete_doc({doc_id})][red]x[/red][/]"
            )
            docs_list.mount(Static(markup, classes="doc-row"))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Reagiert auf Button-Klicks."""
        btn_id = event.button.id or ""
        if btn_id == "btn-save":
            self.action_save()
        elif btn_id == "btn-cancel":
            self.action_cancel()
        elif btn_id == "btn-delete":
            self.action_request_delete()
        elif btn_id == "btn-date-picker":
            self._open_date_picker()
        elif btn_id == "btn-add-doc":
            self._open_file_picker()

    def action_request_delete(self) -> None:
        """Schliesst den Dialog mit einer Delete-Anforderung an den Caller.

        Der Caller (app.py) fuehrt dann den Confirm-Dialog + das eigentliche
        Loeschen aus — so gibt es nur einen Confirm-Pfad.
        """
        if self._trip is None or self._trip.id <= 0:
            return
        self.dismiss(DELETE_REQUESTED)  # type: ignore[arg-type]

    def _open_date_picker(self) -> None:
        """Oeffnet den Kalender-Dialog zur Datumsauswahl."""
        from fahrtenbuch_app.screens.date_picker_screen import DatePickerScreen

        current_de = self.query_one("#input-date", Input).value.strip()
        current_iso = _de_to_iso(current_de) if current_de else self._default_date
        self.app.push_screen(
            DatePickerScreen(initial_date=current_iso),
            callback=self._on_date_selected,
        )

    def _on_date_selected(self, selected: str | None) -> None:
        """Callback nach Datumsauswahl aus dem Kalender."""
        if selected is not None:
            self.query_one("#input-date", Input).value = _iso_to_de(selected)

    def _open_file_picker(self) -> None:
        """Oeffnet den File-Picker-Screen."""
        from fahrtenbuch_app.screens.file_picker_screen import FilePickerScreen

        start = self._database.path
        self.app.push_screen(
            FilePickerScreen(start_path=start),
            callback=self._on_file_selected,
        )

    def _on_file_selected(self, selected: Path | None) -> None:
        """Callback nach Dateiauswahl — speichert Dokument in DB."""
        if selected is None or self._trip is None:
            return
        try:
            rel_path = os.path.relpath(str(selected), str(self._database.path))
        except ValueError:
            rel_path = str(selected)
        self._database.add_document(rel_path, trip_id=self._trip.id)
        self._refresh_docs()

    def action_open_doc(self, doc_id: int) -> None:
        """Oeffnet einen Beleg im Standard-Programm."""
        if self._trip is None:
            return
        docs = self._database.get_documents(trip_id=self._trip.id)
        for doc in docs:
            if int(doc.get("id", 0)) != doc_id:
                continue
            rel_or_abs = str(doc.get("path", ""))
            file_path = Path(rel_or_abs)
            if not file_path.is_absolute():
                file_path = Path(self._database.path) / file_path
            try:
                from fahrtenbuch_app.services.os_utils import open_file_in_system
                open_file_in_system(file_path)
            except FileNotFoundError:
                self.notify(f"Datei nicht gefunden: {file_path}", severity="error")
            except Exception as exc:
                self.notify(f"Konnte Datei nicht oeffnen: {exc}", severity="error")
            return

    def action_delete_doc(self, doc_id: int) -> None:
        """Loescht ein Dokument."""
        self._database.delete_document(doc_id)
        self._refresh_docs()

    def action_save(self) -> None:
        """Speichert die Fahrt."""
        trip_date_input = self.query_one("#input-date", Input).value.strip()
        if not trip_date_input:
            self.notify("Datum ist erforderlich", severity="error")
            return
        trip_date = _de_to_iso(trip_date_input)

        category_select = self.query_one("#select-category", Select)
        category = str(category_select.value) if category_select.value != Select.BLANK else "business"

        km_start = parse_km(self.query_one("#input-km-start", Input).value)
        km_end = parse_km(self.query_one("#input-km-end", Input).value)
        km_business = parse_km(self.query_one("#input-km-business", Input).value)
        km_private = parse_km(self.query_one("#input-km-private", Input).value)

        is_informational = category in get_informational_categories()

        if is_informational:
            # Informationelle Trips (Anlieferung, Rueckgabe) haben keine km,
            # kein Ziel, keinen Zweck. Die DB-Schicht forciert 0/0 auch noch
            # einmal — hier schon sauber setzen, damit die Werte konsistent
            # im Trip-Objekt landen.
            km_start = 0
            km_end = 0
            km_business = 0
            km_private = 0
            destination_value = ""
            purpose_value = ""
            round_trip = False
        else:
            # Wenn der User die km manuell in genau eine Spalte geschrieben hat,
            # die nicht zur Kategorie passt, gleicht sich die Kategorie an — nicht
            # umgekehrt. Frueher hat ein Safety-Net hier die User-Eingaben
            # ueberschrieben, sodass "km auf privat umbuchen" nie gespeichert wurde.
            if km_private > 0 and km_business == 0 and category in get_business_categories():
                category = "fuel_private" if category == "fuel" else "private"
            elif km_business > 0 and km_private == 0 and category not in get_business_categories():
                category = "fuel" if category == "fuel_private" else "business"

            destination_value = self.query_one("#input-destination", TextArea).text.strip()
            purpose_value = self.query_one("#input-purpose", Input).value.strip()
            round_trip = self._is_round_trip()

        # Tankfelder nur bei fuel/fuel_private beruecksichtigen
        fuel_liters = 0.0
        fuel_full_tank = False
        if category in ("fuel", "fuel_private"):
            try:
                fuel_liters = _parse_liters(
                    self.query_one("#input-fuel-liters", Input).value
                )
                fuel_full_tank = bool(
                    self.query_one("#check-fuel-full-tank", Checkbox).value
                )
            except Exception:
                pass

        trip = Trip(
            id=self._trip.id if self._is_edit and self._trip else 0,
            date=trip_date,
            time_from=self.query_one("#input-time-from", Input).value.strip(),
            time_to=self.query_one("#input-time-to", Input).value.strip(),
            destination=destination_value,
            purpose=purpose_value,
            km_start=km_start,
            km_end=km_end,
            km_business=km_business,
            km_private=km_private,
            category=category,
            round_trip=round_trip,
            fuel_liters=fuel_liters,
            fuel_full_tank=fuel_full_tank,
        )
        self.dismiss(trip)

    def action_cancel(self) -> None:
        """Bricht ab."""
        self.dismiss(None)
