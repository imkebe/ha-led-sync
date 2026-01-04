# Home Assistant Integration Spec

## Overview

The tray app exposes a lightweight MQTT interface so Home Assistant (or other
automation hubs) can both **drive** the monitor LEDs and **read** their current
state. Three complementary topics are used:

- `mqtt_topic` (default `lg/monitor/colour`) – inbound commands for **Zen mode**
- `mqtt_state_topic` (default `lg/monitor/state`) – connection status
  (`connected`/`disconnected`)
- `mqtt_led_topic` (default `lg/monitor/out`) – outbound binary LED frames
  reflecting the current colours (`color1…color4` and Lightsync)

All MQTT settings (host, port, user/pass, SSL, topics) are configurable inside
the Integration tab of the UI and persist to `settings.yaml`.

## Zen Mode (Inbound Topic)

- Subscribe to `mqtt_topic`.
- Payload formats:
  - Hex string (`rrggbb`) – sets colour immediately.
  - JSON: `{"colour":"#rrggbb","brightness":12}` – optional brightness (1‑12).
- On receipt the app:
  - Stores the colour in bank 4, calls `get_set_color_command(4, colour)` and
    switches monitors to `color4`.
  - Applies brightness if provided.
  - Persists the new colour to `settings.yaml`.
- Intended update frequency: low (~1 per minute). No per‑LED streaming; this
  keeps CPU usage minimal when the monitor or system wakes from sleep.

## LED Frame Publishing (Outbound Topic)

- Enabled whenever `mqtt_led_topic` is non-empty.
- Whenever the user selects/updates `color1…color4`, the current 48‑LED colour
  array is published as a raw binary payload (identical to Hyperion RawUDP):

```
# payload length = led_count * 3 bytes
[ R0 G0 B0 ][ R1 G1 B1 ] … [ R47 G47 B47 ]
```

- Colours are clamped so each component is at least `0x01` (monitor firmware
  stability requirement). Lightsync frames are relayed at the same cadence so
  other consumers can mirror the LEDs in near real time.
- Home Assistant listeners can parse this payload directly or forward it to
  other devices for syncing.

## Connection State Topic

- Whenever the app detects at least one selected monitor, it publishes
  `connected` to `mqtt_state_topic`; when no monitors are reachable it
  publishes `disconnected`.
- Subscribers can use this as an availability flag before reacting to `mqtt_topic`
  or `mqtt_led_topic`.

## Future Work

- Extend outbound publishing to dynamic modes (Peaceful/Dynamic) once we have a
  deterministic mapping to colour frames.
- The `custom_components/lg_monitor` integration in this repository consumes
  these topics and exposes services/entities in Home Assistant.
