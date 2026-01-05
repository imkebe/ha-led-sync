"""MQTT helper/wrapper for the LG monitor integration."""

from __future__ import annotations

import asyncio
from contextlib import suppress
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
import random
import time
from typing import Any, Iterable, Tuple

from homeassistant.components import mqtt
from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_HS_COLOR,
    ATTR_RGB_COLOR,
    ATTR_TRANSITION,
)
from homeassistant.components.mqtt.models import ReceiveMessage
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import dispatcher
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.util import color as color_util
from homeassistant.util import dt as dt_util

from .const import (
    CONF_BRIGHTNESS_LEVELS,
    CONF_BRIGHTNESS_CUTOFF,
    CONF_BRIGHTNESS_GAIN,
    CONF_COMMAND_TOPIC,
    CONF_COMMAND_SPACING,
    CONF_CUTOFF_BLUE,
    CONF_CUTOFF_GREEN,
    CONF_CUTOFF_RED,
    CONF_ENABLE_STATE_SENSOR,
    CONF_GROUPS,
    CONF_LED_COUNT,
    CONF_LED_IN_TOPIC,
    CONF_LED_OUT_TOPIC,
    CONF_MODE,
    CONF_STATE_TOPIC,
    CONF_SYNC_INTERVAL,
    CONF_SATURATION_GAIN,
    CONF_TEMPERATURE_SHIFT,
    CONF_TRANSITION,
    DEFAULT_BRIGHTNESS_LEVELS,
    DEFAULT_BRIGHTNESS_CUTOFF,
    DEFAULT_BRIGHTNESS_GAIN,
    DEFAULT_COMMAND_TOPIC,
    DEFAULT_COMMAND_SPACING,
    DEFAULT_CUTOFF_BLUE,
    DEFAULT_CUTOFF_GREEN,
    DEFAULT_CUTOFF_RED,
    DEFAULT_LED_COUNT,
    DEFAULT_LED_IN_TOPIC,
    DEFAULT_LED_OUT_TOPIC,
    DEFAULT_MODE,
    DEFAULT_STATE_TOPIC,
    DEFAULT_SYNC_INTERVAL,
    DEFAULT_SATURATION_GAIN,
    DEFAULT_TEMPERATURE_SHIFT,
    DEFAULT_TRANSITION,
    DOMAIN,
    MODE_BROADCAST,
    MODE_LISTEN,
    SIGNAL_COMMAND,
    SIGNAL_GROUPS,
    SIGNAL_STATE_FRAME,
)


@dataclass(slots=True)
class LgFrameState:
    """Container describing the latest static LED frame."""

    colours: list[str]
    updated_at: datetime
    payload_len: int
    led_count: int


@dataclass(slots=True)
class LightGroup:
    """User-defined mapping between MQTT LEDs and HA lights."""

    name: str
    entities: list[str]
    led_indices: list[int]
    strategy: str


@dataclass(slots=True)
class LightServiceCommand:
    """Queued service call to reduce bursts."""

    service: str
    data: dict[str, Any]


class LgMonitorCoordinator:
    """Orchestrates MQTT publish/subscribe for this config entry."""

    def __init__(self, hass: HomeAssistant, entry) -> None:
        self.hass = hass
        self.entry = entry
        self._frame_unsub: Callable[[], None] | None = None
        self._state_listener_unsub: Callable[[], None] | None = None
        self._broadcast_pending: asyncio.Task | None = None
        self._command_worker: asyncio.Task | None = None
        self._command_lock = asyncio.Lock()
        self._command_queue: asyncio.Queue[str] = asyncio.Queue()
        self._queued_entities: set[str] = set()
        self._pending_light_commands: dict[str, LightServiceCommand] = {}
        self._frame: LgFrameState | None = None
        self._rgb_command: tuple[int, int, int] | None = None
        self._brightness_level: int | None = None
        self._command_topic = self._get_entry_value(CONF_COMMAND_TOPIC, DEFAULT_COMMAND_TOPIC)
        self._state_topic = self._get_entry_value(CONF_STATE_TOPIC, DEFAULT_STATE_TOPIC)
        self._led_in_topic = self._get_entry_value(CONF_LED_IN_TOPIC, DEFAULT_LED_IN_TOPIC)
        self._led_out_topic = self._get_entry_value(CONF_LED_OUT_TOPIC, DEFAULT_LED_OUT_TOPIC)
        self._led_count = self._get_entry_value(CONF_LED_COUNT, DEFAULT_LED_COUNT)
        self._brightness_levels = self._get_entry_value(
            CONF_BRIGHTNESS_LEVELS, DEFAULT_BRIGHTNESS_LEVELS
        )
        self._sync_interval = max(
            0.0, float(self._get_entry_value(CONF_SYNC_INTERVAL, DEFAULT_SYNC_INTERVAL))
        )
        self._command_spacing = max(
            0.0,
            float(self._get_entry_value(CONF_COMMAND_SPACING, DEFAULT_COMMAND_SPACING)),
        )
        self._transition = max(
            0.0, float(self._get_entry_value(CONF_TRANSITION, DEFAULT_TRANSITION))
        )
        self._brightness_cutoff = max(
            0,
            min(
                255,
                int(
                    self._get_entry_value(
                        CONF_BRIGHTNESS_CUTOFF, DEFAULT_BRIGHTNESS_CUTOFF
                    )
                ),
            ),
        )
        self._cutoff_red = max(
            0,
            min(255, int(self._get_entry_value(CONF_CUTOFF_RED, DEFAULT_CUTOFF_RED))),
        )
        self._cutoff_green = max(
            0,
            min(255, int(self._get_entry_value(CONF_CUTOFF_GREEN, DEFAULT_CUTOFF_GREEN))),
        )
        self._cutoff_blue = max(
            0,
            min(255, int(self._get_entry_value(CONF_CUTOFF_BLUE, DEFAULT_CUTOFF_BLUE))),
        )
        self._brightness_gain = max(
            0.0, float(self._get_entry_value(CONF_BRIGHTNESS_GAIN, DEFAULT_BRIGHTNESS_GAIN))
        )
        self._saturation_gain = max(
            0.0, float(self._get_entry_value(CONF_SATURATION_GAIN, DEFAULT_SATURATION_GAIN))
        )
        self._temperature_shift = max(
            -1.0,
            min(
                1.0,
                float(
                    self._get_entry_value(CONF_TEMPERATURE_SHIFT, DEFAULT_TEMPERATURE_SHIFT)
                ),
            ),
        )
        self._state_enabled = self._get_entry_value(CONF_ENABLE_STATE_SENSOR, True)
        self._mode = self._get_entry_value(CONF_MODE, DEFAULT_MODE)
        self._groups = self._normalise_groups(self._get_entry_value(CONF_GROUPS, []))
        self._command_signal = f"{SIGNAL_COMMAND}_{entry.entry_id}"
        self._state_signal = f"{SIGNAL_STATE_FRAME}_{entry.entry_id}"
        self._groups_signal = f"{SIGNAL_GROUPS}_{entry.entry_id}"
        self._group_rgb: list[tuple[int, int, int] | None] = [None] * len(self._groups)
        self._group_brightness: list[int | None] = [None] * len(self._groups)
        self._last_listen_update: list[float] = [0.0] * len(self._groups)
        self._last_broadcast_publish: float = 0.0
        self._last_groups_signal: float = 0.0

    def _get_entry_value(self, key: str, default: Any) -> Any:
        if key in self.entry.options:
            return self.entry.options[key]
        return self.entry.data.get(key, default)

    def _normalise_groups(self, raw: list[dict[str, Any]]) -> list[LightGroup]:
        groups: list[LightGroup] = []
        for idx, item in enumerate(raw or []):
            if not isinstance(item, dict):
                continue
            entities = [ent for ent in item.get("entities", []) if ent]
            led_indices = [int(v) for v in item.get("led_indices", []) if isinstance(v, int) and v >= 0]
            if not entities or not led_indices:
                continue
            name = item.get("name") or f"Group {idx + 1}"
            strategy = item.get("strategy") or "average"
            groups.append(
                LightGroup(
                    name=name,
                    entities=entities,
                    led_indices=sorted(set(led_indices)),
                    strategy=strategy,
                )
            )
        return groups

    @property
    def command_topic(self) -> str:
        return self._command_topic

    @property
    def state_topic(self) -> str:
        return self._state_topic

    @property
    def led_in_topic(self) -> str:
        return self._led_in_topic

    @property
    def led_out_topic(self) -> str:
        return self._led_out_topic

    @property
    def led_count(self) -> int:
        return self._led_count

    @property
    def brightness_levels(self) -> int:
        return max(1, self._brightness_levels)

    @property
    def sync_interval(self) -> float:
        return float(self._sync_interval)

    @property
    def command_spacing(self) -> float:
        return float(self._command_spacing)

    @property
    def transition(self) -> float:
        return float(self._transition)

    @property
    def brightness_cutoff(self) -> int:
        return int(self._brightness_cutoff)

    @property
    def cutoff_red(self) -> int:
        return int(self._cutoff_red)

    @property
    def cutoff_green(self) -> int:
        return int(self._cutoff_green)

    @property
    def cutoff_blue(self) -> int:
        return int(self._cutoff_blue)

    @property
    def brightness_gain(self) -> float:
        return float(self._brightness_gain)

    @property
    def saturation_gain(self) -> float:
        return float(self._saturation_gain)

    @property
    def temperature_shift(self) -> float:
        return float(self._temperature_shift)

    @property
    def state_enabled(self) -> bool:
        return bool(self._led_in_topic and self._state_enabled)

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def groups(self) -> list[LightGroup]:
        return list(self._groups)

    @property
    def frame_state(self) -> LgFrameState | None:
        return self._frame

    @property
    def last_rgb(self) -> tuple[int, int, int] | None:
        return self._rgb_command

    @property
    def last_brightness_level(self) -> int | None:
        return self._brightness_level

    @property
    def command_signal(self) -> str:
        return self._command_signal

    @property
    def state_signal(self) -> str:
        return self._state_signal

    @property
    def groups_signal(self) -> str:
        return self._groups_signal

    def group_rgb(self, group_index: int) -> tuple[int, int, int] | None:
        if group_index < 0 or group_index >= len(self._group_rgb):
            return None
        return self._group_rgb[group_index]

    def group_brightness(self, group_index: int) -> int | None:
        if group_index < 0 or group_index >= len(self._group_brightness):
            return None
        return self._group_brightness[group_index]

    async def async_set_group_colour(
        self,
        group_index: int,
        rgb: tuple[int, int, int],
        brightness: int | None = None,
    ) -> None:
        if group_index < 0 or group_index >= len(self._groups):
            return
        group = self._groups[group_index]
        for entity_id in group.entities:
            await self._call_light(entity_id, rgb, brightness=brightness, apply_calibration=False)
        self._set_group_state(group_index, rgb, brightness=brightness)
        self._dispatch_groups_signal(time.monotonic(), force=True)

    async def async_turn_off_group(self, group_index: int) -> None:
        if group_index < 0 or group_index >= len(self._groups):
            return
        group = self._groups[group_index]
        await self._turn_off_light(group.entities, transition=self._transition)
        self._set_group_state(group_index, (0, 0, 0), brightness=0)
        self._dispatch_groups_signal(time.monotonic(), force=True)

    async def async_setup(self) -> None:
        """Start listening for incoming frames and state changes."""
        if (self.state_enabled or self._mode == MODE_LISTEN) and not self._frame_unsub:
            topic = self._led_in_topic or self._state_topic
            if topic:
                self._frame_unsub = await mqtt.async_subscribe(
                    self.hass,
                    topic,
                    self._async_handle_frame,
                    qos=0,
                    encoding=None,
                )
        if self._mode == MODE_BROADCAST and self._groups:
            await self._setup_broadcast_listener()
            self._update_group_states_from_lights()
            self._dispatch_groups_signal(time.monotonic(), force=True)

    async def async_unload(self) -> None:
        """Tear down MQTT subscriptions."""
        if self._frame_unsub:
            self._frame_unsub()
            self._frame_unsub = None
        if self._state_listener_unsub:
            self._state_listener_unsub()
            self._state_listener_unsub = None
        if self._broadcast_pending and not self._broadcast_pending.done():
            self._broadcast_pending.cancel()
        self._broadcast_pending = None
        if self._command_worker and not self._command_worker.done():
            self._command_worker.cancel()
            with suppress(asyncio.CancelledError):
                await self._command_worker
        self._command_worker = None
        async with self._command_lock:
            self._pending_light_commands.clear()
            self._queued_entities.clear()
            while not self._command_queue.empty():
                with suppress(asyncio.QueueEmpty):
                    self._command_queue.get_nowait()
                    self._command_queue.task_done()
        self._frame = None
        self._group_rgb = []
        self._group_brightness = []
        self._last_listen_update = []

    def _ensure_command_worker(self) -> None:
        if self._command_worker and not self._command_worker.done():
            return
        self._command_worker = self.hass.async_create_task(self._async_command_worker())

    async def _queue_light_service(self, entity_id: str, command: LightServiceCommand) -> None:
        self._ensure_command_worker()
        async with self._command_lock:
            self._pending_light_commands[entity_id] = command
            if entity_id not in self._queued_entities:
                self._queued_entities.add(entity_id)
                self._command_queue.put_nowait(entity_id)

    async def _async_command_worker(self) -> None:
        try:
            while True:
                entity_id = await self._command_queue.get()
                try:
                    async with self._command_lock:
                        self._queued_entities.discard(entity_id)
                        command = self._pending_light_commands.pop(entity_id, None)
                    if not command:
                        continue
                    await self.hass.services.async_call(
                        "light", command.service, command.data, blocking=False
                    )
                    spacing = self._command_spacing
                    if spacing > 0:
                        await asyncio.sleep(spacing + random.uniform(0.0, spacing * 0.25))
                finally:
                    self._command_queue.task_done()
        except asyncio.CancelledError:
            return

    async def async_publish_colour(
        self,
        rgb: tuple[int, int, int],
        brightness: int | None = None,
    ) -> None:
        """Publish a Zen colour command to the configured topic."""
        payload: str
        r = max(0, min(255, int(rgb[0])))
        g = max(0, min(255, int(rgb[1])))
        b = max(0, min(255, int(rgb[2])))
        rgb_tuple: Tuple[int, int, int] = (r, g, b)
        hex_colour = "#%02x%02x%02x" % rgb_tuple
        brightness_level: int | None = None
        if brightness is not None:
            brightness_level = self._brightness_from_ha(brightness)
        if brightness_level is None:
            payload = hex_colour.lstrip("#")
        else:
            import json

            payload = json.dumps(
                {
                    "colour": hex_colour,
                    "brightness": brightness_level,
                }
            )
        await mqtt.async_publish(
            self.hass,
            self._command_topic,
            payload,
            qos=0,
            retain=False,
            encoding="utf-8",
        )
        self._rgb_command = rgb_tuple
        self._brightness_level = brightness_level
        dispatcher.async_dispatcher_send(self.hass, self._command_signal)

    async def async_turn_off(self) -> None:
        """Send a black frame to effectively switch LEDs off."""
        await self.async_publish_colour((0, 0, 0))

    async def _setup_broadcast_listener(self) -> None:
        targets = {entity for group in self._groups for entity in group.entities}
        if self._state_listener_unsub:
            self._state_listener_unsub()
            self._state_listener_unsub = None
        if not targets:
            return

        @callback
        def _state_change(_event) -> None:
            self._schedule_broadcast_publish()

        self._state_listener_unsub = async_track_state_change_event(
            self.hass, list(targets), _state_change
        )

    async def _async_handle_frame(self, msg: ReceiveMessage) -> None:
        payload = msg.payload
        if not payload:
            return
        buf = payload if isinstance(payload, (bytes, bytearray)) else payload.encode("utf-8")
        if len(buf) % 3 != 0:
            return
        colours: list[str] = []
        for idx in range(0, len(buf), 3):
            r, g, b = buf[idx], buf[idx + 1], buf[idx + 2]
            colours.append(f"{r:02x}{g:02x}{b:02x}")
        self._frame = LgFrameState(
            colours=colours,
            updated_at=dt_util.utcnow(),
            payload_len=len(buf),
            led_count=len(colours),
        )
        self._led_count = len(colours)
        dispatcher.async_dispatcher_send(self.hass, self._state_signal)
        await self._process_listen_groups(colours)

    def _brightness_from_ha(self, brightness: int) -> int:
        brightness = max(1, min(255, brightness))
        levels = max(1, self._brightness_levels)
        scaled = round(brightness / 255 * levels)
        return max(1, min(levels, scaled))

    def ha_brightness(self) -> int | None:
        if not self._brightness_level:
            return None
        levels = max(1, self._brightness_levels)
        value = round(self._brightness_level / levels * 255)
        return max(1, min(255, value))

    async def _process_listen_groups(self, colours: list[str]) -> None:
        if self._mode != MODE_LISTEN or not self._groups:
            return
        if not colours:
            return
        now = time.monotonic()
        interval = self._sync_interval
        rgb_frame = [self._hex_to_rgb(col) for col in colours]
        for group_index, group in enumerate(self._groups):
            led_indices = [idx for idx in group.led_indices if idx < len(rgb_frame)]
            if not led_indices:
                self._set_group_state(group_index, None)
                continue
            if group.strategy == "one_to_one":
                processed = [self.apply_calibration(rgb_frame[idx]) for idx in led_indices]
                group_colour = self._aggregate_colour(processed, "average")
                if group_colour is None:
                    self._set_group_state(group_index, None)
                else:
                    self._set_group_state_from_intensity(group_index, group_colour)
                if interval <= 0 or now - self._last_listen_update[group_index] >= interval:
                    self._last_listen_update[group_index] = now
                    for entity_id, colour in zip(group.entities, processed):
                        await self._call_light_intensity(entity_id, colour)
                continue
            subset = [rgb_frame[idx] for idx in led_indices]
            colour = self._aggregate_colour(subset, group.strategy)
            if not colour:
                self._set_group_state(group_index, None)
                continue
            processed_colour = self.apply_calibration(colour)
            self._set_group_state_from_intensity(group_index, processed_colour)
            if interval <= 0 or now - self._last_listen_update[group_index] >= interval:
                self._last_listen_update[group_index] = now
                for entity_id in group.entities:
                    await self._call_light_intensity(entity_id, processed_colour)
        self._dispatch_groups_signal(now)

    def _schedule_broadcast_publish(self) -> None:
        if self._broadcast_pending and not self._broadcast_pending.done():
            return
        self._broadcast_pending = self.hass.async_create_task(self._async_debounced_broadcast())

    async def _async_debounced_broadcast(self) -> None:
        interval = self._sync_interval
        if interval > 0:
            now = time.monotonic()
            delay = interval - (now - self._last_broadcast_publish)
            if delay > 0:
                await asyncio.sleep(delay)
        await self._publish_broadcast_frame()

    async def _publish_broadcast_frame(self) -> None:
        if self._mode != MODE_BROADCAST or not self._groups:
            return
        if not self._led_out_topic:
            return
        self._update_group_states_from_lights()
        now = time.monotonic()
        self._dispatch_groups_signal(now)
        frame = self._build_frame_from_groups()
        if not frame:
            return
        await self._publish_frame_bytes(frame)
        self._last_broadcast_publish = time.monotonic()

    def _build_frame_from_groups(self) -> list[str]:
        led_count = max(1, int(self._led_count))
        frame: list[str] = ["000000"] * led_count
        for group in self._groups:
            if not group.led_indices:
                continue
            if group.strategy == "one_to_one":
                for entity_id, led_idx in zip(group.entities, group.led_indices):
                    colour = self._get_entity_colour(entity_id)
                    if colour is None or led_idx >= led_count:
                        continue
                    frame[led_idx] = "%02x%02x%02x" % colour
                continue
            colours = [self._get_entity_colour(ent) for ent in group.entities]
            colours = [c for c in colours if c is not None]
            if not colours:
                continue
            colour = self._aggregate_colour(colours, group.strategy)
            if not colour:
                continue
            for led_idx in group.led_indices:
                if led_idx < led_count:
                    frame[led_idx] = "%02x%02x%02x" % colour
        return frame

    async def _publish_frame_bytes(self, frame: list[str]) -> None:
        try:
            payload = bytearray()
            for col in frame:
                payload.extend(bytes.fromhex(col))
        except Exception:
            return
        await mqtt.async_publish(
            self.hass,
            self._led_out_topic,
            bytes(payload),
            retain=False,
            qos=0,
            encoding=None,
        )

    def apply_calibration(self, rgb: tuple[int, int, int]) -> tuple[int, int, int]:
        """Apply user configured calibration before sending to lights."""
        r = max(0, min(255, int(rgb[0])))
        g = max(0, min(255, int(rgb[1])))
        b = max(0, min(255, int(rgb[2])))

        shift = self._temperature_shift
        if shift:
            if shift > 0:
                r = round(r * (1 + shift))
                b = round(b * (1 - shift))
            else:
                cool = abs(shift)
                r = round(r * (1 - cool))
                b = round(b * (1 + cool))
            r = max(0, min(255, int(r)))
            b = max(0, min(255, int(b)))

        h, s, v = color_util.color_RGB_to_hsv(r, g, b)
        s = max(0.0, min(100.0, s * self._saturation_gain))
        v = max(0.0, min(100.0, v * self._brightness_gain))
        r, g, b = color_util.color_hsv_to_RGB(h, s, v)

        if r < self._cutoff_red:
            r = 0
        if g < self._cutoff_green:
            g = 0
        if b < self._cutoff_blue:
            b = 0

        if self._brightness_cutoff and max(r, g, b) < self._brightness_cutoff:
            return (0, 0, 0)

        return (int(r), int(g), int(b))

    def _rgb_intensity_to_service(self, rgb: tuple[int, int, int]) -> tuple[tuple[int, int, int], int]:
        r = max(0, min(255, int(rgb[0])))
        g = max(0, min(255, int(rgb[1])))
        b = max(0, min(255, int(rgb[2])))
        brightness = max(r, g, b)
        if brightness <= 0:
            return (0, 0, 0), 0
        scale = 255 / brightness
        rgb_norm = (
            max(0, min(255, round(r * scale))),
            max(0, min(255, round(g * scale))),
            max(0, min(255, round(b * scale))),
        )
        return (int(rgb_norm[0]), int(rgb_norm[1]), int(rgb_norm[2])), int(brightness)

    async def _call_light(
        self,
        entity_id: str,
        colour: tuple[int, int, int],
        brightness: int | None = None,
        transition: float | None = None,
        *,
        apply_calibration: bool = True,
    ) -> None:
        if transition is None:
            transition = self._transition

        if apply_calibration:
            await self._call_light_intensity(
                entity_id, self.apply_calibration(colour), transition=transition
            )
            return

        if brightness is not None and int(brightness) <= 0:
            await self._turn_off_light(entity_id, transition=transition)
            return

        service_data = {"entity_id": entity_id, ATTR_RGB_COLOR: colour}
        if brightness is not None:
            service_data[ATTR_BRIGHTNESS] = max(0, min(255, int(brightness)))
        if transition and transition > 0:
            service_data[ATTR_TRANSITION] = float(transition)
        await self._queue_light_service(
            entity_id, LightServiceCommand(service="turn_on", data=service_data)
        )

    async def _call_light_intensity(
        self,
        entity_id: str,
        colour: tuple[int, int, int],
        *,
        transition: float | None = None,
    ) -> None:
        if transition is None:
            transition = self._transition

        rgb_norm, brightness = self._rgb_intensity_to_service(colour)
        if brightness <= 0:
            await self._turn_off_light(entity_id, transition=transition)
            return

        service_data = {
            "entity_id": entity_id,
            ATTR_RGB_COLOR: rgb_norm,
            ATTR_BRIGHTNESS: brightness,
        }
        if transition and transition > 0:
            service_data[ATTR_TRANSITION] = float(transition)
        await self._queue_light_service(
            entity_id, LightServiceCommand(service="turn_on", data=service_data)
        )

    async def _turn_off_light(
        self,
        entity_id: str | list[str],
        *,
        transition: float | None = None,
    ) -> None:
        if isinstance(entity_id, list):
            for ent in entity_id:
                await self._turn_off_light(ent, transition=transition)
            return

        data: dict[str, Any] = {"entity_id": entity_id}
        if transition and transition > 0:
            data[ATTR_TRANSITION] = float(transition)
        await self._queue_light_service(
            entity_id, LightServiceCommand(service="turn_off", data=data)
        )

    def _aggregate_colour(
        self, colours: Iterable[tuple[int, int, int]], strategy: str
    ) -> tuple[int, int, int] | None:
        colour_list = list(colours)
        if not colour_list:
            return None
        strategy = (strategy or "average").lower()
        if strategy == "random":
            return random.choice(colour_list)
        if strategy == "dominant":
            return max(colour_list, key=lambda c: sum(c))
        # default to average
        r = round(sum(c[0] for c in colour_list) / len(colour_list))
        g = round(sum(c[1] for c in colour_list) / len(colour_list))
        b = round(sum(c[2] for c in colour_list) / len(colour_list))
        return (r, g, b)

    def _rgb_to_brightness(self, colour: tuple[int, int, int]) -> int:
        return max(0, min(255, max(colour)))

    def _hex_to_rgb(self, colour: str) -> tuple[int, int, int]:
        colour = colour.strip().lstrip("#").lower().rjust(6, "0")
        try:
            return (int(colour[0:2], 16), int(colour[2:4], 16), int(colour[4:6], 16))
        except Exception:
            return (0, 0, 0)

    def _get_entity_colour(self, entity_id: str) -> tuple[int, int, int] | None:
        state = self.hass.states.get(entity_id)
        if not state:
            return None
        attrs = state.attributes
        if ATTR_RGB_COLOR in attrs:
            colour = attrs[ATTR_RGB_COLOR]
        elif ATTR_HS_COLOR in attrs:
            hs = attrs[ATTR_HS_COLOR]
            colour = color_util.color_hs_to_RGB(*hs)
        else:
            return None
        brightness = attrs.get(ATTR_BRIGHTNESS)
        if brightness is not None:
            scale = max(1, min(255, int(brightness))) / 255
            colour = tuple(max(0, min(255, round(c * scale))) for c in colour)
        try:
            return (int(colour[0]), int(colour[1]), int(colour[2]))
        except Exception:
            return None

    def _set_group_state(
        self,
        group_index: int,
        rgb: tuple[int, int, int] | None,
        brightness: int | None = None,
    ) -> None:
        if group_index < 0 or group_index >= len(self._group_rgb):
            return
        if rgb is None:
            self._group_rgb[group_index] = None
            self._group_brightness[group_index] = None
            return
        self._group_rgb[group_index] = (
            max(0, min(255, int(rgb[0]))),
            max(0, min(255, int(rgb[1]))),
            max(0, min(255, int(rgb[2]))),
        )
        if brightness is None:
            self._group_brightness[group_index] = self._rgb_to_brightness(rgb)
        else:
            self._group_brightness[group_index] = max(0, min(255, int(brightness)))

    def _set_group_state_from_intensity(
        self,
        group_index: int,
        rgb: tuple[int, int, int] | None,
    ) -> None:
        if group_index < 0 or group_index >= len(self._group_rgb):
            return
        if rgb is None:
            self._group_rgb[group_index] = None
            self._group_brightness[group_index] = None
            return
        rgb_norm, brightness = self._rgb_intensity_to_service(rgb)
        self._group_rgb[group_index] = rgb_norm
        self._group_brightness[group_index] = brightness

    def _update_group_states_from_lights(self) -> None:
        for group_index, group in enumerate(self._groups):
            colours = [self._get_entity_colour(ent) for ent in group.entities]
            colours = [c for c in colours if c is not None]
            if not colours:
                self._set_group_state(group_index, None)
                continue
            strategy = "average" if group.strategy == "one_to_one" else group.strategy
            colour = self._aggregate_colour(colours, strategy)
            if colour is None:
                self._set_group_state(group_index, None)
                continue
            self._set_group_state_from_intensity(group_index, colour)

    def _dispatch_groups_signal(self, now: float, *, force: bool = False) -> None:
        interval = self._sync_interval
        if force or interval <= 0 or now - self._last_groups_signal >= interval:
            self._last_groups_signal = now
            dispatcher.async_dispatcher_send(self.hass, self._groups_signal)
