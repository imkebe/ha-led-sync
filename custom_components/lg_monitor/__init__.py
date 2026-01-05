"""Home Assistant integration for the LG monitor Zen lights."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, PLATFORMS


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the LG monitor component (placeholder for config entries)."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Create configured entities and MQTT subscriptions."""
    from .coordinator import LgMonitorCoordinator

    hass.data.setdefault(DOMAIN, {})
    coordinator = LgMonitorCoordinator(hass, entry)
    await coordinator.async_setup()
    hass.data[DOMAIN][entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    from .coordinator import LgMonitorCoordinator

    coordinator: LgMonitorCoordinator | None = hass.data[DOMAIN].pop(entry.entry_id, None)
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if coordinator:
        await coordinator.async_unload()
    return unload_ok
