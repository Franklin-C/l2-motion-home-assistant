"""Config flow for L2 Motion Bed."""

from __future__ import annotations

import asyncio
from typing import Any

import aiohttp
import voluptuous as vol
from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ADDRESS, CONF_HOST, CONF_PORT, CONF_TOKEN
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    CONF_CONNECTION_TYPE,
    CONNECTION_BLUETOOTH,
    CONNECTION_WINDOWS_BRIDGE,
    DEFAULT_BRIDGE_PORT,
    DEVICE_NAME,
    DOMAIN,
)


class L2MotionConfigFlow(ConfigFlow, domain=DOMAIN):
    """Configure the bed through HA Bluetooth or the Windows bridge."""

    VERSION = 2
    _address: str | None = None

    @staticmethod
    def _is_exact_bed(info: BluetoothServiceInfoBleak) -> bool:
        names = {
            info.name,
            getattr(info, "local_name", None),
            getattr(getattr(info, "advertisement", None), "local_name", None),
        }
        return DEVICE_NAME in {
            str(name).strip().upper() for name in names if name
        }

    async def _async_finish_bluetooth(self, address: str) -> ConfigFlowResult:
        await self.async_set_unique_id(address)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=DEVICE_NAME,
            data={
                CONF_CONNECTION_TYPE: CONNECTION_BLUETOOTH,
                CONF_ADDRESS: address,
            },
        )

    async def _async_finish_bridge(
        self, user_input: dict[str, Any]
    ) -> ConfigFlowResult:
        host = str(user_input[CONF_HOST]).strip()
        port = int(user_input[CONF_PORT])
        token = str(user_input[CONF_TOKEN]).strip()
        session = async_get_clientsession(self.hass)
        try:
            async with session.get(
                f"http://{host}:{port}/health",
                headers={"Authorization": f"Bearer {token}"},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                payload = await response.json(content_type=None)
                if response.status >= 400 or not payload.get("ok"):
                    raise ValueError("Bridge rejected the connection")
        except (aiohttp.ClientError, asyncio.TimeoutError, ValueError):
            return self.async_show_form(
                step_id="user",
                data_schema=self._user_schema(user_input),
                errors={"base": "cannot_connect"},
            )

        await self.async_set_unique_id(f"windows-bridge:{host}:{port}")
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=f"{DEVICE_NAME} via {host}",
            data={
                CONF_CONNECTION_TYPE: CONNECTION_WINDOWS_BRIDGE,
                CONF_HOST: host,
                CONF_PORT: port,
                CONF_TOKEN: token,
            },
        )

    @staticmethod
    def _user_schema(defaults: dict[str, Any] | None = None) -> vol.Schema:
        defaults = defaults or {}
        return vol.Schema(
            {
                vol.Required(
                    CONF_CONNECTION_TYPE,
                    default=defaults.get(
                        CONF_CONNECTION_TYPE, CONNECTION_WINDOWS_BRIDGE
                    ),
                ): vol.In(
                    {
                        CONNECTION_WINDOWS_BRIDGE: "Windows bridge",
                        CONNECTION_BLUETOOTH: "Home Assistant Bluetooth",
                    }
                ),
                vol.Optional(
                    CONF_HOST, default=defaults.get(CONF_HOST, "")
                ): str,
                vol.Optional(
                    CONF_PORT,
                    default=defaults.get(CONF_PORT, DEFAULT_BRIDGE_PORT),
                ): vol.All(vol.Coerce(int), vol.Range(min=1, max=65535)),
                vol.Optional(
                    CONF_TOKEN, default=defaults.get(CONF_TOKEN, "")
                ): str,
            }
        )

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        if not discovery_info.connectable or not self._is_exact_bed(discovery_info):
            return self.async_abort(reason="not_supported")
        self._address = discovery_info.address
        await self.async_set_unique_id(self._address)
        self._abort_if_unique_id_configured()
        self.context["title_placeholders"] = {"name": DEVICE_NAME}
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None and self._address:
            return await self._async_finish_bluetooth(self._address)
        return self.async_show_form(
            step_id="bluetooth_confirm",
            description_placeholders={"name": DEVICE_NAME},
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is None:
            return self.async_show_form(
                step_id="user", data_schema=self._user_schema()
            )

        if user_input[CONF_CONNECTION_TYPE] == CONNECTION_WINDOWS_BRIDGE:
            if not str(user_input.get(CONF_HOST, "")).strip():
                return self.async_show_form(
                    step_id="user",
                    data_schema=self._user_schema(user_input),
                    errors={CONF_HOST: "required"},
                )
            if len(str(user_input.get(CONF_TOKEN, "")).strip()) < 24:
                return self.async_show_form(
                    step_id="user",
                    data_schema=self._user_schema(user_input),
                    errors={CONF_TOKEN: "invalid_token"},
                )
            return await self._async_finish_bridge(user_input)

        active_scan = getattr(bluetooth, "async_request_active_scan", None)
        if active_scan is not None:
            await active_scan(self.hass)

        discovered = {
            info.address: f"{info.name or DEVICE_NAME} ({info.address})"
            for info in bluetooth.async_discovered_service_info(
                self.hass, connectable=True
            )
            if self._is_exact_bed(info)
        }
        if not discovered:
            if (
                "bluetooth" not in self.hass.config.components
                and not self.hass.config_entries.async_entries("bluetooth")
            ):
                return self.async_abort(reason="bluetooth_unavailable")
            return self.async_abort(reason="not_found")
        return self.async_show_form(
            step_id="bluetooth_select",
            data_schema=vol.Schema(
                {vol.Required(CONF_ADDRESS): vol.In(discovered)}
            ),
        )

    async def async_step_bluetooth_select(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return await self._async_finish_bluetooth(user_input[CONF_ADDRESS])
        return self.async_abort(reason="not_found")
