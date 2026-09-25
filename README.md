# bleeCELL

bleeCELL is an experimental, software-only cellular network simulator written in Python.

It models a tiny cellular network without transmitting on real radio frequencies:

```
UE-0001 ──┐
UE-0002 ──┼── virtual cell ── virtual core
UE-0003 ──┘
```

## v0.4 wideband virtual cell\n\nThe simulator now includes a large-bandwidth virtual cellular radio model. The default cell is **100 MHz wide** with an approximately 277-resource-block model and a nominal 450 Mbps aggregate throughput model. Connected UEs share the virtual spectrum through a simple scheduler.\n\nThis is deliberately a software resource model: it does not create or transmit 100 MHz of RF or consume 100 MHz of sampled radio bandwidth. Audio and data still travel over the simulator TCP connection.\n\nClients can query their current cell bandwidth, modeled throughput, resource blocks, and per-UE allocation.\n\n## v0.3 client + audio

The project now includes a standalone client app:

```
microphone -> bleeCELL client -> virtual cell -> core -> other client -> speaker
```

The client requires an audio input device before it connects. It also lets you select an output device for received call audio.

Features:

- connect to a remote/local virtual cell
- UE ID and authentication key
- microphone input selection
- speaker/output selection
- register + authenticate
- call another virtual UE
- end calls
- send live microphone PCM over the simulated network
- receive and play PCM from another client
- text messaging

This is software audio carried by TCP/JSON packets. It does not transmit cellular RF.

## install

On Arch Linux:

```bash
sudo pacman -S python python-pip tk
python -m pip install --user -r requirements.txt
```

## run the server GUI

```bash
python bleecell_app.py
```

Start the virtual network first.

## run the client

```bash
python bleecell_client.py
```

In the client:

1. choose a microphone/input device
2. choose a speaker/output device
3. enter the cell host/port
4. enter a UE ID and key
5. click **connect**
6. register/authenticate
7. enter another UE ID and start a call

Both clients need to be connected and authenticated. Audio is sent only while a call is active.

## command-line demo

```bash
python -m examples.basic_network
```

bleeCELL is a simulator, not an implementation of a real cellular standard.
