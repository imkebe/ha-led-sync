# ha-led-sync

Home Assistant custom integration + HACS custom template for controlling and syncing LG monitor LEDs via MQTT.

## HACS integration

- Integration directory: `custom_components/lg_monitor/`
- HACS repository type: **Integration**

## HACS custom template

- Template file: `lg_monitor.jinja`
- HACS repository type: **Template**

## Repository structure (HACS)

- `README.md` in repo root
- `hacs.json` in repo root
- `lg_monitor.jinja` in repo root (matches `hacs.json` → `filename`)
- `custom_components/lg_monitor/` contains all integration files (and it’s the only integration under `custom_components/`)

## Documentation

- Integration spec: `docs/homeassistant.md`
