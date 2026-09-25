from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from .packets import Packet


@dataclass
class Subscriber:
    ue_id: str
    key: str
    authenticated: bool = False


@dataclass
class CoreNetwork:
    host: str = "127.0.0.1"
    port: int = 9000
    subscribers: dict[str, Subscriber] = field(default_factory=dict)
    devices: dict[str, asyncio.StreamWriter] = field(default_factory=dict)

    def add_subscriber(self, ue_id: str, key: str) -> None:
        self.subscribers[ue_id] = Subscriber(ue_id, key)

    async def handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            while data := await reader.readline():
                packet = Packet.decode(data)

                if packet.kind == "REGISTER":
                    ue_id = packet.sender
                    if ue_id not in self.subscribers:
                        self.add_subscriber(ue_id, packet.payload.get("key", ""))
                    self.devices[ue_id] = writer
                    await self.send(writer, Packet("REGISTER_OK", "CORE", ue_id))

                elif packet.kind == "AUTH":
                    sub = self.subscribers.get(packet.sender)
                    ok = sub is not None and packet.payload.get("key") == sub.key
                    if sub:
                        sub.authenticated = ok
                    await self.send(writer, Packet("AUTH_OK" if ok else "AUTH_FAIL", "CORE", packet.sender))

                elif packet.kind == "DATA":
                    sub = self.subscribers.get(packet.sender)
                    if not sub or not sub.authenticated:
                        await self.send(writer, Packet("ERROR", "CORE", packet.sender, {"reason": "not authenticated"}))
                        continue

                    target = self.devices.get(packet.recipient or "")
                    if target is None:
                        await self.send(writer, Packet("ERROR", "CORE", packet.sender, {"reason": "device unavailable"}))
                        continue

                    await self.send(target, packet)
        finally:
            for ue_id, connection in list(self.devices.items()):
                if connection is writer:
                    del self.devices[ue_id]
            writer.close()
            await writer.wait_closed()

    @staticmethod
    async def send(writer: asyncio.StreamWriter, packet: Packet) -> None:
        writer.write(packet.encode())
        await writer.drain()

    async def start(self) -> asyncio.AbstractServer:
        return await asyncio.start_server(self.handle, self.host, self.port)
