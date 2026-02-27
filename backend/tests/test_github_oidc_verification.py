import base64
import json

import jwt
import pytest

from app.security import oidc_providers as op


def _make_dummy_jwt_with_header(header: dict) -> str:
    """Create a syntactically valid JWT string with the given header and dummy payload/signature."""
    header_b64 = base64.urlsafe_b64encode(json.dumps(header).encode("utf-8")).rstrip(b"=").decode("ascii")
    payload_b64 = base64.urlsafe_b64encode(b"{}").rstrip(b"=").decode("ascii")
    return f"{header_b64}.{payload_b64}.signature"


def test_jwt_header_kid_extraction():
    """Ensure we can extract 'kid' from a JWT header."""
    token = _make_dummy_jwt_with_header({"kid": "test-kid", "alg": "RS256"})
    header = jwt.get_unverified_header(token)
    assert header["kid"] == "test-kid"


def test_verify_github_oidc_uses_kid_and_validates_aud(monkeypatch):
    """verify_github_oidc_token should select the correct JWK by kid and require aud contains 'thandev'."""

    # Force get_unverified_header to return a known kid without needing a real signed token.
    def fake_get_unverified_header(_token: str):
        return {"kid": "good-kid", "alg": "RS256"}

    monkeypatch.setattr(op.jwt, "get_unverified_header", fake_get_unverified_header)

    # Stub discovery + JWKS
    def fake_get_github_openid_configuration():
        return {"jwks_uri": "https://example.com/jwks"}

    monkeypatch.setattr(op, "_get_github_openid_configuration", fake_get_github_openid_configuration)

    def fake_get_jwks(uri: str):
        assert uri == "https://example.com/jwks"
        return {
            "keys": [
                {"kid": "other-kid", "kty": "RSA", "n": "n1", "e": "AQAB"},
                {"kid": "good-kid", "kty": "RSA", "n": "n2", "e": "AQAB"},
            ]
        }

    monkeypatch.setattr(op, "_get_jwks", fake_get_jwks)

    captured_jwk = {}

    def fake_from_jwk(jwk_json: str):
        jwk_dict = json.loads(jwk_json)
        captured_jwk.update(jwk_dict)
        return "PUBLIC_KEY"

    monkeypatch.setattr(op.algorithms.RSAAlgorithm, "from_jwk", staticmethod(fake_from_jwk))

    def fake_decode(token: str, key: str, algorithms, issuer=None, options=None):
        # Ensure we got the key built from the selected JWK and correct issuer.
        assert key == "PUBLIC_KEY"
        assert issuer == op.GITHUB_CONFIG.issuer
        # Return payload with acceptable audience.
        return {"aud": ["something", "thandev"], "iss": issuer}

    monkeypatch.setattr(op.jwt, "decode", fake_decode)

    payload = op.verify_github_oidc_token("dummy-token")
    assert "thandev" in payload["aud"]
    # Ensure the JWK used to build the key matches the expected kid
    assert captured_jwk["kid"] == "good-kid"


def test_verify_github_oidc_rejects_wrong_aud(monkeypatch):
    """verify_github_oidc_token should fail when aud does not contain 'thandev'."""

    def fake_get_unverified_header(_token: str):
        return {"kid": "good-kid", "alg": "RS256"}

    monkeypatch.setattr(op.jwt, "get_unverified_header", fake_get_unverified_header)

    def fake_get_github_openid_configuration():
        return {"jwks_uri": "https://example.com/jwks"}

    monkeypatch.setattr(op, "_get_github_openid_configuration", fake_get_github_openid_configuration)

    def fake_get_jwks(uri: str):
        return {"keys": [{"kid": "good-kid", "kty": "RSA", "n": "n", "e": "AQAB"}]}

    monkeypatch.setattr(op, "_get_jwks", fake_get_jwks)

    def fake_from_jwk(jwk_json: str):
        return "PUBLIC_KEY"

    monkeypatch.setattr(op.algorithms.RSAAlgorithm, "from_jwk", staticmethod(fake_from_jwk))

    def fake_decode(token: str, key: str, algorithms, issuer=None, options=None):
        return {"aud": "wrong-audience", "iss": issuer}

    monkeypatch.setattr(op.jwt, "decode", fake_decode)

    with pytest.raises(ValueError) as excinfo:
        op.verify_github_oidc_token("dummy-token")
    assert "audience must contain 'thandev'" in str(excinfo.value)

