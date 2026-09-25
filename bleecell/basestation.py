from __future__ import annotations

import asyncio

from .packets import Packet


class BaseStation:
    def __init__(self, host: str = "127.0.0.1", port: int = 9100, core_port: int = 9000, cell_id: str = "0001"):
        self.host = host
        self.port = port
        self.core_port = core_port
        self.cell_id = cell_id

    async def handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        core_reader, core_writer = await asyncio.open_connection(self.host, self.core_port)
        try:
            while data := await reader.readline():
                packet = Packet.decode(data)
                await self.send(core_writer, packet)

                response = await core_reader.readline()
                if response:
                    writer.write(response)
                    await writer.drain()
        finally:
            core_writer.close()
            await core_writer.wait_closed()
            writer.close()
            await writer.wait_closed()

    async def send(self, writer: asyncio.StreamWriter, packet: Packet) -> None:
        writer.write(packet.encode())
        await writer.drain()

    async def start(self) -> asyncio.AbstractServer:
        return await asyncio.start_server(self.handle, self.host, self.port)
