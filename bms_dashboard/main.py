from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager, suppress
from dataclasses import asdict
from datetime import datetime

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from .analytics import EnergyAccumulator
from .models import AnalyticsSnapshot, FaultState, Measurement, MeasurementWithAnalytics
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
FAIL_RETRY_BASE_SEC = float(os.getenv("BMS_RETRY_BASE_SEC", "1.0"))
FAIL_RETRY_MAX_SEC = float(os.getenv("BMS_RETRY_MAX_SEC", "10.0"))

engine = make_engine(os.getenv("BMS_DB_PATH", "data/bms.db"))
SessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
reader = BMSReader(use_mock=USE_MOCK)
accumulator = EnergyAccumulator()
latest_measurement: Measurement | None = None
latest_analytics = AnalyticsSnapshot()
latest_fault = FaultState()
logger = logging.getLogger("bms_dashboard")


async def poll_bms_loop() -> None:
    global latest_measurement, latest_analytics, latest_fault
    reader.open()
    consecutive_failures = 0
    try:
        while True:
            try:
                m = reader.read_measurement()
                latest_measurement = m
                latest_analytics = accumulator.update(m)
                async with SessionLocal() as session:
                    await insert_measurement(session, m)
                consecutive_failures = 0
                latest_fault = FaultState(status="ok", consecutive_failures=0, updated_at=datetime.utcnow())
                await asyncio.sleep(POLL_INTERVAL_SEC)
            except Exception as exc:
                consecutive_failures += 1
                sleep_s = min(FAIL_RETRY_BASE_SEC * (2 ** (consecutive_failures - 1)), FAIL_RETRY_MAX_SEC)
                latest_fault = FaultState(
                    status="degraded",
                    consecutive_failures=consecutive_failures,
                    last_error=str(exc),
                    updated_at=datetime.utcnow(),
                )
                logger.warning(
                    "bms_poll_failure",
                    extra={
                        "consecutive_failures": consecutive_failures,
                        "retry_backoff_sec": sleep_s,
                        "error": str(exc),
                    },
                )
                await asyncio.sleep(sleep_s)
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


@app.get("/", response_class=HTMLResponse)
async def dashboard() -> str:
    return """
<!doctype html>
<html>
  <head>
    <meta charset=\"utf-8\" />
    <title>BMS Dashboard</title>
    <script src=\"https://cdn.jsdelivr.net/npm/chart.js\"></script>
    <style>
      body { font-family: Arial, sans-serif; margin: 24px; background: #0f172a; color: #e2e8f0; }
      .cards { display:grid; grid-template-columns:repeat(4,minmax(160px,1fr)); gap:12px; }
      .card { background:#1e293b; padding:14px; border-radius:10px; }
      .label { color:#94a3b8; font-size:12px; }
      .value { font-size:24px; font-weight:600; }
      .chart { background:#1e293b; padding:16px; border-radius:10px; margin-top:14px; }
    </style>
  </head>
  <body>
    <h2>L99BM114 BMS Dashboard (SPI via STEVAL-BMS1T)</h2>
    <div class=\"cards\">
      <div class=\"card\"><div class=\"label\">Pack Voltage</div><div class=\"value\" id=\"packV\">--</div></div>
      <div class=\"card\"><div class=\"label\">Current</div><div class=\"value\" id=\"current\">--</div></div>
      <div class=\"card\"><div class=\"label\">SOC</div><div class=\"value\" id=\"soc\">--</div></div>
      <div class=\"card\"><div class=\"label\">Efficiency</div><div class=\"value\" id=\"eff\">--</div></div>
    </div>

    <div class=\"chart\"><canvas id=\"hist\"></canvas></div>
    <div class=\"chart\"><canvas id=\"cells\"></canvas></div>

    <script>
      const ctx = document.getElementById('hist').getContext('2d');
      const chart = new Chart(ctx, {
        type: 'line',
        data: { labels: [], datasets: [
          {label:'Pack Voltage (V)', data:[], borderColor:'#22d3ee'},
          {label:'Current (A)', data:[], borderColor:'#f97316'}
        ] },
        options: { animation:false, scales:{x:{ticks:{color:'#cbd5e1'}}, y:{ticks:{color:'#cbd5e1'}}}, plugins:{legend:{labels:{color:'#e2e8f0'}}}}
      });

      const cctx = document.getElementById('cells').getContext('2d');
      const cellChart = new Chart(cctx, {
        type: 'bar',
        data: { labels: [], datasets: [{ label: 'Cell Voltage (V)', data: [], backgroundColor: '#34d399' }] },
        options: {
          animation: false,
          scales: {
            x: { ticks: { color: '#cbd5e1' } },
            y: { ticks: { color: '#cbd5e1' }, suggestedMin: 2.5, suggestedMax: 4.3 }
          },
          plugins: { legend: { labels: { color: '#e2e8f0' } } }
        }
      });

      function clamp(v, lo, hi) {
        return Math.max(lo, Math.min(hi, v));
      }

      async function refreshLive() {
        const r = await fetch('/api/live');
        const data = await r.json();
        const eff = clamp(data.analytics.round_trip_efficiency_pct, 0, 100);
        document.getElementById('packV').textContent = `${data.measurement.pack_voltage_v.toFixed(2)} V`;
        document.getElementById('current').textContent = `${data.measurement.current_a.toFixed(2)} A`;
        document.getElementById('soc').textContent = `${data.measurement.soc_pct.toFixed(1)} %`;
        document.getElementById('eff').textContent = `${eff.toFixed(1)} %`;

        const cells = data.measurement.cell_voltages_v || [];
        cellChart.data.labels = cells.map((_, i) => `Cell ${i + 1}`);
        cellChart.data.datasets[0].data = cells;
        cellChart.update();
      }

      async function refreshHistory() {
        const r = await fetch('/api/history?limit=120');
        const rows = await r.json();
        chart.data.labels = rows.map(x => x.timestamp.substring(11,19));
        chart.data.datasets[0].data = rows.map(x => x.pack_voltage_v);
        chart.data.datasets[1].data = rows.map(x => x.current_a);
        chart.update();
      }

      async function tick() {
        await Promise.all([refreshLive(), refreshHistory()]);
      }

      tick();
      setInterval(tick, 2000);
    </script>
  </body>
</html>
"""


@app.get("/api/live")
async def api_live() -> dict:
    if latest_measurement is None:
        return asdict(MeasurementWithAnalytics(measurement=Measurement(), analytics=latest_analytics, fault=latest_fault))
    return asdict(MeasurementWithAnalytics(measurement=latest_measurement, analytics=latest_analytics, fault=latest_fault))


@app.get("/api/history")
async def api_history(limit: int = 500) -> list[dict]:
    async with SessionLocal() as session:
        rows = await get_measurements(session, limit=limit)
    return [asdict(r) for r in rows]


@app.get("/api/analytics")
async def api_analytics() -> dict:
    return asdict(latest_analytics)
