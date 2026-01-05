"""Sensor platform exposing the static LED frames."""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DEFAULT_NAME, DOMAIN
from .coordinator import LgMonitorCoordinator


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities) -> None:
    """Set up the sensor if state publishing is enabled."""
    coordinator: LgMonitorCoordinator = hass.data[DOMAIN][entry.entry_id]
    if not coordinator.state_enabled:
        return
    async_add_entities([LgMonitorFrameSensor(coordinator, entry)])


class LgMonitorFrameSensor(SensorEntity):
    """Represents the raw 48-LED frame emitted by the tray app."""

    _attr_icon = "mdi:led-strip-variant"
    _attr_native_unit_of_measurement = "LEDs"
    _attr_has_entity_name = True

    def __init__(self, coordinator: LgMonitorCoordinator, entry) -> None:
        self._coordinator = coordinator
        self._entry = entry
        self._attr_name = f"{entry.title} LED frame"
        self._attr_unique_id = f"{entry.entry_id}_frame"

    @property
    def native_value(self) -> int | None:
        frame = self._coordinator.frame_state
        if not frame:
            return None
        return len(frame.colours)

    @property
    def extra_state_attributes(self) -> dict[str, object] | None:
        frame = self._coordinator.frame_state
        if not frame:
            return None
        return {
            "led_frame": frame.colours,
            "updated_at": frame.updated_at.isoformat() if frame.updated_at else None,
            "payload_length": frame.payload_len,
            "led_count": frame.led_count,
        }

    @property
    def available(self) -> bool:
        return self._coordinator.state_enabled

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            manufacturer="LG",
            name=self._entry.title or DEFAULT_NAME,
            model="Monitor LED Controller",
        )

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, self._coordinator.state_signal, self._handle_state
            )
        )

    @callback
    def _handle_state(self) -> None:
        self.async_write_ha_state()
