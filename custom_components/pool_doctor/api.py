from __future__ import annotations

from typing import Any
from aiohttp import ClientSession, ClientTimeout


class PoolDoctorApiError(Exception):
    pass


class PoolDoctorApi:
    def __init__(self, session: ClientSession, endpoint: str, token: str | None = None) -> None:
        self._session = session
        self._endpoint = endpoint
        self._token = token

    async def _post(self, payload: dict[str, Any]) -> dict[str, Any]:
        headers = {"Content-Type": "application/json"}
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        try:
            async with self._session.post(
                self._endpoint,
                json=payload,
                headers=headers,
                timeout=ClientTimeout(total=20),
            ) as response:
                data = await response.json(content_type=None)
                if response.status >= 400:
                    raise PoolDoctorApiError(data.get("error") or f"HTTP {response.status}")
                return data
        except PoolDoctorApiError:
            raise
        except Exception as err:
            raise PoolDoctorApiError(str(err)) from err

    async def pair(self, code: str, name: str) -> dict[str, Any]:
        return await self._post({"action": "pair", "code": code, "name": name})

    async def ingest(self, states: dict[str, Any], mappings: dict[str, str]) -> dict[str, Any]:
        return await self._post({"action": "ingest", "states": states, "mappings": mappings})

    async def snapshot(self) -> dict[str, Any]:
        return await self._post({"action": "snapshot"})
