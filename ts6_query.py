from __future__ import annotations

import asyncio
import json
import ssl
from dataclasses import asdict, dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen


class Ts6QueryError(Exception):
    """Raised when a TeamSpeak 6 WebQuery request fails."""


@dataclass
class Ts6OnlineUser:
    nickname: str
    channel_name: str
    client_id: str
    database_id: str
    unique_id: str
    client_ip: str
    connected_duration_seconds: int
    away: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class Ts6ServerStatus:
    server_name: str
    server_host: str
    server_port: int
    online_count: int
    channel_names: list[str]
    users: list[Ts6OnlineUser]

    def to_dict(self) -> dict[str, Any]:
        return {
            "server_name": self.server_name,
            "server_host": self.server_host,
            "server_port": self.server_port,
            "online_count": self.online_count,
            "channel_names": self.channel_names,
            "users": [user.to_dict() for user in self.users],
        }


class Ts6WebQueryClient:
    def __init__(
        self,
        host: str,
        server_id: int,
        api_key: str,
        query_port: int = 10080,
        scheme: str = "http",
        server_port: int = 0,
        timeout: float = 10.0,
        verify_tls: bool = True,
        debug: bool = False,
    ):
        self.host = host
        self.server_id = server_id
        self.api_key = api_key
        self.query_port = query_port
        self.scheme = "https" if str(scheme).lower() == "https" else "http"
        self.server_port = server_port
        self.timeout = timeout
        self.verify_tls = verify_tls
        self.debug = debug

    async def fetch_status(self) -> Ts6ServerStatus:
        serverinfo_records, channel_records, client_records = await asyncio.gather(
            self._execute("serverinfo"),
            self._execute("channellist"),
            self._execute("clientlist", options=["uid", "away", "ip"]),
        )

        client_details: dict[str, dict[str, str]] = {}
        for client in client_records:
            if client.get("client_type") == "1":
                continue
            clid = client.get("clid", "")
            if not clid:
                continue
            detail_records = await self._execute("clientinfo", params={"clid": clid})
            client_details[clid] = detail_records[0] if detail_records else {}

        serverinfo = serverinfo_records[0] if serverinfo_records else {}
        channels = {
            channel.get("cid", ""): channel.get("channel_name", "")
            for channel in channel_records
        }
        channel_names = [
            channel_name
            for channel_name in (channel.get("channel_name", "") for channel in channel_records)
            if channel_name
        ]

        users: list[Ts6OnlineUser] = []
        for client in client_records:
            if client.get("client_type") == "1":
                continue

            detail = client_details.get(client.get("clid", ""), {})
            users.append(
                Ts6OnlineUser(
                    nickname=client.get("client_nickname", ""),
                    channel_name=channels.get(client.get("cid", ""), ""),
                    client_id=client.get("clid", ""),
                    database_id=client.get("client_database_id", ""),
                    unique_id=client.get("client_unique_identifier", ""),
                    client_ip=client.get("connection_client_ip", ""),
                    connected_duration_seconds=_parse_connected_duration(detail),
                    away=client.get("client_away", "0") == "1",
                )
            )

        users.sort(key=lambda item: item.nickname.casefold())

        return Ts6ServerStatus(
            server_name=serverinfo.get("virtualserver_name", ""),
            server_host=self.host,
            server_port=int(serverinfo.get("virtualserver_port", self.server_port or 0) or 0),
            online_count=len(users),
            channel_names=channel_names,
            users=users,
        )

    async def list_virtual_servers(self) -> list[dict[str, str]]:
        return await self._execute("serverlist", use_server_id=False, options=["uid"])

    async def _execute(
        self,
        command: str,
        params: dict[str, str | int] | None = None,
        options: list[str] | None = None,
        use_server_id: bool = True,
    ) -> list[dict[str, str]]:
        payload = await asyncio.to_thread(
            self._request_json,
            command,
            params or {},
            options or [],
            use_server_id,
        )
        return self._extract_body(payload, command)

    def _request_json(
        self,
        command: str,
        params: dict[str, str | int],
        options: list[str],
        use_server_id: bool,
    ) -> dict[str, Any]:
        url = self._build_url(command, params, options, use_server_id)
        request = Request(
            url,
            headers={
                "x-api-key": self.api_key,
                "accept": "application/json",
                "user-agent": "astrbot-plugin-ts6-tracker/1.0",
            },
            method="GET",
        )
        try:
            context = None
            if self.scheme == "https" and not self.verify_tls:
                context = ssl._create_unverified_context()
            with urlopen(request, timeout=self.timeout, context=context) as response:
                raw = response.read().decode("utf-8", errors="replace")
        except HTTPError as exc:  # pragma: no cover - network dependent
            detail = exc.read().decode("utf-8", errors="replace")
            raise Ts6QueryError(f"WebQuery HTTP {exc.code}: {detail or exc.reason}") from exc
        except URLError as exc:  # pragma: no cover - network dependent
            raise Ts6QueryError(f"无法连接到 WebQuery：{self.base_url} ({exc.reason})") from exc
        except Exception as exc:  # pragma: no cover - network dependent
            raise Ts6QueryError(f"WebQuery 请求失败：{exc}") from exc

        try:
            payload = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise Ts6QueryError(f"WebQuery 返回了非 JSON 内容：{raw[:200]}") from exc
        if not isinstance(payload, dict):
            raise Ts6QueryError("WebQuery 返回格式不正确：根节点不是对象")
        return payload

    def _build_url(
        self,
        command: str,
        params: dict[str, str | int],
        options: list[str],
        use_server_id: bool,
    ) -> str:
        path_parts = []
        if use_server_id:
            path_parts.append(str(self.server_id))
        path_parts.append(quote(command.strip("/")))
        query_parts = []
        if params:
            query_parts.append(urlencode({key: str(value) for key, value in params.items()}))
        query_parts.extend(f"-{quote(str(option).lstrip('-'))}" for option in options)
        query = "&".join(part for part in query_parts if part)
        return f"{self.base_url}/{'/'.join(path_parts)}" + (f"?{query}" if query else "")

    @property
    def base_url(self) -> str:
        host = self.host
        if ":" in host and not host.startswith("["):
            host = f"[{host}]"
        return f"{self.scheme}://{host}:{self.query_port}"

    def _extract_body(self, payload: dict[str, Any], command: str) -> list[dict[str, str]]:
        status = payload.get("status") or {}
        code = _safe_int(status.get("code"), 0)
        if code != 0:
            message = status.get("message") or status.get("msg") or "unknown error"
            raise Ts6QueryError(f"{command} 失败：{message} (code={code})")

        body = payload.get("body", [])
        if body is None:
            return []
        if isinstance(body, dict):
            body = [body]
        if not isinstance(body, list):
            raise Ts6QueryError(f"{command} 返回格式不正确：body 不是列表")

        records: list[dict[str, str]] = []
        for item in body:
            if isinstance(item, dict):
                records.append({str(key): str(value) for key, value in item.items()})
        return records


def _parse_connected_duration(detail: dict[str, str]) -> int:
    value = detail.get("connection_connected_time", "0") or "0"
    return max(0, _safe_int(value, 0) // 1000)


def _safe_int(value: object, default: int) -> int:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return default
