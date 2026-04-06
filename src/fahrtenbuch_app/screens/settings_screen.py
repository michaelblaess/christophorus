"""Settings-Dialog mit Tabs fuer Fahrzeug, Adressen etc."""

from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    Input,
    Label,
    Static,
    TabbedContent,
    TabPane,
)

from fahrtenbuch_app.models.settings import AddressEntry
from fahrtenbuch_app.models.vehicle import Vehicle
from fahrtenbuch_app.services.database import Database


class SettingsScreen(ModalScreen[bool | None]):
    """Einstellungen mit Tabs — speichert in die SQLite-Datenbank."""

    DEFAULT_CSS = """
    SettingsScreen {
        align: center middle;
    }
    SettingsScreen > Vertical {
        width: 90;
        height: 36;
        background: $surface;
        border: thick $accent;
        padding: 1 2;
    }
    SettingsScreen #title {
        text-align: center;
        text-style: bold;
        margin-bottom: 1;
    }
    SettingsScreen .form-row {
        height: auto;
        margin-bottom: 1;
    }
    SettingsScreen .form-row Label {
        width: 22;
        padding: 0 1;
    }
    SettingsScreen .form-row Input {
        width: 1fr;
    }
    SettingsScreen .addr-block {
        height: auto;
        margin-bottom: 1;
        padding: 0 1;
        border: solid $surface-lighten-1;
    }
    SettingsScreen .addr-block Label {
        width: 12;
    }
    SettingsScreen .addr-block Input {
        width: 1fr;
    }
    SettingsScreen .button-row {
        height: auto;
        margin-top: 1;
        align: center middle;
        dock: bottom;
    }
    SettingsScreen Button {
        margin: 0 1;
    }
    """

    BINDINGS = [
        Binding("escape", "cancel", "Abbrechen"),
        Binding("ctrl+s", "save", "Speichern"),
    ]

    def __init__(self, database: Database, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._database = database
        self._vehicle = database.get_vehicle()
        self._addresses: dict[str, list[AddressEntry]] = {}
        self._load_addresses()

    def _load_addresses(self) -> None:
        """Laedt alle Adressen aus der Datenbank gruppiert nach Kategorie."""
        categories = [
            "customer", "gas_station", "shopping",
            "steuerberaterin", "restaurant", "other",
        ]
        for cat in categories:
            rows = self._database.get_addresses(cat)
            self._addresses[cat] = [
                AddressEntry(
                    id=int(row.get("id", 0)),
                    category=str(row.get("category", "")),
                    name=str(row.get("name", "")),
                    address=str(row.get("address", "")),
                    km=float(row.get("km", 0.0)),
                )
                for row in rows
            ]

    def compose(self) -> ComposeResult:
        """Erstellt die Settings-Tabs."""
        v = self._vehicle
        home_address = self._database.get_setting("home_address", "")

        with Vertical():
            yield Static("Einstellungen", id="title")

            with TabbedContent():
                with TabPane("Fahrzeug", id="tab-vehicle"):
                    with VerticalScroll():
                        yield from self._vehicle_fields(v)

                with TabPane("Wohnung", id="tab-home"):
                    with VerticalScroll():
                        yield from self._home_fields(home_address)

                with TabPane("Kunden", id="tab-customers"):
                    with VerticalScroll():
                        yield from self._address_list_fields(
                            self._addresses.get("customer", []), "cust"
                        )

                with TabPane("Tankstellen", id="tab-gas"):
                    with VerticalScroll():
                        yield from self._address_list_fields(
                            self._addresses.get("gas_station", []), "gas"
                        )

                with TabPane("Einkaufen", id="tab-shopping"):
                    with VerticalScroll():
                        yield from self._address_list_fields(
                            self._addresses.get("shopping", []), "shop"
                        )

                with TabPane("Steuerberater", id="tab-steuerberater"):
                    with VerticalScroll():
                        yield from self._steuerberater_fields()

                with TabPane("Restaurants", id="tab-restaurants"):
                    with VerticalScroll():
                        yield from self._address_list_fields(
                            self._addresses.get("restaurant", []), "rest"
                        )

                with TabPane("Sonstige", id="tab-other"):
                    with VerticalScroll():
                        yield from self._address_list_fields(
                            self._addresses.get("other", []), "other"
                        )

            with Horizontal(classes="button-row"):
                yield Button(
                    "Speichern (Ctrl+S)", variant="primary", id="btn-save"
                )
                yield Button(
                    "Abbrechen (Esc)", variant="default", id="btn-cancel"
                )

    def _vehicle_fields(self, v: Vehicle) -> ComposeResult:
        """Felder fuer das Fahrzeug-Tab."""
        with Horizontal(classes="form-row"):
            yield Label("Fahrzeug-Name:")
            yield Input(value=v.name, id="v-name")
        with Horizontal(classes="form-row"):
            yield Label("Kennzeichen:")
            yield Input(value=v.plate, id="v-plate")
        with Horizontal(classes="form-row"):
            yield Label("Vertragsnummer:")
            yield Input(value=v.contract_number, id="v-contract")
        with Horizontal(classes="form-row"):
            yield Label("km/Monat (Inklusiv):")
            yield Input(value=str(v.lease_km_per_month), id="v-lease-km")
        with Horizontal(classes="form-row"):
            yield Label("Start-km:")
            yield Input(value=str(v.start_km) if v.start_km > 0 else "", id="v-start-km")
        with Horizontal(classes="form-row"):
            yield Label("End-km:")
            yield Input(value=str(v.end_km) if v.end_km > 0 else "", id="v-end-km")
        with Horizontal(classes="form-row"):
            yield Label("Leasingbeginn:")
            yield Input(
                value=v.start_date,
                placeholder="DD.MM.YYYY",
                id="v-start-date",
            )
        with Horizontal(classes="form-row"):
            yield Label("Leasingende:")
            yield Input(
                value=v.end_date,
                placeholder="DD.MM.YYYY",
                id="v-end-date",
            )
        with Horizontal(classes="form-row"):
            yield Label("Leasingdauer (Monate):")
            yield Input(value=str(v.lease_months), id="v-lease-months")

    def _home_fields(self, home_address: str) -> ComposeResult:
        """Felder fuer die Wohnadresse."""
        with Horizontal(classes="form-row"):
            yield Label("Wohnadresse:")
            yield Input(
                value=home_address,
                placeholder="Strasse, PLZ Ort",
                id="home-address",
            )

    def _address_list_fields(
        self, entries: list[AddressEntry], prefix: str
    ) -> ComposeResult:
        """Felder fuer eine Adressliste."""
        for i, entry in enumerate(entries):
            with Vertical(classes="addr-block"):
                with Horizontal(classes="form-row"):
                    yield Label("Name:")
                    yield Input(value=entry.name, id=f"{prefix}-name-{i}")
                with Horizontal(classes="form-row"):
                    yield Label("Adresse:")
                    yield Input(value=entry.address, id=f"{prefix}-addr-{i}")
                with Horizontal(classes="form-row"):
                    yield Label("Entfernung km:")
                    yield Input(
                        value=str(entry.km) if entry.km > 0 else "",
                        id=f"{prefix}-km-{i}",
                    )

        yield Button(
            "+ Hinzufuegen",
            variant="success",
            id=f"btn-add-{prefix}",
        )

    def _steuerberater_fields(self) -> ComposeResult:
        """Felder fuer Steuerberater(in)."""
        st_list = self._addresses.get("steuerberaterin", [])
        st = st_list[0] if st_list else AddressEntry()

        with Vertical(classes="addr-block"):
            with Horizontal(classes="form-row"):
                yield Label("Name:")
                yield Input(value=st.name, id="st-name")
            with Horizontal(classes="form-row"):
                yield Label("Adresse:")
                yield Input(value=st.address, id="st-addr")
            with Horizontal(classes="form-row"):
                yield Label("Entfernung km:")
                yield Input(
                    value=str(st.km) if st.km > 0 else "",
                    id="st-km",
                )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        """Reagiert auf Button-Klicks."""
        btn_id = event.button.id or ""
        if btn_id == "btn-save":
            self.action_save()
        elif btn_id == "btn-cancel":
            self.action_cancel()
        elif btn_id.startswith("btn-add-"):
            prefix = btn_id.replace("btn-add-", "")
            self._add_address_entry(prefix)

    def _add_address_entry(self, prefix: str) -> None:
        """Fuegt einen leeren Adresseintrag hinzu."""
        category_map = {
            "cust": "customer",
            "gas": "gas_station",
            "shop": "shopping",
            "rest": "restaurant",
            "other": "other",
        }
        cat = category_map.get(prefix)
        if cat:
            new_entry = AddressEntry(category=cat)
            if cat not in self._addresses:
                self._addresses[cat] = []
            self._addresses[cat].append(new_entry)
        self.notify("Eintrag hinzugefuegt — bitte Speichern und neu oeffnen")

    def action_save(self) -> None:
        """Speichert alle Settings in die SQLite-Datenbank."""
        # Fahrzeug speichern
        vehicle = Vehicle(
            name=self._get_input("v-name"),
            plate=self._get_input("v-plate"),
            contract_number=self._get_input("v-contract"),
            lease_km_per_month=self._parse_int("v-lease-km", 1500),
            start_km=self._parse_int("v-start-km", 0),
            end_km=self._parse_int("v-end-km", 0),
            start_date=self._get_input("v-start-date"),
            end_date=self._get_input("v-end-date"),
            lease_months=self._parse_int("v-lease-months", 12),
        )
        self._database.save_vehicle(vehicle)

        # Wohnadresse speichern
        self._database.set_setting(
            "home_address", self._get_input("home-address")
        )

        # Adressen speichern
        self._save_address_list("customer", "cust")
        self._save_address_list("gas_station", "gas")
        self._save_address_list("shopping", "shop")
        self._save_address_list("restaurant", "rest")

        # Steuerberaterin speichern
        self._save_steuerberaterin()

        self.dismiss(True)

    def _save_address_list(self, category: str, prefix: str) -> None:
        """Speichert eine Adressliste in die Datenbank."""
        entries = self._addresses.get(category, [])
        for i, entry in enumerate(entries):
            name = self._get_input(f"{prefix}-name-{i}")
            address = self._get_input(f"{prefix}-addr-{i}")
            km = self._parse_float(f"{prefix}-km-{i}")

            if entry.id > 0:
                self._database.update_address(entry.id, name, address, km)
            else:
                if name or address:
                    self._database.add_address(category, name, address, km)

    def _save_steuerberaterin(self) -> None:
        """Speichert die Steuerberaterin-Adresse."""
        st_list = self._addresses.get("steuerberaterin", [])
        name = self._get_input("st-name")
        address = self._get_input("st-addr")
        km = self._parse_float("st-km")

        if st_list and st_list[0].id > 0:
            self._database.update_address(st_list[0].id, name, address, km)
        else:
            if name or address:
                self._database.add_address(
                    "steuerberaterin", name, address, km
                )

    def _get_input(self, input_id: str) -> str:
        """Liest einen Input-Wert sicher aus."""
        try:
            return self.query_one(f"#{input_id}", Input).value.strip()
        except Exception:
            return ""

    def _parse_int(self, input_id: str, default: int = 0) -> int:
        """Liest einen Integer-Wert sicher aus."""
        try:
            return int(self._get_input(input_id) or str(default))
        except ValueError:
            return default

    def _parse_float(self, input_id: str) -> float:
        """Liest einen Float-Wert sicher aus."""
        try:
            return float(self._get_input(input_id) or "0")
        except ValueError:
            return 0.0

    def action_cancel(self) -> None:
        """Bricht ab."""
        self.dismiss(None)
