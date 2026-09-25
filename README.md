# bleeCELL

bleeCELL is an experimental, software-only cellular network simulator written in Python.

It models a tiny cellular network without transmitting on real radio frequencies:

```
UE-0001 ──┐
UE-0002 ──┼── virtual cell ── virtual core
UE-0003 ──┘
```

## v0.2 GUI

The project now includes a Tkinter GUI with:

- start/stop virtual network
- virtual UE registration and authentication
- device-to-device messaging
- audio output enumeration
- selectable audio output
- test tone
- live network log

The audio output is only a local application output. bleeCELL does not transmit cellular RF.

## install

On Arch Linux:

```bash
sudo pacman -S python python-pip tk
python -m pip install --user sounddevice
```

Or:

```bash
python -m pip install -r requirements.txt
```

## run

```bash
python bleecell_app.py
```

The GUI should open with the network stopped. Click **start network**, then connect/register the two virtual devices.

## command-line demo

```bash
python -m examples.basic_network
```

bleeCELL is a simulator, not an implementation of a real cellular standard.
