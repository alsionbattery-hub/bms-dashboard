from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


class Measurement(BaseModel):
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    voltage_v: float
    current_a: float
    soc_pct: float
    temperature_c: float


class AnalyticsSnapshot(BaseModel):
    total_charge_energy_wh: float
    total_discharge_energy_wh: float
    round_trip_efficiency_pct: float


class MeasurementWithAnalytics(BaseModel):
    measurement: Measurement
    analytics: AnalyticsSnapshot
