"""Async API client for SpotOn."""

from __future__ import annotations

import json
from typing import Any

from aiohttp import ClientError, ClientResponseError, ClientSession

from .const import DEFAULT_BASE_URL


class SpotOnApiError(Exception):
    """Raised when the SpotOn API returns an unexpected error."""


class SpotOnAuthenticationError(SpotOnApiError):
    """Raised when authentication fails."""


class SpotOnApiClient:
    """Small async SpotOn API client for read-only v1 integration work."""

    def __init__(
        self,
        session: ClientSession,
        *,
        email: str,
        password: str,
        base_url: str = DEFAULT_BASE_URL,
        timeout: float = 30.0,
    ) -> None:
        self._session = session
        self._email = email
        self._password = password
        self._base_url = base_url.rstrip("/")
        self.timeout = timeout
        self._access_token: str | None = None
        self._refresh_token: str | None = None

    async def async_authenticate(self) -> None:
        """Authenticate against the SpotOn API."""
        payload = await self._request(
            "POST",
            "/api/v1/authorizations",
            authenticated=False,
            json_body={
                "email": self._email,
                "password": self._password,
            },
        )
        access_token = payload.get("access_token")
        if not access_token:
            raise SpotOnAuthenticationError("Auth response did not include an access token")
        self._access_token = access_token
        self._refresh_token = payload.get("refresh_token")

    async def async_get_current_user(self) -> dict[str, Any]:
        """Fetch the current authenticated user."""
        payload = await self._request("GET", "/api/v1/users/current")
        if not isinstance(payload, dict):
            raise SpotOnApiError("Unexpected current user payload type")
        return payload

    async def async_list_collars(self) -> list[dict[str, Any]]:
        """Fetch the current account's collars."""
        payload = await self._request("GET", "/api/v1/collars")
        if not isinstance(payload, list):
            raise SpotOnApiError("Unexpected collars payload type")
        return payload

    async def async_list_fences(self) -> list[dict[str, Any]]:
        """Fetch the current account's fences."""
        payload = await self._request("GET", "/api/v1/fences")
        if not isinstance(payload, list):
            raise SpotOnApiError("Unexpected fences payload type")
        return payload

    async def async_get_fence(self, fence_id: str | int) -> dict[str, Any]:
        """Fetch a detailed fence payload."""
        payload = await self._request("GET", f"/api/v1/fences/{fence_id}")
        if not isinstance(payload, dict):
            raise SpotOnApiError("Unexpected fence payload type")
        return payload

    async def async_refresh_collar_location(
        self,
        *,
        collar_uid: str,
        collar_id: str | int | None = None,
        collar_name: str | None = None,
        command_timeout: float = 30.0,
    ) -> dict[str, Any]:
        """Trigger the collar refresh WebSocket action used by the mobile app."""
        if not self._access_token:
            await self.async_authenticate()

        identifier = json.dumps(
            {"channel": "CollarChannelPublic", "type": "get_statundefined", "uid": str(collar_uid)},
            separators=(",", ":"),
        )
        subscribe_message = {"command": "subscribe", "identifier": identifier}
        request_message = {
            "command": "message",
            "identifier": identifier,
            "data": json.dumps({"action": "get_stat"}, separators=(",", ":")),
        }
        unsubscribe_message = {"command": "unsubscribe", "identifier": identifier}

        ack_messages: list[dict[str, Any]] = []
        stat_message: dict[str, Any] | None = None
        ws_url = self._base_url.replace("https://", "wss://").replace("http://", "ws://") + "/cable"
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self._access_token}",
        }

        try:
            async with self._session.ws_connect(
                ws_url,
                headers=headers,
                heartbeat=20,
                timeout=self.timeout,
            ) as websocket:
                await websocket.send_json(subscribe_message, dumps=_json_dumps)
                request_sent = False

                while True:
                    message = await websocket.receive(timeout=command_timeout)
                    if message.type.name in {"CLOSE", "CLOSED"}:
                        break
                    if message.type.name == "ERROR":
                        raise SpotOnApiError(
                            f"WebSocket refresh failed for collar {collar_uid}: {websocket.exception()}"
                        )
                    if message.type.name != "TEXT":
                        continue

                    payload = _parse_ws_json(message.data)
                    if not isinstance(payload, dict):
                        continue
                    if payload.get("type") == "ping":
                        continue
                    if payload.get("identifier") != identifier:
                        continue

                    if payload.get("type") == "confirm_subscription":
                        if not request_sent:
                            await websocket.send_json(request_message, dumps=_json_dumps)
                            request_sent = True
                        continue

                    inner_message = payload.get("message")
                    if not isinstance(inner_message, dict):
                        continue

                    action = inner_message.get("action")
                    if action == "get_stat":
                        ack_messages.append(inner_message)
                        continue
                    if action == "stat":
                        stat_message = inner_message
                        break

                await websocket.send_json(unsubscribe_message, dumps=_json_dumps)
        except TimeoutError as err:
            raise SpotOnApiError(
                f"Timed out waiting for WebSocket stat payload for collar {collar_uid}"
            ) from err
        except ClientError as err:
            raise SpotOnApiError(f"WebSocket refresh failed for collar {collar_uid}: {err}") from err

        if stat_message is None:
            raise SpotOnApiError(
                f"WebSocket refresh did not return a stat payload for collar {collar_uid}"
            )

        return {
            "collar_id": collar_id,
            "collar_uid": str(collar_uid),
            "collar_name": collar_name,
            "request_action": "get_stat",
            "ack_messages": ack_messages,
            "stat": stat_message,
        }

    async def _request(
        self,
        method: str,
        path: str,
        *,
        authenticated: bool = True,
        params: dict[str, Any] | None = None,
        json_body: dict[str, Any] | None = None,
        retry_on_auth_failure: bool = True,
    ) -> Any:
        if authenticated and not self._access_token:
            await self.async_authenticate()

        headers = {"Accept": "application/json"}
        if authenticated and self._access_token:
            headers["Authorization"] = f"Bearer {self._access_token}"

        try:
            async with self._session.request(
                method,
                f"{self._base_url}{path}",
                params={key: value for key, value in (params or {}).items() if value is not None},
                json=json_body,
                headers=headers,
            ) as response:
                if response.status == 401:
                    if authenticated and retry_on_auth_failure:
                        self._access_token = None
                        self._refresh_token = None
                        await self.async_authenticate()
                        return await self._request(
                            method,
                            path,
                            authenticated=authenticated,
                            params=params,
                            json_body=json_body,
                            retry_on_auth_failure=False,
                        )
                    raise SpotOnAuthenticationError("SpotOn authentication failed")

                response.raise_for_status()
                if response.content_length == 0:
                    return None
                return await response.json(content_type=None)
        except ClientResponseError as err:
            raise SpotOnApiError(f"SpotOn API error {err.status} on {method} {path}") from err
        except ClientError as err:
            raise SpotOnApiError(f"SpotOn request failed on {method} {path}: {err}") from err


def _json_dumps(payload: Any) -> str:
    return json.dumps(payload, separators=(",", ":"))


def _parse_ws_json(raw_message: str) -> Any:
    try:
        return json.loads(raw_message)
    except json.JSONDecodeError:
        return raw_message
