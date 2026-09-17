"""Startet die Web-Oberflaeche auf einer Arbeitskopie.

    python -m christo.web [QUELLE] [--port 5056] [--neu-kopieren]

Ohne QUELLE wird das zuletzt in der TUI geoeffnete Fahrtenbuch genommen. Die Web-Version
arbeitet immer auf einer Kopie unter `<config_dir>/web/<name>/`, die Datei der TUI bleibt
unberuehrt.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from christo import __version__
from christo.i18n import DEFAULT_LANGUAGE, SUPPORTED_LANGUAGES, load_locale
from christo.models.settings import GlobalConfig
from christo.web.workspace import prepare


def main() -> int:
    """Baut die Arbeitskopie und startet den Server."""
    settings = GlobalConfig.load()
    parser = argparse.ArgumentParser(
        prog="christo-web",
        description="Christophorus - Weboberflaeche auf einer Kopie des Fahrtenbuchs",
    )
    parser.add_argument(
        "quelle",
        nargs="?",
        default=settings.last_opened_path,
        help="Verzeichnis des Fahrtenbuchs (Vorgabe: zuletzt in der TUI geoeffnet)",
    )
    parser.add_argument("--port", type=int, default=5056, help="Port (Vorgabe: 5056)")
    parser.add_argument(
        "--neu-kopieren",
        action="store_true",
        help="Vorhandene Arbeitskopie verwerfen und neu kopieren",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    args = parser.parse_args()

    if not args.quelle:
        parser.error("Kein Fahrtenbuch angegeben und keins zuletzt geoeffnet.")

    load_locale(settings.language if settings.language in SUPPORTED_LANGUAGES else DEFAULT_LANGUAGE)

    try:
        workspace = prepare(Path(args.quelle), refresh=args.neu_kopieren)
    except FileNotFoundError as fehler:
        parser.error(str(fehler))

    import uvicorn

    from christo.web.app import create_app

    print(f"Quelle:       {workspace.source}")
    print(f"Arbeitskopie: {workspace.path} (vom {workspace.copied_at:%d.%m.%Y %H:%M})")
    print(f"Adresse:      http://127.0.0.1:{args.port}/")
    uvicorn.run(create_app(workspace), host="127.0.0.1", port=args.port, log_level="warning")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
