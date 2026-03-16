import json
from urllib.parse import quote_plus

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def parse_origins(value: str | list[str] | None) -> list[str]:
    if value is None:
        return []

    if isinstance(value, list):
        return [origin.strip() for origin in value if isinstance(origin, str) and origin.strip()]

    if not isinstance(value, str):
        raise TypeError("CORS origins must be a string, list, or null")

    raw = value.strip()
    if not raw:
        return []

    if raw.startswith("["):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError("CORS_ORIGINS JSON list is invalid") from exc
        if not isinstance(parsed, list):
            raise ValueError("CORS_ORIGINS JSON value must be a list")
        return [origin.strip() for origin in parsed if isinstance(origin, str) and origin.strip()]

    return [origin.strip() for origin in raw.split(",") if origin.strip()]


def build_database_url(
    user: str,
    password: str,
    host: str,
    port: int,
    database: str,
) -> str:
    encoded_user = quote_plus(user)
    encoded_password = quote_plus(password)
    return f"postgresql+psycopg://{encoded_user}:{encoded_password}@{host}:{port}/{database}"


class Settings(BaseSettings):
    app_env: str = "development"
    database_url: str | None = None
    postgres_user: str = "postgres"
    postgres_password: str = "postgres"
    postgres_host: str = "localhost"
    postgres_port: int = 5432
    postgres_db: str = "personal_expense"
    cors_origins: list[str] = ["http://localhost:5173"]
    imports_storage_dir: str = "data/imports"
    avatars_storage_dir: str = "data/avatars"
    demo_mode: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        enable_decoding=False,
    )

    @model_validator(mode="after")
    def resolve_database_url(self) -> "Settings":
        if self.database_url:
            return self

        self.database_url = build_database_url(
            user=self.postgres_user,
            password=self.postgres_password,
            host=self.postgres_host,
            port=self.postgres_port,
            database=self.postgres_db,
        )
        return self

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_origins(cls, value):
        return parse_origins(value)


settings = Settings()
