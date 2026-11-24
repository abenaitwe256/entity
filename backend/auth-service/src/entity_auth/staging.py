from __future__ import annotations

import json
import os
import ssl
import sys
from typing import Any

import jwt
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, HTTPSHandler, Request, build_opener

from entity_auth.config import get_settings


_ALLOWED_ALGORITHMS = {"RS256", "ES256"}
_MAX_RESPONSE_BYTES = 1_048_576


class StagingValidationError(RuntimeError):
    pass


def validate_provider_documents(
    issuer: str,
    jwks_url: str,
    discovery: dict[str, Any],
    jwks: dict[str, Any],
) -> None:
    """Validate OIDC discovery and signing-key metadata without provider-specific assumptions."""
    if not isinstance(discovery, dict) or not isinstance(jwks, dict):
        raise StagingValidationError("OIDC discovery and JWKS documents must be JSON objects")
    if discovery.get("issuer") != issuer:
        raise StagingValidationError("OIDC discovery issuer does not exactly match configured issuer")
    if discovery.get("jwks_uri") != jwks_url:
        raise StagingValidationError("OIDC discovery JWKS URI does not match configured JWKS URL")

    advertised = discovery.get("id_token_signing_alg_values_supported")
    if not isinstance(advertised, list):
        raise StagingValidationError("Provider does not advertise signing algorithms")
    algorithms = {
        value for value in advertised
        if isinstance(value, str) and value in _ALLOWED_ALGORITHMS
    }
    if not algorithms:
        raise StagingValidationError("Provider does not advertise an accepted signing algorithm")

    keys = jwks.get("keys")
    if not isinstance(keys, list):
        raise StagingValidationError("JWKS document has no key list")

    key_ids = [
        key["kid"] for key in keys
        if isinstance(key, dict) and isinstance(key.get("kid"), str) and key["kid"]
    ]
    if len(key_ids) != len(set(key_ids)):
        raise StagingValidationError("JWKS contains ambiguous duplicate signing key IDs")

    usable_key_ids: set[str] = set()
    for key in keys:
        if (
            not isinstance(key, dict)
            or not isinstance(key.get("kid"), str)
            or not key["kid"]
            or key.get("use", "sig") != "sig"
        ):
            continue
        key_ops = key.get("key_ops")
        if key_ops is not None and (
            not isinstance(key_ops, list)
            or not all(isinstance(operation, str) for operation in key_ops)
            or "verify" not in key_ops
        ):
            continue
        key_algorithm = key.get("alg")
        if key_algorithm is not None and (
            not isinstance(key_algorithm, str)
            or key_algorithm not in algorithms
        ):
            continue

        candidates = ({key_algorithm} if key_algorithm else algorithms)
        for algorithm in candidates:
            expected_kty = "RSA" if algorithm == "RS256" else "EC"
            if key.get("kty") != expected_kty:
                continue
            try:
                # Parse the actual public key parameters instead of treating a kid/kty
                # label as proof that the JWKS entry can verify a token.
                jwt.PyJWK.from_dict(key, algorithm=algorithm)
            except (jwt.PyJWTError, ValueError, TypeError, OverflowError):
                continue
            usable_key_ids.add(key["kid"])
            break

    if not usable_key_ids:
        raise StagingValidationError("JWKS has no usable RSA or EC verification key")


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise StagingValidationError(f"Required staging setting {name} is missing")
    return value


def _https_url(name: str, value: str) -> str:
    parsed = urlsplit(value)
    if (
        parsed.scheme != "https" or not parsed.hostname
        or parsed.username is not None or parsed.password is not None
        or parsed.query or parsed.fragment
    ):
        raise StagingValidationError(f"{name} must be an HTTPS URL without user info, query or fragment")
    return value.rstrip("/")


def _request_json(url: str, *, label: str, bearer_token: str | None = None) -> dict[str, Any]:
    headers = {"Accept": "application/json"}
    if bearer_token is not None:
        headers["Authorization"] = f"Bearer {bearer_token}"
    request = Request(url, headers=headers)
    opener = build_opener(
        HTTPSHandler(context=ssl.create_default_context()),
        _NoRedirect(),
    )
    try:
        with opener.open(request, timeout=10) as response:
            if urlsplit(response.geturl()).scheme != "https":
                raise StagingValidationError(f"{label} left HTTPS")
            raw = response.read(_MAX_RESPONSE_BYTES + 1)
    except HTTPError as exc:
        raise StagingValidationError(f"{label} returned HTTP {exc.code}") from None
    except URLError:
        raise StagingValidationError(f"{label} HTTPS request failed") from None
    if len(raw) > _MAX_RESPONSE_BYTES:
        raise StagingValidationError(f"{label} response exceeded the size limit")
    try:
        result = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise StagingValidationError(f"{label} did not return valid JSON") from None
    if not isinstance(result, dict):
        raise StagingValidationError(f"{label} did not return a JSON object")
    return result


def run_checks() -> list[str]:
    try:
        settings = get_settings()
    except Exception:
        raise StagingValidationError("ENTITY service configuration is invalid") from None
    if settings.environment != "staging":
        raise StagingValidationError("Set ENTITY_ENVIRONMENT=staging before running this check")

    base_url = _https_url("ENTITY_STAGING_BASE_URL", _required("ENTITY_STAGING_BASE_URL"))
    owner_subject = _required("ENTITY_STAGING_OWNER_SUBJECT")
    owner_token = _required("ENTITY_STAGING_OWNER_TOKEN")
    registry_token = _required("ENTITY_STAGING_REGISTRY_TOKEN")

    discovery_url = settings.oidc_issuer.rstrip("/") + "/.well-known/openid-configuration"
    discovery = _request_json(discovery_url, label="OIDC discovery")
    jwks = _request_json(settings.oidc_jwks_url, label="OIDC JWKS")
    validate_provider_documents(settings.oidc_issuer, settings.oidc_jwks_url, discovery, jwks)

    owner = _request_json(
        base_url + "/v1/auth/me", label="Owner staging authentication", bearer_token=owner_token,
    )
    if (
        owner.get("subject") != owner_subject
        or owner.get("rank") != 0
        or owner.get("active") is not True
    ):
        raise StagingValidationError("Staging Owner token did not resolve to the expected active Owner")

    audit = _request_json(
        base_url + "/v1/admin/audit/verify", label="Owner MFA and audit verification",
        bearer_token=owner_token,
    )
    if audit.get("valid") is not True or audit.get("events_checked") != audit.get("event_count"):
        raise StagingValidationError("Staging Owner step-up or audit-chain verification failed")

    registry = _request_json(
        base_url + "/v1/internal/resource-registry/verify",
        label="Trusted resource-registry authentication",
        bearer_token=registry_token,
    )
    if registry.get("status") != "ok":
        raise StagingValidationError("Staging resource-registry identity was not accepted")

    return [
        "OIDC discovery and configured JWKS match",
        "staging Owner token resolves to the expected active Owner and passes fresh-MFA enforcement",
        "staging audit chain verifies",
        "resource-registry token matches the configured audience, subject allowlist and active service account",
    ]


def main() -> None:
    try:
        checks = run_checks()
    except StagingValidationError as exc:
        print(f"STAGING CHECK FAILED: {exc}", file=sys.stderr)
        raise SystemExit(1) from None
    for check in checks:
        print(f"PASS: {check}")


if __name__ == "__main__":
    main()
