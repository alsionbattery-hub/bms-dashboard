from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Measurement:
    timestamp: datetime = field(default_factory=datetime.utcnow)
    pack_voltage_v: float = 0.0
    current_a: float = 0.0
    soc_pct: float = 0.0
    temperature_c: float = 0.0
    cell_voltages_v: list[float] = field(default_factory=list)


@dataclass
class AnalyticsSnapshot:
    total_charge_energy_wh: float = 0.0
    total_discharge_energy_wh: float = 0.0
    round_trip_efficiency_pct: float = 0.0


@dataclass
class MeasurementWithAnalytics:
    measurement: Measurement
    analytics: AnalyticsSnapshot
