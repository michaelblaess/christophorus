"""CLI Entry Point fuer die Fahrtenbuch TUI."""

import argparse


def main() -> None:
    """Startet die Fahrtenbuch TUI."""
    parser = argparse.ArgumentParser(
        prog="fahrtenbuch",
        description="Fahrtenbuch TUI — Finanzamt-konforme Fahrtenbuecher",
    )
    parser.add_argument(
        "--year",
        type=int,
        default=0,
        help="Jahr (z.B. 2024). Default: aus Settings",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__import__('fahrtenbuch_app').__version__}",
    )

    args = parser.parse_args()

    from fahrtenbuch_app.app import FahrtenbuchApp

    app = FahrtenbuchApp(year_override=args.year if args.year > 0 else None)
    app.run()


if __name__ == "__main__":
    main()
