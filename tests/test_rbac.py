"""Tests for Module 1: Roles, Permissions, and RBAC assignment."""
from tests.conftest import signup_plain_user


def test_create_role_without_token_rejected(client):
    resp = client.post("/api/v1/roles", json={"name": "doctor"})
    assert resp.status_code == 401


def test_regular_user_without_permission_forbidden(client):
    """The core bootstrap problem: a plain signed-up user has zero roles/permissions."""
    signup_plain_user(client, "plain@hms.com")
    login = client.post("/api/v1/auth/login", json={"email": "plain@hms.com", "password": "Plain123!"})
    token = login.json()["access_token"]

    resp = client.post(
        "/api/v1/roles", json={"name": "doctor"}, headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 403
    assert "iam:manage_roles" in resp.json()["detail"]


def test_superadmin_bypasses_all_permission_checks(client, auth_headers):
    resp = client.post("/api/v1/roles", json={"name": "doctor"}, headers=auth_headers)
    assert resp.status_code == 201


def test_create_role_duplicate_name_rejected(client, auth_headers):
    client.post("/api/v1/roles", json={"name": "doctor"}, headers=auth_headers)
    resp = client.post("/api/v1/roles", json={"name": "doctor"}, headers=auth_headers)
    assert resp.status_code == 400


def test_create_permission_duplicate_code_rejected(client, auth_headers):
    client.post("/api/v1/permissions", json={"name": "Create Appointment", "code": "appointments:create"}, headers=auth_headers)
    resp = client.post("/api/v1/permissions", json={"name": "Duplicate Attempt", "code": "appointments:create"}, headers=auth_headers)
    assert resp.status_code == 400


def test_assign_multiple_permissions_to_one_role(client, auth_headers):
    role = client.post("/api/v1/roles", json={"name": "doctor"}, headers=auth_headers).json()
    perm1 = client.post("/api/v1/permissions", json={"name": "Create Appt", "code": "appointments:create"}, headers=auth_headers).json()
    perm2 = client.post("/api/v1/permissions", json={"name": "View Appt", "code": "appointments:view"}, headers=auth_headers).json()

    r1 = client.post("/api/v1/permissions/assign", json={"role_id": role["id"], "permission_id": perm1["id"]}, headers=auth_headers)
    r2 = client.post("/api/v1/permissions/assign", json={"role_id": role["id"], "permission_id": perm2["id"]}, headers=auth_headers)
    assert r1.status_code == 200
    assert r2.status_code == 200

    detail = client.get(f"/api/v1/roles/{role['id']}", headers=auth_headers).json()
    codes = {p["code"] for p in detail["permissions"]}
    assert codes == {"appointments:create", "appointments:view"}


def test_assign_multiple_roles_to_one_user(client, auth_headers):
    user = signup_plain_user(client, "multi@hms.com")
    role_a = client.post("/api/v1/roles", json={"name": "doctor"}, headers=auth_headers).json()
    role_b = client.post("/api/v1/roles", json={"name": "department_head"}, headers=auth_headers).json()

    r1 = client.post("/api/v1/roles/assign", json={"user_id": user["id"], "role_id": role_a["id"]}, headers=auth_headers)
    r2 = client.post("/api/v1/roles/assign", json={"user_id": user["id"], "role_id": role_b["id"]}, headers=auth_headers)
    assert r1.status_code == 200
    assert r2.status_code == 200


def test_assigned_permission_actually_grants_access(client, auth_headers):
    """End-to-end: assign the real iam:manage_roles permission to a new role,
    give that role to a plain user, and verify the user can now genuinely
    create roles (this is what actually matters, not just a 403 vs 401 check)."""
    # iam:manage_roles already exists (seeded for superadmin) — reuse it via the list endpoint
    all_perms = client.get("/api/v1/permissions", headers=auth_headers).json()
    manage_roles_perm = next(p for p in all_perms if p["code"] == "iam:manage_roles")

    role = client.post("/api/v1/roles", json={"name": "role_manager"}, headers=auth_headers).json()
    client.post(
        "/api/v1/permissions/assign", json={"role_id": role["id"], "permission_id": manage_roles_perm["id"]}, headers=auth_headers
    )

    user = signup_plain_user(client, "empowered@hms.com")
    client.post("/api/v1/roles/assign", json={"user_id": user["id"], "role_id": role["id"]}, headers=auth_headers)

    login = client.post("/api/v1/auth/login", json={"email": "empowered@hms.com", "password": "Plain123!"})
    token = login.json()["access_token"]

    resp = client.post(
        "/api/v1/roles", json={"name": "nurse"}, headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 201  # this user now genuinely has iam:manage_roles


def test_unassign_role_removes_access(client, auth_headers):
    all_perms = client.get("/api/v1/permissions", headers=auth_headers).json()
    manage_roles_perm = next(p for p in all_perms if p["code"] == "iam:manage_roles")

    role = client.post("/api/v1/roles", json={"name": "temp_role"}, headers=auth_headers).json()
    client.post(
        "/api/v1/permissions/assign", json={"role_id": role["id"], "permission_id": manage_roles_perm["id"]}, headers=auth_headers
    )

    user = signup_plain_user(client, "revoked@hms.com")
    client.post("/api/v1/roles/assign", json={"user_id": user["id"], "role_id": role["id"]}, headers=auth_headers)
    unassign_resp = client.request(
        "DELETE", "/api/v1/roles/unassign", json={"user_id": user["id"], "role_id": role["id"]}, headers=auth_headers
    )
    assert unassign_resp.status_code == 200

    login = client.post("/api/v1/auth/login", json={"email": "revoked@hms.com", "password": "Plain123!"})
    token = login.json()["access_token"]
    resp = client.post("/api/v1/roles", json={"name": "some_role"}, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 403  # role removed -> permission gone -> back to forbidden
