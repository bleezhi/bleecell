from __future__ import annotations

import asyncio

from .packets import Packet


class BaseStation:
    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 9100,
        core_port: int = 9000,
        cell_id: str = "0001",
    ):
        self.host = host
        self.port = port
        self.core_port = core_port
        self.cell_id = cell_id

    async def handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        core_reader, core_writer = await asyncio.open_connection(self.host, self.core_port)

        async def client_to_core() -> None:
            while data := await reader.readline():
                await self.send(core_writer, Packet.decode(data))

        async def core_to_client() -> None:
            while data := await core_reader.readline():
                writer.write(data)
                await writer.drain()

        try:
            await asyncio.gather(client_to_core(), core_to_client())
        finally:
            core_writer.close()
            await core_writer.wait_closed()
            writer.close()
            await writer.wait_closed()

    @staticmethod
    async def send(writer: asyncio.StreamWriter, packet: Packet) -> None:
        writer.write(packet.encode())
        await writer.drain()

    async def start(self) -> asyncio.AbstractServer:
        return await asyncio.start_server(self.handle, self.host, self.port)
