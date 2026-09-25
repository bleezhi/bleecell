from __future__ import annotations

import asyncio
import threading
import tkinter as tk
from tkinter import messagebox, ttk

from .audio import AudioOutput
from .device import Device
from .network import BleeCellNetwork


class App:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("bleeCELL")
        self.root.geometry("760x520")

        self.loop = asyncio.new_event_loop()
        self.thread = threading.Thread(target=self.loop.run_forever, daemon=True)
        self.thread.start()

        self.network: BleeCellNetwork | None = None
        self.core_server = None
        self.cell_server = None
        self.devices: dict[str, Device] = {}
        self.audio: AudioOutput | None = None
        self.audio_devices: list[tuple[int, str]] = []

        self._build()
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def _build(self) -> None:
        main = ttk.Frame(self.root, padding=12)
        main.pack(fill="both", expand=True)

        ttk.Label(main, text="bleeCELL", font=("TkDefaultFont", 20, "bold")).pack(anchor="w")
        ttk.Label(main, text="software-only cellular network simulator").pack(anchor="w", pady=(0, 12))

        net = ttk.LabelFrame(main, text="network")
        net.pack(fill="x", pady=5)
        self.net_status = ttk.Label(net, text="stopped")
        self.net_status.grid(row=0, column=0, padx=8, pady=8)
        ttk.Button(net, text="start network", command=self.start_network).grid(row=0, column=1, padx=8)
        ttk.Button(net, text="stop", command=self.stop_network).grid(row=0, column=2, padx=8)

        devices = ttk.LabelFrame(main, text="virtual devices")
        devices.pack(fill="x", pady=5)

        ttk.Label(devices, text="device").grid(row=0, column=0, padx=8, pady=8)
        self.device_box = ttk.Combobox(devices, values=["UE-0001", "UE-0002"], state="readonly")
        self.device_box.current(0)
        self.device_box.grid(row=0, column=1, padx=8)
        ttk.Button(devices, text="connect/register", command=self.connect_device).grid(row=0, column=2, padx=8)

        ttk.Label(devices, text="recipient").grid(row=1, column=0, padx=8, pady=8)
        self.recipient_box = ttk.Combobox(devices, values=["UE-0001", "UE-0002"], state="readonly")
        self.recipient_box.current(1)
        self.recipient_box.grid(row=1, column=1, padx=8)
        self.message_box = ttk.Entry(devices)
        self.message_box.grid(row=1, column=2, padx=8, sticky="ew")
        ttk.Button(devices, text="send", command=self.send_message).grid(row=1, column=3, padx=8)
        devices.columnconfigure(2, weight=1)

        audio = ttk.LabelFrame(main, text="audio output")
        audio.pack(fill="x", pady=5)
        self.audio_box = ttk.Combobox(audio, state="readonly", width=65)
        self.audio_box.grid(row=0, column=0, padx=8, pady=8, sticky="ew")
        ttk.Button(audio, text="refresh", command=self.refresh_audio).grid(row=0, column=1, padx=4)
        ttk.Button(audio, text="test tone", command=self.test_tone).grid(row=0, column=2, padx=4)
        audio.columnconfigure(0, weight=1)

        log_frame = ttk.LabelFrame(main, text="log")
        log_frame.pack(fill="both", expand=True, pady=5)
        self.log = tk.Text(log_frame, height=12, state="disabled")
        self.log.pack(fill="both", expand=True)

        self.refresh_audio()

    def write(self, text: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", text + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def submit(self, coro) -> None:
        asyncio.run_coroutine_threadsafe(coro, self.loop)

    def start_network(self) -> None:
        if self.network:
            return

        async def start() -> None:
            try:
                self.network = BleeCellNetwork()
                self.network.core.add_subscriber("UE-0001", "key-one")
                self.network.core.add_subscriber("UE-0002", "key-two")
                self.core_server, self.cell_server = await self.network.start()
                self.root.after(0, lambda: self.net_status.config(text="running"))
                self.root.after(0, lambda: self.write("core :9000 / cell :9100 started"))
            except Exception as exc:
                self.root.after(0, lambda: messagebox.showerror("bleeCELL", str(exc)))

        self.submit(start())

    def stop_network(self) -> None:
        if not self.network:
            return

        def stop() -> None:
            async def close() -> None:
                if self.core_server:
                    self.core_server.close()
                    await self.core_server.wait_closed()
                if self.cell_server:
                    self.cell_server.close()
                    await self.cell_server.wait_closed()
                self.network = None
                self.root.after(0, lambda: self.net_status.config(text="stopped"))

            self.submit(close())

        stop()

    def connect_device(self) -> None:
        ue_id = self.device_box.get()
        key = {"UE-0001": "key-one", "UE-0002": "key-two"}[ue_id]

        async def connect() -> None:
            try:
                device = Device(ue_id, key)
                await device.connect()
                await device.register()
                await device.authenticate()
                self.devices[ue_id] = device
                self.root.after(0, lambda: self.write(f"{ue_id}: registered and authenticated"))
                asyncio.create_task(self.receive_loop(device))
            except Exception as exc:
                self.root.after(0, lambda: messagebox.showerror("device", str(exc)))

        if not self.network:
            self.write("start the network first")
            return
        self.submit(connect())

    async def receive_loop(self, device: Device) -> None:
        while True:
            try:
                packet = await device.receive()
                if not packet.kind:
                    return
                text = packet.payload.get("text", "") if packet.payload else ""
                self.root.after(0, lambda t=f"{packet.sender} -> {packet.recipient}: {text}": self.write(t))
            except (ConnectionError, asyncio.IncompleteReadError):
                return

    def send_message(self) -> None:
        sender = self.device_box.get()
        recipient = self.recipient_box.get()
        text = self.message_box.get()
        device = self.devices.get(sender)
        if not device:
            self.write(f"{sender} is not connected")
            return
        if not text:
            return
        self.submit(device.message(recipient, text))
        self.write(f"{sender} -> {recipient}: {text}")
        self.message_box.delete(0, "end")

    def refresh_audio(self) -> None:
        try:
            self.audio = self.audio or AudioOutput()
            self.audio_devices = self.audio.outputs()
            names = [f"{i}: {name}" for i, name in self.audio_devices]
            self.audio_box["values"] = names
            if names:
                self.audio_box.current(0)
                self.write(f"found {len(names)} audio output(s)")
        except RuntimeError as exc:
            self.audio_box["values"] = ["sounddevice not installed"]
            self.audio_box.current(0)
            self.write(str(exc))

    def test_tone(self) -> None:
        if not self.audio or not self.audio_devices:
            self.write("no audio output available")
            return
        selected = self.audio_devices[self.audio_box.current()][0]
        try:
            self.audio.play_tone(selected)
            self.write(f"test tone -> output {selected}")
        except Exception as exc:
            messagebox.showerror("audio", str(exc))

    def close(self) -> None:
        self.stop_network()
        self.loop.call_soon_threadsafe(self.loop.stop)
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
