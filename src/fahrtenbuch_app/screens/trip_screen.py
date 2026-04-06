"""Fahrt anlegen oder bearbeiten."""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Label, Select, Static

from fahrtenbuch_app.models.settings import AddressEntry
from fahrtenbuch_app.models.trip import Trip, get_business_categories
from fahrtenbuch_app.services.database import Database


class TripScreen(ModalScreen[Trip | None]):
    """Dialog zum Anlegen oder Bearbeiten einer Fahrt."""

    DEFAULT_CSS = """
    TripScreen {
        align: center middle;
    }
    TripScreen > VerticalScroll {
        width: 80;
        height: auto;
        max-height: 38;
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
    }
    TripScreen Select {
        width: 1fr;
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
        self._is_edit = trip is not None
        self._addresses: list[AddressEntry] = []

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

        default_date = trip.date if self._is_edit else self._default_date
        default_km_start = trip.km_start if self._is_edit else self._last_km_end

        with VerticalScroll():
            yield Static(title, id="title")

            with Horizontal(classes="form-row"):
                yield Label("Datum:")
                yield Input(
                    value=default_date,
                    placeholder="YYYY-MM-DD",
                    id="input-date",
                )

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
                yield Input(
                    value=trip.destination,
                    placeholder="Strasse, PLZ Ort",
                    id="input-destination",
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
                    value=str(default_km_start) if default_km_start > 0 else "",
                    placeholder="Kilometerstand",
                    id="input-km-start",
                )

            with Horizontal(classes="form-row"):
                yield Label("km Ende:")
                yield Input(
                    value=str(trip.km_end) if self._is_edit and trip.km_end > 0 else "",
                    placeholder="Kilometerstand",
                    id="input-km-end",
                )

            with Horizontal(classes="form-row"):
                yield Label("km geschaeftl.:")
                yield Input(
                    value=str(trip.km_business) if self._is_edit and trip.km_business > 0 else "",
                    placeholder="0",
                    id="input-km-business",
                )

            with Horizontal(classes="form-row"):
                yield Label("km privat:")
                yield Input(
                    value=str(trip.km_private) if self._is_edit and trip.km_private > 0 else "",
                    placeholder="0",
                    id="input-km-private",
                )

            with Horizontal(classes="button-row"):
                yield Button("Speichern (Ctrl+S)", variant="primary", id="btn-save")
                yield Button("Abbrechen (Esc)", variant="default", id="btn-cancel")

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

    def on_select_changed(self, event: Select.Changed) -> None:
        """Fuellt Adresse und km wenn ein Ziel ausgewaehlt wird."""
        if event.select.id != "select-destination":
            return
        if event.value == Select.BLANK:
            return

        key = str(event.value)
        entry = self._find_address_entry(key)
        if entry is None:
            return

        dest_input = self.query_one("#input-destination", Input)
        dest_input.value = f"{entry.name}\n{entry.address}"

        km_start_input = self.query_one("#input-km-start", Input)
        km_end_input = self.query_one("#input-km-end", Input)

        try:
            km_start = int(km_start_input.value.strip())
        except ValueError:
            km_start = 0

        if km_start > 0 and entry.km > 0:
            km_end = km_start + int(entry.km)
            km_end_input.value = str(km_end)

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

        biz_input = self.query_one("#input-km-business", Input)
        priv_input = self.query_one("#input-km-private", Input)
        current_category = str(category_select.value)

        if current_category in get_business_categories():
            if km_start > 0 and entry.km > 0:
                biz_input.value = str(int(entry.km))
                priv_input.value = "0"
        elif current_category == "private":
            if km_start > 0 and entry.km > 0:
                biz_input.value = "0"
                priv_input.value = str(int(entry.km))

    def _build_destination_options(self) -> list[tuple[str, str]]:
        """Baut die Auswahlliste fuer Ziele aus den DB-Adressen."""
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

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Reagiert auf Button-Klicks."""
        if event.button.id == "btn-save":
            self.action_save()
        elif event.button.id == "btn-cancel":
            self.action_cancel()

    def action_save(self) -> None:
        """Speichert die Fahrt."""
        trip_date = self.query_one("#input-date", Input).value.strip()
        if not trip_date:
            self.notify("Datum ist erforderlich", severity="error")
            return

        category_select = self.query_one("#select-category", Select)
        category = str(category_select.value) if category_select.value != Select.BLANK else "business"

        try:
            km_start = int(self.query_one("#input-km-start", Input).value.strip() or "0")
        except ValueError:
            km_start = 0

        try:
            km_end = int(self.query_one("#input-km-end", Input).value.strip() or "0")
        except ValueError:
            km_end = 0

        try:
            km_business = int(self.query_one("#input-km-business", Input).value.strip() or "0")
        except ValueError:
            km_business = 0

        try:
            km_private = int(self.query_one("#input-km-private", Input).value.strip() or "0")
        except ValueError:
            km_private = 0

        trip = Trip(
            id=self._trip.id if self._is_edit and self._trip else 0,
            date=trip_date,
            time_from=self.query_one("#input-time-from", Input).value.strip(),
            time_to=self.query_one("#input-time-to", Input).value.strip(),
            destination=self.query_one("#input-destination", Input).value.strip(),
            purpose=self.query_one("#input-purpose", Input).value.strip(),
            km_start=km_start,
            km_end=km_end,
            km_business=km_business,
            km_private=km_private,
            category=category,
        )
        self.dismiss(trip)

    def action_cancel(self) -> None:
        """Bricht ab."""
        self.dismiss(None)
