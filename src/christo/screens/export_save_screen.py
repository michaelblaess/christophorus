"""Der Speichern-Dialog des Exports.

`textual_fspicker.FileSave` bringt Auswahlfeld und Dateiliste schon mit,
laesst dabei aber zwei Dinge offen, die genau hier gebraucht werden:

- Beim Umschalten des Filters bleibt die Endung im Namensfeld stehen. Wer von
  Excel auf JSON wechselt, bekaeme sonst weiter einen Namen auf `.xlsx`.
- Zurueck kommt nur der Pfad, nicht der gewaehlte Filter. Das Format muss also
  aus der Endung ablesbar sein - und ist es nur, wenn die Endung stimmt.

Beides erledigt diese Unterklasse: der Filterwechsel zieht die Endung nach,
und beim Schliessen wird sie notfalls ergaenzt. Der Rueckgabewert bleibt ein
schlichter `Path`, aus dem `format_for_path()` das Format liest.

Uebernommen aus jira-timesheet (screens/export_save_screen.py, v1.22.1).
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from textual import on
from textual.await_complete import AwaitComplete
from textual.widgets import Input, Select
from textual_fspicker import FileSave, Filters

from christo.i18n import t
from christo.models.export_format import (
    EXPORT_FORMATS,
    ExportFormat,
    format_for_path,
    swap_suffix,
)


class ExportSaveScreen(FileSave):
    """Speichern-Dialog mit Formatauswahl fuer den Fahrtenbuch-Export."""

    def __init__(self, location: str | Path, default_file: str, start_format: ExportFormat) -> None:
        """Baut den Dialog samt Filtereintraegen aus der Formatliste.

        Args:
            location: Das Verzeichnis, in dem der Dialog aufgeht. Muss existieren.
            default_file: Der vorgeschlagene Dateiname.
            start_format: Das vorausgewaehlte Format. Seine Endung muss die des
                vorgeschlagenen Namens sein.
        """
        self._formats = EXPORT_FORMATS
        self._selected = start_format
        super().__init__(
            location=location,
            title=t("save_dialog.title"),
            save_button=t("save_dialog.save_button"),
            cancel_button=t("save_dialog.cancel_button"),
            default_file=default_file,
            filters=Filters(
                *[(t(f.filter_key), _suffix_test(f)) for f in self._formats],
                (t("save_dialog.filter_all"), lambda p: True),
            ),
        )

    @property
    def selected_format(self) -> ExportFormat:
        """Das zuletzt im Auswahlfeld gewaehlte Format.

        "Alle Dateien" laesst den Wert stehen - der Eintrag sagt etwas darueber
        aus, was die Liste zeigt, nicht darueber, was geschrieben werden soll.
        """
        return self._selected

    @on(Select.Changed)
    def _follow_filter_with_suffix(self, event: Select.Changed) -> None:
        """Zieht die Endung im Namensfeld dem gewaehlten Filter nach.

        Args:
            event: Die Meldung des Auswahlfeldes.
        """
        if not isinstance(event.value, int) or event.value >= len(self._formats):
            return
        self._selected = self._formats[event.value]
        name_field = self.query_one(Input)
        name_field.value = swap_suffix(name_field.value, self._selected)

    def dismiss(self, result: Path | None = None) -> AwaitComplete:
        """Schliesst den Dialog und sorgt dafuer, dass der Pfad eine Endung traegt.

        Eine bekannte Endung bleibt unangetastet - wer `.md` tippt, obwohl im
        Auswahlfeld Excel steht, bekommt Markdown. Nur wenn die Endung zu keinem
        Format gehoert, tritt die des gewaehlten Formats dahinter.

        Args:
            result: Der gewaehlte Pfad, oder None beim Abbrechen.

        Returns:
            Das Warteobjekt von Textual.
        """
        if result is not None and format_for_path(result) is None:
            result = result.with_name(swap_suffix(result.name, self._selected))
        return super().dismiss(result)


def _suffix_test(export_format: ExportFormat) -> Callable[[Path], bool]:
    """Baut die Testfunktion eines Filtereintrags.

    Args:
        export_format: Das Format, dessen Dateien der Eintrag zeigen soll.

    Returns:
        Die Testfunktion fuer `Filters`.
    """
    return lambda path: path.suffix.lower() == export_format.suffix
