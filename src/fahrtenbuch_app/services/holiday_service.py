"""Feiertags- und Wochenend-Erkennung."""

from datetime import date, timedelta

import holidays

_STATE_NAMES: dict[str, str] = {
    "BW": "Baden-Wuerttemberg",
    "BY": "Bayern",
    "BE": "Berlin",
    "BB": "Brandenburg",
    "HB": "Bremen",
    "HH": "Hamburg",
    "HE": "Hessen",
    "MV": "Mecklenburg-Vorpommern",
    "NI": "Niedersachsen",
    "NW": "Nordrhein-Westfalen",
    "RP": "Rheinland-Pfalz",
    "SL": "Saarland",
    "SN": "Sachsen",
    "ST": "Sachsen-Anhalt",
    "SH": "Schleswig-Holstein",
    "TH": "Thueringen",
}


class HolidayService:
    """Erkennt Feiertage und Wochenenden fuer ein deutsches Bundesland."""

    def __init__(self, federal_state: str = "BB") -> None:
        if federal_state not in _STATE_NAMES:
            federal_state = "BB"
        self._state = federal_state
        self._cache: dict[int, holidays.Germany] = {}

    def _get_holidays(self, year: int) -> holidays.Germany:
        """Gibt die Feiertage fuer ein Jahr zurueck (gecacht)."""
        if year not in self._cache:
            self._cache[year] = holidays.Germany(subdiv=self._state, years=year)
        return self._cache[year]

    def is_holiday(self, d: date) -> bool:
        """Prueft ob ein Datum ein Feiertag ist."""
        return d in self._get_holidays(d.year)

    def get_holiday_name(self, d: date) -> str:
        """Gibt den Feiertagsnamen zurueck oder leeren String."""
        h = self._get_holidays(d.year)
        return h.get(d, "")

    def is_weekend(self, d: date) -> bool:
        """Prueft ob ein Datum ein Wochenende ist."""
        return d.weekday() >= 5

    def is_workday(self, d: date) -> bool:
        """Prueft ob ein Datum ein Arbeitstag ist (kein Wochenende, kein Feiertag)."""
        return not self.is_weekend(d) and not self.is_holiday(d)

    def get_holidays_in_month(self, year: int, month: int) -> dict[date, str]:
        """Gibt alle Feiertage eines Monats zurueck als {date: name}."""
        h = self._get_holidays(year)
        result: dict[date, str] = {}
        for d, name in sorted(h.items()):
            if d.month == month and d.year == year:
                result[d] = name
        return result

    def count_workdays_in_month(self, year: int, month: int) -> int:
        """Zaehlt die Arbeitstage in einem Monat."""
        import calendar
        count = 0
        cal = calendar.Calendar()
        for day_num, weekday in cal.itermonthdays2(year, month):
            if day_num == 0:
                continue
            d = date(year, month, day_num)
            if self.is_workday(d):
                count += 1
        return count
