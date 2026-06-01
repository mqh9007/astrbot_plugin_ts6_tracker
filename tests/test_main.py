from __future__ import annotations

import asyncio
import importlib
import sys
import types
import unittest
from pathlib import Path
from types import SimpleNamespace


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def _install_astrbot_stubs() -> None:
    if "astrbot" in sys.modules:
        return

    astrbot_module = types.ModuleType("astrbot")
    api_module = types.ModuleType("astrbot.api")
    event_module = types.ModuleType("astrbot.api.event")
    star_module = types.ModuleType("astrbot.api.star")
    core_module = types.ModuleType("astrbot.core")
    utils_module = types.ModuleType("astrbot.core.utils")
    astrbot_path_module = types.ModuleType("astrbot.core.utils.astrbot_path")

    class DummyLogger:
        def info(self, *args, **kwargs):
            return None

        def warning(self, *args, **kwargs):
            return None

        def exception(self, *args, **kwargs):
            return None

    class DummyMessageChain:
        def message(self, text):
            self.text = text
            return self

    class DummyFilter:
        class PermissionType:
            ADMIN = "admin"

        class EventMessageType:
            ALL = "all"

        def command(self, *args, **kwargs):
            return lambda func: func

        def permission_type(self, *args, **kwargs):
            return lambda func: func

        def event_message_type(self, *args, **kwargs):
            return lambda func: func

        def on_astrbot_loaded(self, *args, **kwargs):
            return lambda func: func

    class DummyStar:
        def __init__(self, context=None):
            self.context = context

    def register(*args, **kwargs):
        return lambda cls: cls

    api_module.AstrBotConfig = dict
    api_module.logger = DummyLogger()
    event_module.AstrMessageEvent = object
    event_module.MessageChain = DummyMessageChain
    event_module.filter = DummyFilter()
    star_module.Context = object
    star_module.Star = DummyStar
    star_module.register = register
    astrbot_path_module.get_astrbot_data_path = lambda: str(REPO_ROOT / "test_data")

    sys.modules["astrbot"] = astrbot_module
    sys.modules["astrbot.api"] = api_module
    sys.modules["astrbot.api.event"] = event_module
    sys.modules["astrbot.api.star"] = star_module
    sys.modules["astrbot.core"] = core_module
    sys.modules["astrbot.core.utils"] = utils_module
    sys.modules["astrbot.core.utils.astrbot_path"] = astrbot_path_module


_install_astrbot_stubs()
plugin_module = importlib.import_module("main")
notifications_module = importlib.import_module("notifications")
query_module = importlib.import_module("ts6_query")


def _make_plugin(config: dict | None = None):
    plugin = object.__new__(plugin_module.Ts6TrackerPlugin)
    plugin.config = config or {}
    plugin.monitor_task = None
    plugin._recent_message_claims = {}
    plugin.storage = None
    plugin.presence_tracker = None
    plugin.context = SimpleNamespace()
    return plugin


def _make_event(group_id=None):
    return SimpleNamespace(
        get_group_id=lambda: group_id,
        message_obj=SimpleNamespace(group_id=group_id),
    )


class MemoryStorage:
    def __init__(self):
        self.meta = {}

    def get_meta(self, key, default=None):
        return self.meta.get(key, default)

    def set_meta(self, key, value):
        self.meta[key] = value


class Ts6TrackerPluginTests(unittest.TestCase):
    def test_status_message_without_duration_toggle(self):
        plugin = _make_plugin({"show_online_duration_in_status": False})
        status = SimpleNamespace(
            users=[
                SimpleNamespace(
                    nickname="test",
                    channel_name="APEX",
                    connected_duration_seconds=1380,
                )
            ],
            channel_names=["APEX"],
        )

        async def fake_fetch_status():
            return status

        plugin._fetch_status = fake_fetch_status

        message = asyncio.run(plugin._build_status_message())
        self.assertEqual(message, "APEX:\ntest")

    def test_status_message_with_duration_toggle(self):
        plugin = _make_plugin({"show_online_duration_in_status": True})
        status = SimpleNamespace(
            users=[
                SimpleNamespace(
                    nickname="test",
                    channel_name="APEX",
                    connected_duration_seconds=1380,
                )
            ],
            channel_names=["APEX"],
        )

        async def fake_fetch_status():
            return status

        plugin._fetch_status = fake_fetch_status

        message = asyncio.run(plugin._build_status_message())
        self.assertEqual(message, "APEX:\ntest(23分钟)")

    def test_status_message_puts_each_user_on_own_line(self):
        plugin = _make_plugin({"show_online_duration_in_status": True})
        status = SimpleNamespace(
            users=[
                SimpleNamespace(
                    nickname="alpha",
                    channel_name="APEX",
                    connected_duration_seconds=60,
                ),
                SimpleNamespace(
                    nickname="bravo",
                    channel_name="APEX",
                    connected_duration_seconds=3600,
                ),
            ],
            channel_names=["APEX"],
        )

        async def fake_fetch_status():
            return status

        plugin._fetch_status = fake_fetch_status

        message = asyncio.run(plugin._build_status_message())
        self.assertEqual(message, "APEX:\nalpha(1分钟)\nbravo(1小时)")

    def test_group_whitelist_allows_private_chat(self):
        plugin = _make_plugin(
            {
                "enable_group_whitelist": True,
                "group_whitelist": "123456789",
            }
        )

        self.assertTrue(plugin._is_group_event_allowed(_make_event(group_id=None)))

    def test_group_whitelist_allows_listed_group(self):
        plugin = _make_plugin(
            {
                "enable_group_whitelist": True,
                "group_whitelist": "123456789,987654321",
            }
        )

        self.assertTrue(plugin._is_group_event_allowed(_make_event(group_id="987654321")))

    def test_group_whitelist_blocks_unlisted_group(self):
        plugin = _make_plugin(
            {
                "enable_group_whitelist": True,
                "group_whitelist": "123456789\n987654321",
            }
        )

        self.assertFalse(plugin._is_group_event_allowed(_make_event(group_id="555555555")))

    def test_online_message_supports_custom_template_variables(self):
        expected_time = notifications_module.format_timestamp(0)
        message = notifications_module.build_online_message(
            nickname="test_user",
            timestamp=0,
            total_users=3,
            online_names=["test_user", "foo", "bar"],
            template="{nickname}|{time}|{online_count}|{online_list}",
        )

        self.assertEqual(
            message,
            f"test_user|{expected_time}|3|test_user, foo, bar",
        )

    def test_offline_message_supports_custom_template_variables(self):
        expected_start_time = notifications_module.format_timestamp(0)
        expected_end_time = notifications_module.format_timestamp(1380)
        message = notifications_module.build_offline_message(
            nickname="test_user",
            start_ts=0,
            end_ts=1380,
            online_names=["foo", "bar"],
            template="{username}|{start_time}|{end_time}|{duration}|{total_users}",
        )

        self.assertEqual(
            message,
            f"test_user|{expected_start_time}|{expected_end_time}|23分钟|2",
        )

    def test_invalid_template_falls_back_to_default_message(self):
        message = notifications_module.build_online_message(
            nickname="test_user",
            timestamp=0,
            total_users=1,
            online_names=["test_user"],
            template="{nickname",
        )

        self.assertIn("test_user", message)
        self.assertIn("上线时间", message)

    def test_template_backslash_n_is_rendered_as_newline(self):
        message = notifications_module.build_online_message(
            nickname="test_user",
            timestamp=0,
            total_users=1,
            online_names=["test_user"],
            template="第一行\\n第二行：{nickname}",
        )

        self.assertEqual(message, "第一行\n第二行：test_user")

    def test_ts6_webquery_url_uses_server_id_and_options(self):
        client = query_module.Ts6WebQueryClient(
            host="127.0.0.1",
            server_id=1,
            api_key="secret",
            query_port=10080,
        )

        url = client._build_url(
            "clientlist",
            params={"clid": 7},
            options=["uid", "-away", "ip"],
            use_server_id=True,
        )

        self.assertEqual(
            url,
            "http://127.0.0.1:10080/1/clientlist?clid=7&-uid&-away&-ip",
        )

    def test_ts6_webquery_extracts_body_and_status_errors(self):
        client = query_module.Ts6WebQueryClient(
            host="127.0.0.1",
            server_id=1,
            api_key="secret",
        )

        records = client._extract_body(
            {
                "status": {"code": 0, "message": "ok"},
                "body": {"virtualserver_name": "My TS6"},
            },
            "serverinfo",
        )
        self.assertEqual(records, [{"virtualserver_name": "My TS6"}])

        with self.assertRaises(query_module.Ts6QueryError):
            client._extract_body(
                {"status": {"code": 256, "message": "insufficient permissions"}},
                "serverinfo",
            )

    def test_ts6_config_requires_host_and_api_key(self):
        plugin = _make_plugin({"server_host": "127.0.0.1"})

        self.assertEqual(plugin._get_missing_required_fields(), ["WebQuery API Key"])

    def test_ts6_status_query_uses_sequential_webquery_requests(self):
        client = query_module.Ts6WebQueryClient(
            host="127.0.0.1",
            server_id=1,
            api_key="secret",
        )
        calls = []

        async def fake_execute(command, params=None, options=None, use_server_id=True):
            calls.append((command, tuple(options or [])))
            if command == "serverinfo":
                return [{"virtualserver_name": "TS6", "virtualserver_port": "9987"}]
            if command == "channellist":
                return [{"cid": "1", "channel_name": "大厅"}]
            if command == "clientlist":
                return []
            return []

        client._execute = fake_execute

        status = asyncio.run(client.fetch_status())

        self.assertEqual(status.server_name, "TS6")
        self.assertEqual(
            calls,
            [
                ("serverinfo", ()),
                ("channellist", ()),
                ("clientlist", ()),
            ],
        )

    def test_ts6_status_query_skips_clientinfo_by_default(self):
        client = query_module.Ts6WebQueryClient(
            host="127.0.0.1",
            server_id=1,
            api_key="secret",
        )
        calls = []

        async def fake_execute(command, params=None, options=None, use_server_id=True):
            calls.append(command)
            if command == "serverinfo":
                return [{"virtualserver_name": "TS6", "virtualserver_port": "9987"}]
            if command == "channellist":
                return [{"cid": "1", "channel_name": "大厅"}]
            if command == "clientlist":
                return [
                    {
                        "clid": "351",
                        "cid": "1",
                        "client_nickname": "tester",
                        "client_type": "0",
                        "connection_connected_time": "1380000",
                    }
                ]
            if command == "clientinfo":
                raise AssertionError("clientinfo should be skipped by default")
            return []

        client._execute = fake_execute

        status = asyncio.run(client.fetch_status())

        self.assertEqual(status.users[0].nickname, "tester")
        self.assertEqual(status.users[0].connected_duration_seconds, 1380)
        self.assertNotIn("clientinfo", calls)

    def test_ts6_status_query_accepts_clientlist_duration_seconds(self):
        client = query_module.Ts6WebQueryClient(
            host="127.0.0.1",
            server_id=1,
            api_key="secret",
        )

        async def fake_execute(command, params=None, options=None, use_server_id=True):
            if command == "serverinfo":
                return [{"virtualserver_name": "TS6", "virtualserver_port": "9987"}]
            if command == "channellist":
                return [{"cid": "1", "channel_name": "大厅"}]
            if command == "clientlist":
                return [
                    {
                        "clid": "351",
                        "cid": "1",
                        "client_nickname": "tester",
                        "client_type": "0",
                        "connection_duration": "1380",
                    }
                ]
            return []

        client._execute = fake_execute

        status = asyncio.run(client.fetch_status())

        self.assertEqual(status.users[0].connected_duration_seconds, 1380)

    def test_ts6_status_query_ignores_clientinfo_failures_when_enabled(self):
        client = query_module.Ts6WebQueryClient(
            host="127.0.0.1",
            server_id=1,
            api_key="secret",
            fetch_client_details=True,
        )

        async def fake_execute(command, params=None, options=None, use_server_id=True):
            if command == "serverinfo":
                return [{"virtualserver_name": "TS6", "virtualserver_port": "9987"}]
            if command == "channellist":
                return [{"cid": "1", "channel_name": "大厅"}]
            if command == "clientlist":
                return [
                    {
                        "clid": "351",
                        "cid": "1",
                        "client_nickname": "tester",
                        "client_type": "0",
                    }
                ]
            if command == "clientinfo":
                raise query_module.Ts6QueryError("clientinfo disconnected")
            return []

        client._execute = fake_execute

        status = asyncio.run(client.fetch_status())

        self.assertEqual(status.online_count, 1)
        self.assertEqual(status.users[0].nickname, "tester")

    def test_local_duration_estimate_updates_zero_duration_users(self):
        plugin = _make_plugin({"enable_local_duration_estimate": True})
        plugin.storage = MemoryStorage()
        user = SimpleNamespace(
            unique_id="",
            database_id="",
            client_id="351",
            nickname="tester",
            connected_duration_seconds=0,
        )
        status = SimpleNamespace(
            server_host="127.0.0.1",
            server_port=9987,
            users=[user],
        )
        original_time = plugin_module.time.time
        try:
            plugin_module.time.time = lambda: 100
            plugin._apply_local_duration_estimates(status)
            self.assertEqual(user.connected_duration_seconds, 0)

            plugin_module.time.time = lambda: 160
            plugin._apply_local_duration_estimates(status)
            self.assertEqual(user.connected_duration_seconds, 60)
        finally:
            plugin_module.time.time = original_time

    def test_local_duration_estimate_preserves_server_duration(self):
        plugin = _make_plugin({"enable_local_duration_estimate": True})
        plugin.storage = MemoryStorage()
        user = SimpleNamespace(
            unique_id="",
            database_id="",
            client_id="351",
            nickname="tester",
            connected_duration_seconds=1380,
        )
        status = SimpleNamespace(
            server_host="127.0.0.1",
            server_port=9987,
            users=[user],
        )

        plugin._apply_local_duration_estimates(status)

        self.assertEqual(user.connected_duration_seconds, 1380)


if __name__ == "__main__":
    unittest.main()
