from __future__ import annotations

import asyncio
import os
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI

from .analytics import EnergyAccumulator
from .models import AnalyticsSnapshot, Measurement, MeasurementWithAnalytics
from .spi_bms import BMSReader
from .storage import (
    AsyncSession,
    async_sessionmaker,
    get_measurements,
    init_db,
    insert_measurement,
    make_engine,
)

POLL_INTERVAL_SEC = float(os.getenv("BMS_POLL_INTERVAL_SEC", "1.0"))
USE_MOCK = os.getenv("BMS_USE_MOCK", "1") == "1"

engine = make_engine(os.getenv("BMS_DB_PATH", "data/bms.db"))
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
reader = BMSReader(use_mock=USE_MOCK)
accumulator = EnergyAccumulator()
latest_measurement: Measurement | None = None
latest_analytics = AnalyticsSnapshot(
    total_charge_energy_wh=0.0,
    total_discharge_energy_wh=0.0,
    round_trip_efficiency_pct=0.0,
)


async def poll_bms_loop() -> None:
    global latest_measurement, latest_analytics
    reader.open()
    try:
        while True:
            m = reader.read_measurement()
            latest_measurement = m
            latest_analytics = accumulator.update(m)
            async with SessionLocal() as session:
                await insert_measurement(session, m)
            await asyncio.sleep(POLL_INTERVAL_SEC)
    finally:
        reader.close()


@asynccontextmanager
async def lifespan(_: FastAPI):
    await init_db(SessionLocal)
    task = asyncio.create_task(poll_bms_loop())
    try:
        yield
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task


app = FastAPI(title="BMS Dashboard API", lifespan=lifespan)


@app.get("/api/live", response_model=MeasurementWithAnalytics)
async def api_live() -> MeasurementWithAnalytics:
    if latest_measurement is None:
        return MeasurementWithAnalytics(
            measurement=Measurement(voltage_v=0, current_a=0, soc_pct=0, temperature_c=0),
            analytics=latest_analytics,
        )
    return MeasurementWithAnalytics(measurement=latest_measurement, analytics=latest_analytics)


@app.get("/api/history", response_model=list[Measurement])
async def api_history(limit: int = 500) -> list[Measurement]:
    async with SessionLocal() as session:
        rows = await get_measurements(session, limit=limit)
    return list(rows)


@app.get("/api/analytics", response_model=AnalyticsSnapshot)
async def api_analytics() -> AnalyticsSnapshot:
    return latest_analytics
