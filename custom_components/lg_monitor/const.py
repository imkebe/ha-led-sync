"""Constants for the LG monitor Home Assistant integration."""

from __future__ import annotations

DOMAIN = "lg_monitor"
PLATFORMS = ["light", "sensor", "camera"]

CONF_COMMAND_TOPIC = "command_topic"
CONF_STATE_TOPIC = "state_topic"
CONF_LED_IN_TOPIC = "led_in_topic"
CONF_LED_OUT_TOPIC = "led_out_topic"
CONF_LED_COUNT = "led_count"
CONF_BRIGHTNESS_LEVELS = "brightness_levels"
CONF_SYNC_INTERVAL = "sync_interval"
CONF_COMMAND_SPACING = "command_spacing"
CONF_TRANSITION = "transition"
CONF_BRIGHTNESS_CUTOFF = "brightness_cutoff"
CONF_CUTOFF_RED = "cutoff_red"
CONF_CUTOFF_GREEN = "cutoff_green"
CONF_CUTOFF_BLUE = "cutoff_blue"
CONF_BRIGHTNESS_GAIN = "brightness_gain"
CONF_SATURATION_GAIN = "saturation_gain"
CONF_TEMPERATURE_SHIFT = "temperature_shift"
CONF_ENABLE_STATE_SENSOR = "enable_state_sensor"
CONF_MODE = "mode"
CONF_GROUPS = "groups"

MODE_LISTEN = "listen"
MODE_BROADCAST = "broadcast"
MODE_OPTIONS = [MODE_LISTEN, MODE_BROADCAST]

DEFAULT_NAME = "LG Monitor"
DEFAULT_COMMAND_TOPIC = "lg/monitor/colour"
DEFAULT_STATE_TOPIC = "lg/monitor/state"
DEFAULT_LED_IN_TOPIC = "lg/monitor/out"
DEFAULT_LED_OUT_TOPIC = "lg/monitor/out"
DEFAULT_LED_COUNT = 48
DEFAULT_BRIGHTNESS_LEVELS = 12
DEFAULT_SYNC_INTERVAL = 0.1
DEFAULT_COMMAND_SPACING = 0.0
DEFAULT_TRANSITION = 0.0
DEFAULT_BRIGHTNESS_CUTOFF = 0
DEFAULT_CUTOFF_RED = 0
DEFAULT_CUTOFF_GREEN = 0
DEFAULT_CUTOFF_BLUE = 0
DEFAULT_BRIGHTNESS_GAIN = 1.0
DEFAULT_SATURATION_GAIN = 1.0
DEFAULT_TEMPERATURE_SHIFT = 0.0
DEFAULT_MODE = MODE_LISTEN

SIGNAL_COMMAND = "lg_monitor_command"
SIGNAL_STATE_FRAME = "lg_monitor_state_frame"
SIGNAL_GROUPS = "lg_monitor_groups"
