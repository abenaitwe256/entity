import os
import secrets


os.environ.setdefault("ENTITY_OIDC_ISSUER", "https://identity.test.invalid/")
os.environ.setdefault("ENTITY_OIDC_AUDIENCE", "entity-api-tests")
os.environ.setdefault("ENTITY_OIDC_JWKS_URL", "https://identity.test.invalid/.well-known/jwks.json")
os.environ.setdefault("ENTITY_DATABASE_URL", "postgresql+psycopg://postgres@localhost:5432/entity")
os.environ.setdefault("ENTITY_AUDIT_HMAC_KEY", secrets.token_urlsafe(48))
os.environ.setdefault("ENTITY_ENVIRONMENT", "development")
os.environ.setdefault("ENTITY_ORIGINAL_OWNER_SUBJECT", "owner-sub")
os.environ.setdefault("ENTITY_ORIGINAL_OWNER_BOOTSTRAP_REVIEWER_SUBJECT", "reviewer-sub")

import pytest

from entity_auth.db import Base, engine


@pytest.fixture(autouse=True)
def isolated_database():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)
