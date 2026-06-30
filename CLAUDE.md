# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Custom Home Assistant integration for Samsung air conditioners using the port 2878 / "Jungfrau" / AC14K protocol. Fully async, config-flow based, distributed via HACS. Tested device: Samsung AR12HSFSAWKN.

## Development

There is no build system, test suite, linter, or CI/CD. The integration runs inside Home Assistant.

**Install for development:** Copy `custom_components/samsung_2878/` into your HA `config/custom_components/` directory and restart HA.

**CLI tool (standalone, no HA needed):**
```bash
python3 samsung_ac_cli.py configure --host 192.168.1.100 --token YOUR_TOKEN --mac AA:BB:CC:DD:EE:FF
python3 samsung_ac_cli.py status
python3 samsung_ac_cli.py on|off|mode|temp|fan|swing|preset|sleep|info|raw
```

## Architecture

```
HA Entities (climate, sensor, switch, number, select, button)
        │
Samsung2878Coordinator   (DataUpdateCoordinator, 20s poll/keepalive, optimistic + real-time push)
        │
Samsung2878Client        (pure asyncio TCP/TLS, no HA dependency)
        │
Samsung AC on port 2878  (line-delimited XML over TLS 1.0, mutual TLS)
```

**`Samsung2878Client`** (`client.py`): Pure asyncio TCP/TLS client. Handles the 3-step auth handshake (greeting → InvalidateAccount → AuthToken). After auth, a single background reader task (`_read_loop`) owns all socket reads and dispatches each line: `<Response>` lines fulfil the in-flight command's future (`_pending_response`), unsolicited `<Update>` pushes go to a registered callback. `_io_lock` serializes command submission so only one response is awaited at a time. Reads are never issued concurrently. Also used by the CLI tool (loaded via `importlib` to avoid HA imports).

**`Samsung2878State`** (`client.py`): Dataclass holding parsed AC state. Notable parsing: outdoor temp = raw − 55, energy = raw ÷ 10.0, temp_set 0 → 24 default.

**`Samsung2878Coordinator`** (`coordinator.py`): Wraps the client. `ensure_connected()` auto-reconnects on both poll and command. The poll doubles as a keepalive that keeps the socket warm for push. `_handle_push()` applies real-time `<Update>` messages (remote/app changes) via `merge_push` + `async_update_listeners` (without rescheduling the poll). `send_command()` supports optimistic state updates and reconnect-and-retry-once.

**`Samsung2878Climate`** (`climate.py`): Primary control entity. Uses MAC as unique_id.

**Entity unique_id pattern:** All entities use `f"{mac}_{suffix}"`.

**Platform registration** (`__init__.py`): BUTTON, CLIMATE, NUMBER, SELECT, SENSOR, SWITCH.

**Config flow:** Single step collecting host, port (default 2878), token, MAC. DUID derived from MAC (strip colons, uppercase). Tests connection before creating entry.

## Key Conventions

- `from __future__ import annotations` in all files
- Modern HA entity style: `_attr_*` class attributes instead of property overrides
- `_attr_has_entity_name = True` with `_attr_name` set per entity (climate uses `None` for device name)
- `# noqa: BLE001` on broad `except Exception` catches
- All constants and mode maps live in `const.py`
- TLS 1.0 with `AES256-SHA` cipher and `SECLEVEL=0` required for legacy AC protocol; SSL context creation runs in `asyncio.to_thread` since it involves blocking I/O
- The bundled `ac14k_m.pem` certificate is used for mutual TLS authentication
- CLI tool uses `importlib.util.spec_from_file_location` to load `client.py` directly, config stored at `~/.config/samsung-ac/config.json`
