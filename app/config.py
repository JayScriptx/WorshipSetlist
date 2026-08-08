"""
Application configuration.

All configuration is read from environment variables so the same codebase
works both locally (via a .env file) and on Render (via Render's
environment variable dashboard). Never hardcode secrets or credentials.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # PostgreSQL connection string, e.g.
    # postgresql+psycopg2://user:password@host:5432/dbname
    DATABASE_URL: str = "postgresql+psycopg2://worship:worship@localhost:5432/worship_setlist"

    # Used later for auth/session signing (V2). Kept now so the env var
    # contract is stable and doesn't need to change when auth is added.
    SECRET_KEY: str = "dev-secret-key-change-me"

    # Comma separated list of allowed CORS origins. "*" allows everything,
    # which is fine for a single-origin deployment (frontend served by the
    # same FastAPI app) but can be tightened later.
    CORS_ORIGINS: str = "*"

    # Dev convenience only: if true, tables are created directly from the
    # SQLAlchemy models on startup instead of relying on Alembic. This
    # should be left False in production - use `alembic upgrade head`.
    AUTO_CREATE_TABLES: bool = False

    ENVIRONMENT: str = "development"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        if self.CORS_ORIGINS.strip() == "*":
            return ["*"]
        return [o.strip() for o in self.CORS_ORIGINS.split(",") if o.strip()]


settings = Settings()
