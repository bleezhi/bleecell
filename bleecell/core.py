from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from .cell import WidebandCell
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
    cell: WidebandCell = field(default_factory=WidebandCell)

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
                    self.cell.attach(ue_id)
                    await self.send(writer, Packet("REGISTER_OK", "CORE", ue_id, {"radio": self.cell.snapshot()}))

                elif packet.kind == "AUTH":
                    sub = self.subscribers.get(packet.sender)
                    ok = sub is not None and packet.payload.get("key") == sub.key
                    if sub:
                        sub.authenticated = ok
                    await self.send(writer, Packet("AUTH_OK" if ok else "AUTH_FAIL", "CORE", packet.sender))

                elif packet.kind == "RADIO_INFO":
                    await self.send(writer, Packet("RADIO_INFO", "CORE", packet.sender, self.cell.snapshot()))

                elif packet.kind in {"CALL", "CALL_END"}:
                    sub = self.subscribers.get(packet.sender)
                    if not sub or not sub.authenticated:
                        await self.send(writer, Packet("ERROR", "CORE", packet.sender, {"reason": "not authenticated"}))
                        continue

                    target_id = packet.recipient or ""
                    target = self.devices.get(target_id)
                    if target is None:
                        await self.send(writer, Packet("ERROR", "CORE", packet.sender, {"reason": "device unavailable"}))
                        continue

                    await self.send(target, packet)
                    if packet.kind == "CALL":
                        await self.send(writer, Packet("CALL_SENT", "CORE", packet.sender, {"target": target_id}))
                    else:
                        await self.send(writer, Packet("CALL_END_OK", "CORE", packet.sender, {"target": target_id}))

                elif packet.kind in {"DATA", "AUDIO"}:
                    sub = self.subscribers.get(packet.sender)
                    if not sub or not sub.authenticated:
                        await self.send(writer, Packet("ERROR", "CORE", packet.sender, {"reason": "not authenticated"}))
                        continue

                    target_id = packet.recipient or ""
                    target = self.devices.get(target_id)
                    if target is None:
                        await self.send(writer, Packet("ERROR", "CORE", packet.sender, {"reason": "device unavailable"}))
                        continue

                    payload = packet.payload or {}
                    byte_count = len(payload.get("data", "").encode()) if packet.kind == "AUDIO" else len(payload.get("text", "").encode())
                    self.cell.account(packet.sender, "up", byte_count)
                    self.cell.account(target_id, "down", byte_count)
                    await self.send(target, packet)

                    if packet.kind == "DATA":
                        await self.send(writer, Packet("DATA_SENT", "CORE", packet.sender, {"target": target_id, "radio": self.cell.snapshot()}))

        finally:
            for ue_id, connection in list(self.devices.items()):
                if connection is writer:
                    del self.devices[ue_id]
                    self.cell.detach(ue_id)
            writer.close()
            await writer.wait_closed()

    @staticmethod
    async def send(writer: asyncio.StreamWriter, packet: Packet) -> None:
        writer.write(packet.encode())
        await writer.drain()

    async def start(self) -> asyncio.AbstractServer:
        return await asyncio.start_server(self.handle, self.host, self.port)
