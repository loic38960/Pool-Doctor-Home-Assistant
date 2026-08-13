from __future__ import annotations

from collections import deque
from datetime import datetime, timedelta, timezone
import math
import re
from statistics import median
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

_WATER_KEYS = (
    "temperatureC",
    "ph",
    "freeChlorinePpm",
    "tacPpm",
    "cyaPpm",
    "saltGL",
    "orpMv",
)
_CHEMISTRY_KEYS = (
    "ph",
    "freeChlorinePpm",
    "tacPpm",
    "cyaPpm",
    "saltGL",
    "orpMv",
)
_ANALYSIS_WINDOW = timedelta(minutes=30)
_ANALYSIS_MIN_SPAN = timedelta(minutes=25)
_ANALYSIS_MIN_SAMPLES = 10
_ANALYSIS_BUFFER = timedelta(minutes=90)
_CHEMISTRY_HIDDEN_WINDOW = timedelta(minutes=10)
_UNSTABLE_WINDOW = timedelta(minutes=10)
_STUCK_WINDOW = timedelta(minutes=60)
_STUCK_MIN_SAMPLES = 30
_UNSTABLE_RANGES = {
    "ph": 0.25,
    "freeChlorinePpm": 1.0,
    "tacPpm": 35.0,
    "cyaPpm": 25.0,
    "saltGL": 1.0,
    "orpMv": 120.0,
}
_STUCK_RANGES = {
    "ph": 0.001,
    "freeChlorinePpm": 0.005,
    "tacPpm": 0.05,
    "cyaPpm": 0.05,
    "saltGL": 0.005,
    "orpMv": 0.5,
}


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
        value = float(state.state.replace(",", "."))
        return value if math.isfinite(value) else None
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


def _iso_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _finite_number(value: Any) -> float | None:
    if not isinstance(value, (int, float)):
        return None
    number = float(value)
    return number if math.isfinite(number) else None


class PoolDoctorCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.entry = entry
        self.api = PoolDoctorApi(
            async_get_clientsession(hass),
            entry.data.get(CONF_ENDPOINT, DEFAULT_ENDPOINT),
            entry.data[CONF_TOKEN],
        )
        self._water_samples: deque[tuple[datetime, dict[str, float]]] = deque()
        self._last_reliable_chemistry: dict[str, Any] | None = None
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
                if value is True:
                    state = self.hass.states.get(entity_id)
                    if state is not None and state.last_changed is not None:
                        states["pumpOnSince"] = state.last_changed.astimezone(timezone.utc).isoformat()
            elif canonical_key == "filtrationHoursToday":
                value = _duration_state_hours(self.hass, entity_id)
            else:
                value = _numeric_state(self.hass, entity_id)
            if value is not None:
                states[canonical_key] = value
        return states, mappings

    def _hide_chemistry(self, states: dict[str, Any]) -> None:
        for key in _CHEMISTRY_KEYS:
            states.pop(key, None)

    def _diagnostics(self, now: datetime) -> dict[str, Any]:
        unstable_cutoff = now - _UNSTABLE_WINDOW
        stuck_cutoff = now - _STUCK_WINDOW
        recent = [sample for sample in self._water_samples if sample[0] >= unstable_cutoff]
        long_window = [sample for sample in self._water_samples if sample[0] >= stuck_cutoff]

        diagnostics: dict[str, Any] = {}
        for key in _CHEMISTRY_KEYS:
            recent_values = [payload[key] for _, payload in recent if key in payload]
            long_values = [payload[key] for _, payload in long_window if key in payload]
            if len(recent_values) < 5 and len(long_values) < _STUCK_MIN_SAMPLES:
                continue

            state = "ok"
            value_range: float | None = None
            sample_count = len(recent_values)

            if len(recent_values) >= 5:
                recent_range = max(recent_values) - min(recent_values)
                value_range = recent_range
                if recent_range >= _UNSTABLE_RANGES[key]:
                    state = "unstable"

            if state == "ok" and len(long_values) >= _STUCK_MIN_SAMPLES:
                long_range = max(long_values) - min(long_values)
                if long_range <= _STUCK_RANGES[key]:
                    state = "possibly_stuck"
                    value_range = long_range
                    sample_count = len(long_values)

            diagnostics[key] = {
                "state": state,
                "sampleCount": sample_count,
                "range": round(value_range or 0.0, 4),
            }
        return diagnostics

    def _prepare_water_measurements(self, states: dict[str, Any]) -> None:
        now = datetime.now(timezone.utc)
        pump_on = states.get("pumpOn") is True
        pump_on_since = _iso_datetime(states.get("pumpOnSince"))

        if not pump_on or pump_on_since is None:
            self._water_samples.clear()
            self._hide_chemistry(states)
            states["waterMeasurementState"] = {
                "stage": "pump_off" if states.get("pumpOn") is False else "pump_unknown",
                "chemistryVisible": False,
                "chemistryUsable": False,
                "analysisAllowed": False,
                "reason": "pump_off" if states.get("pumpOn") is False else "pump_unknown",
            }
            if self._last_reliable_chemistry:
                states["lastReliableChemistry"] = dict(self._last_reliable_chemistry)
            return

        while self._water_samples and self._water_samples[0][0] < pump_on_since:
            self._water_samples.popleft()

        raw_water: dict[str, float] = {}
        for key in _WATER_KEYS:
            value = _finite_number(states.get(key))
            if value is not None:
                raw_water[key] = value
        if raw_water:
            self._water_samples.append((now, raw_water))

        buffer_cutoff = now - _ANALYSIS_BUFFER
        while self._water_samples and self._water_samples[0][0] < buffer_cutoff:
            self._water_samples.popleft()

        elapsed = now - pump_on_since
        elapsed_minutes = max(0, int(elapsed.total_seconds() // 60))
        diagnostics = self._diagnostics(now)
        if diagnostics:
            states["sensorDiagnostics"] = diagnostics

        if elapsed < _CHEMISTRY_HIDDEN_WINDOW:
            self._hide_chemistry(states)
            states["waterMeasurementState"] = {
                "stage": "stabilizing_hidden",
                "elapsedMinutes": elapsed_minutes,
                "chemistryVisible": False,
                "chemistryUsable": False,
                "analysisAllowed": False,
                "reason": "initial_stabilization",
            }
            if self._last_reliable_chemistry:
                states["lastReliableChemistry"] = dict(self._last_reliable_chemistry)
            return

        if elapsed < _ANALYSIS_WINDOW:
            states["waterMeasurementState"] = {
                "stage": "stabilizing_visible",
                "elapsedMinutes": elapsed_minutes,
                "chemistryVisible": True,
                "chemistryUsable": False,
                "analysisAllowed": False,
                "reason": "stabilization",
            }
            if self._last_reliable_chemistry:
                states["lastReliableChemistry"] = dict(self._last_reliable_chemistry)
            return

        states["waterMeasurementState"] = {
            "stage": "reliable",
            "elapsedMinutes": elapsed_minutes,
            "chemistryVisible": True,
            "chemistryUsable": True,
            "analysisAllowed": True,
            "reason": "circulation_stable",
        }

        window_cutoff = now - _ANALYSIS_WINDOW
        samples = [sample for sample in self._water_samples if sample[0] >= window_cutoff]
        if len(samples) < _ANALYSIS_MIN_SAMPLES:
            states["waterMeasurementState"]["analysisAllowed"] = False
            states["waterMeasurementState"]["reason"] = "insufficient_samples"
            return
        if samples[-1][0] - samples[0][0] < _ANALYSIS_MIN_SPAN:
            states["waterMeasurementState"]["analysisAllowed"] = False
            states["waterMeasurementState"]["reason"] = "insufficient_span"
            return

        representative: dict[str, float] = {}
        for key in _WATER_KEYS:
            values = [payload[key] for _, payload in samples if key in payload]
            if len(values) < 3:
                continue
            diagnostic_state = diagnostics.get(key, {}).get("state")
            if diagnostic_state in ("unstable", "possibly_stuck"):
                continue
            representative[key] = round(float(median(values)), 3)

        chemistry = {key: representative[key] for key in _CHEMISTRY_KEYS if key in representative}
        if not chemistry:
            states["waterMeasurementState"]["analysisAllowed"] = False
            states["waterMeasurementState"]["reason"] = "no_reliable_chemistry"
            return

        self._last_reliable_chemistry = {
            "at": samples[-1][0].isoformat(),
            "values": chemistry,
        }
        states["lastReliableChemistry"] = dict(self._last_reliable_chemistry)

        states["analysisCandidate"] = {
            "at": samples[-1][0].isoformat(),
            "windowStartAt": samples[0][0].isoformat(),
            "windowEndAt": samples[-1][0].isoformat(),
            "sampleCount": len(samples),
            "values": representative,
        }

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            states, mappings = self._mapped_states()
            self._prepare_water_measurements(states)
            if states:
                await self.api.ingest(states, mappings)
            return await self.api.snapshot()
        except PoolDoctorApiError as err:
            raise UpdateFailed(str(err)) from err
