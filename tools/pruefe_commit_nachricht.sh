#!/bin/sh
# Prueft die Commit-Nachricht auf Ersatzschreibung (ae/oe/ue/ss) und die harten
# Checks aus check_ai_tells.py. Deutsche Commit-Nachrichten sind Lesertext.
#
# Hintergrund: 5e8421c (17.09.2026) ging mit "Loeschen", "Aenderung", "Pruefung"
# und vier weiteren Stellen ins Remote. Der Linter allein haette nur einen Teil
# gemeldet, seine Wortliste ist kuratiert - deshalb zusaetzlich eine eigene
# Wortpruefung mit Ausnahmeliste. Vorlage: happy-watches.de/.githooks/commit-msg.
#
# Laeuft als pre-commit-Hook der Stufe commit-msg, NICHT ueber core.hooksPath -
# das wuerde die uebrigen pre-commit-Gates (ruff, mypy, pytest) aushebeln.
# Einrichten je Klon:  pre-commit install --hook-type commit-msg
# Bewusst umgehen:     git commit --no-verify
#
# Der Linter liegt in claude-config und ist auf jedem Rechner unter
# ~/.claude/skills/ verlinkt. Anderer Ort: CHRISTO_LINTER setzen.

set -u

MSG_FILE="$1"
LINTER="${CHRISTO_LINTER:-$HOME/.claude/skills/michaels-writing-style/check_ai_tells.py}"

# Kommentarzeilen, den Diff-Anhang von "commit -v" und die Attributionszeilen
# entfernen - die gehoeren nicht zum Lesertext.
TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT
sed -e '/^#/d' -e '/^diff --git /,$d' -e '/^Co-Authored-By:/d' -e '/^Claude-Session:/d' \
    "$MSG_FILE" > "$TMP"

FEHLER=0

# ------------------------------------------------------------------ Linter ---

if [ -f "$LINTER" ]; then
    PY=""
    for c in python python3 py; do
        if command -v "$c" >/dev/null 2>&1; then PY="$c"; break; fi
    done
    if [ -n "$PY" ]; then
        OUT="$(PYTHONUTF8=1 "$PY" "$LINTER" "$TMP" 2>&1)"
        RC=$?
        if [ $RC -ne 0 ] && [ $RC -ne 1 ]; then
            echo "commit-msg: Linter brach ab (Code $RC):" >&2
            echo "$OUT" >&2
            exit 1
        fi
        if printf '%s' "$OUT" | grep -q '\[HART'; then
            echo "" >&2
            echo "commit-msg: harte Treffer des Linters:" >&2
            printf '%s\n' "$OUT" | grep '\[HART' \
                | sed -E -e 's|^.*:([0-9]+): |Zeile \1: |' -e 's/^/  /' >&2
            FEHLER=1
        fi
    else
        echo "commit-msg: kein Python im PATH, nur die Wortpruefung laeuft." >&2
    fi
else
    # Kein fail-closed: dieses Repo steht oeffentlich und laeuft auch ohne
    # claude-config. Die Wortpruefung unten braucht den Linter nicht.
    echo "commit-msg: Linter nicht gefunden ($LINTER), nur die Wortpruefung laeuft." >&2
fi

# --------------------------------------------------- Wortpruefung ae/oe/ue ---

# Woerter mit ae/oe/ue. Ausgenommen sind Bezeichner (mit _ / Backtick oder einem
# Punkt mitten im Wort wie sync_web_assets.py - ein Satzpunkt am Ende zaehlt
# nicht) und echte Woerter, in denen die Buchstabenfolge richtig ist. Die
# Ausnahmen stammen aus der Auswertung aller bisherigen Nachrichten dieses Repos.
AUSNAHMEN='neu|quell|uell|euer|aue|blue|true|joe|request|zuerst|michael|aero|poet|queue|value|issue|continue|due|status'

# Hex-Ketten sind Commit-SHAs, keine Woerter - 0a6aae2 enthaelt "aae".
WOERTER="$(tr -s ' \t' '\n' < "$TMP" \
    | grep -vE '[_/`]|\.[A-Za-z]' \
    | grep -viE '^[(]?[0-9a-f]{7,40}[),.]?$' \
    | grep -oiE "[a-zäöüß-]*(ae|oe|ue)[a-zäöüß-]*" \
    | grep -viE "$AUSNAHMEN" \
    | sort -u | tr '\n' ' ')"

if [ -n "$WOERTER" ]; then
    echo "" >&2
    echo "commit-msg: Ersatzschreibung in der Nachricht:" >&2
    echo "  $WOERTER" >&2
    FEHLER=1
fi

if [ $FEHLER -ne 0 ]; then
    echo "" >&2
    echo "  Deutsche Commit-Nachrichten sind Lesertext und brauchen echte Umlaute." >&2
    echo "  Bezeichner wie km_geschaeftlich in Backticks setzen. Echtes Wort" >&2
    echo "  faelschlich gemeldet: in AUSNAHMEN in tools/pruefe_commit_nachricht.sh" >&2
    echo "  eintragen." >&2
    echo "" >&2
    exit 1
fi

exit 0
