"""CLI Entry Point fuer die Fahrtenbuch TUI."""

import argparse

from textual_widgets import reset_terminal_title, set_terminal_title

from death_proof import __version__
from death_proof.i18n import DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES, load_locale
from death_proof.models.settings import GlobalConfig


def main() -> None:
    """Startet die Fahrtenbuch TUI."""
    # Sprache aus Settings als Default fuer den argparse-Default lesen.
    settings = GlobalConfig.load()
    saved_lang = settings.language if settings.language in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE

    parser = argparse.ArgumentParser(
        prog="death-proof",
        description="Death Proof - Fahrtenbuch als Terminal-Anwendung mit Plausibilitaetspruefung",
    )
    parser.add_argument(
        "--year",
        type=int,
        default=0,
        help="Jahr (z.B. 2024). Default: aus Settings",
    )
    parser.add_argument(
        "--lang",
        default=saved_lang,
        choices=SUPPORTED_LANGUAGES,
        help=f"Sprache (default: {saved_lang})",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    args = parser.parse_args()

    # Sprache laden BEVOR App-Modul importiert wird — sonst sind t()-Aufrufe
    # in Modul-Ebene leer.
    load_locale(args.lang)

    # Wenn per CLI eine andere Sprache als gespeichert gewaehlt wurde,
    # gleich persistent uebernehmen.
    if args.lang != saved_lang:
        settings.language = args.lang
        settings.save()

    from death_proof.app import FahrtenbuchApp

    # Terminal-Tab-Titel setzen - Textual macht das nicht selbst.
    set_terminal_title(f"Death Proof v{__version__}")
    try:
        app = FahrtenbuchApp(year_override=args.year if args.year > 0 else None)
        app.run()
    finally:
        reset_terminal_title()


if __name__ == "__main__":
    main()
