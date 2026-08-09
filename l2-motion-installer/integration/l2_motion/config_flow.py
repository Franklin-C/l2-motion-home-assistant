"""Config flow for L2 Motion Bed."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.components.bluetooth import async_discovered_service_info
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ADDRESS

from .const import DEVICE_NAME, DOMAIN


class L2MotionConfigFlow(ConfigFlow, domain=DOMAIN):
    """Configure the discovered bed by Bluetooth address."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        discovered = {
            info.address: f"{info.name or DEVICE_NAME} ({info.address})"
            for info in async_discovered_service_info(self.hass, connectable=True)
            if (info.name or "").upper().startswith(DEVICE_NAME)
        }

        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            await self.async_set_unique_id(address)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=DEVICE_NAME,
                data={CONF_ADDRESS: address},
            )

        if not discovered:
            return self.async_abort(reason="not_found")

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_ADDRESS): vol.In(discovered)}
            ),
        )
