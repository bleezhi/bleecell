from __future__ import annotations

from .basestation import BaseStation
from .core import CoreNetwork


class BleeCellNetwork:
    def __init__(self, core_port: int = 9000, cell_port: int = 9100):
        self.core = CoreNetwork(port=core_port)
        self.base_station = BaseStation(port=cell_port, core_port=core_port)

    async def start(self):
        core_server = await self.core.start()
        base_server = await self.base_station.start()
        return core_server, base_server
