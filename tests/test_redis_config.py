from axiolex.core.cache import RedisConfig


def test_redis_config_loads_shared_environment(monkeypatch):
    monkeypatch.setenv("AXIOLEX_REDIS_HOST", "redis.internal")
    monkeypatch.setenv("AXIOLEX_REDIS_PORT", "6381")
    monkeypatch.setenv("AXIOLEX_REDIS_DB", "2")

    config = RedisConfig.from_env()

    assert config.host == "redis.internal"
    assert config.port == 6381
    assert config.db == 2
