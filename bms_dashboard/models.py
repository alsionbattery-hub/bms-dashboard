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
class FaultState:
    status: str = "ok"
    consecutive_failures: int = 0
    last_error: str = ""
    updated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class MeasurementWithAnalytics:
    measurement: Measurement
    analytics: AnalyticsSnapshot
    fault: FaultState = field(default_factory=FaultState)
