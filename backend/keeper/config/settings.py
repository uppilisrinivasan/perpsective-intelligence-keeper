"""Typed settings from `.env` and the process environment (docs/07-configuration/01-env-file.md).

Process environment variables override `.env`. Secrets are `SecretStr`, so they never print.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(os.environ.get("KEEPER_ROOT") or Path(__file__).resolve().parents[3])
ENV_FILE = ROOT / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(ENV_FILE), env_file_encoding="utf-8", extra="ignore",
                                      case_sensitive=True)

    # ---- Model provider
    LLM_PROVIDER: Literal["nebius", "openai_compatible", "fake"] = "nebius"
    NEBIUS_API_KEY: SecretStr = SecretStr("")
    NEBIUS_BASE_URL: str = "https://api.tokenfactory.nebius.com/v1/"
    LLM_BASE_URL: str = ""
    LLM_API_KEY: SecretStr = SecretStr("")
    KEEPER_MODEL_FAST: str = ""
    KEEPER_MODEL_JUDGE: str = ""
    KEEPER_MODEL_DEEP: str = ""
    KEEPER_MODEL_ASSISTANT: str = ""
    # ---- Gateway limits
    LLM_TIMEOUT_SECONDS: float = 120
    LLM_MAX_RETRIES: int = 4
    LLM_RETRY_BASE_SECONDS: float = 2
    LLM_MAX_CONCURRENCY: int = 8
    LLM_RATE_LIMIT_RPM: int = 120
    LLM_TOKENS_PER_DAY: int = 0
    LLM_CACHE: bool = True
    LLM_LOG_PROMPTS: bool = False
    # ---- Spending
    KEEPER_SPEND_CAP_USD: float = 20
    KEEPER_SPEND_CAP_PERIOD: Literal["day", "month", "total"] = "month"
    KEEPER_AUTO_APPROVE_USD: float = 0.05
    # ---- Batch and embeddings
    BATCH_API_ENABLED: bool = False
    EMBEDDINGS_PROVIDER: Literal["none", "nebius"] = "none"
    # ---- GitHub
    GITHUB_TOKEN: SecretStr = SecretStr("")
    GITHUB_API_URL: str = "https://api.github.com"
    IMPORT_ALLOWED: bool = True
    # ---- Sandbox
    SANDBOX_PROVIDER: Literal["contree", "docker", "local"] = "local"
    CONTREE_API_URL: str = ""
    CONTREE_API_KEY: SecretStr = SecretStr("")
    KEEPER_KEEP_SANDBOXES: bool = False
    # ---- External services
    TAVILY_API_KEY: SecretStr = SecretStr("")
    OSV_API_URL: str = "https://api.osv.dev/v1"
    # ---- App
    KEEPER_MODE: Literal["demo", "workspace"] = "demo"
    APP_HOST: str = "127.0.0.1"
    APP_PORT: int = 8430
    FRONTEND_DEV_PORT: int = 5174
    OPEN_BROWSER: bool = True
    KEEPER_DATA_DIR: str = "./data"
    KEEPER_RUNTIME_DIR: str = "./.runtime"
    KEEPER_CONFIG_DIR: str = "./config"
    DATABASE_URL: SecretStr = SecretStr("")
    LOG_LEVEL: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    JOB_WORKERS: int = 2
    API_DOCS: bool = True
    # ---- Cloud access
    KEEPER_AUTH_MODE: Literal["none", "access_code"] = "none"
    KEEPER_ACCESS_CODES: SecretStr = SecretStr("")
    KEEPER_SESSION_SECRET: SecretStr = SecretStr("")
    API_RATE_LIMIT_PER_MINUTE: int = 120
    KEEPER_ALLOW_OPEN: bool = False  # deliberately not in .env.example
    # ---- Jobs
    JOB_RUNNER: Literal["local", "nebius"] = "local"
    # ---- Data generation
    DATAGEN_PROFILE: str = "demo"
    DATAGEN_SEED: int = 20261025
    DATAGEN_SPEND_CAP_USD: float = 25
    DATAGEN_CONCURRENCY: int = 6
    # ---- Nebius deployment
    NEBIUS_PROJECT_ID: str = ""
    NEBIUS_REGION: str = "eu-north1"
    NEBIUS_REGISTRY: str = ""
    NEBIUS_SUBNET_ID: str = ""
    S3_ENDPOINT_URL: str = "https://storage.eu-north1.nebius.cloud"
    S3_REGION: str = "eu-north1"
    S3_BUCKET: str = ""
    S3_ACCESS_KEY_ID: SecretStr = SecretStr("")
    S3_SECRET_ACCESS_KEY: SecretStr = SecretStr("")
    NEBIUS_SA_CREDENTIALS: SecretStr = SecretStr("")
    LOG_FORMAT: Literal["", "text", "json"] = ""

    @field_validator("*", mode="before")
    @classmethod
    def _empty_means_default(cls, v: object, info) -> object:  # type: ignore[no-untyped-def]
        # An empty value in .env (KEY=) means "use the default", like an unset variable.
        if v == "" and info.field_name in _NON_STRING_FIELDS:
            return cls.model_fields[info.field_name].default
        return v

    # ---- Derived
    def path(self, value: str) -> Path:
        p = Path(value)
        return p if p.is_absolute() else (ROOT / p).resolve()

    @property
    def data_dir(self) -> Path:
        return self.path(self.KEEPER_DATA_DIR)

    @property
    def runtime_dir(self) -> Path:
        return self.path(self.KEEPER_RUNTIME_DIR)

    @property
    def config_dir(self) -> Path:
        return self.path(self.KEEPER_CONFIG_DIR)

    @property
    def database_url(self) -> str:
        url = self.DATABASE_URL.get_secret_value()
        return url or f"sqlite:///{self.runtime_dir / 'keeper.db'}"

    @property
    def api_key(self) -> str:
        if self.LLM_PROVIDER == "openai_compatible":
            return self.LLM_API_KEY.get_secret_value() or self.NEBIUS_API_KEY.get_secret_value()
        return self.NEBIUS_API_KEY.get_secret_value()

    @property
    def base_url(self) -> str:
        return self.LLM_BASE_URL if self.LLM_PROVIDER == "openai_compatible" else self.NEBIUS_BASE_URL

    @property
    def live(self) -> bool:
        """Live model calls are possible (a key is set, or the offline fake provider is chosen)."""
        return self.LLM_PROVIDER == "fake" or bool(self.api_key)

    @property
    def reason_if_not_live(self) -> str | None:
        if self.live:
            return None
        return "no_api_key"

    @property
    def log_format(self) -> str:
        if self.LOG_FORMAT:
            return self.LOG_FORMAT
        import sys
        return "text" if sys.stdout.isatty() else "json"

    def access_codes(self) -> list[str]:
        return [c.strip() for c in self.KEEPER_ACCESS_CODES.get_secret_value().split(",") if c.strip()]

    def secret_values(self) -> list[str]:
        out = []
        for name, field in type(self).model_fields.items():
            if field.annotation is SecretStr:
                v = getattr(self, name).get_secret_value()
                if v and len(v) >= 6:
                    out.append(v)
        return out


_NON_STRING_FIELDS = {n for n, f in Settings.model_fields.items() if f.annotation not in (str, SecretStr)}


class StartupError(RuntimeError):
    """Configuration that must stop the app (docs/07-configuration/01-env-file.md §3)."""


def validate_startup(s: Settings) -> list[str]:
    """Return warnings; raise StartupError for configurations that must not start."""
    warnings: list[str] = []
    if s.LLM_PROVIDER in ("nebius", "openai_compatible") and not s.api_key:
        warnings.append("No API key: starting in saved-results mode")
    if s.KEEPER_AUTH_MODE == "access_code":
        secret = s.KEEPER_SESSION_SECRET.get_secret_value()
        if not s.access_codes() or len(secret) < 32:
            raise StartupError("KEEPER_AUTH_MODE=access_code needs KEEPER_ACCESS_CODES and a KEEPER_SESSION_SECRET "
                               "of at least 32 characters.")
    if s.APP_HOST not in ("127.0.0.1", "localhost", "::1") and s.KEEPER_AUTH_MODE == "none" and not s.KEEPER_ALLOW_OPEN:
        raise StartupError(f"APP_HOST={s.APP_HOST} is not loopback while KEEPER_AUTH_MODE=none. Use access codes, "
                           "or set KEEPER_ALLOW_OPEN=true if you really mean it.")
    if s.KEEPER_SPEND_CAP_USD <= 0:
        raise StartupError("KEEPER_SPEND_CAP_USD must be greater than 0.")
    unknown = sorted(k for k in os.environ if k.startswith("KEEPER_") and k not in Settings.model_fields
                     and k not in ("KEEPER_ROOT",))
    if unknown:
        warnings.append("Unknown KEEPER_* variables (typo?): " + ", ".join(unknown))
    return warnings


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


def reset_settings() -> None:
    get_settings.cache_clear()
