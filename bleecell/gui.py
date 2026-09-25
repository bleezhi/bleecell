from __future__ import annotations
import asyncio
import threading
import tkinter as tk
from tkinter import messagebox,ttk
from .audio import AudioOutput
from .device import Device
from .network import BleeCellNetwork

class App:
    def __init__(self,root):
        self.root=root; self.root.title("bleeCELL"); self.root.geometry("820x650")
        self.loop=asyncio.new_event_loop(); self.thread=threading.Thread(target=self.loop.run_forever,daemon=True); self.thread.start()
        self.network=None; self.core_server=None; self.cell_server=None; self.devices={}; self.audio=None; self.audio_devices=[]; self.call_active=False
        self._build(); self.root.protocol("WM_DELETE_WINDOW",self.close)
    def _build(self):
        main=ttk.Frame(self.root,padding=12); main.pack(fill="both",expand=True)
        ttk.Label(main,text="bleeCELL",font=("TkDefaultFont",20,"bold")).pack(anchor="w")
        ttk.Label(main,text="software-only cellular network simulator").pack(anchor="w",pady=(0,12))
        net=ttk.LabelFrame(main,text="network"); net.pack(fill="x",pady=5)
        self.net_status=ttk.Label(net,text="stopped"); self.net_status.grid(row=0,column=0,padx=8,pady=8)
        ttk.Button(net,text="start network",command=self.start_network).grid(row=0,column=1,padx=8); ttk.Button(net,text="stop",command=self.stop_network).grid(row=0,column=2,padx=8)
        devices=ttk.LabelFrame(main,text="virtual devices"); devices.pack(fill="x",pady=5)
        ttk.Label(devices,text="device").grid(row=0,column=0,padx=8,pady=8)
        self.device_box=ttk.Combobox(devices,values=["UE-0001","UE-0002"],state="readonly"); self.device_box.current(0); self.device_box.grid(row=0,column=1,padx=8)
        ttk.Button(devices,text="connect/register",command=self.connect_device).grid(row=0,column=2,padx=8)
        ttk.Label(devices,text="recipient").grid(row=1,column=0,padx=8,pady=8)
        self.recipient_box=ttk.Combobox(devices,values=["UE-0001","UE-0002"],state="readonly"); self.recipient_box.current(1); self.recipient_box.grid(row=1,column=1,padx=8)
        self.message_box=ttk.Entry(devices); self.message_box.grid(row=1,column=2,padx=8,sticky="ew"); ttk.Button(devices,text="send",command=self.send_message).grid(row=1,column=3,padx=8); devices.columnconfigure(2,weight=1)
        calls=ttk.LabelFrame(main,text="calls"); calls.pack(fill="x",pady=5)
        ttk.Label(calls,text="call from").grid(row=0,column=0,padx=8,pady=8)
        self.call_from=ttk.Combobox(calls,values=["UE-0001","UE-0002"],state="readonly"); self.call_from.current(0); self.call_from.grid(row=0,column=1,padx=8)
        ttk.Label(calls,text="to").grid(row=0,column=2,padx=8); self.call_to=ttk.Combobox(calls,values=["UE-0001","UE-0002"],state="readonly"); self.call_to.current(1); self.call_to.grid(row=0,column=3,padx=8)
        ttk.Button(calls,text="start call",command=self.start_call).grid(row=0,column=4,padx=8); ttk.Button(calls,text="end call",command=self.end_call).grid(row=0,column=5,padx=8)
        self.call_status=ttk.Label(calls,text="idle"); self.call_status.grid(row=1,column=0,columnspan=6,padx=8,pady=(0,8),sticky="w")
        audio=ttk.LabelFrame(main,text="audio output"); audio.pack(fill="x",pady=5)
        self.audio_box=ttk.Combobox(audio,state="readonly",width=65); self.audio_box.grid(row=0,column=0,padx=8,pady=8,sticky="ew")
        ttk.Button(audio,text="refresh",command=self.refresh_audio).grid(row=0,column=1,padx=4); ttk.Button(audio,text="start audio",command=self.start_audio).grid(row=0,column=2,padx=4); ttk.Button(audio,text="stop audio",command=self.stop_audio).grid(row=0,column=3,padx=4); ttk.Button(audio,text="test event",command=self.test_tone).grid(row=0,column=4,padx=4)
        self.audio_status=ttk.Label(audio,text="audio stopped"); self.audio_status.grid(row=1,column=0,columnspan=5,padx=8,pady=(0,8),sticky="w"); audio.columnconfigure(0,weight=1)
        log_frame=ttk.LabelFrame(main,text="log"); log_frame.pack(fill="both",expand=True,pady=5); self.log=tk.Text(log_frame,height=12,state="disabled"); self.log.pack(fill="both",expand=True); self.refresh_audio()
    def write(self,text):
        self.log.configure(state="normal"); self.log.insert("end",text+"\n"); self.log.see("end"); self.log.configure(state="disabled")
    def submit(self,coro): return asyncio.run_coroutine_threadsafe(coro,self.loop)
    def selected_audio(self):
        return self.audio_devices[self.audio_box.current()][0] if self.audio_devices and self.audio_box.current()>=0 else None
    def ensure_audio(self):
        if not self.audio: self.write("audio unavailable"); return False
        d=self.selected_audio()
        if d is None: self.write("no audio output selected"); return False
        try:
            if not self.audio.is_running(): self.audio.start(d)
            return True
        except Exception as exc: messagebox.showerror("audio",str(exc)); return False
    def start_network(self):
        if self.network:return
        async def start():
            try:
                self.network=BleeCellNetwork(); self.network.core.add_subscriber("UE-0001","key-one"); self.network.core.add_subscriber("UE-0002","key-two"); self.core_server,self.cell_server=await self.network.start()
                self.root.after(0,lambda:self.net_status.config(text="running")); self.root.after(0,lambda:self.write("core :9000 / cell :9100 started")); self.audio_event(330)
            except Exception as exc:self.root.after(0,lambda:messagebox.showerror("bleeCELL",str(exc)))
        self.submit(start())
    def stop_network(self):
        if not self.network:return
        async def close():
            if self.core_server:self.core_server.close(); await self.core_server.wait_closed()
            if self.cell_server:self.cell_server.close(); await self.cell_server.wait_closed()
            self.network=None; self.root.after(0,lambda:self.net_status.config(text="stopped"))
        self.submit(close()); self.end_call(); self.audio_event(180)
    def connect_device(self):
        ue=self.device_box.get(); key={"UE-0001":"key-one","UE-0002":"key-two"}[ue]
        async def connect():
            try:
                device=Device(ue,key); await device.connect(); await device.register(); await device.authenticate(); self.devices[ue]=device
                self.root.after(0,lambda:self.write(f"{ue}: registered and authenticated")); self.audio_event(660); asyncio.create_task(self.receive_loop(device))
            except Exception as exc:self.root.after(0,lambda:messagebox.showerror("device",str(exc)))
        if not self.network:self.write("start the network first"); return
        self.submit(connect())
    async def receive_loop(self,device):
        while True:
            try:
                packet=await device.receive()
                if not packet.kind:return
                text=packet.payload.get("text","") if packet.payload else ""; self.root.after(0,lambda t=f"{packet.sender} -> {packet.recipient}: {text}":self.write(t))
                if packet.kind=="DATA":self.audio_event(880,.18,.12)
            except (ConnectionError,asyncio.IncompleteReadError):return
    def send_message(self):
        sender=self.device_box.get(); recipient=self.recipient_box.get(); text=self.message_box.get(); device=self.devices.get(sender)
        if not device:self.write(f"{sender} is not connected"); return
        if not text:return
        self.submit(device.message(recipient,text)); self.write(f"{sender} -> {recipient}: {text}"); self.audio_event(880,.18,.12); self.message_box.delete(0,"end")
    def start_call(self):
        caller=self.call_from.get(); target=self.call_to.get()
        if caller==target:self.write("caller and target must be different"); return
        if caller not in self.devices or target not in self.devices:self.write("both devices must be connected first"); return
        if not self.ensure_audio():return
        self.call_active=True; self.audio.set_call(True,440,.08); self.call_status.config(text=f"active: {caller} -> {target}"); self.write(f"call started: {caller} -> {target}"); self.audio_event(880,.25,.14)
    def end_call(self):
        if self.audio:self.audio.set_call(False)
        if self.call_active:self.write("call ended")
        self.call_active=False; self.call_status.config(text="idle")
    def refresh_audio(self):
        try:
            self.audio=self.audio or AudioOutput(); self.audio_devices=self.audio.outputs(); names=[f"{i}: {name}" for i,name in self.audio_devices]; self.audio_box["values"]=names
            if names:self.audio_box.current(0); self.write(f"found {len(names)} audio output(s)")
        except RuntimeError as exc:self.audio_box["values"]=["sounddevice not installed"]; self.audio_box.current(0); self.write(str(exc))
    def start_audio(self):
        if not self.ensure_audio():return
        self.audio_status.config(text=f"audio running -> output {self.selected_audio()}"); self.write(f"continuous audio -> output {self.selected_audio()}")
    def stop_audio(self):
        self.end_call()
        if self.audio:self.audio.stop()
        self.audio_status.config(text="audio stopped"); self.write("continuous audio stopped")
    def audio_event(self,frequency,seconds=.12,level=.10):
        if self.audio and self.audio.is_running():self.audio.event(frequency,seconds,level)
    def test_tone(self):
        if not self.ensure_audio():return
        self.audio.event(440,.5,.15); self.write(f"test event -> output {self.selected_audio()}")
    def close(self):
        self.stop_audio(); self.stop_network(); self.loop.call_soon_threadsafe(self.loop.stop); self.root.destroy()

def main():
    root=tk.Tk(); App(root); root.mainloop()

if __name__=="__main__":main()
