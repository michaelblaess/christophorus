"""Kopiert die statischen Fremddateien fuer christo.web nach src/christo/web/static/vendor/.

Quellen:
    - web-themes (Nachbar-Repo, privat): dist/ und die mitgelieferten Bibliotheken
      Tabler, Tabulator, Manrope und JetBrains Mono samt Lizenzen
    - htmx: Pfad zu einer entpackten htmx.org-Distribution (npm), Lizenz 0BSD

christo.web braucht von web-themes nur die fertigen Dateien. Eine Python-Abhaengigkeit auf das
private Repo wuerde Installation und CI fuer alle anderen brechen.

Aufruf:
    uv run python tools/sync_web_assets.py --web-themes ../web-themes --htmx <pfad>/node_modules/htmx.org
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
from datetime import date
from pathlib import Path

ZIEL = Path(__file__).resolve().parent.parent / "src" / "christo" / "web" / "static" / "vendor"


def _commit(repo: Path) -> str:
    ergebnis = subprocess.run(
        ["git", "-C", str(repo), "rev-parse", "--short", "HEAD"],
        capture_output=True,
        text=True,
        stdin=subprocess.DEVNULL,
        check=False,
    )
    return ergebnis.stdout.strip() or "unbekannt"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--web-themes", type=Path, required=True)
    parser.add_argument("--htmx", type=Path, required=True, help="Ordner des npm-Pakets htmx.org")
    args = parser.parse_args()

    themes: Path = args.web_themes.resolve()
    katalog_vendor = themes / "src" / "web_themes" / "catalog" / "static" / "vendor"
    kopien = {
        themes / "dist" / "web-themes.css": ZIEL / "web-themes" / "web-themes.css",
        themes / "dist" / "web-themes-tabulator.css": ZIEL / "web-themes" / "web-themes-tabulator.css",
        themes / "dist" / "web-themes.js": ZIEL / "web-themes" / "web-themes.js",
        themes / "LICENSE": ZIEL / "web-themes" / "LICENSE",
        args.htmx / "dist" / "htmx.min.js": ZIEL / "htmx" / "htmx.min.js",
        args.htmx / "LICENSE": ZIEL / "htmx" / "LICENSE",
    }
    for unterordner in ("tabler", "tabulator", "fonts"):
        for datei in (katalog_vendor / unterordner).iterdir():
            kopien[datei] = ZIEL / unterordner / datei.name

    for quelle, ziel in kopien.items():
        if not quelle.is_file():
            raise SystemExit(f"Quelle fehlt: {quelle}")
        ziel.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(quelle, ziel)

    import json

    htmx_version = json.loads((args.htmx / "package.json").read_text(encoding="utf-8"))["version"]
    vermerk = (
        "Herkunft der Dateien in diesem Ordner, geschrieben von tools/sync_web_assets.py\n\n"
        f"Stand:      {date.today():%d.%m.%Y}\n"
        f"web-themes: Commit {_commit(themes)} (dist/ sowie tabler, tabulator, fonts aus dem Katalog)\n"
        f"htmx:       {htmx_version} (npm htmx.org, Lizenz 0BSD)\n\n"
        "Nicht von Hand aendern. Neue Staende immer ueber das Werkzeug holen.\n"
    )
    (ZIEL / "HERKUNFT.txt").write_text(vermerk, encoding="utf-8", newline="\n")
    print(f"{len(kopien)} Dateien nach {ZIEL} kopiert")
    print(vermerk)


if __name__ == "__main__":
    main()
