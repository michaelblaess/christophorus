"""Fahrzeug-Modell."""

from dataclasses import dataclass
from typing import Any


@dataclass
class Vehicle:
    """Leasing-Fahrzeug mit Vertragsdaten."""

    name: str = ""
    plate: str = ""
    contract_number: str = ""
    lease_km_per_month: int = 1500
    start_km: int = 0
    end_km: int = 0
    start_date: str = ""
    end_date: str = ""
    lease_months: int = 12
    tank_capacity_l: float = 0.0
    consumption_l_100km: float = 0.0

    @property
    def total_lease_km(self) -> int:
        """Gesamte Inklusivkilometer ueber Vertragslaufzeit."""
        return self.lease_km_per_month * self.lease_months

    @property
    def total_driven_km(self) -> int:
        """Tatsaechlich gefahrene Kilometer."""
        return self.end_km - self.start_km

    @property
    def km_over_limit(self) -> int:
        """Ueberschreitung der Inklusivkilometer (negativ = unter Limit)."""
        return self.total_driven_km - self.total_lease_km

    def to_dict(self) -> dict[str, Any]:
        """Serialisierung fuer JSON."""
        return {
            "name": self.name,
            "plate": self.plate,
            "contract_number": self.contract_number,
            "lease_km_per_month": self.lease_km_per_month,
            "start_km": self.start_km,
            "end_km": self.end_km,
            "start_date": self.start_date,
            "end_date": self.end_date,
            "lease_months": self.lease_months,
            "tank_capacity_l": self.tank_capacity_l,
            "consumption_l_100km": self.consumption_l_100km,
        }

    @staticmethod
    def from_dict(data: dict[str, Any]) -> "Vehicle":
        """Deserialisierung aus JSON."""
        return Vehicle(
            name=data.get("name", ""),
            plate=data.get("plate", ""),
            contract_number=data.get("contract_number", ""),
            lease_km_per_month=data.get("lease_km_per_month", 1500),
            start_km=data.get("start_km", 0),
            end_km=data.get("end_km", 0),
            start_date=data.get("start_date", ""),
            end_date=data.get("end_date", ""),
            lease_months=data.get("lease_months", 12),
            tank_capacity_l=float(data.get("tank_capacity_l", 0.0)),
            consumption_l_100km=float(data.get("consumption_l_100km", 0.0)),
        )
