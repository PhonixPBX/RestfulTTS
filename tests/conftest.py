from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from restfultts.app import create_app
from restfultts.config import Settings
from restfultts.engine import FakeEngine


@pytest.fixture
def engine() -> FakeEngine:
    return FakeEngine()


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(data_dir=tmp_path, api_token="", max_text_chars=200, cache_max_mb=50, allowed_hosts="testserver")


@pytest.fixture
def client(settings: Settings, engine: FakeEngine) -> Iterator[TestClient]:
    with TestClient(create_app(settings, engine)) as c:
        yield c


@pytest.fixture
def secured(settings: Settings, engine: FakeEngine) -> Iterator[TestClient]:
    settings.api_token = "s3cret"
    with TestClient(create_app(settings, engine)) as c:
        yield c
