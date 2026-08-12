from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_CONNECTION_ID, CONF_POOL_NAME, DOMAIN


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities) -> None:
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([PoolDoctorWaterProblem(coordinator, entry), PoolDoctorPump(coordinator, entry)])


class _Base(CoordinatorEntity, BinarySensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator, entry: ConfigEntry, key: str, name: str) -> None:
        super().__init__(coordinator)
        self._attr_name = name
        self._attr_unique_id = f"{entry.data[CONF_CONNECTION_ID]}_{key}"
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.data[CONF_CONNECTION_ID])},
            "name": f"Pool Doctor · {entry.data.get(CONF_POOL_NAME, 'Piscine')}",
            "manufacturer": "Pool Doctor",
            "model": "Pool Doctor Connect",
        }


class PoolDoctorWaterProblem(_Base):
    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry, "water_problem", "Problème eau")

    @property
    def is_on(self):
        return (self.coordinator.data or {}).get("health") == "alert"


class PoolDoctorPump(_Base):
    def __init__(self, coordinator, entry):
        super().__init__(coordinator, entry, "pump_running", "Pompe filtration")

    @property
    def is_on(self):
        return (self.coordinator.data or {}).get("values", {}).get("pumpOn") is True
