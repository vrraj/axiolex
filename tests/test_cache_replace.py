from axiolex.core.cache import ToolCacheManager


class FakePipeline:
    def __init__(self):
        self.commands = []

    def delete(self, *keys):
        self.commands.append(("delete", keys))
        return self

    def hset(self, key, mapping):
        self.commands.append(("hset", key, mapping))
        return self

    def set(self, key, value):
        self.commands.append(("set", key, value))
        return self

    def execute(self):
        self.commands.append(("execute",))


class FakeRedis:
    def __init__(self):
        self.pipeline_instance = FakePipeline()

    def keys(self, pattern):
        return ["axiolex:idx:tool:old", "axiolex:run:tool:old"]

    def pipeline(self, transaction):
        assert transaction is True
        return self.pipeline_instance


def test_replace_all_tools_uses_single_transaction_without_ttls():
    manager = ToolCacheManager()
    manager._client = FakeRedis()

    count = manager.replace_all_tools(
        [{
            "id": "quote",
            "title": "Quote",
            "description": "Get quote.",
            "tool_name": "get_quote",
            "params": {},
            "provider": "markets",
            "source": "mcp-discovery",
        }],
        [{
            "id": "quote",
            "runtime": {
                "tool_name": "get_quote",
                "transport": "streamable-http",
                "endpoint": "http://localhost:9001/mcp",
            },
        }],
    )

    assert count == 1
    assert manager._client.pipeline_instance.commands[-1] == ("execute",)
    assert any(
        command[0:2] == ("set", "axiolex:catalog:version")
        for command in manager._client.pipeline_instance.commands
    )
    assert not any(
        command[0] == "expire"
        for command in manager._client.pipeline_instance.commands
    )
