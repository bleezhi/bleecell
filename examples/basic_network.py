from __future__ import annotations

import asyncio

from bleecell.device import Device
from bleecell.network import BleeCellNetwork


async def main() -> None:
    network = BleeCellNetwork()

    network.core.add_subscriber("UE-0001", "key-one")
    network.core.add_subscriber("UE-0002", "key-two")

    core_server, base_server = await network.start()

    ue1 = Device("UE-0001", "key-one")
    ue2 = Device("UE-0002", "key-two")

    await ue1.connect()
    await ue2.connect()

    await ue1.register()
    await ue2.register()
    await ue1.authenticate()
    await ue2.authenticate()

    await ue1.message("UE-0002", "hello from bleeCELL")

    packet = await ue2.receive()
    print(f"{packet.sender} -> {packet.recipient}: {packet.payload['text']}")

    core_server.close()
    base_server.close()
    await core_server.wait_closed()
    await base_server.wait_closed()


if __name__ == "__main__":
    asyncio.run(main())
