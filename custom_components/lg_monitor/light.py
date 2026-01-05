"""Light platform for controlling LG monitor Zen mode."""

from __future__ import annotations

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_HS_COLOR,
    ATTR_RGB_COLOR,
    ColorMode,
    LightEntity,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.util import color as color_util

from .const import DEFAULT_NAME, DOMAIN
from .coordinator import LgMonitorCoordinator


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities) -> None:
    """Create the Zen light entity for this entry."""
    coordinator: LgMonitorCoordinator = hass.data[DOMAIN][entry.entry_id]
    entities: list[LightEntity] = [LgMonitorZenLight(coordinator, entry)]
    for idx, group in enumerate(coordinator.groups):
        entities.append(LgMonitorGroupLight(coordinator, entry, idx, group))
    async_add_entities(entities)


class LgMonitorZenLight(LightEntity):
    """Expose the Zen mode as a light entity."""

    _attr_supported_color_modes = {ColorMode.RGB}
    _attr_color_mode = ColorMode.RGB
    _attr_has_entity_name = True
    _attr_assumed_state = True

    def __init__(self, coordinator: LgMonitorCoordinator, entry) -> None:
        self._coordinator = coordinator
        self._entry = entry
        title = entry.title or DEFAULT_NAME
        self._attr_name = f"{title} Zen"
        self._attr_unique_id = f"{entry.entry_id}_zen"

    @property
    def is_on(self) -> bool:
        rgb = self._coordinator.last_rgb
        if not rgb:
            return False
        return any(component > 0 for component in rgb)

    @property
    def rgb_color(self) -> tuple[int, int, int] | None:
        return self._coordinator.last_rgb

    @property
    def brightness(self) -> int | None:
        return self._coordinator.ha_brightness()

    async def async_turn_on(self, **kwargs) -> None:
        rgb = kwargs.get(ATTR_RGB_COLOR)
        if not rgb and (hs := kwargs.get(ATTR_HS_COLOR)):
            rgb = color_util.color_hs_to_RGB(*hs)
        if not rgb:
            rgb = self._coordinator.last_rgb or (255, 255, 255)
        brightness = kwargs.get(ATTR_BRIGHTNESS, self.brightness)
        await self._coordinator.async_publish_colour(rgb, brightness)

    async def async_turn_off(self, **kwargs) -> None:
        await self._coordinator.async_turn_off()

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, self._coordinator.command_signal, self._handle_command
            )
        )

    @callback
    def _handle_command(self) -> None:
        self.async_write_ha_state()

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            manufacturer="LG",
            name=self._entry.title or DEFAULT_NAME,
            model="Monitor LED Controller",
        )


class LgMonitorGroupLight(LightEntity):
    """Virtual light entity representing a mapping group."""

    _attr_supported_color_modes = {ColorMode.RGB}
    _attr_color_mode = ColorMode.RGB
    _attr_has_entity_name = True
    _attr_assumed_state = True

    def __init__(
        self,
        coordinator: LgMonitorCoordinator,
        entry,
        group_index: int,
        group,
    ) -> None:
        self._coordinator = coordinator
        self._entry = entry
        self._group_index = group_index
        self._group = group
        self._attr_name = getattr(group, "name", f"Group {group_index + 1}")
        self._attr_unique_id = f"{entry.entry_id}_group_{group_index}"

    @property
    def is_on(self) -> bool:
        rgb = self._coordinator.group_rgb(self._group_index)
        if not rgb:
            return False
        return any(component > 0 for component in rgb)

    @property
    def rgb_color(self) -> tuple[int, int, int] | None:
        return self._coordinator.group_rgb(self._group_index)

    @property
    def brightness(self) -> int | None:
        return self._coordinator.group_brightness(self._group_index)

    async def async_turn_on(self, **kwargs) -> None:
        rgb = kwargs.get(ATTR_RGB_COLOR)
        if not rgb and (hs := kwargs.get(ATTR_HS_COLOR)):
            rgb = color_util.color_hs_to_RGB(*hs)
        if not rgb:
            rgb = self.rgb_color or (255, 255, 255)
        brightness = kwargs.get(ATTR_BRIGHTNESS)
        await self._coordinator.async_set_group_colour(self._group_index, rgb, brightness=brightness)

    async def async_turn_off(self, **kwargs) -> None:
        await self._coordinator.async_turn_off_group(self._group_index)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, self._coordinator.groups_signal, self._handle_group_update
            )
        )

    @callback
    def _handle_group_update(self) -> None:
        self.async_write_ha_state()

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        return {
            "group_name": getattr(self._group, "name", None),
            "strategy": getattr(self._group, "strategy", None),
            "entities": list(getattr(self._group, "entities", []) or []),
            "led_indices": list(getattr(self._group, "led_indices", []) or []),
        }

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            manufacturer="LG",
            name=self._entry.title or DEFAULT_NAME,
            model="Monitor LED Controller",
        )
