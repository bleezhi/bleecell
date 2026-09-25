from __future__ import annotations

import math
import time
from dataclasses import dataclass, field


@dataclass
class RadioBearer:
    ue_id: str
    bandwidth_hz: float = 0.0
    downlink_bps: float = 0.0
    uplink_bps: float = 0.0
    bytes_down: int = 0
    bytes_up: int = 0


@dataclass
class WidebandCell:
    """Software-only wideband cellular resource model.

    This models spectrum and scheduler capacity; it does not generate RF.
    """
    cell_id: str = "0001"
    center_frequency_hz: int = 3_500_000_000
    bandwidth_hz: int = 100_000_000
    subcarrier_spacing_hz: int = 30_000
    spectral_efficiency: float = 4.5
    bearers: dict[str, RadioBearer] = field(default_factory=dict)
    last_schedule: float = field(default_factory=time.monotonic)

    @property
    def resource_blocks(self) -> int:
        # 5G NR-style approximation for a 100 MHz / 30 kHz channel.
        return max(1, int(self.bandwidth_hz / (12 * self.subcarrier_spacing_hz)))

    @property
    def theoretical_bps(self) -> float:
        return self.bandwidth_hz * self.spectral_efficiency

    def attach(self, ue_id: str) -> RadioBearer:
        bearer = self.bearers.setdefault(ue_id, RadioBearer(ue_id))
        self.schedule()
        return bearer

    def detach(self, ue_id: str) -> None:
        self.bearers.pop(ue_id, None)
        self.schedule()

    def schedule(self) -> None:
        if not self.bearers:
            return
        share = self.bandwidth_hz / len(self.bearers)
        rate = self.theoretical_bps / len(self.bearers)
        for bearer in self.bearers.values():
            bearer.bandwidth_hz = share
            bearer.downlink_bps = rate
            bearer.uplink_bps = rate
        self.last_schedule = time.monotonic()

    def account(self, ue_id: str, direction: str, byte_count: int) -> None:
        bearer = self.bearers.get(ue_id)
        if bearer is None:
            return
        if direction == "up":
            bearer.bytes_up += byte_count
        else:
            bearer.bytes_down += byte_count

    def snapshot(self) -> dict:
        self.schedule()
        return {
            "cell_id": self.cell_id,
            "center_frequency_hz": self.center_frequency_hz,
            "bandwidth_hz": self.bandwidth_hz,
            "bandwidth_mhz": self.bandwidth_hz / 1_000_000,
            "resource_blocks": self.resource_blocks,
            "theoretical_bps": self.theoretical_bps,
            "theoretical_mbps": self.theoretical_bps / 1_000_000,
            "ues": {
                ue: {
                    "bandwidth_hz": b.bandwidth_hz,
                    "bandwidth_mhz": b.bandwidth_hz / 1_000_000,
                    "downlink_bps": b.downlink_bps,
                    "uplink_bps": b.uplink_bps,
                    "downlink_mbps": b.downlink_bps / 1_000_000,
                    "uplink_mbps": b.uplink_bps / 1_000_000,
                    "bytes_down": b.bytes_down,
                    "bytes_up": b.bytes_up,
                }
                for ue, b in self.bearers.items()
            },
        }
