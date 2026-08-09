"""Windows BLE-to-HTTP bridge for an HHC D345 / L2 Motion bed."""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import secrets
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from aiohttp import web
from bleak import BleakClient, BleakScanner

LOGGER = logging.getLogger("l2_motion_bridge")

DEFAULT_DEVICE_NAME = "HHC0051745CDEF"
DEFAULT_PORT = 8765
WRITE_UUID = "0000ffe1-0000-1000-8000-00805f9b34fb"

COMMANDS = {
    "light": "A",
    "foot_massage": "B",
    "head_massage": "C",
    "stop_massage": "D",
    "head_up": "K",
    "head_down": "L",
    "feet_up": "M",
    "feet_down": "N",
    "home": "O",
    "extra_up": "P",
    "extra_down": "Q",
    "memory_1": "U",
    "memory_2": "V",
}


@dataclass(frozen=True)
class BridgeConfig:
    """Runtime configuration loaded from JSON or command-line arguments."""

    token: str
    host: str = "0.0.0.0"
    port: int = DEFAULT_PORT
    device_name: str = DEFAULT_DEVICE_NAME
    address: str | None = None

    @classmethod
    def from_json(cls, path: Path) -> "BridgeConfig":
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        return cls(
            token=str(data["token"]),
            host=str(data.get("host", "0.0.0.0")),
            port=int(data.get("port", DEFAULT_PORT)),
            device_name=str(data.get("device_name", DEFAULT_DEVICE_NAME)),
            address=data.get("address") or None,
        )

    def validate(self) -> None:
        if len(self.token) < 24:
            raise ValueError("The bridge token must be at least 24 characters long")
        if not 1 <= self.port <= 65535:
            raise ValueError("The bridge port must be between 1 and 65535")


class BedController:
    """Serialize BLE access and reproduce the D345 phone-app write cadence."""

    def __init__(self, config: BridgeConfig) -> None:
        self.config = config
        self._lock = asyncio.Lock()
        self.last_address: str | None = config.address
        self.last_rssi: int | None = None

    async def discover(self, timeout: float = 10.0):
        """Find the exact bed by configured address or verified local name."""
        if self.config.address:
            device = await BleakScanner.find_device_by_address(
                self.config.address, timeout=timeout
            )
        else:
            device = await BleakScanner.find_device_by_name(
                self.config.device_name, timeout=timeout
            )
        if device is None:
            raise RuntimeError(
                f"{self.config.device_name} was not visible to Windows Bluetooth"
            )
        self.last_address = device.address
        return device

    async def scan_status(self) -> dict[str, Any]:
        device = await self.discover()
        return {
            "visible": True,
            "name": device.name or self.config.device_name,
            "address": device.address,
        }

    @staticmethod
    async def _write(client: BleakClient, letter: str) -> None:
        await client.write_gatt_char(WRITE_UUID, f"${letter}".encode(), response=False)

    async def _connected_client(self) -> BleakClient:
        device = await self.discover()
        client = BleakClient(device)
        await client.connect()
        return client

    async def single(self, command: str) -> None:
        if command not in COMMANDS:
            raise ValueError(f"Unsupported command: {command}")
        async with self._lock:
            client = await self._connected_client()
            try:
                await self._write(client, COMMANDS[command])
            finally:
                with suppress(Exception):
                    await client.disconnect()

    async def move(self, section: str, direction: str, duration: float) -> None:
        command = f"{section}_{direction}"
        if command not in COMMANDS:
            raise ValueError(f"Unsupported movement: {command}")
        duration = max(0.1, min(float(duration), 30.0))
        async with self._lock:
            client = await self._connected_client()
            try:
                loop = asyncio.get_running_loop()
                stop_at = loop.time() + duration
                while loop.time() < stop_at:
                    await asyncio.sleep(0.1)
                    await self._write(client, COMMANDS[command])
            finally:
                with suppress(Exception):
                    await client.disconnect()

    async def run_profile(
        self, *, home_wait: float, head: float, feet: float, extra: float
    ) -> None:
        values = {
            "head": max(0.0, min(float(head), 30.0)),
            "feet": max(0.0, min(float(feet), 30.0)),
            "extra": max(0.0, min(float(extra), 30.0)),
        }
        home_wait = max(8.0, min(float(home_wait), 45.0))
        async with self._lock:
            client = await self._connected_client()
            try:
                await self._write(client, COMMANDS["home"])
            finally:
                with suppress(Exception):
                    await client.disconnect()

            await asyncio.sleep(home_wait)
            client = await self._connected_client()
            try:
                loop = asyncio.get_running_loop()
                for section, duration in values.items():
                    if duration <= 0:
                        continue
                    stop_at = loop.time() + duration
                    while loop.time() < stop_at:
                        await asyncio.sleep(0.1)
                        await self._write(client, COMMANDS[f"{section}_up"])
                    await asyncio.sleep(0.25)
            finally:
                with suppress(Exception):
                    await client.disconnect()


def _json_body(request: web.Request) -> dict[str, Any]:
    body = request.get("json")
    if not isinstance(body, dict):
        raise web.HTTPBadRequest(text="Expected a JSON object")
    return body


@web.middleware
async def json_and_error_middleware(request: web.Request, handler):
    """Parse JSON once and return predictable JSON errors."""
    try:
        if request.can_read_body and request.content_type == "application/json":
            request["json"] = await request.json()
        return await handler(request)
    except web.HTTPException:
        raise
    except (ValueError, RuntimeError) as err:
        LOGGER.warning("Request failed: %s", err)
        return web.json_response({"ok": False, "error": str(err)}, status=400)
    except Exception as err:  # pragma: no cover - defensive server boundary
        LOGGER.exception("Unexpected bridge failure")
        return web.json_response({"ok": False, "error": str(err)}, status=500)


def create_app(config: BridgeConfig) -> web.Application:
    """Create the authenticated local bridge API."""
    config.validate()
    controller = BedController(config)

    @web.middleware
    async def auth_middleware(request: web.Request, handler):
        supplied = request.headers.get("Authorization", "")
        expected = f"Bearer {config.token}"
        if not secrets.compare_digest(supplied, expected):
            raise web.HTTPUnauthorized(text="Missing or invalid bearer token")
        return await handler(request)

    app = web.Application(middlewares=[json_and_error_middleware, auth_middleware])
    app["controller"] = controller

    async def health(_request: web.Request) -> web.Response:
        return web.json_response(
            {
                "ok": True,
                "service": "l2-motion-windows-bridge",
                "device_name": config.device_name,
                "last_address": controller.last_address,
            }
        )

    async def scan(_request: web.Request) -> web.Response:
        return web.json_response({"ok": True, **await controller.scan_status()})

    async def command(request: web.Request) -> web.Response:
        body = _json_body(request)
        await controller.single(str(body.get("command", "")))
        return web.json_response({"ok": True})

    async def move(request: web.Request) -> web.Response:
        body = _json_body(request)
        await controller.move(
            str(body.get("section", "")),
            str(body.get("direction", "")),
            float(body.get("duration", 0.5)),
        )
        return web.json_response({"ok": True})

    async def profile(request: web.Request) -> web.Response:
        body = _json_body(request)
        await controller.run_profile(
            home_wait=float(body.get("home_wait", 18)),
            head=float(body.get("head", 0)),
            feet=float(body.get("feet", 0)),
            extra=float(body.get("extra", 0)),
        )
        return web.json_response({"ok": True})

    app.router.add_get("/health", health)
    app.router.add_post("/scan", scan)
    app.router.add_post("/command", command)
    app.router.add_post("/move", move)
    app.router.add_post("/profile", profile)
    return app


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, help="Path to bridge JSON config")
    parser.add_argument("--token", help="Bearer token (prefer --config)")
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--device-name", default=DEFAULT_DEVICE_NAME)
    parser.add_argument("--address")
    parser.add_argument("--log-level", default="INFO")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    if args.config:
        config = BridgeConfig.from_json(args.config)
    else:
        config = BridgeConfig(
            token=args.token or "",
            host=args.host,
            port=args.port,
            device_name=args.device_name,
            address=args.address,
        )
    config.validate()
    LOGGER.info(
        "Starting L2 Motion bridge on %s:%s for %s",
        config.host,
        config.port,
        config.device_name,
    )
    web.run_app(create_app(config), host=config.host, port=config.port)


if __name__ == "__main__":
    main()
