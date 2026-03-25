from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Iterable

from sqlalchemy import DateTime, Float, Integer, select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from .models import Measurement


class Base(DeclarativeBase):
    pass


class MeasurementRow(Base):
    __tablename__ = "measurements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, index=True)
    voltage_v: Mapped[float] = mapped_column(Float)
    current_a: Mapped[float] = mapped_column(Float)
    soc_pct: Mapped[float] = mapped_column(Float)
    temperature_c: Mapped[float] = mapped_column(Float)


def make_engine(db_path: str = "data/bms.db"):
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    return create_async_engine(f"sqlite+aiosqlite:///{db_path}", future=True)


async def init_db(session_factory: async_sessionmaker[AsyncSession]) -> None:
    engine = session_factory.kw["bind"]
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def insert_measurement(session: AsyncSession, m: Measurement) -> None:
    session.add(
        MeasurementRow(
            timestamp=m.timestamp,
            voltage_v=m.voltage_v,
            current_a=m.current_a,
            soc_pct=m.soc_pct,
            temperature_c=m.temperature_c,
        )
    )
    await session.commit()


async def get_measurements(
    session: AsyncSession,
    limit: int = 500,
) -> Iterable[Measurement]:
    q = select(MeasurementRow).order_by(MeasurementRow.timestamp.desc()).limit(limit)
    rows = (await session.execute(q)).scalars().all()
    return [
        Measurement(
            timestamp=r.timestamp,
            voltage_v=r.voltage_v,
            current_a=r.current_a,
            soc_pct=r.soc_pct,
            temperature_c=r.temperature_c,
        )
        for r in reversed(rows)
    ]
