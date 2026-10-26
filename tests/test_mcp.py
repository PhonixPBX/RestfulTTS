import base64
import json

import pytest
from mcp import Client

from restfultts.mcp_server import build_mcp


@pytest.fixture
def mcp(client):
    return build_mcp(client.app.state.service)


async def test_list_voices(mcp):
    async with Client(mcp) as c:
        tools = {t.name for t in (await c.list_tools()).tools}
        assert {"list_voices", "list_formats", "synthesize"} <= tools
        result = await c.call_tool("list_voices", {"language": "fr"})
        assert not result.is_error
        assert "ff_siwis" in json.dumps(result.structured_content)


async def test_synthesize_returns_audio(mcp):
    async with Client(mcp) as c:
        result = await c.call_tool("synthesize", {"text": "Hallo Welt", "language": "de", "format": "wav8"})
        assert not result.is_error
        audio, info = result.content
        assert audio.type == "audio"
        assert base64.b64decode(audio.data)[:4] == b"RIFF"
        meta = json.loads(info.text)
        assert meta["voice"] == "thorsten"
        assert meta["url"].endswith(".wav")


async def test_synthesize_error(mcp):
    async with Client(mcp) as c:
        result = await c.call_tool("synthesize", {"text": "x", "voice": "nobody"})
        assert result.is_error


def test_http_endpoint_and_auth(secured):
    init = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}
    headers = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json"}
    assert secured.post("/mcp", json=init, headers=headers).status_code == 401
    r = secured.post("/mcp", json=init, headers={**headers, "Authorization": "Bearer s3cret"})
    assert r.status_code == 200
    assert "synthesize" in {t["name"] for t in r.json()["result"]["tools"]}


async def test_delete_audio(mcp):
    async with Client(mcp) as c:
        result = await c.call_tool("synthesize", {"text": "Kurz", "language": "de"})
        url = json.loads(result.content[1].text)["url"]
        assert not (await c.call_tool("delete_audio", {"url": url})).is_error
        assert (await c.call_tool("delete_audio", {"url": url})).is_error
