from __future__ import annotations

import asyncio
import base64
import queue
import threading
import tkinter as tk
from tkinter import ttk

import numpy as np
import sounddevice as sd

from bleecell.device import Device


class AudioLink:
    RATE = 48000
    BLOCK = 480

    def __init__(self, log):
        self.log = log
        self.input_stream = None
        self.output_stream = None
        self.tx_queue: queue.Queue[bytes] = queue.Queue(maxsize=12)
        self.rx_queue: queue.Queue[np.ndarray] = queue.Queue(maxsize=24)

    @staticmethod
    def inputs():
        return [(i, str(d["name"])) for i, d in enumerate(sd.query_devices())
                if int(d["max_input_channels"]) > 0]

    @staticmethod
    def outputs():
        return [(i, str(d["name"])) for i, d in enumerate(sd.query_devices())
                if int(d["max_output_channels"]) > 0]

    def start(self, input_device, output_device):
        self.stop()
        sd.check_input_settings(device=input_device, samplerate=self.RATE,
                                channels=1, dtype="int16")
        sd.check_output_settings(device=output_device, samplerate=self.RATE,
                                 channels=1, dtype="int16")
        self.input_stream = sd.InputStream(
            samplerate=self.RATE, channels=1, dtype="int16",
            device=input_device, blocksize=self.BLOCK,
            callback=self._input_callback,
        )
        self.output_stream = sd.OutputStream(
            samplerate=self.RATE, channels=1, dtype="int16",
            device=output_device, blocksize=self.BLOCK,
            callback=self._output_callback,
        )
        try:
            self.input_stream.start()
            self.output_stream.start()
        except Exception:
            self.stop()
            raise
        self.log("microphone and speaker started")

    def stop(self):
        for name in ("input_stream", "output_stream"):
            stream = getattr(self, name)
            setattr(self, name, None)
            if stream is not None:
                try:
                    stream.stop()
                finally:
                    stream.close()
        self._clear()

    def _clear(self):
        while True:
            try:
                self.tx_queue.get_nowait()
            except queue.Empty:
                break
        while True:
            try:
                self.rx_queue.get_nowait()
            except queue.Empty:
                break

    def _input_callback(self, indata, frames, _time, status):
        if status:
            self.log(f"audio input: {status}")
        chunk = indata[:, 0].copy().tobytes()
        try:
            self.tx_queue.put_nowait(chunk)
        except queue.Full:
            try:
                self.tx_queue.get_nowait()
                self.tx_queue.put_nowait(chunk)
            except queue.Empty:
                pass

    def _output_callback(self, outdata, frames, _time, status):
        if status:
            self.log(f"audio output: {status}")
        try:
            samples = self.rx_queue.get_nowait()
            count = min(len(samples), frames)
            outdata[:, 0] = 0
            outdata[:count, 0] = samples[:count]
        except queue.Empty:
            outdata.fill(0)

    def pop_tx(self):
        try:
            return self.tx_queue.get_nowait()
        except queue.Empty:
            return None

    def push_rx(self, pcm):
        samples = np.frombuffer(pcm, dtype=np.int16)
        if len(samples) == 0:
            return
        try:
            self.rx_queue.put_nowait(samples.copy())
        except queue.Full:
            try:
                self.rx_queue.get_nowait()
                self.rx_queue.put_nowait(samples.copy())
            except queue.Empty:
                pass


class ClientApp:
    def __init__(self, root):
        self.root = root
        self.root.title("bleeCELL client")
        self.loop = asyncio.new_event_loop()
        threading.Thread(target=self._loop_thread, daemon=True).start()

        self.device = None
        self.audio = AudioLink(self.log)
        self.connected = False
        self.call_active = False
        self.call_target = None

        self._build()

    def _loop_thread(self):
        asyncio.set_event_loop(self.loop)
        self.loop.run_forever()

    def _run(self, coro):
        return asyncio.run_coroutine_threadsafe(coro, self.loop)

    def _build(self):
        main = ttk.Frame(self.root, padding=12)
        main.pack(fill="both", expand=True)

        conn = ttk.LabelFrame(main, text="connection")
        conn.pack(fill="x", pady=(0, 8))

        self.host = tk.StringVar(value="127.0.0.1")
        self.port = tk.StringVar(value="9100")
        self.ue = tk.StringVar(value="UE-CLIENT-01")
        self.key = tk.StringVar(value="client")

        for label, var in (("host", self.host), ("port", self.port),
                           ("ue id", self.ue), ("key", self.key)):
            row = ttk.Frame(conn)
            row.pack(fill="x", pady=2)
            ttk.Label(row, text=label, width=10).pack(side="left")
            ttk.Entry(row, textvariable=var).pack(side="left", fill="x", expand=True)

        self.connect_btn = ttk.Button(conn, text="connect", command=self.connect)
        self.connect_btn.pack(fill="x", pady=(5, 0))

        audio = ttk.LabelFrame(main, text="required audio")
        audio.pack(fill="x", pady=(0, 8))
        self.input_combo = ttk.Combobox(audio, state="readonly")
        self.output_combo = ttk.Combobox(audio, state="readonly")
        self.input_combo.pack(fill="x", pady=2)
        self.output_combo.pack(fill="x", pady=2)
        ttk.Button(audio, text="refresh audio devices",
                   command=self.refresh_audio).pack(fill="x")
        self.audio_status = ttk.Label(
            audio, text="a microphone is required before connecting"
        )
        self.audio_status.pack(anchor="w", pady=(4, 0))

        call = ttk.LabelFrame(main, text="call")
        call.pack(fill="x", pady=(0, 8))
        self.target = tk.StringVar(value="UE-CLIENT-02")
        ttk.Entry(call, textvariable=self.target).pack(fill="x", pady=2)
        buttons = ttk.Frame(call)
        buttons.pack(fill="x")
        ttk.Button(buttons, text="start call",
                   command=self.start_call).pack(side="left", expand=True,
                                                 fill="x", padx=(0, 2))
        ttk.Button(buttons, text="end call",
                   command=self.end_call).pack(side="left", expand=True,
                                               fill="x", padx=(2, 0))
        self.call_status = ttk.Label(call, text="idle")
        self.call_status.pack(anchor="w", pady=(4, 0))

        msg = ttk.LabelFrame(main, text="message")
        msg.pack(fill="x", pady=(0, 8))
        self.message = tk.StringVar()
        ttk.Entry(msg, textvariable=self.message).pack(fill="x")
        ttk.Button(msg, text="send", command=self.send_message).pack(fill="x", pady=2)

        self.log_text = tk.Text(main, height=12, width=70)
        self.log_text.pack(fill="both", expand=True)
        self.refresh_audio()

    def log(self, message):
        self.root.after(
            0,
            lambda: (
                self.log_text.insert("end", message + "\n"),
                self.log_text.see("end"),
            ),
        )

    def refresh_audio(self):
        self.input_devices = AudioLink.inputs()
        self.output_devices = AudioLink.outputs()
        self.input_combo["values"] = [f"{i}: {n}" for i, n in self.input_devices]
        self.output_combo["values"] = [f"{i}: {n}" for i, n in self.output_devices]
        if self.input_devices:
            self.input_combo.current(0)
        if self.output_devices:
            self.output_combo.current(0)

    def _selected(self, combo, devices):
        index = combo.current()
        if index < 0 or index >= len(devices):
            return None
        return devices[index][0]

    def connect(self):
        if not self.input_devices:
            self.audio_status.config(text="no microphone/input device found")
            return

        input_device = self._selected(self.input_combo, self.input_devices)
        output_device = self._selected(self.output_combo, self.output_devices)
        if input_device is None or output_device is None:
            self.audio_status.config(text="select both microphone and speaker")
            return

        try:
            self.audio.start(input_device, output_device)
        except Exception as exc:
            self.audio_status.config(text=f"audio error: {exc}")
            self.log(f"audio error: {exc}")
            return

        try:
            port = int(self.port.get())
        except ValueError:
            self.audio.stop()
            self.audio_status.config(text="invalid port")
            return

        self.device = Device(self.ue.get().strip(), self.key.get(),
                             self.host.get().strip(), port)
        self._run(self._connect_async())

    async def _connect_async(self):
        try:
            await self.device.connect()
            await self.device.register()
            await self.device.authenticate()
            self.connected = True
            self.log(f"connected and authenticated as {self.device.ue_id}")
            self.root.after(
                0, lambda: self.connect_btn.config(text="connected", state="disabled")
            )
            asyncio.create_task(self._receive_loop())
            asyncio.create_task(self._audio_send_loop())
        except Exception as exc:
            self.connected = False
            self.audio.stop()
            self.log(f"connection failed: {exc}")
            self.root.after(
                0, lambda: self.audio_status.config(text=f"connection failed: {exc}")
            )

    async def _receive_loop(self):
        try:
            while self.device:
                packet = await self.device.receive()

                if packet.kind == "AUDIO" and self.call_active:
                    encoded = packet.payload.get("data", "")
                    self.audio.push_rx(base64.b64decode(encoded))

                elif packet.kind == "CALL":
                    self.call_target = packet.sender
                    self.call_active = True
                    self.root.after(
                        0,
                        lambda: self.call_status.config(
                            text=f"in call with {self.call_target}"
                        ),
                    )
                    self.log(f"incoming call from {packet.sender}")

                elif packet.kind == "CALL_END":
                    self.call_active = False
                    self.root.after(0, lambda: self.call_status.config(text="call ended"))
                    self.log("call ended")

                elif packet.kind == "DATA":
                    self.log(f"{packet.sender}: {packet.payload.get('text', '')}")

                elif packet.kind in {"CALL_SENT", "CALL_END_OK", "DATA_SENT"}:
                    self.log(packet.kind)

                elif packet.kind == "ERROR":
                    self.log(f"network error: {packet.payload.get('reason', '')}")

        except Exception as exc:
            self.connected = False
            self.log(f"receive loop stopped: {exc}")

    async def _audio_send_loop(self):
        while self.connected and self.device:
            if self.call_active and self.call_target:
                pcm = self.audio.pop_tx()
                if pcm:
                    await self.device.send_audio(self.call_target, pcm)
            else:
                await asyncio.sleep(0.01)
            await asyncio.sleep(0.005)

    def start_call(self):
        if not self.connected or not self.device:
            self.log("connect first")
            return

        target = self.target.get().strip()
        if not target or target == self.device.ue_id:
            self.log("invalid call target")
            return

        self.call_target = target
        self.call_active = True
        self.call_status.config(text=f"calling {target}")
        self._run(self.device.call(target))

    def end_call(self):
        if not self.device or not self.call_target:
            return
        target = self.call_target
        self.call_active = False
        self._run(self.device.end_call(target))
        self.call_status.config(text="idle")
        self.log(f"ended call with {target}")

    def send_message(self):
        if not self.connected or not self.device:
            self.log("connect first")
            return
        target = self.target.get().strip()
        message = self.message.get()
        if not target or not message:
            return
        self._run(self.device.message(target, message))
        self.message.set("")


def main():
    root = tk.Tk()
    ClientApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
