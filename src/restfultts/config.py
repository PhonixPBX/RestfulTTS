"""Runtime settings, read from ``RESTFULTTS_*`` environment variables."""

from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="RESTFULTTS_", env_file=".env", extra="ignore")

    data_dir: Path = Path("data")
    # Bearer token for REST, MCP and the UI login; empty means open access (internal networks only).
    api_token: str = ""
    device: Literal["auto", "cpu", "cuda"] = "auto"
    # Thorsten-Voice/Kokoro checkpoint; 5 is the default `model.pth`.
    thorsten_epoch: Annotated[int, Field(ge=1, le=10)] = 5
    # Comma separated languages whose models are loaded at startup, e.g. "de,en".
    preload: str = ""
    max_text_chars: Annotated[int, Field(ge=1)] = 5000
    cache_max_mb: Annotated[int, Field(ge=0)] = 1024
    host: str = "127.0.0.1"
    port: int = 8000
    # Comma separated Host header names the server answers to ("*" = any, "*.example.org" = subdomains).
    # Empty: localhost/127.0.0.1 when listening on loopback, otherwise any.
    allowed_hosts: str = ""

    @property
    def trusted_hosts(self) -> list[str]:
        if self.allowed_hosts.strip():
            return [h.strip() for h in self.allowed_hosts.split(",") if h.strip()]
        if self.host in ("127.0.0.1", "localhost", "::1"):
            return ["localhost", "127.0.0.1"]
        return ["*"]

    @property
    def cache_dir(self) -> Path:
        return self.data_dir / "cache"

    @property
    def preload_languages(self) -> list[str]:
        return [lang.strip() for lang in self.preload.split(",") if lang.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
