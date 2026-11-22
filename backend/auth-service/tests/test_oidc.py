from datetime import datetime, timedelta, timezone

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from entity_auth import oidc


class FakeSigningKey:
    def __init__(self, key):
        self.key = key


class FakeJwksClient:
    def __init__(self, key):
        self.key = key

    def get_signing_key_from_jwt(self, _token):
        return FakeSigningKey(self.key)


@pytest.fixture
def signing_key(monkeypatch):
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    monkeypatch.setattr(oidc, "_client", lambda: FakeJwksClient(private_key.public_key()))
    return private_key


def claims(**overrides):
    payload = {
        "sub": "user-sub", "iss": "https://identity.test.invalid/", "aud": "entity-api-tests",
        "iat": datetime.now(timezone.utc), "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
        "jti": "opaque-token-id",
    }
    payload.update(overrides)
    return payload


def test_valid_access_token_is_verified_and_jti_is_hashed(signing_key):
    token = jwt.encode(claims(), signing_key, algorithm="RS256", headers={"kid": "test"})
    verified = oidc.verify_bearer(token)
    assert verified.claims["sub"] == "user-sub"
    assert verified.token_hash != "opaque-token-id"
    assert len(verified.token_hash) == 64


@pytest.mark.parametrize("overrides", [
    {"iss": "https://attacker.invalid/"},
    {"aud": "different-api"},
    {"exp": datetime.now(timezone.utc) - timedelta(minutes=1)},
    {"sub": ""},
])
def test_invalid_issuer_audience_expiry_or_subject_is_rejected(signing_key, overrides):
    token = jwt.encode(claims(**overrides), signing_key, algorithm="RS256", headers={"kid": "test"})
    with pytest.raises(jwt.PyJWTError):
        oidc.verify_bearer(token)
