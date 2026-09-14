"""DataTable mit zuschaltbarer Vim-Navigation."""

from __future__ import annotations

from typing import Any

from textual import events
from textual.widgets import DataTable
from textual_widgets import vim_navigation_bindings


class NavigableDataTable(DataTable[Any]):
    """DataTable, die j/k, h/l, g/G und Strg+D/Strg+U versteht, wenn eingeschaltet.

    Die Bindung haengt am Widget und nicht an der App, weil sie nur gelten
    soll, solange die Tabelle den Fokus hat. Deshalb zieht das Log im
    F-Tasten-Stil von `l` auf F4 - eine Widget-Bindung schlaegt die
    gleichnamige an der App, und die App-Aktion feuerte sonst gar nicht.
    """

    def _on_mount(self, event: events.Mount) -> None:
        """Haengt die Vim-Navigation ein, wenn sie eingeschaltet ist.

        Bewusst `_on_mount` und nicht `on_mount`: In Textual laeuft jeder
        `_on_*`-Haken der MRO, ein oeffentliches `on_mount` wuerde dagegen das
        einer Ableitung verdecken.

        Args:
            event: Das Mount-Ereignis.
        """
        if not getattr(self.app, "vim_navigation", False):
            return
        for key, action in vim_navigation_bindings():
            self._bindings.bind(key, action, show=False)
