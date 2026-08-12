from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfPower, UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_CONNECTION_ID, CONF_POOL_NAME, DOMAIN


@dataclass(frozen=True, kw_only=True)
class PoolDoctorSensorDescription(SensorEntityDescription):
    path: tuple[str, ...]


SENSORS = (
    PoolDoctorSensorDescription(key="score", translation_key="score", name="Score", path=("score",), native_unit_of_measurement="%"),
    PoolDoctorSensorDescription(key="temperature", translation_key="temperature", name="Température eau", path=("values", "temperatureC"), native_unit_of_measurement=UnitOfTemperature.CELSIUS),
    PoolDoctorSensorDescription(key="ph", translation_key="ph", name="pH", path=("values", "ph")),
    PoolDoctorSensorDescription(key="orp", translation_key="orp", name="ORP", path=("values", "orpMv"), native_unit_of_measurement="mV"),
    PoolDoctorSensorDescription(key="salt", translation_key="salt", name="Sel", path=("values", "saltGL"), native_unit_of_measurement="g/L"),
    PoolDoctorSensorDescription(key="chlorine", translation_key="chlorine", name="Chlore libre", path=("values", "freeChlorinePpm"), native_unit_of_measurement="ppm"),
    PoolDoctorSensorDescription(key="filtration_today", translation_key="filtration_today", name="Filtration aujourd'hui", path=("values", "filtrationHoursToday"), native_unit_of_measurement=UnitOfTime.HOURS),
    PoolDoctorSensorDescription(key="filtration_target", translation_key="filtration_target", name="Filtration recommandée", path=("filtrationTargetHours",), native_unit_of_measurement=UnitOfTime.HOURS),
    PoolDoctorSensorDescription(key="pump_power", translation_key="pump_power", name="Puissance pompe", path=("values", "pumpPowerW"), native_unit_of_measurement=UnitOfPower.WATT),
    PoolDoctorSensorDescription(key="next_action", translation_key="next_action", name="Action prioritaire", path=("nextAction",)),
)


def _get(data: dict[str, Any], path: tuple[str, ...]):
    value: Any = data
    for key in path:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(PoolDoctorSensor(coordinator, entry, desc) for desc in SENSORS)


class PoolDoctorSensor(CoordinatorEntity, SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, entry: ConfigEntry, description: PoolDoctorSensorDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.data[CONF_CONNECTION_ID]}_{description.key}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.data[CONF_CONNECTION_ID])},
            "name": f"Pool Doctor · {entry.data.get(CONF_POOL_NAME, 'Piscine')}",
            "manufacturer": "Pool Doctor",
            "model": "Pool Doctor Connect",
        }

    @property
    def native_value(self):
        return _get(self.coordinator.data or {}, self.entity_description.path)
