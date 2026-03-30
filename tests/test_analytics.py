from datetime import datetime, timedelta

from bms_dashboard.analytics import EnergyAccumulator
from bms_dashboard.models import Measurement
from bms_dashboard.spi_bms import L99BM114Config, L99BM114Protocol


def test_round_trip_efficiency():
    acc = EnergyAccumulator()
    t0 = datetime(2026, 1, 1, 0, 0, 0)

    acc.update(Measurement(timestamp=t0, pack_voltage_v=50.0, current_a=-10.0, soc_pct=30, temperature_c=20))
    # 1 hour charge: 500Wh in
    snap = acc.update(
        Measurement(timestamp=t0 + timedelta(hours=1), pack_voltage_v=50.0, current_a=-10.0, soc_pct=40, temperature_c=20)
    )
    assert snap.total_charge_energy_wh == 500.0

    # 0.5 hour discharge at 400W: 200Wh out, eff=40%
    snap = acc.update(
        Measurement(timestamp=t0 + timedelta(hours=1, minutes=30), pack_voltage_v=40.0, current_a=10.0, soc_pct=35, temperature_c=20)
    )

    assert round(snap.total_discharge_energy_wh, 6) == 200.0
    assert round(snap.round_trip_efficiency_pct, 6) == 40.0


def test_l99bm114_protocol_crc_round_trip():
    proto = L99BM114Protocol()
    frame = proto.build_read_frame(device_id=2, reg_addr=0x10)
    # Echo request bytes for deterministic validation.
    assert proto.decode_read_response(frame) == 0x00


def test_efficiency_is_bounded_to_100_pct():
    acc = EnergyAccumulator()
    t0 = datetime(2026, 1, 1, 0, 0, 0)

    # charge 10Wh
    acc.update(Measurement(timestamp=t0, pack_voltage_v=10.0, current_a=-1.0, soc_pct=30, temperature_c=20))
    snap = acc.update(
        Measurement(timestamp=t0 + timedelta(hours=1), pack_voltage_v=10.0, current_a=-1.0, soc_pct=40, temperature_c=20)
    )
    assert snap.total_charge_energy_wh == 10.0

    # then discharge 20Wh; unclamped value would be 200%
    snap = acc.update(
        Measurement(timestamp=t0 + timedelta(hours=2), pack_voltage_v=20.0, current_a=1.0, soc_pct=35, temperature_c=20)
    )
    assert snap.total_discharge_energy_wh == 20.0
    assert snap.round_trip_efficiency_pct == 100.0


def test_l99bm114_config_can_be_loaded_from_environment(monkeypatch):
    monkeypatch.setenv("BMS_DEVICE_ID", "3")
    monkeypatch.setenv("BMS_REG_PACK_VOLTAGE", "0x40")
    monkeypatch.setenv("BMS_CELL_COUNT", "12")
    monkeypatch.setenv("BMS_CURRENT_OFFSET", "-6.25")
    monkeypatch.setenv("BMS_CELL_V_SCALE", "0.005")

    cfg = L99BM114Config.from_env()
    assert cfg.device_id == 3
    assert cfg.reg_pack_voltage == 0x40
    assert cfg.cell_count == 12
    assert cfg.current_offset == -6.25
    assert cfg.cell_voltage_scale == 0.005
