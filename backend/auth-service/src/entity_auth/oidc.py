from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from typing import Any

import jwt
from jwt import PyJWKClient

from entity_auth.config import get_settings


@dataclass(frozen=True)
class VerifiedToken:
    claims: dict[str, Any]
    token_hash: str


_jwks: PyJWKClient | None = None


def _client() -> PyJWKClient:
    global _jwks
    settings = get_settings()
    if _jwks is None:
        _jwks = PyJWKClient(settings.oidc_jwks_url, timeout=settings.jwks_timeout_seconds, cache_jwk_set=True)
    return _jwks


def verify_bearer(token: str, *, audience: str | None = None) -> VerifiedToken:
    settings = get_settings()
    expected_audience = audience or settings.oidc_audience
    signing_key = _client().get_signing_key_from_jwt(token)
    claims = jwt.decode(
        token,
        signing_key.key,
        algorithms=["RS256", "ES256"],
        audience=expected_audience,
        issuer=settings.oidc_issuer,
        options={"require": ["sub", "exp", "iat", "jti"]},
        leeway=30,
    )
    if not isinstance(claims.get("sub"), str) or not claims["sub"]:
        raise jwt.InvalidTokenError("Missing subject")
    jti = claims.get("jti")
    if not isinstance(jti, str) or not jti:
        raise jwt.InvalidTokenError("Missing or invalid token ID")
    token_identity = f"{settings.oidc_issuer}\0{expected_audience}\0{claims['sub']}\0{jti}"
    return VerifiedToken(claims=claims, token_hash=sha256(token_identity.encode("utf-8")).hexdigest())
