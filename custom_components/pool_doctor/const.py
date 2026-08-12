DOMAIN = "pool_doctor"
DEFAULT_ENDPOINT = "https://kxvbuqpdhzkzncelsuvu.supabase.co/functions/v1/pool-doctor-connect"
CONF_TOKEN = "token"
CONF_CONNECTION_ID = "connection_id"
CONF_POOL_NAME = "pool_name"
CONF_ENDPOINT = "endpoint"

MAPPING_KEYS = {
    "temperature_entity": "temperatureC",
    "ph_entity": "ph",
    "orp_entity": "orpMv",
    "chlorine_entity": "freeChlorinePpm",
    "tac_entity": "tacPpm",
    "cya_entity": "cyaPpm",
    "salt_entity": "saltGL",
    "pump_entity": "pumpOn",
    "pump_power_entity": "pumpPowerW",
    "filtration_hours_entity": "filtrationHoursToday",
}
