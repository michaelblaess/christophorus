"""Zentrale Formatierungs-Helfer fuer Zahlen, km-Werte und deutsches Format."""


def format_km(value: int | float | None) -> str:
    """Formatiert einen km-Wert mit deutschem Tausender-Trennzeichen (Punkt).

    Beispiele:
      * 594     → "594"
      * 1234    → "1.234"
      * 19444   → "19.444"
      * 0 / None → "0"
      * 3.5     → "4"   (nur ganze km — Feldwerte sind im Modell int)
    """
    if value is None:
        return "0"
    n = int(round(float(value)))
    # Pythons f"{n:,}" benutzt Komma als Tausender-Trenner. Wir wollen einen
    # Punkt (deutsches Format), deshalb Komma -> Punkt.
    return f"{n:,}".replace(",", ".")


def parse_km(raw: str | None, default: int = 0) -> int:
    """Wandelt einen Anwender-String in einen int-km-Wert um.

    Akzeptiert Leerstring, reine Zahlen und deutsche Tausender-Trennzeichen.
    Beispiele:
      * "19.444"  → 19444
      * "19444"   → 19444
      * ""        → default
      * " 1.234 " → 1234
      * "abc"     → default
    """
    if raw is None:
        return default
    cleaned = raw.strip().replace(".", "").replace(" ", "")
    if not cleaned:
        return default
    try:
        return int(cleaned)
    except ValueError:
        return default
