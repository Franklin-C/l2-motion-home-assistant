"""L2 Motion Bed integration."""

from __future__ import annotations

import voluptuous as vol
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS, CONF_HOST, CONF_PORT, CONF_TOKEN
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import config_validation as cv

from .const import (
    CONF_CONNECTION_TYPE,
    CONNECTION_BLUETOOTH,
    CONNECTION_WINDOWS_BRIDGE,
    DOMAIN,
    PLATFORMS,
)
from .controller import L2MotionBridgeController, L2MotionController

MOVE_SCHEMA = vol.Schema({
    vol.Optional("config_entry_id"): cv.string,
    vol.Required("section"): vol.In(["head", "feet", "extra"]),
    vol.Required("direction"): vol.In(["up", "down"]),
    vol.Required("duration", default=0.5): vol.All(vol.Coerce(float), vol.Range(min=0.1, max=30)),
})

PROFILE_SCHEMA = vol.Schema({
    vol.Optional("config_entry_id"): cv.string,
    vol.Required("home_wait", default=18): vol.All(vol.Coerce(float), vol.Range(min=8, max=45)),
    vol.Required("head", default=0): vol.All(vol.Coerce(float), vol.Range(min=0, max=30)),
    vol.Required("feet", default=0): vol.All(vol.Coerce(float), vol.Range(min=0, max=30)),
    vol.Required("extra", default=0): vol.All(vol.Coerce(float), vol.Range(min=0, max=30)),
})

COMMAND_SCHEMA = vol.Schema({
    vol.Optional("config_entry_id"): cv.string,
    vol.Required("command"): vol.In([
        "home", "memory_1", "memory_2", "light",
        "head_massage", "foot_massage", "stop_massage",
    ]),
})


def _controller(
    hass: HomeAssistant, entry_id: str | None
) -> L2MotionController | L2MotionBridgeController:
    controllers = hass.data[DOMAIN]
    if entry_id:
        return controllers[entry_id]
    return next(iter(controllers.values()))


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    hass.data.setdefault(DOMAIN, {})

    async def move(call: ServiceCall) -> None:
        await _controller(hass, call.data.get("config_entry_id")).move(
            call.data["section"], call.data["direction"], call.data["duration"]
        )

    async def run_profile(call: ServiceCall) -> None:
        await _controller(hass, call.data.get("config_entry_id")).run_profile(
            home_wait=call.data["home_wait"],
            head=call.data["head"],
            feet=call.data["feet"],
            extra=call.data["extra"],
        )

    async def command(call: ServiceCall) -> None:
        await _controller(hass, call.data.get("config_entry_id")).single(
            call.data["command"]
        )

    hass.services.async_register(DOMAIN, "move", move, schema=MOVE_SCHEMA)
    hass.services.async_register(DOMAIN, "run_profile", run_profile, schema=PROFILE_SCHEMA)
    hass.services.async_register(DOMAIN, "command", command, schema=COMMAND_SCHEMA)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    connection_type = entry.data.get(CONF_CONNECTION_TYPE, CONNECTION_BLUETOOTH)
    if connection_type == CONNECTION_WINDOWS_BRIDGE:
        controller = L2MotionBridgeController(
            hass,
            entry.data[CONF_HOST],
            entry.data[CONF_PORT],
            entry.data[CONF_TOKEN],
        )
    else:
        controller = L2MotionController(hass, entry.data[CONF_ADDRESS])
    hass.data[DOMAIN][entry.entry_id] = controller
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id)
    return unloaded
