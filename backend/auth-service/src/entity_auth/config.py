from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ENTITY_", case_sensitive=False)

    oidc_issuer: str
    oidc_audience: str
    oidc_jwks_url: str
    database_url: str
    audit_hmac_key: str
    environment: str = "development"
    mfa_amr_values: str = "mfa,otp,hwk"
    privileged_max_rank: int = 3
    step_up_max_age_seconds: int = 300
    jwks_timeout_seconds: int = 5

    @field_validator("oidc_issuer")
    @classmethod
    def issuer_must_be_https(cls, value: str) -> str:
        if not value.startswith("https://"):
            raise ValueError("OIDC issuer must use HTTPS")
        return value

    @field_validator("oidc_jwks_url")
    @classmethod
    def jwks_must_be_https(cls, value: str) -> str:
        if not value.startswith("https://"):
            raise ValueError("JWKS URL must use HTTPS")
        return value

    @field_validator("database_url")
    @classmethod
    def require_postgres(cls, value: str) -> str:
        if not value.startswith("postgresql+psycopg://"):
            raise ValueError("ENTITY_DATABASE_URL must use PostgreSQL with psycopg")
        return value

    @field_validator("audit_hmac_key")
    @classmethod
    def require_audit_key(cls, value: str) -> str:
        if len(value.encode("utf-8")) < 32 or value.startswith("replace-"):
            raise ValueError("ENTITY_AUDIT_HMAC_KEY must be at least 32 bytes and privately set")
        return value

    @field_validator("environment")
    @classmethod
    def valid_environment(cls, value: str) -> str:
        normalized = value.lower()
        if normalized not in {"development", "staging", "production"}:
            raise ValueError("ENTITY_ENVIRONMENT must be development, staging, or production")
        return normalized

    @property
    def mfa_methods(self) -> frozenset[str]:
        return frozenset(item.strip().lower() for item in self.mfa_amr_values.split(",") if item.strip())


@lru_cache
def get_settings() -> Settings:
    return Settings()
