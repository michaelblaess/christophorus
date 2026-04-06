"""Settings-Dialog mit Tabs fuer Fahrzeug, Adressen etc."""

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
    TabbedContent,
    TabPane,
)

from fahrtenbuch_app.models.settings import AddressEntry
from fahrtenbuch_app.models.vehicle import Vehicle
from fahrtenbuch_app.services.database import Database

_COLOR_OPTIONS: list[tuple[str, str]] = [
    ("Gruen", "green"),
    ("Blau", "blue"),
    ("Gelb", "yellow"),
    ("Magenta", "magenta"),
    ("Rot", "red"),
    ("Cyan", "cyan"),
    ("Weiss", "white"),
]

_STATE_OPTIONS: list[tuple[str, str]] = [
    ("Baden-Wuerttemberg", "BW"),
    ("Bayern", "BY"),
    ("Berlin", "BE"),
    ("Brandenburg", "BB"),
    ("Bremen", "HB"),
    ("Hamburg", "HH"),
    ("Hessen", "HE"),
    ("Mecklenburg-Vorpommern", "MV"),
    ("Niedersachsen", "NI"),
    ("Nordrhein-Westfalen", "NW"),
    ("Rheinland-Pfalz", "RP"),
    ("Saarland", "SL"),
    ("Sachsen", "SN"),
    ("Sachsen-Anhalt", "ST"),
    ("Schleswig-Holstein", "SH"),
    ("Thueringen", "TH"),
]


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
    SettingsScreen .cat-block {
        height: auto;
        margin-bottom: 1;
        padding: 0 1;
        border: solid $surface-lighten-1;
    }
    SettingsScreen .cat-block Label {
        width: 22;
    }
    SettingsScreen .cat-block Input {
        width: 1fr;
    }
    SettingsScreen .cat-block Select {
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
        self._federal_state = database.get_setting("federal_state", "BB")
        self._addresses: dict[str, list[AddressEntry]] = {}
        self._load_addresses()
        self._categories: list[dict[str, object]] = database.get_categories()

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

                with TabPane("Kategorien", id="tab-categories"):
                    with VerticalScroll():
                        yield from self._category_fields()

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
        with Horizontal(classes="form-row"):
            yield Label("Bundesland:")
            yield Select(
                options=_STATE_OPTIONS,
                value=self._federal_state,
                id="select-federal-state",
            )

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

    def _category_fields(self) -> ComposeResult:
        """Felder fuer das Kategorien-Tab."""
        for i, cat in enumerate(self._categories):
            cat_id = int(cat.get("id", 0))
            name = str(cat.get("name", ""))
            display_name = str(cat.get("display_name", ""))
            counts_biz = bool(cat.get("counts_as_business", 1))
            color = str(cat.get("color", "green"))

            with Vertical(classes="cat-block"):
                with Horizontal(classes="form-row"):
                    yield Label("Schluessel (intern):")
                    yield Input(value=name, id=f"cat-name-{i}")
                with Horizontal(classes="form-row"):
                    yield Label("Anzeigename:")
                    yield Input(value=display_name, id=f"cat-display-{i}")
                with Horizontal(classes="form-row"):
                    yield Label("Farbe:")
                    yield Select(
                        options=_COLOR_OPTIONS,
                        value=color,
                        id=f"cat-color-{i}",
                    )
                with Horizontal(classes="form-row"):
                    yield Label("")
                    yield Checkbox(
                        "Zaehlt als geschaeftlich",
                        value=counts_biz,
                        id=f"cat-biz-{i}",
                    )
                with Horizontal(classes="form-row"):
                    yield Label("")
                    yield Button(
                        "Loeschen",
                        variant="error",
                        id=f"btn-del-cat-{i}",
                    )

        yield Button(
            "+ Kategorie hinzufuegen",
            variant="success",
            id="btn-add-cat",
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
            if prefix == "cat":
                self._add_category_entry()
            else:
                self._add_address_entry(prefix)
        elif btn_id.startswith("btn-del-cat-"):
            self._delete_category_entry(btn_id)

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

    def _add_category_entry(self) -> None:
        """Fuegt eine neue leere Kategorie hinzu."""
        new_cat: dict[str, object] = {
            "id": 0,
            "name": "",
            "display_name": "",
            "counts_as_business": 1,
            "color": "green",
        }
        self._categories.append(new_cat)
        self.notify("Kategorie hinzugefuegt — bitte Speichern und neu oeffnen")

    def _delete_category_entry(self, btn_id: str) -> None:
        """Loescht eine Kategorie anhand des Button-IDs."""
        try:
            idx = int(btn_id.replace("btn-del-cat-", ""))
        except ValueError:
            return

        if idx < 0 or idx >= len(self._categories):
            return

        cat = self._categories[idx]
        cat_id = int(cat.get("id", 0))
        cat_name = str(cat.get("name", ""))

        if cat_id > 0:
            self._database.delete_category(cat_id)

        self._categories.pop(idx)
        self.notify(
            f"Kategorie '{cat_name}' geloescht — bitte Speichern und neu oeffnen"
        )

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

        # Bundesland speichern
        state_select = self.query_one("#select-federal-state", Select)
        if state_select.value != Select.BLANK:
            self._database.set_setting("federal_state", str(state_select.value))

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

        # Kategorien speichern
        self._save_categories()

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

    def _save_categories(self) -> None:
        """Speichert alle Kategorien in die Datenbank."""
        for i, cat in enumerate(self._categories):
            cat_id = int(cat.get("id", 0))
            name = self._get_input(f"cat-name-{i}")
            display_name = self._get_input(f"cat-display-{i}")

            color_select = self._query_select(f"cat-color-{i}")
            color = color_select if color_select else "green"

            counts_biz = self._get_checkbox(f"cat-biz-{i}")

            if not name:
                continue

            if cat_id > 0:
                self._database.update_category(
                    cat_id, name, display_name, counts_biz, color
                )
            else:
                self._database.add_category(
                    name, display_name, counts_biz, color
                )

    def _query_select(self, select_id: str) -> str:
        """Liest einen Select-Wert sicher aus."""
        try:
            select = self.query_one(f"#{select_id}", Select)
            if select.value != Select.BLANK:
                return str(select.value)
        except Exception:
            pass
        return ""

    def _get_checkbox(self, checkbox_id: str) -> bool:
        """Liest einen Checkbox-Wert sicher aus."""
        try:
            return self.query_one(f"#{checkbox_id}", Checkbox).value
        except Exception:
            return False

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
