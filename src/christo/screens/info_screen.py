"""Info-Dialog — duenner Wrapper um textual_widgets.AboutScreen."""

from textual_widgets import AboutScreen

from christo import __author__, __version__, __year__
from christo.i18n import current_language, t


class InfoScreen(AboutScreen):  # type: ignore[misc]
    """About-Dialog aus textual_widgets, vorkonfiguriert fuer Christophorus."""

    def __init__(self) -> None:
        super().__init__(
            app_name="christophorus",
            version=__version__,
            author=__author__,
            release=__year__,
            description=t("info.description"),
            license="Apache-2.0",
            lang=current_language(),
            url="https://github.com/michaelblaess/christophorus",
        )
