import pytest
from app.core.token import create_access_token, create_refresh_token, create_reset_token, decode_token
from app.exceptions import AuthenticationError


def test_create_access_token_has_correct_claims():
    """Ensure that a created access token includes type and expiration claims"""
    token = create_access_token({"sub": "1", "role": "STUDENT"})
    payload = decode_token(token, exp_type="access")
    assert payload["type"] == "access"
    assert payload["sub"] == "1"
    assert "exp" in payload


def test_create_refresh_token_has_correct_claims():
    """Ensure that a created refresh token includes type and expiration claims"""
    token = create_refresh_token({"sub": "1", "role": "STUDENT"})
    payload = decode_token(token, exp_type="refresh")
    assert payload["type"] == "refresh"
    assert payload["sub"] == "1"


def test_decode_token_wrong_type_fails():
    """Ensure that decoding fails when a refresh token is supplied where an access token is expected"""
    token = create_refresh_token({"sub": "1", "role": "STUDENT"})
    with pytest.raises(AuthenticationError):
        decode_token(token, exp_type="access")


def test_decode_token_invalid_signature_fails():
    """Ensure that decoding fails when a token with an invalid signature is provided"""
    with pytest.raises(AuthenticationError):
        decode_token("not.a.valid.token", exp_type="access")


def test_create_reset_token_has_correct_claims():
    """Ensure that a created reset token contains type='reset', custom claims, and expiration"""
    token = create_reset_token({
        "sub": "1",
        "email": "user@example.com",
        "pwd": "a1b2c3d4e5f6g7h8",
    })
    payload = decode_token(token, exp_type="reset")
    assert payload["type"] == "reset"
    assert payload["sub"] == "1"
    assert payload["email"] == "user@example.com"
    assert payload["pwd"] == "a1b2c3d4e5f6g7h8"
    assert "exp" in payload


def test_decode_reset_token_with_wrong_exp_type_fails():
    """Ensure that decoding a reset token expecting access token fails"""
    token = create_reset_token({"sub": "1", "email": "user@example.com", "pwd": "fingerprint12345"})
    with pytest.raises(AuthenticationError):
        decode_token(token, exp_type="access")


def test_decode_access_token_with_reset_exp_type_fails():
    """Ensure that decoding an access token expecting reset token fails"""
    token = create_access_token({"sub": "1", "role": "STUDENT"})
    with pytest.raises(AuthenticationError):
        decode_token(token, exp_type="reset")
