from __future__ import annotations

import asyncio

from .packets import Packet


class Device:
    def __init__(self, ue_id: str, key: str, host: str = "127.0.0.1", port: int = 9100):
        self.ue_id = ue_id
        self.key = key
        self.host = host
        self.port = port
        self.reader: asyncio.StreamReader | None = None
        self.writer: asyncio.StreamWriter | None = None

    async def connect(self) -> None:
        self.reader, self.writer = await asyncio.open_connection(self.host, self.port)

    async def send(self, packet: Packet) -> None:
        assert self.writer is not None
        self.writer.write(packet.encode())
        await self.writer.drain()

    async def register(self) -> None:
        await self.send(Packet("REGISTER", self.ue_id, payload={"key": self.key}))
        await self.expect("REGISTER_OK")

    async def authenticate(self) -> None:
        await self.send(Packet("AUTH", self.ue_id, payload={"key": self.key}))
        await self.expect("AUTH_OK")

    async def message(self, recipient: str, text: str) -> None:
        await self.send(Packet("DATA", self.ue_id, recipient, {"text": text}))

    async def receive(self) -> Packet:
        assert self.reader is not None
        return Packet.decode(await self.reader.readline())

    async def expect(self, kind: str) -> Packet:
        packet = await self.receive()
        if packet.kind != kind:
            raise RuntimeError(f"expected {kind}, got {packet.kind}")
        return packet
