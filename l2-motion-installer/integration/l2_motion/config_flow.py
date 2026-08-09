"""Config flow for L2 Motion Bed."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.components import bluetooth
from homeassistant.components.bluetooth import BluetoothServiceInfoBleak
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ADDRESS

from .const import DEVICE_NAME, DOMAIN


class L2MotionConfigFlow(ConfigFlow, domain=DOMAIN):
    """Configure the discovered bed by Bluetooth address."""

    VERSION = 1
    _address: str | None = None

    @staticmethod
    def _is_exact_bed(info: BluetoothServiceInfoBleak) -> bool:
        """Match the exact local name used by the verified bed controller."""
        names = {
            info.name,
            getattr(info, "local_name", None),
            getattr(getattr(info, "advertisement", None), "local_name", None),
        }
        return DEVICE_NAME in {str(name).strip().upper() for name in names if name}

    async def _async_finish(self, address: str) -> ConfigFlowResult:
        await self.async_set_unique_id(address)
        self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=DEVICE_NAME,
            data={CONF_ADDRESS: address},
        )

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handle exact-name automatic Bluetooth discovery."""
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
        """Confirm a discovered bed before adding it."""
        if user_input is not None and self._address:
            return await self._async_finish(self._address)
        return self.async_show_form(
            step_id="bluetooth_confirm",
            description_placeholders={"name": DEVICE_NAME},
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
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

        if user_input is not None:
            return await self._async_finish(user_input[CONF_ADDRESS])

        if not discovered:
            if (
                "bluetooth" not in self.hass.config.components
                and not self.hass.config_entries.async_entries("bluetooth")
            ):
                return self.async_abort(reason="bluetooth_unavailable")
            return self.async_abort(reason="not_found")

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_ADDRESS): vol.In(discovered)}
            ),
        )
