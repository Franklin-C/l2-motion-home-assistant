"""Controllers for a local or Windows-bridged HHC D345 bed."""

from __future__ import annotations

import asyncio
from contextlib import suppress
from typing import Any

import aiohttp
from bleak import BleakClient
from bleak_retry_connector import establish_connection
from homeassistant.components.bluetooth import async_ble_device_from_address
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import COMMANDS, DEVICE_NAME, WRITE_UUID


class L2MotionController:
    """Serialize commands through Home Assistant Bluetooth or a proxy."""

    def __init__(self, hass: HomeAssistant, address: str) -> None:
        self.hass = hass
        self.address = address
        self.identifier = address
        self._lock = asyncio.Lock()
        self._client: BleakClient | None = None

    def _disconnected(self, client: BleakClient) -> None:
        """Forget a connection that the bed or proxy closed."""
        if self._client is client:
            self._client = None

    async def _connect(self) -> BleakClient:
        if self._client is not None and self._client.is_connected:
            return self._client

        self._client = None
        device = async_ble_device_from_address(
            self.hass, self.address, connectable=True
        )
        if device is None:
            raise HomeAssistantError(
                "The bed is not visible to Home Assistant Bluetooth. "
                "Move the Bluetooth adapter closer or add an ESPHome Bluetooth proxy."
            )
        try:
            client = await establish_connection(
                BleakClient,
                device,
                DEVICE_NAME,
                disconnected_callback=self._disconnected,
                max_attempts=3,
            )
            self._client = client
            # Android/ESPHome proxies can report connected before the write
            # characteristic is fully ready. The working web app naturally has
            # this pause between Connect and the first button press.
            await asyncio.sleep(0.25)
            return client
        except Exception as err:
            raise HomeAssistantError(
                f"Could not connect to the L2 Motion bed: {err}"
            ) from err

    async def _write(self, client: BleakClient, letter: str) -> None:
        try:
            await client.write_gatt_char(
                WRITE_UUID, f"${letter}".encode(), response=False
            )
        except Exception:
            if self._client is client:
                self._client = None
            with suppress(Exception):
                await client.disconnect()
            raise

    async def _stop_motion(self, client: BleakClient) -> None:
        """Reproduce the official app's five-write release sequence."""
        for _ in range(5):
            await self._write(client, "b")
            await asyncio.sleep(0.02)

    async def async_close(self) -> None:
        """Release the persistent GATT connection when the entry unloads."""
        async with self._lock:
            client, self._client = self._client, None
            if client is not None:
                with suppress(Exception):
                    await client.disconnect()

    async def single(self, command: str) -> None:
        letter = COMMANDS[command]
        async with self._lock:
            client = await self._connect()
            await self._write(client, letter)

    async def move(self, section: str, direction: str, duration: float) -> None:
        command = f"{section}_{direction}"
        if command not in COMMANDS:
            raise HomeAssistantError(f"Unsupported movement: {command}")
        duration = max(0.1, min(float(duration), 30.0))
        async with self._lock:
            client = await self._connect()
            try:
                loop = asyncio.get_running_loop()
                stop_at = loop.time() + duration
                while loop.time() < stop_at:
                    await self._write(client, COMMANDS[command])
                    await asyncio.sleep(0.1)
            finally:
                with suppress(Exception):
                    await self._stop_motion(client)

    async def run_profile(
        self,
        *,
        home_wait: float,
        head: float,
        feet: float,
        extra: float,
    ) -> None:
        values = {
            "head": max(0.0, min(float(head), 30.0)),
            "feet": max(0.0, min(float(feet), 30.0)),
            "extra": max(0.0, min(float(extra), 30.0)),
        }
        home_wait = max(8.0, min(float(home_wait), 45.0))
        async with self._lock:
            client = await self._connect()
            await self._write(client, COMMANDS["home"])

            await asyncio.sleep(home_wait)
            client = await self._connect()
            loop = asyncio.get_running_loop()
            for section, duration in values.items():
                if duration <= 0:
                    continue
                client = await self._connect()
                stop_at = loop.time() + duration
                try:
                    while loop.time() < stop_at:
                        await self._write(client, COMMANDS[f"{section}_up"])
                        await asyncio.sleep(0.1)
                finally:
                    with suppress(Exception):
                        await self._stop_motion(client)
                await asyncio.sleep(0.25)


class L2MotionBridgeController:
    """Send verified bed operations to the authenticated Windows bridge."""

    def __init__(
        self,
        hass: HomeAssistant,
        host: str,
        port: int,
        token: str,
    ) -> None:
        self.hass = hass
        self.host = host
        self.port = port
        self.token = token
        self.identifier = f"windows-bridge:{host}:{port}"
        self.address = self.identifier
        self._base_url = f"http://{host}:{port}"

    async def _request(
        self,
        path: str,
        data: dict[str, Any] | None = None,
        *,
        timeout: float = 30,
    ) -> dict[str, Any]:
        session = async_get_clientsession(self.hass)
        headers = {"Authorization": f"Bearer {self.token}"}
        try:
            async with session.post(
                f"{self._base_url}{path}",
                json=data or {},
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=timeout),
            ) as response:
                payload = await response.json(content_type=None)
                if response.status >= 400 or not payload.get("ok"):
                    raise HomeAssistantError(
                        payload.get("error")
                        or f"Bridge returned HTTP {response.status}"
                    )
                return payload
        except HomeAssistantError:
            raise
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as err:
            raise HomeAssistantError(
                f"Could not reach the L2 Motion Windows bridge at "
                f"{self.host}:{self.port}: {err}"
            ) from err

    async def single(self, command: str) -> None:
        await self._request("/command", {"command": command})

    async def move(self, section: str, direction: str, duration: float) -> None:
        duration = max(0.1, min(float(duration), 30.0))
        await self._request(
            "/move",
            {"section": section, "direction": direction, "duration": duration},
            timeout=duration + 20,
        )

    async def run_profile(
        self,
        *,
        home_wait: float,
        head: float,
        feet: float,
        extra: float,
    ) -> None:
        await self._request(
            "/profile",
            {
                "home_wait": home_wait,
                "head": head,
                "feet": feet,
                "extra": extra,
            },
            timeout=float(home_wait)
            + float(head)
            + float(feet)
            + float(extra)
            + 30,
        )
