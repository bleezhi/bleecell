from __future__ import annotations

import math
import threading
from array import array


class AudioOutput:
    def __init__(self) -> None:
        try:
            import sounddevice as sd
        except ImportError as exc:
            raise RuntimeError("audio support requires the 'sounddevice' package") from exc
        self.sd = sd

    def outputs(self) -> list[tuple[int, str]]:
        return [
            (i, str(d["name"]))
            for i, d in enumerate(self.sd.query_devices())
            if int(d["max_output_channels"]) > 0
        ]

    def play_tone(self, device: int | None = None, frequency: float = 440.0, seconds: float = 0.5) -> None:
        rate = 48000
        frames = int(rate * seconds)
        samples = array("f", (
            0.15 * math.sin(2 * math.pi * frequency * n / rate)
            for n in range(frames)
        ))
        self.sd.play(samples, samplerate=rate, device=device, blocking=False)
