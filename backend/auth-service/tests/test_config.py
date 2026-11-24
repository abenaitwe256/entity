import pytest
from pydantic import ValidationError

from entity_auth.config import Settings


BASE = {
    "oidc_issuer": "https://identity.example.test/",
    "oidc_audience": "entity-api",
    "oidc_jwks_url": "https://identity.example.test/.well-known/jwks.json",
    "database_url": "postgresql+psycopg://entity@localhost:5432/entity",
    "audit_hmac_key": "x" * 48,
    "original_owner_subject": "owner-sub",
    "original_owner_bootstrap_reviewer_subject": "reviewer-sub",
}


def settings(**overrides):
    return Settings(_env_file=None, **(BASE | overrides))


@pytest.mark.parametrize("field,value", [
    ("oidc_issuer", "http://identity.example.test/"),
    ("oidc_issuer", "https://user:pass@identity.example.test/"),
    ("oidc_jwks_url", "https://identity.example.test/keys?redirect=https://attacker.test"),
    ("database_url", "sqlite:///./entity.db"),
    ("audit_hmac_key", "short"),
])
def test_invalid_security_configuration_fails_closed(field, value):
    with pytest.raises(ValidationError):
        settings(**{field: value})


def test_partial_resource_registry_configuration_is_rejected():
    with pytest.raises(ValidationError):
        settings(resource_registry_audience="entity-registry")


def test_staging_requires_verified_postgres_tls_registry_and_pinned_owner():
    with pytest.raises(ValidationError):
        settings(
            environment="staging",
            resource_registry_audience="entity-registry",
            resource_registry_subjects="entity-resource-registry",
        )
    with pytest.raises(ValidationError):
        settings(
            environment="staging",
            database_url="postgresql+psycopg://entity@db.example.test/entity?sslmode=verify-full",
        )

    with pytest.raises(ValidationError, match="pinned ENTITY_ORIGINAL_OWNER_SUBJECT"):
        settings(
            environment="staging",
            database_url="postgresql+psycopg://entity@db.example.test/entity?sslmode=verify-full",
            resource_registry_audience="entity-registry",
            resource_registry_subjects="entity-resource-registry",
            original_owner_subject=None,
        )

    staging = settings(
        environment="staging",
        database_url="postgresql+psycopg://entity@db.example.test/entity?sslmode=verify-full",
        resource_registry_audience="entity-registry",
        resource_registry_subjects="entity-resource-registry",
    )
    assert staging.environment == "staging"
    assert staging.trusted_resource_registry_subjects == frozenset({"entity-resource-registry"})


def test_production_requires_verified_postgres_tls_and_trusted_registry():
    with pytest.raises(ValidationError):
        settings(
            environment="production",
            database_url="postgresql+psycopg://entity@db.example.test/entity",
            resource_registry_audience="entity-registry",
            resource_registry_subjects="entity-resource-registry",
        )
    with pytest.raises(ValidationError):
        settings(
            environment="production",
            database_url="postgresql+psycopg://entity@db.example.test/entity?sslmode=verify-full",
        )

    with pytest.raises(ValidationError, match="pinned ENTITY_ORIGINAL_OWNER_SUBJECT"):
        settings(
            environment="production",
            database_url="postgresql+psycopg://entity@db.example.test/entity?sslmode=verify-full",
            resource_registry_audience="entity-registry",
            resource_registry_subjects="entity-resource-registry",
            original_owner_subject=None,
        )

    production = settings(
        environment="production",
        database_url="postgresql+psycopg://entity@db.example.test/entity?sslmode=verify-full",
        resource_registry_audience="entity-registry",
        resource_registry_subjects="entity-resource-registry",
    )
    assert production.environment == "production"
    assert production.trusted_resource_registry_subjects == frozenset({"entity-resource-registry"})
