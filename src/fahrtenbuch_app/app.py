"""Fahrtenbuch TUI — Hauptanwendung."""

from datetime import date, datetime
from pathlib import Path

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import ContentSwitcher, Footer, Header, RichLog, Tab, Tabs

from fahrtenbuch_app import __version__, __year__
from fahrtenbuch_app.models.fahrtenbuch import Fahrtenbuch
from fahrtenbuch_app.models.settings import GlobalConfig
from fahrtenbuch_app.models.trip import Trip, set_business_categories
from fahrtenbuch_app.models.vehicle import Vehicle
from fahrtenbuch_app.widgets.blacklist_view import BlacklistView
from fahrtenbuch_app.widgets.calendar_view import CalendarView
from fahrtenbuch_app.widgets.config_panel import ConfigPanel
from fahrtenbuch_app.widgets.summary_panel import SummaryPanel
from fahrtenbuch_app.services.holiday_service import HolidayService
from fahrtenbuch_app.widgets.trip_table import TripTable
from fahrtenbuch_app.widgets.year_view import YearView


class FahrtenbuchApp(App):
    """Fahrtenbuch TUI fuer Finanzamt-konforme Fahrtenbuecher."""

    CSS_PATH = "app.tcss"
    TITLE = f"Fahrtenbuch v{__version__} ({__year__})"

    BINDINGS = [
        Binding("q", "quit", "Beenden"),
        Binding("n", "new_trip", "Neue Fahrt"),
        Binding("d", "delete_trip", "Loeschen"),
        Binding("e", "export_excel", "Excel"),
        Binding("s", "show_settings", "Settings"),
        Binding("j", "show_year", "Jahr"),
        Binding("o", "open_fahrtenbuch", "Oeffnen"),
        Binding("v", "toggle_view", "View"),
        Binding("b", "toggle_blacklist", "Blacklist"),
        Binding("comma", "prev_month", "Monat", key_display="<"),
        Binding("full_stop", "next_month", "Monat", key_display=">"),
        Binding("p", "check_plausibility", "Plausibilitaet"),
        Binding("l", "toggle_log", "Log"),
        Binding("i", "show_info", "Info"),
    ]

    def __init__(self, year_override: int | None = None, **kwargs: object) -> None:
        super().__init__(**kwargs)
        self._config = GlobalConfig.load()

        try:
            from textual_themes import register_all
            register_all(self)
        except ImportError:
            pass

        self.theme = self._config.theme

        self._year = year_override or date.today().year
        self._month = date.today().month
        self._year_override = year_override
        self._current_view = "list"  # "list" | "calendar" | "year" | "blacklist"
        self._fahrtenbuch: Fahrtenbuch | None = None
        self._selected_trip_index: int = -1
        self._holiday_service = HolidayService("BB")  # Brandenburg

    def compose(self) -> ComposeResult:
        """Erstellt das UI-Layout."""
        yield Header()
        yield ConfigPanel(
            vehicle=None,
            year=self._year,
            month=self._month,
            fb_path="",
            id="config-panel",
        )
        yield Tabs(
            Tab("Liste", id="tab-list"),
            Tab("Kalender", id="tab-calendar"),
            Tab("Jahr", id="tab-year"),
            Tab("Blacklist", id="tab-blacklist"),
            id="view-tabs",
        )
        with ContentSwitcher(initial="trip-table", id="view-switcher"):
            yield TripTable(id="trip-table")
            yield CalendarView(id="calendar-view")
            yield YearView(id="year-view")
            yield BlacklistView(id="blacklist-view")
        yield SummaryPanel(id="summary-panel")
        yield RichLog(id="log-panel", highlight=True, markup=True)
        yield Footer()

    def on_mount(self) -> None:
        """Wird nach dem Starten aufgerufen."""
        if not self._config.log_visible:
            self.query_one("#log-panel").add_class("hidden")

        self._write_log(f"Fahrtenbuch v{__version__} gestartet")

        # Versuche zuletzt geoeffnetes Fahrtenbuch zu oeffnen
        last_path = self._config.last_opened_path
        if last_path and Path(last_path).exists():
            self._open_fahrtenbuch(last_path)
        else:
            self._show_start_screen()

    def _show_start_screen(self) -> None:
        """Zeigt den Start-Screen zum Oeffnen/Erstellen eines Fahrtenbuchs."""
        from fahrtenbuch_app.screens.start_screen import StartScreen

        self.push_screen(
            StartScreen(self._config),
            callback=self._on_start_screen_closed,
        )

    def _on_start_screen_closed(self, path: str | None) -> None:
        """Callback nach dem StartScreen."""
        if path is None:
            if self._fahrtenbuch is None:
                self._write_log(
                    "[yellow]Kein Fahrtenbuch geoeffnet. "
                    "Druecke [O] zum Oeffnen.[/yellow]"
                )
            return
        self._open_fahrtenbuch(path)

    def _open_fahrtenbuch(self, path_str: str) -> None:
        """Oeffnet oder erstellt ein Fahrtenbuch am angegebenen Pfad."""
        path = Path(path_str)

        # Altes Fahrtenbuch schliessen
        if self._fahrtenbuch is not None:
            self._fahrtenbuch.close()
            self._fahrtenbuch = None

        try:
            db_file = path / "fahrtenbuch.db"
            if db_file.exists():
                self._fahrtenbuch = Fahrtenbuch.open(path)
                self._write_log(f"Fahrtenbuch geoeffnet: {path}")
            else:
                # Neues Fahrtenbuch anlegen — Fahrzeug wird spaeter ueber Settings konfiguriert
                self._fahrtenbuch = Fahrtenbuch.create(path, Vehicle())
                self._write_log(f"[green]Neues Fahrtenbuch erstellt: {path}[/green]")
                self._write_log(
                    "[yellow]Druecke [S] um das Fahrzeug zu konfigurieren.[/yellow]"
                )
        except Exception as exc:
            self._write_log(f"[red]Fehler beim Oeffnen: {exc}[/red]")
            self.notify(f"Fehler: {exc}", severity="error")
            return

        # GlobalConfig aktualisieren
        self._config.last_opened_path = path_str
        self._config.add_recent(path_str)
        self._config.save()

        # Monat bestimmen: gespeichert > erster Trip > heute
        db = self._fahrtenbuch.database
        if not self._year_override:
            saved_year = db.get_setting("last_viewed_year", "")
            saved_month = db.get_setting("last_viewed_month", "")
            if saved_year and saved_month:
                self._year = int(saved_year)
                self._month = int(saved_month)
            else:
                first = db.get_first_trip_date()
                if first:
                    self._year, self._month = first

        # Business-Kategorien aus DB laden
        set_business_categories(db.get_business_category_names())

        # HolidayService mit gespeichertem Bundesland
        federal_state = db.get_setting("federal_state", "BB")
        self._holiday_service = HolidayService(federal_state)

        # UI aktualisieren
        vehicle = self._fahrtenbuch.vehicle
        config_panel = self.query_one("#config-panel", ConfigPanel)
        config_panel.update_vehicle(vehicle, path_str)
        config_panel.update_month(self._year, self._month)

        if vehicle and vehicle.name:
            self._write_log(f"Fahrzeug: {vehicle.name} ({vehicle.plate})")

        self._refresh_data()

    def _refresh_data(self) -> None:
        """Laedt und zeigt die Daten fuer den aktuellen Monat."""
        if self._fahrtenbuch is None or not self._fahrtenbuch.is_open:
            return

        db = self._fahrtenbuch.database
        month_data = db.get_month_data(self._year, self._month)
        lease_km = 1500
        vehicle = self._fahrtenbuch.vehicle
        if vehicle:
            lease_km = vehicle.lease_km_per_month

        holidays_map = self._holiday_service.get_holidays_in_month(
            self._year, self._month
        )

        category_colors = db.get_category_colors()

        # Blacklist laden (fuer Kalenderansicht und Blacklist-Tab)
        blacklist_entries = db.get_blacklist()
        blacklist_map: dict[date, str] = {}
        for entry in blacklist_entries:
            try:
                parts = str(entry.get("date", "")).split("-")
                d = date(int(parts[0]), int(parts[1]), int(parts[2]))
                blacklist_map[d] = str(entry.get("reason", ""))
            except (ValueError, IndexError):
                pass

        table = self.query_one("#trip-table", TripTable)
        table.load_data(month_data, holidays_map, category_colors, blacklist_map, blacklist_entries)

        calendar_view = self.query_one("#calendar-view", CalendarView)
        calendar_view.load_data(month_data, holidays_map, category_colors, blacklist_map)

        bl_view = self.query_one("#blacklist-view", BlacklistView)
        bl_view.load_data(blacklist_entries)

        summary = self.query_one("#summary-panel", SummaryPanel)
        summary.update_data(month_data, lease_km)

        # Warnungen fuer geschaeftliche Fahrten an Feiertagen/Wochenenden
        warnings = 0
        for trip in month_data.trips:
            if not trip.is_business_km:
                continue
            try:
                parts = trip.date.split("-")
                d = date(int(parts[0]), int(parts[1]), int(parts[2]))
            except (ValueError, IndexError):
                continue
            holiday_name = holidays_map.get(d, "")
            if holiday_name:
                self._write_log(
                    f"[bold red]WARNUNG: Geschaeftliche Fahrt am Feiertag "
                    f"{d.strftime('%d.%m.%Y')} ({holiday_name}): "
                    f"{trip.purpose}[/bold red]"
                )
                warnings += 1
            elif d.weekday() >= 5:
                self._write_log(
                    f"[bold red]WARNUNG: Geschaeftliche Fahrt am Wochenende "
                    f"{d.strftime('%d.%m.%Y')}: {trip.purpose}[/bold red]"
                )
                warnings += 1

        self._write_log(
            f"Daten geladen: {len(month_data.trips)} Fahrten, "
            f"{month_data.km_total} km gesamt"
            + (f", [bold red]{warnings} Warnungen[/bold red]" if warnings else "")
        )

    def _write_log(self, message: str) -> None:
        """Schreibt eine Nachricht ins Log mit Zeitstempel."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        log = self.query_one("#log-panel", RichLog)
        log.write(f"[dim]{timestamp}[/dim] {message}")

    def action_quit(self) -> None:
        """Speichert den aktuellen Monat und beendet die App."""
        if self._fahrtenbuch is not None and self._fahrtenbuch.is_open:
            db = self._fahrtenbuch.database
            db.set_setting("last_viewed_year", str(self._year))
            db.set_setting("last_viewed_month", str(self._month))
        self.exit()

    def watch_theme(self, theme_name: str) -> None:
        """Speichert das Theme bei Aenderung persistent."""
        self._config.theme = theme_name
        self._config.save()

    def on_config_panel_month_changed(
        self, event: ConfigPanel.MonthChanged
    ) -> None:
        """Reagiert auf Monatswechsel."""
        self._year = event.year
        self._month = event.month
        self._refresh_data()

    def on_trip_table_trip_selected(
        self, event: TripTable.TripSelected
    ) -> None:
        """Reagiert auf Auswahl einer Fahrt — oeffnet den Editor."""
        if event.trip is None or self._fahrtenbuch is None:
            return
        self._selected_trip_index = event.index

        from fahrtenbuch_app.screens.trip_screen import TripScreen

        self.push_screen(
            TripScreen(
                database=self._fahrtenbuch.database,
                trip=event.trip,
            ),
            callback=self._on_trip_edited,
        )

    def _on_trip_edited(self, trip: "Trip | None") -> None:
        """Callback nach dem Bearbeiten einer Fahrt."""
        if trip is None or self._fahrtenbuch is None:
            return
        # Trip hat eine ID — direkt in der DB aktualisieren
        if trip.id > 0:
            self._fahrtenbuch.database.update_trip(trip.id, trip)
        self._write_log(
            f"[green]Fahrt aktualisiert: {trip.date} — {trip.purpose}[/green]"
        )
        self._refresh_data()

    def on_blacklist_view_entry_selected(
        self, event: "BlacklistView.EntrySelected"
    ) -> None:
        """Oeffnet Blacklist-Detail beim Auswaehlen eines Eintrags im Blacklist-Tab."""
        self._show_blacklist_detail(event.entry_id, event.date_str, event.reason)

    def on_trip_table_blacklist_entry_activated(
        self, event: "TripTable.BlacklistEntryActivated"
    ) -> None:
        """Oeffnet Blacklist-Detail beim Auswaehlen einer Blacklist-Zeile in der Liste."""
        self._show_blacklist_detail(event.entry_id, event.date_str, event.reason)

    def _show_blacklist_detail(
        self, entry_id: int, date_str: str, reason: str
    ) -> None:
        """Oeffnet den Blacklist-Detail-Screen."""
        from fahrtenbuch_app.screens.blacklist_detail_screen import BlacklistDetailScreen

        self.push_screen(
            BlacklistDetailScreen(entry_id, date_str, reason),
            callback=self._on_blacklist_detail_closed,
        )

    def _on_blacklist_detail_closed(self, entry_id_to_delete: int | None) -> None:
        """Callback nach dem BlacklistDetailScreen — loescht Eintrag falls gewuenscht."""
        if entry_id_to_delete is None or self._fahrtenbuch is None:
            return
        db = self._fahrtenbuch.database
        db.delete_blacklist_entry(entry_id_to_delete)
        self._write_log(f"[red]Blacklist-Eintrag geloescht (ID {entry_id_to_delete})[/red]")
        self._refresh_data()

    def action_delete_trip(self) -> None:
        """Loescht die ausgewaehlte Fahrt."""
        if self._fahrtenbuch is None or self._selected_trip_index < 0:
            self.notify("Keine Fahrt ausgewaehlt", severity="warning")
            return

        db = self._fahrtenbuch.database
        month_data = db.get_month_data(self._year, self._month)
        if self._selected_trip_index >= len(month_data.trips):
            return

        trip = month_data.trips[self._selected_trip_index]
        if trip.id > 0:
            db.delete_trip(trip.id)
        self._write_log(
            f"[red]Fahrt geloescht: {trip.date} — {trip.purpose}[/red]"
        )
        self._selected_trip_index = -1
        self._refresh_data()

    def action_prev_month(self) -> None:
        """Wechselt zum vorherigen Monat."""
        config = self.query_one("#config-panel", ConfigPanel)
        config.prev_month()

    def action_next_month(self) -> None:
        """Wechselt zum naechsten Monat."""
        config = self.query_one("#config-panel", ConfigPanel)
        config.next_month()

    def on_tabs_tab_activated(self, event: Tabs.TabActivated) -> None:
        """Reagiert auf Tab-Wechsel."""
        tab_map = {
            "tab-list": "trip-table",
            "tab-calendar": "calendar-view",
            "tab-year": "year-view",
            "tab-blacklist": "blacklist-view",
        }
        view_id = tab_map.get(event.tab.id or "", "trip-table")
        switcher = self.query_one("#view-switcher", ContentSwitcher)
        switcher.current = view_id
        self._current_view = event.tab.id or "tab-list"

        if view_id == "year-view":
            self._refresh_year_view()

    def action_toggle_view(self) -> None:
        """Wechselt zum naechsten Tab."""
        tabs = self.query_one("#view-tabs", Tabs)
        tabs.action_next_tab()

    def action_toggle_blacklist(self) -> None:
        """Schaltet Blacklist-Markierung in Liste und Kalender ein/aus."""
        if self._fahrtenbuch is None:
            self.notify("Kein Fahrtenbuch geoeffnet", severity="warning")
            return

        trip_table = self.query_one("#trip-table", TripTable)
        calendar_view = self.query_one("#calendar-view", CalendarView)
        is_on = trip_table.toggle_blacklist()
        calendar_view.toggle_blacklist()

        status = "[bold red]EIN[/bold red]" if is_on else "[dim]AUS[/dim]"
        self._write_log(f"Blacklist-Anzeige: {status}")
        self.notify(
            f"Blacklist {'aktiv' if is_on else 'deaktiviert'}",
            severity="information" if is_on else "warning",
        )

    def _refresh_year_view(self) -> None:
        """Laedt die Jahresdaten in die YearView."""
        if self._fahrtenbuch is None or not self._fahrtenbuch.is_open:
            return
        db = self._fahrtenbuch.database
        month_data = db.get_all_month_data(self._year)
        lease_km = 1500
        vehicle = self._fahrtenbuch.vehicle
        if vehicle:
            lease_km = vehicle.lease_km_per_month
        year_view = self.query_one("#year-view", YearView)
        year_view.load_data(self._year, month_data, lease_km)

    def action_toggle_log(self) -> None:
        """Blendet das Log-Panel ein/aus."""
        log = self.query_one("#log-panel")
        log.toggle_class("hidden")
        self._config.log_visible = not log.has_class("hidden")
        self._config.save()

    def action_new_trip(self) -> None:
        """Oeffnet den Dialog fuer eine neue Fahrt."""
        if self._fahrtenbuch is None:
            self.notify("Kein Fahrtenbuch geoeffnet", severity="warning")
            return

        from fahrtenbuch_app.screens.trip_screen import TripScreen

        db = self._fahrtenbuch.database
        last_km = db.get_last_km_end(self._year, self._month)

        default_date = f"{self._year}-{self._month:02d}-"

        self.push_screen(
            TripScreen(
                database=db,
                last_km_end=last_km,
                default_date=default_date,
            ),
            callback=self._on_trip_created,
        )

    def _on_trip_created(self, trip: "Trip | None") -> None:
        """Callback nach dem TripScreen."""
        if trip is None or self._fahrtenbuch is None:
            return
        self._fahrtenbuch.database.add_trip(trip)
        self._write_log(
            f"[green]Fahrt angelegt: {trip.date} — {trip.purpose}[/green]"
        )
        self._refresh_data()

    def action_export_excel(self) -> None:
        """Exportiert das Fahrtenbuch als Excel-Datei."""
        self._write_log("[dim]Excel-Export — noch nicht implementiert[/dim]")
        self.notify("Excel-Export — noch nicht implementiert", severity="warning")

    def action_show_settings(self) -> None:
        """Oeffnet die Einstellungen."""
        if self._fahrtenbuch is None:
            self.notify("Kein Fahrtenbuch geoeffnet", severity="warning")
            return

        from fahrtenbuch_app.screens.settings_screen import SettingsScreen

        self.push_screen(
            SettingsScreen(self._fahrtenbuch.database),
            callback=self._on_settings_closed,
        )

    def _on_settings_closed(self, changed: bool | None) -> None:
        """Callback nach dem SettingsScreen."""
        if not changed or self._fahrtenbuch is None:
            return

        # Fahrzeug-Daten und Bundesland aus DB neu laden
        db = self._fahrtenbuch.database
        self._fahrtenbuch._vehicle = db.get_vehicle()
        vehicle = self._fahrtenbuch.vehicle

        # Business-Kategorien aus DB neu laden
        set_business_categories(db.get_business_category_names())

        federal_state = db.get_setting("federal_state", "BB")
        self._holiday_service = HolidayService(federal_state)

        self._write_log("[green]Einstellungen gespeichert[/green]")

        if vehicle:
            self._write_log(f"Fahrzeug: {vehicle.name} ({vehicle.plate})")

        config_panel = self.query_one("#config-panel", ConfigPanel)
        config_panel.update_vehicle(vehicle, str(self._fahrtenbuch.path))
        self._refresh_data()

    def action_open_fahrtenbuch(self) -> None:
        """Oeffnet den Start-Screen zum Wechseln des Fahrtenbuchs."""
        self._show_start_screen()

    def action_show_year(self) -> None:
        """Wechselt direkt zur Jahresuebersicht."""
        tabs = self.query_one("#view-tabs", Tabs)
        tabs.active = "tab-year"

    def action_check_plausibility(self) -> None:
        """Fuehrt die Plausibilitaetspruefung durch."""
        self._write_log("[dim]Plausibilitaet — noch nicht implementiert[/dim]")
        self.notify("Plausibilitaet — noch nicht implementiert", severity="warning")

    def action_show_info(self) -> None:
        """Zeigt den Info-Dialog."""
        from fahrtenbuch_app.screens.info_screen import InfoScreen

        self.push_screen(InfoScreen())

    def check_action(self, action: str, parameters: tuple) -> bool | None:  # type: ignore[override]
        """Blendet Aktionen aus wenn ModalScreen offen oder nicht verfuegbar."""
        # ModalScreen offen → alle App-Bindings deaktivieren
        if len(self.screen_stack) > 1:
            return None
        if action == "export_excel" and self._fahrtenbuch is None:
            return None
        return True
