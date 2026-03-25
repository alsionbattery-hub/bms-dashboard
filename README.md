# BMS Dashboard (Raspberry Pi + SPI)

This project provides a lightweight backend for a Battery Management System (BMS) dashboard that supports:

- **Real-time measurements** from a BMS connected via **SPI** on Raspberry Pi.
- **Historical measurements** persisted in SQLite.
- **Analytics** including round-trip efficiency from cumulative discharge/charge energy:
  - `efficiency = total_discharge_energy / total_charge_energy * 100`

## Architecture

- `bms_dashboard/spi_bms.py` — SPI reader abstraction with mock mode for local dev.
- `bms_dashboard/storage.py` — async SQLite persistence.
- `bms_dashboard/analytics.py` — cumulative energy + efficiency calculations.
- `bms_dashboard/main.py` — FastAPI app exposing live/history/analytics endpoints.

## Quick start

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn bms_dashboard.main:app --reload --host 0.0.0.0 --port 8000
```

By default, the app runs in mock mode (`BMS_USE_MOCK=1`) so you can test quickly.

## Raspberry Pi SPI setup

1. Enable SPI:
   ```bash
   sudo raspi-config
   # Interface Options -> SPI -> Enable
   ```
2. Ensure device nodes exist:
   ```bash
   ls /dev/spidev*
   ```
3. Run with actual SPI instead of mock:
   ```bash
   export BMS_USE_MOCK=0
   uvicorn bms_dashboard.main:app --host 0.0.0.0 --port 8000
   ```

## API endpoints

- `GET /api/live`
  - latest measurement + latest analytics
- `GET /api/history?limit=500`
  - chronological historical measurements
- `GET /api/analytics`
  - latest cumulative charge/discharge energies and round-trip efficiency

## Notes for your BMS protocol

`spi_bms.py` contains a placeholder frame request/decode flow. Replace:

- `read_raw_frame()` command bytes
- `_decode_frame()` scaling/offset logic

with your BMS vendor protocol.
