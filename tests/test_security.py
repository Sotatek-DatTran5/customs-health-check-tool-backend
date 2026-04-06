"""Unit tests for core security functions."""
from app.core.security import (
    hash_password,
    verify_password,
    validate_password_strength,
    create_access_token,
    create_refresh_token,
    decode_access_token,
)


def test_hash_and_verify():
    pw = "MySecret@123"
    hashed = hash_password(pw)
    assert hashed != pw
    assert verify_password(pw, hashed)
    assert not verify_password("wrong", hashed)


def test_validate_password_strength():
    assert validate_password_strength("short") is not None  # too short
    assert validate_password_strength("alllowercase1") is not None  # no upper
    assert validate_password_strength("ALLUPPERCASE1") is not None  # no lower
    assert validate_password_strength("NoDigits!") is not None  # no digit
    assert validate_password_strength("Valid@123") is None  # valid


def test_access_token_roundtrip():
    data = {"user_id": 1, "tenant_id": 2, "role": "user"}
    token = create_access_token(data)
    decoded = decode_access_token(token)
    assert decoded["user_id"] == 1
    assert decoded["type"] == "access"


def test_refresh_token_type():
    data = {"user_id": 1}
    token = create_refresh_token(data)
    decoded = decode_access_token(token)
    assert decoded["type"] == "refresh"
