# AstrBot TeamSpeak 6 查询与通知插件

这是一个给 AstrBot 使用的 TeamSpeak 6 插件，功能对齐旧版 TS3 Tracker：

- 查询当前 TS6 在线用户
- 查询 TS6 服务器名称、地址、端口和频道信息
- 按频道展示在线成员
- 可选显示在线时长
- 可选限制只有指定群可以触发插件命令
- 支持自定义进服/退服通知模板
- 持续监听成员上线、离线，并向已绑定会话推送通知

## TS6 连接方式

TS6 不再使用 TS3 的 telnet ServerQuery。本插件使用 TS6 的 HTTP/HTTPS WebQuery：

- HTTP Query 默认端口：`10080`
- HTTPS Query 默认端口：`10443`
- 认证方式：HTTP 请求头 `x-api-key`
- 命令路径示例：`http://127.0.0.1:10080/1/serverinfo`

服务器需要开启 HTTP Query：

```bash
./tsserver --query-http-enable --query-http-port 10080
```

Docker 环境可使用环境变量：

```bash
TSSERVER_QUERY_HTTP_ENABLED=1
TSSERVER_QUERY_HTTP_PORT=10080
```

API Key 需要由有权限的查询账号创建，例如通过 TS6 的 SSH Query 执行：

```text
apikeyadd scope=manage lifetime=0
```

## 配置项

在 AstrBot 插件配置页填写：

- `server_host`：TS6 服务器 IP 或域名
- `server_port`：语音端口，仅用于显示兜底；留 `0` 时优先使用 `serverinfo` 返回值
- `virtual_server_id`：虚拟服务器 ID，默认 `1`
- `webquery_scheme`：`http` 或 `https`
- `webquery_port`：WebQuery 端口，默认 `10080`
- `webquery_api_key`：WebQuery API Key
- `verify_tls`：HTTPS 时是否校验证书；自签证书可关闭
- `enable_plain_text_trigger`：是否允许 `ts`、`上号`、`人呢` 这种无前缀触发
- `show_online_duration_in_status`：在线列表是否显示在线时长
- `enable_group_whitelist` / `group_whitelist`：群白名单
- `enable_monitor` / `monitor_interval_seconds`：上下线监听
- `online_message_template` / `offline_message_template`：通知模板
- `debug`：输出详细日志

## 使用命令

普通查询：

```text
/ts
/上号
/人呢
/tsinfo
/ts服务器
```

通知绑定，需管理员权限：

```text
/tsnotify status
/tsnotify on
/tsnotify off
/tsbind
/tsunbind
```

清空插件本地状态，需管理员权限：

```text
/tsdbclear 确认
```

## 本地测试

可以先用独立脚本验证 WebQuery 是否可用：

```bash
python ts6_test_cli.py --host 127.0.0.1 --api-key YOUR_API_KEY --server-id 1 --port 10080
```

如果这里能列出在线用户，AstrBot 插件配置相同参数即可。
