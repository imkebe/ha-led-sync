"""Configuration flow for the LG monitor integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers import selector

from .const import (
    CONF_BRIGHTNESS_LEVELS,
    CONF_COMMAND_TOPIC,
    CONF_ENABLE_STATE_SENSOR,
    CONF_GROUPS,
    CONF_LED_COUNT,
    CONF_LED_IN_TOPIC,
    CONF_LED_OUT_TOPIC,
    CONF_MODE,
    CONF_STATE_TOPIC,
    DEFAULT_BRIGHTNESS_LEVELS,
    DEFAULT_COMMAND_TOPIC,
    DEFAULT_LED_COUNT,
    DEFAULT_LED_IN_TOPIC,
    DEFAULT_LED_OUT_TOPIC,
    DEFAULT_MODE,
    DEFAULT_NAME,
    DEFAULT_STATE_TOPIC,
    DOMAIN,
    MODE_OPTIONS,
)


class LgMonitorConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle the initial configuration flow."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            data = dict(user_input)
            data[CONF_COMMAND_TOPIC] = data[CONF_COMMAND_TOPIC].strip()
            state_topic = data.get(CONF_STATE_TOPIC, "")
            data[CONF_STATE_TOPIC] = state_topic.strip()
            unique_id = data[CONF_COMMAND_TOPIC]
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title=data[CONF_NAME], data=data)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
                    vol.Required(CONF_COMMAND_TOPIC, default=DEFAULT_COMMAND_TOPIC): str,
                    vol.Optional(CONF_STATE_TOPIC, default=DEFAULT_STATE_TOPIC): str,
                    vol.Optional(CONF_LED_IN_TOPIC, default=DEFAULT_LED_IN_TOPIC): str,
                    vol.Optional(CONF_LED_OUT_TOPIC, default=DEFAULT_LED_OUT_TOPIC): str,
                    vol.Required(
                        CONF_LED_COUNT, default=DEFAULT_LED_COUNT
                    ): vol.All(int, vol.Range(min=1, max=512)),
                    vol.Required(
                        CONF_BRIGHTNESS_LEVELS, default=DEFAULT_BRIGHTNESS_LEVELS
                    ): vol.All(int, vol.Range(min=1, max=255)),
                    vol.Required(CONF_ENABLE_STATE_SENSOR, default=True): bool,
                    vol.Required(
                        CONF_MODE, default=DEFAULT_MODE
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(options=MODE_OPTIONS, multiple=False)
                    ),
                }
            ),
            errors=errors,
        )

    @staticmethod
    def async_get_options_flow(config_entry: config_entries.ConfigEntry) -> config_entries.OptionsFlow:
        return LgMonitorOptionsFlow(config_entry)


class LgMonitorOptionsFlow(config_entries.OptionsFlow):
    """Allow users to adjust topics and behaviour after setup."""

    def __init__(self, entry: config_entries.ConfigEntry) -> None:
        self.config_entry = entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        if user_input is not None:
            data = dict(user_input)
            data[CONF_COMMAND_TOPIC] = data[CONF_COMMAND_TOPIC].strip()
            if CONF_STATE_TOPIC in data and data[CONF_STATE_TOPIC] is not None:
                data[CONF_STATE_TOPIC] = data[CONF_STATE_TOPIC].strip()
            if CONF_LED_IN_TOPIC in data and data[CONF_LED_IN_TOPIC] is not None:
                data[CONF_LED_IN_TOPIC] = data[CONF_LED_IN_TOPIC].strip()
            if CONF_LED_OUT_TOPIC in data and data[CONF_LED_OUT_TOPIC] is not None:
                data[CONF_LED_OUT_TOPIC] = data[CONF_LED_OUT_TOPIC].strip()

            groups: list[dict[str, Any]] = []
            for idx in range(1, 4):
                name_key = f"group_{idx}_name"
                entities_key = f"group_{idx}_entities"
                leds_key = f"group_{idx}_leds"
                strategy_key = f"group_{idx}_strategy"
                entities = data.pop(entities_key, []) or []
                leds_raw = data.pop(leds_key, "").strip()
                strategy = data.pop(strategy_key, "average")
                name = data.pop(name_key, f"Group {idx}")
                led_indices = _parse_led_indices(leds_raw)
                if entities and led_indices:
                    groups.append(
                        {
                            "name": name or f"Group {idx}",
                            "entities": entities if isinstance(entities, list) else [entities],
                            "led_indices": led_indices,
                            "strategy": strategy,
                        }
                    )
            data[CONF_GROUPS] = groups
            return self.async_create_entry(title="", data=data)

        data = {**self.config_entry.data, **self.config_entry.options}
        existing_groups: list[dict[str, Any]] = data.get(CONF_GROUPS, []) or []
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_COMMAND_TOPIC, default=data.get(CONF_COMMAND_TOPIC, DEFAULT_COMMAND_TOPIC)
                    ): str,
                    vol.Optional(
                        CONF_STATE_TOPIC, default=data.get(CONF_STATE_TOPIC, DEFAULT_STATE_TOPIC)
                    ): str,
                    vol.Optional(
                        CONF_LED_IN_TOPIC, default=data.get(CONF_LED_IN_TOPIC, DEFAULT_LED_IN_TOPIC)
                    ): str,
                    vol.Optional(
                        CONF_LED_OUT_TOPIC, default=data.get(CONF_LED_OUT_TOPIC, DEFAULT_LED_OUT_TOPIC)
                    ): str,
                    vol.Required(
                        CONF_LED_COUNT, default=data.get(CONF_LED_COUNT, DEFAULT_LED_COUNT)
                    ): vol.All(int, vol.Range(min=1, max=512)),
                    vol.Required(
                        CONF_BRIGHTNESS_LEVELS,
                        default=data.get(CONF_BRIGHTNESS_LEVELS, DEFAULT_BRIGHTNESS_LEVELS),
                    ): vol.All(int, vol.Range(min=1, max=255)),
                    vol.Required(
                        CONF_ENABLE_STATE_SENSOR,
                        default=data.get(CONF_ENABLE_STATE_SENSOR, True),
                    ): bool,
                    vol.Required(
                        CONF_MODE, default=data.get(CONF_MODE, DEFAULT_MODE)
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(options=MODE_OPTIONS, multiple=False)
                    ),
                    vol.Optional(
                        "group_1_name", default=_group_value(existing_groups, 0, "name", "Group 1")
                    ): str,
                    vol.Optional(
                        "group_1_entities",
                        default=_group_value(existing_groups, 0, "entities", []),
                    ): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain=["light"], multiple=True)
                    ),
                    vol.Optional(
                        "group_1_leds",
                        default=_led_indices_to_str(_group_value(existing_groups, 0, "led_indices", [])),
                    ): str,
                    vol.Optional(
                        "group_1_strategy",
                        default=_group_value(existing_groups, 0, "strategy", "average"),
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=["average", "dominant", "random", "one_to_one"], multiple=False
                        )
                    ),
                    vol.Optional(
                        "group_2_name", default=_group_value(existing_groups, 1, "name", "Group 2")
                    ): str,
                    vol.Optional(
                        "group_2_entities",
                        default=_group_value(existing_groups, 1, "entities", []),
                    ): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain=["light"], multiple=True)
                    ),
                    vol.Optional(
                        "group_2_leds",
                        default=_led_indices_to_str(_group_value(existing_groups, 1, "led_indices", [])),
                    ): str,
                    vol.Optional(
                        "group_2_strategy",
                        default=_group_value(existing_groups, 1, "strategy", "average"),
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=["average", "dominant", "random", "one_to_one"], multiple=False
                        )
                    ),
                    vol.Optional(
                        "group_3_name", default=_group_value(existing_groups, 2, "name", "Group 3")
                    ): str,
                    vol.Optional(
                        "group_3_entities",
                        default=_group_value(existing_groups, 2, "entities", []),
                    ): selector.EntitySelector(
                        selector.EntitySelectorConfig(domain=["light"], multiple=True)
                    ),
                    vol.Optional(
                        "group_3_leds",
                        default=_led_indices_to_str(_group_value(existing_groups, 2, "led_indices", [])),
                    ): str,
                    vol.Optional(
                        "group_3_strategy",
                        default=_group_value(existing_groups, 2, "strategy", "average"),
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=["average", "dominant", "random", "one_to_one"], multiple=False
                        )
                    ),
                }
            ),
        )


def _group_value(groups: list[dict[str, Any]], idx: int, key: str, default: Any) -> Any:
    if idx >= len(groups):
        return default
    return groups[idx].get(key, default)


def _parse_led_indices(raw: str) -> list[int]:
    values: set[int] = set()
    if not raw:
        return []
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        if "-" in part:
            try:
                start_s, end_s = part.split("-", 1)
                start = int(start_s)
                end = int(end_s)
            except ValueError:
                continue
            for val in range(min(start, end), max(start, end) + 1):
                values.add(val)
        else:
            try:
                values.add(int(part))
            except ValueError:
                continue
    return sorted(v for v in values if v >= 0)


def _led_indices_to_str(values: list[int]) -> str:
    if not values:
        return ""
    return ",".join(str(v) for v in values)
