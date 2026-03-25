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


class BMSReader:
    """Reads measurements from a SPI-connected BMS.

    Protocol decoding can vary by BMS vendor. The `read_raw_frame` and
    `_decode_frame` methods provide a clear seam for custom implementations.
    """

    def __init__(self, config: SPIConfig | None = None, use_mock: bool = False):
        self.config = config or SPIConfig()
        self.use_mock = use_mock
        self._spi = None

    def open(self) -> None:
        if self.use_mock:
            return
        if spidev is None:
            raise RuntimeError(
                "spidev is not installed; either install it on Raspberry Pi or run with mock mode."
            )
        self._spi = spidev.SpiDev()
        self._spi.open(self.config.bus, self.config.device)
        self._spi.max_speed_hz = self.config.max_speed_hz
        self._spi.mode = self.config.mode

    def close(self) -> None:
        if self._spi is not None:
            self._spi.close()
            self._spi = None

    def read_raw_frame(self) -> list[int]:
        if self.use_mock:
            return [
                random.randint(480, 540),
                random.randint(-120, 120),
                random.randint(20, 100),
                random.randint(15, 45),
            ]
        if self._spi is None:
            raise RuntimeError("SPI bus not open")
        # Replace with BMS-specific frame request/response.
        return self._spi.xfer2([0xAA, 0x55, 0x00, 0x00])

    def _decode_frame(self, frame: list[int]) -> Measurement:
        # Placeholder decoder. Replace scaling/offset with your BMS protocol.
        voltage_v = frame[0] / 10.0
        current_a = frame[1] / 10.0
        soc_pct = float(frame[2])
        temperature_c = float(frame[3])
        return Measurement(
            timestamp=datetime.utcnow(),
            voltage_v=voltage_v,
            current_a=current_a,
            soc_pct=soc_pct,
            temperature_c=temperature_c,
        )

    def read_measurement(self) -> Measurement:
        return self._decode_frame(self.read_raw_frame())
