from __future__ import annotations

from datetime import timedelta
import math
import re
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import PoolDoctorApi, PoolDoctorApiError
from .const import CONF_ENDPOINT, CONF_TOKEN, DEFAULT_ENDPOINT, DOMAIN, MAPPING_KEYS

_INVALID_STATES = {
    "",
    "unknown",
    "unavailable",
    "none",
    "null",
    "nan",
    "undefined",
    "inconnu",
    "indisponible",
}

_DURATION_TOKEN_RE = re.compile(
    r"(\d+(?:[.,]\d+)?)\s*"
    r"(millisecondes?|milliseconds?|ms|secondes?|seconds?|secs?|sec|s|"
    r"minutes?|mins?|min|m|heures?|hours?|hrs?|hr|h|jours?|days?|day|d)\b",
    re.IGNORECASE,
)


def _duration_unit_multiplier_minutes(unit: Any) -> float | None:
    normalized = str(unit or "").strip().lower().replace(".", "")
    if normalized in ("ms", "millisecond", "milliseconds", "milliseconde", "millisecondes"):
        return 1 / 60000
    if normalized in ("s", "sec", "secs", "second", "seconds", "seconde", "secondes"):
        return 1 / 60
    if normalized in ("m", "min", "mins", "minute", "minutes"):
        return 1
    if normalized in ("h", "hr", "hrs", "hour", "hours", "heure", "heures"):
        return 60
    if normalized in ("d", "day", "days", "jour", "jours"):
        return 1440
    return None


def _numeric_state(hass: HomeAssistant, entity_id: str | None) -> float | None:
    if not entity_id:
        return None
    state = hass.states.get(entity_id)
    if state is None or state.state.lower() in _INVALID_STATES:
        return None
    try:
        return float(state.state.replace(",", "."))
    except (TypeError, ValueError):
        return None


def _duration_state_hours(hass: HomeAssistant, entity_id: str | None) -> float | None:
    """Return a Home Assistant duration sensor as decimal hours."""
    if not entity_id:
        return None

    state = hass.states.get(entity_id)
    if state is None:
        return None

    raw = str(state.state).strip()
    if raw.lower() in _INVALID_STATES:
        return None

    numeric: float | None = None
    try:
        numeric = float(raw.replace(",", "."))
    except (TypeError, ValueError):
        pass

    unit = state.attributes.get("unit_of_measurement")
    multiplier = _duration_unit_multiplier_minutes(unit)
    if numeric is not None and math.isfinite(numeric) and numeric >= 0 and multiplier is not None:
        return numeric * multiplier / 60

    iso = re.fullmatch(
        r"P(?:(\d+(?:[.,]\d+)?)D)?T(?:(\d+(?:[.,]\d+)?)H)?"
        r"(?:(\d+(?:[.,]\d+)?)M)?(?:(\d+(?:[.,]\d+)?)S)?",
        raw,
        re.IGNORECASE,
    )
    if iso:
        days, hours, minutes, seconds = [
            float((value or "0").replace(",", ".")) for value in iso.groups()
        ]
        return days * 24 + hours + minutes / 60 + seconds / 3600

    clock = re.fullmatch(r"(\d{1,3}):([0-5]?\d)(?::([0-5]?\d))?", raw)
    if clock:
        return int(clock.group(1)) + int(clock.group(2)) / 60 + int(clock.group(3) or 0) / 3600

    total_minutes = 0.0
    token_count = 0
    for match in _DURATION_TOKEN_RE.finditer(raw):
        token_value = float(match.group(1).replace(",", "."))
        token_multiplier = _duration_unit_multiplier_minutes(match.group(2))
        if token_multiplier is None:
            return None
        total_minutes += token_value * token_multiplier
        token_count += 1
    if token_count:
        return total_minutes / 60

    compact = re.fullmatch(
        r"(\d+(?:[.,]\d+)?)\s*h(?:\s*(\d{1,2})(?:\s*m(?:in)?)?)?",
        raw,
        re.IGNORECASE,
    )
    if compact:
        hours = float(compact.group(1).replace(",", "."))
        minutes = int(compact.group(2) or 0)
        if minutes >= 60:
            return None
        return hours + minutes / 60

    if numeric is not None and math.isfinite(numeric) and numeric >= 0:
        if numeric <= 24:
            return numeric
        if numeric <= 1440:
            return numeric / 60
        return numeric / 3600

    return None


def _bool_state(hass: HomeAssistant, entity_id: str | None) -> bool | None:
    if not entity_id:
        return None
    state = hass.states.get(entity_id)
    if state is None or state.state.lower() in _INVALID_STATES:
        return None
    return state.state.lower() in ("on", "true", "1", "running", "open")


class PoolDoctorCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.entry = entry
        self.api = PoolDoctorApi(
            async_get_clientsession(hass),
            entry.data.get(CONF_ENDPOINT, DEFAULT_ENDPOINT),
            entry.data[CONF_TOKEN],
        )
        super().__init__(
            hass,
            logger=__import__("logging").getLogger(__name__),
            name=DOMAIN,
            update_interval=timedelta(seconds=60),
        )

    def _mapped_states(self) -> tuple[dict[str, Any], dict[str, str]]:
        states: dict[str, Any] = {}
        mappings: dict[str, str] = {}
        options = self.entry.options
        for option_key, canonical_key in MAPPING_KEYS.items():
            entity_id = options.get(option_key)
            if not entity_id:
                continue
            mappings[canonical_key] = entity_id
            if canonical_key == "pumpOn":
                value = _bool_state(self.hass, entity_id)
            elif canonical_key == "filtrationHoursToday":
                value = _duration_state_hours(self.hass, entity_id)
            else:
                value = _numeric_state(self.hass, entity_id)
            if value is not None:
                states[canonical_key] = value
        return states, mappings

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            states, mappings = self._mapped_states()
            if states:
                await self.api.ingest(states, mappings)
            return await self.api.snapshot()
        except PoolDoctorApiError as err:
            raise UpdateFailed(str(err)) from err
