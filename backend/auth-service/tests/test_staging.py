import json

import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from jwt.algorithms import RSAAlgorithm

from entity_auth.staging import StagingValidationError, validate_provider_documents


ISSUER = "https://sso.example.test/realms/entity-staging"
JWKS_URL = "https://sso.example.test/realms/entity-staging/protocol/openid-connect/certs"
DISCOVERY = {
    "issuer": ISSUER,
    "jwks_uri": JWKS_URL,
    "id_token_signing_alg_values_supported": ["RS256"],
}


def _public_jwk():
    public_key = rsa.generate_private_key(
        public_exponent=65537, key_size=2048,
    ).public_key()
    return {
        **json.loads(RSAAlgorithm.to_jwk(public_key)),
        "kid": "staging-key-1",
        "use": "sig",
        "alg": "RS256",
    }


JWKS = {"keys": [_public_jwk()]}


def test_oidc_staging_document_validation_is_provider_neutral():
    validate_provider_documents(ISSUER, JWKS_URL, DISCOVERY, JWKS)


@pytest.mark.parametrize("field,value", [
    ("issuer", "https://attacker.example.test/realms/entity-staging"),
    ("jwks_uri", "https://attacker.example.test/keys"),
])
def test_oidc_staging_rejects_discovery_mismatch(field, value):
    discovery = DISCOVERY | {field: value}
    with pytest.raises(StagingValidationError):
        validate_provider_documents(ISSUER, JWKS_URL, discovery, JWKS)


def test_oidc_staging_rejects_unsupported_algorithms():
    discovery = DISCOVERY | {"id_token_signing_alg_values_supported": ["HS256"]}
    with pytest.raises(StagingValidationError):
        validate_provider_documents(ISSUER, JWKS_URL, discovery, JWKS)


def test_oidc_staging_rejects_malformed_discovery_algorithms():
    discovery = DISCOVERY | {"id_token_signing_alg_values_supported": [{}]}
    with pytest.raises(StagingValidationError):
        validate_provider_documents(ISSUER, JWKS_URL, discovery, JWKS)


def test_oidc_staging_rejects_jwks_without_permitted_signing_keys():
    jwks = {"keys": [{"kid": "wrong", "kty": "oct", "use": "sig", "alg": "HS256"}]}
    with pytest.raises(StagingValidationError):
        validate_provider_documents(ISSUER, JWKS_URL, DISCOVERY, jwks)



def test_oidc_staging_rejects_key_algorithm_mismatch():
    jwks = {"keys": [{
        "kid": "wrong-key",
        "kty": "EC",
        "use": "sig",
        "alg": "RS256",
        "crv": "P-256",
        "x": "AQ",
        "y": "AQ",
    }]}
    with pytest.raises(StagingValidationError):
        validate_provider_documents(ISSUER, JWKS_URL, DISCOVERY, jwks)


def test_oidc_staging_rejects_key_without_verification_use():
    jwks = {"keys": [{
        **_public_jwk(),
        "key_ops": ["sign"],
    }]}
    with pytest.raises(StagingValidationError):
        validate_provider_documents(ISSUER, JWKS_URL, DISCOVERY, jwks)


def test_oidc_staging_rejects_non_object_documents():
    with pytest.raises(StagingValidationError):
        validate_provider_documents(ISSUER, JWKS_URL, [], JWKS)
    with pytest.raises(StagingValidationError):
        validate_provider_documents(ISSUER, JWKS_URL, DISCOVERY, [])


def test_oidc_staging_rejects_ambiguous_duplicate_key_ids():
    key = _public_jwk()
    with pytest.raises(StagingValidationError, match="duplicate"):
        validate_provider_documents(ISSUER, JWKS_URL, DISCOVERY, {"keys": [key, key]})
