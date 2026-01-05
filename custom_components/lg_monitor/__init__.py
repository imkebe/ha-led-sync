"""Home Assistant integration for the LG monitor Zen lights."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DEFAULT_NAME, DOMAIN, PLATFORMS


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the LG monitor component (placeholder for config entries)."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Create configured entities and MQTT subscriptions."""
    from .coordinator import LgMonitorCoordinator

    if not entry.title or not entry.title.strip():
        hass.config_entries.async_update_entry(entry, title=DEFAULT_NAME)

    hass.data.setdefault(DOMAIN, {})
    coordinator = LgMonitorCoordinator(hass, entry)
    await coordinator.async_setup()
    hass.data[DOMAIN][entry.entry_id] = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    from .coordinator import LgMonitorCoordinator

    coordinator: LgMonitorCoordinator | None = hass.data[DOMAIN].pop(entry.entry_id, None)
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if coordinator:
        await coordinator.async_unload()
    return unload_ok


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options updates by reloading the config entry."""
    await hass.config_entries.async_reload(entry.entry_id)
