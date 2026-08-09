"""Button entities for L2 Motion Bed."""

from __future__ import annotations

from dataclasses import dataclass

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DEVICE_NAME, DOMAIN
from .controller import L2MotionController


@dataclass(frozen=True, kw_only=True)
class L2ButtonDescription(ButtonEntityDescription):
    command: str | None = None
    section: str | None = None
    direction: str | None = None


BUTTONS = (
    L2ButtonDescription(key="home", name="Home / Flat", icon="mdi:bed-flat", command="home"),
    L2ButtonDescription(key="memory_1", name="Memory 1", icon="mdi:numeric-1-box", command="memory_1"),
    L2ButtonDescription(key="memory_2", name="Memory 2", icon="mdi:numeric-2-box", command="memory_2"),
    L2ButtonDescription(key="head_up", name="Head Up (0.5 seconds)", icon="mdi:arrow-up-bold", section="head", direction="up"),
    L2ButtonDescription(key="head_down", name="Head Down (0.5 seconds)", icon="mdi:arrow-down-bold", section="head", direction="down"),
    L2ButtonDescription(key="feet_up", name="Feet Up (0.5 seconds)", icon="mdi:arrow-up-bold", section="feet", direction="up"),
    L2ButtonDescription(key="feet_down", name="Feet Down (0.5 seconds)", icon="mdi:arrow-down-bold", section="feet", direction="down"),
    L2ButtonDescription(key="extra_up", name="Extra Up (0.5 seconds)", icon="mdi:arrow-up-bold", section="extra", direction="up"),
    L2ButtonDescription(key="extra_down", name="Extra Down (0.5 seconds)", icon="mdi:arrow-down-bold", section="extra", direction="down"),
    L2ButtonDescription(key="light", name="Toggle Under-bed Light", icon="mdi:lightbulb", command="light"),
    L2ButtonDescription(key="head_massage", name="Head Massage", icon="mdi:vibrate", command="head_massage"),
    L2ButtonDescription(key="foot_massage", name="Foot Massage", icon="mdi:vibrate", command="foot_massage"),
    L2ButtonDescription(key="stop_massage", name="Stop Massage", icon="mdi:stop", command="stop_massage"),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    controller: L2MotionController = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(L2MotionButton(controller, entry, description) for description in BUTTONS)


class L2MotionButton(ButtonEntity):
    """A one-shot or fixed-duration bed control."""

    _attr_has_entity_name = True

    def __init__(self, controller: L2MotionController, entry: ConfigEntry, description: L2ButtonDescription) -> None:
        self.controller = controller
        self.entity_description = description
        self._attr_unique_id = f"{entry.data[CONF_ADDRESS]}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.data[CONF_ADDRESS])},
            name="L2 Motion Bed",
            manufacturer="Leon's / HHC",
            model="D345",
        )

    async def async_press(self) -> None:
        description = self.entity_description
        if description.command:
            await self.controller.single(description.command)
        else:
            await self.controller.move(description.section, description.direction, 0.5)
