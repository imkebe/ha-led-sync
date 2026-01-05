"""Camera platform providing live preview of group LED mappings."""

from __future__ import annotations

from html import escape

from homeassistant.components.camera import Camera
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.util import dt as dt_util

from .const import DEFAULT_NAME, DOMAIN
from .coordinator import LgMonitorCoordinator, LightGroup


async def async_setup_entry(hass: HomeAssistant, entry, async_add_entities) -> None:
    """Set up preview cameras for each mapping group."""
    coordinator: LgMonitorCoordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [LgMonitorGroupPreviewCamera(coordinator, entry, idx, group) for idx, group in enumerate(coordinator.groups)]
    )


class LgMonitorGroupPreviewCamera(Camera):
    """Renders an SVG preview of a mapping group."""

    _attr_icon = "mdi:palette"
    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: LgMonitorCoordinator,
        entry,
        group_index: int,
        group: LightGroup,
    ) -> None:
        super().__init__()
        self._coordinator = coordinator
        self._entry = entry
        self._group_index = group_index
        self._group = group
        self._attr_unique_id = f"{entry.entry_id}_group_{group_index}_preview"
        self._attr_name = f"{group.name} preview"
        self.content_type = "image/svg+xml"
        self._attr_frame_interval = max(0.5, coordinator.sync_interval or 0.5)
        self._last_updated = dt_util.utcnow()

    async def async_camera_image(self, width: int | None = None, height: int | None = None) -> bytes:
        return self._render_svg().encode("utf-8")

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, self._coordinator.groups_signal, self._handle_group_update
            )
        )

    @callback
    def _handle_group_update(self) -> None:
        self._last_updated = dt_util.utcnow()
        self.async_write_ha_state()

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        colour_hex = self._group_colour_hex()
        return {
            "group_name": self._group.name,
            "strategy": self._group.strategy,
            "entities": list(self._group.entities),
            "led_indices": list(self._group.led_indices),
            "sync_interval": self._coordinator.sync_interval,
            "colour": colour_hex,
            "last_updated": self._last_updated.isoformat(),
        }

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._entry.entry_id)},
            manufacturer="LG",
            name=self._entry.title or DEFAULT_NAME,
            model="Monitor LED Controller",
        )

    def _group_colour_hex(self) -> str:
        rgb = self._coordinator.group_rgb(self._group_index)
        if not rgb:
            return "#000000"
        return "#%02x%02x%02x" % (rgb[0], rgb[1], rgb[2])

    def _render_svg(self) -> str:
        frame = self._coordinator.frame_state
        led_count = frame.led_count if frame else max(1, int(self._coordinator.led_count))
        colours = frame.colours if frame else ["000000"] * led_count

        highlight = set(self._group.led_indices)
        led_w = 10
        width = max(1, led_count) * led_w
        padding = 6
        bar_h = 14
        swatch_h = 20
        text_h = 16
        height = padding * 3 + bar_h + swatch_h + text_h

        rects: list[str] = []
        y_bar = padding
        for idx in range(led_count):
            x = idx * led_w
            if idx in highlight and idx < len(colours):
                fill = f"#{colours[idx]}"
            else:
                fill = "#111111"
            rects.append(
                f'<rect x="{x}" y="{y_bar}" width="{led_w}" height="{bar_h}" fill="{fill}" />'
            )

        colour_hex = self._group_colour_hex()
        y_swatch = y_bar + bar_h + padding
        y_text = y_swatch + swatch_h + padding + 12
        title = escape(f"{self._entry.title or DEFAULT_NAME} · {self._group.name}")

        return (
            '<?xml version="1.0" encoding="UTF-8"?>'
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}">'
            '<rect width="100%" height="100%" fill="#000000" />'
            + "".join(rects)
            + f'<rect x="0" y="{y_swatch}" width="{width}" height="{swatch_h}" fill="{colour_hex}" />'
            f'<text x="0" y="{y_text}" fill="#ffffff" font-size="14" font-family="sans-serif">{title}</text>'
            "</svg>"
        )
