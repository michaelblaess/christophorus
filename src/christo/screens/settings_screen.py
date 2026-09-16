"""Settings-Dialog mit Tabs fuer Fahrzeug, Adressen etc.

Subklasse von ``textual_widgets.BaseSettingsScreen`` — der Basisdialog
liefert die Aussenhuelle (Titel, Save/Cancel, Sprach-Tab, Speicherort-Tab,
einheitliche Bindings). Wir steuern nur die app-spezifischen Tabs bei.
"""

from pathlib import Path
from typing import Any

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.widgets import (
    Button,
    Checkbox,
    Input,
    Label,
    Select,
    Static,
    TabPane,
)
from textual_widgets import BaseSettingsScreen
from textual_widgets.keymap import KeymapStyle

from christo.i18n import t
from christo.models.settings import AddressEntry, GlobalConfig
from christo.models.vehicle import Vehicle
from christo.services.database import Database
from christo.services.formatting import format_km, parse_km


def _format_km(value: float) -> str:
    """Formatiert einen km-Wert fuer die Anzeige mit deutschem Komma.

    - leere / nicht positive Werte → ""
    - ganze Zahlen ohne Nachkommastellen (z.B. 42)
    - sonst mit deutschem Komma (z.B. "3,5")
    """
    if value is None or value <= 0:
        return ""
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.2f}".rstrip("0").rstrip(".").replace(".", ",")


def _format_float(value: float) -> str:
    """Formatiert eine Gleitkommazahl fuer Eingabefelder."""
    if value is None or value <= 0:
        return ""
    if float(value).is_integer():
        return str(int(value))
    return f"{value:.2f}".rstrip("0").rstrip(".").replace(".", ",")


def _parse_float(raw: str) -> float:
    """Parst eine Gleitkommazahl aus der UI (mit deutschem Komma)."""
    s = (raw or "").strip().replace(",", ".")
    if not s:
        return 0.0
    try:
        return float(s)
    except ValueError:
        return 0.0


def _color_options() -> list[tuple[str, str]]:
    return [
        (t("settings.color.green"), "green"),
        (t("settings.color.blue"), "blue"),
        (t("settings.color.yellow"), "yellow"),
        (t("settings.color.magenta"), "magenta"),
        (t("settings.color.red"), "red"),
        (t("settings.color.cyan"), "cyan"),
        (t("settings.color.white"), "white"),
    ]


def _journal_mode_options() -> list[tuple[str, str]]:
    return [
        (t("settings.journal.delete"), "DELETE"),
        (t("settings.journal.wal"), "WAL"),
        (t("settings.journal.truncate"), "TRUNCATE"),
        (t("settings.journal.persist"), "PERSIST"),
        (t("settings.journal.memory"), "MEMORY"),
        (t("settings.journal.off"), "OFF"),
    ]


def _keymap_style_options() -> list[tuple[str, str]]:
    """Baut die Auswahl der Belegungsstile.

    Als Funktion und nicht als Konstante, weil `t()` sonst beim Import
    ausgewertet wuerde und ein Sprachwechsel die Beschriftungen nicht erreichte.

    Returns:
        Paare aus Beschriftung und gespeichertem Wert. Der leere Wert heisst
        "nach Betriebssystem" und ist die Vorgabe.
    """
    return [
        (t("settings.keymap_style_auto"), ""),
        (t("settings.keymap_style_classic"), KeymapStyle.CLASSIC.value),
        (t("settings.keymap_style_function_keys"), KeymapStyle.FUNCTION_KEYS.value),
    ]


def _state_options() -> list[tuple[str, str]]:
    return [
        (t("settings.state.bw"), "BW"),
        (t("settings.state.by"), "BY"),
        (t("settings.state.be"), "BE"),
        (t("settings.state.bb"), "BB"),
        (t("settings.state.hb"), "HB"),
        (t("settings.state.hh"), "HH"),
        (t("settings.state.he"), "HE"),
        (t("settings.state.mv"), "MV"),
        (t("settings.state.ni"), "NI"),
        (t("settings.state.nw"), "NW"),
        (t("settings.state.rp"), "RP"),
        (t("settings.state.sl"), "SL"),
        (t("settings.state.sn"), "SN"),
        (t("settings.state.st"), "ST"),
        (t("settings.state.sh"), "SH"),
        (t("settings.state.th"), "TH"),
    ]


class SettingsScreen(BaseSettingsScreen):  # type: ignore[misc]
    """Einstellungen mit Tabs — speichert in die SQLite-Datenbank.

    Die Persistenz laeuft NICHT ueber das settings-Dict der Basis (das
    dient nur fuer einfache Key/Value-Settings wie Sprache). Adressen,
    Kategorien, Fahrzeug etc. speichern wir direkt in die DB; die App
    schaut nur, ob das Result-Dict nicht None ist und laedt selbst neu.
    """

    DEFAULT_CSS = """
    SettingsScreen .addr-block {
        height: auto;
        margin-bottom: 1;
        padding: 0 1;
        border: solid $surface-lighten-1;
    }
    SettingsScreen .cat-block {
        height: auto;
        margin-bottom: 1;
        padding: 0 1;
        border: solid $surface-lighten-1;
    }
    SettingsScreen .addr-block Label,
    SettingsScreen .cat-block Label {
        width: 16;
        padding: 1 1;
    }
    SettingsScreen .addr-block Input,
    SettingsScreen .cat-block Input,
    SettingsScreen .cat-block Select {
        width: 1fr;
    }
    """

    def __init__(self, database: Database, config: GlobalConfig) -> None:
        # Das settings-Dict enthaelt aktuell nur die Sprache — die Basis
        # rendert daraus den Sprach-Tab. Alles andere bleibt in der DB.
        super().__init__({"language": config.language}, lang=config.language)
        self._database = database
        self._config = config
        self._vehicle = database.get_vehicle()
        self._federal_state = database.get_setting("federal_state", "BB")
        self._journal_mode = database.get_setting("db_journal_mode", "DELETE").upper()
        self._show_id_column = database.get_setting("show_id_column", "0") == "1"
        self._show_code_column = database.get_setting("show_code_column", "0") == "1"
        self._check_ghost_trips = database.get_setting("check_ghost_trips", "0") == "1"
        self._fuel_winter_tolerance = database.get_setting("fuel_winter_tolerance", "1") == "1"
        self._show_fuel_column = database.get_setting("show_fuel_column", "0") == "1"
        self._export_include_prev_december = database.get_setting("export_include_prev_december", "0") == "1"
        self._addresses: dict[str, list[AddressEntry]] = {}
        self._load_addresses()
        self._categories: list[dict[str, Any]] = database.get_categories()

    def _load_addresses(self) -> None:
        """Laedt alle Adressen aus der Datenbank gruppiert nach Kategorie."""
        categories = [
            "customer",
            "gas_station",
            "shopping",
            "steuerberaterin",
            "restaurant",
            "other",
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

    # ------------------------------------------------------------------
    # BaseSettingsScreen Hooks
    # ------------------------------------------------------------------
    def app_tabs(self) -> ComposeResult:
        """Liefert die app-spezifischen TabPanes."""
        v = self._vehicle
        home_address = self._database.get_setting("home_address", "")

        with TabPane(t("settings.tab.vehicle"), id="tab-vehicle"), VerticalScroll():
            yield from self._vehicle_fields(v)

        with TabPane(t("settings.tab.home"), id="tab-home"), VerticalScroll():
            yield from self._home_fields(home_address)

        with TabPane(t("settings.tab.customers"), id="tab-customers"), VerticalScroll():
            yield from self._address_list_fields(self._addresses.get("customer", []), "cust")

        with TabPane(t("settings.tab.gas"), id="tab-gas"), VerticalScroll():
            yield from self._address_list_fields(self._addresses.get("gas_station", []), "gas")

        with TabPane(t("settings.tab.shopping"), id="tab-shopping"), VerticalScroll():
            yield from self._address_list_fields(self._addresses.get("shopping", []), "shop")

        with TabPane(t("settings.tab.tax_advisor"), id="tab-steuerberater"), VerticalScroll():
            yield from self._steuerberater_fields()

        with TabPane(t("settings.tab.restaurants"), id="tab-restaurants"), VerticalScroll():
            yield from self._address_list_fields(self._addresses.get("restaurant", []), "rest")

        with TabPane(t("settings.tab.other"), id="tab-other"), VerticalScroll():
            yield from self._address_list_fields(self._addresses.get("other", []), "other")

        with TabPane(t("settings.tab.categories"), id="tab-categories"), VerticalScroll():
            yield from self._category_fields()

        with TabPane(t("settings.tab.database"), id="tab-database"), VerticalScroll():
            yield from self._database_fields()

        with TabPane(t("settings.tab.keyboard"), id="tab-keyboard"), VerticalScroll():
            yield from self._keyboard_fields()

    def _keyboard_fields(self) -> ComposeResult:
        """Felder fuer den Reiter Tastatur (Stil und Vim-Navigation)."""
        yield Static(t("settings.keymap_intro"), classes="hint")
        with Horizontal(classes="field-row"):
            yield Label(t("settings.keymap_style"), classes="field-label")
            yield Select(
                options=_keymap_style_options(),
                value=self._config.keymap_style or "",
                allow_blank=False,
                id="set-keymap-style",
                classes="field-input",
            )
        checkbox = Checkbox(t("settings.keymap_vim"), value=self._config.keymap_vim, id="set-keymap-vim")
        checkbox.tooltip = t("settings.keymap_vim_tip")
        yield checkbox
        yield Static(t("settings.keymap_custom_hint"), classes="hint")

    def storage_paths(self) -> list[tuple[str, Path]]:
        """Pfade fuer den Speicherort-Tab der Basis."""
        return [
            (t("settings.storage.config"), self._config.CONFIG_FILE),
            (t("settings.storage.db"), Path(self._database.path)),
            (t("settings.storage.disclaimer"), self._config.CONFIG_DIR / "disclaimer.json"),
        ]

    def collect_app_settings(self, settings: dict[str, object]) -> None:
        """Schreibt alle Werte direkt in die DB.

        Das settings-Dict bekommt nur die Sprache (steht schon drin). Die
        App liest die Sprache nach dem Save aus dem Dict und persistiert sie
        in GlobalConfig.
        """
        # Fahrzeug speichern
        vehicle = Vehicle(
            name=self._get_input("v-name"),
            plate=self._get_input("v-plate"),
            contract_number=self._get_input("v-contract"),
            lease_km_per_month=parse_km(self._get_input("v-lease-km"), 1500),
            start_km=parse_km(self._get_input("v-start-km"), 0),
            end_km=parse_km(self._get_input("v-end-km"), 0),
            start_date=self._get_input("v-start-date"),
            end_date=self._get_input("v-end-date"),
            lease_months=self._parse_int("v-lease-months", 12),
            tank_capacity_l=_parse_float(self._get_input("v-tank-capacity")),
            consumption_l_100km=_parse_float(self._get_input("v-consumption")),
        )
        self._database.save_vehicle(vehicle)

        # Bundesland
        state_select = self.query_one("#select-federal-state", Select)
        if state_select.value != Select.BLANK:
            self._database.set_setting("federal_state", str(state_select.value))

        # Journal-Modus
        journal_select = self.query_one("#select-journal-mode", Select)
        if journal_select.value != Select.BLANK:
            self._database.set_setting("db_journal_mode", str(journal_select.value))

        # Anzeige-Toggles
        self._database.set_setting("show_id_column", "1" if self._get_checkbox("check-show-id-column") else "0")
        self._database.set_setting("show_code_column", "1" if self._get_checkbox("check-show-code-column") else "0")
        self._database.set_setting("show_fuel_column", "1" if self._get_checkbox("check-show-fuel-column") else "0")

        # Plausi-Checks
        self._database.set_setting("check_ghost_trips", "1" if self._get_checkbox("check-ghost-trips") else "0")
        self._database.set_setting(
            "fuel_winter_tolerance", "1" if self._get_checkbox("check-fuel-winter-tolerance") else "0"
        )

        # Excel-Export
        self._database.set_setting(
            "export_include_prev_december",
            "1" if self._get_checkbox("check-export-include-prev-december") else "0",
        )

        # Wohnadresse
        self._database.set_setting("home_address", self._get_input("home-address"))

        # Adressen
        self._save_address_list("customer", "cust")
        self._save_address_list("gas_station", "gas")
        self._save_address_list("shopping", "shop")
        self._save_address_list("restaurant", "rest")
        self._save_address_list("other", "other")
        self._save_steuerberaterin()

        # Kategorien
        self._save_categories()

        # Sprache aus dem Dict in den GlobalConfig persistieren — die App liest
        # spaeter den GlobalConfig (oder das Result-Dict) und entscheidet ob
        # ein Restart-Hinweis noetig ist.
        lang = str(settings.get("language", self._config.language))
        if lang in ("de", "en") and lang != self._config.language:
            self._config.language = lang
            self._config.save()

        # Tastenbelegung ebenfalls in GlobalConfig - sie gilt fuer alle
        # Fahrtenbuecher und wird beim naechsten Start gebunden.
        style_value = self.query_one("#set-keymap-style", Select).value
        keymap_style = style_value if isinstance(style_value, str) else ""
        keymap_vim = bool(self.query_one("#set-keymap-vim", Checkbox).value)
        if (keymap_style, keymap_vim) != (self._config.keymap_style, self._config.keymap_vim):
            self._config.keymap_style = keymap_style
            self._config.keymap_vim = keymap_vim
            self._config.save()

    # ------------------------------------------------------------------
    # Tab content builders
    # ------------------------------------------------------------------
    def _vehicle_fields(self, v: Vehicle) -> ComposeResult:
        """Felder fuer das Fahrzeug-Tab."""
        with Horizontal(classes="settings-row"):
            yield Label(t("settings.label.vehicle_name"))
            yield Input(value=v.name, id="v-name")
        with Horizontal(classes="settings-row"):
            yield Label(t("settings.label.plate"))
            yield Input(value=v.plate, id="v-plate")
        with Horizontal(classes="settings-row"):
            yield Label(t("settings.label.contract_no"))
            yield Input(value=v.contract_number, id="v-contract")
        with Horizontal(classes="settings-row"):
            yield Label(t("settings.label.km_per_month"))
            yield Input(value=format_km(v.lease_km_per_month), id="v-lease-km")
        with Horizontal(classes="settings-row"):
            yield Label(t("settings.label.start_km"))
            yield Input(value=format_km(v.start_km) if v.start_km > 0 else "", id="v-start-km")
        with Horizontal(classes="settings-row"):
            yield Label(t("settings.label.end_km"))
            yield Input(value=format_km(v.end_km) if v.end_km > 0 else "", id="v-end-km")
        with Horizontal(classes="settings-row"):
            yield Label(t("settings.label.start_date"))
            yield Input(value=v.start_date, placeholder=t("settings.placeholder.date_de"), id="v-start-date")
        with Horizontal(classes="settings-row"):
            yield Label(t("settings.label.end_date"))
            yield Input(value=v.end_date, placeholder=t("settings.placeholder.date_de"), id="v-end-date")
        with Horizontal(classes="settings-row"):
            yield Label(t("settings.label.lease_months"))
            yield Input(value=str(v.lease_months), id="v-lease-months")
        with Horizontal(classes="settings-row"):
            yield Label(t("settings.label.tank_capacity"))
            yield Input(
                value=_format_float(v.tank_capacity_l),
                placeholder=t("settings.placeholder.tank"),
                id="v-tank-capacity",
            )
        with Horizontal(classes="settings-row"):
            yield Label(t("settings.label.consumption"))
            yield Input(
                value=_format_float(v.consumption_l_100km),
                placeholder=t("settings.placeholder.consumption"),
                id="v-consumption",
            )
        with Horizontal(classes="settings-row"):
            yield Label(t("settings.label.federal_state"))
            yield Select(
                options=_state_options(),
                value=self._federal_state,
                id="select-federal-state",
            )

    def _home_fields(self, home_address: str) -> ComposeResult:
        with Horizontal(classes="settings-row"):
            yield Label(t("settings.label.home_address"))
            yield Input(
                value=home_address,
                placeholder=t("settings.placeholder.address"),
                id="home-address",
            )

    def _address_list_fields(self, entries: list[AddressEntry], prefix: str) -> ComposeResult:
        for i, entry in enumerate(entries):
            with Vertical(classes="addr-block"):
                with Horizontal(classes="settings-row"):
                    yield Label(t("settings.label.address_name"))
                    yield Input(value=entry.name, id=f"{prefix}-name-{i}")
                with Horizontal(classes="settings-row"):
                    yield Label(t("settings.label.address_addr"))
                    yield Input(value=entry.address, id=f"{prefix}-addr-{i}")
                with Horizontal(classes="settings-row"):
                    yield Label(t("settings.label.address_km"))
                    yield Input(value=_format_km(entry.km), id=f"{prefix}-km-{i}")

        yield Button(t("settings.btn_add"), variant="success", id=f"btn-add-{prefix}")

    def _steuerberater_fields(self) -> ComposeResult:
        st_list = self._addresses.get("steuerberaterin", [])
        st = st_list[0] if st_list else AddressEntry()

        with Vertical(classes="addr-block"):
            with Horizontal(classes="settings-row"):
                yield Label(t("settings.label.address_name"))
                yield Input(value=st.name, id="st-name")
            with Horizontal(classes="settings-row"):
                yield Label(t("settings.label.address_addr"))
                yield Input(value=st.address, id="st-addr")
            with Horizontal(classes="settings-row"):
                yield Label(t("settings.label.address_km"))
                yield Input(value=_format_km(st.km), id="st-km")

    def _category_fields(self) -> ComposeResult:
        for i, cat in enumerate(self._categories):
            int(cat.get("id", 0))
            name = str(cat.get("name", ""))
            display_name = str(cat.get("display_name", ""))
            counts_biz = bool(cat.get("counts_as_business", 1))
            color = str(cat.get("color", "green"))

            with Vertical(classes="cat-block"):
                with Horizontal(classes="settings-row"):
                    yield Label(t("settings.label.category_key"))
                    yield Input(value=name, id=f"cat-name-{i}")
                with Horizontal(classes="settings-row"):
                    yield Label(t("settings.label.category_display"))
                    yield Input(value=display_name, id=f"cat-display-{i}")
                with Horizontal(classes="settings-row"):
                    yield Label(t("settings.label.category_color"))
                    yield Select(options=_color_options(), value=color, id=f"cat-color-{i}")
                with Horizontal(classes="settings-row"):
                    yield Label("")
                    yield Checkbox(t("settings.cat.business"), value=counts_biz, id=f"cat-biz-{i}")
                with Horizontal(classes="settings-row"):
                    yield Label("")
                    yield Button(t("settings.btn_delete"), variant="error", id=f"btn-del-cat-{i}")

        yield Button(t("settings.btn_add_category"), variant="success", id="btn-add-cat")

    def _database_fields(self) -> ComposeResult:
        allowed = {opt[1] for opt in _journal_mode_options()}
        current = self._journal_mode if self._journal_mode in allowed else "DELETE"

        with Horizontal(classes="settings-row"):
            yield Label(t("settings.label.journal_mode"))
            yield Select(options=_journal_mode_options(), value=current, id="select-journal-mode")
        yield Static(t("settings.journal_hint"), classes="settings-hint")
        with Horizontal(classes="settings-row"):
            yield Label(t("settings.label.display"))
            yield Checkbox(t("settings.show_id_column"), value=self._show_id_column, id="check-show-id-column")
        with Horizontal(classes="settings-row"):
            yield Label("")
            yield Checkbox(t("settings.show_code_column"), value=self._show_code_column, id="check-show-code-column")
        with Horizontal(classes="settings-row"):
            yield Label("")
            yield Checkbox(t("settings.show_fuel_column"), value=self._show_fuel_column, id="check-show-fuel-column")
        with Horizontal(classes="settings-row"):
            yield Label(t("settings.label.plausi_checks"))
            yield Checkbox(t("settings.check_ghost_trips"), value=self._check_ghost_trips, id="check-ghost-trips")
        with Horizontal(classes="settings-row"):
            yield Label("")
            yield Checkbox(
                t("settings.fuel_winter_tolerance"),
                value=self._fuel_winter_tolerance,
                id="check-fuel-winter-tolerance",
            )
        with Horizontal(classes="settings-row"):
            yield Label(t("settings.label.excel_export"))
            yield Checkbox(
                t("settings.export_include_prev_december"),
                value=self._export_include_prev_december,
                id="check-export-include-prev-december",
            )

    # ------------------------------------------------------------------
    # Button handlers — App-eigene Buttons IMMER via @on (NICHT
    # on_button_pressed-Override, sonst MRO-Crash mit der Basis).
    # ------------------------------------------------------------------
    @on(Button.Pressed, "#btn-add-cust")
    def _on_add_cust(self) -> None:
        self._add_address_entry("cust")

    @on(Button.Pressed, "#btn-add-gas")
    def _on_add_gas(self) -> None:
        self._add_address_entry("gas")

    @on(Button.Pressed, "#btn-add-shop")
    def _on_add_shop(self) -> None:
        self._add_address_entry("shop")

    @on(Button.Pressed, "#btn-add-rest")
    def _on_add_rest(self) -> None:
        self._add_address_entry("rest")

    @on(Button.Pressed, "#btn-add-other")
    def _on_add_other(self) -> None:
        self._add_address_entry("other")

    @on(Button.Pressed, "#btn-add-cat")
    def _on_add_cat(self) -> None:
        self._add_category_entry()

    @on(Button.Pressed)
    def _on_dynamic_button(self, event: Button.Pressed) -> None:
        """Faengt dynamische del-cat-N-Buttons ab."""
        btn_id = event.button.id or ""
        if btn_id.startswith("btn-del-cat-"):
            self._delete_category_entry(btn_id)

    def _add_address_entry(self, prefix: str) -> None:
        """Fuegt einen leeren Adresseintrag hinzu und mountet neue Widgets sofort."""
        category_map = {
            "cust": "customer",
            "gas": "gas_station",
            "shop": "shopping",
            "rest": "restaurant",
            "other": "other",
        }
        cat = category_map.get(prefix)
        if not cat:
            return

        if cat not in self._addresses:
            self._addresses[cat] = []
        self._addresses[cat].append(AddressEntry(category=cat))
        i = len(self._addresses[cat]) - 1

        btn = self.query_one(f"#btn-add-{prefix}", Button)
        new_block = Vertical(
            Horizontal(
                Label(t("settings.label.address_name")),
                Input(id=f"{prefix}-name-{i}"),
                classes="settings-row",
            ),
            Horizontal(
                Label(t("settings.label.address_addr")),
                Input(id=f"{prefix}-addr-{i}"),
                classes="settings-row",
            ),
            Horizontal(
                Label(t("settings.label.address_km")),
                Input(id=f"{prefix}-km-{i}"),
                classes="settings-row",
            ),
            classes="addr-block",
        )
        btn.parent.mount(new_block, before=btn)
        new_block.scroll_visible()
        self.set_focus(self.query_one(f"#{prefix}-name-{i}", Input))

    def _add_category_entry(self) -> None:
        """Mountet einen neuen Kategorie-Block direkt vor dem Add-Button."""
        new_cat: dict[str, object] = {
            "id": 0,
            "name": "",
            "display_name": "",
            "counts_as_business": 1,
            "color": "green",
        }
        self._categories.append(new_cat)
        i = len(self._categories) - 1

        btn = self.query_one("#btn-add-cat", Button)
        new_block = Vertical(
            Horizontal(
                Label(t("settings.label.category_key")),
                Input(id=f"cat-name-{i}"),
                classes="settings-row",
            ),
            Horizontal(
                Label(t("settings.label.category_display")),
                Input(id=f"cat-display-{i}"),
                classes="settings-row",
            ),
            Horizontal(
                Label(t("settings.label.category_color")),
                Select(options=_color_options(), value="green", id=f"cat-color-{i}"),
                classes="settings-row",
            ),
            Horizontal(
                Label(""),
                Checkbox(t("settings.cat.business"), value=True, id=f"cat-biz-{i}"),
                classes="settings-row",
            ),
            Horizontal(
                Label(""),
                Button(t("settings.btn_delete"), variant="error", id=f"btn-del-cat-{i}"),
                classes="settings-row",
            ),
            classes="cat-block",
        )
        btn.parent.mount(new_block, before=btn)
        new_block.scroll_visible()
        self.set_focus(self.query_one(f"#cat-name-{i}", Input))

    def _delete_category_entry(self, btn_id: str) -> None:
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
        self.notify(t("settings.category_deleted_hint", name=cat_name))

    # ------------------------------------------------------------------
    # Save helpers
    # ------------------------------------------------------------------
    def _save_address_list(self, category: str, prefix: str) -> None:
        entries = self._addresses.get(category, [])
        for i, entry in enumerate(entries):
            name = self._get_input(f"{prefix}-name-{i}")
            address = self._get_input(f"{prefix}-addr-{i}")
            km = self._parse_float_field(f"{prefix}-km-{i}")

            if entry.id > 0:
                self._database.update_address(entry.id, name, address, km)
            else:
                if name or address:
                    self._database.add_address(category, name, address, km)

    def _save_steuerberaterin(self) -> None:
        st_list = self._addresses.get("steuerberaterin", [])
        name = self._get_input("st-name")
        address = self._get_input("st-addr")
        km = self._parse_float_field("st-km")

        if st_list and st_list[0].id > 0:
            self._database.update_address(st_list[0].id, name, address, km)
        else:
            if name or address:
                self._database.add_address("steuerberaterin", name, address, km)

    def _save_categories(self) -> None:
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
                self._database.update_category(cat_id, name, display_name, counts_biz, color)
            else:
                self._database.add_category(name, display_name, counts_biz, color)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _query_select(self, select_id: str) -> str:
        try:
            select = self.query_one(f"#{select_id}", Select)
            if select.value != Select.BLANK:
                return str(select.value)
        except Exception:
            pass
        return ""

    def _get_checkbox(self, checkbox_id: str) -> bool:
        try:
            return bool(self.query_one(f"#{checkbox_id}", Checkbox).value)
        except Exception:
            return False

    def _get_input(self, input_id: str) -> str:
        try:
            return str(self.query_one(f"#{input_id}", Input).value.strip())
        except Exception:
            return ""

    def _parse_int(self, input_id: str, default: int = 0) -> int:
        try:
            return int(self._get_input(input_id) or str(default))
        except ValueError:
            return default

    def _parse_float_field(self, input_id: str) -> float:
        raw = (self._get_input(input_id) or "0").strip().replace(",", ".")
        try:
            return float(raw)
        except ValueError:
            return 0.0
