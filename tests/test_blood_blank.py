"""Tests for Module 7: Blood Bank."""
from tests.conftest import signup_plain_user


def _setup_patient(client, auth_headers, email="bloodpat@hms.com", code="MRN-BLOOD"):
    user = signup_plain_user(client, email)
    return client.post(
        "/api/v1/patients", json={"user_id": user["id"], "patient_code": code, "blood_group": "O+"}, headers=auth_headers
    ).json()


# =========================================================================
# INVENTORY
# =========================================================================
def test_upsert_inventory_creates_new_record(client, auth_headers):
    resp = client.put("/api/v1/blood-bank/inventory", json={"blood_group": "O+", "available_units": 50}, headers=auth_headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["available_units"] == 50
    assert body["last_updated_by"] is not None  # stamped from the authenticated caller


def test_upsert_inventory_updates_existing_record(client, auth_headers):
    client.put("/api/v1/blood-bank/inventory", json={"blood_group": "A+", "available_units": 20}, headers=auth_headers)
    resp = client.put("/api/v1/blood-bank/inventory", json={"blood_group": "A+", "available_units": 35}, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["available_units"] == 35

    # confirm it's still ONE row, not a duplicate
    all_inventory = client.get("/api/v1/blood-bank/inventory", headers=auth_headers).json()
    a_pos_rows = [r for r in all_inventory if r["blood_group"] == "A+"]
    assert len(a_pos_rows) == 1


def test_invalid_blood_group_format_rejected(client, auth_headers):
    resp = client.put("/api/v1/blood-bank/inventory", json={"blood_group": "Z+", "available_units": 10}, headers=auth_headers)
    assert resp.status_code == 422


def test_negative_units_rejected(client, auth_headers):
    resp = client.put("/api/v1/blood-bank/inventory", json={"blood_group": "B+", "available_units": -5}, headers=auth_headers)
    assert resp.status_code == 422


def test_inventory_update_requires_permission(client, auth_headers):
    plain = signup_plain_user(client, "noperm@hms.com")
    login = client.post("/api/v1/auth/login", json={"email": "noperm@hms.com", "password": "Plain123!"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    resp = client.put("/api/v1/blood-bank/inventory", json={"blood_group": "AB-", "available_units": 5}, headers=headers)
    assert resp.status_code == 403


# =========================================================================
# BLOOD REQUESTS
# =========================================================================
def test_create_blood_request(client, auth_headers):
    patient = _setup_patient(client, auth_headers)
    resp = client.post(
        "/api/v1/blood-bank/requests",
        json={"patient_id": patient["id"], "blood_group": "O+", "units_required": 2},
        headers=auth_headers,
    )
    assert resp.status_code == 201
    assert resp.json()["status"] == "pending"


def test_create_blood_request_invalid_blood_group_rejected(client, auth_headers):
    patient = _setup_patient(client, auth_headers, email="bloodpat2@hms.com", code="MRN-BLOOD2")
    resp = client.post(
        "/api/v1/blood-bank/requests",
        json={"patient_id": patient["id"], "blood_group": "Z-", "units_required": 1},
        headers=auth_headers,
    )
    assert resp.status_code == 422


def test_create_blood_request_zero_units_rejected(client, auth_headers):
    patient = _setup_patient(client, auth_headers, email="bloodpat3@hms.com", code="MRN-BLOOD3")
    resp = client.post(
        "/api/v1/blood-bank/requests",
        json={"patient_id": patient["id"], "blood_group": "O+", "units_required": 0},
        headers=auth_headers,
    )
    assert resp.status_code == 422


def test_create_blood_request_nonexistent_patient_rejected(client, auth_headers):
    resp = client.post(
        "/api/v1/blood-bank/requests",
        json={"patient_id": 9999, "blood_group": "O+", "units_required": 1},
        headers=auth_headers,
    )
    assert resp.status_code == 404


# =========================================================================
# APPROVAL WORKFLOW (the core business logic)
# =========================================================================
def test_approve_request_deducts_inventory(client, auth_headers):
    patient = _setup_patient(client, auth_headers, email="approve1@hms.com", code="MRN-APPR1")
    client.put("/api/v1/blood-bank/inventory", json={"blood_group": "O+", "available_units": 10}, headers=auth_headers)

    req = client.post(
        "/api/v1/blood-bank/requests",
        json={"patient_id": patient["id"], "blood_group": "O+", "units_required": 4},
        headers=auth_headers,
    ).json()

    resp = client.patch(f"/api/v1/blood-bank/requests/{req['id']}/decision", json={"status": "approved"}, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"

    inventory = client.get("/api/v1/blood-bank/inventory", headers=auth_headers).json()
    o_pos = next(r for r in inventory if r["blood_group"] == "O+")
    assert o_pos["available_units"] == 6  # 10 - 4


def test_approve_request_insufficient_stock_rejected(client, auth_headers):
    patient = _setup_patient(client, auth_headers, email="approve2@hms.com", code="MRN-APPR2")
    client.put("/api/v1/blood-bank/inventory", json={"blood_group": "AB-", "available_units": 2}, headers=auth_headers)

    req = client.post(
        "/api/v1/blood-bank/requests",
        json={"patient_id": patient["id"], "blood_group": "AB-", "units_required": 5},
        headers=auth_headers,
    ).json()

    resp = client.patch(f"/api/v1/blood-bank/requests/{req['id']}/decision", json={"status": "approved"}, headers=auth_headers)
    assert resp.status_code == 400

    # inventory must be UNCHANGED after a rejected approval attempt
    inventory = client.get("/api/v1/blood-bank/inventory", headers=auth_headers).json()
    ab_neg = next(r for r in inventory if r["blood_group"] == "AB-")
    assert ab_neg["available_units"] == 2


def test_approve_request_with_no_inventory_record_rejected(client, auth_headers):
    patient = _setup_patient(client, auth_headers, email="approve3@hms.com", code="MRN-APPR3")
    req = client.post(
        "/api/v1/blood-bank/requests",
        json={"patient_id": patient["id"], "blood_group": "B-", "units_required": 1},  # B- never seeded into inventory
        headers=auth_headers,
    ).json()

    resp = client.patch(f"/api/v1/blood-bank/requests/{req['id']}/decision", json={"status": "approved"}, headers=auth_headers)
    assert resp.status_code == 404


def test_reject_request_does_not_touch_inventory(client, auth_headers):
    patient = _setup_patient(client, auth_headers, email="reject1@hms.com", code="MRN-REJ1")
    client.put("/api/v1/blood-bank/inventory", json={"blood_group": "A-", "available_units": 10}, headers=auth_headers)

    req = client.post(
        "/api/v1/blood-bank/requests",
        json={"patient_id": patient["id"], "blood_group": "A-", "units_required": 3},
        headers=auth_headers,
    ).json()

    resp = client.patch(f"/api/v1/blood-bank/requests/{req['id']}/decision", json={"status": "rejected"}, headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "rejected"

    inventory = client.get("/api/v1/blood-bank/inventory", headers=auth_headers).json()
    a_neg = next(r for r in inventory if r["blood_group"] == "A-")
    assert a_neg["available_units"] == 10  # untouched


def test_cannot_redecide_already_processed_request(client, auth_headers):
    patient = _setup_patient(client, auth_headers, email="redecide@hms.com", code="MRN-REDEC")
    client.put("/api/v1/blood-bank/inventory", json={"blood_group": "O-", "available_units": 20}, headers=auth_headers)

    req = client.post(
        "/api/v1/blood-bank/requests",
        json={"patient_id": patient["id"], "blood_group": "O-", "units_required": 2},
        headers=auth_headers,
    ).json()

    client.patch(f"/api/v1/blood-bank/requests/{req['id']}/decision", json={"status": "approved"}, headers=auth_headers)

    # trying to decide it again (even to reject) must fail
    second = client.patch(f"/api/v1/blood-bank/requests/{req['id']}/decision", json={"status": "rejected"}, headers=auth_headers)
    assert second.status_code == 400


def test_processed_by_is_stamped_on_decision(client, auth_headers):
    patient = _setup_patient(client, auth_headers, email="stamp@hms.com", code="MRN-STAMP")
    client.put("/api/v1/blood-bank/inventory", json={"blood_group": "B+", "available_units": 10}, headers=auth_headers)

    req = client.post(
        "/api/v1/blood-bank/requests",
        json={"patient_id": patient["id"], "blood_group": "B+", "units_required": 1},
        headers=auth_headers,
    ).json()
    assert req["processed_by"] is None

    decided = client.patch(f"/api/v1/blood-bank/requests/{req['id']}/decision", json={"status": "approved"}, headers=auth_headers).json()
    assert decided["processed_by"] is not None


def test_decision_requires_bloodbank_approve_permission(client, auth_headers):
    patient = _setup_patient(client, auth_headers, email="noapprove@hms.com", code="MRN-NOAPPR")
    client.put("/api/v1/blood-bank/inventory", json={"blood_group": "AB+", "available_units": 10}, headers=auth_headers)
    req = client.post(
        "/api/v1/blood-bank/requests",
        json={"patient_id": patient["id"], "blood_group": "AB+", "units_required": 1},
        headers=auth_headers,
    ).json()

    plain = signup_plain_user(client, "noapprove_user@hms.com")
    login = client.post("/api/v1/auth/login", json={"email": "noapprove_user@hms.com", "password": "Plain123!"})
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    resp = client.patch(f"/api/v1/blood-bank/requests/{req['id']}/decision", json={"status": "approved"}, headers=headers)
    assert resp.status_code == 403
