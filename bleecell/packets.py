from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any


@dataclass
class Packet:
    kind: str
    sender: str
    recipient: str | None = None
    payload: dict[str, Any] | None = None

    def encode(self) -> bytes:
        data = asdict(self)
        return (json.dumps(data, separators=(",", ":")) + "\n").encode()

    @classmethod
    def decode(cls, data: bytes) -> "Packet":
        obj = json.loads(data.decode())
        return cls(**obj)
