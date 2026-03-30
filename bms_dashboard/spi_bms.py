from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime

try:
    import spidev
except ImportError:  # pragma: no cover - enabled on non-rPi development hosts
    spidev = None

from .models import Measurement


@dataclass
class SPIConfig:
    bus: int = 0
    device: int = 0
    max_speed_hz: int = 500_000
    mode: int = 0


@dataclass
class L99BM114Config:
    device_id: int = 0
    # Register addresses below are placeholders to demonstrate flow.
    # Replace with exact map from your firmware/data-sheet revision.
    reg_pack_voltage: int = 0x10
    reg_current: int = 0x11
    reg_soc: int = 0x12
    reg_temp: int = 0x13
    reg_cell_base: int = 0x20
    cell_count: int = 14


class L99BM114Protocol:
    """Minimal protocol helper for L99BM114 40-bit SPI transfers.

    NOTE: Validate exact bit layout against your datasheet/user manual revision.
    This implementation provides a maintainable seam for integrating real
    register reads over the STEVAL-BMS1T isolated SPI bridge.
    """

    @staticmethod
    def crc8(data: bytes, poly: int = 0x07, init: int = 0x00) -> int:
        crc = init
        for b in data:
            crc ^= b
            for _ in range(8):
                crc = ((crc << 1) ^ poly) & 0xFF if (crc & 0x80) else (crc << 1) & 0xFF
        return crc

    def build_read_frame(self, device_id: int, reg_addr: int) -> list[int]:
        # Frame skeleton: [cmd, dev, addr, 0x00, crc]
        frame_wo_crc = bytes([0x80, device_id & 0x0F, reg_addr & 0xFF, 0x00])
        return list(frame_wo_crc + bytes([self.crc8(frame_wo_crc)]))

    def decode_read_response(self, response: list[int]) -> int:
        if len(response) != 5:
            raise ValueError(f"Unexpected L99BM114 response length: {len(response)}")
        payload = bytes(response[:4])
        crc = response[4]
        if self.crc8(payload) != crc:
            raise ValueError("CRC mismatch in SPI response")
        return payload[3]


class BMSReader:
    """Reads measurements from a SPI-connected L99BM114-based board."""

    def __init__(
        self,
        spi_config: SPIConfig | None = None,
        bms_config: L99BM114Config | None = None,
        use_mock: bool = False,
    ):
        self.spi_config = spi_config or SPIConfig()
        self.bms_config = bms_config or L99BM114Config()
        self.use_mock = use_mock
        self._spi = None
        self._protocol = L99BM114Protocol()

    def open(self) -> None:
        if self.use_mock:
            return
        if spidev is None:
            raise RuntimeError(
                "spidev is not installed; install it on Raspberry Pi or run in BMS_USE_MOCK=1 mode."
            )
        self._spi = spidev.SpiDev()
        self._spi.open(self.spi_config.bus, self.spi_config.device)
        self._spi.max_speed_hz = self.spi_config.max_speed_hz
        self._spi.mode = self.spi_config.mode

    def close(self) -> None:
        if self._spi is not None:
            self._spi.close()
            self._spi = None

    def _read_register(self, reg_addr: int) -> int:
        if self._spi is None:
            raise RuntimeError("SPI bus not open")
        req = self._protocol.build_read_frame(self.bms_config.device_id, reg_addr)
        resp = self._spi.xfer2(req)
        return self._protocol.decode_read_response(resp)

    def _read_register_scaled(self, reg_addr: int, scale: float, offset: float = 0.0) -> float:
        return self._read_register(reg_addr) * scale + offset

    def read_measurement(self) -> Measurement:
        if self.use_mock:
            cell_voltages = [round(random.uniform(3.35, 3.80), 3) for _ in range(self.bms_config.cell_count)]
            return Measurement(
                timestamp=datetime.utcnow(),
                pack_voltage_v=round(sum(cell_voltages), 3),
                current_a=round(random.uniform(-12, 18), 2),
                soc_pct=round(random.uniform(20, 100), 1),
                temperature_c=round(random.uniform(18, 42), 1),
                cell_voltages_v=cell_voltages,
            )

        cell_voltages = [
            self._read_register_scaled(self.bms_config.reg_cell_base + idx, scale=0.01)
            for idx in range(self.bms_config.cell_count)
        ]
        pack_voltage_v = self._read_register_scaled(self.bms_config.reg_pack_voltage, scale=0.1)
        current_a = self._read_register_scaled(self.bms_config.reg_current, scale=0.1, offset=-12.8)
        soc_pct = self._read_register_scaled(self.bms_config.reg_soc, scale=0.5)
        temperature_c = self._read_register_scaled(self.bms_config.reg_temp, scale=1.0, offset=-40.0)

        return Measurement(
            timestamp=datetime.utcnow(),
            pack_voltage_v=pack_voltage_v,
            current_a=current_a,
            soc_pct=soc_pct,
            temperature_c=temperature_c,
            cell_voltages_v=cell_voltages,
        )
