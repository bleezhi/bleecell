from __future__ import annotations

import math
import threading

import numpy as np


class AudioOutput:
    """Continuous software audio output for the simulator."""

    def __init__(self) -> None:
        try:
            import sounddevice as sd
        except ImportError as exc:
            raise RuntimeError("audio support requires the 'sounddevice' package") from exc
        self.sd = sd
        self.rate = 48000
        self.channels = 1
        self._stream = None
        self._device: int | None = None
        self._lock = threading.Lock()
        self._phase = 0.0
        self._event_phase = 0.0
        self._event_frequency = 0.0
        self._event_level = 0.0
        self._event_remaining = 0

    def outputs(self) -> list[tuple[int, str]]:
        return [
            (i, str(d["name"]))
            for i, d in enumerate(self.sd.query_devices())
            if int(d["max_output_channels"]) > 0
        ]

    def _callback(self, outdata, frames, _time, status) -> None:
        if status:
            pass
        with self._lock:
            event_frequency = self._event_frequency
            event_level = self._event_level
            event_remaining = self._event_remaining

        idle_frequency = 220.0
        idle_level = 0.025
        samples = np.empty(frames, dtype=np.float32)

        for i in range(frames):
            idle = idle_level * math.sin(2 * math.pi * self._phase)
            self._phase = (self._phase + idle_frequency / self.rate) % 1.0

            event = 0.0
            if event_remaining > 0 and event_frequency:
                event = event_level * math.sin(2 * math.pi * self._event_phase)
                self._event_phase = (self._event_phase + event_frequency / self.rate) % 1.0
                event_remaining -= 1

            samples[i] = idle + event

        with self._lock:
            self._event_remaining = event_remaining

        outdata[:, 0] = samples
        if outdata.shape[1] > 1:
            outdata[:, 1:] = samples[:, None]

    def start(self, device: int) -> None:
        self.stop()
        self._device = device
        try:
            self._stream = self.sd.OutputStream(
                samplerate=self.rate,
                channels=self.channels,
                dtype="float32",
                device=device,
                callback=self._callback,
                blocksize=960,
            )
            self._stream.start()
        except Exception:
            self._stream = None
            self._device = None
            raise

    def stop(self) -> None:
        stream = self._stream
        self._stream = None
        if stream is not None:
            stream.stop()
            stream.close()
        self._device = None

    def is_running(self) -> bool:
        return self._stream is not None

    def event(self, frequency: float, seconds: float = 0.12, level: float = 0.10) -> None:
        with self._lock:
            self._event_frequency = frequency
            self._event_level = level
            self._event_phase = 0.0
            self._event_remaining = max(1, int(self.rate * seconds))

    def play_tone(self, device: int | None = None, frequency: float = 440.0, seconds: float = 0.5) -> None:
        if device is not None and (not self.is_running() or self._device != device):
            self.start(device)
        if not self.is_running():
            raise RuntimeError("select an audio output first")
        self.event(frequency, seconds, 0.15)
