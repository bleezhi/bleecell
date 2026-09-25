from __future__ import annotations

import asyncio
import math
import struct
from collections import deque


class RtlTcpClient:
    """Minimal RTL-TCP IQ receiver for bleeCELL's Cell tab.

    RTL-TCP sends unsigned interleaved 8-bit I/Q samples:
    I0, Q0, I1, Q1, ...

    This module intentionally treats the stream as an SDR input. It does
    not assume AM, FM, SSB, or any other over-the-air demodulation mode.
    """

    def __init__(
        self,
        host: str = "argon.simtx.net",
        port: int = 1240,
        sample_rate: int = 250_000,
        frequency_hz: int = 1_500_000_000,
    ):
        self.host = host
        self.port = port
        self.sample_rate = sample_rate
        self.frequency_hz = frequency_hz
        self.reader: asyncio.StreamReader | None = None
        self.writer: asyncio.StreamWriter | None = None
        self.running = False
        self._task: asyncio.Task | None = None
        self.samples_received = 0
        self.rms = 0.0
        self.peak = 0.0
        self._level_window: deque[float] = deque(maxlen=64)

    async def connect(self) -> None:
        self.reader, self.writer = await asyncio.open_connection(
            self.host, self.port
        )
        # RTL-TCP command 0x02 sets sample rate, 32-bit big-endian.
        await self._command(0x02, self.sample_rate)
        # RTL-TCP command 0x01 sets center frequency, 32-bit big-endian.
        # This is limited to the protocol's 32-bit frequency field.
        await self._command(0x01, self.frequency_hz)
        self.running = True
        self._task = asyncio.create_task(self._receive_loop())

    async def _command(self, command: int, value: int) -> None:
        if self.writer is None:
            raise RuntimeError("RTL-TCP is not connected")
        self.writer.write(bytes([command]) + struct.pack(">I", int(value)))
        await self.writer.drain()

    async def set_frequency(self, frequency_hz: int) -> None:
        self.frequency_hz = int(frequency_hz)
        if self.writer is not None:
            await self._command(0x01, self.frequency_hz)

    async def set_sample_rate(self, sample_rate: int) -> None:
        self.sample_rate = int(sample_rate)
        if self.writer is not None:
            await self._command(0x02, self.sample_rate)

    async def _receive_loop(self) -> None:
        assert self.reader is not None
        try:
            while self.running:
                data = await self.reader.read(64 * 1024)
                if not data:
                    break
                self.samples_received += len(data) // 2

                # Convert unsigned 8-bit I/Q to centered values and estimate
                # signal level without retaining the whole IQ stream.
                if len(data) >= 2:
                    count = len(data) // 2
                    power_sum = 0.0
                    peak = 0.0
                    for i in range(0, count * 2, 2):
                        iv = (data[i] - 127.5) / 127.5
                        qv = (data[i + 1] - 127.5) / 127.5
                        power = iv * iv + qv * qv
                        power_sum += power
                        peak = max(peak, math.sqrt(power))
                    rms = math.sqrt(power_sum / count)
                    self.rms = rms
                    self.peak = peak
                    self._level_window.append(rms)
        except (ConnectionError, asyncio.IncompleteReadError):
            pass
        finally:
            self.running = False

    @property
    def signal_dbfs(self) -> float:
        if self.rms <= 0:
            return float("-inf")
        return 20.0 * math.log10(min(self.rms, 1.0))

    async def close(self) -> None:
        self.running = False
        if self._task is not None:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        if self.writer is not None:
            self.writer.close()
            await self.writer.wait_closed()
        self.reader = None
        self.writer = None
