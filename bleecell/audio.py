from __future__ import annotations
import math
import threading
import numpy as np

class AudioOutput:
    """Continuous software audio output and simple call audio."""
    def __init__(self) -> None:
        try:
            import sounddevice as sd
        except ImportError as exc:
            raise RuntimeError("audio support requires the 'sounddevice' package") from exc
        self.sd=sd; self.rate=48000; self.channels=1
        self._stream=None; self._device=None; self._lock=threading.Lock()
        self._phase=0.0; self._event_phase=0.0; self._event_frequency=0.0
        self._event_level=0.0; self._event_remaining=0
        self._call_active=False; self._call_frequency=440.0; self._call_level=0.06; self._call_phase=0.0
    def outputs(self):
        return [(i,str(d["name"])) for i,d in enumerate(self.sd.query_devices()) if int(d["max_output_channels"])>0]
    def _callback(self,outdata,frames,_time,status):
        with self._lock:
            ef,el,er=self._event_frequency,self._event_level,self._event_remaining
            ca,cf,cl=self._call_active,self._call_frequency,self._call_level
        samples=np.empty(frames,dtype=np.float32)
        for i in range(frames):
            sample=0.08*math.sin(2*math.pi*self._phase)
            self._phase=(self._phase+220.0/self.rate)%1.0
            if er>0 and ef:
                sample+=el*math.sin(2*math.pi*self._event_phase)
                self._event_phase=(self._event_phase+ef/self.rate)%1.0; er-=1
            if ca:
                sample+=cl*(math.sin(2*math.pi*cf*self._call_phase)+0.5*math.sin(2*math.pi*cf*1.5*self._call_phase))
                self._call_phase=(self._call_phase+1.0/self.rate)%1.0
            samples[i]=max(-0.8,min(0.8,sample))
        with self._lock: self._event_remaining=er
        outdata[:,0]=samples
        if outdata.shape[1]>1: outdata[:,1:]=samples[:,None]
    def start(self,device):
        self.stop(); self._device=device
        try:
            self._stream=self.sd.OutputStream(samplerate=self.rate,channels=self.channels,dtype="float32",device=device,callback=self._callback,blocksize=960)
            self._stream.start()
        except Exception:
            self._stream=None; self._device=None; raise
    def stop(self):
        stream=self._stream; self._stream=None
        if stream is not None: stream.stop(); stream.close()
        self._device=None
    def is_running(self): return self._stream is not None
    def event(self,frequency,seconds=0.12,level=0.10):
        with self._lock:
            self._event_frequency=frequency; self._event_level=level; self._event_phase=0.0
            self._event_remaining=max(1,int(self.rate*seconds))
    def set_call(self,active,frequency=440.0,level=0.06):
        with self._lock:
            self._call_active=active; self._call_frequency=frequency; self._call_level=level
            if active: self._call_phase=0.0
    def play_tone(self,device=None,frequency=440.0,seconds=0.5):
        if device is not None and (not self.is_running() or self._device!=device): self.start(device)
        if not self.is_running(): raise RuntimeError("select an audio output first")
        self.event(frequency,seconds,0.15)
