#!/usr/bin/env python3
"""CLI tool for Samsung 2878 AC control.

Uses the same client as the HACS integration.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path

# Import client directly to avoid triggering __init__.py (which needs homeassistant)
import importlib.util

_client_path = str(Path(__file__).parent / "custom_components" / "samsung_2878" / "client.py")
_spec = importlib.util.spec_from_file_location("samsung_2878_client", _client_path)
_client_mod = importlib.util.module_from_spec(_spec)
_client_mod.__package__ = "samsung_2878_client"
sys.modules[_spec.name] = _client_mod
_spec.loader.exec_module(_client_mod)

Samsung2878Client = _client_mod.Samsung2878Client
Samsung2878State = _client_mod.Samsung2878State

CONFIG_DIR = Path.home() / ".config" / "samsung-ac"
CONFIG_FILE = CONFIG_DIR / "config.json"


def load_config() -> dict[str, str]:
    """Load saved config from disk."""
    if CONFIG_FILE.exists():
        return json.loads(CONFIG_FILE.read_text())
    return {}


def save_config(cfg: dict[str, str]) -> None:
    """Save config to disk."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(cfg, indent=2) + "\n")


def resolve_config(args: argparse.Namespace) -> tuple[str, str, str]:
    """Resolve host/token/mac from CLI args > env vars > config file."""
    cfg = load_config()

    host = args.host or os.environ.get("SAMSUNG_AC_HOST") or cfg.get("host")
    token = args.token or os.environ.get("SAMSUNG_AC_TOKEN") or cfg.get("token")
    mac = args.mac or os.environ.get("SAMSUNG_AC_MAC") or cfg.get("mac")

    if not host or not token or not mac:
        missing = []
        if not host:
            missing.append("host")
        if not token:
            missing.append("token")
        if not mac:
            missing.append("mac")
        print(
            f"Error: missing {', '.join(missing)}. "
            f"Use --{'/--'.join(missing)}, env vars, or 'configure' command.",
            file=sys.stderr,
        )
        sys.exit(1)

    return host, token, mac


async def connect_client(host: str, token: str, mac: str) -> Samsung2878Client:
    """Create, connect, and authenticate a client."""
    duid = mac.upper().replace(":", "").replace("-", "")
    client = Samsung2878Client(host=host, port=2878, token=token, duid=duid)
    await client.connect()
    await client.authenticate()
    return client


def format_state_table(state: Samsung2878State) -> str:
    """Format state as a readable table."""
    raw = state.raw
    lines = [
        f"{'Power':<24} {'On' if state.power else 'Off'}",
        f"{'Mode':<24} {state.mode}",
        f"{'Current temp':<24} {state.current_temp} °C",
        f"{'Target temp':<24} {state.target_temp} °C",
        f"{'Fan mode':<24} {state.fan_mode}",
        f"{'Swing mode':<24} {state.swing_mode}",
        f"{'Preset':<24} {state.preset}",
    ]
    if state.outdoor_temp is not None:
        lines.append(f"{'Outdoor temp':<24} {state.outdoor_temp} °C")
    if state.error:
        lines.append(f"{'Error':<24} {state.error}")
    lines.append(f"{'Auto clean':<24} {'On' if state.auto_clean else 'Off'}")
    lines.append(f"{'Ionizer (SPI)':<24} {'On' if state.spi else 'Off'}")
    lines.append(f"{'Sleep timer':<24} {state.sleep_timer} min")
    if state.used_watt is not None:
        lines.append(f"{'Energy usage':<24} {state.used_watt} kWh")
    if state.used_power is not None:
        lines.append(f"{'Lifetime energy':<24} {state.used_power} kWh")
    if state.used_time is not None:
        lines.append(f"{'Operating time':<24} {state.used_time} h")
    if state.filter_use_time is not None:
        lines.append(f"{'Filter usage':<24} {state.filter_use_time} h")
    if state.filter_time is not None:
        lines.append(f"{'Filter threshold':<24} {state.filter_time} h")
    if state.cool_capability is not None:
        lines.append(f"{'Cool capability':<24} {state.cool_capability}")
    if state.warm_capability is not None:
        lines.append(f"{'Warm capability':<24} {state.warm_capability}")
    if state.panel_version:
        lines.append(f"{'Panel version':<24} {state.panel_version}")
    if state.outdoor_version:
        lines.append(f"{'Outdoor version':<24} {state.outdoor_version}")

    # Show any raw attributes not already displayed
    known_keys = {
        "AC_FUN_POWER", "AC_FUN_OPMODE", "AC_FUN_TEMPNOW", "AC_FUN_TEMPSET",
        "AC_FUN_WINDLEVEL", "AC_FUN_DIRECTION", "AC_FUN_COMODE", "AC_FUN_ERROR",
        "AC_FUN_SLEEP", "AC_ADD_AUTOCLEAN", "AC_ADD_SPI", "AC_ADD2_USEDWATT",
        "AC_ADD2_USEDPOWER", "AC_ADD2_USEDTIME", "AC_ADD2_FILTER_USE_TIME",
        "AC_ADD2_FILTERTIME", "AC_OUTDOOR_TEMP", "AC_COOL_CAPABILITY",
        "AC_WARM_CAPABILITY",
    }
    extra = {k: v for k, v in raw.items() if k not in known_keys}
    if extra:
        lines.append("")
        lines.append("--- Raw attributes ---")
        for k, v in sorted(extra.items()):
            lines.append(f"  {k:<30} {v}")

    return "\n".join(lines)


# --- Command handlers ---

async def cmd_status(args: argparse.Namespace) -> None:
    host, token, mac = resolve_config(args)
    client = await connect_client(host, token, mac)
    try:
        state = await client.get_status()
        if args.json:
            d = asdict(state)
            print(json.dumps(d, indent=2))
        else:
            print(format_state_table(state))
    finally:
        await client.disconnect()


async def cmd_on(args: argparse.Namespace) -> None:
    host, token, mac = resolve_config(args)
    client = await connect_client(host, token, mac)
    try:
        await client.set_power(True)
        print("Power: On")
    finally:
        await client.disconnect()


async def cmd_off(args: argparse.Namespace) -> None:
    host, token, mac = resolve_config(args)
    client = await connect_client(host, token, mac)
    try:
        await client.set_power(False)
        print("Power: Off")
    finally:
        await client.disconnect()


async def cmd_mode(args: argparse.Namespace) -> None:
    host, token, mac = resolve_config(args)
    client = await connect_client(host, token, mac)
    try:
        await client.set_mode(args.value)
        print(f"Mode: {args.value}")
    finally:
        await client.disconnect()


async def cmd_temp(args: argparse.Namespace) -> None:
    host, token, mac = resolve_config(args)
    client = await connect_client(host, token, mac)
    try:
        await client.set_temperature(args.value)
        print(f"Temperature: {args.value} °C")
    finally:
        await client.disconnect()


async def cmd_fan(args: argparse.Namespace) -> None:
    host, token, mac = resolve_config(args)
    client = await connect_client(host, token, mac)
    try:
        await client.set_fan_mode(args.value)
        print(f"Fan: {args.value}")
    finally:
        await client.disconnect()


async def cmd_swing(args: argparse.Namespace) -> None:
    host, token, mac = resolve_config(args)
    client = await connect_client(host, token, mac)
    try:
        await client.set_swing_mode(args.value)
        print(f"Swing: {args.value}")
    finally:
        await client.disconnect()


async def cmd_preset(args: argparse.Namespace) -> None:
    host, token, mac = resolve_config(args)
    client = await connect_client(host, token, mac)
    try:
        await client.set_preset(args.value)
        print(f"Preset: {args.value}")
    finally:
        await client.disconnect()


async def cmd_autoclean(args: argparse.Namespace) -> None:
    host, token, mac = resolve_config(args)
    client = await connect_client(host, token, mac)
    try:
        on = args.state.lower() in ("on", "true", "1")
        await client.set_auto_clean(on)
        print(f"Auto clean: {'On' if on else 'Off'}")
    finally:
        await client.disconnect()


async def cmd_spi(args: argparse.Namespace) -> None:
    host, token, mac = resolve_config(args)
    client = await connect_client(host, token, mac)
    try:
        on = args.state.lower() in ("on", "true", "1")
        await client.set_spi(on)
        print(f"Ionizer (SPI): {'On' if on else 'Off'}")
    finally:
        await client.disconnect()


async def cmd_sleep(args: argparse.Namespace) -> None:
    host, token, mac = resolve_config(args)
    client = await connect_client(host, token, mac)
    try:
        await client.set_sleep_timer(args.minutes)
        if args.minutes == 0:
            print("Sleep timer: Off")
        else:
            print(f"Sleep timer: {args.minutes} min")
    finally:
        await client.disconnect()


async def cmd_info(args: argparse.Namespace) -> None:
    host, token, mac = resolve_config(args)
    client = await connect_client(host, token, mac)
    try:
        info = await client.get_sw_info()
        if args.json:
            print(json.dumps(info, indent=2))
        else:
            for k, v in info.items():
                print(f"{k:<24} {v}")
    finally:
        await client.disconnect()


async def cmd_power_log(args: argparse.Namespace) -> None:
    host, token, mac = resolve_config(args)
    client = await connect_client(host, token, mac)
    try:
        entries = await client.get_power_usage(
            args.date_from, args.date_to, args.unit
        )
        if args.json:
            print(json.dumps(entries, indent=2))
        else:
            if not entries:
                print("No power usage data.")
            else:
                print(f"{'Date':<16} {'Usage':<12} {'Time':<8}")
                print("-" * 36)
                for e in entries:
                    print(
                        f"{e.get('date', '?'):<16} "
                        f"{e.get('usage', '?'):<12} "
                        f"{e.get('time', '?'):<8}"
                    )
    finally:
        await client.disconnect()


async def cmd_power_log_enable(args: argparse.Namespace) -> None:
    host, token, mac = resolve_config(args)
    client = await connect_client(host, token, mac)
    try:
        await client.set_power_logging_mode(True)
        print("Power logging: Enabled")
    finally:
        await client.disconnect()


async def cmd_power_log_disable(args: argparse.Namespace) -> None:
    host, token, mac = resolve_config(args)
    client = await connect_client(host, token, mac)
    try:
        await client.set_power_logging_mode(False)
        print("Power logging: Disabled")
    finally:
        await client.disconnect()


async def cmd_power_log_reset(args: argparse.Namespace) -> None:
    host, token, mac = resolve_config(args)
    client = await connect_client(host, token, mac)
    try:
        await client.reset_power_logging()
        print("Power logging data reset.")
    finally:
        await client.disconnect()


async def cmd_raw(args: argparse.Namespace) -> None:
    host, token, mac = resolve_config(args)
    client = await connect_client(host, token, mac)
    try:
        response = await client.send_raw_xml(args.xml)
        print(response)
    finally:
        await client.disconnect()


def cmd_configure(args: argparse.Namespace) -> None:
    cfg = load_config()
    if args.host:
        cfg["host"] = args.host
    if args.token:
        cfg["token"] = args.token
    if args.mac:
        cfg["mac"] = args.mac
    save_config(cfg)
    print(f"Config saved to {CONFIG_FILE}")
    for k, v in cfg.items():
        print(f"  {k}: {v}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Samsung 2878 AC CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--host", help="AC IP address")
    parser.add_argument("--token", help="Auth token")
    parser.add_argument("--mac", help="MAC address")
    parser.add_argument("--json", action="store_true", help="JSON output")

    sub = parser.add_subparsers(dest="command", required=True)

    # status
    sub.add_parser("status", help="Show full AC state")

    # on / off
    sub.add_parser("on", help="Turn AC on")
    sub.add_parser("off", help="Turn AC off")

    # mode
    p = sub.add_parser("mode", help="Set operation mode")
    p.add_argument("value", choices=["Auto", "Cool", "Heat", "Dry", "Wind"])

    # temp
    p = sub.add_parser("temp", help="Set target temperature")
    p.add_argument("value", type=int, choices=range(16, 31), metavar="16-30")

    # fan
    p = sub.add_parser("fan", help="Set fan speed")
    p.add_argument("value", choices=["Auto", "Low", "Mid", "High", "Turbo"])

    # swing
    p = sub.add_parser("swing", help="Set swing direction")
    p.add_argument(
        "value",
        choices=[
            "Off", "Fixed", "SwingUD", "SwingLR", "Rotation",
            "Indirect", "Direct", "Center", "Wide", "Left", "Right", "Long",
        ],
    )

    # preset
    p = sub.add_parser("preset", help="Set convenient mode")
    p.add_argument("value", choices=["Off", "Quiet", "Sleep", "Smart", "SoftCool"])

    # autoclean
    p = sub.add_parser("autoclean", help="Toggle auto clean")
    p.add_argument("state", choices=["on", "off"])

    # spi
    p = sub.add_parser("spi", help="Toggle ionizer (SPI)")
    p.add_argument("state", choices=["on", "off"])

    # sleep
    p = sub.add_parser("sleep", help="Set sleep timer")
    p.add_argument("minutes", type=int, help="Minutes (0=off, 1-420)")

    # info
    sub.add_parser("info", help="Show firmware versions")

    # power-log
    p = sub.add_parser("power-log", help="Get power usage history")
    p.add_argument("date_from", help="Start date (yy-MM-dd HH:mm)")
    p.add_argument("date_to", help="End date (yy-MM-dd HH:mm)")
    p.add_argument("--unit", default="Day", choices=["Hour", "Day"])

    # power-log-enable / disable / reset
    sub.add_parser("power-log-enable", help="Enable power logging")
    sub.add_parser("power-log-disable", help="Disable power logging")
    sub.add_parser("power-log-reset", help="Reset power logging data")

    # raw
    p = sub.add_parser("raw", help="Send raw XML command")
    p.add_argument("xml", help="XML string to send")

    # configure
    sub.add_parser("configure", help="Save connection config")

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    cmd = args.command

    if cmd == "configure":
        cmd_configure(args)
        return

    handler = {
        "status": cmd_status,
        "on": cmd_on,
        "off": cmd_off,
        "mode": cmd_mode,
        "temp": cmd_temp,
        "fan": cmd_fan,
        "swing": cmd_swing,
        "preset": cmd_preset,
        "autoclean": cmd_autoclean,
        "spi": cmd_spi,
        "sleep": cmd_sleep,
        "info": cmd_info,
        "power-log": cmd_power_log,
        "power-log-enable": cmd_power_log_enable,
        "power-log-disable": cmd_power_log_disable,
        "power-log-reset": cmd_power_log_reset,
        "raw": cmd_raw,
    }.get(cmd)

    if handler is None:
        parser.print_help()
        sys.exit(1)

    try:
        asyncio.run(handler(args))
    except KeyboardInterrupt:
        pass
    except Exception as err:
        print(f"Error: {err}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
