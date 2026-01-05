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
    entities: list[Camera] = [LgMonitorCalibrationChartCamera(coordinator, entry)]
    entities.extend(
        [
            LgMonitorGroupPreviewCamera(coordinator, entry, idx, group)
            for idx, group in enumerate(coordinator.groups)
        ]
    )
    async_add_entities(entities)


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
            "transition": self._coordinator.transition,
            "brightness_cutoff": self._coordinator.brightness_cutoff,
            "cutoff_red": self._coordinator.cutoff_red,
            "cutoff_green": self._coordinator.cutoff_green,
            "cutoff_blue": self._coordinator.cutoff_blue,
            "brightness_gain": self._coordinator.brightness_gain,
            "saturation_gain": self._coordinator.saturation_gain,
            "temperature_shift": self._coordinator.temperature_shift,
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
        brightness = self._coordinator.group_brightness(self._group_index) or 0
        if brightness <= 0:
            return "#000000"
        scale = max(0.0, min(1.0, brightness / 255))
        return "#%02x%02x%02x" % (
            round(rgb[0] * scale),
            round(rgb[1] * scale),
            round(rgb[2] * scale),
        )

    def _render_svg(self) -> str:
        frame = self._coordinator.frame_state
        led_count = frame.led_count if frame else max(1, int(self._coordinator.led_count))
        colours = frame.colours if frame else ["000000"] * led_count

        highlight = set(self._group.led_indices)
        led_w = 10
        width = max(1, led_count) * led_w
        padding = 6
        bar_h = 14
        bar_gap = 4
        swatch_h = 20
        text_h = 16
        height = padding * 4 + bar_h * 2 + bar_gap + swatch_h + text_h

        rects: list[str] = []
        y_raw = padding
        y_processed = y_raw + bar_h + bar_gap
        for idx in range(led_count):
            x = idx * led_w
            if idx in highlight and idx < len(colours):
                fill = f"#{colours[idx]}"
            else:
                fill = "#111111"
            rects.append(
                f'<rect x="{x}" y="{y_raw}" width="{led_w}" height="{bar_h}" fill="{fill}" />'
            )

            if idx in highlight and idx < len(colours):
                raw = colours[idx]
                try:
                    rgb = (int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16))
                except Exception:
                    rgb = (0, 0, 0)
                processed = self._coordinator.apply_calibration(rgb)
                processed_fill = "#%02x%02x%02x" % processed
            else:
                processed_fill = "#111111"
            rects.append(
                f'<rect x="{x}" y="{y_processed}" width="{led_w}" height="{bar_h}" fill="{processed_fill}" />'
            )

        colour_hex = self._group_colour_hex()
        y_swatch = y_processed + bar_h + padding
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


class LgMonitorCalibrationChartCamera(Camera):
    """Renders an SVG chart of the current calibration settings."""

    _attr_icon = "mdi:chart-line"
    _attr_has_entity_name = True

    def __init__(self, coordinator: LgMonitorCoordinator, entry) -> None:
        super().__init__()
        self._coordinator = coordinator
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_calibration_chart"
        self._attr_name = "Calibration chart"
        self.content_type = "image/svg+xml"
        self._attr_frame_interval = max(0.5, coordinator.sync_interval or 0.5)
        self._last_updated = dt_util.utcnow()

    async def async_camera_image(self, width: int | None = None, height: int | None = None) -> bytes:
        return self._render_svg().encode("utf-8")

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, self._coordinator.groups_signal, self._handle_update
            )
        )

    @callback
    def _handle_update(self) -> None:
        self._last_updated = dt_util.utcnow()
        self.async_write_ha_state()

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        return {
            "sync_interval": self._coordinator.sync_interval,
            "transition": self._coordinator.transition,
            "brightness_cutoff": self._coordinator.brightness_cutoff,
            "cutoff_red": self._coordinator.cutoff_red,
            "cutoff_green": self._coordinator.cutoff_green,
            "cutoff_blue": self._coordinator.cutoff_blue,
            "brightness_gain": self._coordinator.brightness_gain,
            "saturation_gain": self._coordinator.saturation_gain,
            "temperature_shift": self._coordinator.temperature_shift,
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

    def _curve(self, rgb: tuple[int, int, int], step: int = 4) -> str:
        points: list[str] = []
        for x in range(0, 256, step):
            base = (rgb[0] * x // 255, rgb[1] * x // 255, rgb[2] * x // 255)
            out = self._coordinator.apply_calibration(base)
            y = max(out)
            points.append(f"{x},{255 - y}")
        out = self._coordinator.apply_calibration(rgb)
        points.append(f"255,{255 - max(out)}")
        return " ".join(points)

    def _render_svg(self) -> str:
        pad_l = 40
        pad_t = 20
        chart_w = 256
        chart_h = 160
        width = pad_l + chart_w + 12
        height = pad_t + chart_h + 40

        title = escape(self._entry.title or DEFAULT_NAME)

        cutoff = self._coordinator.brightness_cutoff
        cutoff_y = pad_t + (255 - cutoff) / 255 * chart_h

        def _translate_points(points: str) -> str:
            out: list[str] = []
            for pair in points.split():
                x_s, y_s = pair.split(",")
                x = pad_l + (int(x_s) / 255) * chart_w
                y = pad_t + (int(y_s) / 255) * chart_h
                out.append(f"{x:.1f},{y:.1f}")
            return " ".join(out)

        red = _translate_points(self._curve((255, 0, 0)))
        green = _translate_points(self._curve((0, 255, 0)))
        blue = _translate_points(self._curve((0, 0, 255)))

        gain_line = (
            f"gain={self._coordinator.brightness_gain:.2f} "
            f"sat={self._coordinator.saturation_gain:.2f} "
            f"temp={self._coordinator.temperature_shift:.2f}"
        )

        return (
            '<?xml version="1.0" encoding="UTF-8"?>'
            f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}">'
            '<rect width="100%" height="100%" fill="#000000" />'
            f'<text x="{pad_l}" y="14" fill="#ffffff" font-size="14" font-family="sans-serif">{title} · calibration</text>'
            f'<rect x="{pad_l}" y="{pad_t}" width="{chart_w}" height="{chart_h}" fill="#0b0b0b" stroke="#444" />'
            + (
                f'<line x1="{pad_l}" y1="{cutoff_y:.1f}" x2="{pad_l + chart_w}" y2="{cutoff_y:.1f}" '
                'stroke="#666" stroke-dasharray="4 4" />'
                if cutoff > 0
                else ""
            )
            + f'<polyline points="{red}" fill="none" stroke="#ff4040" stroke-width="2" />'
            + f'<polyline points="{green}" fill="none" stroke="#40ff40" stroke-width="2" />'
            + f'<polyline points="{blue}" fill="none" stroke="#4040ff" stroke-width="2" />'
            f'<text x="{pad_l}" y="{pad_t + chart_h + 22}" fill="#cccccc" font-size="12" font-family="sans-serif">'
            f"cutoff={cutoff}  {escape(gain_line)}"
            "</text>"
            "</svg>"
        )
