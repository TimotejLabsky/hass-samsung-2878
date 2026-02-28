# Samsung 2878 AC Integration for Home Assistant

Custom Home Assistant integration for Samsung air conditioners using the port 2878 protocol (AC14K / Jungfrau series).

Fully async, config-flow based replacement for the legacy [samsungrac](https://github.com/SebuZet/samsungrac) integration.

## Features

- UI-based configuration (no YAML needed)
- Fully async (no event loop blocking)
- OpenSSL 3.x compatible (TLSv1 + SECLEVEL=0 baked in)
- HVAC modes: Auto, Cool, Heat, Dry, Fan Only
- Fan speeds: Auto, Low, Mid, High, Turbo
- Swing modes: Off, Vertical, Horizontal, Both
- Presets: Quiet, Sleep, Smart, SoftCool
- Current & outdoor temperature sensors
- HACS compatible

## Installation

### HACS (Recommended)

1. Add this repository as a custom repository in HACS
2. Search for "Samsung 2878 AC" and install
3. Restart Home Assistant

### Manual

1. Copy `custom_components/samsung_2878/` to your HA `config/custom_components/` directory
2. Restart Home Assistant

## Configuration

1. Go to **Settings** > **Devices & Services** > **Add Integration**
2. Search for **Samsung 2878 AC**
3. Enter:
   - **IP Address**: Your AC's IP (e.g., `192.168.1.100`)
   - **Port**: `2878` (default)
   - **Token**: Authentication token from initial pairing
   - **MAC Address**: AC's MAC address (e.g., `AA:BB:CC:DD:EE:FF`)
4. The integration will test the connection and create the climate entity

## Getting Your Token

If you don't have a token yet:

1. Connect to your AC's IP on port 2878 using the Samsung Smart AC app
2. Send a `GetToken` request
3. Power-cycle the AC with the remote (OFF, wait 5s, ON)
4. The AC will broadcast the token

See [PROTOCOL.md](PROTOCOL.md) for detailed protocol documentation.

## Supported Models

Tested with Samsung AR12HSFSAWKN (AC14K / Jungfrau variant). Should work with other Samsung ACs that use port 2878 and the Jungfrau protocol variant.
