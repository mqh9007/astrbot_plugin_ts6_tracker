from __future__ import annotations

import argparse
import asyncio
from pathlib import Path
import sys

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from ts6_query import Ts6QueryError, Ts6WebQueryClient


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="独立的 TS6 WebQuery 测试脚本。")
    parser.add_argument("--host", required=True, help="TS6 服务器 IP 或域名")
    parser.add_argument("--api-key", required=True, help="WebQuery API Key")
    parser.add_argument("--server-id", type=int, default=1, help="虚拟服务器 ID，默认 1")
    parser.add_argument("--port", type=int, default=10080, help="WebQuery 端口，默认 10080")
    parser.add_argument("--scheme", choices=["http", "https"], default="http")
    parser.add_argument("--server-port", type=int, default=0, help="语音端口，仅用于显示兜底")
    parser.add_argument("--no-verify-tls", action="store_true", help="HTTPS 时不校验证书")
    return parser


async def main() -> int:
    args = build_parser().parse_args()
    client = Ts6WebQueryClient(
        host=args.host,
        server_id=args.server_id,
        api_key=args.api_key,
        query_port=args.port,
        scheme=args.scheme,
        server_port=args.server_port,
        verify_tls=not args.no_verify_tls,
    )
    try:
        status = await client.fetch_status()
    except Ts6QueryError as exc:
        print(f"查询失败：{exc}")
        return 1

    print(f"服务器：{status.server_name or '-'} ({status.server_host}:{status.server_port})")
    print(f"在线人数：{status.online_count}")
    for user in status.users:
        print(f"- [{user.channel_name or '未知频道'}] {user.nickname}")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
