import json
import time

import aiohttp

import config


class IikoError(Exception):
    pass


class IikoClient:
    def __init__(self):
        self._token: str | None = None
        self._token_time: float = 0.0

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self._token}"}

    async def _ensure_token(self, http: aiohttp.ClientSession) -> str:
        if self._token and time.time() - self._token_time < 3300:
            return self._token
        url = f"{config.IIKO_API_URL}/api/1/access_token"
        async with http.post(url, json={"apiLogin": config.IIKO_API_LOGIN}) as resp:
            data = await resp.json()
            if resp.status != 200 or "token" not in data:
                raise IikoError(f"access_token: {resp.status} {data}")
        self._token = data["token"]
        self._token_time = time.time()
        return self._token

    async def _request(self, method_path: str, payload: dict | None = None) -> dict:
        timeout = aiohttp.ClientTimeout(total=60)
        async with aiohttp.ClientSession(timeout=timeout) as http:
            token = await self._ensure_token(http)
            url = f"{config.IIKO_API_URL}{method_path}"
            async with http.post(
                url,
                json=payload if payload is not None else {},
                headers=self._headers(),
            ) as resp:
                text = await resp.text()
                if resp.status >= 400:
                    raise IikoError(f"{method_path}: HTTP {resp.status}: {text[:500]}")
                try:
                    return json.loads(text)
                except Exception:
                    raise IikoError(f"{method_path}: не-JSON ответ: {text[:300]}")

    async def get_organizations(self) -> list[dict]:
        data = await self._request("/api/1/organization")
        return data.get("organizations", [])

    async def get_terminal_groups(self, organization_ids: list[str]) -> dict:
        return await self._request(
            "/api/1/terminal_groups",
            {"organizationIds": organization_ids, "includeDisabled": True},
        )

    async def get_nomenclature(self, organization_id: str) -> dict:
        return await self._request(
            "/api/1/nomenclature", {"organizationId": organization_id}
        )

    async def create_delivery_order(self, order_payload: dict) -> dict:
        return await self._request("/api/1/delivery/create", order_payload)


client = IikoClient()
