"""Start the real stdio server with an empty temporary account profile."""
import asyncio
import json
import os
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def main():
    root = Path(__file__).resolve().parent
    with TemporaryDirectory() as profile:
        env = dict(os.environ, LOCALAPPDATA=profile)
        if sys.platform != 'win32':
            env['HOME'] = profile
        params = StdioServerParameters(command="node",
            args=[str(root / 'plugins/ssu-lms/launch.cjs')], env=env)
        async with stdio_client(params) as (reader, writer):
            async with ClientSession(reader, writer) as client:
                await client.initialize()
                names = {tool.name for tool in (await client.list_tools()).tools}
                assert {'auth_status', 'start_login', 'restore_learningx_session',
                        'list_courses', 'list_materials', 'lecture_transcript'} <= names
                result = await client.call_tool('auth_status', {})
                assert not result.isError
                data = json.loads(next(item.text for item in result.content if item.type == 'text'))
                assert data['authenticated'] is False
                assert data['verified_live'] is False
                print(f'MCP startup, {len(names)} tools and unauthenticated call passed')

if __name__ == '__main__':
    asyncio.run(asyncio.wait_for(main(), timeout=30))
