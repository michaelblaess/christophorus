"""Erzeugt die GitHub-Pages-Seite unter docs/ (Englisch unter /, Deutsch unter /de/).

Beide Sprachen kommen aus derselben Vorlage, damit sie nicht auseinanderlaufen.
Aufruf aus dem Repo-Wurzelverzeichnis:

    python web/baue_seiten.py
    cd web && node pruefe-gate.mjs
"""

from __future__ import annotations

import html
from pathlib import Path

WURZEL = Path(__file__).resolve().parent.parent
DOCS = WURZEL / "docs"
BASIS = "https://michaelblaess.github.io/christophorus"
PFAD = "/christophorus"
REPO = "https://github.com/michaelblaess/christophorus"
JAHR = "2026"
STAND = "16.09.2026"

ANBIETER = {
    "name": "Michael Blaess",
    "strasse": "Kurze Str. 2",
    "ort": "15345 Rehfelde",
    "land": "Deutschland",
    "mail": "mail@michaelblaess.de",
}

# Welche Seite in welcher Sprache wo liegt. Schluessel sind sprachneutral.
SEITEN = {
    "en": {"start": "index.html", "impressum": "legal.html", "datenschutz": "privacy.html"},
    "de": {"start": "de/index.html", "impressum": "de/impressum.html", "datenschutz": "de/datenschutz.html"},
}

TEXT = {
    "en": {
        "lang": "en",
        "nav_features": "Features",
        "nav_download": "Download",
        "toggle": "Switch theme",
        "impressum": "Legal notice",
        "datenschutz": "Privacy",
        "andere_sprache": "Deutsch",
        "footer": "Made by Michael Blaess · Apache License 2.0",
    },
    "de": {
        "lang": "de",
        "nav_features": "Funktionen",
        "nav_download": "Download",
        "toggle": "Hell oder dunkel",
        "impressum": "Impressum",
        "datenschutz": "Datenschutz",
        "andere_sprache": "English",
        "footer": "Von Michael Blaess · Apache License 2.0",
    },
}


def url(sprache: str, seite: str) -> str:
    """Absolute Adresse einer Seite, ohne index.html."""
    ziel = SEITEN[sprache][seite].removesuffix("index.html")
    return f"{BASIS}/{ziel}"


def pfad(sprache: str, seite: str) -> str:
    """Pfad fuer Links innerhalb der Seite, mit Projektpraefix."""
    return f"{PFAD}/{SEITEN[sprache][seite]}"


def rahmen(sprache: str, seite: str, titel: str, beschreibung: str, inhalt: str) -> str:
    """Kopf, Kopfzeile, Fusszeile und Metadaten um einen Seiteninhalt."""
    t = TEXT[sprache]
    andere = "de" if sprache == "en" else "en"
    hreflang = "\n".join(f'  <link rel="alternate" hreflang="{s}" href="{url(s, seite)}">' for s in ("en", "de"))
    return f"""<!DOCTYPE html>
<html lang="{t["lang"]}" data-theme="dark">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{html.escape(titel)}</title>
  <meta name="description" content="{html.escape(beschreibung)}">
  <link rel="canonical" href="{url(sprache, seite)}">
{hreflang}
  <link rel="alternate" hreflang="x-default" href="{url("en", seite)}">
  <meta property="og:title" content="{html.escape(titel)}">
  <meta property="og:description" content="{html.escape(beschreibung)}">
  <meta property="og:image" content="{BASIS}/social-preview.png">
  <meta property="og:url" content="{url(sprache, seite)}">
  <meta name="twitter:card" content="summary_large_image">
  <link rel="icon" href="{PFAD}/favicon.ico" sizes="any">
  <link rel="icon" type="image/png" href="{PFAD}/favicon.png">
  <link rel="stylesheet" href="{PFAD}/css/precision.css">
  <link rel="stylesheet" href="{PFAD}/css/christophorus.css">
  <script src="{PFAD}/js/theme.js"></script>
</head>
<body>

  <header class="header">
    <div class="header-left">
      <a href="{pfad(sprache, "start")}" class="header-home">
        <img src="{PFAD}/christophorus.png" alt="" class="header-logo">
        <span class="header-repo">christophorus</span>
      </a>
    </div>
    <div class="header-right">
      <a href="{pfad(sprache, "start")}#features" class="header-link">{t["nav_features"]}</a>
      <a href="{pfad(sprache, "start")}#screenshots" class="header-link">Screenshots</a>
      <a href="{pfad(sprache, "start")}#download" class="header-link">{t["nav_download"]}</a>
      <a href="{REPO}" class="header-link">GitHub</a>
      <a href="{pfad(andere, seite)}" class="header-link" hreflang="{andere}">{t["andere_sprache"]}</a>
      <button class="theme-toggle" onclick="toggleTheme()" aria-label="{t["toggle"]}">
        <svg class="icon-moon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/></svg>
        <svg class="icon-sun" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/><line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/></svg>
      </button>
    </div>
  </header>

{inhalt}

  <div class="divider"><div class="divider-line"></div></div>

  <footer class="footer">
    <div class="footer-left">
      <span>&copy; {JAHR} Michael Blaess · {t["footer"].split(" · ")[1]}</span>
    </div>
    <div class="footer-links">
      <a href="{pfad("en", "impressum")}" hreflang="en">Legal notice</a>
      <a href="{pfad("en", "datenschutz")}" hreflang="en">Privacy</a>
      <a href="{pfad("de", "impressum")}" hreflang="de">Impressum</a>
      <a href="{pfad("de", "datenschutz")}" hreflang="de">Datenschutz</a>
      <a href="{REPO}">GitHub</a>
    </div>
  </footer>

</body>
</html>
"""


# --- Startseite ------------------------------------------------------------------

START = {
    "en": {
        "titel": "Christophorus - vehicle logbook for the terminal",
        "beschreibung": "Open-source terminal application for keeping a vehicle logbook: trips, odometer chain, plausibility checks and Excel export, for leased and owned vehicles.",
        "badge": "Open source · Apache 2.0",
        "lead": "A terminal application for keeping a vehicle logbook, for leased and owned vehicles alike. It records every trip, keeps the odometer chain consistent, checks the entries for plausibility and exports the logbook as Excel, JSON or Markdown.",
        "btn_repo": "GitHub repository",
        "btn_download": "Download",
        "features_label": "Features",
        "features_titel": "What it does",
        "features_text": "Built for people who have to keep a logbook for the tax office and want to do it with the keyboard.",
        "features": [
            (
                "🚗",
                "Trips",
                "Date, travel time, destination, purpose, odometer start and end, business and private kilometres, round trips and fuel.",
            ),
            (
                "🔗",
                "Odometer chain",
                "Start and end values follow each other without gaps. A repair rebuilds the chain without changing any distance.",
            ),
            (
                "🔍",
                "Plausibility checks",
                "Gaps, jumps backwards, business trips on weekends and public holidays, fuel consumption, suspected duplicates.",
            ),
            (
                "📅",
                "Views",
                "List per month and year, calendar, year overview, blocked days, receipts and working hours.",
            ),
            (
                "📤",
                "Export",
                "Excel with live formulas, JSON with every field, Markdown table, chosen in a save dialog.",
            ),
            (
                "🕶️",
                "Anonymize",
                "Replaces destinations, purposes, vehicle and folder in the display, for screenshots. The database stays untouched.",
            ),
        ],
        "download_label": "Download",
        "download_titel": "Get started",
        "download_text": "One command installs the prebuilt package of the latest release. No Python and no git required. Running it again updates the program, your settings and logbooks stay untouched.",
        "download_karten": [
            (
                "Windows (PowerShell)",
                "irm https://raw.githubusercontent.com/michaelblaess/christophorus/main/install.ps1 | iex",
            ),
            (
                "Linux x86_64 / macOS Apple Silicon",
                "curl -fsSL https://raw.githubusercontent.com/michaelblaess/christophorus/main/install.sh | bash",
            ),
        ],
        "download_manuell": "Prefer to download it yourself? Every release contains standalone builds for Windows, Linux and macOS:",
        "download_releases": "Releases on GitHub",
        "shots_label": "Screenshots",
        "shots_titel": "How it looks",
        "shots_text": "All screenshots show made-up data.",
        "shots": [
            ("01-month-list", "Month list"),
            ("02-calendar", "Calendar"),
            ("03-year-overview", "Year overview"),
            ("04-plausicheck", "Plausibility check"),
            ("05-new-trip", "New trip"),
        ],
        "hinweis_label": "Please note",
        "hinweis_titel": "No tax advice",
        "hinweis": "Whether a logbook is accepted for tax purposes is decided solely by the tax office. Christophorus helps you keep one and checks the entries for plausibility, but it does not guarantee acceptance and does not replace tax advice. The software is provided under the Apache License 2.0, without warranty of any kind. On first start the program asks you to confirm this notice.",
    },
    "de": {
        "titel": "Christophorus - Fahrtenbuch im Terminal",
        "beschreibung": "Quelloffene Terminal-Anwendung für das Fahrtenbuch: Fahrten, Kilometerkette, Plausibilitätsprüfung und Excel-Export, für geleaste und gekaufte Fahrzeuge.",
        "badge": "Open Source · Apache 2.0",
        "lead": "Eine Terminal-Anwendung für das Fahrtenbuch, für geleaste wie für gekaufte Fahrzeuge. Sie erfasst jede Fahrt, hält die Kilometerkette stimmig, prüft die Einträge auf Plausibilität und exportiert das Fahrtenbuch als Excel, JSON oder Markdown.",
        "btn_repo": "GitHub-Repository",
        "btn_download": "Download",
        "features_label": "Funktionen",
        "features_titel": "Was es kann",
        "features_text": "Gebaut für alle, die ein Fahrtenbuch fürs Finanzamt führen müssen und das mit der Tastatur erledigen wollen.",
        "features": [
            (
                "🚗",
                "Fahrten",
                "Datum, Fahrzeit, Ziel, Reisezweck, Kilometerstand am Anfang und Ende, geschäftliche und private Kilometer, Hin- und Rückfahrt, Tanken.",
            ),
            (
                "🔗",
                "Kilometerkette",
                "Anfangs- und Endstände schließen lückenlos aneinander an. Die Reparatur setzt die Kette neu, ohne eine Strecke zu verändern.",
            ),
            (
                "🔍",
                "Plausicheck",
                "Lücken, Rückwärtssprünge, Geschäftsfahrten am Wochenende und an Feiertagen, Verbrauch, verdächtige Doppeleinträge.",
            ),
            (
                "📅",
                "Ansichten",
                "Liste je Monat und Jahr, Kalender, Jahresübersicht, gesperrte Tage, Belege und Arbeitszeit.",
            ),
            (
                "📤",
                "Export",
                "Excel mit Live-Formeln, JSON mit allen Feldern, Markdown-Tabelle, gewählt im Speichern-Dialog.",
            ),
            (
                "🕶️",
                "Anonymisieren",
                "Ersetzt Ziele, Zwecke, Fahrzeug und Ordner in der Anzeige, für Screenshots. Die Datenbank bleibt unberührt.",
            ),
        ],
        "download_label": "Download",
        "download_titel": "Loslegen",
        "download_text": "Ein Befehl installiert das fertige Paket des neuesten Releases. Python und git brauchst du dafür nicht. Ein zweiter Aufruf aktualisiert das Programm, deine Einstellungen und Fahrtenbücher bleiben unberührt.",
        "download_karten": [
            (
                "Windows (PowerShell)",
                "irm https://raw.githubusercontent.com/michaelblaess/christophorus/main/install.ps1 | iex",
            ),
            (
                "Linux x86_64 / macOS Apple Silicon",
                "curl -fsSL https://raw.githubusercontent.com/michaelblaess/christophorus/main/install.sh | bash",
            ),
        ],
        "download_manuell": "Lieber selbst herunterladen? Jedes Release enthält eigenständige Builds für Windows, Linux und macOS:",
        "download_releases": "Releases auf GitHub",
        "shots_label": "Screenshots",
        "shots_titel": "So sieht es aus",
        "shots_text": "Alle Screenshots zeigen erfundene Daten.",
        "shots": [
            ("01-month-list", "Monatsliste"),
            ("02-calendar", "Kalender"),
            ("03-year-overview", "Jahresübersicht"),
            ("04-plausicheck", "Plausicheck"),
            ("05-new-trip", "Neue Fahrt"),
        ],
        "hinweis_label": "Wichtiger Hinweis",
        "hinweis_titel": "Keine Steuerberatung",
        "hinweis": "Ob ein Fahrtenbuch steuerlich anerkannt wird, entscheidet allein das Finanzamt. Christophorus hilft beim Führen und prüft die Einträge auf Plausibilität, sichert die Anerkennung aber nicht zu und ersetzt keine steuerliche Beratung. Die Software steht unter der Apache License 2.0 und wird ohne jede Gewährleistung bereitgestellt. Beim ersten Start musst du diesen Hinweis bestätigen.",
    },
}


def startseite(sprache: str) -> str:
    s = START[sprache]
    karten = "\n".join(
        f"""      <div class="feature-card">
        <div class="feature-icon">{icon}</div>
        <h3>{html.escape(kopf)}</h3>
        <p>{html.escape(text)}</p>
      </div>"""
        for icon, kopf, text in s["features"]
    )
    download = "\n".join(
        f"""      <div class="install-card">
        <h4>{html.escape(kopf)}</h4>
        <div class="install-cmd">{html.escape(cmd)}</div>
      </div>"""
        for kopf, cmd in s["download_karten"]
    )
    bilder = "\n".join(
        f"""      <figure class="shot">
        <a href="{PFAD}/screenshots/{sprache}/{datei}.png"><img src="{PFAD}/screenshots/{sprache}/{datei}.png" alt="{html.escape(text)}" loading="lazy" width="1620" height="928"></a>
        <figcaption>{html.escape(text)}</figcaption>
      </figure>"""
        for datei, text in s["shots"]
    )
    inhalt = f"""  <section class="hero">
    <img src="{PFAD}/christophorus.png" alt="Christophorus" class="hero-logo" width="200" height="200">
    <div class="hero-badge"><span class="dot"></span> {s["badge"]}</div>
    <h1>Christo<span class="accent">phorus</span></h1>
    <p class="hero-description">{html.escape(s["lead"])}</p>
    <div class="hero-actions">
      <a href="{REPO}" class="btn btn-primary">{s["btn_repo"]}</a>
      <a href="{REPO}/releases" class="btn btn-secondary">{s["btn_download"]}</a>
    </div>
  </section>

  <section class="terminal-section">
    <div class="terminal">
      <div class="terminal-header">
        <div class="terminal-dot r"></div>
        <div class="terminal-dot y"></div>
        <div class="terminal-dot g"></div>
        <div class="terminal-title">christophorus</div>
      </div>
      <div class="terminal-body">
        <div><span class="prompt">$</span> <span class="cmd">christophorus</span></div>
        <div><span class="prompt">$</span> <span class="cmd">christophorus</span> <span class="flag">--year</span> <span class="url">2024</span></div>
        <div><span class="prompt">$</span> <span class="cmd">christophorus</span> <span class="flag">--lang</span> <span class="url">en</span></div>
        <div><span class="prompt">$</span> <span class="cmd">christo</span> <span class="flag">--version</span></div>
        <div><span class="ok">christophorus 1.3.1</span></div>
      </div>
    </div>
  </section>

  <div class="divider"><div class="divider-line"></div></div>

  <section class="section" id="features">
    <div class="section-label">{s["features_label"]}</div>
    <h2 class="section-title">{s["features_titel"]}</h2>
    <p class="section-description">{html.escape(s["features_text"])}</p>
    <div class="feature-grid">
{karten}
    </div>
  </section>

  <div class="divider"><div class="divider-line"></div></div>

  <section class="section" id="screenshots">
    <div class="section-label">{s["shots_label"]}</div>
    <h2 class="section-title">{s["shots_titel"]}</h2>
    <p class="section-description">{html.escape(s["shots_text"])}</p>
    <div class="shot-grid">
{bilder}
    </div>
  </section>

  <div class="divider"><div class="divider-line"></div></div>

  <section class="section" id="download">
    <div class="section-label">{s["download_label"]}</div>
    <h2 class="section-title">{s["download_titel"]}</h2>
    <p class="section-description">{html.escape(s["download_text"])}</p>
    <div class="install-grid">
{download}
    </div>
    <p class="section-description manual">{html.escape(s["download_manuell"])} <a href="{REPO}/releases">{s["download_releases"]}</a></p>
  </section>

  <div class="divider"><div class="divider-line"></div></div>

  <section class="section" id="hinweis">
    <div class="section-label">{s["hinweis_label"]}</div>
    <h2 class="section-title">{s["hinweis_titel"]}</h2>
    <p class="section-description notice">{html.escape(s["hinweis"])}</p>
  </section>"""
    return rahmen(sprache, "start", s["titel"], s["beschreibung"], inhalt)


# --- Rechtsseiten ----------------------------------------------------------------

ADRESSE = f"""{ANBIETER["name"]}<br>
        {ANBIETER["strasse"]}<br>
        {ANBIETER["ort"]}<br>
        {ANBIETER["land"]}"""

MAIL = f'<a href="mailto:{ANBIETER["mail"]}">{ANBIETER["mail"]}</a>'

MARKEN_DE = (
    "GitHub ist eine Marke von GitHub, Inc. Windows ist eine Marke der Microsoft Corporation, macOS eine "
    "Marke von Apple Inc., Linux eine Marke von Linus Torvalds und Python eine Marke der Python Software "
    "Foundation. Textual ist ein Projekt von Textualize. Alle genannten Marken gehören ihren jeweiligen "
    "Inhabern. Christophorus steht mit keinem von ihnen in Verbindung und wird von keinem unterstützt."
)
MARKEN_EN = (
    "GitHub is a trademark of GitHub, Inc. Windows is a trademark of Microsoft Corporation, macOS a trademark "
    "of Apple Inc., Linux a trademark of Linus Torvalds and Python a trademark of the Python Software "
    "Foundation. Textual is a project by Textualize. All trademarks mentioned belong to their respective "
    "owners. Christophorus is not affiliated with or endorsed by any of them."
)


def abschnitt(kopf: str, *absaetze: str) -> str:
    text = "\n".join(f"      <p>{a}</p>" for a in absaetze)
    return f"""    <div class="legal-block">
      <h2>{kopf}</h2>
{text}
    </div>"""


def rechtsseite(sprache: str, seite: str, label: str, titel: str, beschreibung: str, bloecke: list[str]) -> str:
    inhalt = f"""  <section class="section legal">
    <div class="section-label">{label}</div>
    <h1 class="section-title">{titel.split(" - ")[0]}</h1>
{chr(10).join(bloecke)}
  </section>"""
    return rahmen(sprache, seite, titel, beschreibung, inhalt)


def impressum_de() -> str:
    return rechtsseite(
        "de",
        "impressum",
        "Rechtliches",
        "Impressum - Christophorus",
        "Impressum der Projektseite von Christophorus, dem Fahrtenbuch im Terminal.",
        [
            abschnitt("Angaben gemäß § 5 DDG", ADRESSE),
            abschnitt("Kontakt", f"E-Mail: {MAIL}"),
            abschnitt(
                "Verantwortlich für den Inhalt nach § 18 Abs. 2 MStV",
                f"{ANBIETER['name']}, Anschrift wie oben.",
            ),
            abschnitt(
                "Zu diesem Projekt",
                "Christophorus ist ein privates, nicht-kommerzielles Open-Source-Projekt. Es wird nichts "
                "verkauft, vermittelt oder beworben, und diese Seite enthält weder Werbung noch Affiliate-Links.",
            ),
            abschnitt(
                "Haftungsausschluss für die Software",
                "Christophorus wird unter der Apache License 2.0 bereitgestellt, so wie es ist und ohne "
                "Gewährleistung jeglicher Art, weder ausdrücklich noch stillschweigend. Maßgeblich ist der "
                f'<a href="{REPO}/blob/main/LICENSE">Lizenztext</a>.',
                "Ob ein Fahrtenbuch steuerlich anerkannt wird, entscheidet allein das Finanzamt. Die Software "
                "sichert diese Anerkennung nicht zu und ersetzt keine steuerliche Beratung. Für die Richtigkeit "
                "der erfassten Daten und für Folgen ihrer Verwendung bist du selbst verantwortlich.",
            ),
            abschnitt(
                "Haftung für Inhalte",
                "Die Inhalte dieser Seite wurden mit Sorgfalt erstellt. Für die Richtigkeit, Vollständigkeit "
                "und Aktualität kann ich jedoch keine Gewähr übernehmen.",
            ),
            abschnitt(
                "Haftung für Links",
                "Diese Seite enthält Links zu externen Webseiten, vor allem zu GitHub, auf deren Inhalte ich "
                "keinen Einfluss habe. Für diese fremden Inhalte kann ich keine Gewähr übernehmen, "
                "verantwortlich ist der jeweilige Anbieter. Bei Bekanntwerden von Rechtsverletzungen entferne "
                "ich solche Links umgehend.",
            ),
            abschnitt("Markenhinweis", MARKEN_DE),
            abschnitt(
                "Urheberrecht",
                f"&copy; {JAHR} Michael Blaess. Der Quellcode von Christophorus steht unter der Apache License 2.0.",
            ),
            abschnitt(
                "Streitbeilegung",
                "Ich bin nicht bereit oder verpflichtet, an Streitbeilegungsverfahren vor einer "
                "Verbraucherschlichtungsstelle teilzunehmen.",
            ),
        ],
    )


def legal_en() -> str:
    return rechtsseite(
        "en",
        "impressum",
        "Legal",
        "Legal notice - Christophorus",
        "Legal notice for the project page of Christophorus, the vehicle logbook for the terminal.",
        [
            abschnitt(
                "Provider according to § 5 DDG (German Digital Services Act)",
                ADRESSE,
                'The legally binding version is the German <a href="'
                + pfad("de", "impressum")
                + '" hreflang="de">Impressum</a>.',
            ),
            abschnitt("Contact", f"Email: {MAIL}"),
            abschnitt(
                "Responsible for the content according to § 18 (2) MStV",
                f"{ANBIETER['name']}, address as above.",
            ),
            abschnitt(
                "About this project",
                "Christophorus is a private, non-commercial open-source project. Nothing is sold, brokered or "
                "advertised, and this page contains neither advertising nor affiliate links.",
            ),
            abschnitt(
                "Software disclaimer",
                'Christophorus is provided under the Apache License 2.0, on an "as is" basis, without '
                "warranties or conditions of any kind, either express or implied. The "
                f'<a href="{REPO}/blob/main/LICENSE">license text</a> is authoritative.',
                "Whether a logbook is accepted for tax purposes is decided solely by the tax office. The "
                "software does not guarantee that acceptance and does not replace tax advice. You are "
                "responsible for the accuracy of the data you enter and for the consequences of using it.",
            ),
            abschnitt(
                "Liability for content",
                "The content of this page was created with care. However, I cannot guarantee that it is "
                "correct, complete or up to date.",
            ),
            abschnitt(
                "Liability for links",
                "This page links to external websites, mainly GitHub, whose content is beyond my control. "
                "I cannot accept any liability for that content, the respective provider is responsible. "
                "If I become aware of any infringement, I will remove such links immediately.",
            ),
            abschnitt("Trademarks", MARKEN_EN),
            abschnitt(
                "Copyright",
                f"&copy; {JAHR} Michael Blaess. The source code of Christophorus is licensed under the Apache License 2.0.",
            ),
            abschnitt(
                "Dispute resolution",
                "I am neither willing nor obliged to take part in dispute resolution proceedings before a "
                "consumer arbitration board.",
            ),
        ],
    )


GITHUB_PRIVACY = "https://docs.github.com/en/site-policy/privacy-policies/github-general-privacy-statement"
GITHUB_PAGES_DOC = "https://docs.github.com/en/pages/getting-started-with-github-pages/what-is-github-pages"


def datenschutz_de() -> str:
    return rechtsseite(
        "de",
        "datenschutz",
        "Rechtliches",
        "Datenschutzerklärung - Christophorus",
        "Datenschutzerklärung der Projektseite von Christophorus: Hosting bei GitHub Pages, keine Cookies, kein Tracking.",
        [
            abschnitt(
                "Kurz gesagt",
                "Diese Seite ist eine statische Projektseite. Sie setzt keine Cookies, verwendet kein Tracking, "
                "keine Statistik und kein Kontaktformular. Schriften, Bilder und Skripte liegen alle auf "
                "demselben Server, es wird nichts von fremden Servern nachgeladen. Personenbezogene Daten "
                "fallen nur beim Hosting an, siehe unten.",
            ),
            abschnitt("Verantwortlicher", ADRESSE, f"E-Mail: {MAIL}"),
            abschnitt(
                "Hosting bei GitHub Pages",
                "Diese Seite wird über GitHub Pages ausgeliefert. Anbieter ist für Nutzer im Europäischen "
                "Wirtschaftsraum die GitHub B.V., Prins Bernhardplein 200, 1097 JB Amsterdam, Niederlande, "
                "eine Tochter der GitHub, Inc. in den USA.",
                "Beim Aufruf protokolliert GitHub nach eigener Angabe die IP-Adresse jedes Besuchers und "
                f'speichert sie zu Sicherheitszwecken (<a href="{GITHUB_PAGES_DOC}">GitHub Docs</a>). '
                "Wie lange GitHub diese Daten aufbewahrt, bestimmt GitHub. Ich selbst erhalte keine "
                "Zugriffsdaten und keine Statistik.",
                "Rechtsgrundlage ist Art. 6 Abs. 1 lit. f DSGVO. Mein berechtigtes Interesse liegt in einer "
                "sicheren, kostenlosen Bereitstellung der Projektseite. Dabei können Daten in die USA "
                "übermittelt werden. GitHub gibt an, nach dem EU-U.S. Data Privacy Framework zertifiziert zu "
                f'sein. Einzelheiten stehen in der <a href="{GITHUB_PRIVACY}">Datenschutzerklärung von GitHub</a>.',
            ),
            abschnitt(
                "Speicherung im Browser",
                "Wenn du den Schalter für hell oder dunkel benutzt, wird deine Wahl unter dem Schlüssel "
                "<code>theme</code> im Local Storage deines Browsers gespeichert. Sie verlässt deinen Browser "
                "nicht und enthält keine personenbezogenen Daten. Rechtsgrundlage ist § 25 Abs. 2 Nr. 2 TDDDG, "
                "weil die Speicherung für die von dir gewünschte Darstellung erforderlich ist. Du kannst den "
                "Eintrag jederzeit über die Einstellungen deines Browsers löschen.",
            ),
            abschnitt(
                "Links zu GitHub",
                "Links auf das Repository, die Releases und die Lizenz führen zu GitHub. Dort gilt die "
                "Datenschutzerklärung von GitHub.",
            ),
            abschnitt(
                "Kontakt per E-Mail",
                "Wenn du mir schreibst, verwende ich deine Angaben nur, um deine Anfrage zu beantworten, und "
                "gebe sie nicht weiter. Rechtsgrundlage ist Art. 6 Abs. 1 lit. f DSGVO.",
            ),
            abschnitt(
                "Die Software selbst",
                "Christophorus läuft auf deinem Rechner. Die Anwendung überträgt keine Fahrtenbuch-Daten an mich "
                "oder an Dritte, die Daten bleiben in dem Ordner, den du wählst.",
            ),
            abschnitt(
                "Deine Rechte",
                "Du hast nach der DSGVO das Recht auf Auskunft (Art. 15), Berichtigung (Art. 16), Löschung "
                "(Art. 17), Einschränkung der Verarbeitung (Art. 18), Datenübertragbarkeit (Art. 20) und "
                "Widerspruch (Art. 21). Außerdem kannst du dich bei einer Datenschutz-Aufsichtsbehörde "
                "beschweren (Art. 77), zum Beispiel an deinem Wohnort. Für Daten, die GitHub verarbeitet, "
                "wendest du dich am besten direkt an GitHub.",
            ),
            abschnitt("Stand", STAND),
        ],
    )


def privacy_en() -> str:
    return rechtsseite(
        "en",
        "datenschutz",
        "Legal",
        "Privacy policy - Christophorus",
        "Privacy policy for the project page of Christophorus: hosted on GitHub Pages, no cookies, no tracking.",
        [
            abschnitt(
                "In short",
                "This is a static project page. It sets no cookies and uses no tracking, no analytics and no "
                "contact form. Fonts, images and scripts are all served from the same server, nothing is loaded "
                "from third-party servers. Personal data is only processed by the hosting, see below. The "
                f'legally binding version is the German <a href="{pfad("de", "datenschutz")}" hreflang="de">'
                "Datenschutzerklärung</a>.",
            ),
            abschnitt("Controller", ADRESSE, f"Email: {MAIL}"),
            abschnitt(
                "Hosting on GitHub Pages",
                "This page is served by GitHub Pages. For users in the European Economic Area the provider is "
                "GitHub B.V., Prins Bernhardplein 200, 1097 JB Amsterdam, the Netherlands, a subsidiary of "
                "GitHub, Inc. in the USA.",
                "According to GitHub, the IP address of every visitor is logged and stored for security "
                f'purposes (<a href="{GITHUB_PAGES_DOC}">GitHub Docs</a>). GitHub decides how long this data '
                "is kept. I do not receive any access data or statistics.",
                "The legal basis is Art. 6 (1) (f) GDPR. My legitimate interest is a secure, free way to publish "
                "the project page. Data may be transferred to the USA. GitHub states that it is certified under "
                f'the EU-U.S. Data Privacy Framework. Details are in the <a href="{GITHUB_PRIVACY}">GitHub '
                "Privacy Statement</a>.",
            ),
            abschnitt(
                "Storage in your browser",
                "If you use the light/dark switch, your choice is stored under the key <code>theme</code> in "
                "your browser's local storage. It never leaves your browser and contains no personal data. The "
                "legal basis is § 25 (2) no. 2 TDDDG, because the storage is necessary for the display you "
                "requested. You can delete it at any time in your browser settings.",
            ),
            abschnitt(
                "Links to GitHub",
                "Links to the repository, the releases and the license lead to GitHub, where GitHub's privacy "
                "statement applies.",
            ),
            abschnitt(
                "Contact by email",
                "If you write to me, I use your details only to answer your request and do not pass them on. "
                "The legal basis is Art. 6 (1) (f) GDPR.",
            ),
            abschnitt(
                "The software itself",
                "Christophorus runs on your computer. The application does not send any logbook data to me or to "
                "third parties, the data stays in the folder you choose.",
            ),
            abschnitt(
                "Your rights",
                "Under the GDPR you have the right of access (Art. 15), rectification (Art. 16), erasure "
                "(Art. 17), restriction of processing (Art. 18), data portability (Art. 20) and objection "
                "(Art. 21). You may also lodge a complaint with a data protection supervisory authority "
                "(Art. 77). For data processed by GitHub, please contact GitHub directly.",
            ),
            abschnitt("Last updated", "16 September 2026"),
        ],
    )


def fehlerseite() -> str:
    inhalt = f"""  <section class="hero">
    <img src="{PFAD}/christophorus.png" alt="" class="hero-logo" width="140" height="140">
    <h1>404</h1>
    <p class="hero-description">This page does not exist. Diese Seite gibt es nicht.</p>
    <div class="hero-actions">
      <a href="{pfad("en", "start")}" class="btn btn-primary">Home</a>
      <a href="{pfad("de", "start")}" class="btn btn-secondary">Startseite</a>
    </div>
  </section>"""
    return rahmen("en", "start", "404 - Christophorus", "Page not found.", inhalt).replace(
        f'<link rel="canonical" href="{url("en", "start")}">\n', ""
    )


def sitemap() -> str:
    eintraege = "\n".join(
        f"  <url><loc>{url(s, seite)}</loc><lastmod>2026-09-16</lastmod></url>"
        for s in ("en", "de")
        for seite in ("start", "impressum", "datenschutz")
    )
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
{eintraege}
</urlset>
"""


def schreibe(rel: str, inhalt: str) -> None:
    ziel = DOCS / rel
    ziel.parent.mkdir(parents=True, exist_ok=True)
    ziel.write_text(inhalt, encoding="utf-8", newline="\n")
    print("geschrieben:", rel)


def main() -> None:
    schreibe("index.html", startseite("en"))
    schreibe("de/index.html", startseite("de"))
    schreibe("legal.html", legal_en())
    schreibe("privacy.html", privacy_en())
    schreibe("de/impressum.html", impressum_de())
    schreibe("de/datenschutz.html", datenschutz_de())
    schreibe("404.html", fehlerseite())
    schreibe("sitemap.xml", sitemap())
    schreibe("robots.txt", f"User-agent: *\nAllow: /\n\nSitemap: {BASIS}/sitemap.xml\n")
    schreibe(".nojekyll", "")


if __name__ == "__main__":
    main()
