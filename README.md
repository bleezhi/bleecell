# bleeCELL

bleeCELL is an experimental, software-only cellular network simulator written in Python.

The first version models a tiny cellular network without transmitting on real radio frequencies:

```
UE-0001 ──┐
UE-0002 ──┼── base station ── core
UE-0003 ──┘
```

## v0.1

- virtual user equipment (UE)
- virtual base station
- subscriber registration
- authentication
- device-to-device messaging through the core
- JSON messages over TCP
- no real cellular radio or spectrum required

## Run

```bash
python -m examples.basic_network
```

The demo starts a core, a base station, two virtual devices, registers them, authenticates them, and sends a message.

bleeCELL is a simulator, not an implementation of a real cellular standard.
