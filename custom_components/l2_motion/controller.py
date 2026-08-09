"""Bluetooth controller for an HHC D345 / L2 Motion bed."""

from __future__ import annotations

import asyncio
from contextlib import suppress

from bleak import BleakClient
from bleak_retry_connector import establish_connection
from homeassistant.components.bluetooth import async_ble_device_from_address
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .const import COMMANDS, DEVICE_NAME, WRITE_UUID


class L2MotionController:
    """Serialize commands and reconnect through HA Bluetooth or a proxy."""

    def __init__(self, hass: HomeAssistant, address: str) -> None:
        self.hass = hass
        self.address = address
        self._lock = asyncio.Lock()

    async def _connect(self) -> BleakClient:
        device = async_ble_device_from_address(
            self.hass, self.address, connectable=True
        )
        if device is None:
            raise HomeAssistantError(
                "The bed is not visible to Home Assistant Bluetooth. "
                "Move the Bluetooth adapter closer or add an ESPHome Bluetooth proxy."
            )
        try:
            return await establish_connection(
                BleakClient,
                device,
                DEVICE_NAME,
                max_attempts=3,
            )
        except Exception as err:
            raise HomeAssistantError(f"Could not connect to the L2 Motion bed: {err}") from err

    @staticmethod
    async def _write(client: BleakClient, letter: str) -> None:
        await client.write_gatt_char(WRITE_UUID, f"${letter}".encode(), response=False)

    async def single(self, command: str) -> None:
        """Send a one-shot command such as Home or Memory."""
        letter = COMMANDS[command]
        async with self._lock:
            client = await self._connect()
            try:
                await self._write(client, letter)
            finally:
                with suppress(Exception):
                    await client.disconnect()

    async def move(self, section: str, direction: str, duration: float) -> None:
        """Repeat a motor command at the D345 app's 100 ms cadence."""
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
                    await asyncio.sleep(0.1)
                    await self._write(client, COMMANDS[command])
            finally:
                # D345 has no motor-stop packet. Ceasing writes is the stop action.
                with suppress(Exception):
                    await client.disconnect()

    async def run_profile(
        self,
        *,
        home_wait: float,
        head: float,
        feet: float,
        extra: float,
    ) -> None:
        """Home first, then reproduce a position using timed upward movement."""
        values = {
            "head": max(0.0, min(float(head), 30.0)),
            "feet": max(0.0, min(float(feet), 30.0)),
            "extra": max(0.0, min(float(extra), 30.0)),
        }
        home_wait = max(8.0, min(float(home_wait), 45.0))
        async with self._lock:
            client = await self._connect()
            try:
                await self._write(client, COMMANDS["home"])
            finally:
                with suppress(Exception):
                    await client.disconnect()

            # Home is a one-shot full-travel command. Reconnect only after it finishes.
            await asyncio.sleep(home_wait)
            client = await self._connect()
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
