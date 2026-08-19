"""Tests for Module 1: Authentication endpoints."""
import pytest

from tests.conftest import signup_plain_user

VALID_SIGNUP = {
    "email": "hafiz@hms.com",
    "password": "Strong1!",
    "first_name": "Hafiz",
    "last_name": "Sahi",
    "gender": "male",
    "dob": "1998-05-10",
    "primary_phone": "03001234567",
}


def test_signup_success(client):
    resp = client.post("/api/v1/auth/signup", json=VALID_SIGNUP)
    assert resp.status_code == 201
    body = resp.json()
    assert body["email"] == VALID_SIGNUP["email"]
    assert body["profile"]["first_name"] == "Hafiz"
    assert body["contact"]["primary_phone"] == "03001234567"


@pytest.mark.parametrize(
    "bad_password",
    ["weak", "alllowercase1!", "ALLUPPERCASE1!", "NoDigitsHere!", "NoSpecialChar1"],
)
def test_signup_weak_password_rejected(client, bad_password):
    payload = {**VALID_SIGNUP, "password": bad_password}
    resp = client.post("/api/v1/auth/signup", json=payload)
    assert resp.status_code == 422


def test_signup_missing_phone_rejected(client):
    payload = {k: v for k, v in VALID_SIGNUP.items() if k != "primary_phone"}
    resp = client.post("/api/v1/auth/signup", json=payload)
    assert resp.status_code == 422


def test_signup_duplicate_email_rejected(client):
    client.post("/api/v1/auth/signup", json=VALID_SIGNUP)
    resp = client.post("/api/v1/auth/signup", json=VALID_SIGNUP)
    assert resp.status_code == 400


def test_login_success(client):
    client.post("/api/v1/auth/signup", json=VALID_SIGNUP)
    resp = client.post("/api/v1/auth/login", json={"email": VALID_SIGNUP["email"], "password": VALID_SIGNUP["password"]})
    assert resp.status_code == 200
    assert "access_token" in resp.json()
    assert "refresh_token" in resp.json()


def test_login_wrong_password_rejected(client):
    client.post("/api/v1/auth/signup", json=VALID_SIGNUP)
    resp = client.post("/api/v1/auth/login", json={"email": VALID_SIGNUP["email"], "password": "WrongPass1!"})
    assert resp.status_code == 401


def test_login_nonexistent_email_rejected(client):
    resp = client.post("/api/v1/auth/login", json={"email": "nobody@hms.com", "password": "Whatever1!"})
    assert resp.status_code == 401


def test_refresh_with_bogus_token_rejected(client):
    resp = client.post("/api/v1/auth/refresh", json={"refresh_token": "not-a-real-token"})
    assert resp.status_code == 401


def test_get_me_without_token_rejected(client):
    resp = client.get("/api/v1/users/me")
    assert resp.status_code == 401


def test_get_me_with_valid_token_succeeds(client):
    signup_plain_user(client, "self@hms.com")
    login = client.post("/api/v1/auth/login", json={"email": "self@hms.com", "password": "Plain123!"})
    token = login.json()["access_token"]
    resp = client.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["email"] == "self@hms.com"
