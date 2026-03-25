from datetime import datetime, timedelta

from bms_dashboard.analytics import EnergyAccumulator
from bms_dashboard.models import Measurement


def test_round_trip_efficiency():
    acc = EnergyAccumulator()
    t0 = datetime(2026, 1, 1, 0, 0, 0)

    acc.update(Measurement(timestamp=t0, voltage_v=50.0, current_a=-10.0, soc_pct=30, temperature_c=20))
    # 1 hour charge: 500Wh in
    snap = acc.update(
        Measurement(timestamp=t0 + timedelta(hours=1), voltage_v=50.0, current_a=-10.0, soc_pct=40, temperature_c=20)
    )
    assert snap.total_charge_energy_wh == 500.0

    # 0.5 hour discharge at 400W: 200Wh out, eff=40%
    snap = acc.update(
        Measurement(timestamp=t0 + timedelta(hours=1, minutes=30), voltage_v=40.0, current_a=10.0, soc_pct=35, temperature_c=20)
    )

    assert round(snap.total_discharge_energy_wh, 6) == 200.0
    assert round(snap.round_trip_efficiency_pct, 6) == 40.0
