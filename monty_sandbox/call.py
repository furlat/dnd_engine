"""Make one real MCP call; arguments come from JSON stdin, output is JSON."""
import argparse
import asyncio
import json
import sys

from mcp import Client


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('tool', help='Tool name, or list')
    parser.add_argument('--url', default='http://127.0.0.1:18892/mcp')
    args = parser.parse_args()
    async with Client(args.url, read_timeout_seconds=70) as client:
        if args.tool == 'list':
            result = await client.list_tools()
            print(result.model_dump_json())
        else:
            result = await client.call_tool(args.tool, json.load(sys.stdin))
            print(json.dumps({'is_error': result.is_error, 'data': result.structured_content,
                'errors': [part.model_dump() for part in result.content] if result.is_error else []}))


if __name__ == '__main__':
    asyncio.run(main())
