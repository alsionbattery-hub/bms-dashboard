from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from .models import AnalyticsSnapshot, Measurement


@dataclass
class EnergyAccumulator:
    total_charge_energy_wh: float = 0.0
    total_discharge_energy_wh: float = 0.0
    _last_ts: datetime | None = None

    def update(self, measurement: Measurement) -> AnalyticsSnapshot:
        if self._last_ts is not None:
            dt_hours = (measurement.timestamp - self._last_ts).total_seconds() / 3600.0
            power_w = measurement.voltage_v * measurement.current_a
            energy_wh = power_w * dt_hours
            if energy_wh >= 0:
                self.total_discharge_energy_wh += energy_wh
            else:
                self.total_charge_energy_wh += abs(energy_wh)

        self._last_ts = measurement.timestamp

        eff = 0.0
        if self.total_charge_energy_wh > 0:
            eff = 100.0 * self.total_discharge_energy_wh / self.total_charge_energy_wh

        return AnalyticsSnapshot(
            total_charge_energy_wh=self.total_charge_energy_wh,
            total_discharge_energy_wh=self.total_discharge_energy_wh,
            round_trip_efficiency_pct=eff,
        )
