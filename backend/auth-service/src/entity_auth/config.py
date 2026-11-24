from functools import lru_cache
from urllib.parse import parse_qs, urlsplit

from pydantic import Field, field_validator, model_validator
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
    privileged_max_rank: int = Field(default=3, ge=0, le=6)
    step_up_max_age_seconds: int = Field(default=300, ge=1, le=3600)
    jwks_timeout_seconds: int = Field(default=5, ge=1, le=30)
    resource_registry_audience: str | None = None
    resource_registry_subjects: str = ""

    @field_validator("oidc_issuer", "oidc_jwks_url")
    @classmethod
    def secure_https_url(cls, value: str) -> str:
        parsed = urlsplit(value)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.fragment
        ):
            raise ValueError("OIDC issuer and JWKS URL must be absolute HTTPS URLs without user info or fragments")
        if parsed.query:
            raise ValueError("OIDC issuer and JWKS URL must not contain query strings")
        return value

    @field_validator("oidc_audience")
    @classmethod
    def nonempty_audience(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("ENTITY_OIDC_AUDIENCE must not be empty")
        return value.strip()

    @field_validator("resource_registry_audience", mode="before")
    @classmethod
    def blank_registry_audience_is_disabled(cls, value: object) -> object:
        return None if value == "" else value

    @field_validator("resource_registry_audience")
    @classmethod
    def nonempty_registry_audience(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            raise ValueError("ENTITY_RESOURCE_REGISTRY_AUDIENCE must not be empty")
        return value.strip() if value is not None else None

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

    @field_validator("mfa_amr_values")
    @classmethod
    def require_mfa_amr_values(cls, value: str) -> str:
        if not {item.strip().lower() for item in value.split(",") if item.strip()}:
            raise ValueError("ENTITY_MFA_AMR_VALUES must include at least one provider MFA claim")
        return value

    @model_validator(mode="after")
    def validate_resource_registry_configuration(self) -> "Settings":
        has_audience = self.resource_registry_audience is not None
        has_subjects = bool(self.resource_registry_subjects.strip())
        if has_audience != has_subjects:
            raise ValueError(
                "Configure both ENTITY_RESOURCE_REGISTRY_AUDIENCE and "
                "ENTITY_RESOURCE_REGISTRY_SUBJECTS, or leave both unset"
            )
        if self.environment in {"staging", "production"}:
            sslmode = parse_qs(urlsplit(self.database_url).query).get("sslmode", [])
            if sslmode != ["verify-full"]:
                raise ValueError("Staging and production PostgreSQL connections must use sslmode=verify-full")
            if not has_audience:
                raise ValueError("Staging and production require a dedicated trusted resource-registry identity")
        return self

    @property
    def mfa_methods(self) -> frozenset[str]:
        return frozenset(item.strip().lower() for item in self.mfa_amr_values.split(",") if item.strip())

    @property
    def trusted_resource_registry_subjects(self) -> frozenset[str]:
        return frozenset(item.strip() for item in self.resource_registry_subjects.split(",") if item.strip())


@lru_cache
def get_settings() -> Settings:
    return Settings()
