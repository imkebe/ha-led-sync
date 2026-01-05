"""Configuration flow for the LG monitor integration."""

from __future__ import annotations

from copy import deepcopy
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
            name = (data.get(CONF_NAME) or "").strip() or DEFAULT_NAME
            data[CONF_NAME] = name
            data[CONF_COMMAND_TOPIC] = (data.get(CONF_COMMAND_TOPIC) or "").strip()
            data[CONF_STATE_TOPIC] = (data.get(CONF_STATE_TOPIC) or "").strip()
            data[CONF_LED_IN_TOPIC] = (data.get(CONF_LED_IN_TOPIC) or "").strip()
            data[CONF_LED_OUT_TOPIC] = (data.get(CONF_LED_OUT_TOPIC) or "").strip()
            unique_id = data[CONF_COMMAND_TOPIC]
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title=name, data=data)

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
        existing = {**entry.data, **entry.options}
        self._options: dict[str, Any] = {
            CONF_COMMAND_TOPIC: existing.get(CONF_COMMAND_TOPIC, DEFAULT_COMMAND_TOPIC),
            CONF_STATE_TOPIC: existing.get(CONF_STATE_TOPIC, DEFAULT_STATE_TOPIC),
            CONF_LED_IN_TOPIC: existing.get(CONF_LED_IN_TOPIC, DEFAULT_LED_IN_TOPIC),
            CONF_LED_OUT_TOPIC: existing.get(CONF_LED_OUT_TOPIC, DEFAULT_LED_OUT_TOPIC),
            CONF_LED_COUNT: existing.get(CONF_LED_COUNT, DEFAULT_LED_COUNT),
            CONF_BRIGHTNESS_LEVELS: existing.get(CONF_BRIGHTNESS_LEVELS, DEFAULT_BRIGHTNESS_LEVELS),
            CONF_ENABLE_STATE_SENSOR: existing.get(CONF_ENABLE_STATE_SENSOR, True),
            CONF_MODE: existing.get(CONF_MODE, DEFAULT_MODE),
        }
        self._groups: list[dict[str, Any]] = deepcopy(existing.get(CONF_GROUPS, []) or [])
        self._edit_group_index: int | None = None

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        return self.async_show_menu(
            step_id="init",
            menu_options={
                "settings": "Settings",
                "groups": "Groups",
                "finish": "Save",
            },
        )

    async def async_step_settings(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            data = dict(user_input)
            self._options[CONF_COMMAND_TOPIC] = (data.get(CONF_COMMAND_TOPIC) or "").strip()
            self._options[CONF_STATE_TOPIC] = (data.get(CONF_STATE_TOPIC) or "").strip()
            self._options[CONF_LED_IN_TOPIC] = (data.get(CONF_LED_IN_TOPIC) or "").strip()
            self._options[CONF_LED_OUT_TOPIC] = (data.get(CONF_LED_OUT_TOPIC) or "").strip()
            self._options[CONF_LED_COUNT] = int(data.get(CONF_LED_COUNT, DEFAULT_LED_COUNT))
            self._options[CONF_BRIGHTNESS_LEVELS] = int(
                data.get(CONF_BRIGHTNESS_LEVELS, DEFAULT_BRIGHTNESS_LEVELS)
            )
            self._options[CONF_ENABLE_STATE_SENSOR] = bool(
                data.get(CONF_ENABLE_STATE_SENSOR, True)
            )
            self._options[CONF_MODE] = data.get(CONF_MODE, DEFAULT_MODE)
            return await self.async_step_init()

        return self.async_show_form(
            step_id="settings",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_COMMAND_TOPIC,
                        default=self._options.get(CONF_COMMAND_TOPIC, DEFAULT_COMMAND_TOPIC),
                    ): str,
                    vol.Optional(
                        CONF_STATE_TOPIC, default=self._options.get(CONF_STATE_TOPIC, DEFAULT_STATE_TOPIC)
                    ): str,
                    vol.Optional(
                        CONF_LED_IN_TOPIC,
                        default=self._options.get(CONF_LED_IN_TOPIC, DEFAULT_LED_IN_TOPIC),
                    ): str,
                    vol.Optional(
                        CONF_LED_OUT_TOPIC,
                        default=self._options.get(CONF_LED_OUT_TOPIC, DEFAULT_LED_OUT_TOPIC),
                    ): str,
                    vol.Required(
                        CONF_LED_COUNT,
                        default=self._options.get(CONF_LED_COUNT, DEFAULT_LED_COUNT),
                    ): vol.All(int, vol.Range(min=1, max=512)),
                    vol.Required(
                        CONF_BRIGHTNESS_LEVELS,
                        default=self._options.get(CONF_BRIGHTNESS_LEVELS, DEFAULT_BRIGHTNESS_LEVELS),
                    ): vol.All(int, vol.Range(min=1, max=255)),
                    vol.Required(
                        CONF_ENABLE_STATE_SENSOR,
                        default=self._options.get(CONF_ENABLE_STATE_SENSOR, True),
                    ): bool,
                    vol.Required(
                        CONF_MODE,
                        default=self._options.get(CONF_MODE, DEFAULT_MODE),
                    ): selector.SelectSelector(
                        selector.SelectSelectorConfig(options=MODE_OPTIONS, multiple=False)
                    ),
                }
            ),
            errors=errors,
        )

    async def async_step_groups(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        return self.async_show_menu(
            step_id="groups",
            menu_options={
                "add_group": "Add group",
                "edit_group": "Edit group",
                "remove_group": "Remove group",
                "finish": "Save",
                "back": "Back",
            },
        )

    async def async_step_add_group(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            group = _group_from_user_input(user_input, errors)
            if not errors and group is not None:
                self._groups.append(group)
                return await self.async_step_groups()

        return self.async_show_form(
            step_id="add_group",
            data_schema=_group_schema(
                default_name=f"Group {len(self._groups) + 1}",
                default_entities=[],
                default_leds="",
                default_strategy="average",
            ),
            errors=errors,
        )

    async def async_step_edit_group(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors: dict[str, str] = {}
        if not self._groups:
            errors["base"] = "no_groups"
            return self.async_show_form(step_id="edit_group", data_schema=vol.Schema({}), errors=errors)

        if user_input is not None:
            try:
                self._edit_group_index = int(user_input["group_index"])
            except (KeyError, ValueError, TypeError):
                errors["base"] = "invalid_group"
            else:
                return await self.async_step_edit_group_form()

        return self.async_show_form(
            step_id="edit_group",
            data_schema=vol.Schema(
                {
                    vol.Required("group_index"): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=_group_index_options(self._groups), multiple=False
                        )
                    )
                }
            ),
            errors=errors,
        )

    async def async_step_edit_group_form(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}
        idx = self._edit_group_index
        if idx is None or idx < 0 or idx >= len(self._groups):
            self._edit_group_index = None
            errors["base"] = "invalid_group"
            return self.async_show_form(step_id="edit_group_form", data_schema=vol.Schema({}), errors=errors)

        current = self._groups[idx]
        if user_input is not None:
            group = _group_from_user_input(user_input, errors)
            if not errors and group is not None:
                self._groups[idx] = group
                self._edit_group_index = None
                return await self.async_step_groups()

        return self.async_show_form(
            step_id="edit_group_form",
            data_schema=_group_schema(
                default_name=str(current.get("name") or f"Group {idx + 1}"),
                default_entities=list(current.get("entities") or []),
                default_leds=_led_indices_to_str(list(current.get("led_indices") or [])),
                default_strategy=str(current.get("strategy") or "average"),
            ),
            errors=errors,
        )

    async def async_step_remove_group(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        errors: dict[str, str] = {}
        if not self._groups:
            errors["base"] = "no_groups"
            return self.async_show_form(
                step_id="remove_group", data_schema=vol.Schema({}), errors=errors
            )

        if user_input is not None:
            try:
                idx = int(user_input["group_index"])
            except (KeyError, ValueError, TypeError):
                errors["base"] = "invalid_group"
            else:
                if 0 <= idx < len(self._groups):
                    self._groups.pop(idx)
                    return await self.async_step_groups()
                errors["base"] = "invalid_group"

        return self.async_show_form(
            step_id="remove_group",
            data_schema=vol.Schema(
                {
                    vol.Required("group_index"): selector.SelectSelector(
                        selector.SelectSelectorConfig(
                            options=_group_index_options(self._groups), multiple=False
                        )
                    )
                }
            ),
            errors=errors,
        )

    async def async_step_back(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        return await self.async_step_init()

    async def async_step_finish(self, user_input: dict[str, Any] | None = None) -> FlowResult:
        options = dict(self._options)
        options[CONF_COMMAND_TOPIC] = (options.get(CONF_COMMAND_TOPIC) or "").strip()
        options[CONF_STATE_TOPIC] = (options.get(CONF_STATE_TOPIC) or "").strip()
        options[CONF_LED_IN_TOPIC] = (options.get(CONF_LED_IN_TOPIC) or "").strip()
        options[CONF_LED_OUT_TOPIC] = (options.get(CONF_LED_OUT_TOPIC) or "").strip()
        options[CONF_GROUPS] = self._groups
        return self.async_create_entry(title="", data=options)


def _group_schema(
    *,
    default_name: str,
    default_entities: list[str],
    default_leds: str,
    default_strategy: str,
) -> vol.Schema:
    return vol.Schema(
        {
            vol.Required("group_name", default=default_name): str,
            vol.Required("group_entities", default=default_entities): selector.EntitySelector(
                selector.EntitySelectorConfig(domain=["light"], multiple=True)
            ),
            vol.Required("group_leds", default=default_leds): str,
            vol.Required("group_strategy", default=default_strategy): selector.SelectSelector(
                selector.SelectSelectorConfig(
                    options=["average", "dominant", "random", "one_to_one"], multiple=False
                )
            ),
        }
    )


def _group_index_options(groups: list[dict[str, Any]]) -> list[dict[str, str]]:
    options: list[dict[str, str]] = []
    for idx, group in enumerate(groups):
        name = group.get("name") or f"Group {idx + 1}"
        options.append({"label": f"{idx + 1}: {name}", "value": str(idx)})
    return options


def _group_from_user_input(
    user_input: dict[str, Any], errors: dict[str, str]
) -> dict[str, Any] | None:
    name = (user_input.get("group_name") or "").strip()
    entities = user_input.get("group_entities") or []
    leds_raw = (user_input.get("group_leds") or "").strip()
    strategy = user_input.get("group_strategy") or "average"

    if not name:
        errors["group_name"] = "group_name_required"

    if not entities:
        errors["group_entities"] = "group_entities_required"

    led_indices = _parse_led_indices(leds_raw)
    if not led_indices:
        errors["group_leds"] = "group_leds_required"

    if (
        strategy == "one_to_one"
        and entities
        and led_indices
        and len(entities) != len(led_indices)
    ):
        errors["base"] = "one_to_one_mismatch"

    if errors:
        return None

    entity_list = entities if isinstance(entities, list) else [entities]
    return {
        "name": name,
        "entities": entity_list,
        "led_indices": led_indices,
        "strategy": str(strategy),
    }


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
