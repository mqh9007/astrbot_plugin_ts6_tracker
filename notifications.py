from __future__ import annotations

import time


DEFAULT_ONLINE_MESSAGE_TEMPLATE = (
    "让我看看是谁还没上号 👀\\n"
    "🧾 昵称：{nickname}\\n"
    "🟢 上线时间：{time}\\n"
    "📣 {nickname} 进入了 TS 服务器\\n"
    "👥 当前在线人数：{total_users}\\n"
    "📜 在线列表：{online_list}"
)

DEFAULT_OFFLINE_MESSAGE_TEMPLATE = (
    "📤 用户下线通知\\n"
    "🧾 昵称：{nickname}\\n"
    "🟢 上线时间：{start_time}\\n"
    "🔴 下线时间：{end_time}\\n"
    "⏱️ 在线时长：{duration}\\n"
    "👥 当前在线人数：{online_count}\\n"
    "📜 在线列表：{online_list}"
)


def format_timestamp(timestamp: float) -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(timestamp))


def format_duration(duration_seconds: int) -> str:
    seconds = max(0, int(duration_seconds))
    days, remainder = divmod(seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)

    parts: list[str] = []
    if days:
        parts.append(f"{days}天")
    if hours:
        parts.append(f"{hours}小时")
    if minutes:
        parts.append(f"{minutes}分钟")
    if seconds or not parts:
        parts.append(f"{seconds}秒")
    return "".join(parts)


class SafeTemplateDict(dict):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def _build_online_list_text(online_names: list[str]) -> str:
    return ", ".join(online_names) if online_names else "（无在线用户）"


def _normalize_template_text(template: str) -> str:
    return (
        str(template or "")
        .replace("\\r\\n", "\n")
        .replace("\\n", "\n")
        .replace("\\t", "\t")
    )


def render_message_template(
    template: str,
    context: dict[str, object],
    fallback_template: str,
) -> str:
    selected_template = _normalize_template_text(template).strip() or _normalize_template_text(
        fallback_template
    )
    normalized_fallback = _normalize_template_text(fallback_template)
    try:
        return selected_template.format_map(SafeTemplateDict(context))
    except Exception:
        return normalized_fallback.format_map(SafeTemplateDict(context))


def build_online_message(
    nickname: str,
    timestamp: float,
    total_users: int,
    online_names: list[str],
    template: str = DEFAULT_ONLINE_MESSAGE_TEMPLATE,
) -> str:
    formatted_time = format_timestamp(timestamp)
    context = {
        "nickname": nickname,
        "username": nickname,
        "time": formatted_time,
        "timestamp": formatted_time,
        "start_time": formatted_time,
        "online_time": formatted_time,
        "total_users": total_users,
        "online_count": total_users,
        "online_list": _build_online_list_text(online_names),
    }
    return render_message_template(template, context, DEFAULT_ONLINE_MESSAGE_TEMPLATE)


def build_offline_message(
    nickname: str,
    start_ts: float,
    end_ts: float,
    online_names: list[str],
    template: str = DEFAULT_OFFLINE_MESSAGE_TEMPLATE,
) -> str:
    duration = int(end_ts - start_ts)
    start_time = format_timestamp(start_ts)
    end_time = format_timestamp(end_ts)
    total_users = len(online_names)
    context = {
        "nickname": nickname,
        "username": nickname,
        "time": end_time,
        "timestamp": end_time,
        "start_time": start_time,
        "end_time": end_time,
        "offline_time": end_time,
        "duration": format_duration(duration),
        "total_users": total_users,
        "online_count": total_users,
        "online_list": _build_online_list_text(online_names),
    }
    return render_message_template(template, context, DEFAULT_OFFLINE_MESSAGE_TEMPLATE)
