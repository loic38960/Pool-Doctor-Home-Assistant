from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import selector
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import PoolDoctorApi, PoolDoctorApiError
from .const import CONF_CONNECTION_ID, CONF_ENDPOINT, CONF_POOL_NAME, CONF_TOKEN, DEFAULT_ENDPOINT, DOMAIN


class PoolDoctorConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            endpoint = user_input.get(CONF_ENDPOINT) or DEFAULT_ENDPOINT
            api = PoolDoctorApi(async_get_clientsession(self.hass), endpoint)
            try:
                paired = await api.pair(user_input["pairing_code"], user_input.get("name") or "Home Assistant")
                await self.async_set_unique_id(paired["connectionId"])
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title=paired.get("pool", {}).get("name") or "Pool Doctor",
                    data={
                        CONF_TOKEN: paired["token"],
                        CONF_CONNECTION_ID: paired["connectionId"],
                        CONF_POOL_NAME: paired.get("pool", {}).get("name") or "Piscine",
                        CONF_ENDPOINT: endpoint,
                    },
                )
            except PoolDoctorApiError:
                errors["base"] = "cannot_connect"

        schema = vol.Schema({
            vol.Required("pairing_code"): str,
            vol.Optional("name", default="Home Assistant"): str,
            vol.Optional(CONF_ENDPOINT, default=DEFAULT_ENDPOINT): str,
        })
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return PoolDoctorOptionsFlow()


class PoolDoctorOptionsFlow(config_entries.OptionsFlow):
    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = self.config_entry.options

        def ent(domains: list[str]):
            return selector.EntitySelector(selector.EntitySelectorConfig(domain=domains, multiple=False))

        schema = vol.Schema({
            vol.Optional("temperature_entity", description={"suggested_value": current.get("temperature_entity")}): ent(["sensor"]),
            vol.Optional("ph_entity", description={"suggested_value": current.get("ph_entity")}): ent(["sensor"]),
            vol.Optional("orp_entity", description={"suggested_value": current.get("orp_entity")}): ent(["sensor"]),
            vol.Optional("chlorine_entity", description={"suggested_value": current.get("chlorine_entity")}): ent(["sensor"]),
            vol.Optional("tac_entity", description={"suggested_value": current.get("tac_entity")}): ent(["sensor"]),
            vol.Optional("cya_entity", description={"suggested_value": current.get("cya_entity")}): ent(["sensor"]),
            vol.Optional("salt_entity", description={"suggested_value": current.get("salt_entity")}): ent(["sensor"]),
            vol.Optional("pump_entity", description={"suggested_value": current.get("pump_entity")}): ent(["switch", "binary_sensor", "sensor"]),
            vol.Optional("pump_power_entity", description={"suggested_value": current.get("pump_power_entity")}): ent(["sensor"]),
            vol.Optional("filtration_hours_entity", description={"suggested_value": current.get("filtration_hours_entity")}): ent(["sensor"]),
        })
        return self.async_show_form(step_id="init", data_schema=schema)
